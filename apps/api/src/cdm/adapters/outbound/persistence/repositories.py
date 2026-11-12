"""Implementación de repositorios mediante SQLAlchemy (CDM-26).

Mapea entidades de persistencia (modelos ORM) hacia y desde el dominio.
Los casos de uso solo consumen los puertos de aplicación (AGENTS.md §8).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from cdm.adapters.outbound.persistence.models import (
    UserModel,
    WorkspaceMembershipModel,
    WorkspaceModel,
)
from cdm.application.ports.workspace_repository import (
    MembershipRepositoryPort,
    UserRepositoryPort,
    WorkspaceRepositoryPort,
)
from cdm.domain.workspace import MembershipStatus, User, Workspace, WorkspaceMembership


class SqlAlchemyUserRepository(UserRepositoryPort):
    """Implementación de persistencia de usuarios con SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, user: User) -> User:
        existing = self._session.get(UserModel, user.id)
        if existing:
            existing.cognito_sub = user.cognito_sub
            existing.email = user.email
            existing.display_name = user.display_name
            existing.updated_at = user.updated_at
            self._session.flush()
            return existing.to_domain()

        model = UserModel.from_domain(user)
        self._session.add(model)
        self._session.flush()
        return model.to_domain()

    def get_by_id(self, user_id: UUID) -> User | None:
        model = self._session.get(UserModel, user_id)
        return model.to_domain() if model else None

    def get_by_cognito_sub(self, cognito_sub: str) -> User | None:
        stmt = select(UserModel).where(UserModel.cognito_sub == cognito_sub)
        model = self._session.scalars(stmt).first()
        return model.to_domain() if model else None

    def get_by_email(self, email: str) -> User | None:
        clean_email = email.strip().lower()
        stmt = select(UserModel).where(UserModel.email == clean_email)
        model = self._session.scalars(stmt).first()
        return model.to_domain() if model else None


class SqlAlchemyWorkspaceRepository(WorkspaceRepositoryPort):
    """Implementación de persistencia de workspaces con SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, workspace: Workspace) -> Workspace:
        existing = self._session.get(WorkspaceModel, workspace.id)
        if existing:
            existing.name = workspace.name
            existing.slug = workspace.slug
            existing.updated_at = workspace.updated_at
            self._session.flush()
            return existing.to_domain()

        model = WorkspaceModel.from_domain(workspace)
        self._session.add(model)
        self._session.flush()
        return model.to_domain()

    def get_by_id(self, workspace_id: UUID) -> Workspace | None:
        model = self._session.get(WorkspaceModel, workspace_id)
        return model.to_domain() if model else None

    def get_by_slug(self, slug: str) -> Workspace | None:
        stmt = select(WorkspaceModel).where(WorkspaceModel.slug == slug)
        model = self._session.scalars(stmt).first()
        return model.to_domain() if model else None


class SqlAlchemyMembershipRepository(MembershipRepositoryPort):
    """Implementación de persistencia de membresías con SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        existing = self._session.get(WorkspaceMembershipModel, membership.id)
        if existing:
            existing.role = membership.role.value
            existing.status = membership.status.value
            existing.updated_at = membership.updated_at
            self._session.flush()
            return existing.to_domain()

        model = WorkspaceMembershipModel.from_domain(membership)
        self._session.add(model)
        self._session.flush()
        return model.to_domain()

    def get_by_workspace_and_user(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceMembership | None:
        stmt = select(WorkspaceMembershipModel).where(
            WorkspaceMembershipModel.workspace_id == workspace_id,
            WorkspaceMembershipModel.user_id == user_id,
        )
        model = self._session.scalars(stmt).first()
        return model.to_domain() if model else None

    def list_by_user_id(
        self, user_id: UUID, status: MembershipStatus | None = None
    ) -> list[WorkspaceMembership]:
        stmt = select(WorkspaceMembershipModel).where(WorkspaceMembershipModel.user_id == user_id)
        if status:
            stmt = stmt.where(WorkspaceMembershipModel.status == status.value)
        models = self._session.scalars(stmt).all()
        return [m.to_domain() for m in models]

    def list_by_workspace_id(
        self, workspace_id: UUID, status: MembershipStatus | None = None
    ) -> list[WorkspaceMembership]:
        stmt = select(WorkspaceMembershipModel).where(
            WorkspaceMembershipModel.workspace_id == workspace_id
        )
        if status:
            stmt = stmt.where(WorkspaceMembershipModel.status == status.value)
        models = self._session.scalars(stmt).all()
        return [m.to_domain() for m in models]
