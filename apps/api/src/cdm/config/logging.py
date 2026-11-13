"""Configuración y sanitización de logs para Cloud Document Manager (CDM-52 / AGENTS.md §8, §14).

Garantiza observabilidad completa en CloudWatch y protección contra fuga de información:
- Formato estructurado JSON con correlación (request_id, tenant_id, document_id).
- Sanitización estricta de Bearer tokens, JWTs, contraseñas y firmas prefirmadas de S3.
"""

from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Context variables para trazabilidad y correlación distribuida (CDM-52)
current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)
current_tenant_id: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)
current_document_id: ContextVar[str | None] = ContextVar("current_document_id", default=None)


def set_log_context(
    request_id: str | None = None,
    tenant_id: str | None = None,
    document_id: str | None = None,
) -> None:
    """Establece los identificadores de correlación en el contexto de ejecución actual."""
    if request_id is not None:
        current_request_id.set(request_id)
    if tenant_id is not None:
        current_tenant_id.set(tenant_id)
    if document_id is not None:
        current_document_id.set(document_id)


def clear_log_context() -> None:
    """Limpia los identificadores de correlación del contexto actual."""
    current_request_id.set(None)
    current_tenant_id.set(None)
    current_document_id.set(None)


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


class StructuredJsonFormatter(logging.Formatter):
    """Formateador JSON estructurado para CloudWatch Logs con correlación (CDM-52)."""

    def format(self, record: logging.LogRecord) -> str:
        # Extraer mensaje base ya formateado
        message = record.getMessage()

        # Extraer metadatos de correlación desde contextvars o desde record.extra
        request_id = getattr(record, "request_id", None) or current_request_id.get()
        tenant_id = getattr(record, "tenant_id", None) or current_tenant_id.get()
        document_id = getattr(record, "document_id", None) or current_document_id.get()

        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_log_message(message),
        }

        if request_id:
            log_data["request_id"] = request_id
        if tenant_id:
            log_data["tenant_id"] = str(tenant_id)
        if document_id:
            log_data["document_id"] = str(document_id)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def configure_logging(log_level: str = "INFO", structured: bool = False) -> None:
    """Configura el logging raíz con el filtro sanitizador y opcionalmente formato JSON."""
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Añadir el filtro sanitizador al logger raíz si no está presente
    has_filter = any(isinstance(f, SensitiveDataSanitizingFilter) for f in root_logger.filters)
    if not has_filter:
        root_logger.addFilter(SensitiveDataSanitizingFilter())

    if structured:
        # Configurar un handler con StructuredJsonFormatter
        json_handler = logging.StreamHandler()
        json_handler.setFormatter(StructuredJsonFormatter())
        json_handler.addFilter(SensitiveDataSanitizingFilter())
        root_logger.handlers = [json_handler]
    else:
        # Asegurar que los handlers existentes también tengan el filtro
        for existing_handler in root_logger.handlers:
            has_existing_filter = any(
                isinstance(f, SensitiveDataSanitizingFilter) for f in existing_handler.filters
            )
            if not has_existing_filter:
                existing_handler.addFilter(SensitiveDataSanitizingFilter())
