"""Pruebas unitarias para la inspección de contenido y metadatos técnicos (CDM-38).

Valida los criterios de aceptación:
1. Registra tamaño real, MIME detectado, extensión normalizada, checksum y timestamps.
2. Detecta discrepancias entre MIME declarado y contenido real (anti-spoofing).
3. Maneja archivos corruptos o ejecutables no admitidos como FAILED sin exponer stack traces.
4. No intenta ejecutar ni renderizar archivos (análisis pasivo por magic bytes y checksum).
5. Documenta formatos y límites del MVP.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from cdm.adapters.outbound.persistence.models import (
    Base,
    DocumentModel,
    UserModel,
    WorkspaceModel,
)
from cdm.adapters.outbound.persistence.repositories import SqlAlchemyDocumentRepository
from cdm.adapters.outbound.storage.s3_storage import S3StorageAdapter
from cdm.application.use_cases.process_document_event import (
    ProcessDocumentEventUseCase,
)
from cdm.bootstrap.worker_handler import process_sqs_event
from cdm.domain.content_inspection import (
    compute_sha256,
    detect_mime_type,
    validate_content_consistency,
)
from cdm.domain.document import DocumentStatus


@pytest.fixture
def sqlite_session():
    """Crea una sesión de base de datos SQLite en memoria para tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def sample_workspace_and_user(sqlite_session: Session):
    """Crea usuario y workspace para pruebas de persistencia."""
    user = UserModel(
        id=uuid4(),
        cognito_sub="sub-insp",
        email="insp@test.com",
        display_name="Inspector",
    )
    ws = WorkspaceModel(
        id=uuid4(),
        name="Insp WS",
        slug="insp-ws",
        created_by=user.id,
    )
    sqlite_session.add_all([user, ws])
    sqlite_session.commit()
    return ws, user


