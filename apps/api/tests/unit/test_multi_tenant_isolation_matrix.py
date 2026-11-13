"""Pruebas exhaustivas de aislamiento multi-tenant y matriz de permisos (CDM-28).

Verifica de forma automatizada y rigurosa:
1. Dos workspaces independientes (Alpha y Beta) con documentos y usuarios propios.
2. Matriz de permisos completa por rol (OWNER, ADMIN, EDITOR, MEMBER, VIEWER, EXTERNO).
3. Pruebas negativas de acceso cruzado (cross-tenant) para list, detail, download y delete.
4. Pruebas contra UUIDs conocidos de otros tenants y UUIDs aleatorios no existentes.
5. Invariante de seguridad: respuestas 403/404 sin filtración de existencia sensible ni IDOR.
"""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from cdm.adapters.inbound.http.auth import get_current_user
from cdm.adapters.inbound.http.dependencies import get_db_session
from cdm.adapters.outbound.persistence.models import (
    Base,
    DocumentModel,
    UserModel,
    WorkspaceMembershipModel,
    WorkspaceModel,
)
from cdm.bootstrap.app import create_app
from cdm.config.settings import Settings
from cdm.domain.document import DocumentStatus
from cdm.domain.identity import AuthenticatedUser


class TenantFixture:
    """Contenedor de datos de prueba para dos workspaces independientes."""

    def __init__(self, session: Session) -> None:
        self.session = session

        # --- Workspace Alpha ---
        self.u_owner_a = UserModel(id=uuid4(), cognito_sub="sub-owner-a", email="owner.a@corp.com")
        self.u_admin_a = UserModel(id=uuid4(), cognito_sub="sub-admin-a", email="admin.a@corp.com")
        self.u_editor_a = UserModel(
            id=uuid4(), cognito_sub="sub-editor-a", email="editor.a@corp.com"
        )
        self.u_member_a = UserModel(
            id=uuid4(), cognito_sub="sub-member-a", email="member.a@corp.com"
        )
        self.u_viewer_a = UserModel(
            id=uuid4(), cognito_sub="sub-viewer-a", email="viewer.a@corp.com"
        )

        self.ws_a = WorkspaceModel(
            id=uuid4(), name="Workspace Alpha", slug="ws-alpha", created_by=self.u_owner_a.id
        )

        self.m_owner_a = WorkspaceMembershipModel(
            id=uuid4(),
            workspace_id=self.ws_a.id,
            user_id=self.u_owner_a.id,
            role="OWNER",
            status="ACTIVE",
        )
        self.m_admin_a = WorkspaceMembershipModel(
            id=uuid4(),
            workspace_id=self.ws_a.id,
            user_id=self.u_admin_a.id,
            role="ADMIN",
            status="ACTIVE",
        )
        self.m_editor_a = WorkspaceMembershipModel(
            id=uuid4(),
            workspace_id=self.ws_a.id,
            user_id=self.u_editor_a.id,
            role="EDITOR",
            status="ACTIVE",
        )
        self.m_member_a = WorkspaceMembershipModel(
            id=uuid4(),
            workspace_id=self.ws_a.id,
            user_id=self.u_member_a.id,
            role="MEMBER",
            status="ACTIVE",
        )
        self.m_viewer_a = WorkspaceMembershipModel(
            id=uuid4(),
            workspace_id=self.ws_a.id,
            user_id=self.u_viewer_a.id,
            role="VIEWER",
            status="ACTIVE",
        )

        self.doc_a = DocumentModel(
            id=uuid4(),
            workspace_id=self.ws_a.id,
            uploaded_by=self.u_member_a.id,
            original_filename="confidencial_alpha.pdf",
            storage_key=f"workspaces/{self.ws_a.id}/confidencial_alpha.pdf",
            content_type="application/pdf",
            size_bytes=4096,
            status=DocumentStatus.READY.value,
        )

        # --- Workspace Beta ---
        self.u_owner_b = UserModel(id=uuid4(), cognito_sub="sub-owner-b", email="owner.b@other.com")
        self.u_member_b = UserModel(
            id=uuid4(), cognito_sub="sub-member-b", email="member.b@other.com"
        )

        self.ws_b = WorkspaceModel(
            id=uuid4(), name="Workspace Beta", slug="ws-beta", created_by=self.u_owner_b.id
        )

        self.m_owner_b = WorkspaceMembershipModel(
            id=uuid4(),
            workspace_id=self.ws_b.id,
            user_id=self.u_owner_b.id,
            role="OWNER",
            status="ACTIVE",
        )
        self.m_member_b = WorkspaceMembershipModel(
            id=uuid4(),
            workspace_id=self.ws_b.id,
            user_id=self.u_member_b.id,
            role="MEMBER",
            status="ACTIVE",
        )

        self.doc_b = DocumentModel(
            id=uuid4(),
            workspace_id=self.ws_b.id,
            uploaded_by=self.u_owner_b.id,
            original_filename="secreto_beta.pdf",
            storage_key=f"workspaces/{self.ws_b.id}/secreto_beta.pdf",
            content_type="application/pdf",
            size_bytes=8192,
            status=DocumentStatus.READY.value,
        )

        # --- Usuario Gamma (Externo sin ningún workspace) ---
        self.u_gamma = UserModel(id=uuid4(), cognito_sub="sub-gamma", email="externo@global.com")

        # Persistir todo en BD
        self.session.add_all(
            [
                self.u_owner_a,
                self.u_admin_a,
                self.u_editor_a,
                self.u_member_a,
                self.u_viewer_a,
                self.ws_a,
                self.m_owner_a,
                self.m_admin_a,
                self.m_editor_a,
                self.m_member_a,
                self.m_viewer_a,
                self.doc_a,
                self.u_owner_b,
                self.u_member_b,
                self.ws_b,
                self.m_owner_b,
                self.m_member_b,
                self.doc_b,
                self.u_gamma,
            ]
        )
        self.session.commit()


