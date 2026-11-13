"""Pruebas unitarias de casos de uso de Documentos y Aislamiento por Tenant (CDM-27).

Valida los criterios de aceptación de CDM-27:
- tenant_id se incluye obligatoriamente en todas las lecturas/escrituras.
- Los repositorios no exponen búsquedas globales accidentales.
- Las acciones por rol se validan en la capa de aplicación.
- Pruebas de acceso cruzado pasan para list, detail, download y delete.
"""

from uuid import UUID, uuid4

import pytest

from cdm.application.ports.document_repository import DocumentRepositoryPort
from cdm.application.ports.storage import StoragePort
from cdm.application.use_cases.documents import (
    AuthorizeDocumentDownloadUseCase,
    CreateDocumentRecordUseCase,
    DeleteDocumentUseCase,
    GetDocumentDetailUseCase,
    ListDocumentsUseCase,
)
from cdm.domain.document import Document, DocumentStatus
from cdm.domain.errors import DocumentNotFoundError, PermissionDeniedError
from cdm.domain.tenant import TenantContext
from cdm.domain.workspace import WorkspaceRole


class InMemoryDocumentRepository(DocumentRepositoryPort):
    def __init__(self) -> None:
        self.documents: dict[UUID, Document] = {}

    def save(self, document: Document) -> Document:
        self.documents[document.id] = document
        return document

    def get_by_id(
        self,
        workspace_id: UUID,
        document_id: UUID,
        include_deleted: bool = False,
    ) -> Document | None:
        doc = self.documents.get(document_id)
        if doc is None or doc.workspace_id != workspace_id:
            return None
        if not include_deleted and doc.is_deleted:
            return None
        return doc

    def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
        status: DocumentStatus | None = None,
    ) -> list[Document]:
        items = [
            doc
            for doc in self.documents.values()
            if doc.workspace_id == workspace_id
            and (status is None or doc.status == status)
            and (status is not None or include_deleted or not doc.is_deleted)
        ]
        items.sort(key=lambda d: d.created_at, reverse=True)
        return items[offset : offset + limit]

    def count_by_workspace(
        self,
        workspace_id: UUID,
        include_deleted: bool = False,
        status: DocumentStatus | None = None,
    ) -> int:
        return sum(
            1
            for doc in self.documents.values()
            if doc.workspace_id == workspace_id
            and (status is None or doc.status == status)
            and (status is not None or include_deleted or not doc.is_deleted)
        )

    def soft_delete(self, workspace_id: UUID, document_id: UUID) -> bool:
        doc = self.get_by_id(workspace_id, document_id, include_deleted=False)
        if doc is None:
            return False
        self.documents[document_id] = doc.mark_deleted()
        return True


class MockStorageService(StoragePort):
    def generate_download_url(
        self,
        storage_key: str,
        expires_in_seconds: int = 900,
        filename: str | None = None,
    ) -> str:
        return f"https://mock-s3.amazonaws.com/{storage_key}?expires={expires_in_seconds}"


@pytest.fixture
def doc_repo():
    return InMemoryDocumentRepository()


@pytest.fixture
def storage():
    return MockStorageService()


def test_cross_tenant_list_isolation(doc_repo):
    """Listar documentos solo retorna los pertenecientes al tenant del TenantContext."""
    ws_a = uuid4()
    ws_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()

    tenant_a = TenantContext(ws_a, user_a, "user_a@test.com", WorkspaceRole.MEMBER)
    tenant_b = TenantContext(ws_b, user_b, "user_b@test.com", WorkspaceRole.MEMBER)

    # Crear 2 documentos en Workspace A
    doc_repo.save(Document.create(ws_a, user_a, "docA1.pdf", "keyA1", "application/pdf", 100))
    doc_repo.save(Document.create(ws_a, user_a, "docA2.pdf", "keyA2", "application/pdf", 200))

    # Crear 1 documento en Workspace B
    doc_repo.save(Document.create(ws_b, user_b, "docB1.pdf", "keyB1", "application/pdf", 300))

    list_uc = ListDocumentsUseCase(doc_repo)

    result_a = list_uc.execute(tenant_a)
    assert result_a.total == 2
    assert len(result_a.items) == 2
    assert all(d.workspace_id == ws_a for d in result_a.items)

    result_b = list_uc.execute(tenant_b)
    assert result_b.total == 1
    assert len(result_b.items) == 1
    assert result_b.items[0].workspace_id == ws_b


