"""Puertos de persistencia para Workspaces, Membresías y Usuarios (CDM-26).

Contratos puros de la capa de aplicación. Los casos de uso dependen exclusivamente
de estas interfaces (Protocol). Ningún detalle de SQLAlchemy se filtra aquí.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from cdm.domain.workspace import MembershipStatus, User, Workspace, WorkspaceMembership


class UserRepositoryPort(Protocol):
    """Contrato de persistencia para usuarios."""

    def save(self, user: User) -> User:
        """Persiste o actualiza un usuario y retorna la entidad actualizada."""
        ...

    def get_by_id(self, user_id: UUID) -> User | None:
        """Busca un usuario por su identificador UUID."""
        ...

    def get_by_cognito_sub(self, cognito_sub: str) -> User | None:
        """Busca un usuario por su identificador sub de Cognito."""
        ...

    def get_by_email(self, email: str) -> User | None:
        """Busca un usuario por su dirección de correo electrónico."""
        ...


class WorkspaceRepositoryPort(Protocol):
    """Contrato de persistencia para workspaces."""

    def save(self, workspace: Workspace) -> Workspace:
        """Persiste o actualiza un workspace y retorna la entidad."""
        ...

    def get_by_id(self, workspace_id: UUID) -> Workspace | None:
        """Busca un workspace por su identificador UUID."""
        ...

    def get_by_slug(self, slug: str) -> Workspace | None:
        """Busca un workspace por su slug único."""
        ...


class MembershipRepositoryPort(Protocol):
    """Contrato de persistencia para membresías en workspaces."""

    def save(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        """Persiste una membresía y retorna la entidad."""
        ...

    def get_by_workspace_and_user(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceMembership | None:
        """Busca la membresía de un usuario en un workspace específico."""
        ...

    def list_by_user_id(
        self, user_id: UUID, status: MembershipStatus | None = None
    ) -> list[WorkspaceMembership]:
        """Lista todas las membresías de un usuario, opcionalmente filtradas por estado."""
        ...

    def list_by_workspace_id(
        self, workspace_id: UUID, status: MembershipStatus | None = None
    ) -> list[WorkspaceMembership]:
        """Lista todas las membresías de un workspace, opcionalmente filtradas por estado."""
        ...
