"""Pruebas unitarias para el dominio de Documentos (CDM-27 / AGENTS.md §10).

Verifica entidades puras, invariantes de creación y transiciones de ciclo de vida.
"""

from uuid import uuid4

import pytest

from cdm.domain.document import Document, DocumentStatus
from cdm.domain.errors import InvalidDocumentDataError


def test_document_creation_valid():
    """Crea un documento con valores válidos y estado inicial PENDING_UPLOAD."""
    ws_id = uuid4()
    user_id = uuid4()
    doc = Document.create(
        workspace_id=ws_id,
        uploaded_by=user_id,
        original_filename="contrato.pdf",
        storage_key=f"workspaces/{ws_id}/contrato.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        checksum_sha256="a" * 64,
        technical_metadata={"pages": 3},
    )

    assert doc.workspace_id == ws_id
    assert doc.uploaded_by == user_id
    assert doc.original_filename == "contrato.pdf"
    assert doc.status == DocumentStatus.PENDING_UPLOAD
    assert not doc.is_deleted
    assert doc.technical_metadata == {"pages": 3}


def test_document_creation_invalid_invariants():
    """Rechaza documentos con datos vacíos o tamaño negativo."""
    ws_id = uuid4()
    user_id = uuid4()

    with pytest.raises(InvalidDocumentDataError):
        Document.create(ws_id, user_id, "", "key", "application/pdf", 100)

    with pytest.raises(InvalidDocumentDataError):
        Document.create(ws_id, user_id, "file.pdf", "", "application/pdf", 100)

    with pytest.raises(InvalidDocumentDataError):
        Document.create(ws_id, user_id, "file.pdf", "key", "", 100)

    with pytest.raises(InvalidDocumentDataError):
        Document.create(ws_id, user_id, "file.pdf", "key", "application/pdf", -1)


def test_document_status_transitions():
    """Realiza transiciones de estado válidas y rechaza transiciones sobre documentos eliminados."""
    doc = Document.create(
        workspace_id=uuid4(),
        uploaded_by=uuid4(),
        original_filename="doc.pdf",
        storage_key="key",
        content_type="application/pdf",
        size_bytes=100,
    )

    uploaded = doc.transition_to(DocumentStatus.UPLOADED)
    assert uploaded.status == DocumentStatus.UPLOADED

    processing = uploaded.transition_to(DocumentStatus.PROCESSING)
    assert processing.status == DocumentStatus.PROCESSING

    ready = processing.transition_to(DocumentStatus.READY)
    assert ready.status == DocumentStatus.READY

    deleted = ready.mark_deleted()
    assert deleted.is_deleted
    assert deleted.status == DocumentStatus.DELETED
    assert deleted.deleted_at is not None

    with pytest.raises(InvalidDocumentDataError):
        deleted.transition_to(DocumentStatus.READY)
