"""Endpoint de salud (AGENTS.md §11).

Sin autenticación, sin secretos ni configuración sensible en la respuesta.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])

_SERVICE = "cdm-api"
_VERSION = "0.1.0"


@router.get("/health")
async def health() -> dict[str, str]:
    """Indica que el proceso responde. No revela configuración interna."""
    return {"status": "ok", "service": _SERVICE, "version": _VERSION}
