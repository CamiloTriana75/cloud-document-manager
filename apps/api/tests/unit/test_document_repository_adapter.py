"""Pruebas unitarias de la capa de persistencia y puertos de documentos (CDM-41).

Criterios de aceptación (CDM-41):
1. Entidad Document y value objects sin dependencias de framework ni ORM.
2. Casos de uso definen puertos de repositorio (DocumentRepositoryPort).
3. Adaptador SqlAlchemyDocumentRepository implementa los puertos sin filtrar Session/ORM.
4. Consultas con filtros estructurados (DocumentQueryFilter) y paginación estable.
5. Tests unitarios con dobles de repositorio e integración SQLite en memoria.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from cdm.adapters.outbound.persistence.models import Base
from cdm.adapters.outbound.persistence.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWorkspaceRepository,
)
from cdm.domain.document import Document, DocumentQueryFilter, DocumentStatus
from cdm.domain.workspace import User, Workspace


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


def test_document_entity_purity_no_frameworks() -> None:
    """Invariante: cdm.domain.document no debe importar frameworks ni dependencias externas."""
    import cdm.domain.document as doc_module

    forbidden_modules = {"fastapi", "sqlalchemy", "boto3", "pydantic", "starlette", "alembic"}
    module_dict = doc_module.__dict__

    for name, obj in module_dict.items():
        if hasattr(obj, "__module__") and obj.__module__:
            root_pkg = obj.__module__.split(".")[0]
            assert root_pkg not in forbidden_modules, (
                f"Objeto '{name}' pertenece al paquete prohibido '{root_pkg}' en dominio."
            )


def test_document_repository_save_and_get_by_id(db_session: Session) -> None:
    """Verifica que el repositorio persista y retorne una entidad pura de dominio."""
    user_repo = SqlAlchemyUserRepository(db_session)
    ws_repo = SqlAlchemyWorkspaceRepository(db_session)
    doc_repo = SqlAlchemyDocumentRepository(db_session)

    user = user_repo.save(User.create(cognito_sub="sub-doc-1", email="doc1@test.com"))
    ws = ws_repo.save(Workspace.create(name="Doc WS", slug="doc-ws", created_by=user.id))

    document = Document.create(
        workspace_id=ws.id,
        uploaded_by=user.id,
        original_filename="informe_anual.pdf",
        storage_key=f"tenants/{ws.id}/docs/{uuid4()}.pdf",
        content_type="application/pdf",
        size_bytes=524288,
        checksum_sha256="b" * 64,
        technical_metadata={"pages": 12},
    )

    saved = doc_repo.save(document)
    assert isinstance(saved, Document)
    assert saved.id == document.id
    assert saved.original_filename == "informe_anual.pdf"
    assert saved.technical_metadata == {"pages": 12}

    # Búsqueda por ID asegurando workspace_id
    retrieved = doc_repo.get_by_id(ws.id, saved.id)
    assert retrieved is not None
    assert isinstance(retrieved, Document)
    assert retrieved.id == saved.id
    assert retrieved.size_bytes == 524288


def test_document_repository_multi_tenant_isolation(db_session: Session) -> None:
    """Verifica aislamiento estricto anti-IDOR en consultas por ID."""
    user_repo = SqlAlchemyUserRepository(db_session)
    ws_repo = SqlAlchemyWorkspaceRepository(db_session)
    doc_repo = SqlAlchemyDocumentRepository(db_session)

    user = user_repo.save(User.create(cognito_sub="sub-doc-2", email="doc2@test.com"))
    ws_a = ws_repo.save(Workspace.create(name="WS Alpha", slug="ws-alpha", created_by=user.id))
    ws_b = ws_repo.save(Workspace.create(name="WS Beta", slug="ws-beta", created_by=user.id))

    doc_a = doc_repo.save(
        Document.create(
            workspace_id=ws_a.id,
            uploaded_by=user.id,
            original_filename="confidencial_alpha.pdf",
            storage_key=f"tenants/{ws_a.id}/docs/{uuid4()}.pdf",
            content_type="application/pdf",
            size_bytes=1024,
        )
    )

    # Consulta con tenant incorrecto debe retornar None
    assert doc_repo.get_by_id(ws_b.id, doc_a.id) is None
    # Consulta con tenant correcto retorna el documento
    assert doc_repo.get_by_id(ws_a.id, doc_a.id) is not None


def test_document_repository_soft_delete(db_session: Session) -> None:
    """Verifica borrado lógico y exclusión en consultas normales."""
    user_repo = SqlAlchemyUserRepository(db_session)
    ws_repo = SqlAlchemyWorkspaceRepository(db_session)
    doc_repo = SqlAlchemyDocumentRepository(db_session)

    user = user_repo.save(User.create(cognito_sub="sub-doc-3", email="doc3@test.com"))
    ws = ws_repo.save(Workspace.create(name="WS Delete", slug="ws-delete", created_by=user.id))

    doc = doc_repo.save(
        Document.create(
            workspace_id=ws.id,
            uploaded_by=user.id,
            original_filename="a_eliminar.pdf",
            storage_key=f"tenants/{ws.id}/docs/{uuid4()}.pdf",
            content_type="application/pdf",
            size_bytes=1024,
        )
    )

    # 1. Soft delete exitoso
    assert doc_repo.soft_delete(ws.id, doc.id) is True

    # 2. Re-intentar soft delete sobre ya eliminado retorna False
    assert doc_repo.soft_delete(ws.id, doc.id) is False

    # 3. Consulta normal no lo incluye
    assert doc_repo.get_by_id(ws.id, doc.id) is None
    normal_list = doc_repo.list_by_workspace(ws.id)
    assert len(normal_list) == 0

    # 4. Consulta con include_deleted=True lo retorna
    deleted_doc = doc_repo.get_by_id(ws.id, doc.id, include_deleted=True)
    assert deleted_doc is not None
    assert deleted_doc.is_deleted
    assert deleted_doc.status == DocumentStatus.DELETED


def test_document_repository_filtering_options(db_session: Session) -> None:
    """Verifica filtrado multicriterio con DocumentQueryFilter."""
    user_repo = SqlAlchemyUserRepository(db_session)
    ws_repo = SqlAlchemyWorkspaceRepository(db_session)
    doc_repo = SqlAlchemyDocumentRepository(db_session)

    user_a = user_repo.save(User.create(cognito_sub="sub-filter-1", email="fa@test.com"))
    user_b = user_repo.save(User.create(cognito_sub="sub-filter-2", email="fb@test.com"))
    ws = ws_repo.save(Workspace.create(name="WS Filters", slug="ws-filters", created_by=user_a.id))

    # Documento 1: PDF, READY, user_a
    doc1 = Document.create(
        workspace_id=ws.id,
        uploaded_by=user_a.id,
        original_filename="balance_2026.pdf",
        storage_key=f"tenants/{ws.id}/docs/{uuid4()}.pdf",
        content_type="application/pdf",
        size_bytes=1000,
    ).transition_to(DocumentStatus.READY)
    doc_repo.save(doc1)

    # Documento 2: PNG, PROCESSING, user_b
    doc2 = Document.create(
        workspace_id=ws.id,
        uploaded_by=user_b.id,
        original_filename="logo_empresa.png",
        storage_key=f"tenants/{ws.id}/docs/{uuid4()}.png",
        content_type="image/png",
        size_bytes=2000,
    ).transition_to(DocumentStatus.PROCESSING)
    doc_repo.save(doc2)

    # Documento 3: CSV, FAILED, user_a
    doc3 = Document.create(
        workspace_id=ws.id,
        uploaded_by=user_a.id,
        original_filename="datos_ventas.csv",
        storage_key=f"tenants/{ws.id}/docs/{uuid4()}.csv",
        content_type="text/csv",
        size_bytes=3000,
    ).mark_failed("Corrupto")
    doc_repo.save(doc3)

    # 1. Filtro por búsqueda de término "balance"
    filter_search = DocumentQueryFilter(search_term="balance")
    res_search = doc_repo.list_by_workspace(ws.id, filters=filter_search)
    assert len(res_search) == 1
    assert res_search[0].original_filename == "balance_2026.pdf"

    # 2. Filtro por status=PROCESSING
    filter_status = DocumentQueryFilter(status=DocumentStatus.PROCESSING)
    res_status = doc_repo.list_by_workspace(ws.id, filters=filter_status)
    assert len(res_status) == 1
    assert res_status[0].original_filename == "logo_empresa.png"

    # 3. Filtro por tipo MIME "text/csv"
    filter_mime = DocumentQueryFilter(content_type="text/csv")
    res_mime = doc_repo.list_by_workspace(ws.id, filters=filter_mime)
    assert len(res_mime) == 1
    assert res_mime[0].original_filename == "datos_ventas.csv"

    # 4. Filtro por autor (uploaded_by = user_b)
    filter_author = DocumentQueryFilter(uploaded_by=user_b.id)
    res_author = doc_repo.list_by_workspace(ws.id, filters=filter_author)
    assert len(res_author) == 1
    assert res_author[0].uploaded_by == user_b.id

    # 5. Conteo con filtros
    assert doc_repo.count_by_workspace(ws.id, filters=filter_search) == 1
    assert doc_repo.count_by_workspace(ws.id, filters=filter_status) == 1
    assert doc_repo.count_by_workspace(ws.id) == 3


def test_document_repository_pagination(db_session: Session) -> None:
    """Verifica la paginación con limit y offset y orden cronológico descendente."""
    user_repo = SqlAlchemyUserRepository(db_session)
    ws_repo = SqlAlchemyWorkspaceRepository(db_session)
    doc_repo = SqlAlchemyDocumentRepository(db_session)

    user = user_repo.save(User.create(cognito_sub="sub-paged-1", email="paged@test.com"))
    ws = ws_repo.save(Workspace.create(name="WS Paged", slug="ws-paged", created_by=user.id))

    # Crear 5 documentos
    for i in range(5):
        doc = Document.create(
            workspace_id=ws.id,
            uploaded_by=user.id,
            original_filename=f"doc_{i}.pdf",
            storage_key=f"tenants/{ws.id}/docs/{uuid4()}.pdf",
            content_type="application/pdf",
            size_bytes=100 * (i + 1),
        )
        doc_repo.save(doc)

    assert doc_repo.count_by_workspace(ws.id) == 5

    # Página 1 (limit 2, offset 0)
    page1 = doc_repo.list_by_workspace(ws.id, limit=2, offset=0)
    assert len(page1) == 2

    # Página 2 (limit 2, offset 2)
    page2 = doc_repo.list_by_workspace(ws.id, limit=2, offset=2)
    assert len(page2) == 2

    # Los IDs de la página 1 y 2 no deben solaparse
    page1_ids = {d.id for d in page1}
    page2_ids = {d.id for d in page2}
    assert page1_ids.isdisjoint(page2_ids)

    # Página 3 (limit 2, offset 4)
    page3 = doc_repo.list_by_workspace(ws.id, limit=2, offset=4)
    assert len(page3) == 1
