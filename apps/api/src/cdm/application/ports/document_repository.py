"""Puertos de persistencia para Documentos con aislamiento multi-tenant (CDM-27).

Contrato puro de la capa de aplicación. Todo método de búsqueda o mutación exige
el workspace_id (tenant_id) de forma explícita y obligatoria.
Los repositorios no exponen métodos de consulta globales accidentales (AGENTS.md §14).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from cdm.domain.document import Document, DocumentQueryFilter, DocumentStatus


class DocumentRepositoryPort(Protocol):
    """Contrato de persistencia para documentos restringido por tenant."""

    def save(self, document: Document) -> Document:
        """Persiste o actualiza un documento garantizando que conserve su workspace_id."""
        ...

    def get_by_id(
        self,
        workspace_id: UUID,
        document_id: UUID,
        include_deleted: bool = False,
    ) -> Document | None:
        """Busca un documento exigiendo estrictamente su workspace_id correspondiente.

        Nunca busca únicamente por document_id, impidiendo cualquier acceso cross-tenant.
        """
        ...

    def list_by_workspace(
        self,
        workspace_id: UUID,
        filters: DocumentQueryFilter | None = None,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
        status: DocumentStatus | None = None,
    ) -> list[Document]:
        """Lista documentos de un workspace con paginación y filtros opcionales."""
        ...

    def count_by_workspace(
        self,
        workspace_id: UUID,
        filters: DocumentQueryFilter | None = None,
        include_deleted: bool = False,
        status: DocumentStatus | None = None,
    ) -> int:
        """Cuenta el total de documentos pertenecientes a un workspace específico."""
        ...

    def soft_delete(self, workspace_id: UUID, document_id: UUID) -> bool:
        """Elimina lógicamente un documento dentro del workspace especificado."""
        ...
