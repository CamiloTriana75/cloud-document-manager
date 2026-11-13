"""Dominio: Auditoría y trazabilidad de eventos multi-tenant (CDM-40 / AGENTS.md §10).

Puro: sin dependencias de frameworks ni infraestructura.
Registra cambios relevantes de autorización, seguridad y ciclo de vida de recursos.
Invariante de seguridad: Los detalles de auditoría nunca deben contener tokens,
contraseñas, URLs prefirmadas ni secretos sensibles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class AuditAction(str, Enum):
    """Acciones auditables del sistema."""

    # Documentos
    DOCUMENT_CREATED = "DOCUMENT_CREATED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_PROCESSED = "DOCUMENT_PROCESSED"
    DOCUMENT_FAILED = "DOCUMENT_FAILED"
    DOCUMENT_RETRIED = "DOCUMENT_RETRIED"
    DOCUMENT_DOWNLOADED = "DOCUMENT_DOWNLOADED"
    DOCUMENT_DELETED = "DOCUMENT_DELETED"

    # Workspaces y membresías
    WORKSPACE_CREATED = "WORKSPACE_CREATED"
    MEMBER_ADDED = "MEMBER_ADDED"
    MEMBER_ROLE_UPDATED = "MEMBER_ROLE_UPDATED"
    MEMBER_REMOVED = "MEMBER_REMOVED"


class ResourceType(str, Enum):
    """Tipos de recursos auditables."""

    DOCUMENT = "DOCUMENT"
    WORKSPACE = "WORKSPACE"
    MEMBERSHIP = "MEMBERSHIP"
    UPLOAD_SESSION = "UPLOAD_SESSION"


_FORBIDDEN_DETAIL_KEYS = {
    "token",
    "access_token",
    "id_token",
    "refresh_token",
    "authorization",
    "secret",
    "password",
    "signature",
    "download_url",
    "upload_url",
}


def sanitize_audit_details(details: dict[str, Any]) -> dict[str, Any]:
    """Sanitiza el diccionario de detalles para impedir la filtración de secretos."""
    sanitized: dict[str, Any] = {}
    for key, value in details.items():
        clean_key = key.lower().strip()
        if any(forbidden in clean_key for forbidden in _FORBIDDEN_DETAIL_KEYS):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_audit_details(value)
        else:
            sanitized[key] = value
    return sanitized


@dataclass(frozen=True)
class AuditEvent:
    """Entidad pura de dominio que representa un evento de auditoría."""

    id: UUID
    workspace_id: UUID
    action: AuditAction
    resource_type: ResourceType
    actor_user_id: UUID | None = None
    resource_id: UUID | None = None
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def record(
        cls,
        workspace_id: UUID,
        action: AuditAction,
        resource_type: ResourceType,
        actor_user_id: UUID | None = None,
        resource_id: UUID | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        event_id: UUID | None = None,
    ) -> AuditEvent:
        """Crea un evento de auditoría aplicando sanitización automática de seguridad."""
        clean_details = sanitize_audit_details(details or {})
        return cls(
            id=event_id or uuid4(),
            workspace_id=workspace_id,
            action=action,
            resource_type=resource_type,
            actor_user_id=actor_user_id,
            resource_id=resource_id,
            details=clean_details,
            ip_address=ip_address.strip() if ip_address else None,
            created_at=datetime.now(UTC),
        )
