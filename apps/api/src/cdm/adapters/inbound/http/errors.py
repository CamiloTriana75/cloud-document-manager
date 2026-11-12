"""Mapeo central de errores → envelope HTTP estable (docs/api/standards.md §3).

Único lugar donde los errores de dominio se traducen a HTTP. Ningún handler
expone stack traces ni estructura interna.
"""

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from cdm.domain.errors import (
    ConflictError,
    DomainError,
    FilePolicyViolationError,
    NotAMemberError,
    NotFoundError,
    PermissionDeniedError,
    UnauthenticatedError,
)

_ERROR_ENVELOPE_DEFINITION: dict[str, object] = {
    "description": "Envelope estándar de error",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "not_found",
                    "message": "El recurso solicitado no existe.",
                    "details": None,
                }
            }
        }
    },
}

#: Respuestas de error reutilizables en la declaracion de routers.
ERROR_RESPONSES: dict[int | str, object] = {
    400: _ERROR_ENVELOPE_DEFINITION,
    403: _ERROR_ENVELOPE_DEFINITION,
    404: _ERROR_ENVELOPE_DEFINITION,
    422: _ERROR_ENVELOPE_DEFINITION,
}

#: Estado HTTP por tipo de error de dominio.
_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    NotAMemberError: status.HTTP_403_FORBIDDEN,
    UnauthenticatedError: status.HTTP_401_UNAUTHORIZED,
    ConflictError: status.HTTP_409_CONFLICT,
    FilePolicyViolationError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    DomainError: status.HTTP_400_BAD_REQUEST,
}


def _error_body(
    code: str, message: str, details: list[dict[str, str]] | None = None
) -> dict[str, object]:
    return {"error": {"code": code, "message": message, "details": details}}


def _json(status_code: int, body: dict[str, object]) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


def register_error_handlers(app: FastAPI) -> None:
    """Registra los handlers en la app (llamado desde bootstrap)."""

    @app.exception_handler(DomainError)
    async def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        status_code = _STATUS_BY_ERROR.get(type(exc), status.HTTP_400_BAD_REQUEST)
        return _json(status_code, _error_body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in err.get("loc", [])),
                "message": err.get("msg", "Valor inválido."),
            }
            for err in exc.errors()
        ]
        return _json(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            _error_body("validation_error", "Entrada inválida.", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Error en la solicitud."
        code = "not_found" if exc.status_code == status.HTTP_404_NOT_FOUND else "request_error"
        return _json(exc.status_code, _error_body(code, message))

    @app.exception_handler(Exception)
    async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return _json(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            _error_body("internal_error", "Error interno. Inténtalo de nuevo."),
        )
