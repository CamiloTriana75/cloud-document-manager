"""Pruebas de contrato del endpoint de salud (AGENTS.md §15)."""

from fastapi.testclient import TestClient

from cdm.bootstrap.app import create_app


def test_health_responde_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "cdm-api"
    assert set(body) == {"status", "service", "version"}


def test_health_no_revela_configuracion() -> None:
    client = TestClient(create_app())
    response = client.get("/health")

    text = response.text.lower()
    for secreto in ("database_url", "password", "secret", "token", "postgres"):
        assert secreto not in text
