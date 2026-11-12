"""Pruebas unitarias de endpoints de Sesiones de Carga Prefirmada (CDM-29 / CDM-30).

Prueba los contratos HTTP, códigos de estado (201, 401, 403, 404, 413, 415, 422),
autorización por rol (OWNER, ADMIN, EDITOR, MEMBER, VIEWER, EXTERNAL),
generación de URL prefirmada S3, persistencia en BD y ausencia de credenciales AWS.
"""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from cdm.adapters.inbound.http.auth import get_current_user
from cdm.adapters.inbound.http.dependencies import get_db_session
from cdm.adapters.outbound.persistence.models import (
    Base,
    DocumentModel,
    UploadSessionModel,
    UserModel,
    WorkspaceMembershipModel,
    WorkspaceModel,
)
from cdm.bootstrap.app import create_app
from cdm.config.settings import Settings
from cdm.domain.document import DocumentStatus
from cdm.domain.identity import AuthenticatedUser
from cdm.domain.upload_session import UploadSessionStatus
from cdm.domain.workspace import MembershipStatus, WorkspaceRole


@pytest.fixture
def sqlite_session() -> Iterator[Session]:
    """Crea una base de datos SQLite en memoria para la prueba."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def app(sqlite_session: Session) -> FastAPI:
    """Instancia la aplicación FastAPI configurada para pruebas."""
    settings = Settings(
        database_url="sqlite:///:memory:",
        cors_origins="*",
        cognito_user_pool_id="us-east-1_mock",
        cognito_client_id="mock-client-id",
        cognito_region="us-east-1",
        max_upload_size_bytes=10 * 1024 * 1024,  # 10 MB para pruebas
        upload_url_expires_in_seconds=900,
    )
    application = create_app(settings)

    def override_db() -> Iterator[Session]:
        yield sqlite_session

    application.dependency_overrides[get_db_session] = override_db
    return application


@pytest.fixture
def test_client(app: FastAPI) -> TestClient:
    """Crea el cliente HTTP de pruebas."""
    return TestClient(app)


def _seed_workspace_and_member(
    session: Session, role: WorkspaceRole
) -> tuple[UserModel, WorkspaceModel, WorkspaceMembershipModel]:
    """Crea un usuario, workspace y membresía con el rol especificado."""
    user = UserModel(id=uuid4(), cognito_sub=f"sub-{uuid4().hex[:8]}", email="user@test.com")
    workspace = WorkspaceModel(
        id=uuid4(), name="Test WS", slug=f"ws-{uuid4().hex[:6]}", created_by=user.id
    )
    membership = WorkspaceMembershipModel(
        id=uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role=role.value,
        status=MembershipStatus.ACTIVE.value,
    )
    session.add_all([user, workspace, membership])
    session.commit()
    return user, workspace, membership


# --- Tests de Autenticación y Autorización ---


def test_upload_session_unauthenticated_returns_401(test_client: TestClient) -> None:
    """Solicitar sesión de carga sin token devuelve 401 missing_token."""
    ws_id = uuid4()
    response = test_client.post(
        f"/api/v1/workspaces/{ws_id}/upload-sessions",
        json={
            "original_filename": "reporte.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_token"


def test_upload_session_external_user_returns_404_anti_idor(
    test_client: TestClient, app: FastAPI, sqlite_session: Session
) -> None:
    """Usuario sin membresía en el workspace recibe 404 (evita enumeración de tenants)."""
    _user, ws, _ = _seed_workspace_and_member(sqlite_session, WorkspaceRole.MEMBER)

    external_user = AuthenticatedUser(
        cognito_sub="sub-external-123",
        email="external@test.com",
    )
    app.dependency_overrides[get_current_user] = lambda: external_user

    response = test_client.post(
        f"/api/v1/workspaces/{ws.id}/upload-sessions",
        json={
            "original_filename": "reporte.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
        },
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "workspace_not_found"


def test_upload_session_viewer_role_returns_403(
    test_client: TestClient, app: FastAPI, sqlite_session: Session
) -> None:
    """El rol VIEWER no tiene permisos para subir documentos (403 permission_denied)."""
    user, ws, _ = _seed_workspace_and_member(sqlite_session, WorkspaceRole.VIEWER)

    auth_user = AuthenticatedUser(cognito_sub=user.cognito_sub, email=user.email)
    app.dependency_overrides[get_current_user] = lambda: auth_user

    response = test_client.post(
        f"/api/v1/workspaces/{ws.id}/upload-sessions",
        json={
            "original_filename": "reporte.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


@pytest.mark.parametrize(
    "role",
    [WorkspaceRole.MEMBER, WorkspaceRole.EDITOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER],
)
def test_upload_session_allowed_roles_return_201(
    test_client: TestClient, app: FastAPI, sqlite_session: Session, role: WorkspaceRole
) -> None:
    """Roles MEMBER, EDITOR, ADMIN y OWNER pueden iniciar sesiones de carga exitosamente."""
    user, ws, _ = _seed_workspace_and_member(sqlite_session, role)

    auth_user = AuthenticatedUser(cognito_sub=user.cognito_sub, email=user.email)
    app.dependency_overrides[get_current_user] = lambda: auth_user

    response = test_client.post(
        f"/api/v1/workspaces/{ws.id}/upload-sessions",
        json={
            "original_filename": "balance.pdf",
            "content_type": "application/pdf",
            "size_bytes": 2048,
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]

    # Verificación de estructura de respuesta
    assert "upload_session_id" in data
    assert "document_id" in data
    assert "upload_url" in data
    assert "storage_key" in data
    assert data["expires_in_seconds"] == 900
    assert data["required_headers"] == {"Content-Type": "application/pdf"}

    # Verificación de aislamiento de storage_key bajo el tenant
    assert data["storage_key"].startswith(f"workspaces/{ws.id}/documents/{data['document_id']}/")
    assert data["storage_key"].endswith(".pdf")

    # Cero credenciales AWS en la respuesta
    body_str = str(response.json())
    assert "aws_access_key_id" not in body_str.lower()
    assert "aws_secret_access_key" not in body_str.lower()
    assert "session_token" not in body_str.lower()


def test_upload_session_persists_pending_records_in_db(
    test_client: TestClient, app: FastAPI, sqlite_session: Session
) -> None:
    """La sesión de carga crea Document en PENDING_UPLOAD y UploadSession en PENDING en BD."""
    user, ws, _ = _seed_workspace_and_member(sqlite_session, WorkspaceRole.MEMBER)

    auth_user = AuthenticatedUser(cognito_sub=user.cognito_sub, email=user.email)
    app.dependency_overrides[get_current_user] = lambda: auth_user

    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    response = test_client.post(
        f"/api/v1/workspaces/{ws.id}/upload-sessions",
        json={
            "original_filename": "contrato_final.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1048576,
            "checksum_sha256": sha256,
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    doc_id = UUID(data["document_id"])
    session_id = UUID(data["upload_session_id"])

    # Verificar registro en tabla documents
    doc_model = sqlite_session.get(DocumentModel, doc_id)
    assert doc_model is not None
    assert doc_model.workspace_id == ws.id
    assert doc_model.uploaded_by == user.id
    assert doc_model.original_filename == "contrato_final.pdf"
    assert doc_model.status == DocumentStatus.PENDING_UPLOAD.value
    assert doc_model.size_bytes == 1048576
    assert doc_model.checksum_sha256 == sha256

    # Verificar registro en tabla upload_sessions
    session_model = sqlite_session.get(UploadSessionModel, session_id)
    assert session_model is not None
    assert session_model.workspace_id == ws.id
    assert session_model.user_id == user.id
    assert session_model.document_id == doc_id
    assert session_model.status == UploadSessionStatus.PENDING.value
    assert session_model.expected_size_bytes == 1048576
    assert session_model.expected_checksum_sha256 == sha256


# --- Tests de Políticas de Archivo (CDM-30) ---


def test_upload_session_rejects_path_traversal(
    test_client: TestClient, app: FastAPI, sqlite_session: Session
) -> None:
    """Rechaza nombres con path traversal (../) con 422 invalid_file_name."""
    user, ws, _ = _seed_workspace_and_member(sqlite_session, WorkspaceRole.MEMBER)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=user.cognito_sub, email=user.email
    )

    response = test_client.post(
        f"/api/v1/workspaces/{ws.id}/upload-sessions",
        json={
            "original_filename": "../../etc/shadow.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_file_name"


def test_upload_session_rejects_disallowed_mime(
    test_client: TestClient, app: FastAPI, sqlite_session: Session
) -> None:
    """Rechaza tipos MIME no admitidos con 415 file_type_not_allowed."""
    user, ws, _ = _seed_workspace_and_member(sqlite_session, WorkspaceRole.MEMBER)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=user.cognito_sub, email=user.email
    )

    response = test_client.post(
        f"/api/v1/workspaces/{ws.id}/upload-sessions",
        json={
            "original_filename": "script.sh",
            "content_type": "application/x-sh",
            "size_bytes": 1024,
        },
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "file_type_not_allowed"


def test_upload_session_rejects_mime_extension_mismatch(
    test_client: TestClient, app: FastAPI, sqlite_session: Session
) -> None:
    """Rechaza discrepancias entre MIME y extensión (.exe con application/pdf) con 415."""
    user, ws, _ = _seed_workspace_and_member(sqlite_session, WorkspaceRole.MEMBER)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=user.cognito_sub, email=user.email
    )

    response = test_client.post(
        f"/api/v1/workspaces/{ws.id}/upload-sessions",
        json={
            "original_filename": "malicioso.exe",
            "content_type": "application/pdf",
            "size_bytes": 1024,
        },
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "file_type_not_allowed"


def test_upload_session_rejects_exceeded_size(
    test_client: TestClient, app: FastAPI, sqlite_session: Session
) -> None:
    """Rechaza archivos que exceden el límite máximo configurado con 413 file_size_exceeded."""
    user, ws, _ = _seed_workspace_and_member(sqlite_session, WorkspaceRole.MEMBER)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=user.cognito_sub, email=user.email
    )

    # El fixture app tiene límite de 10 MB (10 * 1024 * 1024)
    response = test_client.post(
        f"/api/v1/workspaces/{ws.id}/upload-sessions",
        json={
            "original_filename": "video_pesado.pdf",
            "content_type": "application/pdf",
            "size_bytes": 15 * 1024 * 1024,  # 15 MB
        },
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_size_exceeded"


def test_upload_session_rejects_zero_size(
    test_client: TestClient, app: FastAPI, sqlite_session: Session
) -> None:
    """Rechaza archivos de 0 bytes con error de validación (422)."""
    user, ws, _ = _seed_workspace_and_member(sqlite_session, WorkspaceRole.MEMBER)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=user.cognito_sub, email=user.email
    )

    response = test_client.post(
        f"/api/v1/workspaces/{ws.id}/upload-sessions",
        json={
            "original_filename": "vacio.pdf",
            "content_type": "application/pdf",
            "size_bytes": 0,
        },
    )
    assert response.status_code == 422


def test_upload_session_rejects_invalid_checksum(
    test_client: TestClient, app: FastAPI, sqlite_session: Session
) -> None:
    """Rechaza checksums con formato no SHA-256 (64 hex) con 422 invalid_checksum."""
    user, ws, _ = _seed_workspace_and_member(sqlite_session, WorkspaceRole.MEMBER)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=user.cognito_sub, email=user.email
    )

    response = test_client.post(
        f"/api/v1/workspaces/{ws.id}/upload-sessions",
        json={
            "original_filename": "archivo.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
            "checksum_sha256": "invalido",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_checksum"
