"""Dominio: TenantContext para autorización y aislamiento multi-tenant (CDM-27).

Representa el contexto seguro y verificado de pertenencia a un workspace (tenant).
Nunca se construye a partir de datos no confiables del cliente.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cdm.domain.errors import PermissionDeniedError
from cdm.domain.workspace import MembershipStatus, WorkspaceRole


@dataclass(frozen=True)
class TenantContext:
    """Contexto verificado de un tenant para una operación de negocio.

    Garantiza que toda operación sobre documentos y recursos conozca el tenant_id
    de forma explícita y obligatoria, además del rol verificado del usuario.
    """

    workspace_id: UUID
    user_id: UUID
    user_email: str
    role: WorkspaceRole
    status: MembershipStatus = MembershipStatus.ACTIVE

    def require_role(self, minimum_role: WorkspaceRole) -> None:
        """Verifica que el rol del usuario en este tenant cumpla o supere el mínimo requerido.

        Lanza:
            PermissionDeniedError: Si el rol del usuario no tiene la jerarquía requerida.
        """
        if not self.role.has_min_role(minimum_role):
            msg = f"Requiere rol mínimo {minimum_role.value}, rol actual: {self.role.value}."
            raise PermissionDeniedError(msg)

    def can_delete_documents(self) -> bool:
        """Verifica si el usuario puede eliminar documentos (EDITOR o superior, ADR-0001)."""
        return self.role.has_min_role(WorkspaceRole.EDITOR)

    def can_upload_documents(self) -> bool:
        """Verifica si el usuario puede subir documentos (MEMBER o superior, ADR-0001)."""
        return self.role.has_min_role(WorkspaceRole.MEMBER)
