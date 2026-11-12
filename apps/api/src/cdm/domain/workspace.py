"""Dominio: Workspaces, membresías y roles (CDM-26 / ADR-0001).

Puro: sin dependencias de frameworks ni librerías de infraestructura.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from cdm.domain.errors import InvalidWorkspaceDataError


class WorkspaceRole(str, Enum):
    """Roles de acceso dentro de un workspace según ADR-0001.

    Jerarquía: VIEWER (10) < MEMBER (20) < EDITOR (30) < ADMIN (40) < OWNER (50).
    """

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"

    @property
    def rank(self) -> int:
        """Nivel numérico para comparaciones jerárquicas."""
        ranks = {
            WorkspaceRole.VIEWER: 10,
            WorkspaceRole.MEMBER: 20,
            WorkspaceRole.EDITOR: 30,
            WorkspaceRole.ADMIN: 40,
            WorkspaceRole.OWNER: 50,
        }
        return ranks[self]

    def has_min_role(self, minimum: WorkspaceRole) -> bool:
        """Retorna True si este rol tiene igual o mayor jerarquía que el mínimo requerido."""
        return self.rank >= minimum.rank

    def can_admin_members(self) -> bool:
        """Determina si el rol tiene privilegios para gestionar miembros."""
        return self in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)


class MembershipStatus(str, Enum):
    """Estado de una membresía en un workspace."""

    ACTIVE = "ACTIVE"
    INVITED = "INVITED"
    SUSPENDED = "SUSPENDED"


_SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify(text: str) -> str:
    """Convierte texto en un slug normalizado (minúsculas, guiones, caracteres válidos)."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\s-]", "", ascii_text).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug


@dataclass(frozen=True)
class User:
    """Entidad de dominio: Usuario registrado en el sistema."""

    id: UUID
    cognito_sub: str
    email: str
    display_name: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        cognito_sub: str,
        email: str,
        display_name: str | None = None,
        user_id: UUID | None = None,
    ) -> User:
        """Fábrica para crear un nuevo usuario validando invariantes."""
        clean_email = email.strip().lower()
        if not clean_email or "@" not in clean_email:
            raise InvalidWorkspaceDataError("El email del usuario no es válido.")
        if not cognito_sub.strip():
            raise InvalidWorkspaceDataError("El cognito_sub no puede estar vacío.")

        now = datetime.now(UTC)
        return cls(
            id=user_id or uuid4(),
            cognito_sub=cognito_sub.strip(),
            email=clean_email,
            display_name=display_name.strip() if display_name else None,
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True)
class Workspace:
    """Entidad de dominio: Workspace (tenant de aislamiento documental)."""

    id: UUID
    name: str
    slug: str
    created_by: UUID
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        name: str,
        created_by: UUID,
        slug: str | None = None,
        workspace_id: UUID | None = None,
    ) -> Workspace:
        """Crea un Workspace validando invariantes de negocio."""
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 100:
            raise InvalidWorkspaceDataError(
                "El nombre del workspace debe tener entre 1 y 100 caracteres."
            )

        clean_slug = slug.strip().lower() if slug else slugify(clean_name)
        if not clean_slug or len(clean_slug) > 100:
            raise InvalidWorkspaceDataError(
                "El slug del workspace debe tener entre 1 y 100 caracteres."
            )
        if not _SLUG_REGEX.match(clean_slug):
            raise InvalidWorkspaceDataError(
                "El slug solo puede contener letras minúsculas, números y guiones sencillos."
            )

        now = datetime.now(UTC)
        return cls(
            id=workspace_id or uuid4(),
            name=clean_name,
            slug=clean_slug,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True)
class WorkspaceMembership:
    """Entidad de dominio: Membresía de un usuario en un workspace."""

    id: UUID
    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    status: MembershipStatus = MembershipStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        workspace_id: UUID,
        user_id: UUID,
        role: WorkspaceRole,
        status: MembershipStatus = MembershipStatus.ACTIVE,
        membership_id: UUID | None = None,
    ) -> WorkspaceMembership:
        """Crea una membresía validando invariantes."""
        now = datetime.now(UTC)
        return cls(
            id=membership_id or uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            status=status,
            created_at=now,
            updated_at=now,
        )
