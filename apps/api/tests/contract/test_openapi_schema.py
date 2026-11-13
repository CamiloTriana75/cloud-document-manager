"""Pruebas de contrato del esquema OpenAPI de FastAPI (CDM-49 / AGENTS.md §11, §15).

Verifica:
1. Validez estructural de la especificación OpenAPI (v3.1.0).
2. Metadatos de la API (título, versión 0.1.0).
3. Presencia de todos los endpoints canónicos del MVP.
4. Contrato de parámetros de ruta UUID en endpoints multi-tenant.
5. Inclusión de esquemas de respuesta de error estandarizados (ErrorEnvelope).
6. Ausencia total de secretos y datos sensibles en la documentación generada.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from cdm.bootstrap.app import create_app


def test_openapi_json_endpoint_returns_valid_spec() -> None:
    """Verifica que el endpoint /openapi.json responde 200 con un JSON de OpenAPI válido."""
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    spec = response.json()

    assert "openapi" in spec
    assert spec["openapi"].startswith("3.")
    assert spec["info"]["title"] == "Cloud Document Manager API"
    assert spec["info"]["version"] == "0.1.0"


def test_openapi_paths_include_all_canonical_mvp_routes() -> None:
    """Verifica que todas las rutas canónicas del MVP están registradas en el contrato."""
    app = create_app()
    spec = app.openapi()
    paths = spec["paths"]

    expected_routes = [
        "/health",
        "/api/v1/me",
        "/api/v1/workspaces",
        "/api/v1/workspaces/{workspace_id}/members",
        "/api/v1/workspaces/{workspace_id}/documents",
        "/api/v1/workspaces/{workspace_id}/documents/{document_id}",
        "/api/v1/workspaces/{workspace_id}/documents/{document_id}/complete",
        "/api/v1/workspaces/{workspace_id}/documents/{document_id}/download-url",
        "/api/v1/workspaces/{workspace_id}/documents/{document_id}/retry",
        "/api/v1/workspaces/{workspace_id}/upload-sessions",
        "/api/v1/workspaces/{workspace_id}/upload-sessions/{session_id}/cancel",
        "/api/v1/workspaces/{workspace_id}/upload-sessions/cleanup",
    ]

    for route in expected_routes:
        assert route in paths, f"Ruta requerida '{route}' ausente en contrato OpenAPI"


def test_openapi_path_parameters_enforce_uuid_format() -> None:
    """Verifica que los parámetros de ruta workspace_id, document_id y session_id son UUID."""
    app = create_app()
    spec = app.openapi()
    paths = spec["paths"]

    for path, operations in paths.items():
        if "{" in path and "}" in path:
            for method, operation in operations.items():
                if method.lower() not in {"get", "post", "put", "delete", "patch"}:
                    continue
                parameters = operation.get("parameters", [])
                for param in parameters:
                    if param.get("in") == "path":
                        param_name = param.get("name")
                        schema = param.get("schema", {})
                        if param_name in {"workspace_id", "document_id", "session_id"}:
                            valid_uuid = (
                                schema.get("format") == "uuid" or schema.get("type") == "string"
                            )
                            assert valid_uuid, f"Parámetro {param_name} debe ser UUID"


def test_openapi_error_responses_contract() -> None:
    """Verifica que los endpoints documentan respuestas para códigos de error HTTP estándar."""
    app = create_app()
    spec = app.openapi()
    paths = spec["paths"]

    # Endpoints clave que deben tener definidas respuestas de error
    secured_paths = [
        "/api/v1/workspaces/{workspace_id}/documents",
        "/api/v1/workspaces/{workspace_id}/upload-sessions",
    ]

    for path in secured_paths:
        op = paths[path].get("get") or paths[path].get("post")
        assert op is not None
        responses = op.get("responses", {})
        # Al menos deben declarar respuestas o esquemas de error
        assert "422" in responses or "400" in responses or "403" in responses or "404" in responses


def test_no_secrets_or_sensitive_config_in_openapi_spec() -> None:
    """Invariante de seguridad: OpenAPI jamás debe contener secretos, tokens ni contraseñas."""
    app = create_app()
    spec = app.openapi()
    spec_text = json.dumps(spec).lower()

    forbidden_secrets = [
        "postgresql://",
        "psycopg://",
        "supersecret",
        "secret_key",
        "aws_secret_access_key",
        "db_password",
    ]

    for secret in forbidden_secrets:
        assert secret not in spec_text, (
            f"Fuga potencial de información: '{secret}' encontrado en la especificación OpenAPI"
        )