def test_cross_tenant_detail_isolation(doc_repo):
    """Intentar acceder al detalle de un documento de otro tenant lanza DocumentNotFoundError."""
    ws_a = uuid4()
    ws_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()

    tenant_a = TenantContext(ws_a, user_a, "user_a@test.com", WorkspaceRole.MEMBER)

    doc_b = doc_repo.save(
        Document.create(ws_b, user_b, "secreto.pdf", "keyB", "application/pdf", 500)
    )

    detail_uc = GetDocumentDetailUseCase(doc_repo)

    with pytest.raises(DocumentNotFoundError):
        detail_uc.execute(tenant_a, doc_b.id)


def test_cross_tenant_download_isolation(doc_repo, storage):
    """Intentar descargar un documento de otro tenant lanza DocumentNotFoundError."""
    ws_a = uuid4()
    ws_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()

    tenant_a = TenantContext(ws_a, user_a, "user_a@test.com", WorkspaceRole.MEMBER)

    doc_b = Document.create(ws_b, user_b, "secreto.pdf", "keyB", "application/pdf", 500)
    doc_b_ready = doc_b.transition_to(DocumentStatus.READY)
    doc_repo.save(doc_b_ready)

    download_uc = AuthorizeDocumentDownloadUseCase(doc_repo, storage)

    with pytest.raises(DocumentNotFoundError):
        download_uc.execute(tenant_a, doc_b_ready.id)


def test_cross_tenant_delete_isolation(doc_repo):
    """Intentar eliminar un documento de otro tenant lanza DocumentNotFoundError."""
    ws_a = uuid4()
    ws_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()

    # Usuario A es OWNER en Workspace A
    tenant_a = TenantContext(ws_a, user_a, "user_a@test.com", WorkspaceRole.OWNER)

    # Documento pertenece a Workspace B
    doc_b = doc_repo.save(
        Document.create(ws_b, user_b, "archivo_b.pdf", "keyB", "application/pdf", 100)
    )

    delete_uc = DeleteDocumentUseCase(doc_repo)

    with pytest.raises(DocumentNotFoundError):
        delete_uc.execute(tenant_a, doc_b.id)

    # Verificar que el documento de B no fue alterado
    assert not doc_repo.documents[doc_b.id].is_deleted


def test_role_enforcement_viewer_cannot_upload(doc_repo):
    """Un usuario con rol VIEWER no puede crear ni registrar documentos."""
    ws = uuid4()
    user = uuid4()
    viewer_tenant = TenantContext(ws, user, "viewer@test.com", WorkspaceRole.VIEWER)

    create_uc = CreateDocumentRecordUseCase(doc_repo)

    with pytest.raises(PermissionDeniedError):
        create_uc.execute(
            tenant=viewer_tenant,
            original_filename="doc.pdf",
            storage_key="key",
            content_type="application/pdf",
            size_bytes=100,
        )


def test_role_enforcement_delete_requires_editor_or_higher(doc_repo):
    """MEMBER y VIEWER no pueden eliminar documentos; EDITOR, ADMIN y OWNER sí pueden."""
    ws = uuid4()
    user = uuid4()

    viewer = TenantContext(ws, user, "viewer@test.com", WorkspaceRole.VIEWER)
    member = TenantContext(ws, user, "member@test.com", WorkspaceRole.MEMBER)
    editor = TenantContext(ws, user, "editor@test.com", WorkspaceRole.EDITOR)

    doc = doc_repo.save(Document.create(ws, user, "doc.pdf", "key", "application/pdf", 100))

    delete_uc = DeleteDocumentUseCase(doc_repo)

    # VIEWER falla
    with pytest.raises(PermissionDeniedError):
        delete_uc.execute(viewer, doc.id)

    # MEMBER falla
    with pytest.raises(PermissionDeniedError):
        delete_uc.execute(member, doc.id)

    # EDITOR triunfa
    delete_uc.execute(editor, doc.id)
    assert doc_repo.documents[doc.id].is_deleted
