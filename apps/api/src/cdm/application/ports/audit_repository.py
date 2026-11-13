"""Puerto: Repositorio de eventos de auditoría (CDM-40 / AGENTS.md §8.1).

Contrato abstracto de aplicación sin dependencias de frameworks ni SQLAlchemy.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from cdm.domain.audit import AuditEvent


class AuditRepositoryPort(Protocol):
    """Contrato abstracto de persistencia para eventos de auditoría."""

    def save(self, event: AuditEvent) -> AuditEvent:
        """Persiste un nuevo evento de auditoría."""
        ...

    def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Lista los eventos de auditoría pertenecientes al workspace."""
        ...

    def count_by_workspace(self, workspace_id: UUID) -> int:
        """Retorna el total de eventos de auditoría registrados para el workspace."""
        ...
