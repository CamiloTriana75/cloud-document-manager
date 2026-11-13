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


def test_document_failed_transition_and_sanitized_reason():
    """Documento en FAILED guarda razón sanitizada y no expone stack traces (CDM-37)."""
    doc = Document.create(
        workspace_id=uuid4(),
        uploaded_by=uuid4(),
        original_filename="corrupted.pdf",
        storage_key="key",
        content_type="application/pdf",
        size_bytes=100,
    )

    failed = doc.mark_failed(
        "Traceback (most recent call last):\n  File 'x.py', line 12\nKeyError: 'raw'"
    )
    assert failed.status == DocumentStatus.FAILED
    # Solo conserva la primera línea segura truncada (sin volcado de traza)
    assert failed.failure_reason == "Traceback (most recent call last):"
    assert "failed_at" in failed.technical_metadata

    # Reintento controlado: transiciona de FAILED a PROCESSING incrementando retry_count
    retried = failed.retry_processing()
    assert retried.status == DocumentStatus.PROCESSING
    assert retried.failure_reason is None
    assert retried.technical_metadata.get("retry_count") == 1
    assert "last_retry_at" in retried.technical_metadata


def test_document_forbidden_backward_transitions():
    """Valida que transiciones retrógradas prohibidas arrojen error (CDM-37)."""
    doc = Document.create(
        workspace_id=uuid4(),
        uploaded_by=uuid4(),
        original_filename="doc.pdf",
        storage_key="key",
        content_type="application/pdf",
        size_bytes=100,
    )

    uploaded = doc.transition_to(DocumentStatus.UPLOADED)
    processing = uploaded.transition_to(DocumentStatus.PROCESSING)
    ready = processing.transition_to(DocumentStatus.READY)

    # READY no puede retroceder a UPLOADED ni a PROCESSING
    with pytest.raises(InvalidDocumentDataError):
        ready.transition_to(DocumentStatus.PROCESSING)

    with pytest.raises(InvalidDocumentDataError):
        ready.transition_to(DocumentStatus.UPLOADED)

    # FAILED no puede retroceder a PENDING_UPLOAD
    failed = processing.mark_failed("Error")
    with pytest.raises(InvalidDocumentDataError):
        failed.transition_to(DocumentStatus.PENDING_UPLOAD)
