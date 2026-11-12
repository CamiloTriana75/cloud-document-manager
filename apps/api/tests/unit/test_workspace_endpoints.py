"""Pruebas unitarias de endpoints HTTP de Workspaces y Miembros (CDM-26 / AGENTS.md §11).

Prueba los contratos OpenAPI, códigos de estado (201, 200, 401, 403, 404, 409, 422)
y respuestas estándar mediante TestClient con base de datos SQLite en memoria.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from cdm.adapters.inbound.http.auth import get_current_user
from cdm.adapters.inbound.http.dependencies import get_db_session
from cdm.adapters.outbound.persistence.models import Base
from cdm.bootstrap.app import create_app
from cdm.config.settings import Settings
from cdm.domain.identity import AuthenticatedUser
from cdm.domain.workspace import WorkspaceRole


@pytest.fixture
def sqlite_session() -> Iterator[Session]:
    """Crea una base de datos SQLite en memoria para la prueba."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def test_client(sqlite_session: Session) -> TestClient:
    settings = Settings(
        database_url="sqlite:///:memory:",
        cors_origins="*",
        cognito_user_pool_id="us-east-1_mock",
        cognito_client_id="mock-client-id",
        cognito_region="us-east-1",
    )
    app = create_app(settings)

    # Override de la sesión de BD
    def override_db() -> Iterator[Session]:
        yield sqlite_session

    app.dependency_overrides[get_db_session] = override_db
    return TestClient(app)


def test_create_workspace_unauthenticated_returns_401(test_client: TestClient):
    """Sin token de autorización devuelve 401 con envelope estándar."""
    response = test_client.post("/api/v1/workspaces", json={"name": "Test"})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "missing_token"


def test_create_workspace_success(test_client: TestClient):
    """Crea un workspace correctamente y devuelve 201 con rol OWNER."""
    mock_user = AuthenticatedUser(
        cognito_sub="sub-user-1",
        email="user1@example.com",
        name="User One",
    )
    test_client.app.dependency_overrides[get_current_user] = lambda: mock_user

    response = test_client.post(
        "/api/v1/workspaces",
        json={"name": "Espacio de Ingeniería", "slug": "espacio-ingenieria"},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Espacio de Ingeniería"
    assert data["slug"] == "espacio-ingenieria"
    assert data["role"] == WorkspaceRole.OWNER.value
    assert "id" in data


def test_create_workspace_validation_error(test_client: TestClient):
    """Payload inválido devuelve 422 validation_error."""
    mock_user = AuthenticatedUser(cognito_sub="sub-1", email="u1@test.com")
    test_client.app.dependency_overrides[get_current_user] = lambda: mock_user

    response = test_client.post("/api/v1/workspaces", json={"name": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_workspaces_returns_only_user_workspaces(test_client: TestClient):
    """GET /api/v1/workspaces retorna la lista de workspaces accesibles."""
    user1 = AuthenticatedUser(cognito_sub="sub-1", email="u1@test.com")
    test_client.app.dependency_overrides[get_current_user] = lambda: user1

    # Crear workspace para user1
    test_client.post("/api/v1/workspaces", json={"name": "Workspace A"})

    res = test_client.get("/api/v1/workspaces")
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 1
    assert items[0]["name"] == "Workspace A"
    assert items[0]["role"] == "OWNER"

    # Cambiar a user2: no debe ver el workspace de user1
    user2 = AuthenticatedUser(cognito_sub="sub-2", email="u2@test.com")
    test_client.app.dependency_overrides[get_current_user] = lambda: user2

    res2 = test_client.get("/api/v1/workspaces")
    assert res2.status_code == 200
    assert len(res2.json()["data"]) == 0


def test_list_members_unauthorized_workspace_returns_404(test_client: TestClient):
    """Acceder a miembros de workspace al que no pertenece devuelve 404 (no revela existencia)."""
    user1 = AuthenticatedUser(cognito_sub="sub-1", email="u1@test.com")
    test_client.app.dependency_overrides[get_current_user] = lambda: user1

    create_res = test_client.post("/api/v1/workspaces", json={"name": "Workspace Secreto"})
    ws_id = create_res.json()["data"]["id"]

    # Usuario ajeno intenta listar miembros
    user_stranger = AuthenticatedUser(cognito_sub="sub-stranger", email="stranger@test.com")
    test_client.app.dependency_overrides[get_current_user] = lambda: user_stranger

    res = test_client.get(f"/api/v1/workspaces/{ws_id}/members")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "workspace_not_found"


def test_add_member_and_list_members_flow(test_client: TestClient):
    """Flujo completo: OWNER agrega un miembro y ambos aparecen en el listado."""
    owner = AuthenticatedUser(cognito_sub="sub-owner", email="owner@test.com")
    test_client.app.dependency_overrides[get_current_user] = lambda: owner

    create_res = test_client.post("/api/v1/workspaces", json={"name": "Equipo Dev"})
    ws_id = create_res.json()["data"]["id"]

    # Agregar miembro
    add_res = test_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "colaborador@test.com", "role": "MEMBER"},
    )
    assert add_res.status_code == 201
    member_data = add_res.json()["data"]
    assert member_data["email"] == "colaborador@test.com"
    assert member_data["role"] == "MEMBER"

    # Listar miembros
    list_res = test_client.get(f"/api/v1/workspaces/{ws_id}/members")
    assert list_res.status_code == 200
    members = list_res.json()["data"]
    assert len(members) == 2
    emails = [m["email"] for m in members]
    assert "owner@test.com" in emails
    assert "colaborador@test.com" in emails


def test_add_member_permission_denied_for_member_role(test_client: TestClient):
    """Un usuario con rol MEMBER que intenta invitar a otro recibe 403."""
    owner = AuthenticatedUser(cognito_sub="sub-owner", email="owner@test.com")
    test_client.app.dependency_overrides[get_current_user] = lambda: owner

    create_res = test_client.post("/api/v1/workspaces", json={"name": "Equipo"})
    ws_id = create_res.json()["data"]["id"]

    # Agregar un MEMBER
    test_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "simplemember@test.com", "role": "MEMBER"},
    )

    # Autenticar como el simple MEMBER
    simple_member = AuthenticatedUser(
        cognito_sub="invited:simplemember@test.com", email="simplemember@test.com"
    )
    test_client.app.dependency_overrides[get_current_user] = lambda: simple_member

    # Intento de invitar a alguien más
    res = test_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "thirdperson@test.com", "role": "VIEWER"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "permission_denied"


def test_add_member_conflict_if_already_member(test_client: TestClient):
    """Intentar agregar a alguien que ya es miembro devuelve 409 conflict."""
    owner = AuthenticatedUser(cognito_sub="sub-owner", email="owner@test.com")
    test_client.app.dependency_overrides[get_current_user] = lambda: owner

    create_res = test_client.post("/api/v1/workspaces", json={"name": "Equipo"})
    ws_id = create_res.json()["data"]["id"]

    test_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "colleague@test.com", "role": "MEMBER"},
    )

    # Intento duplicado
    res2 = test_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "colleague@test.com", "role": "MEMBER"},
    )
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "user_already_member"
