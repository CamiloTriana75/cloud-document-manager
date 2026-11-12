"""Pruebas unitarias para el dominio de Workspaces y Membresías (CDM-26).

Verifica entidades puras, invariantes de negocio y jerarquía de roles (ADR-0001).
"""

from uuid import uuid4

import pytest

from cdm.domain.errors import InvalidWorkspaceDataError
from cdm.domain.workspace import (
    MembershipStatus,
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    slugify,
)


def test_workspace_role_hierarchy():
    """Valida la jerarquía de roles según ADR-0001: VIEWER < MEMBER < EDITOR < ADMIN < OWNER."""
    assert WorkspaceRole.VIEWER.rank < WorkspaceRole.MEMBER.rank
    assert WorkspaceRole.MEMBER.rank < WorkspaceRole.EDITOR.rank
    assert WorkspaceRole.EDITOR.rank < WorkspaceRole.ADMIN.rank
    assert WorkspaceRole.ADMIN.rank < WorkspaceRole.OWNER.rank

    assert WorkspaceRole.OWNER.has_min_role(WorkspaceRole.ADMIN)
    assert WorkspaceRole.ADMIN.has_min_role(WorkspaceRole.ADMIN)
    assert not WorkspaceRole.MEMBER.has_min_role(WorkspaceRole.ADMIN)
    assert not WorkspaceRole.VIEWER.has_min_role(WorkspaceRole.MEMBER)


def test_workspace_role_admin_privileges():
    """Solo OWNER y ADMIN pueden administrar miembros."""
    assert WorkspaceRole.OWNER.can_admin_members()
    assert WorkspaceRole.ADMIN.can_admin_members()
    assert not WorkspaceRole.EDITOR.can_admin_members()
    assert not WorkspaceRole.MEMBER.can_admin_members()
    assert not WorkspaceRole.VIEWER.can_admin_members()


def test_slugify_normalization():
    """Valida la generación de slugs limpios a partir de nombres arbitrarios."""
    assert slugify("Mi Primer Workspace") == "mi-primer-workspace"
    assert slugify("  Área Técnica & Legal 2026!  ") == "area-tecnica-legal-2026"
    assert slugify("Super---Espacio") == "super-espacio"


def test_workspace_creation_valid():
    """Crea un workspace con slug autogenerado o provisto."""
    creator_id = uuid4()
    ws = Workspace.create(name="Equipo Finanzas", created_by=creator_id)
    assert ws.name == "Equipo Finanzas"
    assert ws.slug == "equipo-finanzas"
    assert ws.created_by == creator_id

    ws2 = Workspace.create(name="Equipo Finanzas", created_by=creator_id, slug="finanzas-corp")
    assert ws2.slug == "finanzas-corp"


def test_workspace_creation_invalid_name():
    """Rechaza nombres vacíos o excesivamente largos."""
    creator_id = uuid4()
    with pytest.raises(InvalidWorkspaceDataError):
        Workspace.create(name="", created_by=creator_id)

    with pytest.raises(InvalidWorkspaceDataError):
        Workspace.create(name="   ", created_by=creator_id)

    with pytest.raises(InvalidWorkspaceDataError):
        Workspace.create(name="a" * 101, created_by=creator_id)


def test_workspace_creation_invalid_slug():
    """Rechaza slugs con caracteres no permitidos o formato inválido."""
    creator_id = uuid4()
    with pytest.raises(InvalidWorkspaceDataError):
        Workspace.create(name="Test", created_by=creator_id, slug="invalid slug with spaces")

    with pytest.raises(InvalidWorkspaceDataError):
        Workspace.create(name="Test", created_by=creator_id, slug="-leading-dash")


def test_workspace_membership_creation():
    """Crea una membresía válida."""
    ws_id = uuid4()
    user_id = uuid4()
    membership = WorkspaceMembership.create(
        workspace_id=ws_id,
        user_id=user_id,
        role=WorkspaceRole.EDITOR,
    )
    assert membership.workspace_id == ws_id
    assert membership.user_id == user_id
    assert membership.role == WorkspaceRole.EDITOR
    assert membership.status == MembershipStatus.ACTIVE


def test_user_creation_valid_and_invalid():
    """Valida invariantes de entidad User."""
    user = User.create(cognito_sub="sub-123", email="user@example.com", display_name="User Name")
    assert user.email == "user@example.com"
    assert user.cognito_sub == "sub-123"
    assert user.display_name == "User Name"

    with pytest.raises(InvalidWorkspaceDataError):
        User.create(cognito_sub="", email="user@example.com")

    with pytest.raises(InvalidWorkspaceDataError):
        User.create(cognito_sub="sub-123", email="not-an-email")
