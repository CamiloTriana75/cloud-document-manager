"""Pruebas unitarias de endpoints HTTP de Documentos y Aislamiento por Tenant (CDM-27).

Prueba los contratos REST OpenAPI, códigos de estado (201, 200, 401, 403, 404)
y verificaciones de aislamiento multi-tenant con SQLite en memoria.
"""

from collections.abc import Iterator
from uuid import UUID, uuid4

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


@pytest.fixture
def sqlite_session() -> Iterator[Session]:
    """Crea una base de datos SQLite en memoria con el esquema completo."""
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


def test_list_documents_unauthenticated_returns_401(test_client: TestClient):
    """Sin token de autorización devuelve 401 missing_token."""
    ws_id = uuid4()
    res = test_client.get(f"/api/v1/workspaces/{ws_id}/documents")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "missing_token"


def test_cross_tenant_access_denied_returns_404(test_client: TestClient, sqlite_session: Session):
    """Acceder a documentos de un workspace al que no se pertenece devuelve 404 (anti-IDOR)."""
    # Crear usuario 1 y workspace 1
    u1 = UserModel(id=uuid4(), cognito_sub="sub-u1", email="u1@test.com")
    ws1 = WorkspaceModel(id=uuid4(), name="WS 1", slug="ws-1", created_by=u1.id)
    m1 = WorkspaceMembershipModel(
        id=uuid4(), workspace_id=ws1.id, user_id=u1.id, role="OWNER", status="ACTIVE"
    )

    # Crear usuario 2 ajeno
    u2 = UserModel(id=uuid4(), cognito_sub="sub-u2", email="u2@test.com")

    sqlite_session.add_all([u1, ws1, m1, u2])
    sqlite_session.commit()

    # Usuario 2 intenta consultar el workspace 1
    auth_user2 = AuthenticatedUser(cognito_sub="sub-u2", email="u2@test.com")
    test_client.app.dependency_overrides[get_current_user] = lambda: auth_user2

    res = test_client.get(f"/api/v1/workspaces/{ws1.id}/documents")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "workspace_not_found"


