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


class MaxRetriesExceededError(ConflictError):
    """Se ha alcanzado el límite máximo de reintentos permitidos para el documento (CDM-39)."""

    code = "max_retries_exceeded"


class WorkspaceNotFoundError(NotFoundError):
    """Workspace inexistente o inaccesible para el usuario actual."""

    code = "workspace_not_found"


class DocumentNotFoundError(NotFoundError):
    """Documento inexistente o perteneciente a otro workspace."""

    code = "document_not_found"


class InvalidDocumentDataError(DomainError):
    """Datos o estado del documento inválidos."""

    code = "invalid_document_data"


class WorkspaceSlugAlreadyExistsError(ConflictError):
    """El slug de workspace ya está en uso."""

    code = "workspace_slug_exists"


class UserAlreadyMemberError(ConflictError):
    """El usuario ya es miembro de este workspace."""

    code = "user_already_member"


class InvalidWorkspaceDataError(DomainError):
    """Datos de workspace o membresía inválidos según las reglas de negocio."""

    code = "invalid_workspace_data"


class FilePolicyViolationError(DomainError):
    """Formato no permitido o tamaño excedido según la política de archivos."""

    code = "file_policy_violation"


class FileTypeNotAllowedError(FilePolicyViolationError):
    """Tipo MIME o extensión de archivo no permitidos en la allowlist."""

    code = "file_type_not_allowed"


class FileSizeExceededError(FilePolicyViolationError):
    """El tamaño del archivo supera el límite configurado."""

    code = "file_size_exceeded"


class InvalidFileNameError(DomainError):
    """Nombre de archivo inválido, vacío o con intento de path traversal."""

    code = "invalid_file_name"


class InvalidChecksumError(DomainError):
    """Formato de checksum no válido (se requiere SHA-256 hexadecimal de 64 caracteres)."""

    code = "invalid_checksum"


class UploadSessionNotFoundError(NotFoundError):
    """Sesión de carga inexistente o perteneciente a otro workspace."""

    code = "upload_session_not_found"


class UploadSessionExpiredError(ConflictError):
    """La sesión de carga ha expirado y ya no puede ser completada."""

    code = "upload_session_expired"


class InvalidS3EventError(DomainError):
    """Estructura o contenido de evento S3 / SQS inválido o malformado."""

    code = "invalid_s3_event"
