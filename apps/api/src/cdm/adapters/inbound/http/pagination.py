"""Parámetros y respuesta de paginación estándar (docs/api/standards.md §4).

``page_params`` es una dependencia FastAPI reutilizable por todo listado.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

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


class PaginationParams(BaseModel):
    """Parámetros de paginación offset/limit estándar."""

    limit: int = Field(default=50, ge=1, le=_MAX_LIMIT, description="Límite de resultados")
    offset: int = Field(default=0, ge=0, description="Desplazamiento inicial")


class PaginationMeta(BaseModel):
    """Metadatos de paginación para respuestas estructuradas."""

    total: int
    limit: int
    offset: int
    has_more: bool = False

    @classmethod
    def build(cls, total: int, limit: int, offset: int) -> PaginationMeta:
        return cls(
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total,
        )
