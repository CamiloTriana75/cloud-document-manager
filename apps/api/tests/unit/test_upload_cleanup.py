"""Pruebas unitarias para expiración, cancelación y limpieza de cargas incompletas (CDM-34).

Criterios de aceptación verificados:
- Upload sessions vencidas se marcan EXPIRED.
- Objetos temporales sin confirmación se eliminan según lifecycle.
- La limpieza no borra documentos confirmados (UPLOADED, PROCESSING, READY).
- Cancelación explícita marca CANCELLED y limpia objetos huérfanos.
- Prueba explícita de no eliminación de objetos y documentos válidos.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
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
    UploadSessionModel,
    UserModel,
    WorkspaceMembershipModel,
    WorkspaceModel,
)
from cdm.application.ports.document_repository import DocumentRepositoryPort
from cdm.application.ports.storage import StoragePort
from cdm.application.ports.upload_session_repository import UploadSessionRepositoryPort
from cdm.application.use_cases.upload_sessions import (
    CancelUploadSessionUseCase,
    CleanupExpiredUploadSessionsUseCase,
)
from cdm.bootstrap.app import create_app
from cdm.config.settings import Settings
from cdm.domain.document import Document, DocumentStatus
from cdm.domain.errors import (
    ConflictError,
    PermissionDeniedError,
    UploadSessionNotFoundError,
)
from cdm.domain.identity import AuthenticatedUser
from cdm.domain.tenant import TenantContext
from cdm.domain.upload_session import UploadSession, UploadSessionStatus
from cdm.domain.workspace import WorkspaceRole


class InMemorySessionDocRepo(DocumentRepositoryPort):
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


class InMemoryUploadSessionRepo(UploadSessionRepositoryPort):
    def __init__(self) -> None:
        self.sessions: dict[UUID, UploadSession] = {}

    def save(self, session: UploadSession) -> UploadSession:
        self.sessions[session.id] = session
        return session

    def get_by_id(self, session_id: UUID, workspace_id: UUID) -> UploadSession | None:
        sess = self.sessions.get(session_id)
        if sess is None or sess.workspace_id != workspace_id:
            return None
        return sess

    def get_by_document_id(self, document_id: UUID, workspace_id: UUID) -> UploadSession | None:
        for s in self.sessions.values():
            if s.document_id == document_id and s.workspace_id == workspace_id:
                return s
        return None

    def list_expired(self, workspace_id: UUID | None = None) -> list[UploadSession]:
        now = datetime.now(UTC)
        result = []
        for s in self.sessions.values():
            if (
                s.status == UploadSessionStatus.PENDING
                and s.expires_at <= now
                and (workspace_id is None or s.workspace_id == workspace_id)
            ):
                result.append(s)
        return result


class MockStorageWithTracking(StoragePort):
    def __init__(self) -> None:
        self.deleted_keys: list[str] = []
        self.objects: set[str] = set()

    def generate_download_url(
        self, storage_key: str, expires_in_seconds: int = 900, filename: str | None = None
    ) -> str:
        return f"https://s3/{storage_key}"

    def generate_upload_url(
        self, storage_key: str, content_type: str, size_bytes: int, expires_in_seconds: int = 900
    ) -> str:
        return f"https://s3/upload/{storage_key}"

    def get_object_metadata(self, storage_key: str):
        return None

    def delete_object(self, storage_key: str) -> bool:
        self.deleted_keys.append(storage_key)
        self.objects.discard(storage_key)
        return True


# ==============================================================================
# Pruebas Unitarias de Cancelación y Expiración
# ==============================================================================


def test_cancel_upload_session_success():
    """Cancelar una sesión PENDING la marca CANCELLED, el doc a FAILED y purga S3."""
    session_repo = InMemoryUploadSessionRepo()
    doc_repo = InMemorySessionDocRepo()
    storage = MockStorageWithTracking()

    ws_id = uuid4()
    user_id = uuid4()
    tenant = TenantContext(ws_id, user_id, "u@test.com", WorkspaceRole.MEMBER)

    doc = Document.create(
        ws_id, user_id, "archivo.pdf", "tenants/ws/doc.pdf", "application/pdf", 100
    )
    doc_repo.save(doc)

    session = UploadSession.create(
        ws_id, user_id, doc.id, "tenants/ws/doc.pdf", 100, "application/pdf"
    )
    session_repo.save(session)
    storage.objects.add("tenants/ws/doc.pdf")

    cancel_uc = CancelUploadSessionUseCase(session_repo, doc_repo, storage)
    cancel_uc.execute(tenant, session.id)

    # 1. Sesión queda CANCELLED
    updated_session = session_repo.sessions[session.id]
    assert updated_session.status == UploadSessionStatus.CANCELLED

    # 2. Documento queda FAILED
    updated_doc = doc_repo.docs[doc.id]
    assert updated_doc.status == DocumentStatus.FAILED

    # 3. Binario huérfano en S3 eliminado
    assert "tenants/ws/doc.pdf" in storage.deleted_keys


def test_cancel_upload_session_rejects_completed():
    """No se puede cancelar una sesión que ya ha sido completada exitosamente (Conflict)."""
    session_repo = InMemoryUploadSessionRepo()
    doc_repo = InMemorySessionDocRepo()
    storage = MockStorageWithTracking()

    ws_id = uuid4()
    tenant = TenantContext(ws_id, uuid4(), "u@test.com", WorkspaceRole.MEMBER)
    doc = Document.create(ws_id, tenant.user_id, "doc.pdf", "key", "application/pdf", 100)
    doc_repo.save(doc)

    session = UploadSession.create(ws_id, tenant.user_id, doc.id, "key", 100, "application/pdf")
    completed_session = session.mark_completed()
    session_repo.save(completed_session)

    cancel_uc = CancelUploadSessionUseCase(session_repo, doc_repo, storage)
    with pytest.raises(ConflictError) as exc:
        cancel_uc.execute(tenant, completed_session.id)

    assert "ya ha sido completada" in str(exc.value)


def test_cancel_upload_session_cross_tenant_isolation():
    """Un usuario no puede cancelar sesiones de carga de otro workspace (404 anti-IDOR)."""
    session_repo = InMemoryUploadSessionRepo()
    doc_repo = InMemorySessionDocRepo()
    storage = MockStorageWithTracking()

    ws_a = uuid4()
    ws_b = uuid4()
    tenant_a = TenantContext(ws_a, uuid4(), "a@test.com", WorkspaceRole.ADMIN)

    session_b = UploadSession.create(ws_b, uuid4(), uuid4(), "keyB", 100, "application/pdf")
    session_repo.save(session_b)

    cancel_uc = CancelUploadSessionUseCase(session_repo, doc_repo, storage)
    with pytest.raises(UploadSessionNotFoundError):
        cancel_uc.execute(tenant_a, session_b.id)


def test_cancel_upload_session_viewer_rejected():
    """Un rol VIEWER no puede cancelar sesiones de carga (403)."""
    session_repo = InMemoryUploadSessionRepo()
    doc_repo = InMemorySessionDocRepo()
    storage = MockStorageWithTracking()

    ws = uuid4()
    viewer_tenant = TenantContext(ws, uuid4(), "v@test.com", WorkspaceRole.VIEWER)
    session = UploadSession.create(ws, uuid4(), uuid4(), "key", 100, "application/pdf")
    session_repo.save(session)

    cancel_uc = CancelUploadSessionUseCase(session_repo, doc_repo, storage)
    with pytest.raises(PermissionDeniedError):
        cancel_uc.execute(viewer_tenant, session.id)


# ==============================================================================
# Pruebas de Limpieza de Sesiones Expiradas e Invariante de No Eliminación
# ==============================================================================


def test_cleanup_expired_sessions_and_orphan_objects():
    """Sesiones expiradas pasan a EXPIRED, doc a FAILED y binario huérfano se purga."""
    session_repo = InMemoryUploadSessionRepo()
    doc_repo = InMemorySessionDocRepo()
    storage = MockStorageWithTracking()

    ws_id = uuid4()
    user_id = uuid4()

    # Sesión expirada (expiró hace 10 minutos)
    expired_time = datetime.now(UTC) - timedelta(minutes=10)
    doc_orphan = Document.create(
        ws_id, user_id, "abandonado.pdf", "key_orphan", "application/pdf", 100
    )
    doc_repo.save(doc_orphan)

    session_expired = UploadSession(
        id=uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        document_id=doc_orphan.id,
        storage_key="key_orphan",
        expected_size_bytes=100,
        expected_content_type="application/pdf",
        status=UploadSessionStatus.PENDING,
        expires_at=expired_time,
    )
    session_repo.save(session_expired)
    storage.objects.add("key_orphan")

    cleanup_uc = CleanupExpiredUploadSessionsUseCase(session_repo, doc_repo, storage)
    report = cleanup_uc.execute(workspace_id=ws_id)

    assert report.expired_sessions_count == 1
    assert report.cleaned_objects_count == 1
    assert report.skipped_confirmed_documents_count == 0

    # Estado final verificado
    assert session_repo.sessions[session_expired.id].status == UploadSessionStatus.EXPIRED
    assert doc_repo.docs[doc_orphan.id].status == DocumentStatus.FAILED
    assert "key_orphan" in storage.deleted_keys


def test_cleanup_preserves_confirmed_documents_invariantly():
    """CRITERIO 3 & 5: Limpieza NUNCA borra documentos UPLOADED o READY ni sus claves S3."""
    session_repo = InMemoryUploadSessionRepo()
    doc_repo = InMemorySessionDocRepo()
    storage = MockStorageWithTracking()

    ws_id = uuid4()
    user_id = uuid4()
    past_time = datetime.now(UTC) - timedelta(minutes=5)

    # 1. Documento válido UPLOADED
    doc_uploaded = Document.create(
        ws_id, user_id, "confirmado.pdf", "key_uploaded", "application/pdf", 500
    )
    doc_uploaded = doc_uploaded.transition_to(DocumentStatus.UPLOADED)
    doc_repo.save(doc_uploaded)

    session_for_uploaded = UploadSession(
        id=uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        document_id=doc_uploaded.id,
        storage_key="key_uploaded",
        expected_size_bytes=500,
        expected_content_type="application/pdf",
        status=UploadSessionStatus.PENDING,
        expires_at=past_time,
    )
    session_repo.save(session_for_uploaded)
    storage.objects.add("key_uploaded")

    # 2. Documento válido READY
    doc_ready = Document.create(ws_id, user_id, "listo.pdf", "key_ready", "application/pdf", 700)
    doc_ready = doc_ready.transition_to(DocumentStatus.READY)
    doc_repo.save(doc_ready)

    session_for_ready = UploadSession(
        id=uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        document_id=doc_ready.id,
        storage_key="key_ready",
        expected_size_bytes=700,
        expected_content_type="application/pdf",
        status=UploadSessionStatus.PENDING,
        expires_at=past_time,
    )
    session_repo.save(session_for_ready)
    storage.objects.add("key_ready")

    # Ejecutar limpieza
    cleanup_uc = CleanupExpiredUploadSessionsUseCase(session_repo, doc_repo, storage)
    report = cleanup_uc.execute(workspace_id=ws_id)

    # Verificación de preservación total
    assert report.skipped_confirmed_documents_count == 2
    assert report.expired_sessions_count == 0
    assert report.cleaned_objects_count == 0

    # Las claves S3 NO fueron borradas
    assert "key_uploaded" not in storage.deleted_keys
    assert "key_ready" not in storage.deleted_keys

    # Los documentos permanecen intactos
    assert doc_repo.docs[doc_uploaded.id].status == DocumentStatus.UPLOADED
    assert doc_repo.docs[doc_ready.id].status == DocumentStatus.READY


# ==============================================================================
# Pruebas de Endpoints HTTP (FastAPI + SQLite)
# ==============================================================================


@pytest.fixture
def sqlite_test_db() -> Iterator[Session]:
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
def test_http_client(sqlite_test_db: Session) -> TestClient:
    settings = Settings(
        database_url="sqlite:///:memory:",
        cors_origins="*",
        cognito_user_pool_id="us-east-1_mock",
        cognito_client_id="mock-client-id",
        cognito_region="us-east-1",
    )
    app = create_app(settings)

    def override_db() -> Iterator[Session]:
        yield sqlite_test_db

    app.dependency_overrides[get_db_session] = override_db
    return TestClient(app)


def test_cancel_endpoint_flow(test_http_client: TestClient, sqlite_test_db: Session):
    """Endpoint POST /{workspace_id}/upload-sessions/{session_id}/cancel cancela sesión."""
    user = UserModel(id=uuid4(), cognito_sub="sub-member", email="member@test.com")
    ws = WorkspaceModel(id=uuid4(), name="WS Cancel", slug="ws-cancel", created_by=user.id)
    membership = WorkspaceMembershipModel(
        id=uuid4(), workspace_id=ws.id, user_id=user.id, role="MEMBER", status="ACTIVE"
    )
    doc = DocumentModel(
        id=uuid4(),
        workspace_id=ws.id,
        uploaded_by=user.id,
        original_filename="doc.pdf",
        storage_key="key",
        content_type="application/pdf",
        size_bytes=100,
        status="PENDING_UPLOAD",
    )
    session = UploadSessionModel(
        id=uuid4(),
        workspace_id=ws.id,
        user_id=user.id,
        document_id=doc.id,
        storage_key="key",
        expected_size_bytes=100,
        expected_content_type="application/pdf",
        status="PENDING",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    sqlite_test_db.add_all([user, ws, membership, doc, session])
    sqlite_test_db.commit()

    auth_member = AuthenticatedUser(cognito_sub="sub-member", email="member@test.com")
    test_http_client.app.dependency_overrides[get_current_user] = lambda: auth_member

    res = test_http_client.post(f"/api/v1/workspaces/{ws.id}/upload-sessions/{session.id}/cancel")
    assert res.status_code == 200
    assert "cancelada exitosamente" in res.json()["data"]["message"]

    # Re-consultar DB
    db_session = sqlite_test_db.get(UploadSessionModel, session.id)
    assert db_session is not None
    assert db_session.status == "CANCELLED"


def test_cleanup_endpoint_requires_admin(test_http_client: TestClient, sqlite_test_db: Session):
    """Endpoint POST /{workspace_id}/upload-sessions/cleanup requiere rol ADMIN o superior."""
    owner = UserModel(id=uuid4(), cognito_sub="sub-owner", email="owner@test.com")
    member = UserModel(id=uuid4(), cognito_sub="sub-member", email="member@test.com")
    ws = WorkspaceModel(id=uuid4(), name="WS Cleanup", slug="ws-cleanup", created_by=owner.id)

    m_owner = WorkspaceMembershipModel(
        id=uuid4(), workspace_id=ws.id, user_id=owner.id, role="OWNER", status="ACTIVE"
    )
    m_member = WorkspaceMembershipModel(
        id=uuid4(), workspace_id=ws.id, user_id=member.id, role="MEMBER", status="ACTIVE"
    )
    sqlite_test_db.add_all([owner, member, ws, m_owner, m_member])
    sqlite_test_db.commit()

    # 1. MEMBER recibe 403 Forbidden
    auth_member = AuthenticatedUser(cognito_sub="sub-member", email="member@test.com")
    test_http_client.app.dependency_overrides[get_current_user] = lambda: auth_member

    res_member = test_http_client.post(f"/api/v1/workspaces/{ws.id}/upload-sessions/cleanup")
    assert res_member.status_code == 403
    assert res_member.json()["error"]["code"] == "permission_denied"

    # 2. OWNER recibe 200 OK con el reporte
    auth_owner = AuthenticatedUser(cognito_sub="sub-owner", email="owner@test.com")
    test_http_client.app.dependency_overrides[get_current_user] = lambda: auth_owner

    res_owner = test_http_client.post(f"/api/v1/workspaces/{ws.id}/upload-sessions/cleanup")
    assert res_owner.status_code == 200
    report_data = res_owner.json()["data"]
    assert "expired_sessions_count" in report_data
    assert "cleaned_objects_count" in report_data
    assert "skipped_confirmed_documents_count" in report_data
