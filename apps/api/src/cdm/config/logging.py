"""Configuración y sanitización de logs para Cloud Document Manager (CDM-51 / AGENTS.md §8, §14).

Garantiza que ningún logger de la aplicación registre información sensible:
- Tokens de autenticación (Bearer tokens, JWTs).
- URLs prefirmadas de S3 (que contienen credenciales temporales y firmas X-Amz-Signature).
- Claves secretas o contraseñas en queries o cuerpos de mensaje.
"""

from __future__ import annotations

import logging
import re

# Patrones sensibles a redactar
_BEARER_TOKEN_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{15,}", re.IGNORECASE)
_JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")
_S3_PRESIGNED_PATTERN = re.compile(
    r"https://[^\s]+\?(?:[^\s]*X-Amz-Signature=[^\s]*|[^\s]*AWSAccessKeyId=[^\s]*)",
    re.IGNORECASE,
)
_CREDENTIAL_KEY_PATTERN = re.compile(
    r"(password|secret|authorization|access_token|refresh_token)\s*[:=]\s*['\"]?[^\s,'\"]+['\"]?",
    re.IGNORECASE,
)


def sanitize_log_message(message: str) -> str:
    """Sanitiza una cadena de texto eliminando credenciales, tokens y URLs prefirmadas."""
    if not message:
        return message

    sanitized = _BEARER_TOKEN_PATTERN.sub("Bearer [REDACTED]", message)
    sanitized = _JWT_PATTERN.sub("[JWT_TOKEN_REDACTED]", sanitized)
    sanitized = _S3_PRESIGNED_PATTERN.sub("https://[S3_PRESIGNED_URL_REDACTED]", sanitized)
    sanitized = _CREDENTIAL_KEY_PATTERN.sub(r"\1=[REDACTED]", sanitized)
    return sanitized


class SensitiveDataSanitizingFilter(logging.Filter):
    """Filtro de logging que sanea automáticamente el mensaje de cualquier LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_log_message(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: sanitize_log_message(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    sanitize_log_message(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        return True


def configure_logging(log_level: str = "INFO") -> None:
    """Configura el logging raíz con el filtro sanitizador de datos sensibles."""
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Añadir el filtro sanitizador al logger raíz si no está presente
    has_filter = any(isinstance(f, SensitiveDataSanitizingFilter) for f in root_logger.filters)
    if not has_filter:
        root_logger.addFilter(SensitiveDataSanitizingFilter())

    # Asegurar que los handlers existentes también tengan el filtro
    for handler in root_logger.handlers:
        if not any(isinstance(f, SensitiveDataSanitizingFilter) for f in handler.filters):
            handler.addFilter(SensitiveDataSanitizingFilter())
