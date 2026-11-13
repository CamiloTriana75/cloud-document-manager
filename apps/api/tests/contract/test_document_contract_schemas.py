"""Pruebas de contrato de esquemas y DTOs de documentos (CDM-49 / AGENTS.md §11).

Verifica la serialización exacta de los contratos HTTP y sus envelopes para:
1. DocumentResponse y EnvelopeDocument.
2. EnvelopeDocumentList con metadatos de paginación.
3. UploadSessionResponse y EnvelopeUploadSession.
4. DownloadUrlResponse y EnvelopeDownloadUrl.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from cdm.adapters.inbound.http.documents import (
    DocumentResponse,
    DownloadUrlResponse,
    EnvelopeDocument,
    EnvelopeDocumentList,
    EnvelopeDownloadUrl,
)
from cdm.adapters.inbound.http.pagination import PaginationMeta
from cdm.adapters.inbound.http.upload_sessions import (
    EnvelopeUploadSession,
    UploadSessionResponse,
)
from cdm.domain.document import DocumentStatus


def test_document_response_contract_schema() -> None:
    """Verifica que DocumentResponse serializa todos los campos obligatorios del contrato."""
    doc_id = uuid4()
    ws_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    model = DocumentResponse(
        id=doc_id,
        workspace_id=ws_id,
        uploaded_by=user_id,
        original_filename="informe_anual.pdf",
        storage_key=f"tenants/{ws_id}/documents/{doc_id}/informe_anual.pdf",
        content_type="application/pdf",
        size_bytes=1048576,
        checksum_sha256="abc123sha256",
        status=DocumentStatus.READY,
        technical_metadata={"page_count": 12},
        created_at=now,
        updated_at=now,
        failure_reason=None,
        retry_count=0,
    )

    envelope = EnvelopeDocument(data=model)
    serialized = envelope.model_dump(mode="json")

    assert "data" in serialized
    data = serialized["data"]
    assert data["id"] == str(doc_id)
    assert data["workspace_id"] == str(ws_id)
    assert data["uploaded_by"] == str(user_id)
    assert data["original_filename"] == "informe_anual.pdf"
    assert data["content_type"] == "application/pdf"
    assert data["size_bytes"] == 1048576
    assert data["status"] == "READY"
    assert data["technical_metadata"]["page_count"] == 12
    assert "created_at" in data
    assert "updated_at" in data


def test_document_list_envelope_contract_schema() -> None:
    """Verifica que EnvelopeDocumentList serializa la lista de items y el objeto pagination."""
    doc_id = uuid4()
    ws_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    item = DocumentResponse(
        id=doc_id,
        workspace_id=ws_id,
        uploaded_by=user_id,
        original_filename="doc.pdf",
        storage_key=None,
        content_type="application/pdf",
        size_bytes=512,
        checksum_sha256=None,
        status=DocumentStatus.READY,
        technical_metadata={},
        created_at=now,
        updated_at=now,
        failure_reason=None,
        retry_count=0,
    )

    pagination = PaginationMeta(
        total=1,
        limit=10,
        offset=0,
        has_more=False,
    )

    list_response = EnvelopeDocumentList(
        data=[item],
        pagination=pagination,
    )

    serialized = list_response.model_dump(mode="json")
    assert "data" in serialized
    assert "pagination" in serialized
    assert len(serialized["data"]) == 1
    assert serialized["pagination"]["total"] == 1
    assert serialized["pagination"]["limit"] == 10
    assert serialized["pagination"]["offset"] == 0
    assert serialized["pagination"]["has_more"] is False


def test_upload_session_response_contract_schema() -> None:
    """Verifica que UploadSessionResponse expone la URL prefirmada y cabeceras exactas."""
    session_id = uuid4()
    doc_id = uuid4()
    now = datetime.now(UTC)

    model = UploadSessionResponse(
        upload_session_id=session_id,
        document_id=doc_id,
        upload_url="https://s3.amazonaws.com/test-bucket/tenants/ws/doc/upload?signature=abc",
        storage_key="tenants/ws/doc/upload.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        checksum_sha256=None,
        expires_at=now,
        expires_in_seconds=900,
        required_headers={"Content-Type": "application/pdf"},
    )

    envelope = EnvelopeUploadSession(data=model)
    serialized = envelope.model_dump(mode="json")

    assert "data" in serialized
    data = serialized["data"]
    assert data["upload_session_id"] == str(session_id)
    assert data["document_id"] == str(doc_id)
    assert data["upload_url"].startswith("https://")
    assert data["required_headers"] == {"Content-Type": "application/pdf"}
    assert data["expires_in_seconds"] == 900


def test_download_url_response_contract_schema() -> None:
    """Verifica que EnvelopeDownloadUrl contiene document_id, original_filename y download_url."""
    doc_id = uuid4()
    model = DownloadUrlResponse(
        document_id=doc_id,
        original_filename="informe.pdf",
        download_url="https://s3.amazonaws.com/test-bucket/tenants/ws/doc/download?signature=xyz",
        expires_in_seconds=900,
    )

    envelope = EnvelopeDownloadUrl(data=model)
    serialized = envelope.model_dump(mode="json")

    assert "data" in serialized
    data = serialized["data"]
    assert data["document_id"] == str(doc_id)
    assert data["original_filename"] == "informe.pdf"
    assert data["download_url"].startswith("https://")
    assert data["expires_in_seconds"] == 900
