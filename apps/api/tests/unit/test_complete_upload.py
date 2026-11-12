"""Pruebas unitarias de confirmación de carga y reconciliación S3 (CDM-32).

Prueba:
- Verificación HeadObject de presencia física en S3 y coincidencia de tamaño.
- Transición atómica de PENDING_UPLOAD a UPLOADED.
- Transición de UploadSession de PENDING a COMPLETED.
- Idempotencia ante llamadas repetidas.
- Aislamiento multi-tenant y prevención de IDOR (404 uniforme).
- Rechazo de roles sin permisos (403 para VIEWER).
- Rechazo de sesiones expiradas o discrepancias de tamaño (409 Conflict).
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from cdm.adapters.inbound.http.auth import get_current_user
from cdm.adapters.inbound.http.dependencies import get_db_session, get_storage_port
from cdm.adapters.outbound.persistence.models import (
    Base,
    DocumentModel,
    UploadSessionModel,
    UserModel,
    WorkspaceMembershipModel,
    WorkspaceModel,
)
from cdm.adapters.outbound.storage.s3_storage import S3StorageAdapter
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
def mock_storage() -> S3StorageAdapter:
    """Adaptador de almacenamiento con almacén simulado."""
    return S3StorageAdapter(bucket_name="test-bucket", region="us-east-1")


@pytest.fixture
def app(sqlite_session: Session, mock_storage: S3StorageAdapter) -> FastAPI:
    """Instancia la aplicación FastAPI configurada para pruebas."""
    settings = Settings(
        database_url="sqlite:///:memory:",
        cors_origins="*",
        cognito_user_pool_id="us-east-1_mock",
        cognito_client_id="mock-client-id",
        cognito_region="us-east-1",
        max_upload_size_bytes=10 * 1024 * 1024,
        upload_url_expires_in_seconds=900,
    )
    application = create_app(settings)

    def override_db() -> Iterator[Session]:
        yield sqlite_session

    application.dependency_overrides[get_db_session] = override_db
    application.dependency_overrides[get_storage_port] = lambda: mock_storage
    return application


@pytest.fixture
def test_client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _seed_context(
    session: Session, role: WorkspaceRole, size_bytes: int = 1024, is_expired: bool = False
) -> tuple[UserModel, WorkspaceModel, DocumentModel, UploadSessionModel]:
    """Crea un usuario, workspace, documento PENDING_UPLOAD y sesión de carga asociada."""
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
    doc_id = uuid4()
    storage_key = f"workspaces/{workspace.id}/documents/{doc_id}/test.pdf"
    document = DocumentModel(
        id=doc_id,
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_filename="test.pdf",
        storage_key=storage_key,
        content_type="application/pdf",
        size_bytes=size_bytes,
        status=DocumentStatus.PENDING_UPLOAD.value,
        technical_metadata={},
    )
    now = datetime.now(UTC)
    expires_at = now - timedelta(minutes=5) if is_expired else now + timedelta(minutes=15)
    upload_session = UploadSessionModel(
        id=uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        document_id=doc_id,
        storage_key=storage_key,
        expected_size_bytes=size_bytes,
        expected_content_type="application/pdf",
        status=UploadSessionStatus.PENDING.value,
        expires_at=expires_at,
    )
    session.add_all([user, workspace, membership, document, upload_session])
    session.commit()
    return user, workspace, document, upload_session


# --- Tests de Autenticación y Autorización ---


def test_complete_upload_unauthenticated_returns_401(test_client: TestClient) -> None:
    """Confirmar sin token devuelve 401 missing_token."""
    response = test_client.post(f"/api/v1/workspaces/{uuid4()}/documents/{uuid4()}/complete")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_token"


def test_complete_upload_external_user_returns_404_anti_idor(
    test_client: TestClient, app: FastAPI, sqlite_session: Session
) -> None:
    """Usuario ajeno al workspace recibe 404 (anti-IDOR y anti-enumeración)."""
    _user, ws, doc, _ = _seed_context(sqlite_session, WorkspaceRole.MEMBER)

    external_user = AuthenticatedUser(cognito_sub="sub-external-999", email="ext@test.com")
    app.dependency_overrides[get_current_user] = lambda: external_user

    response = test_client.post(f"/api/v1/workspaces/{ws.id}/documents/{doc.id}/complete")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "workspace_not_found"


def test_complete_upload_viewer_returns_403(
    test_client: TestClient, app: FastAPI, sqlite_session: Session
) -> None:
    """Rol VIEWER no puede confirmar cargas (403 permission_denied)."""
    user, ws, doc, _ = _seed_context(sqlite_session, WorkspaceRole.VIEWER)

    auth_user = AuthenticatedUser(cognito_sub=user.cognito_sub, email=user.email)
    app.dependency_overrides[get_current_user] = lambda: auth_user

    response = test_client.post(f"/api/v1/workspaces/{ws.id}/documents/{doc.id}/complete")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_complete_upload_document_not_found_returns_404(
    test_client: TestClient, app: FastAPI, sqlite_session: Session
) -> None:
    """Confirmar documento inexistente devuelve 404 document_not_found."""
    user, ws, _, _ = _seed_context(sqlite_session, WorkspaceRole.MEMBER)

    auth_user = AuthenticatedUser(cognito_sub=user.cognito_sub, email=user.email)
    app.dependency_overrides[get_current_user] = lambda: auth_user

    response = test_client.post(f"/api/v1/workspaces/{ws.id}/documents/{uuid4()}/complete")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


# --- Tests de Reconciliación con S3 y Errores de Negocio ---


def test_complete_upload_object_missing_in_s3_returns_409(
    test_client: TestClient, app: FastAPI, sqlite_session: Session
) -> None:
    """Si el archivo no está en S3, rechaza con 409 conflict."""
    user, ws, doc, _ = _seed_context(sqlite_session, WorkspaceRole.MEMBER)

    auth_user = AuthenticatedUser(cognito_sub=user.cognito_sub, email=user.email)
    app.dependency_overrides[get_current_user] = lambda: auth_user

    response = test_client.post(f"/api/v1/workspaces/{ws.id}/documents/{doc.id}/complete")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert "no se encuentra en el almacenamiento" in response.json()["error"]["message"]


def test_complete_upload_size_mismatch_returns_409(
    test_client: TestClient,
    app: FastAPI,
    sqlite_session: Session,
    mock_storage: S3StorageAdapter,
) -> None:
    """Si el tamaño en S3 difiere del tamaño registrado, rechaza con 409 conflict."""
    user, ws, doc, _ = _seed_context(sqlite_session, WorkspaceRole.MEMBER, size_bytes=1024)

    # Simular objeto en S3 con tamaño erróneo (500 bytes en vez de 1024)
    mock_storage.register_mock_object(
        storage_key=doc.storage_key,
        size_bytes=500,
        content_type="application/pdf",
    )

    auth_user = AuthenticatedUser(cognito_sub=user.cognito_sub, email=user.email)
    app.dependency_overrides[get_current_user] = lambda: auth_user

    response = test_client.post(f"/api/v1/workspaces/{ws.id}/documents/{doc.id}/complete")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert "no coincide con el tamaño esperado" in response.json()["error"]["message"]


def test_complete_upload_expired_session_returns_409(
    test_client: TestClient,
    app: FastAPI,
    sqlite_session: Session,
    mock_storage: S3StorageAdapter,
) -> None:
    """Si la sesión de carga ha expirado, rechaza con 409 upload_session_expired."""
    user, ws, doc, _ = _seed_context(
        sqlite_session, WorkspaceRole.MEMBER, size_bytes=1024, is_expired=True
    )

    mock_storage.register_mock_object(
        storage_key=doc.storage_key,
        size_bytes=1024,
        content_type="application/pdf",
    )

    auth_user = AuthenticatedUser(cognito_sub=user.cognito_sub, email=user.email)
    app.dependency_overrides[get_current_user] = lambda: auth_user

    response = test_client.post(f"/api/v1/workspaces/{ws.id}/documents/{doc.id}/complete")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "upload_session_expired"


# --- Tests de Éxito e Idempotencia ---


def test_complete_upload_success_transitions_to_uploaded(
    test_client: TestClient,
    app: FastAPI,
    sqlite_session: Session,
    mock_storage: S3StorageAdapter,
) -> None:
    """Confirmación exitosa transiciona Document a UPLOADED y UploadSession a COMPLETED."""
    user, ws, doc, session_model = _seed_context(
        sqlite_session, WorkspaceRole.MEMBER, size_bytes=2048
    )

    mock_storage.register_mock_object(
        storage_key=doc.storage_key,
        size_bytes=2048,
        content_type="application/pdf",
    )

    auth_user = AuthenticatedUser(cognito_sub=user.cognito_sub, email=user.email)
    app.dependency_overrides[get_current_user] = lambda: auth_user

    response = test_client.post(f"/api/v1/workspaces/{ws.id}/documents/{doc.id}/complete")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == str(doc.id)
    assert data["status"] == DocumentStatus.UPLOADED.value

    # Verificar actualización en base de datos
    sqlite_session.expire_all()
    updated_doc = sqlite_session.get(DocumentModel, doc.id)
    assert updated_doc is not None
    assert updated_doc.status == DocumentStatus.UPLOADED.value

    updated_session = sqlite_session.get(UploadSessionModel, session_model.id)
    assert updated_session is not None
    assert updated_session.status == UploadSessionStatus.COMPLETED.value


def test_complete_upload_idempotency_returns_200_without_error(
    test_client: TestClient,
    app: FastAPI,
    sqlite_session: Session,
    mock_storage: S3StorageAdapter,
) -> None:
    """Llamadas repetidas a complete retornan 200 con el estado actual de forma idempotente."""
    user, ws, doc, _ = _seed_context(sqlite_session, WorkspaceRole.MEMBER, size_bytes=1024)

    mock_storage.register_mock_object(
        storage_key=doc.storage_key,
        size_bytes=1024,
        content_type="application/pdf",
    )

    auth_user = AuthenticatedUser(cognito_sub=user.cognito_sub, email=user.email)
    app.dependency_overrides[get_current_user] = lambda: auth_user

    # Primera llamada
    res1 = test_client.post(f"/api/v1/workspaces/{ws.id}/documents/{doc.id}/complete")
    assert res1.status_code == 200
    assert res1.json()["data"]["status"] == DocumentStatus.UPLOADED.value

    # Segunda llamada (idempotente)
    res2 = test_client.post(f"/api/v1/workspaces/{ws.id}/documents/{doc.id}/complete")
    assert res2.status_code == 200
    assert res2.json()["data"]["status"] == DocumentStatus.UPLOADED.value
