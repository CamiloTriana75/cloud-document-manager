"""Pruebas unitarias para TenantContext y autorización de roles (CDM-27).

Verifica que el contexto verificado aplique la jerarquía de roles ADR-0001.
"""

from uuid import uuid4

import pytest

from cdm.domain.errors import PermissionDeniedError
from cdm.domain.tenant import TenantContext
from cdm.domain.workspace import WorkspaceRole


def test_tenant_context_role_requirement_success():
    """Un usuario con rol adecuado satisface require_role."""
    tenant_admin = TenantContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        user_email="admin@test.com",
        role=WorkspaceRole.ADMIN,
    )
    # ADMIN supera VIEWER, MEMBER, EDITOR y ADMIN
    tenant_admin.require_role(WorkspaceRole.VIEWER)
    tenant_admin.require_role(WorkspaceRole.MEMBER)
    tenant_admin.require_role(WorkspaceRole.EDITOR)
    tenant_admin.require_role(WorkspaceRole.ADMIN)


def test_tenant_context_role_requirement_failure():
    """Un usuario con rol inferior es rechazado con PermissionDeniedError."""
    tenant_viewer = TenantContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        user_email="viewer@test.com",
        role=WorkspaceRole.VIEWER,
    )
    with pytest.raises(PermissionDeniedError) as exc_info:
        tenant_viewer.require_role(WorkspaceRole.MEMBER)
    assert "MEMBER" in str(exc_info.value)


def test_tenant_context_document_action_permissions():
    """Valida los métodos de conveniencia de permisos documentales según ADR-0001."""
    owner = TenantContext(uuid4(), uuid4(), "owner@test.com", WorkspaceRole.OWNER)
    editor = TenantContext(uuid4(), uuid4(), "editor@test.com", WorkspaceRole.EDITOR)
    member = TenantContext(uuid4(), uuid4(), "member@test.com", WorkspaceRole.MEMBER)
    viewer = TenantContext(uuid4(), uuid4(), "viewer@test.com", WorkspaceRole.VIEWER)

    # Subida: MEMBER o superior
    assert owner.can_upload_documents()
    assert editor.can_upload_documents()
    assert member.can_upload_documents()
    assert not viewer.can_upload_documents()

    # Eliminación: EDITOR o superior
    assert owner.can_delete_documents()
    assert editor.can_delete_documents()
    assert not member.can_delete_documents()
    assert not viewer.can_delete_documents()
