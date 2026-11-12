"""Errores de dominio tipados.

Puros: sin HTTP ni frameworks. El adaptador HTTP los mapea a códigos/estados
estables (ver ``adapters/inbound/http/errors.py`` y ``docs/api/standards.md``).
"""

from __future__ import annotations


class DomainError(Exception):
    """Base de todos los errores de dominio de CDM."""

    code = "domain_error"

    def __init__(self, message: str, *, details: list[dict[str, str]] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(DomainError):
    """Recurso inexistente o de otro tenant (nunca revelar cuál de las dos)."""

    code = "not_found"


class PermissionDeniedError(DomainError):
    """Miembro válido sin rol suficiente para la acción."""

    code = "permission_denied"


class NotAMemberError(DomainError):
    """Usuario sin membership activa en el workspace."""

    code = "not_a_member"


class UnauthenticatedError(DomainError):
    """Token ausente, inválido o expirado."""

    code = "unauthenticated"


class MissingTokenError(UnauthenticatedError):
    """Encabezado de autorización ausente o con formato incorrecto."""

    code = "missing_token"


class InvalidTokenError(UnauthenticatedError):
    """Firma de token inválida, issuer no coincide o claims corruptos."""

    code = "invalid_token"


class ExpiredTokenError(UnauthenticatedError):
    """El token ha superado su tiempo de vida (exp)."""

    code = "token_expired"


class ConflictError(DomainError):
    """El estado actual impide la operación (p. ej. transición prohibida)."""

    code = "conflict"


class FilePolicyViolationError(DomainError):
    """Formato no permitido o tamaño excedido según la política de archivos."""

    code = "file_policy_violation"
