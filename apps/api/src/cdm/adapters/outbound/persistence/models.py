"""Modelos ORM de SQLAlchemy para persistencia relacional (CDM-26).

Viven exclusivamente en adapters/outbound/persistence. No se exponen hacia el
dominio ni hacia la capa de aplicación (AGENTS.md §8.2).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from cdm.domain.audit import AuditAction, AuditEvent, ResourceType
from cdm.domain.document import Document, DocumentStatus
from cdm.domain.upload_session import UploadSession, UploadSessionStatus
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
    documents: Mapped[list[DocumentModel]] = relationship(
        "DocumentModel", back_populates="workspace", cascade="all, delete-orphan"
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


class DocumentModel(Base):
    """Modelo ORM para la tabla documents (CDM-27 / AGENTS.md §10)."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_UPLOAD")
    technical_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
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
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    workspace: Mapped[WorkspaceModel] = relationship("WorkspaceModel", back_populates="documents")

    __table_args__ = (
        Index("ix_documents_workspace_created", "workspace_id", "created_at"),
        Index("ix_documents_workspace_status", "workspace_id", "status"),
    )

    def to_domain(self) -> Document:
        """Convierte este registro ORM a la entidad de dominio."""
        return Document(
            id=self.id,
            workspace_id=self.workspace_id,
            uploaded_by=self.uploaded_by,
            original_filename=self.original_filename,
            storage_key=self.storage_key,
            content_type=self.content_type,
            size_bytes=self.size_bytes,
            checksum_sha256=self.checksum_sha256,
            status=DocumentStatus(self.status),
            technical_metadata=dict(self.technical_metadata) if self.technical_metadata else {},
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
        )

    @classmethod
    def from_domain(cls, doc: Document) -> DocumentModel:
        """Crea una instancia ORM a partir de la entidad pura de dominio."""
        return cls(
            id=doc.id,
            workspace_id=doc.workspace_id,
            uploaded_by=doc.uploaded_by,
            original_filename=doc.original_filename,
            storage_key=doc.storage_key,
            content_type=doc.content_type,
            size_bytes=doc.size_bytes,
            checksum_sha256=doc.checksum_sha256,
            status=doc.status.value,
            technical_metadata=doc.technical_metadata,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            deleted_at=doc.deleted_at,
        )


class UploadSessionModel(Base):
    """Modelo ORM para la tabla upload_sessions (CDM-29 / AGENTS.md §10)."""

    __tablename__ = "upload_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    expected_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
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

    workspace: Mapped[WorkspaceModel] = relationship("WorkspaceModel")
    user: Mapped[UserModel] = relationship("UserModel")
    document: Mapped[DocumentModel] = relationship("DocumentModel")

    def to_domain(self) -> UploadSession:
        return UploadSession(
            id=self.id,
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            document_id=self.document_id,
            storage_key=self.storage_key,
            expected_size_bytes=self.expected_size_bytes,
            expected_content_type=self.expected_content_type,
            expected_checksum_sha256=self.expected_checksum_sha256,
            status=UploadSessionStatus(self.status),
            expires_at=self.expires_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, session: UploadSession) -> UploadSessionModel:
        return cls(
            id=session.id,
            workspace_id=session.workspace_id,
            user_id=session.user_id,
            document_id=session.document_id,
            storage_key=session.storage_key,
            expected_size_bytes=session.expected_size_bytes,
            expected_content_type=session.expected_content_type,
            expected_checksum_sha256=session.expected_checksum_sha256,
            status=session.status.value,
            expires_at=session.expires_at,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )


class AuditEventModel(Base):
    """Modelo ORM para la tabla audit_events (CDM-40 / AGENTS.md §10)."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID_TYPE, nullable=True, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        index=True,
    )

    workspace: Mapped[WorkspaceModel] = relationship("WorkspaceModel")
    actor: Mapped[UserModel | None] = relationship("UserModel")

    __table_args__ = (
        Index("ix_audit_events_workspace_created", "workspace_id", "created_at"),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),
    )

    def to_domain(self) -> AuditEvent:
        """Convierte este registro ORM a la entidad de dominio."""
        return AuditEvent(
            id=self.id,
            workspace_id=self.workspace_id,
            action=AuditAction(self.action),
            resource_type=ResourceType(self.resource_type),
            actor_user_id=self.actor_user_id,
            resource_id=self.resource_id,
            details=dict(self.details) if self.details else {},
            ip_address=self.ip_address,
            created_at=self.created_at,
        )

    @classmethod
    def from_domain(cls, event: AuditEvent) -> AuditEventModel:
        """Crea una instancia ORM a partir de la entidad pura de dominio."""
        return cls(
            id=event.id,
            workspace_id=event.workspace_id,
            actor_user_id=event.actor_user_id,
            action=event.action.value,
            resource_type=event.resource_type.value,
            resource_id=event.resource_id,
            details=event.details,
            ip_address=event.ip_address,
            created_at=event.created_at,
        )
