"""Contrato del envelope de error estándar (docs/api/standards.md §3)."""

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from cdm.adapters.inbound.http.pagination import PageParams, page_params
from cdm.bootstrap.app import create_app
from cdm.domain.errors import (
    ConflictError,
    NotAMemberError,
    NotFoundError,
    PermissionDeniedError,
)


def _app_with_test_routes() -> FastAPI:
    """App real + rutas de prueba que disparan cada error mapeado."""
    app = create_app()
    router = APIRouter(prefix="/api/v1", tags=["contract-probe"])

    @router.get("/contract-not-found")
    async def not_found() -> None:
        raise NotFoundError("El recurso solicitado no existe.")

    @router.get("/contract-permission")
    async def permission_denied() -> None:
        raise PermissionDeniedError("No tienes permiso para esta acción.")

    @router.get("/contract-not-member")
    async def not_a_member() -> None:
        raise NotAMemberError("No perteneces a este workspace.")

    @router.get("/contract-conflict")
    async def conflict() -> None:
        raise ConflictError("El documento ya fue confirmado.")

    @router.get("/contract-pagination")
    async def pagination(
        params: Annotated[PageParams, Depends(page_params)],
    ) -> dict[str, int]:
        return {"limit": params.limit}

    app.include_router(router)
    return app


def test_not_found_usa_envelope_y_404() -> None:
    client = TestClient(_app_with_test_routes())
    response = client.get("/api/v1/contract-not-found")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "El recurso solicitado no existe.",
            "details": None,
        }
    }


def test_permission_denied_y_not_member_son_403() -> None:
    client = TestClient(_app_with_test_routes())

    for path in ("/api/v1/contract-permission", "/api/v1/contract-not-member"):
        response = client.get(path)
        assert response.status_code == 403
        assert response.json()["error"]["details"] is None


def test_conflict_es_409() -> None:
    client = TestClient(_app_with_test_routes())
    response = client.get("/api/v1/contract-conflict")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_ruta_desconocida_usa_envelope_sin_stack() -> None:
    client = TestClient(_app_with_test_routes())
    response = client.get("/api/v1/no-existe")

    assert response.status_code == 404
    body = response.json()["error"]
    assert body["code"] == "not_found"
    assert "Traceback" not in body["message"]


def test_limit_invalido_es_422_con_details_por_campo() -> None:
    client = TestClient(_app_with_test_routes())
    response = client.get("/api/v1/contract-pagination", params={"limit": 999})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "query.limit"


def test_limit_valido_se_aplica() -> None:
    client = TestClient(_app_with_test_routes())
    response = client.get("/api/v1/contract-pagination", params={"limit": 50})

    assert response.status_code == 200
    assert response.json() == {"limit": 50}


def test_fallback_500_no_expone_stack() -> None:
    app = create_app()
    router = APIRouter(prefix="/api/v1", tags=["contract-probe"])

    @router.get("/contract-crash")
    async def crash() -> None:
        raise RuntimeError("secreto-interno-xyz")

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/contract-crash")

    assert response.status_code == 500
    body = response.text
    assert "secreto-interno-xyz" not in body
    assert "RuntimeError" not in body
