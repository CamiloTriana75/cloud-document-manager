"""Casos de uso para sesiones de carga prefirmada (CDM-29 / AGENTS.md §8, §12).

Orquesta la validación de políticas de archivos (CDM-30), permisos de rol,
generación de URL prefirmada PUT para S3 y persistencia segura de metadatos provisionales.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from cdm.application.ports.document_repository import DocumentRepositoryPort
from cdm.application.ports.storage import StoragePort
from cdm.application.ports.upload_session_repository import UploadSessionRepositoryPort
from cdm.domain.document import Document, DocumentStatus
from cdm.domain.errors import (
    ConflictError,
    PermissionDeniedError,
    UploadSessionNotFoundError,
)
from cdm.domain.file_policy import (
    generate_storage_key,
    validate_and_sanitize_filename,
    validate_checksum,
    validate_file_size,
    validate_file_type,
)
from cdm.domain.tenant import TenantContext
from cdm.domain.upload_session import UploadSession, UploadSessionStatus
from cdm.domain.workspace import WorkspaceRole

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadSessionResult:
    """Resultado devuelto al cliente para iniciar la subida directa a S3."""

    upload_session_id: UUID
    document_id: UUID
    upload_url: str
    storage_key: str
    expires_in_seconds: int
    required_headers: dict[str, str]


class CreateUploadSessionUseCase:
    """Caso de uso: Solicitar una sesión de carga y obtener una URL prefirmada (CDM-29)."""

    def __init__(
        self,
        document_repo: DocumentRepositoryPort,
        upload_session_repo: UploadSessionRepositoryPort,
        storage: StoragePort,
        max_upload_size_bytes: int = 52428800,
        expires_in_seconds: int = 900,
    ) -> None:
        self._document_repo = document_repo
        self._upload_session_repo = upload_session_repo
        self._storage = storage
        self._max_upload_size_bytes = max_upload_size_bytes
        self._expires_in_seconds = expires_in_seconds

    def execute(
        self,
        tenant: TenantContext,
        original_filename: str,
        content_type: str,
        size_bytes: int,
        checksum_sha256: str | None = None,
    ) -> UploadSessionResult:
        """Ejecuta la creación de una sesión de carga prefirmada."""
        # 1. Autorización: Solo OWNER, ADMIN, EDITOR y MEMBER pueden subir archivos
        if tenant.role == WorkspaceRole.VIEWER:
            raise PermissionDeniedError(
                "El rol VIEWER no tiene permisos para solicitar sesiones de carga de documentos."
            )

        # 2. Validación y saneamiento del nombre de archivo (anti-path traversal)
        clean_filename = validate_and_sanitize_filename(original_filename)

        # 3. Validación de allowlist de tipo MIME y correspondencia con extensión
        clean_content_type, extension = validate_file_type(clean_filename, content_type)

        # 4. Validación de límites de tamaño
        verified_size = validate_file_size(size_bytes, self._max_upload_size_bytes)

        # 5. Validación de formato de checksum si fue provisto
        verified_checksum = validate_checksum(checksum_sha256)

        # 6. Generación de IDs y clave S3 opaca bajo prefijo de tenant
        document_id = uuid4()
        storage_key = generate_storage_key(tenant.workspace_id, document_id, extension)

        # 7. Generación de URL prefirmada para PUT directo en S3
        upload_url = self._storage.generate_upload_url(
            storage_key=storage_key,
            content_type=clean_content_type,
            size_bytes=verified_size,
            expires_in_seconds=self._expires_in_seconds,
        )

        # 8. Persistencia de registro de documento en PENDING_UPLOAD
        document = Document.create(
            workspace_id=tenant.workspace_id,
            uploaded_by=tenant.user_id,
            original_filename=clean_filename,
            storage_key=storage_key,
            content_type=clean_content_type,
            size_bytes=verified_size,
            checksum_sha256=verified_checksum,
            document_id=document_id,
        )
        self._document_repo.save(document)

        # 9. Persistencia de sesión de carga en PENDING
        upload_session = UploadSession.create(
            workspace_id=tenant.workspace_id,
            user_id=tenant.user_id,
            document_id=document_id,
            storage_key=storage_key,
            expected_size_bytes=verified_size,
            expected_content_type=clean_content_type,
            expires_in_seconds=self._expires_in_seconds,
            expected_checksum_sha256=verified_checksum,
        )
        saved_session = self._upload_session_repo.save(upload_session)

        # 10. Retorno sin credenciales AWS
        return UploadSessionResult(
            upload_session_id=saved_session.id,
            document_id=document_id,
            upload_url=upload_url,
            storage_key=storage_key,
            expires_in_seconds=self._expires_in_seconds,
            required_headers={"Content-Type": clean_content_type},
        )


class CancelUploadSessionUseCase:
    """Caso de uso: Cancelar una sesión de carga prefirmada (CDM-34)."""

    def __init__(
        self,
        upload_session_repo: UploadSessionRepositoryPort,
        document_repo: DocumentRepositoryPort,
        storage: StoragePort,
    ) -> None:
        self._upload_session_repo = upload_session_repo
        self._document_repo = document_repo
        self._storage = storage

    def execute(self, tenant: TenantContext, upload_session_id: UUID) -> None:
        # Requiere rol MEMBER o superior
        tenant.require_role(WorkspaceRole.MEMBER)

        session = self._upload_session_repo.get_by_id(
            session_id=upload_session_id,
            workspace_id=tenant.workspace_id,
        )
        if session is None:
            raise UploadSessionNotFoundError(
                "La sesión de carga solicitada no existe o no tiene acceso a ella."
            )

        if session.status == UploadSessionStatus.COMPLETED:
            raise ConflictError(
                "No se puede cancelar una sesión de carga que ya ha sido completada."
            )

        if session.status == UploadSessionStatus.CANCELLED:
            return  # Idempotente

        # 1. Marcar sesión cancelada
        cancelled_session = session.mark_cancelled()
        self._upload_session_repo.save(cancelled_session)

        # 2. Transicionar documento provisional si está en PENDING_UPLOAD
        doc = self._document_repo.get_by_id(
            workspace_id=tenant.workspace_id,
            document_id=session.document_id,
            include_deleted=True,
        )
        if doc and doc.status == DocumentStatus.PENDING_UPLOAD:
            updated_doc = doc.transition_to(DocumentStatus.FAILED)
            self._document_repo.save(updated_doc)

        # 3. Limpiar cualquier binario huérfano en S3 si existiera
        self._storage.delete_object(session.storage_key)

        logger.info(
            "Cancelled upload session id=%s for tenant=%s user=%s",
            session.id,
            tenant.workspace_id,
            tenant.user_id,
        )


@dataclass(frozen=True)
class CleanupReportDTO:
    """Informe del proceso de limpieza de sesiones expiradas y objetos huérfanos."""

    expired_sessions_count: int
    cleaned_objects_count: int
    skipped_confirmed_documents_count: int


class CleanupExpiredUploadSessionsUseCase:
    """Caso de uso: Expirar sesiones vencidas y limpiar objetos huérfanos sin confirmar (CDM-34).

    Criterios garantizados:
    1. Upload sessions vencidas se marcan EXPIRED.
    2. Objetos temporales sin confirmación se eliminan del almacenamiento.
    3. La limpieza NUNCA borra documentos CONFIRMED (UPLOADED, PROCESSING, READY).
    """

    def __init__(
        self,
        upload_session_repo: UploadSessionRepositoryPort,
        document_repo: DocumentRepositoryPort,
        storage: StoragePort,
    ) -> None:
        self._upload_session_repo = upload_session_repo
        self._document_repo = document_repo
        self._storage = storage

    def execute(self, workspace_id: UUID | None = None) -> CleanupReportDTO:
        expired_sessions = self._upload_session_repo.list_expired(workspace_id=workspace_id)

        expired_count = 0
        cleaned_objects_count = 0
        skipped_confirmed_count = 0

        for session in expired_sessions:
            doc = self._document_repo.get_by_id(
                workspace_id=session.workspace_id,
                document_id=session.document_id,
                include_deleted=True,
            )

            # Criterio 3: NUNCA borrar documentos confirmados/válidos
            if doc is not None and doc.status in (
                DocumentStatus.UPLOADED,
                DocumentStatus.PROCESSING,
                DocumentStatus.READY,
            ):
                # Si el documento ya fue confirmado o procesado válidamente,
                # marcamos la sesión como completada y nunca tocamos el binario ni el documento.
                if session.status == UploadSessionStatus.PENDING:
                    session_completed = session.mark_completed()
                    self._upload_session_repo.save(session_completed)
                skipped_confirmed_count += 1
                continue

            # 1. Marcar sesión como EXPIRED
            expired_session = session.mark_expired()
            self._upload_session_repo.save(expired_session)
            expired_count += 1

            # 2. Si el documento sigue en PENDING_UPLOAD, marcarlo como FAILED
            if doc is not None and doc.status == DocumentStatus.PENDING_UPLOAD:
                failed_doc = doc.transition_to(DocumentStatus.FAILED)
                self._document_repo.save(failed_doc)

            # 3. Eliminar objeto temporal huérfano de S3 si existiera
            deleted = self._storage.delete_object(session.storage_key)
            if deleted:
                cleaned_objects_count += 1

            logger.info(
                "Cleaned expired upload session id=%s doc_id=%s tenant=%s",
                session.id,
                session.document_id,
                session.workspace_id,
            )

        return CleanupReportDTO(
            expired_sessions_count=expired_count,
            cleaned_objects_count=cleaned_objects_count,
            skipped_confirmed_documents_count=skipped_confirmed_count,
        )
