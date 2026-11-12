"""Pruebas para las dependencias de autenticación y el endpoint /api/v1/me (CDM-25 / CDM-82).

Verifica rechazo con 401 ante token ausente, expirado o manipulado,
y respuesta 200 con envelope estándar ante identidad válida.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cdm.adapters.inbound.http.auth import get_token_verifier
from cdm.application.ports.auth import TokenVerifierPort
from cdm.bootstrap.app import create_app
from cdm.domain.errors import ExpiredTokenError, InvalidTokenError
from cdm.domain.identity import AuthenticatedUser


class FakeTokenVerifier(TokenVerifierPort):
    """Verificador de prueba para aislar las dependencias HTTP."""

    def verify_token(self, token: str) -> AuthenticatedUser:
        if token == "valid-token":
            return AuthenticatedUser(
                cognito_sub="sub-usuario-12345",
                email="ana@empresa.com",
                name="Ana Garcia",
                email_verified=True,
                token_use="access",
            )
        if token == "expired-token":
            raise ExpiredTokenError("El token ha expirado.")
        if token == "invalid-token":
            raise InvalidTokenError("Firma criptográfica inválida.")

        raise InvalidTokenError("Token desconocido.")


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier()
    return TestClient(app)


def test_get_me_without_authorization_header_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "missing_token"
    assert "WWW-Authenticate" in response.headers
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_get_me_with_invalid_token_returns_401(client: TestClient) -> None:
    response = client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "invalid_token"
    assert "WWW-Authenticate" in response.headers


def test_get_me_with_expired_token_returns_401(client: TestClient) -> None:
    response = client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer expired-token"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "token_expired"


def test_get_me_with_valid_token_returns_200_and_user_profile(client: TestClient) -> None:
    response = client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert body["data"]["sub"] == "sub-usuario-12345"
    assert body["data"]["email"] == "ana@empresa.com"
    assert body["data"]["name"] == "Ana Garcia"
    assert body["data"]["email_verified"] is True
    assert body["data"]["token_use"] == "access"
