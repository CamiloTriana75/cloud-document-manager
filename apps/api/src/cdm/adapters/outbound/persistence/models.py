"""Modelos ORM de SQLAlchemy para persistencia relacional (CDM-26).

Viven exclusivamente en adapters/outbound/persistence. No se exponen hacia el
dominio ni hacia la capa de aplicación (AGENTS.md §8.2).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from cdm.domain.workspace import (
    MembershipStatus,
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
)


class Base(DeclarativeBase):
    """Base declarativa de SQLAlchemy 2.0."""

    pass


# Tipo UUID compatible con PostgreSQL y SQLite (para pruebas unitarias en memoria)
UUID_TYPE = Uuid().with_variant(PG_UUID(as_uuid=True), "postgresql")


class UserModel(Base):
    """Modelo ORM para la tabla users."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    cognito_sub: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    workspaces_created: Mapped[list[WorkspaceModel]] = relationship(
        "WorkspaceModel", back_populates="creator", cascade="all, delete-orphan"
    )
    memberships: Mapped[list[WorkspaceMembershipModel]] = relationship(
        "WorkspaceMembershipModel", back_populates="user", cascade="all, delete-orphan"
    )

    def to_domain(self) -> User:
        """Convierte este registro ORM a la entidad pura de dominio."""
        return User(
            id=self.id,
            cognito_sub=self.cognito_sub,
            email=self.email,
            display_name=self.display_name,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, user: User) -> UserModel:
        """Crea una instancia del modelo ORM a partir de la entidad de dominio."""
        return cls(
            id=user.id,
            cognito_sub=user.cognito_sub,
            email=user.email,
            display_name=user.display_name,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class WorkspaceModel(Base):
    """Modelo ORM para la tabla workspaces."""

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    creator: Mapped[UserModel] = relationship("UserModel", back_populates="workspaces_created")
    memberships: Mapped[list[WorkspaceMembershipModel]] = relationship(
        "WorkspaceMembershipModel", back_populates="workspace", cascade="all, delete-orphan"
    )

    def to_domain(self) -> Workspace:
        """Convierte este registro ORM a la entidad pura de dominio."""
        return Workspace(
            id=self.id,
            name=self.name,
            slug=self.slug,
            created_by=self.created_by,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, workspace: Workspace) -> WorkspaceModel:
        """Crea una instancia del modelo ORM a partir de la entidad de dominio."""
        return cls(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            created_by=workspace.created_by,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )


class WorkspaceMembershipModel(Base):
    """Modelo ORM para la tabla workspace_memberships."""

    __tablename__ = "workspace_memberships"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    workspace: Mapped[WorkspaceModel] = relationship("WorkspaceModel", back_populates="memberships")
    user: Mapped[UserModel] = relationship("UserModel", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership_user"),
    )

    def to_domain(self) -> WorkspaceMembership:
        """Convierte este registro ORM a la entidad pura de dominio."""
        return WorkspaceMembership(
            id=self.id,
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            role=WorkspaceRole(self.role),
            status=MembershipStatus(self.status),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, membership: WorkspaceMembership) -> WorkspaceMembershipModel:
        """Crea una instancia del modelo ORM a partir de la entidad de dominio."""
        return cls(
            id=membership.id,
            workspace_id=membership.workspace_id,
            user_id=membership.user_id,
            role=membership.role.value,
            status=membership.status.value,
            created_at=membership.created_at,
            updated_at=membership.updated_at,
        )
