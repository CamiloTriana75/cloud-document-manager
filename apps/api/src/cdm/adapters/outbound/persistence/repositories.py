"""Implementación de repositorios mediante SQLAlchemy (CDM-26 / CDM-27).

Mapea entidades de persistencia (modelos ORM) hacia y desde el dominio.
Los casos de uso solo consumen los puertos de aplicación (AGENTS.md §8).
Toda operación sobre documentos exige workspace_id obligatoriamente (aislamiento multi-tenant).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cdm.adapters.outbound.persistence.models import (
    DocumentModel,
    UserModel,
    WorkspaceMembershipModel,
    WorkspaceModel,
)
from cdm.application.ports.document_repository import DocumentRepositoryPort
from cdm.application.ports.workspace_repository import (
    MembershipRepositoryPort,
    UserRepositoryPort,
    WorkspaceRepositoryPort,
)
from cdm.domain.document import Document, DocumentStatus
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


class SqlAlchemyDocumentRepository(DocumentRepositoryPort):
    """Implementación de persistencia para documentos con aislamiento estricto por tenant.

    Todas las consultas filtran obligatoriamente por workspace_id (tenant_id).
    No existe ningún método que consulte la tabla documents sin workspace_id (AGENTS.md §14).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, document: Document) -> Document:
        existing = self._session.get(DocumentModel, document.id)
        if existing:
            # Asegurar que el workspace_id nunca cambie en una actualización
            if existing.workspace_id != document.workspace_id:
                raise ValueError("No está permitido transferir un documento entre workspaces.")
            existing.original_filename = document.original_filename
            existing.status = document.status.value
            existing.technical_metadata = document.technical_metadata
            existing.checksum_sha256 = document.checksum_sha256
            existing.updated_at = document.updated_at
            existing.deleted_at = document.deleted_at
            self._session.flush()
            return existing.to_domain()

        model = DocumentModel.from_domain(document)
        self._session.add(model)
        self._session.flush()
        return model.to_domain()

    def get_by_id(
        self,
        workspace_id: UUID,
        document_id: UUID,
        include_deleted: bool = False,
    ) -> Document | None:
        stmt = select(DocumentModel).where(
            DocumentModel.id == document_id,
            DocumentModel.workspace_id == workspace_id,
        )
        if not include_deleted:
            stmt = stmt.where(
                DocumentModel.deleted_at.is_(None),
                DocumentModel.status != DocumentStatus.DELETED.value,
            )
        model = self._session.scalars(stmt).first()
        return model.to_domain() if model else None

    def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> list[Document]:
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.workspace_id == workspace_id)
            .order_by(DocumentModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if not include_deleted:
            stmt = stmt.where(
                DocumentModel.deleted_at.is_(None),
                DocumentModel.status != DocumentStatus.DELETED.value,
            )
        models = self._session.scalars(stmt).all()
        return [m.to_domain() for m in models]

    def count_by_workspace(
        self,
        workspace_id: UUID,
        include_deleted: bool = False,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(DocumentModel)
            .where(DocumentModel.workspace_id == workspace_id)
        )
        if not include_deleted:
            stmt = stmt.where(
                DocumentModel.deleted_at.is_(None),
                DocumentModel.status != DocumentStatus.DELETED.value,
            )
        count = self._session.scalar(stmt)
        return count or 0

    def soft_delete(self, workspace_id: UUID, document_id: UUID) -> bool:
        stmt = select(DocumentModel).where(
            DocumentModel.id == document_id,
            DocumentModel.workspace_id == workspace_id,
            DocumentModel.deleted_at.is_(None),
        )
        model = self._session.scalars(stmt).first()
        if model is None:
            return False

        now = datetime.now(UTC)
        model.deleted_at = now
        model.status = DocumentStatus.DELETED.value
        model.updated_at = now
        self._session.flush()
        return True
