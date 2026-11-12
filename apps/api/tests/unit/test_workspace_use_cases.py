"""Pruebas unitarias de casos de uso de Workspaces y Membresías (CDM-26).

Verifica la orquestación de negocio, aislamiento multi-tenant y reglas de permisos
usando dobles en memoria para aislar la lógica del almacenamiento.
"""

from uuid import UUID

import pytest

from cdm.application.ports.workspace_repository import (
    MembershipRepositoryPort,
    UserRepositoryPort,
    WorkspaceRepositoryPort,
)
from cdm.application.use_cases.workspaces import (
    AddWorkspaceMemberUseCase,
    CreateWorkspaceUseCase,
    ListUserWorkspacesUseCase,
    ListWorkspaceMembersUseCase,
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


class InMemoryUserRepository(UserRepositoryPort):
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    def save(self, user: User) -> User:
        self.users[user.id] = user
        return user

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    def get_by_cognito_sub(self, cognito_sub: str) -> User | None:
        for u in self.users.values():
            if u.cognito_sub == cognito_sub:
                return u
        return None

    def get_by_email(self, email: str) -> User | None:
        clean = email.strip().lower()
        for u in self.users.values():
            if u.email.lower() == clean:
                return u
        return None


class InMemoryWorkspaceRepository(WorkspaceRepositoryPort):
    def __init__(self) -> None:
        self.workspaces: dict[UUID, Workspace] = {}

    def save(self, workspace: Workspace) -> Workspace:
        self.workspaces[workspace.id] = workspace
        return workspace

    def get_by_id(self, workspace_id: UUID) -> Workspace | None:
        return self.workspaces.get(workspace_id)

    def get_by_slug(self, slug: str) -> Workspace | None:
        for w in self.workspaces.values():
            if w.slug == slug:
                return w
        return None


class InMemoryMembershipRepository(MembershipRepositoryPort):
    def __init__(self) -> None:
        self.memberships: dict[UUID, WorkspaceMembership] = {}

    def save(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        self.memberships[membership.id] = membership
        return membership

    def get_by_workspace_and_user(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceMembership | None:
        for m in self.memberships.values():
            if m.workspace_id == workspace_id and m.user_id == user_id:
                return m
        return None

    def list_by_user_id(
        self, user_id: UUID, status: MembershipStatus | None = None
    ) -> list[WorkspaceMembership]:
        return [
            m
            for m in self.memberships.values()
            if m.user_id == user_id and (status is None or m.status == status)
        ]

    def list_by_workspace_id(
        self, workspace_id: UUID, status: MembershipStatus | None = None
    ) -> list[WorkspaceMembership]:
        return [
            m
            for m in self.memberships.values()
            if m.workspace_id == workspace_id and (status is None or m.status == status)
        ]


@pytest.fixture
def repos():
    return {
        "users": InMemoryUserRepository(),
        "workspaces": InMemoryWorkspaceRepository(),
        "memberships": InMemoryMembershipRepository(),
    }


def test_create_workspace_assigns_owner_role(repos):
    """El creador del workspace se guarda y se le asigna rol OWNER automáticamente."""
    auth_user = AuthenticatedUser(
        cognito_sub="sub-owner", email="owner@test.com", name="Owner Name"
    )
    uc = CreateWorkspaceUseCase(repos["workspaces"], repos["memberships"], repos["users"])

    dto = uc.execute(auth_user=auth_user, name="Equipo Alpha")

    assert dto.name == "Equipo Alpha"
    assert dto.slug == "equipo-alpha"
    assert dto.role == WorkspaceRole.OWNER

    # Verificar que existe en el repositorio
    ws = repos["workspaces"].get_by_id(dto.id)
    assert ws is not None
    assert ws.name == "Equipo Alpha"

    # Verificar membresía
    user = repos["users"].get_by_cognito_sub("sub-owner")
    assert user is not None
    membership = repos["memberships"].get_by_workspace_and_user(ws.id, user.id)
    assert membership is not None
    assert membership.role == WorkspaceRole.OWNER
    assert membership.status == MembershipStatus.ACTIVE


def test_create_workspace_slug_collision_raises_error(repos):
    """Rechaza la creación si el slug ya está en uso."""
    auth_user = AuthenticatedUser(cognito_sub="sub-1", email="user1@test.com")
    uc = CreateWorkspaceUseCase(repos["workspaces"], repos["memberships"], repos["users"])

    uc.execute(auth_user=auth_user, name="Workspace Unico", slug="mi-espacio")

    with pytest.raises(WorkspaceSlugAlreadyExistsError):
        uc.execute(auth_user=auth_user, name="Otro Nombre", slug="mi-espacio")


def test_list_user_workspaces_only_returns_member_workspaces(repos):
    """Un usuario solo lista los workspaces donde tiene membresía activa."""
    user1 = AuthenticatedUser(cognito_sub="sub-1", email="u1@test.com")
    user2 = AuthenticatedUser(cognito_sub="sub-2", email="u2@test.com")

    create_uc = CreateWorkspaceUseCase(repos["workspaces"], repos["memberships"], repos["users"])
    list_uc = ListUserWorkspacesUseCase(repos["workspaces"], repos["memberships"], repos["users"])

    ws1 = create_uc.execute(user1, name="Workspace Uno")
    ws2 = create_uc.execute(user2, name="Workspace Dos")

    u1_workspaces = list_uc.execute(user1)
    assert len(u1_workspaces) == 1
    assert u1_workspaces[0].id == ws1.id

    u2_workspaces = list_uc.execute(user2)
    assert len(u2_workspaces) == 1
    assert u2_workspaces[0].id == ws2.id


def test_list_workspace_members_enforces_tenant_isolation(repos):
    """Si el usuario no pertenece al workspace, se lanza WorkspaceNotFoundError (no IDOR)."""
    user1 = AuthenticatedUser(cognito_sub="sub-1", email="u1@test.com")
    user_stranger = AuthenticatedUser(cognito_sub="sub-stranger", email="stranger@test.com")

    create_uc = CreateWorkspaceUseCase(repos["workspaces"], repos["memberships"], repos["users"])
    members_uc = ListWorkspaceMembersUseCase(
        repos["workspaces"], repos["memberships"], repos["users"]
    )

    ws = create_uc.execute(user1, name="Privado")

    # El dueño sí puede listar
    members = members_uc.execute(user1, ws.id)
    assert len(members) == 1
    assert members[0].email == "u1@test.com"
    assert members[0].role == WorkspaceRole.OWNER

    # El extraño recibe WorkspaceNotFoundError
    with pytest.raises(WorkspaceNotFoundError):
        members_uc.execute(user_stranger, ws.id)


def test_add_workspace_member_owner_and_admin_allowed(repos):
    """OWNER y ADMIN pueden invitar miembros."""
    owner = AuthenticatedUser(cognito_sub="sub-owner", email="owner@test.com")
    create_uc = CreateWorkspaceUseCase(repos["workspaces"], repos["memberships"], repos["users"])
    add_uc = AddWorkspaceMemberUseCase(repos["workspaces"], repos["memberships"], repos["users"])
    members_uc = ListWorkspaceMembersUseCase(
        repos["workspaces"], repos["memberships"], repos["users"]
    )

    ws = create_uc.execute(owner, name="Empresa")

    # Owner agrega un ADMIN
    m_admin = add_uc.execute(
        auth_user=owner,
        workspace_id=ws.id,
        email="admin@test.com",
        role=WorkspaceRole.ADMIN,
    )
    assert m_admin.role == WorkspaceRole.ADMIN
    assert m_admin.email == "admin@test.com"

    # Simular login del nuevo ADMIN
    admin_auth = AuthenticatedUser(cognito_sub="invited:admin@test.com", email="admin@test.com")
    # Admin agrega un MEMBER
    m_member = add_uc.execute(
        auth_user=admin_auth,
        workspace_id=ws.id,
        email="member@test.com",
        role=WorkspaceRole.MEMBER,
    )
    assert m_member.role == WorkspaceRole.MEMBER

    # Verificar que ahora hay 3 miembros
    members = members_uc.execute(owner, ws.id)
    assert len(members) == 3


def test_add_workspace_member_forbids_member_and_editor_roles(repos):
    """Un usuario con rol MEMBER o EDITOR no puede agregar miembros."""
    owner = AuthenticatedUser(cognito_sub="sub-owner", email="owner@test.com")
    create_uc = CreateWorkspaceUseCase(repos["workspaces"], repos["memberships"], repos["users"])
    add_uc = AddWorkspaceMemberUseCase(repos["workspaces"], repos["memberships"], repos["users"])

    ws = create_uc.execute(owner, name="Empresa")
    add_uc.execute(owner, ws.id, "editor@test.com", WorkspaceRole.EDITOR)

    editor_auth = AuthenticatedUser(cognito_sub="invited:editor@test.com", email="editor@test.com")

    with pytest.raises(PermissionDeniedError):
        add_uc.execute(editor_auth, ws.id, "viewer@test.com", WorkspaceRole.VIEWER)


def test_admin_cannot_appoint_owner_privilege_escalation(repos):
    """Un ADMIN no puede nombrar otro OWNER (prevención de escalación)."""
    owner = AuthenticatedUser(cognito_sub="sub-owner", email="owner@test.com")
    create_uc = CreateWorkspaceUseCase(repos["workspaces"], repos["memberships"], repos["users"])
    add_uc = AddWorkspaceMemberUseCase(repos["workspaces"], repos["memberships"], repos["users"])

    ws = create_uc.execute(owner, name="Empresa")
    add_uc.execute(owner, ws.id, "admin@test.com", WorkspaceRole.ADMIN)

    admin_auth = AuthenticatedUser(cognito_sub="invited:admin@test.com", email="admin@test.com")

    with pytest.raises(PermissionDeniedError):
        add_uc.execute(admin_auth, ws.id, "newowner@test.com", WorkspaceRole.OWNER)


def test_add_workspace_member_duplicate_raises_conflict(repos):
    """Agregar un usuario que ya pertenece al workspace lanza UserAlreadyMemberError."""
    owner = AuthenticatedUser(cognito_sub="sub-owner", email="owner@test.com")
    create_uc = CreateWorkspaceUseCase(repos["workspaces"], repos["memberships"], repos["users"])
    add_uc = AddWorkspaceMemberUseCase(repos["workspaces"], repos["memberships"], repos["users"])

    ws = create_uc.execute(owner, name="Empresa")
    add_uc.execute(owner, ws.id, "member@test.com", WorkspaceRole.MEMBER)

    with pytest.raises(UserAlreadyMemberError):
        add_uc.execute(owner, ws.id, "member@test.com", WorkspaceRole.MEMBER)
