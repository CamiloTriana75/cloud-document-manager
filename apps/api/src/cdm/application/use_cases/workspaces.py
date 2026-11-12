"""Casos de uso para Workspaces y Gestión de Miembros (CDM-26 / ADR-0001).

Orquestan operaciones de negocio multi-tenant utilizando puertos puros.
No dependen de FastAPI, SQLAlchemy ni ningún framework HTTP/ORM.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from cdm.application.ports.workspace_repository import (
    MembershipRepositoryPort,
    UserRepositoryPort,
    WorkspaceRepositoryPort,
)
from cdm.domain.errors import (
    PermissionDeniedError,
    UserAlreadyMemberError,
    WorkspaceNotFoundError,
    WorkspaceSlugAlreadyExistsError,
)
from cdm.domain.identity import AuthenticatedUser
from cdm.domain.workspace import (
    MembershipStatus,
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
)


@dataclass(frozen=True)
class WorkspaceWithRoleDTO:
    """DTO de workspace enriquecido con el rol que el usuario autenticado posee en él."""

    id: UUID
    name: str
    slug: str
    role: WorkspaceRole
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class WorkspaceMemberDTO:
    """DTO representativo de un miembro perteneciente a un workspace."""

    membership_id: UUID
    user_id: UUID
    email: str
    display_name: str | None
    role: WorkspaceRole
    status: MembershipStatus
    created_at: datetime


def _sync_user(user_repo: UserRepositoryPort, auth_user: AuthenticatedUser) -> User:
    """Sincroniza o crea la entidad de usuario a partir del token autenticado."""
    existing = user_repo.get_by_cognito_sub(auth_user.cognito_sub)
    if existing:
        # Actualiza email o display_name si cambiaron
        if existing.email != auth_user.email or existing.display_name != auth_user.name:
            updated = User(
                id=existing.id,
                cognito_sub=existing.cognito_sub,
                email=auth_user.email,
                display_name=auth_user.name or existing.display_name,
                created_at=existing.created_at,
                updated_at=datetime.now(existing.updated_at.tzinfo),
            )
            return user_repo.save(updated)
        return existing

    # Si no existe por cognito_sub, buscar por email para vincular invitaciones previas
    by_email = user_repo.get_by_email(auth_user.email)
    if by_email:
        linked = User(
            id=by_email.id,
            cognito_sub=auth_user.cognito_sub,
            email=auth_user.email,
            display_name=auth_user.name or by_email.display_name,
            created_at=by_email.created_at,
            updated_at=datetime.now(by_email.updated_at.tzinfo),
        )
        return user_repo.save(linked)

    new_user = User.create(
        cognito_sub=auth_user.cognito_sub,
        email=auth_user.email,
        display_name=auth_user.name,
    )
    return user_repo.save(new_user)


class CreateWorkspaceUseCase:
    """Caso de uso: Crear un workspace y asociar al creador como OWNER (CDM-26)."""

    def __init__(
        self,
        workspace_repo: WorkspaceRepositoryPort,
        membership_repo: MembershipRepositoryPort,
        user_repo: UserRepositoryPort,
    ) -> None:
        self._workspace_repo = workspace_repo
        self._membership_repo = membership_repo
        self._user_repo = user_repo

    def execute(
        self,
        auth_user: AuthenticatedUser,
        name: str,
        slug: str | None = None,
    ) -> WorkspaceWithRoleDTO:
        user = _sync_user(self._user_repo, auth_user)

        workspace = Workspace.create(name=name, created_by=user.id, slug=slug)

        # Validar unicidad del slug
        existing_slug = self._workspace_repo.get_by_slug(workspace.slug)
        if existing_slug is not None:
            raise WorkspaceSlugAlreadyExistsError(
                f"El slug '{workspace.slug}' ya se encuentra en uso por otro workspace."
            )

        saved_workspace = self._workspace_repo.save(workspace)

        # Crear automáticamente la membresía de OWNER para el creador
        membership = WorkspaceMembership.create(
            workspace_id=saved_workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self._membership_repo.save(membership)

        return WorkspaceWithRoleDTO(
            id=saved_workspace.id,
            name=saved_workspace.name,
            slug=saved_workspace.slug,
            role=WorkspaceRole.OWNER,
            created_at=saved_workspace.created_at,
            updated_at=saved_workspace.updated_at,
        )


class ListUserWorkspacesUseCase:
    """Caso de uso: Listar todos los workspaces donde el usuario tiene membresía activa."""

    def __init__(
        self,
        workspace_repo: WorkspaceRepositoryPort,
        membership_repo: MembershipRepositoryPort,
        user_repo: UserRepositoryPort,
    ) -> None:
        self._workspace_repo = workspace_repo
        self._membership_repo = membership_repo
        self._user_repo = user_repo

    def execute(self, auth_user: AuthenticatedUser) -> list[WorkspaceWithRoleDTO]:
        user = self._user_repo.get_by_cognito_sub(auth_user.cognito_sub)
        if user is None:
            return []

        memberships = self._membership_repo.list_by_user_id(user.id, status=MembershipStatus.ACTIVE)
        results: list[WorkspaceWithRoleDTO] = []
        for membership in memberships:
            workspace = self._workspace_repo.get_by_id(membership.workspace_id)
            if workspace:
                results.append(
                    WorkspaceWithRoleDTO(
                        id=workspace.id,
                        name=workspace.name,
                        slug=workspace.slug,
                        role=membership.role,
                        created_at=workspace.created_at,
                        updated_at=workspace.updated_at,
                    )
                )

        # Ordenar por nombre para consistencia de presentación
        results.sort(key=lambda w: w.name.lower())
        return results


class ListWorkspaceMembersUseCase:
    """Caso de uso: Listar los miembros de un workspace asegurando aislamiento multi-tenant."""

    def __init__(
        self,
        workspace_repo: WorkspaceRepositoryPort,
        membership_repo: MembershipRepositoryPort,
        user_repo: UserRepositoryPort,
    ) -> None:
        self._workspace_repo = workspace_repo
        self._membership_repo = membership_repo
        self._user_repo = user_repo

    def execute(self, auth_user: AuthenticatedUser, workspace_id: UUID) -> list[WorkspaceMemberDTO]:
        user = self._user_repo.get_by_cognito_sub(auth_user.cognito_sub)
        if user is None:
            # Multi-tenancy: No revelar si el workspace existe a un usuario desconocido
            raise WorkspaceNotFoundError("El workspace solicitado no existe o no tiene acceso.")

        caller_membership = self._membership_repo.get_by_workspace_and_user(workspace_id, user.id)
        if caller_membership is None or caller_membership.status != MembershipStatus.ACTIVE:
            # Multi-tenancy: Mismo mensaje para evitar enumeración de recursos
            raise WorkspaceNotFoundError("El workspace solicitado no existe o no tiene acceso.")

        workspace = self._workspace_repo.get_by_id(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("El workspace solicitado no existe o no tiene acceso.")

        memberships = self._membership_repo.list_by_workspace_id(workspace_id)
        results: list[WorkspaceMemberDTO] = []
        for m in memberships:
            member_user = self._user_repo.get_by_id(m.user_id)
            if member_user:
                results.append(
                    WorkspaceMemberDTO(
                        membership_id=m.id,
                        user_id=member_user.id,
                        email=member_user.email,
                        display_name=member_user.display_name,
                        role=m.role,
                        status=m.status,
                        created_at=m.created_at,
                    )
                )

        # Ordenar miembros: primero OWNER, luego ADMIN, EDITOR, MEMBER, VIEWER
        results.sort(key=lambda m: (-m.role.rank, m.email))
        return results


class AddWorkspaceMemberUseCase:
    """Caso de uso: Agregar o invitar un miembro a un workspace (CDM-26 / ADR-0001)."""

    def __init__(
        self,
        workspace_repo: WorkspaceRepositoryPort,
        membership_repo: MembershipRepositoryPort,
        user_repo: UserRepositoryPort,
    ) -> None:
        self._workspace_repo = workspace_repo
        self._membership_repo = membership_repo
        self._user_repo = user_repo

    def execute(
        self,
        auth_user: AuthenticatedUser,
        workspace_id: UUID,
        email: str,
        role: WorkspaceRole,
    ) -> WorkspaceMemberDTO:
        user = self._user_repo.get_by_cognito_sub(auth_user.cognito_sub)
        if user is None:
            raise WorkspaceNotFoundError("El workspace solicitado no existe o no tiene acceso.")

        caller_membership = self._membership_repo.get_by_workspace_and_user(workspace_id, user.id)
        if caller_membership is None or caller_membership.status != MembershipStatus.ACTIVE:
            raise WorkspaceNotFoundError("El workspace solicitado no existe o no tiene acceso.")

        # Regla de autorización ADR-0001: solo OWNER y ADMIN pueden agregar/administrar miembros
        if not caller_membership.role.can_admin_members():
            raise PermissionDeniedError(
                "Solo los propietarios (OWNER) o administradores (ADMIN) pueden gestionar miembros."
            )

        # Prevención de escalación de privilegios: un ADMIN no puede nombrar un OWNER
        if caller_membership.role == WorkspaceRole.ADMIN and role == WorkspaceRole.OWNER:
            raise PermissionDeniedError(
                "Un administrador no tiene privilegios para transferir o asignar el rol de OWNER."
            )

        workspace = self._workspace_repo.get_by_id(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("El workspace solicitado no existe o no tiene acceso.")

        clean_email = email.strip().lower()
        if not clean_email or "@" not in clean_email:
            raise PermissionDeniedError("El correo electrónico indicado no es válido.")

        # Buscar usuario destino o crear registro placeholder
        target_user = self._user_repo.get_by_email(clean_email)
        if target_user is None:
            target_user = User.create(
                cognito_sub=f"invited:{clean_email}",
                email=clean_email,
                display_name=None,
            )
            target_user = self._user_repo.save(target_user)

        # Verificar si ya es miembro
        existing_membership = self._membership_repo.get_by_workspace_and_user(
            workspace_id, target_user.id
        )
        if existing_membership is not None:
            raise UserAlreadyMemberError(
                f"El usuario '{clean_email}' ya es miembro de este workspace."
            )

        # Crear y persistir membresía
        new_membership = WorkspaceMembership.create(
            workspace_id=workspace_id,
            user_id=target_user.id,
            role=role,
            status=MembershipStatus.ACTIVE,
        )
        saved_membership = self._membership_repo.save(new_membership)

        return WorkspaceMemberDTO(
            membership_id=saved_membership.id,
            user_id=target_user.id,
            email=target_user.email,
            display_name=target_user.display_name,
            role=saved_membership.role,
            status=saved_membership.status,
            created_at=saved_membership.created_at,
        )
