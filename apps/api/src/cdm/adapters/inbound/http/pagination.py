"""Parámetros y respuesta de paginación estándar (docs/api/standards.md §4).

``page_params`` es una dependencia FastAPI reutilizable por todo listado.
"""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

_DEFAULT_LIMIT = 25
_MAX_LIMIT = 100


class PageParams(BaseModel):
    """Límite y cursor de un listado; validados en el borde."""

    limit: int = _DEFAULT_LIMIT
    cursor: str | None = None


def page_params(
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = _DEFAULT_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
) -> PageParams:
    """Dependencia FastAPI: valida y normaliza limit/cursor de la request."""
    return PageParams(limit=limit, cursor=cursor)


class Page[ModelT](BaseModel):
    """Respuesta paginada: items + cursor de continuación (null = última página)."""

    items: list[ModelT]
    next_cursor: str | None = None