def test_document_crud_flow_and_role_permissions(test_client: TestClient, sqlite_session: Session):
    """Flujo completo: creación, listado, detalle, descarga y eliminación respetando roles."""
    # Configurar usuarios y workspace
    owner = UserModel(id=uuid4(), cognito_sub="sub-owner", email="owner@test.com")
    editor = UserModel(id=uuid4(), cognito_sub="sub-editor", email="editor@test.com")
    member = UserModel(id=uuid4(), cognito_sub="sub-member", email="member@test.com")
    ws = WorkspaceModel(id=uuid4(), name="Workspace Dev", slug="ws-dev", created_by=owner.id)

    m_owner = WorkspaceMembershipModel(
        id=uuid4(), workspace_id=ws.id, user_id=owner.id, role="OWNER", status="ACTIVE"
    )
    m_editor = WorkspaceMembershipModel(
        id=uuid4(), workspace_id=ws.id, user_id=editor.id, role="EDITOR", status="ACTIVE"
    )
    m_member = WorkspaceMembershipModel(
        id=uuid4(), workspace_id=ws.id, user_id=member.id, role="MEMBER", status="ACTIVE"
    )

    sqlite_session.add_all([owner, editor, member, ws, m_owner, m_editor, m_member])
    sqlite_session.commit()

    # 1. Crear documento como MEMBER (autorizado)
    auth_member = AuthenticatedUser(cognito_sub="sub-member", email="member@test.com")
    test_client.app.dependency_overrides[get_current_user] = lambda: auth_member

    create_res = test_client.post(
        f"/api/v1/workspaces/{ws.id}/documents",
        json={
            "original_filename": "manual.pdf",
            "storage_key": f"workspaces/{ws.id}/docs/manual.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
            "technical_metadata": {"version": 1},
        },
    )
    assert create_res.status_code == 201
    doc_data = create_res.json()["data"]
    doc_id = doc_data["id"]
    assert doc_data["original_filename"] == "manual.pdf"
    assert doc_data["workspace_id"] == str(ws.id)

    # 2. Listar documentos
    list_res = test_client.get(f"/api/v1/workspaces/{ws.id}/documents")
    assert list_res.status_code == 200
    list_body = list_res.json()
    assert len(list_body["data"]) == 1
    assert list_body["pagination"]["total"] == 1

    # 3. Detalle de documento
    detail_res = test_client.get(f"/api/v1/workspaces/{ws.id}/documents/{doc_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["data"]["id"] == doc_id

    # 4. Generar URL de descarga (actualizar estado a READY en BD)
    db_doc = sqlite_session.get(DocumentModel, UUID(doc_id))
    assert db_doc is not None
    db_doc.status = DocumentStatus.READY.value
    sqlite_session.commit()

    download_res = test_client.post(f"/api/v1/workspaces/{ws.id}/documents/{doc_id}/download-url")
    assert download_res.status_code == 200
    assert "download_url" in download_res.json()["data"]

    # 5. Intentar eliminar como MEMBER -> Rechazado con 403 (ADR-0001)
    del_member_res = test_client.delete(f"/api/v1/workspaces/{ws.id}/documents/{doc_id}")
    assert del_member_res.status_code == 403
    assert del_member_res.json()["error"]["code"] == "permission_denied"

    # 6. Eliminar como EDITOR -> Exitoso con 200
    auth_editor = AuthenticatedUser(cognito_sub="sub-editor", email="editor@test.com")
    test_client.app.dependency_overrides[get_current_user] = lambda: auth_editor

    del_editor_res = test_client.delete(f"/api/v1/workspaces/{ws.id}/documents/{doc_id}")
    assert del_editor_res.status_code == 200

    # 7. Documento ya no aparece en el listado activo
    list_after_del = test_client.get(f"/api/v1/workspaces/{ws.id}/documents")
    assert list_after_del.status_code == 200
    assert len(list_after_del.json()["data"]) == 0


def test_list_documents_filtering_by_status(test_client: TestClient, sqlite_session: Session):
    """Filtra documentos por su estado de procesamiento (CDM-37)."""
    user = UserModel(id=uuid4(), cognito_sub="sub-filter", email="filter@test.com")
    ws = WorkspaceModel(id=uuid4(), name="Filter WS", slug="filter-ws", created_by=user.id)
    membership = WorkspaceMembershipModel(
        id=uuid4(), workspace_id=ws.id, user_id=user.id, role="MEMBER", status="ACTIVE"
    )

    doc_ready = DocumentModel(
        id=uuid4(),
        workspace_id=ws.id,
        uploaded_by=user.id,
        original_filename="ready.pdf",
        storage_key=f"workspaces/{ws.id}/ready.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        status=DocumentStatus.READY.value,
        technical_metadata={"s3_etag": "tag1"},
    )
    doc_failed = DocumentModel(
        id=uuid4(),
        workspace_id=ws.id,
        uploaded_by=user.id,
        original_filename="failed.pdf",
        storage_key=f"workspaces/{ws.id}/failed.pdf",
        content_type="application/pdf",
        size_bytes=500,
        status=DocumentStatus.FAILED.value,
        technical_metadata={"failure_reason": "Archivo no legible."},
    )
    doc_processing = DocumentModel(
        id=uuid4(),
        workspace_id=ws.id,
        uploaded_by=user.id,
        original_filename="proc.pdf",
        storage_key=f"workspaces/{ws.id}/proc.pdf",
        content_type="application/pdf",
        size_bytes=800,
        status=DocumentStatus.PROCESSING.value,
    )

    sqlite_session.add_all([user, ws, membership, doc_ready, doc_failed, doc_processing])
    sqlite_session.commit()

    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub="sub-filter", email="filter@test.com"
    )

    # 1. Sin filtro: retorna los 3 documentos
    res_all = test_client.get(f"/api/v1/workspaces/{ws.id}/documents")
    assert res_all.status_code == 200
    assert len(res_all.json()["data"]) == 3

    # 2. Filtro status=READY: retorna solo doc_ready
    res_ready = test_client.get(f"/api/v1/workspaces/{ws.id}/documents?status=READY")
    assert res_ready.status_code == 200
    assert len(res_ready.json()["data"]) == 1
    assert res_ready.json()["data"][0]["original_filename"] == "ready.pdf"
    assert res_ready.json()["data"][0]["status"] == "READY"
    assert res_ready.json()["data"][0]["failure_reason"] is None

    # 3. Filtro status=FAILED: retorna doc_failed con su razón segura de fallo
    res_failed = test_client.get(f"/api/v1/workspaces/{ws.id}/documents?status=FAILED")
    assert res_failed.status_code == 200
    assert len(res_failed.json()["data"]) == 1
    failed_item = res_failed.json()["data"][0]
    assert failed_item["original_filename"] == "failed.pdf"
    assert failed_item["status"] == "FAILED"
    assert failed_item["failure_reason"] == "Archivo no legible."
    assert "updated_at" in failed_item


