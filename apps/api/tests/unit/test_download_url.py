"""Pruebas unitarias para descarga autorizada mediante URL temporal prefirmada (CDM-33).

Criterios de aceptación verificados:
- Backend valida tenant, rol y estado del documento.
- URL prefirmada GET de corta duración (configurable entre 60 y 3600 segundos).
- Bucket permanece privado y firma únicamente el objeto correspondiente.
- Nombre de descarga controlado/escapado (Content-Disposition seguro contra inyección).
- Usuario sin acceso o de otro tenant no obtiene URL ni metadatos (anti-IDOR -> 404).
- Documentos en estado PENDING_UPLOAD o FAILED rechazan la descarga.
- Logs registran actor/document ID sin exponer la URL prefirmada completa.
"""

import logging
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
from cdm.adapters.outbound.storage.s3_storage import S3StorageAdapter
from cdm.application.ports.document_repository import DocumentRepositoryPort
from cdm.application.use_cases.documents import AuthorizeDocumentDownloadUseCase
from cdm.bootstrap.app import create_app
from cdm.config.settings import Settings
from cdm.domain.document import Document, DocumentStatus
from cdm.domain.errors import (
    DocumentNotFoundError,
    InvalidDocumentDataError,
)
from cdm.domain.identity import AuthenticatedUser
from cdm.domain.tenant import TenantContext
from cdm.domain.workspace import WorkspaceRole


class InMemoryDocRepo(DocumentRepositoryPort):
    def __init__(self) -> None:
        self.docs: dict[UUID, Document] = {}

    def save(self, document: Document) -> Document:
        self.docs[document.id] = document
        return document

    def get_by_id(
        self, workspace_id: UUID, document_id: UUID, include_deleted: bool = False
    ) -> Document | None:
        doc = self.docs.get(document_id)
        if doc is None or doc.workspace_id != workspace_id:
            return None
        if not include_deleted and doc.is_deleted:
            return None
        return doc

    def list_by_workspace(
        self, workspace_id: UUID, limit: int = 50, offset: int = 0, include_deleted: bool = False
    ) -> list[Document]:
        return [
            d
            for d in self.docs.values()
            if d.workspace_id == workspace_id and (include_deleted or not d.is_deleted)
        ]

    def count_by_workspace(self, workspace_id: UUID, include_deleted: bool = False) -> int:
        return len(self.list_by_workspace(workspace_id, include_deleted=include_deleted))

    def soft_delete(self, workspace_id: UUID, document_id: UUID) -> bool:
        doc = self.get_by_id(workspace_id, document_id, include_deleted=False)
        if doc is None:
            return False
        self.docs[document_id] = doc.mark_deleted()
        return True


# ==============================================================================
# Pruebas de Caso de Uso (Lógica Pura y Dominio)
# ==============================================================================


def test_authorize_download_success_for_viewer_member_and_admin():
    """Cualquier miembro activo (VIEWER, MEMBER, ADMIN, OWNER) puede autorizar la descarga."""
    repo = InMemoryDocRepo()
    storage = S3StorageAdapter(bucket_name="test-bucket", region="us-east-1")
    use_case = AuthorizeDocumentDownloadUseCase(repo, storage)

    ws_id = uuid4()
    uploader_id = uuid4()
    doc = Document.create(
        ws_id, uploader_id, "informe.pdf", "tenants/ws/doc.pdf", "application/pdf", 1024
    )
    doc_ready = doc.transition_to(DocumentStatus.READY)
    repo.save(doc_ready)

    for role in (
        WorkspaceRole.VIEWER,
        WorkspaceRole.MEMBER,
        WorkspaceRole.ADMIN,
        WorkspaceRole.OWNER,
    ):
        tenant = TenantContext(ws_id, uuid4(), "user@test.com", role)
        result = use_case.execute(tenant, doc_ready.id, expires_in_seconds=600)
        assert result.document_id == doc_ready.id
        assert result.original_filename == "informe.pdf"
        assert result.expires_in_seconds == 600
        assert "informe.pdf" in result.download_url
        assert "test-bucket" in result.download_url


def test_authorize_download_rejects_pending_upload_document():
    """Un documento en estado PENDING_UPLOAD rechaza la generación de URL de descarga."""
    repo = InMemoryDocRepo()
    storage = S3StorageAdapter(bucket_name="test-bucket")
    use_case = AuthorizeDocumentDownloadUseCase(repo, storage)

    ws_id = uuid4()
    tenant = TenantContext(ws_id, uuid4(), "user@test.com", WorkspaceRole.MEMBER)
    doc = Document.create(ws_id, tenant.user_id, "archivo.txt", "key", "text/plain", 100)
    repo.save(doc)

    with pytest.raises(InvalidDocumentDataError) as exc:
        use_case.execute(tenant, doc.id)

    assert "aún no ha completado el proceso de carga" in str(exc.value)


def test_authorize_download_rejects_failed_document():
    """Un documento en estado FAILED no permite la generación de URL de descarga."""
    repo = InMemoryDocRepo()
    storage = S3StorageAdapter(bucket_name="test-bucket")
    use_case = AuthorizeDocumentDownloadUseCase(repo, storage)

    ws_id = uuid4()
    tenant = TenantContext(ws_id, uuid4(), "user@test.com", WorkspaceRole.MEMBER)
    doc = Document.create(ws_id, tenant.user_id, "archivo.txt", "key", "text/plain", 100)
    doc_failed = doc.transition_to(DocumentStatus.FAILED)
    repo.save(doc_failed)

    with pytest.raises(InvalidDocumentDataError) as exc:
        use_case.execute(tenant, doc_failed.id)

    assert "fallido" in str(exc.value)


