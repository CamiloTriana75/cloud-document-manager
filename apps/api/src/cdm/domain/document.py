"""Dominio: Documentos y estado del ciclo de vida (CDM-27 / AGENTS.md §10).

Puro: sin dependencias de frameworks ni librerías de infraestructura.
Toda entidad Document está explícita y forzosamente asociada a un workspace_id (tenant).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from cdm.domain.errors import InvalidDocumentDataError, MaxRetriesExceededError

#: Número máximo de reintentos manuales permitidos por documento (CDM-39 / AGENTS.md §12).
MAX_DOCUMENT_RETRIES: int = 3


class DocumentStatus(str, Enum):
    """Estados del ciclo de vida documental según AGENTS.md §10."""

    PENDING_UPLOAD = "PENDING_UPLOAD"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    DELETED = "DELETED"


#: Transiciones retrógradas prohibidas para prevenir inconsistencia por reintentos (AGENTS.md §10).
_FORBIDDEN_BACKWARD_TRANSITIONS: dict[DocumentStatus, set[DocumentStatus]] = {
    DocumentStatus.READY: {
        DocumentStatus.PENDING_UPLOAD,
        DocumentStatus.UPLOADED,
        DocumentStatus.PROCESSING,
    },
    DocumentStatus.PROCESSING: {
        DocumentStatus.PENDING_UPLOAD,
        DocumentStatus.UPLOADED,
    },
    DocumentStatus.UPLOADED: {
        DocumentStatus.PENDING_UPLOAD,
    },
    DocumentStatus.FAILED: {
        DocumentStatus.PENDING_UPLOAD,
    },
    DocumentStatus.DELETED: {
        DocumentStatus.PENDING_UPLOAD,
        DocumentStatus.UPLOADED,
        DocumentStatus.PROCESSING,
        DocumentStatus.READY,
        DocumentStatus.FAILED,
    },
}


@dataclass(frozen=True)
class Document:
    """Entidad pura de dominio para un documento en el sistema."""

    id: UUID
    workspace_id: UUID
    uploaded_by: UUID
    original_filename: str
    storage_key: str
    content_type: str
    size_bytes: int
    checksum_sha256: str | None = None
    status: DocumentStatus = DocumentStatus.PENDING_UPLOAD
    technical_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    deleted_at: datetime | None = None

    @classmethod
    def create(
        cls,
        workspace_id: UUID,
        uploaded_by: UUID,
        original_filename: str,
        storage_key: str,
        content_type: str,
        size_bytes: int,
        checksum_sha256: str | None = None,
        technical_metadata: dict[str, Any] | None = None,
        document_id: UUID | None = None,
    ) -> Document:
        """Fábrica de documento validando invariantes."""
        clean_filename = original_filename.strip()
        if not clean_filename:
            raise InvalidDocumentDataError("El nombre original del archivo no puede estar vacío.")

        clean_key = storage_key.strip()
        if not clean_key:
            raise InvalidDocumentDataError("El storage_key no puede estar vacío.")

        clean_content_type = content_type.strip().lower()
        if not clean_content_type:
            raise InvalidDocumentDataError("El tipo de contenido (MIME) no puede estar vacío.")

        if size_bytes < 0:
            raise InvalidDocumentDataError("El tamaño del archivo no puede ser negativo.")

        now = datetime.now(UTC)
        return cls(
            id=document_id or uuid4(),
            workspace_id=workspace_id,
            uploaded_by=uploaded_by,
            original_filename=clean_filename,
            storage_key=clean_key,
            content_type=clean_content_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256.strip() if checksum_sha256 else None,
            status=DocumentStatus.PENDING_UPLOAD,
            technical_metadata=technical_metadata or {},
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )

    @property
    def is_deleted(self) -> bool:
        """Determina si el documento ha sido eliminado lógicamente."""
        return self.deleted_at is not None or self.status == DocumentStatus.DELETED

    @property
    def failure_reason(self) -> str | None:
        """Razón segura de fallo si el documento se encuentra en estado FAILED."""
        if self.status != DocumentStatus.FAILED:
            return None
        reason = self.technical_metadata.get("failure_reason")
        return str(reason) if reason else "Error durante el procesamiento del documento."

    @property
    def retry_count(self) -> int:
        """Número de reintentos ejecutados sobre este documento (CDM-39)."""
        return int(self.technical_metadata.get("retry_count", 0))

    def mark_failed(self, reason: str, failed_at: datetime | None = None) -> Document:
        """Marca el documento como FAILED con razón de error segura (sin stack traces)."""
        if self.is_deleted:
            raise InvalidDocumentDataError(
                "No se puede marcar como fallido un documento eliminado."
            )

        now = failed_at or datetime.now(UTC)
        # Sanitizar para evitar volcado accidental de stack traces
        first_line = reason.strip().split("\n")[0][:255] if reason else ""
        clean_reason = first_line or "Error durante el procesamiento."

        tech_meta = dict(self.technical_metadata)
        tech_meta["failure_reason"] = clean_reason
        tech_meta["failed_at"] = now.isoformat()

        return Document(
            id=self.id,
            workspace_id=self.workspace_id,
            uploaded_by=self.uploaded_by,
            original_filename=self.original_filename,
            storage_key=self.storage_key,
            content_type=self.content_type,
            size_bytes=self.size_bytes,
            checksum_sha256=self.checksum_sha256,
            status=DocumentStatus.FAILED,
            technical_metadata=tech_meta,
            created_at=self.created_at,
            updated_at=now,
            deleted_at=self.deleted_at,
        )

    def retry_processing(
        self,
        retried_at: datetime | None = None,
        max_retries: int = MAX_DOCUMENT_RETRIES,
    ) -> Document:
        """Transiciona un documento FAILED a PROCESSING para reintento controlado (CDM-39)."""
        if self.status != DocumentStatus.FAILED:
            raise InvalidDocumentDataError(
                f"Solo documentos en FAILED pueden reintentarse (actual: {self.status.value})."
            )
        tech_meta = dict(self.technical_metadata)
        current_retries = int(tech_meta.get("retry_count", 0))
        if current_retries >= max_retries:
            raise MaxRetriesExceededError(
                f"Se ha superado el límite máximo de {max_retries} reintentos permitidos."
            )

        now = retried_at or datetime.now(UTC)
        tech_meta["retry_count"] = current_retries + 1
        tech_meta["last_retry_at"] = now.isoformat()
        tech_meta.pop("failure_reason", None)

        return Document(
            id=self.id,
            workspace_id=self.workspace_id,
            uploaded_by=self.uploaded_by,
            original_filename=self.original_filename,
            storage_key=self.storage_key,
            content_type=self.content_type,
            size_bytes=self.size_bytes,
            checksum_sha256=self.checksum_sha256,
            status=DocumentStatus.PROCESSING,
            technical_metadata=tech_meta,
            created_at=self.created_at,
            updated_at=now,
            deleted_at=self.deleted_at,
        )

    def mark_deleted(self, deleted_at: datetime | None = None) -> Document:
        """Genera una copia del documento marcada como eliminada lógicamente."""
        now = deleted_at or datetime.now(UTC)
        return Document(
            id=self.id,
            workspace_id=self.workspace_id,
            uploaded_by=self.uploaded_by,
            original_filename=self.original_filename,
            storage_key=self.storage_key,
            content_type=self.content_type,
            size_bytes=self.size_bytes,
            checksum_sha256=self.checksum_sha256,
            status=DocumentStatus.DELETED,
            technical_metadata=self.technical_metadata,
            created_at=self.created_at,
            updated_at=now,
            deleted_at=now,
        )

    def transition_to(self, new_status: DocumentStatus) -> Document:
        """Realiza una transición de estado validada según el ciclo de vida (AGENTS.md §10)."""
        if self.is_deleted:
            raise InvalidDocumentDataError("No se puede transicionar un documento eliminado.")

        if new_status == self.status:
            # Idempotente: misma transición no genera error
            return self

        forbidden = _FORBIDDEN_BACKWARD_TRANSITIONS.get(self.status, set())
        if new_status in forbidden:
            raise InvalidDocumentDataError(
                f"Transición no válida: de '{self.status.value}' a '{new_status.value}'."
            )

        now = datetime.now(UTC)
        return Document(
            id=self.id,
            workspace_id=self.workspace_id,
            uploaded_by=self.uploaded_by,
            original_filename=self.original_filename,
            storage_key=self.storage_key,
            content_type=self.content_type,
            size_bytes=self.size_bytes,
            checksum_sha256=self.checksum_sha256,
            status=new_status,
            technical_metadata=self.technical_metadata,
            created_at=self.created_at,
            updated_at=now,
            deleted_at=self.deleted_at,
        )
