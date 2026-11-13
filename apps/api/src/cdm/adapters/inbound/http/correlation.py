"""Middleware de trazabilidad y correlación distribuida (CDM-52 / AGENTS.md §8, §14).

Captura o genera el identificador de solicitud (X-Request-ID / X-Correlation-ID)
y lo asocia al contexto de logging para toda la traza de la petición.
"""

from __future__ import annotations

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from cdm.config.logging import clear_log_context, set_log_context

_REQUEST_ID_HEADER = "x-request-id"
_CORRELATION_ID_HEADER = "x-correlation-id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware ASGI que gestiona el request_id en contextvars y en cabeceras de respuesta."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extraer request_id del cliente o generar uno nuevo
        request_id = (
            request.headers.get(_REQUEST_ID_HEADER)
            or request.headers.get(_CORRELATION_ID_HEADER)
            or uuid4().hex
        )

        set_log_context(request_id=request_id)
        try:
            response = await call_next(request)
            response.headers[_REQUEST_ID_HEADER] = request_id
            return response
        finally:
            clear_log_context()
