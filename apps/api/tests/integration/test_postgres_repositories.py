"""Pruebas de integración de repositorios SQLAlchemy contra PostgreSQL 16 real (ADR-0003 / CDM-49).

Verifica:
1. Persistencia y restricciones reales de PostgreSQL (Foreign Keys, Unique Constraints, JSONB).
2. Aislamiento estricto multi-tenant a nivel de base de datos.
3. Búsquedas con ILIKE, tipos MIME y paginación en SQL.
4. Borrado lógico con soft_delete() y control de deleted_at.
5. Sesiones de subida y eventos de auditoría inmutables.
Cada prueba corre dentro de una transacción aislada con rollback automático al finalizar.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cdm.adapters.outbound.persistence.repositories import (
    SqlAlchemyAuditRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyMembershipRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWorkspaceRepository,
)
from cdm.adapters.outbound.persistence.sql_upload_session_repository import (
    SqlAlchemyUploadSessionRepository,
)
from cdm.domain.audit import AuditAction, AuditEvent, ResourceType
from cdm.domain.document import DocumentQueryFilter, DocumentStatus
from cdm.domain.upload_session import UploadSessionStatus
from cdm.domain.workspace import (
    User,
    WorkspaceRole,
)


def test_user_persistence_in_postgres(postgres_session: Session, user_factory: Any) -> None:
    """Verifica el ciclo de vida de persistencia de usuarios en PostgreSQL."""
    user_repo = SqlAlchemyUserRepository(postgres_session)
    user = user_factory(email="postgres-user@example.com", display_name="PG User")

    # Guardar
    saved = user_repo.save(user)
    assert saved.id == user.id
    assert saved.email == "postgres-user@example.com"

    # Buscar por ID
    found_by_id = user_repo.get_by_id(user.id)
    assert found_by_id is not None
    assert found_by_id.email == "postgres-user@example.com"

    # Buscar por Cognito Sub
    found_by_sub = user_repo.get_by_cognito_sub(user.cognito_sub)
    assert found_by_sub is not None
    assert found_by_sub.id == user.id

    # Buscar por Email normalizado
    found_by_email = user_repo.get_by_email("  POSTGRES-USER@example.com  ")
    assert found_by_email is not None
    assert found_by_email.id == user.id

    # Actualizar
    updated_user = User(
        id=user.id,
        cognito_sub=user.cognito_sub,
        email="updated-pg@example.com",
        display_name="PG User Updated",
        created_at=user.created_at,
        updated_at=datetime.now(UTC),
    )
    user_repo.save(updated_user)
    refreshed = user_repo.get_by_id(user.id)
    assert refreshed is not None
    assert refreshed.email == "updated-pg@example.com"
    assert refreshed.display_name == "PG User Updated"


def test_workspace_persistence_and_slug_uniqueness(
    postgres_session: Session, user_factory: Any, workspace_factory: Any
) -> None:
    """Verifica persistencia de workspaces y constraint única de slug en PostgreSQL."""
    user_repo = SqlAlchemyUserRepository(postgres_session)
    ws_repo = SqlAlchemyWorkspaceRepository(postgres_session)

    user = user_repo.save(user_factory())
    ws1 = ws_repo.save(workspace_factory(created_by=user.id, slug="acme-engineering"))

    assert ws1.slug == "acme-engineering"

    # Buscar por slug
    found = ws_repo.get_by_slug("acme-engineering")
    assert found is not None
    assert found.id == ws1.id

    # Intentar guardar otro workspace con el mismo slug debe violar UniqueConstraint
    ws2 = workspace_factory(created_by=user.id, slug="acme-engineering")
    with pytest.raises(IntegrityError):
        ws_repo.save(ws2)


def test_workspace_membership_unique_constraint(
    postgres_session: Session, user_factory: Any, workspace_factory: Any, membership_factory: Any
) -> None:
    """Verifica que un usuario no pueda tener memberships duplicadas en el mismo workspace."""
    user_repo = SqlAlchemyUserRepository(postgres_session)
    ws_repo = SqlAlchemyWorkspaceRepository(postgres_session)
    mem_repo = SqlAlchemyMembershipRepository(postgres_session)

    user = user_repo.save(user_factory())
    ws = ws_repo.save(workspace_factory(created_by=user.id))

    # Guardar membresía OWNER
    mem = mem_repo.save(
        membership_factory(
            workspace_id=ws.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
    )
    assert mem.role == WorkspaceRole.OWNER

    # Búsqueda por workspace y user
    found = mem_repo.get_by_workspace_and_user(ws.id, user.id)
    assert found is not None
    assert found.role == WorkspaceRole.OWNER

    # Listar por user_id
    user_memberships = mem_repo.list_by_user_id(user.id)
    assert len(user_memberships) == 1
    assert user_memberships[0].workspace_id == ws.id

    # Intentar guardar una segunda membresía con diferente ID pero misma tupla (workspace, user)
    duplicate_mem = membership_factory(
        workspace_id=ws.id,
        user_id=user.id,
        role=WorkspaceRole.MEMBER,
    )
    with pytest.raises(IntegrityError):
        mem_repo.save(duplicate_mem)


def test_document_multi_tenant_isolation_in_postgres(
    postgres_session: Session,
    user_factory: Any,
    workspace_factory: Any,
    document_factory: Any,
) -> None:
    """Verifica aislamiento estricto multi-tenant: consultas nunca cruzan datos entre workspaces."""
    user_repo = SqlAlchemyUserRepository(postgres_session)
    ws_repo = SqlAlchemyWorkspaceRepository(postgres_session)
    doc_repo = SqlAlchemyDocumentRepository(postgres_session)

    user = user_repo.save(user_factory())
    ws_alpha = ws_repo.save(workspace_factory(created_by=user.id, slug="alpha-corp"))
    ws_beta = ws_repo.save(workspace_factory(created_by=user.id, slug="beta-inc"))

    # Crear documento en Alpha
    doc_alpha = doc_repo.save(
        document_factory(
            workspace_id=ws_alpha.id,
            uploaded_by=user.id,
            original_filename="confidential_alpha.pdf",
            storage_key=f"tenants/{ws_alpha.id}/documents/{uuid4()}/confidential_alpha.pdf",
        )
    )

    # Crear documento en Beta
    doc_beta = doc_repo.save(
        document_factory(
            workspace_id=ws_beta.id,
            uploaded_by=user.id,
            original_filename="financial_beta.pdf",
            storage_key=f"tenants/{ws_beta.id}/documents/{uuid4()}/financial_beta.pdf",
        )
    )

    # Consulta directa de doc_alpha usando el workspace_id de Beta debe retornar None
    leaked_doc = doc_repo.get_by_id(workspace_id=ws_beta.id, document_id=doc_alpha.id)
    assert leaked_doc is None, "Vulnerabilidad IDOR: doc de Alpha retornado bajo Beta"

    # Consulta de doc_beta usando el workspace_id de Alpha debe retornar None
    leaked_doc2 = doc_repo.get_by_id(workspace_id=ws_alpha.id, document_id=doc_beta.id)
    assert leaked_doc2 is None

    # Listados por workspace deben estar 100% aislados
    alpha_docs = doc_repo.list_by_workspace(workspace_id=ws_alpha.id)
    alpha_total = doc_repo.count_by_workspace(workspace_id=ws_alpha.id)
    assert alpha_total == 1
    assert len(alpha_docs) == 1
    assert alpha_docs[0].id == doc_alpha.id

    beta_docs = doc_repo.list_by_workspace(workspace_id=ws_beta.id)
    beta_total = doc_repo.count_by_workspace(workspace_id=ws_beta.id)
    assert beta_total == 1
    assert len(beta_docs) == 1
    assert beta_docs[0].id == doc_beta.id


def test_document_rich_jsonb_technical_metadata(
    postgres_session: Session,
    user_factory: Any,
    workspace_factory: Any,
    document_factory: Any,
) -> None:
    """Verifica que metadatos técnicos estructurados se persisten en PostgreSQL JSONB."""
    user_repo = SqlAlchemyUserRepository(postgres_session)
    ws_repo = SqlAlchemyWorkspaceRepository(postgres_session)
    doc_repo = SqlAlchemyDocumentRepository(postgres_session)

    user = user_repo.save(user_factory())
    ws = ws_repo.save(workspace_factory(created_by=user.id))

    complex_metadata = {
        "page_count": 42,
        "pdf_version": "1.7",
        "has_text": True,
        "author": "Equipo de Finanzas",
        "keywords": ["anual", "q3", "auditoria"],
        "checksum_verified": True,
        "layers": {
            "embedded_images": 4,
            "fonts": ["Helvetica-Bold", "Times-Roman"],
        },
    }

    doc = document_factory(
        workspace_id=ws.id,
        uploaded_by=user.id,
        technical_metadata=complex_metadata,
        checksum_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    saved = doc_repo.save(doc)

    retrieved = doc_repo.get_by_id(workspace_id=ws.id, document_id=saved.id)
    assert retrieved is not None
    assert retrieved.technical_metadata == complex_metadata
    assert retrieved.technical_metadata["layers"]["fonts"] == ["Helvetica-Bold", "Times-Roman"]
    assert retrieved.checksum_sha256 == doc.checksum_sha256


def test_document_filtering_and_pagination(
    postgres_session: Session,
    user_factory: Any,
    workspace_factory: Any,
    document_factory: Any,
) -> None:
    """Verifica filtros de búsqueda ILIKE, tipos MIME y paginación en PostgreSQL."""
    user_repo = SqlAlchemyUserRepository(postgres_session)
    ws_repo = SqlAlchemyWorkspaceRepository(postgres_session)
    doc_repo = SqlAlchemyDocumentRepository(postgres_session)

    user = user_repo.save(user_factory())
    ws = ws_repo.save(workspace_factory(created_by=user.id))

    # Crear un set diverso de documentos
    doc_repo.save(
        document_factory(
            workspace_id=ws.id,
            uploaded_by=user.id,
            original_filename="reporte_ventas_2025.pdf",
            content_type="application/pdf",
            status=DocumentStatus.READY,
            size_bytes=1000,
        )
    )
    doc_repo.save(
        document_factory(
            workspace_id=ws.id,
            uploaded_by=user.id,
            original_filename="informe_financiero_2026.pdf",
            content_type="application/pdf",
            status=DocumentStatus.READY,
            size_bytes=2000,
        )
    )
    doc_repo.save(
        document_factory(
            workspace_id=ws.id,
            uploaded_by=user.id,
            original_filename="logo_corporativo.png",
            content_type="image/png",
            status=DocumentStatus.PROCESSING,
            size_bytes=3000,
        )
    )
    doc_repo.save(
        document_factory(
            workspace_id=ws.id,
            uploaded_by=user.id,
            original_filename="datos_inventario.csv",
            content_type="text/csv",
            status=DocumentStatus.FAILED,
            size_bytes=500,
        )
    )

    # 1. Búsqueda por término parcial (ILIKE insensible a mayúsculas/minúsculas)
    filter_search = DocumentQueryFilter(search_term="REPORTE")
    docs = doc_repo.list_by_workspace(workspace_id=ws.id, filters=filter_search)
    total = doc_repo.count_by_workspace(workspace_id=ws.id, filters=filter_search)
    assert total == 1
    assert len(docs) == 1
    assert docs[0].original_filename == "reporte_ventas_2025.pdf"

    # 2. Filtro por tipo MIME
    filter_pdf = DocumentQueryFilter(content_type="application/pdf")
    pdf_docs = doc_repo.list_by_workspace(workspace_id=ws.id, filters=filter_pdf)
    pdf_total = doc_repo.count_by_workspace(workspace_id=ws.id, filters=filter_pdf)
    assert pdf_total == 2
    assert len(pdf_docs) == 2
    assert all(d.content_type == "application/pdf" for d in pdf_docs)

    # 3. Filtro por estado
    filter_proc = DocumentQueryFilter(status=DocumentStatus.PROCESSING)
    proc_docs = doc_repo.list_by_workspace(workspace_id=ws.id, filters=filter_proc)
    proc_total = doc_repo.count_by_workspace(workspace_id=ws.id, filters=filter_proc)
    assert proc_total == 1
    assert len(proc_docs) == 1
    assert proc_docs[0].original_filename == "logo_corporativo.png"

    # 4. Paginación: limit=2, offset=0 y luego offset=2
    p1_docs = doc_repo.list_by_workspace(workspace_id=ws.id, limit=2, offset=0)
    total_all = doc_repo.count_by_workspace(workspace_id=ws.id)
    assert total_all == 4
    assert len(p1_docs) == 2

    p2_docs = doc_repo.list_by_workspace(workspace_id=ws.id, limit=2, offset=2)
    assert len(p2_docs) == 2
    # Las páginas no deben solaparse
    assert {d.id for d in p1_docs}.isdisjoint({d.id for d in p2_docs})


def test_document_soft_delete_lifecycle(
    postgres_session: Session,
    user_factory: Any,
    workspace_factory: Any,
    document_factory: Any,
) -> None:
    """Verifica que soft_delete() oculta el documento de consultas estándar."""
    user_repo = SqlAlchemyUserRepository(postgres_session)
    ws_repo = SqlAlchemyWorkspaceRepository(postgres_session)
    doc_repo = SqlAlchemyDocumentRepository(postgres_session)

    user = user_repo.save(user_factory())
    ws = ws_repo.save(workspace_factory(created_by=user.id))

    doc = doc_repo.save(
        document_factory(
            workspace_id=ws.id,
            uploaded_by=user.id,
            status=DocumentStatus.READY,
        )
    )

    # Ejecutar borrado lógico
    deleted_ok = doc_repo.soft_delete(
        workspace_id=ws.id,
        document_id=doc.id,
        deleted_by=user.id,
    )
    assert deleted_ok is True

    # Consulta estándar no debe devolverlo
    active = doc_repo.get_by_id(workspace_id=ws.id, document_id=doc.id)
    assert active is None

    # Listado estándar no debe devolverlo
    docs = doc_repo.list_by_workspace(workspace_id=ws.id)
    total = doc_repo.count_by_workspace(workspace_id=ws.id)
    assert total == 0
    assert len(docs) == 0

    # Consulta con include_deleted=True sí debe encontrarlo
    deleted = doc_repo.get_by_id(workspace_id=ws.id, document_id=doc.id, include_deleted=True)
    assert deleted is not None
    assert deleted.status == DocumentStatus.DELETED
    assert deleted.deleted_at is not None
    assert deleted.technical_metadata.get("deleted_by") == str(user.id)


def test_upload_session_persistence_and_expiration(
    postgres_session: Session,
    user_factory: Any,
    workspace_factory: Any,
    document_factory: Any,
    upload_session_factory: Any,
) -> None:
    """Verifica persistencia y listado de expiración de sesiones de carga en PostgreSQL."""
    user_repo = SqlAlchemyUserRepository(postgres_session)
    ws_repo = SqlAlchemyWorkspaceRepository(postgres_session)
    doc_repo = SqlAlchemyDocumentRepository(postgres_session)
    upload_repo = SqlAlchemyUploadSessionRepository(postgres_session)

    user = user_repo.save(user_factory())
    ws = ws_repo.save(workspace_factory(created_by=user.id))
    doc = doc_repo.save(document_factory(workspace_id=ws.id, uploaded_by=user.id))

    # Sesión activa (expira en el futuro)
    future_session = upload_session_factory(
        workspace_id=ws.id,
        user_id=user.id,
        document_id=doc.id,
        status=UploadSessionStatus.PENDING,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    upload_repo.save(future_session)

    # Sesión expirada (expiró hace 10 minutos)
    doc_expired = doc_repo.save(document_factory(workspace_id=ws.id, uploaded_by=user.id))
    expired_session = upload_session_factory(
        workspace_id=ws.id,
        user_id=user.id,
        document_id=doc_expired.id,
        status=UploadSessionStatus.PENDING,
        expires_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    upload_repo.save(expired_session)

    # Búsqueda por ID y workspace_id
    found = upload_repo.get_by_id(future_session.id, ws.id)
    assert found is not None
    assert found.document_id == doc.id

    # Aislamiento: no se encuentra bajo otro workspace
    assert upload_repo.get_by_id(future_session.id, uuid4()) is None

    # Listar sesiones expiradas
    expired_list = upload_repo.list_expired(workspace_id=ws.id)
    expired_ids = {s.id for s in expired_list}
    assert expired_session.id in expired_ids
    assert future_session.id not in expired_ids


def test_audit_event_repository_in_postgres(
    postgres_session: Session,
    user_factory: Any,
    workspace_factory: Any,
) -> None:
    """Verifica el registro inmutable de eventos de auditoría en PostgreSQL."""
    user_repo = SqlAlchemyUserRepository(postgres_session)
    ws_repo = SqlAlchemyWorkspaceRepository(postgres_session)
    audit_repo = SqlAlchemyAuditRepository(postgres_session)

    user = user_repo.save(user_factory())
    ws = ws_repo.save(workspace_factory(created_by=user.id))
    doc_id = uuid4()

    event1 = AuditEvent(
        id=uuid4(),
        workspace_id=ws.id,
        actor_user_id=user.id,
        action=AuditAction.DOCUMENT_CREATED,
        resource_type=ResourceType.DOCUMENT,
        resource_id=doc_id,
        details={"filename": "auditoria_legal.pdf", "size": 1024},
        ip_address="127.0.0.1",
        created_at=datetime.now(UTC),
    )
    audit_repo.save(event1)

    event2 = AuditEvent(
        id=uuid4(),
        workspace_id=ws.id,
        actor_user_id=user.id,
        action=AuditAction.DOCUMENT_DELETED,
        resource_type=ResourceType.DOCUMENT,
        resource_id=doc_id,
        details={"reason": "Solicitud legal"},
        ip_address="127.0.0.1",
        created_at=datetime.now(UTC),
    )
    audit_repo.save(event2)

    # Listar eventos del workspace
    events = audit_repo.list_by_workspace(ws.id)
    total = audit_repo.count_by_workspace(ws.id)
    assert total >= 2
    assert len(events) >= 2
    actions = [e.action for e in events]
    assert AuditAction.DOCUMENT_CREATED in actions
    assert AuditAction.DOCUMENT_DELETED in actions