def test_detect_mime_type_from_magic_bytes():
    """Detecta correctamente los tipos MIME autorizados por sus magic bytes."""
    # PDF
    assert detect_mime_type(b"%PDF-1.7\n%obj...") == "application/pdf"
    # PNG
    assert detect_mime_type(b"\x89PNG\r\n\x1a\n\x00\x00...") == "image/png"
    # JPEG
    assert detect_mime_type(b"\xff\xd8\xff\xe0\x00\x10JFIF...") == "image/jpeg"
    # DOCX
    assert (
        detect_mime_type(b"PK\x03\x04\x14\x00...", filename="contrato.docx")
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    # XLSX
    assert (
        detect_mime_type(b"PK\x03\x04\x14\x00...", filename="balance.xlsx")
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    # JSON
    assert detect_mime_type(b'{"key": "value"}', filename="data.json") == "application/json"
    # Markdown
    assert detect_mime_type(b"# Titulo\nTexto", filename="README.md") == "text/markdown"
    # CSV
    assert detect_mime_type(b"id,nombre\n1,Prueba", filename="datos.csv") == "text/csv"
    # Texto plano
    assert detect_mime_type(b"Hola mundo", filename="notas.txt") == "text/plain"


def test_detect_prohibited_executables_and_scripts():
    """Detecta binarios ejecutables o scripts sin ejecutarlos ni interpretarlos."""
    # Windows PE executable (MZ)
    assert detect_mime_type(b"MZ\x90\x00\x03\x00...") == "application/x-dosexec"
    # Linux ELF executable
    assert detect_mime_type(b"\x7fELF\x02\x01\x01\x00...") == "application/x-executable"
    # Shell script
    assert detect_mime_type(b"#!/bin/bash\nrm -rf /") == "text/x-shellscript"


def test_validate_content_consistency_success():
    """Validación exitosa cuando el contenido coincide con el MIME declarado."""
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj"
    res = validate_content_consistency(
        data=pdf_bytes,
        declared_mime="application/pdf",
        original_filename="informe.pdf",
    )
    assert res.is_valid is True
    assert res.detected_mime == "application/pdf"
    assert res.declared_mime == "application/pdf"
    assert res.normalized_extension == ".pdf"
    assert res.computed_checksum == compute_sha256(pdf_bytes)
    assert res.failure_reason is None
    assert res.extracted_metadata is not None
    assert res.extracted_metadata["validation_status"] == "VALID"


def test_validate_content_consistency_detects_mime_spoofing():
    """Detecta discrepancia si se sube un ejecutable enmascarado como PDF."""
    fake_pdf = b"MZ\x90\x00\x03\x00...ejecutable malicioso..."
    res = validate_content_consistency(
        data=fake_pdf,
        declared_mime="application/pdf",
        original_filename="factura.pdf",
    )
    assert res.is_valid is False
    assert res.detected_mime == "application/x-dosexec"
    assert "ejecutable o script no permitido" in (res.failure_reason or "")


def test_validate_content_consistency_empty_file():
    """Rechaza archivos vacíos de 0 bytes como inválidos."""
    res = validate_content_consistency(
        data=b"",
        declared_mime="application/pdf",
        original_filename="vacio.pdf",
    )
    assert res.is_valid is False
    assert "vacío" in (res.failure_reason or "")


def test_validate_content_consistency_checksum_mismatch():
    """Detecta discrepancia si el checksum esperado no coincide con el contenido real."""
    data = b"%PDF-1.4\nvalido"
    wrong_checksum = "0" * 64
    res = validate_content_consistency(
        data=data,
        declared_mime="application/pdf",
        original_filename="test.pdf",
        expected_checksum=wrong_checksum,
    )
    assert res.is_valid is False
    assert "checksum SHA-256 no coincide" in (res.failure_reason or "")


def test_worker_processing_with_consistent_file_transitions_to_ready(
    sqlite_session: Session,
    sample_workspace_and_user: tuple[WorkspaceModel, UserModel],
):
    """El worker valida el contenido en S3, extrae metadatos técnicos y pasa a READY."""
    ws, user = sample_workspace_and_user
    doc_id = uuid4()
    storage_key = f"tenants/{ws.id}/documents/{doc_id}/balance.pdf"

    pdf_content = b"%PDF-1.4\n%real-content\nstream\nendstream"
    expected_hash = compute_sha256(pdf_content)

    doc = DocumentModel(
        id=doc_id,
        workspace_id=ws.id,
        uploaded_by=user.id,
        original_filename="balance.pdf",
        storage_key=storage_key,
        content_type="application/pdf",
        size_bytes=len(pdf_content),
        checksum_sha256=expected_hash,
        status=DocumentStatus.UPLOADED.value,
        technical_metadata={},
    )
    sqlite_session.add(doc)
    sqlite_session.commit()

    storage = S3StorageAdapter(bucket_name="test-bucket")
    storage.register_mock_object(
        storage_key=storage_key,
        size_bytes=len(pdf_content),
        content_type="application/pdf",
        etag="etag-valid-123",
        data=pdf_content,
    )

    repo = SqlAlchemyDocumentRepository(sqlite_session)
    use_case = ProcessDocumentEventUseCase(
        document_repo=repo,
        storage=storage,
        expected_bucket_name="test-bucket",
    )

    sqs_event = {
        "Records": [
            {
                "messageId": "msg-val-ok",
                "body": json.dumps(
                    {
                        "Records": [
                            {
                                "eventVersion": "2.1",
                                "eventSource": "aws:s3",
                                "eventName": "ObjectCreated:Put",
                                "s3": {
                                    "bucket": {"name": "test-bucket"},
                                    "object": {
                                        "key": storage_key,
                                        "size": len(pdf_content),
                                        "eTag": "etag-valid-123",
                                    },
                                },
                            }
                        ]
                    }
                ),
            }
        ]
    }

    result = process_sqs_event(event=sqs_event, use_case=use_case)

    # 1. Sin fallos en lote SQS
    assert result == {"batchItemFailures": []}

    # 2. Documento en estado READY
    updated = repo.get_by_id(workspace_id=ws.id, document_id=doc_id)
    assert updated is not None
    assert updated.status == DocumentStatus.READY
    assert updated.checksum_sha256 == expected_hash

    # 3. Metadatos técnicos enriquecidos
    assert updated.technical_metadata["mime_detected"] == "application/pdf"
    assert updated.technical_metadata["mime_declared"] == "application/pdf"
    assert updated.technical_metadata["normalized_extension"] == ".pdf"
    assert updated.technical_metadata["validation_status"] == "VALID"
    assert updated.technical_metadata["checksum_sha256"] == expected_hash
    assert updated.technical_metadata["s3_etag"] == "etag-valid-123"


def test_worker_processing_with_corrupted_file_marks_as_failed_cleanly(
    sqlite_session: Session,
    sample_workspace_and_user: tuple[WorkspaceModel, UserModel],
):
    """Si el archivo en S3 está corrupto o no coincide con el MIME, pasa a FAILED limpiamente."""
    ws, user = sample_workspace_and_user
    doc_id = uuid4()
    storage_key = f"tenants/{ws.id}/documents/{doc_id}/fake.pdf"

    # Contenido con discrepancia: declarado PDF pero contiene un binario DOS
    fake_content = b"MZ\x00\x00binario-invalido"

    doc = DocumentModel(
        id=doc_id,
        workspace_id=ws.id,
        uploaded_by=user.id,
        original_filename="fake.pdf",
        storage_key=storage_key,
        content_type="application/pdf",
        size_bytes=len(fake_content),
        status=DocumentStatus.UPLOADED.value,
        technical_metadata={},
    )
    sqlite_session.add(doc)
    sqlite_session.commit()

    storage = S3StorageAdapter(bucket_name="test-bucket")
    storage.register_mock_object(
        storage_key=storage_key,
        size_bytes=len(fake_content),
        data=fake_content,
    )

    repo = SqlAlchemyDocumentRepository(sqlite_session)
    use_case = ProcessDocumentEventUseCase(
        document_repo=repo,
        storage=storage,
        expected_bucket_name="test-bucket",
    )

    sqs_event = {
        "Records": [
            {
                "messageId": "msg-val-fail",
                "body": json.dumps(
                    {
                        "Records": [
                            {
                                "eventVersion": "2.1",
                                "eventSource": "aws:s3",
                                "eventName": "ObjectCreated:Put",
                                "s3": {
                                    "bucket": {"name": "test-bucket"},
                                    "object": {
                                        "key": storage_key,
                                        "size": len(fake_content),
                                        "eTag": "etag-fake",
                                    },
                                },
                            }
                        ]
                    }
                ),
            }
        ]
    }

    result = process_sqs_event(event=sqs_event, use_case=use_case)

    # Descarte limpio sin reintentos infinitos en SQS
    assert result == {"batchItemFailures": []}

    # Documento marcado como FAILED en base de datos
    updated = repo.get_by_id(workspace_id=ws.id, document_id=doc_id)
    assert updated is not None
    assert updated.status == DocumentStatus.FAILED
    assert updated.failure_reason is not None
    assert "ejecutable o script no permitido" in updated.failure_reason
    assert updated.technical_metadata["validation_status"] == "FAILED"
    assert updated.technical_metadata["mime_detected"] == "application/x-dosexec"
