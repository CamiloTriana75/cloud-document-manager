"""Pruebas unitarias para Retry Controlado de Documentos Fallidos (CDM-39).

Criterios de aceptación (CDM-39):
1. Solo ADMIN u OWNER pueden ejecutar el reintento manual (MEMBER y VIEWER reciben 403).
2. Aislamiento estricto por workspace_id (documento de otro tenant retorna 404).
3. Solo documentos en estado FAILED pueden reintentarse.
4. Límite máximo de reintentos acotado (MAX_DOCUMENT_RETRIES = 3, reintento 4 lanza error 409).
5. Reintento reinicia estado a PROCESSING, incrementa contador y limpia failure_reason.
6. Endpoint HTTP POST /api/v1/workspaces/.../documents/.../retry con respuestas estables.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from cdm.adapters.inbound.http.dependencies import (
    get_current_user,
    get_db_session,
    get_retry_document_processing_use_case,
    get_tenant_context,
)
from cdm.application.ports.document_repository import DocumentRepositoryPort
from cdm.application.use_cases.documents import (
    RetryDocumentProcessingUseCase,
)
from cdm.bootstrap.app import create_app
from cdm.domain.document import MAX_DOCUMENT_RETRIES, Document, DocumentStatus
from cdm.domain.errors import (
    DocumentNotFoundError,
    InvalidDocumentDataError,
    MaxRetriesExceededError,
    PermissionDeniedError,
)
from cdm.domain.identity import AuthenticatedUser
from cdm.domain.tenant import TenantContext
from cdm.domain.workspace import MembershipStatus, WorkspaceRole


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
        return items[offset : offset + limit]

    def count_by_workspace(
        self,
        workspace_id: UUID,
        include_deleted: bool = False,
        status: DocumentStatus | None = None,
    ) -> int:
        return len(self.list_by_workspace(workspace_id, 1000, 0, include_deleted, status))

    def delete_logically(self, workspace_id: UUID, document_id: UUID) -> bool:
        doc = self.get_by_id(workspace_id, document_id)
        if doc is None:
            return False
        self.documents[document_id] = doc.mark_deleted()
        return True


def _make_tenant(workspace_id: UUID, user_id: UUID, role: WorkspaceRole) -> TenantContext:
    return TenantContext(
        workspace_id=workspace_id,
        user_id=user_id,
        user_email="admin@test.com",
        role=role,
        status=MembershipStatus.ACTIVE,
    )


def _make_failed_doc(workspace_id: UUID, user_id: UUID, retry_count: int = 0) -> Document:
    doc = Document.create(
        workspace_id=workspace_id,
        uploaded_by=user_id,
        original_filename="archivo_error.pdf",
        storage_key=f"tenants/{workspace_id}/documents/{uuid4()}/archivo_error.pdf",
        content_type="application/pdf",
        size_bytes=1024,
    )
    # Marcar como fallido con razón y retry_count opcional
    failed_doc = doc.mark_failed("Fallo de conexión transitorio.")
    if retry_count > 0:
        meta = dict(failed_doc.technical_metadata)
        meta["retry_count"] = retry_count
        failed_doc = Document(
            id=failed_doc.id,
            workspace_id=failed_doc.workspace_id,
            uploaded_by=failed_doc.uploaded_by,
            original_filename=failed_doc.original_filename,
            storage_key=failed_doc.storage_key,
            content_type=failed_doc.content_type,
            size_bytes=failed_doc.size_bytes,
            checksum_sha256=failed_doc.checksum_sha256,
            status=DocumentStatus.FAILED,
            technical_metadata=meta,
            created_at=failed_doc.created_at,
            updated_at=failed_doc.updated_at,
        )
    return failed_doc


# --- Pruebas del Caso de Uso ---


def test_retry_processing_success_as_admin() -> None:
    ws_id = uuid4()
    user_id = uuid4()
    repo = InMemoryDocumentRepository()
    use_case = RetryDocumentProcessingUseCase(document_repo=repo)

    doc = _make_failed_doc(ws_id, user_id)
    repo.save(doc)

    admin_tenant = _make_tenant(ws_id, user_id, WorkspaceRole.ADMIN)
    result = use_case.execute(tenant=admin_tenant, document_id=doc.id)

    assert result.status == DocumentStatus.PROCESSING
    assert result.retry_count == 1
    assert result.failure_reason is None

    # Verificar persistencia en repositorio
    persisted = repo.get_by_id(ws_id, doc.id)
    assert persisted is not None
    assert persisted.status == DocumentStatus.PROCESSING
    assert persisted.retry_count == 1


def test_retry_processing_success_as_owner() -> None:
    ws_id = uuid4()
    user_id = uuid4()
    repo = InMemoryDocumentRepository()
    use_case = RetryDocumentProcessingUseCase(document_repo=repo)

    doc = _make_failed_doc(ws_id, user_id)
    repo.save(doc)

    owner_tenant = _make_tenant(ws_id, user_id, WorkspaceRole.OWNER)
    result = use_case.execute(tenant=owner_tenant, document_id=doc.id)

    assert result.status == DocumentStatus.PROCESSING
    assert result.retry_count == 1


def test_retry_processing_forbidden_for_member_and_viewer() -> None:
    ws_id = uuid4()
    user_id = uuid4()
    repo = InMemoryDocumentRepository()
    use_case = RetryDocumentProcessingUseCase(document_repo=repo)

    doc = _make_failed_doc(ws_id, user_id)
    repo.save(doc)

    member_tenant = _make_tenant(ws_id, user_id, WorkspaceRole.MEMBER)
    with pytest.raises(PermissionDeniedError):
        use_case.execute(tenant=member_tenant, document_id=doc.id)

    viewer_tenant = _make_tenant(ws_id, user_id, WorkspaceRole.VIEWER)
    with pytest.raises(PermissionDeniedError):
        use_case.execute(tenant=viewer_tenant, document_id=doc.id)


def test_retry_processing_not_found_on_other_tenant_document() -> None:
    ws_owner = uuid4()
    ws_attacker = uuid4()
    user_id = uuid4()
    repo = InMemoryDocumentRepository()
    use_case = RetryDocumentProcessingUseCase(document_repo=repo)

    # Documento pertenece a ws_owner
    doc = _make_failed_doc(ws_owner, user_id)
    repo.save(doc)

    # Administrador de ws_attacker intenta reintentar documento de ws_owner
    attacker_tenant = _make_tenant(ws_attacker, user_id, WorkspaceRole.ADMIN)
    with pytest.raises(DocumentNotFoundError):
        use_case.execute(tenant=attacker_tenant, document_id=doc.id)


def test_retry_processing_fails_if_document_not_in_failed_status() -> None:
    ws_id = uuid4()
    user_id = uuid4()
    repo = InMemoryDocumentRepository()
    use_case = RetryDocumentProcessingUseCase(document_repo=repo)

    # Documento en estado READY
    ready_doc = Document.create(
        workspace_id=ws_id,
        uploaded_by=user_id,
        original_filename="listo.pdf",
        storage_key=f"tenants/{ws_id}/documents/{uuid4()}/listo.pdf",
        content_type="application/pdf",
        size_bytes=1024,
    ).transition_to(DocumentStatus.READY)
    repo.save(ready_doc)

    admin_tenant = _make_tenant(ws_id, user_id, WorkspaceRole.ADMIN)
    with pytest.raises(InvalidDocumentDataError) as exc_info:
        use_case.execute(tenant=admin_tenant, document_id=ready_doc.id)
    assert "Solo documentos en FAILED pueden reintentarse" in str(exc_info.value)


def test_retry_processing_enforces_max_retries() -> None:
    ws_id = uuid4()
    user_id = uuid4()
    repo = InMemoryDocumentRepository()
    use_case = RetryDocumentProcessingUseCase(document_repo=repo)

    # Documento que ya alcanzó el límite máximo de reintentos (3)
    exhausted_doc = _make_failed_doc(ws_id, user_id, retry_count=MAX_DOCUMENT_RETRIES)
    repo.save(exhausted_doc)

    admin_tenant = _make_tenant(ws_id, user_id, WorkspaceRole.ADMIN)
    with pytest.raises(MaxRetriesExceededError) as exc_info:
        use_case.execute(tenant=admin_tenant, document_id=exhausted_doc.id)
    assert "límite máximo" in str(exc_info.value)


# --- Pruebas del Endpoint HTTP ---


@pytest.fixture
def api_test_setup() -> tuple[TestClient, InMemoryDocumentRepository, UUID, UUID]:
    ws_id = uuid4()
    user_id = uuid4()
    repo = InMemoryDocumentRepository()
    use_case = RetryDocumentProcessingUseCase(document_repo=repo)

    app = create_app()

    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=user_id,
        cognito_sub="sub-admin-123",
        email="admin@test.com",
    )
    app.dependency_overrides[get_tenant_context] = lambda: _make_tenant(
        ws_id, user_id, WorkspaceRole.ADMIN
    )
    app.dependency_overrides[get_retry_document_processing_use_case] = lambda: use_case
    app.dependency_overrides[get_db_session] = lambda: None

    client = TestClient(app)
    return client, repo, ws_id, user_id


def test_http_retry_document_endpoint_success(
    api_test_setup: tuple[TestClient, InMemoryDocumentRepository, UUID, UUID],
) -> None:
    client, repo, ws_id, user_id = api_test_setup
    doc = _make_failed_doc(ws_id, user_id)
    repo.save(doc)

    response = client.post(f"/api/v1/workspaces/{ws_id}/documents/{doc.id}/retry")
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["data"]["id"] == str(doc.id)
    assert body["data"]["status"] == "PROCESSING"
    assert body["data"]["retry_count"] == 1
    assert body["data"]["failure_reason"] is None


def test_http_retry_document_endpoint_conflict_when_max_retries_exceeded(
    api_test_setup: tuple[TestClient, InMemoryDocumentRepository, UUID, UUID],
) -> None:
    client, repo, ws_id, user_id = api_test_setup
    doc = _make_failed_doc(ws_id, user_id, retry_count=3)
    repo.save(doc)

    response = client.post(f"/api/v1/workspaces/{ws_id}/documents/{doc.id}/retry")
    assert response.status_code == status.HTTP_409_CONFLICT
    body = response.json()
    assert body["error"]["code"] == "max_retries_exceeded"


def test_http_retry_document_endpoint_forbidden_for_member(
    api_test_setup: tuple[TestClient, InMemoryDocumentRepository, UUID, UUID],
) -> None:
    client, repo, ws_id, user_id = api_test_setup
    doc = _make_failed_doc(ws_id, user_id)
    repo.save(doc)

    # Forzar rol MEMBER en el tenant context
    client.app.dependency_overrides[get_tenant_context] = lambda: _make_tenant(  # type: ignore[attr-defined]
        ws_id, user_id, WorkspaceRole.MEMBER
    )

    response = client.post(f"/api/v1/workspaces/{ws_id}/documents/{doc.id}/retry")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    body = response.json()
    assert body["error"]["code"] == "permission_denied"


def test_http_retry_document_endpoint_not_found(
    api_test_setup: tuple[TestClient, InMemoryDocumentRepository, UUID, UUID],
) -> None:
    client, _, ws_id, _ = api_test_setup
    non_existent_id = uuid4()

    response = client.post(f"/api/v1/workspaces/{ws_id}/documents/{non_existent_id}/retry")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    body = response.json()
    assert body["error"]["code"] == "document_not_found"