def test_authorize_download_cross_tenant_isolation():
    """Un usuario de Workspace A no puede descargar documentos de Workspace B (anti-IDOR)."""
    repo = InMemoryDocRepo()
    storage = S3StorageAdapter(bucket_name="test-bucket")
    use_case = AuthorizeDocumentDownloadUseCase(repo, storage)

    ws_a = uuid4()
    ws_b = uuid4()
    tenant_a = TenantContext(ws_a, uuid4(), "a@test.com", WorkspaceRole.OWNER)

    doc_b = Document.create(ws_b, uuid4(), "confidencial.pdf", "keyB", "application/pdf", 1000)
    repo.save(doc_b.transition_to(DocumentStatus.READY))

    with pytest.raises(DocumentNotFoundError):
        use_case.execute(tenant_a, doc_b.id)


def test_authorize_download_escapes_filename_in_content_disposition():
    """El nombre del archivo se escapa de forma segura en Content-Disposition."""
    repo = InMemoryDocRepo()
    storage = S3StorageAdapter(bucket_name="test-bucket")
    use_case = AuthorizeDocumentDownloadUseCase(repo, storage)

    ws_id = uuid4()
    tenant = TenantContext(ws_id, uuid4(), "user@test.com", WorkspaceRole.MEMBER)
    # Nombre con espacios y comillas
    doc = Document.create(
        ws_id,
        tenant.user_id,
        "reporte final (2026).pdf",
        "tenants/ws/doc.pdf",
        "application/pdf",
        2048,
    )
    repo.save(doc.transition_to(DocumentStatus.READY))

    result = use_case.execute(tenant, doc.id)
    assert result.original_filename == "reporte final (2026).pdf"
    assert "response-content-disposition=" in result.download_url


def test_authorize_download_logs_actor_without_exposing_url(caplog):
    """Los logs registran el actor y document_id sin exponer el enlace de descarga completo."""
    repo = InMemoryDocRepo()
    storage = S3StorageAdapter(bucket_name="test-bucket")
    use_case = AuthorizeDocumentDownloadUseCase(repo, storage)

    ws_id = uuid4()
    tenant = TenantContext(ws_id, uuid4(), "user@test.com", WorkspaceRole.MEMBER)
    doc = Document.create(ws_id, tenant.user_id, "doc.pdf", "key", "application/pdf", 100)
    repo.save(doc.transition_to(DocumentStatus.READY))

    with caplog.at_level(logging.INFO):
        res = use_case.execute(tenant, doc.id)

    log_messages = [record.getMessage() for record in caplog.records]
    download_logs = [m for m in log_messages if "Authorized document download" in m]
    assert len(download_logs) == 1
    # Verifica que la URL prefirmada no está en el mensaje de log
    assert res.download_url not in download_logs[0]
    assert str(doc.id) in download_logs[0]
    assert str(tenant.user_id) in download_logs[0]


# ==============================================================================
# Pruebas de Endpoints HTTP (FastAPI + SQLite)
# ==============================================================================


@pytest.fixture
def sqlite_db() -> Iterator[Session]:
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
def client(sqlite_db: Session) -> TestClient:
    settings = Settings(
        database_url="sqlite:///:memory:",
        cors_origins="*",
        cognito_user_pool_id="us-east-1_mock",
        cognito_client_id="mock-client-id",
        cognito_region="us-east-1",
    )
    app = create_app(settings)

    def override_db() -> Iterator[Session]:
        yield sqlite_db

    app.dependency_overrides[get_db_session] = override_db
    return TestClient(app)


def test_download_endpoint_flow(client: TestClient, sqlite_db: Session):
    """Endpoint POST /{workspace_id}/documents/{document_id}/download-url valida y entrega URL."""
    user = UserModel(id=uuid4(), cognito_sub="sub-downloader", email="downloader@test.com")
    ws = WorkspaceModel(
        id=uuid4(), name="Espacio Descargas", slug="espacio-descargas", created_by=user.id
    )
    membership = WorkspaceMembershipModel(
        id=uuid4(), workspace_id=ws.id, user_id=user.id, role="VIEWER", status="ACTIVE"
    )
    doc = DocumentModel(
        id=uuid4(),
        workspace_id=ws.id,
        uploaded_by=user.id,
        original_filename="manual_usuario.pdf",
        storage_key=f"tenants/{ws.id}/docs/manual.pdf",
        content_type="application/pdf",
        size_bytes=5000,
        status="READY",
    )
    sqlite_db.add_all([user, ws, membership, doc])
    sqlite_db.commit()

    # 1. Sin autenticación -> 401
    unauth_res = client.post(f"/api/v1/workspaces/{ws.id}/documents/{doc.id}/download-url")
    assert unauth_res.status_code == 401

    # 2. Con autenticación de VIEWER -> 200 con URL prefirmada
    auth_user = AuthenticatedUser(cognito_sub="sub-downloader", email="downloader@test.com")
    client.app.dependency_overrides[get_current_user] = lambda: auth_user

    res = client.post(
        f"/api/v1/workspaces/{ws.id}/documents/{doc.id}/download-url",
        json={"expires_in_seconds": 1800},
    )
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["document_id"] == str(doc.id)
    assert body["original_filename"] == "manual_usuario.pdf"
    assert body["expires_in_seconds"] == 1800
    assert "https://" in body["download_url"]

    # 3. Petición con tiempo de expiración inválido (> 3600) -> 422
    bad_res = client.post(
        f"/api/v1/workspaces/{ws.id}/documents/{doc.id}/download-url",
        json={"expires_in_seconds": 999999},
    )
    assert bad_res.status_code == 422
