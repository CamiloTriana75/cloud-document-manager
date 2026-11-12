"""Puerto para persistencia de sesiones de carga (CDM-29 / AGENTS.md §8.1).

Contrato desacoplado de SQLAlchemy y de bases de datos relacionales.
Toda consulta exige el contexto explícito del workspace_id (tenant).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from cdm.domain.upload_session import UploadSession


class UploadSessionRepositoryPort(Protocol):
    """Contrato del repositorio para sesiones de carga prefirmada."""

    def save(self, session: UploadSession) -> UploadSession:
        """Persiste una sesión de carga (creación o actualización)."""
        ...

    def get_by_id(self, session_id: UUID, workspace_id: UUID) -> UploadSession | None:
        """Obtiene una sesión por su ID dentro del tenant indicado."""
        ...

    def get_by_document_id(self, document_id: UUID, workspace_id: UUID) -> UploadSession | None:
        """Obtiene la sesión asociada a un documento dentro del tenant indicado."""
        ...

    def list_expired(self, workspace_id: UUID | None = None) -> list[UploadSession]:
        """Lista sesiones expiradas para limpieza de objetos huérfanos (CDM-34)."""
        ...
