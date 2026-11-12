"""Casos de uso para Documentos con Aislamiento Multi-Tenant Estricto (CDM-27).

Orquestan operaciones sobre documentos validando el TenantContext verificado.
Toda consulta o mutación delega al repositorio exigiendo forzosamente el workspace_id.
Las reglas de acceso y roles (ADR-0001) se validan estrictamente en esta capa.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from cdm.application.ports.document_repository import DocumentRepositoryPort
from cdm.application.ports.storage import StoragePort
from cdm.application.ports.upload_session_repository import UploadSessionRepositoryPort
from cdm.domain.document import Document, DocumentStatus
from cdm.domain.errors import (
    ConflictError,
    DocumentNotFoundError,
    InvalidDocumentDataError,
    UploadSessionExpiredError,
)
from cdm.domain.file_policy import validate_and_sanitize_filename
from cdm.domain.tenant import TenantContext
from cdm.domain.upload_session import UploadSessionStatus
from cdm.domain.workspace import WorkspaceRole

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentDetailDTO:
    """DTO representativo del detalle de un documento."""

    id: UUID
    workspace_id: UUID
    uploaded_by: UUID
    original_filename: str
    storage_key: str
    content_type: str
    size_bytes: int
    checksum_sha256: str | None
    status: DocumentStatus
    technical_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DocumentDownloadDTO:
    """DTO representativo de una URL de descarga autorizada."""

    document_id: UUID
    original_filename: str
    download_url: str
    expires_in_seconds: int


@dataclass(frozen=True)
class DocumentListDTO:
    """DTO paginado de documentos pertenecientes a un workspace."""

    items: list[DocumentDetailDTO]
    total: int
    limit: int
    offset: int


def _to_dto(doc: Document) -> DocumentDetailDTO:
    return DocumentDetailDTO(
        id=doc.id,
        workspace_id=doc.workspace_id,
        uploaded_by=doc.uploaded_by,
        original_filename=doc.original_filename,
        storage_key=doc.storage_key,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        checksum_sha256=doc.checksum_sha256,
        status=doc.status,
        technical_metadata=doc.technical_metadata,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


class ListDocumentsUseCase:
    """Caso de uso: Listar el catálogo de documentos del tenant activo."""

    def __init__(self, document_repo: DocumentRepositoryPort) -> None:
        self._doc_repo = document_repo

    def execute(
        self,
        tenant: TenantContext,
        limit: int = 50,
        offset: int = 0,
    ) -> DocumentListDTO:
        # Cualquier miembro del workspace (incluso VIEWER) puede listar el catálogo
        tenant.require_role(WorkspaceRole.VIEWER)

        documents = self._doc_repo.list_by_workspace(
            workspace_id=tenant.workspace_id,
            limit=limit,
            offset=offset,
            include_deleted=False,
        )
        total = self._doc_repo.count_by_workspace(
            workspace_id=tenant.workspace_id,
            include_deleted=False,
        )

        return DocumentListDTO(
            items=[_to_dto(d) for d in documents],
            total=total,
            limit=limit,
            offset=offset,
        )


class GetDocumentDetailUseCase:
    """Caso de uso: Obtener el detalle de un documento del tenant activo."""

    def __init__(self, document_repo: DocumentRepositoryPort) -> None:
        self._doc_repo = document_repo

    def execute(self, tenant: TenantContext, document_id: UUID) -> DocumentDetailDTO:
        tenant.require_role(WorkspaceRole.VIEWER)

        # La consulta filtra obligatoriamente por workspace_id y document_id
        document = self._doc_repo.get_by_id(
            workspace_id=tenant.workspace_id,
            document_id=document_id,
            include_deleted=False,
        )
        if document is None:
            # Nunca revelar si el documento existe en otro workspace (prevención de IDOR)
            raise DocumentNotFoundError("El documento solicitado no existe o no tiene acceso a él.")

        return _to_dto(document)


class AuthorizeDocumentDownloadUseCase:
    """Caso de uso: Autorizar la descarga y generar URL prefirmada temporal."""

    def __init__(
        self,
        document_repo: DocumentRepositoryPort,
        storage_service: StoragePort,
    ) -> None:
        self._doc_repo = document_repo
        self._storage = storage_service

    def execute(
        self,
        tenant: TenantContext,
        document_id: UUID,
        expires_in_seconds: int = 900,
    ) -> DocumentDownloadDTO:
        # Cualquier rol con membresía activa puede descargar documentos
        tenant.require_role(WorkspaceRole.VIEWER)

        document = self._doc_repo.get_by_id(
            workspace_id=tenant.workspace_id,
            document_id=document_id,
            include_deleted=False,
        )
        if document is None:
            raise DocumentNotFoundError("El documento solicitado no existe o no tiene acceso a él.")

        if document.status == DocumentStatus.PENDING_UPLOAD:
            raise InvalidDocumentDataError("El documento aún no ha completado el proceso de carga.")

        if document.status == DocumentStatus.FAILED:
            raise InvalidDocumentDataError(
                "El documento se encuentra en estado fallido y no está disponible para descarga."
            )

        safe_filename = validate_and_sanitize_filename(document.original_filename)

        download_url = self._storage.generate_download_url(
            storage_key=document.storage_key,
            expires_in_seconds=expires_in_seconds,
            filename=safe_filename,
        )

        logger.info(
            "Authorized document download for tenant=%s user=%s document=%s expires_in_seconds=%s",
            tenant.workspace_id,
            tenant.user_id,
            document.id,
            expires_in_seconds,
        )

        return DocumentDownloadDTO(
            document_id=document.id,
            original_filename=document.original_filename,
            download_url=download_url,
            expires_in_seconds=expires_in_seconds,
        )


class DeleteDocumentUseCase:
    """Caso de uso: Eliminación lógica de un documento del workspace (ADR-0001)."""

    def __init__(self, document_repo: DocumentRepositoryPort) -> None:
        self._doc_repo = document_repo

    def execute(self, tenant: TenantContext, document_id: UUID) -> None:
        # ADR-0001: Solo EDITOR, ADMIN o OWNER pueden eliminar documentos
        # MEMBER y VIEWER son rechazados con PermissionDeniedError (403)
        tenant.require_role(WorkspaceRole.EDITOR)

        document = self._doc_repo.get_by_id(
            workspace_id=tenant.workspace_id,
            document_id=document_id,
            include_deleted=False,
        )
        if document is None:
            raise DocumentNotFoundError("El documento solicitado no existe o no tiene acceso a él.")

        deleted = self._doc_repo.soft_delete(
            workspace_id=tenant.workspace_id,
            document_id=document_id,
        )
        if not deleted:
            raise DocumentNotFoundError("El documento solicitado no existe o no tiene acceso a él.")


class CreateDocumentRecordUseCase:
    """Caso de uso: Registrar metadatos de un nuevo documento dentro del tenant."""

    def __init__(self, document_repo: DocumentRepositoryPort) -> None:
        self._doc_repo = document_repo

    def execute(
        self,
        tenant: TenantContext,
        original_filename: str,
        storage_key: str,
        content_type: str,
        size_bytes: int,
        checksum_sha256: str | None = None,
        technical_metadata: dict[str, Any] | None = None,
    ) -> DocumentDetailDTO:
        # ADR-0001: Subir/crear documentos requiere MEMBER o superior (VIEWER no puede)
        tenant.require_role(WorkspaceRole.MEMBER)

        document = Document.create(
            workspace_id=tenant.workspace_id,
            uploaded_by=tenant.user_id,
            original_filename=original_filename,
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            technical_metadata=technical_metadata,
        )
        saved = self._doc_repo.save(document)
        return _to_dto(saved)


class CompleteDocumentUploadUseCase:
    """Caso de uso: Confirmar carga y reconciliar objeto S3 con metadatos (CDM-32).

    1. Verifica que el usuario pertenezca al workspace y tenga rol MEMBER o superior.
    2. Obtiene el documento asegurando filtrado estricto por workspace_id (anti-IDOR).
    3. Idempotencia: si el documento ya está en UPLOADED o estado posterior, lo retorna sin error.
    4. Valida que el documento esté en PENDING_UPLOAD.
    5. Obtiene la sesión de carga asociada en upload_sessions y valida su vigencia.
    6. Reconcilia con S3 mediante HeadObject: existencia del objeto y tamaño coincidente.
    7. Transiciona Document a UPLOADED y UploadSession a COMPLETED de forma atómica.
    """

    def __init__(
        self,
        document_repo: DocumentRepositoryPort,
        upload_session_repo: UploadSessionRepositoryPort,
        storage: StoragePort,
    ) -> None:
        self._doc_repo = document_repo
        self._upload_session_repo = upload_session_repo
        self._storage = storage

    def execute(
        self,
        tenant: TenantContext,
        document_id: UUID,
    ) -> DocumentDetailDTO:
        # 1. Autorización: rol MEMBER o superior
        tenant.require_role(WorkspaceRole.MEMBER)

        # 2. Obtención segura filtrada por tenant
        document = self._doc_repo.get_by_id(
            workspace_id=tenant.workspace_id,
            document_id=document_id,
        )
        if document is None or document.is_deleted:
            raise DocumentNotFoundError("El documento solicitado no existe o no tiene acceso a él.")

        # 3. Idempotencia: si ya está UPLOADED, READY o PROCESSING, devolver sin mutar
        if document.status in (
            DocumentStatus.UPLOADED,
            DocumentStatus.PROCESSING,
            DocumentStatus.READY,
        ):
            return _to_dto(document)

        # 4. Estado debe ser PENDING_UPLOAD
        if document.status != DocumentStatus.PENDING_UPLOAD:
            raise ConflictError(
                f"El documento está en estado '{document.status.value}' y no puede completarse."
            )

        # 5. Sesión de carga asociada
        session = self._upload_session_repo.get_by_document_id(
            document_id=document_id,
            workspace_id=tenant.workspace_id,
        )
        if session is None:
            raise ConflictError("No existe una sesión de carga asociada a este documento.")

        if session.status == UploadSessionStatus.COMPLETED:
            return _to_dto(document)

        if session.is_expired():
            expired_session = session.mark_expired()
            self._upload_session_repo.save(expired_session)
            raise UploadSessionExpiredError(
                "La sesión de carga ha expirado y no puede completarse."
            )

        if session.status != UploadSessionStatus.PENDING:
            raise ConflictError(
                f"La sesión de carga se encuentra en estado '{session.status.value}'."
            )

        # 6. Reconciliación con S3 (HeadObject)
        obj_meta = self._storage.get_object_metadata(document.storage_key)
        if obj_meta is None:
            raise ConflictError(
                "El archivo no se encuentra en el almacenamiento en la clave esperada."
            )

        # 7. Verificación de tamaño
        if obj_meta.size_bytes != document.size_bytes:
            raise ConflictError(
                f"El tamaño del archivo en almacenamiento ({obj_meta.size_bytes} bytes) "
                f"no coincide con el tamaño esperado ({document.size_bytes} bytes)."
            )

        # 8. Transición atómica de estados
        updated_doc = document.transition_to(DocumentStatus.UPLOADED)
        saved_doc = self._doc_repo.save(updated_doc)

        completed_session = session.mark_completed()
        self._upload_session_repo.save(completed_session)

        return _to_dto(saved_doc)