@pytest.fixture
def sqlite_session() -> Iterator[Session]:
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
def env(sqlite_session: Session) -> TenantFixture:
    return TenantFixture(sqlite_session)


@pytest.fixture
def test_client(sqlite_session: Session) -> TestClient:
    settings = Settings(
        database_url="sqlite:///:memory:",
        cors_origins="*",
        cognito_user_pool_id="us-east-1_mock",
        cognito_client_id="mock-client-id",
        cognito_region="us-east-1",
    )
    app = create_app(settings)

    def override_db() -> Iterator[Session]:
        yield sqlite_session

    app.dependency_overrides[get_db_session] = override_db
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. Matriz Automatizada de Permisos por Rol (ADR-0001)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sub", "email", "expected_status"),
    [
        ("sub-owner-a", "owner.a@corp.com", 200),
        ("sub-admin-a", "admin.a@corp.com", 200),
        ("sub-editor-a", "editor.a@corp.com", 200),
        ("sub-member-a", "member.a@corp.com", 200),
        ("sub-viewer-a", "viewer.a@corp.com", 200),
        ("sub-gamma", "externo@global.com", 404),
    ],
)
def test_permission_matrix_list_documents(
    test_client: TestClient, env: TenantFixture, sub: str, email: str, expected_status: int
):
    """Matriz: LIST_DOCUMENTS permitido a todos los miembros; externo recibe 404."""
    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=sub, email=email
    )
    res = test_client.get(f"/api/v1/workspaces/{env.ws_a.id}/documents")
    assert res.status_code == expected_status
    if expected_status == 200:
        assert len(res.json()["data"]) == 1


@pytest.mark.parametrize(
    ("sub", "email", "expected_status"),
    [
        ("sub-owner-a", "owner.a@corp.com", 200),
        ("sub-admin-a", "admin.a@corp.com", 200),
        ("sub-editor-a", "editor.a@corp.com", 200),
        ("sub-member-a", "member.a@corp.com", 200),
        ("sub-viewer-a", "viewer.a@corp.com", 200),
        ("sub-gamma", "externo@global.com", 404),
    ],
)
def test_permission_matrix_get_document_detail(
    test_client: TestClient, env: TenantFixture, sub: str, email: str, expected_status: int
):
    """Matriz: GET_DOCUMENT_DETAIL permitido a todos los miembros; externo recibe 404."""
    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=sub, email=email
    )
    res = test_client.get(f"/api/v1/workspaces/{env.ws_a.id}/documents/{env.doc_a.id}")
    assert res.status_code == expected_status
    if expected_status == 200:
        assert res.json()["data"]["id"] == str(env.doc_a.id)


