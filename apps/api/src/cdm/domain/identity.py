"""Dominio: Identidad y usuarios autenticados (CDM-25).

Puro: sin dependencias de frameworks ni librerías de infraestructura.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedUser:
    """Representa la identidad autenticada y verificada del usuario."""

    cognito_sub: str
    email: str
    name: str | None = None
    email_verified: bool = False
    token_use: str = "access"
    id: UUID | None = None
