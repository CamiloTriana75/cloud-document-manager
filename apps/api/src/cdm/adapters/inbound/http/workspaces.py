"""Adaptador inbound HTTP: Endpoints de Workspaces y Miembros (CDM-26 / AGENTS.md §11).

Expone:
- POST /api/v1/workspaces -> Crear workspace
- GET /api/v1/workspaces -> Listar workspaces accesibles
- GET /api/v1/workspaces/{workspace_id}/members -> Listar miembros del workspace
- POST /api/v1/workspaces/{workspace_id}/members -> Invitar/agregar miembro al workspace
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, Field

from cdm.adapters.inbound.http.auth import get_current_user
from cdm.adapters.inbound.http.dependencies import (
    get_add_workspace_member_use_case,
    get_create_workspace_use_case,
    get_list_user_workspaces_use_case,
    get_list_workspace_members_use_case,
)
from cdm.adapters.inbound.http.errors import ERROR_RESPONSES
from cdm.application.use_cases.workspaces import (
    AddWorkspaceMemberUseCase,
    CreateWorkspaceUseCase,
    ListUserWorkspacesUseCase,
    ListWorkspaceMembersUseCase,
)
from cdm.domain.identity import AuthenticatedUser
from cdm.domain.workspace import MembershipStatus, WorkspaceRole

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


# --- Schemas de Entrada ---


class CreateWorkspaceRequest(BaseModel):
    """Payload para la creación de un nuevo workspace."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre visible del workspace",
        examples=["Equipo de Finanzas"],
    )
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="Identificador legible en URL (opcional, generado a partir del nombre)",
        examples=["equipo-de-finanzas"],
    )


class AddWorkspaceMemberRequest(BaseModel):
    """Payload para invitar o agregar un miembro a un workspace."""

    email: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Correo electrónico del usuario a invitar",
        examples=["colleague@example.com"],
    )
    role: WorkspaceRole = Field(
        default=WorkspaceRole.MEMBER,
        description="Rol dentro del workspace según ADR-0001",
        examples=[WorkspaceRole.MEMBER.value],
    )


# --- Schemas de Salida ---


class WorkspaceResponse(BaseModel):
    """Representación pública de un workspace para el usuario autenticado."""

    id: UUID
    name: str
    slug: str
    role: WorkspaceRole
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberResponse(BaseModel):
    """Representación pública de un miembro de un workspace."""

    membership_id: UUID
    user_id: UUID
    email: str
    display_name: str | None
    role: WorkspaceRole
    status: MembershipStatus
    created_at: datetime


class EnvelopeWorkspace(BaseModel):
    """Envelope de respuesta para un único workspace."""

    data: WorkspaceResponse


class EnvelopeWorkspaceList(BaseModel):
    """Envelope de respuesta para una lista de workspaces."""

    data: list[WorkspaceResponse]


class EnvelopeMember(BaseModel):
    """Envelope de respuesta para un miembro agregado."""

    data: WorkspaceMemberResponse


class EnvelopeMemberList(BaseModel):
    """Envelope de respuesta para la lista de miembros."""

    data: list[WorkspaceMemberResponse]


# --- Endpoints ---


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=EnvelopeWorkspace,
    summary="Crear workspace",
    description="Crea un nuevo workspace (tenant) y asigna al creador el rol de OWNER.",
    responses=ERROR_RESPONSES,
)
def create_workspace(
    payload: CreateWorkspaceRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    use_case: Annotated[CreateWorkspaceUseCase, Depends(get_create_workspace_use_case)],
) -> EnvelopeWorkspace:
    workspace = use_case.execute(
        auth_user=current_user,
        name=payload.name,
        slug=payload.slug,
    )
    return EnvelopeWorkspace(
        data=WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            role=workspace.role,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )
    )


@router.get(
    "",
    response_model=EnvelopeWorkspaceList,
    summary="Listar workspaces",
    description="Retorna todos los workspaces donde el usuario autenticado posee membresía activa.",
    responses=ERROR_RESPONSES,
)
def list_workspaces(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    use_case: Annotated[ListUserWorkspacesUseCase, Depends(get_list_user_workspaces_use_case)],
) -> EnvelopeWorkspaceList:
    workspaces = use_case.execute(auth_user=current_user)
    return EnvelopeWorkspaceList(
        data=[
            WorkspaceResponse(
                id=w.id,
                name=w.name,
                slug=w.slug,
                role=w.role,
                created_at=w.created_at,
                updated_at=w.updated_at,
            )
            for w in workspaces
        ]
    )


@router.get(
    "/{workspace_id}/members",
    response_model=EnvelopeMemberList,
    summary="Listar miembros del workspace",
    description=(
        "Retorna la lista de miembros del workspace. Requiere que el usuario "
        "autenticado pertenezca al workspace (aislamiento multi-tenant estricto)."
    ),
    responses=ERROR_RESPONSES,
)
def list_workspace_members(
    workspace_id: Annotated[UUID, Path(description="Identificador del workspace")],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    use_case: Annotated[ListWorkspaceMembersUseCase, Depends(get_list_workspace_members_use_case)],
) -> EnvelopeMemberList:
    members = use_case.execute(auth_user=current_user, workspace_id=workspace_id)
    return EnvelopeMemberList(
        data=[
            WorkspaceMemberResponse(
                membership_id=m.membership_id,
                user_id=m.user_id,
                email=m.email,
                display_name=m.display_name,
                role=m.role,
                status=m.status,
                created_at=m.created_at,
            )
            for m in members
        ]
    )


@router.post(
    "/{workspace_id}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=EnvelopeMember,
    summary="Invitar o agregar miembro al workspace",
    description=(
        "Agrega o invita un usuario al workspace con un rol determinado. "
        "Operación restringida exclusivamente a usuarios con rol OWNER o ADMIN."
    ),
    responses=ERROR_RESPONSES,
)
def add_workspace_member(
    workspace_id: Annotated[UUID, Path(description="Identificador del workspace")],
    payload: AddWorkspaceMemberRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    use_case: Annotated[AddWorkspaceMemberUseCase, Depends(get_add_workspace_member_use_case)],
) -> EnvelopeMember:
    member = use_case.execute(
        auth_user=current_user,
        workspace_id=workspace_id,
        email=payload.email,
        role=payload.role,
    )
    return EnvelopeMember(
        data=WorkspaceMemberResponse(
            membership_id=member.membership_id,
            user_id=member.user_id,
            email=member.email,
            display_name=member.display_name,
            role=member.role,
            status=member.status,
            created_at=member.created_at,
        )
    )