@pytest.mark.parametrize(
    ("sub", "email", "expected_status"),
    [
        ("sub-owner-a", "owner.a@corp.com", 200),
        ("sub-admin-a", "admin.a@corp.com", 200),
        ("sub-editor-a", "editor.a@corp.com", 200),
        ("sub-member-a", "member.a@corp.com", 200),
        ("sub-viewer-a", "viewer.a@corp.com", 200),
        ("sub-gamma", "externo@global.com", 404),
    ],
)
def test_permission_matrix_download_document(
    test_client: TestClient, env: TenantFixture, sub: str, email: str, expected_status: int
):
    """Matriz: DOWNLOAD_DOCUMENT permitido a todos los miembros activos."""
    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=sub, email=email
    )
    url = f"/api/v1/workspaces/{env.ws_a.id}/documents/{env.doc_a.id}/download-url"
    res = test_client.post(url)
    assert res.status_code == expected_status
    if expected_status == 200:
        assert "download_url" in res.json()["data"]


@pytest.mark.parametrize(
    ("sub", "email", "expected_status"),
    [
        ("sub-owner-a", "owner.a@corp.com", 201),
        ("sub-admin-a", "admin.a@corp.com", 201),
        ("sub-editor-a", "editor.a@corp.com", 201),
        ("sub-member-a", "member.a@corp.com", 201),
        ("sub-viewer-a", "viewer.a@corp.com", 403),  # VIEWER rechazado
        ("sub-gamma", "externo@global.com", 404),
    ],
)
def test_permission_matrix_upload_document(
    test_client: TestClient, env: TenantFixture, sub: str, email: str, expected_status: int
):
    """Matriz: UPLOAD_DOCUMENT requiere MEMBER o superior (VIEWER recibe 403)."""
    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=sub, email=email
    )
    res = test_client.post(
        f"/api/v1/workspaces/{env.ws_a.id}/documents",
        json={
            "original_filename": f"test_{sub}.pdf",
            "storage_key": f"workspaces/{env.ws_a.id}/test_{sub}.pdf",
            "content_type": "application/pdf",
            "size_bytes": 100,
        },
    )
    assert res.status_code == expected_status


@pytest.mark.parametrize(
    ("sub", "email", "expected_status"),
    [
        ("sub-owner-a", "owner.a@corp.com", 200),
        ("sub-admin-a", "admin.a@corp.com", 200),
        ("sub-editor-a", "editor.a@corp.com", 200),
        ("sub-member-a", "member.a@corp.com", 403),  # MEMBER rechazado
        ("sub-viewer-a", "viewer.a@corp.com", 403),  # VIEWER rechazado
        ("sub-gamma", "externo@global.com", 404),
    ],
)
def test_permission_matrix_delete_document(
    test_client: TestClient, env: TenantFixture, sub: str, email: str, expected_status: int
):
    """Matriz: DELETE_DOCUMENT requiere EDITOR o superior (MEMBER y VIEWER reciben 403)."""
    # Crear un documento específico para cada prueba de borrado
    doc = DocumentModel(
        id=uuid4(),
        workspace_id=env.ws_a.id,
        uploaded_by=env.u_member_a.id,
        original_filename=f"doc_for_del_{sub}.pdf",
        storage_key=f"workspaces/{env.ws_a.id}/del_{sub}.pdf",
        content_type="application/pdf",
        size_bytes=100,
        status="READY",
    )
    env.session.add(doc)
    env.session.commit()

    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=sub, email=email
    )
    res = test_client.delete(f"/api/v1/workspaces/{env.ws_a.id}/documents/{doc.id}")
    assert res.status_code == expected_status


# -----------------------------------------------------------------------------
# 2. Pruebas Negativas de Acceso Cruzado (Cross-Tenant A vs B)
# -----------------------------------------------------------------------------


def test_cross_tenant_listing_attempt(test_client: TestClient, env: TenantFixture):
    """Usuario de Workspace Alpha no puede listar documentos de Workspace Beta."""
    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=env.u_owner_a.cognito_sub, email=env.u_owner_a.email
    )

    # Intenta listar documentos de Beta
    res = test_client.get(f"/api/v1/workspaces/{env.ws_b.id}/documents")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "workspace_not_found"


def test_cross_tenant_detail_idor_attempt(test_client: TestClient, env: TenantFixture):
    """Ataque IDOR: Usuario de Alpha conoce el UUID del documento de Beta."""
    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=env.u_owner_a.cognito_sub, email=env.u_owner_a.email
    )

    # Intento 1: Pasando workspace_id de Beta -> 404 workspace_not_found
    res1 = test_client.get(f"/api/v1/workspaces/{env.ws_b.id}/documents/{env.doc_b.id}")
    assert res1.status_code == 404
    assert res1.json()["error"]["code"] == "workspace_not_found"

    # Intento 2: Pasando workspace_id de Alpha con el document_id de Beta -> 404 document_not_found
    res2 = test_client.get(f"/api/v1/workspaces/{env.ws_a.id}/documents/{env.doc_b.id}")
    assert res2.status_code == 404
    assert res2.json()["error"]["code"] == "document_not_found"