def test_list_documents_multicriteria_filters_and_pagination(
    test_client: TestClient, sqlite_session: Session
):
    """Criterios de aceptación CDM-42:

    - Paginación con limit y offset y orden estable.
    - Filtros por nombre (search), tipo MIME (content_type) y estado.
    - Ocultamiento de storage_key interna en respuesta pública.
    - Aislamiento estricto de tenant (anti-IDOR).
    """
    u_a = UserModel(id=uuid4(), cognito_sub="sub-cat-a", email="cata@test.com")
    u_b = UserModel(id=uuid4(), cognito_sub="sub-cat-b", email="catb@test.com")
    ws_a = WorkspaceModel(id=uuid4(), name="WS Catalog A", slug="ws-cat-a", created_by=u_a.id)
    ws_b = WorkspaceModel(id=uuid4(), name="WS Catalog B", slug="ws-cat-b", created_by=u_b.id)

    m_a = WorkspaceMembershipModel(
        id=uuid4(), workspace_id=ws_a.id, user_id=u_a.id, role="OWNER", status="ACTIVE"
    )
    m_b = WorkspaceMembershipModel(
        id=uuid4(), workspace_id=ws_b.id, user_id=u_b.id, role="OWNER", status="ACTIVE"
    )

    doc_a1 = DocumentModel(
        id=uuid4(),
        workspace_id=ws_a.id,
        uploaded_by=u_a.id,
        original_filename="informe_financiero_2026.pdf",
        storage_key=f"tenants/{ws_a.id}/docs/a1.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        status=DocumentStatus.READY.value,
    )
    doc_a2 = DocumentModel(
        id=uuid4(),
        workspace_id=ws_a.id,
        uploaded_by=u_a.id,
        original_filename="informe_ventas_q1.docx",
        storage_key=f"tenants/{ws_a.id}/docs/a2.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=2000,
        status=DocumentStatus.READY.value,
    )
    doc_a3 = DocumentModel(
        id=uuid4(),
        workspace_id=ws_a.id,
        uploaded_by=u_a.id,
        original_filename="foto_producto.png",
        storage_key=f"tenants/{ws_a.id}/docs/a3.png",
        content_type="image/png",
        size_bytes=3000,
        status=DocumentStatus.PROCESSING.value,
    )

    # Documento señuelo en WS B con nombre idéntico para validar anti-IDOR
    doc_b_leak = DocumentModel(
        id=uuid4(),
        workspace_id=ws_b.id,
        uploaded_by=u_b.id,
        original_filename="informe_financiero_2026.pdf",
        storage_key=f"tenants/{ws_b.id}/docs/b_leak.pdf",
        content_type="application/pdf",
        size_bytes=9999,
        status=DocumentStatus.READY.value,
    )

    sqlite_session.add_all([u_a, u_b, ws_a, ws_b, m_a, m_b, doc_a1, doc_a2, doc_a3, doc_b_leak])
    sqlite_session.commit()

    test_client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        cognito_sub="sub-cat-a", email="cata@test.com"
    )

    # 1. Búsqueda por término parcial (case-insensitive) "informe" -> doc_a1 y doc_a2
    res_search = test_client.get(f"/api/v1/workspaces/{ws_a.id}/documents?search=INFORME")
    assert res_search.status_code == 200
    data_search = res_search.json()["data"]
    assert len(data_search) == 2
    filenames = {d["original_filename"] for d in data_search}
    assert filenames == {"informe_financiero_2026.pdf", "informe_ventas_q1.docx"}
    # Verificación de que no se fuga la storage_key física en respuestas públicas
    assert all(d["storage_key"] is None for d in data_search)

    # 2. Filtro por tipo MIME: image/png -> solo doc_a3
    res_mime = test_client.get(f"/api/v1/workspaces/{ws_a.id}/documents?content_type=image/png")
    assert res_mime.status_code == 200
    data_mime = res_mime.json()["data"]
    assert len(data_mime) == 1
    assert data_mime[0]["original_filename"] == "foto_producto.png"

    # 3. Paginación: limit=2, offset=0
    res_page1 = test_client.get(f"/api/v1/workspaces/{ws_a.id}/documents?limit=2&offset=0")
    assert res_page1.status_code == 200
    body_p1 = res_page1.json()
    assert len(body_p1["data"]) == 2
    assert body_p1["pagination"]["total"] == 3
    assert body_p1["pagination"]["has_more"] is True

    # Página 2: limit=2, offset=2
    res_page2 = test_client.get(f"/api/v1/workspaces/{ws_a.id}/documents?limit=2&offset=2")
    assert res_page2.status_code == 200
    body_p2 = res_page2.json()
    assert len(body_p2["data"]) == 1
    assert body_p2["pagination"]["has_more"] is False
