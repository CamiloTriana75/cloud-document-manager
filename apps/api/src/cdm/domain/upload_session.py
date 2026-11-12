"""Dominio: Sesiones de carga prefirmada (CDM-29 / AGENTS.md §10, §12).

Entidad pura sin acoplamiento a frameworks.
Modela la intención temporal de carga antes de que el archivo sea transferido a S3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4

from cdm.domain.errors import ConflictError


class UploadSessionStatus(str, Enum):
    """Estados del ciclo de vida de una sesión de carga."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class UploadSession:
    """Entidad pura de dominio que representa una sesión de carga prefirmada."""

    id: UUID
    workspace_id: UUID
    user_id: UUID
    document_id: UUID
    storage_key: str
    expected_size_bytes: int
    expected_content_type: str
    expires_at: datetime
    expected_checksum_sha256: str | None = None
    status: UploadSessionStatus = UploadSessionStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        workspace_id: UUID,
        user_id: UUID,
        document_id: UUID,
        storage_key: str,
        expected_size_bytes: int,
        expected_content_type: str,
        expires_in_seconds: int = 900,
        expected_checksum_sha256: str | None = None,
        session_id: UUID | None = None,
    ) -> UploadSession:
        """Fábrica para instanciar una nueva sesión de carga validada."""
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=expires_in_seconds)

        return cls(
            id=session_id or uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            document_id=document_id,
            storage_key=storage_key,
            expected_size_bytes=expected_size_bytes,
            expected_content_type=expected_content_type,
            expected_checksum_sha256=expected_checksum_sha256,
            status=UploadSessionStatus.PENDING,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        """Determina si la sesión ha caducado temporalmente."""
        current_time = now or datetime.now(UTC)
        return current_time >= self.expires_at

    def mark_completed(self, completed_at: datetime | None = None) -> UploadSession:
        """Transiciona la sesión a COMPLETED una vez confirmada la presencia en S3."""
        if self.status != UploadSessionStatus.PENDING:
            raise ConflictError(
                f"No se puede completar una sesión de carga en estado '{self.status.value}'."
            )
        now = completed_at or datetime.now(UTC)
        return UploadSession(
            id=self.id,
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            document_id=self.document_id,
            storage_key=self.storage_key,
            expected_size_bytes=self.expected_size_bytes,
            expected_content_type=self.expected_content_type,
            expected_checksum_sha256=self.expected_checksum_sha256,
            status=UploadSessionStatus.COMPLETED,
            expires_at=self.expires_at,
            created_at=self.created_at,
            updated_at=now,
        )

    def mark_expired(self, expired_at: datetime | None = None) -> UploadSession:
        """Transiciona la sesión a EXPIRED tras agotarse su vigencia."""
        now = expired_at or datetime.now(UTC)
        return UploadSession(
            id=self.id,
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            document_id=self.document_id,
            storage_key=self.storage_key,
            expected_size_bytes=self.expected_size_bytes,
            expected_content_type=self.expected_content_type,
            expected_checksum_sha256=self.expected_checksum_sha256,
            status=UploadSessionStatus.EXPIRED,
            expires_at=self.expires_at,
            created_at=self.created_at,
            updated_at=now,
        )

    def mark_cancelled(self, cancelled_at: datetime | None = None) -> UploadSession:
        """Cancela la sesión de carga explícitamente."""
        if self.status != UploadSessionStatus.PENDING:
            raise ConflictError(
                f"No se puede cancelar una sesión de carga en estado '{self.status.value}'."
            )
        now = cancelled_at or datetime.now(UTC)
        return UploadSession(
            id=self.id,
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            document_id=self.document_id,
            storage_key=self.storage_key,
            expected_size_bytes=self.expected_size_bytes,
            expected_content_type=self.expected_content_type,
            expected_checksum_sha256=self.expected_checksum_sha256,
            status=UploadSessionStatus.CANCELLED,
            expires_at=self.expires_at,
            created_at=self.created_at,
            updated_at=now,
        )