def test_cross_tenant_download_idor_attempt(test_client: TestClient, env: TenantFixture):
    """Ataque IDOR en descarga: Usuario de Alpha intenta generar URL de doc_b."""
    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=env.u_owner_a.cognito_sub, email=env.u_owner_a.email
    )

    res = test_client.post(
        f"/api/v1/workspaces/{env.ws_a.id}/documents/{env.doc_b.id}/download-url"
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "document_not_found"


def test_cross_tenant_delete_idor_attempt(test_client: TestClient, env: TenantFixture):
    """Ataque IDOR en borrado: OWNER de Alpha intenta borrar doc_b."""
    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=env.u_owner_a.cognito_sub, email=env.u_owner_a.email
    )

    res = test_client.delete(f"/api/v1/workspaces/{env.ws_a.id}/documents/{env.doc_b.id}")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "document_not_found"

    # Verificar que el documento en Beta permanece intacto y no eliminado
    db_doc_b = env.session.get(DocumentModel, env.doc_b.id)
    assert db_doc_b is not None
    assert db_doc_b.deleted_at is None
    assert db_doc_b.status == DocumentStatus.READY.value


# -----------------------------------------------------------------------------
# 3. Pruebas contra UUIDs Aleatorios (Non-Existent IDs)
# -----------------------------------------------------------------------------


def test_random_workspace_uuid_returns_identical_404(test_client: TestClient, env: TenantFixture):
    """Un workspace_id aleatorio inexistente devuelve 404 idéntico al de un workspace ajeno."""
    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=env.u_owner_a.cognito_sub, email=env.u_owner_a.email
    )

    random_ws_id = uuid4()
    res_random = test_client.get(f"/api/v1/workspaces/{random_ws_id}/documents")
    res_other = test_client.get(f"/api/v1/workspaces/{env.ws_b.id}/documents")

    assert res_random.status_code == 404
    assert res_other.status_code == 404
    # La respuesta y mensaje deben ser exactamente iguales para evitar timing / error enumeration
    assert res_random.json() == res_other.json()


def test_random_document_uuid_returns_identical_404(test_client: TestClient, env: TenantFixture):
    """Un document_id aleatorio inexistente devuelve 404 idéntico al de un documento ajeno."""
    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub=env.u_owner_a.cognito_sub, email=env.u_owner_a.email
    )

    random_doc_id = uuid4()
    res_random = test_client.get(f"/api/v1/workspaces/{env.ws_a.id}/documents/{random_doc_id}")
    res_other = test_client.get(f"/api/v1/workspaces/{env.ws_a.id}/documents/{env.doc_b.id}")

    assert res_random.status_code == 404
    assert res_other.status_code == 404
    assert res_random.json() == res_other.json()


# -----------------------------------------------------------------------------
# 4. Prevención de Fuga de Información Sensible
# -----------------------------------------------------------------------------


def test_error_responses_do_not_leak_internals(test_client: TestClient, env: TenantFixture):
    """Verifica que ninguna respuesta de error filtre trazas, claves S3 ni metadatos ajenos."""
    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub="sub-gamma", email="externo@global.com"
    )

    endpoints = [
        ("GET", f"/api/v1/workspaces/{env.ws_a.id}/documents"),
        ("GET", f"/api/v1/workspaces/{env.ws_a.id}/documents/{env.doc_a.id}"),
        ("POST", f"/api/v1/workspaces/{env.ws_a.id}/documents/{env.doc_a.id}/download-url"),
        ("DELETE", f"/api/v1/workspaces/{env.ws_a.id}/documents/{env.doc_a.id}"),
    ]

    for method, path in endpoints:
        if method == "GET":
            res = test_client.get(path)
        elif method == "POST":
            res = test_client.post(path)
        else:
            res = test_client.delete(path)

        assert res.status_code == 404
        body_str = res.text
        # Nunca debe aparecer el nombre del workspace ni su storage_key
        assert "confidencial_alpha" not in body_str
        assert "Workspace Alpha" not in body_str
        assert "Traceback" not in body_str
        assert "sqlalchemy" not in body_str.lower()
