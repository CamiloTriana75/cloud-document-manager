"""Pruebas de esquema relacional PostgreSQL y migraciones Alembic (CDM-40).

Criterios de aceptación (CDM-40):
1. Tablas requeridas: workspaces, workspace_memberships, documents, upload_sessions, audit_events.
2. Claves primarias (PK), foráneas (FK), índices y restricciones coherentes.
3. workspace_id presente y consultable en todas las entidades multi-tenant.
4. SQLAlchemy contenido exclusivamente en adaptadores/repositorios.
5. Migraciones Alembic aplicables y reversibles.
6. Sanitización de eventos de auditoría (sin tokens ni secretos en details).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from cdm.adapters.outbound.persistence.models import (
    Base,
)
from cdm.adapters.outbound.persistence.repositories import (
    SqlAlchemyAuditRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWorkspaceRepository,
)
from cdm.domain.audit import AuditAction, AuditEvent, ResourceType, sanitize_audit_details
from cdm.domain.workspace import (
    User,
    Workspace,
)


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(sqlite_engine):
    session_factory = sessionmaker(bind=sqlite_engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    yield session
    session.close()


def test_schema_tables_exist(sqlite_engine) -> None:
    """Verifica que todas las tablas requeridas por el catálogo existan (CDM-40)."""
    inspector = inspect(sqlite_engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "users",
        "workspaces",
        "workspace_memberships",
        "documents",
        "upload_sessions",
        "audit_events",
    }
    assert expected_tables.issubset(table_names), f"Faltan tablas: {expected_tables - table_names}"


def test_schema_foreign_keys_and_indexes(sqlite_engine) -> None:
    """Verifica las claves foráneas e índices de aislamiento multi-tenant."""
    inspector = inspect(sqlite_engine)

    # 1. Documents FKs e índices
    doc_fks = {fk["referred_table"] for fk in inspector.get_foreign_keys("documents")}
    assert "workspaces" in doc_fks
    assert "users" in doc_fks

    doc_indexes = {idx["name"] for idx in inspector.get_indexes("documents")}
    assert "ix_documents_workspace_id" in doc_indexes
    assert "ix_documents_workspace_status" in doc_indexes
    assert "ix_documents_workspace_created" in doc_indexes

    # 2. Audit Events FKs e índices
    audit_fks = {fk["referred_table"] for fk in inspector.get_foreign_keys("audit_events")}
    assert "workspaces" in audit_fks
    assert "users" in audit_fks

    audit_indexes = {idx["name"] for idx in inspector.get_indexes("audit_events")}
    assert "ix_audit_events_workspace_id" in audit_indexes
    assert "ix_audit_events_workspace_created" in audit_indexes
    assert "ix_audit_events_action" in audit_indexes

    # 3. Workspace Memberships Unique Constraint
    unique_constraints = inspector.get_unique_constraints("workspace_memberships")
    uq_names = {uq["name"] for uq in unique_constraints}
    assert "uq_workspace_membership_user" in uq_names or any(
        set(uq["column_names"]) == {"workspace_id", "user_id"} for uq in unique_constraints
    )


def test_audit_event_sanitization_removes_secrets() -> None:
    """Invariante de seguridad: Los detalles de auditoría no almacenan tokens ni secretos."""
    sensitive_details = {
        "document_name": "reporte.pdf",
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitive",
        "download_url": "https://s3.amazonaws.com/bucket/doc?X-Amz-Signature=secret",
        "secret_key": "my-secret-key",
        "nested": {
            "password": "super-secret-password",
            "safe_field": 12345,
        },
    }

    sanitized = sanitize_audit_details(sensitive_details)

    assert sanitized["document_name"] == "reporte.pdf"
    assert sanitized["token"] == "[REDACTED]"
    assert sanitized["download_url"] == "[REDACTED]"
    assert sanitized["secret_key"] == "[REDACTED]"
    assert sanitized["nested"]["password"] == "[REDACTED]"
    assert sanitized["nested"]["safe_field"] == 12345


def test_audit_repository_crud_and_tenant_isolation(db_session: Session) -> None:
    """Verifica persistencia y aislamiento multi-tenant del repositorio de auditoría."""
    user_repo = SqlAlchemyUserRepository(db_session)
    ws_repo = SqlAlchemyWorkspaceRepository(db_session)
    audit_repo = SqlAlchemyAuditRepository(db_session)

    # 1. Crear usuario y dos workspaces distintos
    user = User.create(cognito_sub="sub-audit-1", email="audit@test.com")
    saved_user = user_repo.save(user)

    ws_a = Workspace.create(name="Tenant Alpha", slug="tenant-alpha", created_by=saved_user.id)
    saved_ws_a = ws_repo.save(ws_a)

    ws_b = Workspace.create(name="Tenant Beta", slug="tenant-beta", created_by=saved_user.id)
    saved_ws_b = ws_repo.save(ws_b)

    # 2. Registrar eventos de auditoría en ambos tenants
    event_a = AuditEvent.record(
        workspace_id=saved_ws_a.id,
        action=AuditAction.DOCUMENT_UPLOADED,
        resource_type=ResourceType.DOCUMENT,
        actor_user_id=saved_user.id,
        resource_id=uuid.uuid4(),
        details={"file_name": "alpha.pdf", "size": 1024},
    )
    audit_repo.save(event_a)

    event_b = AuditEvent.record(
        workspace_id=saved_ws_b.id,
        action=AuditAction.DOCUMENT_DELETED,
        resource_type=ResourceType.DOCUMENT,
        actor_user_id=saved_user.id,
        resource_id=uuid.uuid4(),
        details={"file_name": "beta.pdf"},
    )
    audit_repo.save(event_b)

    # 3. Consultar y verificar aislamiento estricto
    items_a = audit_repo.list_by_workspace(saved_ws_a.id)
    assert len(items_a) == 1
    assert items_a[0].action == AuditAction.DOCUMENT_UPLOADED
    assert items_a[0].details["file_name"] == "alpha.pdf"
    assert audit_repo.count_by_workspace(saved_ws_a.id) == 1

    items_b = audit_repo.list_by_workspace(saved_ws_b.id)
    assert len(items_b) == 1
    assert items_b[0].action == AuditAction.DOCUMENT_DELETED
    assert items_b[0].details["file_name"] == "beta.pdf"
    assert audit_repo.count_by_workspace(saved_ws_b.id) == 1


def test_alembic_upgrade_and_downgrade_chain(tmp_path: Path) -> None:
    """Verifica que la cadena de migraciones Alembic aplique y revierta limpiamente."""
    db_file = tmp_path / "alembic_test.db"
    temp_sqlite_url = f"sqlite:///{db_file.as_posix()}"
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", temp_sqlite_url)

    # 1. Aplicar todas las migraciones (head -> 0005)
    command.upgrade(alembic_cfg, "head")

    # 2. Verificar que el esquema resultante contenga las tablas creadas
    test_engine = create_engine(temp_sqlite_url)
    try:
        inspector = inspect(test_engine)
        tables = set(inspector.get_table_names())
        assert "audit_events" in tables
        assert "documents" in tables
        assert "upload_sessions" in tables
        assert "workspaces" in tables
        assert "users" in tables
    finally:
        test_engine.dispose()

    # 3. Revertir todas las migraciones (base)
    command.downgrade(alembic_cfg, "base")

    # 4. Verificar que se revirtieron correctamente
    test_engine = create_engine(temp_sqlite_url)
    try:
        inspector = inspect(test_engine)
        remaining_tables = set(inspector.get_table_names())
        assert "audit_events" not in remaining_tables
        assert "documents" not in remaining_tables
    finally:
        test_engine.dispose()
