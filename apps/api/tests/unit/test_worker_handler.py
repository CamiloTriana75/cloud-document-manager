"""Pruebas unitarias para el worker Lambda de procesamiento asíncrono e idempotente (CDM-36).

Verifica:
1. Procesamiento exitoso de eventos S3 ObjectCreated vía SQS (transición
   UPLOADED -> PROCESSING -> READY).
2. Enriquecimiento de metadatos técnicos en JSONB (etag, version_id, tamaño, timestamp).
3. Idempotencia estricta: eventos duplicados para documentos ya en READY no mutan la BD ni fallan.
4. Transición tolerante desde PENDING_UPLOAD si el evento llega antes de la llamada de confirmación.
5. Filtrado de claves ajenas al tenant o buckets no esperados (descarte limpio sin reintento).
6. Tolerancia a documentos no encontrados en BD (descarte limpio sin reintento).
7. Manejo de fallos parciales de lote (ReportBatchItemFailures): ante errores transitorios,
   solo el mensaje afectado se devuelve para reintento.
8. Descarte inmediato de mensajes con payload corrupto o no conforme (sin reintento en DLQ).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import MagicMock
from urllib.parse import quote_plus
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
from cdm.application.use_cases.process_document_event import (
    ProcessDocumentEventUseCase,
    ProcessingStatus,
)
from cdm.bootstrap.worker_handler import process_sqs_event
from cdm.domain.document import DocumentStatus


@pytest.fixture
def sqlite_session() -> Iterator[Session]:
    """Crea una sesión de base de datos SQLite en memoria para tests de repositorio."""
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
def sample_user_and_workspace(sqlite_session: Session) -> tuple[UserModel, WorkspaceModel]:
    """Crea un usuario y workspace persistidos para foreign keys de documentos."""
    user = UserModel(
        id=uuid4(),
        cognito_sub=f"sub-{uuid4()}",
        email="worker-test@example.com",
        display_name="Worker Tester",
    )
    workspace = WorkspaceModel(
        id=uuid4(),
        name="Worker Workspace",
        slug=f"worker-ws-{uuid4().hex[:6]}",
        created_by=user.id,
    )
    sqlite_session.add_all([user, workspace])
    sqlite_session.commit()
    return user, workspace


def build_sqs_s3_event(
    bucket_name: str,
    storage_key: str,
    size_bytes: int = 1024,
    etag: str = "d41d8cd98f00b204e9800998ecf8427e",
    version_id: str | None = "v1-test",
    message_id: str = "msg-12345",
) -> dict[str, list[dict[str, str]]]:
    """Genera la estructura de un evento SQS conteniendo un evento S3 ObjectCreated."""
    s3_event_payload = {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": "us-east-1",
                "eventTime": datetime.now(UTC).isoformat(),
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "s3SchemaVersion": "1.0",
                    "configurationId": "test-config",
                    "bucket": {
                        "name": bucket_name,
                        "arn": f"arn:aws:s3:::{bucket_name}",
                    },
                    "object": {
                        "key": quote_plus(storage_key),
                        "size": size_bytes,
                        "eTag": etag,
                        "versionId": version_id,
                    },
                },
            }
        ]
    }

    return {
        "Records": [
            {
                "messageId": message_id,
                "body": json.dumps(s3_event_payload),
            }
        ]
    }


def test_process_sqs_event_successful_transition(
    sqlite_session: Session,
    sample_user_and_workspace: tuple[UserModel, WorkspaceModel],
) -> None:
    """Documento en UPLOADED procesa exitosamente a READY con enriquecimiento técnico."""
    user, workspace = sample_user_and_workspace
    doc_id = uuid4()
    storage_key = f"tenants/{workspace.id}/documents/{doc_id}/test_doc.pdf"

    doc = DocumentModel(
        id=doc_id,
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_filename="test_doc.pdf",
        storage_key=storage_key,
        content_type="application/pdf",
        size_bytes=500,
        status=DocumentStatus.UPLOADED.value,
        technical_metadata={"initial": "data"},
    )
    sqlite_session.add(doc)
    sqlite_session.commit()

    repo = SqlAlchemyDocumentRepository(sqlite_session)
    use_case = ProcessDocumentEventUseCase(
        document_repo=repo,
        expected_bucket_name="test-documents-bucket",
    )

    event = build_sqs_s3_event(
        bucket_name="test-documents-bucket",
        storage_key=storage_key,
        size_bytes=2048,
        etag="etag-abc-999",
        version_id="ver-777",
        message_id="sqs-msg-101",
    )

    result = process_sqs_event(event=event, use_case=use_case)

    # 1. Sin fallos en el lote
    assert result == {"batchItemFailures": []}

    # 2. Documento actualizado a READY en base de datos
    updated = repo.get_by_id(workspace_id=workspace.id, document_id=doc_id)
    assert updated is not None
    assert updated.status == DocumentStatus.READY
    assert updated.size_bytes == 2048

    # 3. Metadatos técnicos enriquecidos
    assert updated.technical_metadata["s3_etag"] == "etag-abc-999"
    assert updated.technical_metadata["s3_version_id"] == "ver-777"
    assert updated.technical_metadata["s3_size_bytes"] == 2048
    assert updated.technical_metadata["s3_event_name"] == "ObjectCreated:Put"
    assert "processed_at" in updated.technical_metadata
    assert updated.technical_metadata["initial"] == "data"


def test_process_sqs_event_idempotency_already_ready(
    sqlite_session: Session,
    sample_user_and_workspace: tuple[UserModel, WorkspaceModel],
) -> None:
    """Documento ya en READY no muta ni genera fallos (idempotencia garantizada)."""
    user, workspace = sample_user_and_workspace
    doc_id = uuid4()
    storage_key = f"tenants/{workspace.id}/documents/{doc_id}/report.pdf"

    initial_time = "2026-11-12T18:00:00Z"
    doc = DocumentModel(
        id=doc_id,
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_filename="report.pdf",
        storage_key=storage_key,
        content_type="application/pdf",
        size_bytes=1000,
        status=DocumentStatus.READY.value,
        technical_metadata={"processed_at": initial_time, "s3_etag": "existing-etag"},
    )
    sqlite_session.add(doc)
    sqlite_session.commit()

    repo = SqlAlchemyDocumentRepository(sqlite_session)
    use_case = ProcessDocumentEventUseCase(
        document_repo=repo,
        expected_bucket_name="test-documents-bucket",
    )

    event = build_sqs_s3_event(
        bucket_name="test-documents-bucket",
        storage_key=storage_key,
        size_bytes=1000,
        etag="new-etag-ignored",
        message_id="msg-dup-1",
    )

    result = process_sqs_event(event=event, use_case=use_case)

    assert result == {"batchItemFailures": []}

    updated = repo.get_by_id(workspace_id=workspace.id, document_id=doc_id)
    assert updated is not None
    assert updated.status == DocumentStatus.READY
    # No debe haberse sobreescrito el timestamp previo
    assert updated.technical_metadata["processed_at"] == initial_time
    assert updated.technical_metadata["s3_etag"] == "existing-etag"


def test_process_sqs_event_transitions_from_pending_upload(
    sqlite_session: Session,
    sample_user_and_workspace: tuple[UserModel, WorkspaceModel],
) -> None:
    """Si el evento S3 llega antes de complete_upload (PENDING_UPLOAD), transiciona a READY."""
    user, workspace = sample_user_and_workspace
    doc_id = uuid4()
    storage_key = f"tenants/{workspace.id}/documents/{doc_id}/early.pdf"

    doc = DocumentModel(
        id=doc_id,
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_filename="early.pdf",
        storage_key=storage_key,
        content_type="application/pdf",
        size_bytes=0,
        status=DocumentStatus.PENDING_UPLOAD.value,
        technical_metadata={},
    )
    sqlite_session.add(doc)
    sqlite_session.commit()

    repo = SqlAlchemyDocumentRepository(sqlite_session)
    use_case = ProcessDocumentEventUseCase(document_repo=repo)

    event = build_sqs_s3_event(
        bucket_name="bucket-1",
        storage_key=storage_key,
        size_bytes=3500,
        etag="early-etag",
    )

    result = process_sqs_event(event=event, use_case=use_case)

    assert result == {"batchItemFailures": []}

    updated = repo.get_by_id(workspace_id=workspace.id, document_id=doc_id)
    assert updated is not None
    assert updated.status == DocumentStatus.READY
    assert updated.size_bytes == 3500


def test_process_sqs_event_skips_non_tenant_key(
    sqlite_session: Session,
) -> None:
    """Claves que no siguen la convención tenants/<ws>/documents/<doc> se descartan sin error."""
    repo = SqlAlchemyDocumentRepository(sqlite_session)
    use_case = ProcessDocumentEventUseCase(document_repo=repo)

    # Clave no conforme
    event = build_sqs_s3_event(
        bucket_name="bucket-1",
        storage_key="system/logs/app.log",
        message_id="msg-system-key",
    )

    result = process_sqs_event(event=event, use_case=use_case)

    # Descarte limpio, no se reintenta en SQS
    assert result == {"batchItemFailures": []}


def test_process_sqs_event_skips_unexpected_bucket(
    sqlite_session: Session,
    sample_user_and_workspace: tuple[UserModel, WorkspaceModel],
) -> None:
    """Eventos de un bucket ajeno al configurado se descartan de forma segura."""
    _user, workspace = sample_user_and_workspace
    doc_id = uuid4()
    storage_key = f"tenants/{workspace.id}/documents/{doc_id}/file.pdf"

    repo = SqlAlchemyDocumentRepository(sqlite_session)
    use_case = ProcessDocumentEventUseCase(
        document_repo=repo,
        expected_bucket_name="cdm-official-bucket",
    )

    event = build_sqs_s3_event(
        bucket_name="foreign-bucket",
        storage_key=storage_key,
        message_id="msg-wrong-bucket",
    )

    result = process_sqs_event(event=event, use_case=use_case)

    assert result == {"batchItemFailures": []}


def test_process_sqs_event_skips_when_document_not_in_db(
    sqlite_session: Session,
) -> None:
    """Si el documento no existe en base de datos, se descarta limpiamente."""
    repo = SqlAlchemyDocumentRepository(sqlite_session)
    use_case = ProcessDocumentEventUseCase(document_repo=repo)

    doc_id = uuid4()
    ws_id = uuid4()
    storage_key = f"tenants/{ws_id}/documents/{doc_id}/ghost.pdf"

    event = build_sqs_s3_event(
        bucket_name="bucket-1",
        storage_key=storage_key,
        message_id="msg-not-found",
    )

    result = process_sqs_event(event=event, use_case=use_case)

    assert result == {"batchItemFailures": []}


def test_process_sqs_event_partial_batch_failure_on_transient_error() -> None:
    """En un lote con múltiples mensajes, solo el mensaje que falla transitoriamente
    se reporta a SQS para reintento individual."""
    mock_use_case = MagicMock(spec=ProcessDocumentEventUseCase)

    # El primer mensaje triunfa, el segundo genera error transitorio (ej. DB timeout)
    ws_id = uuid4()
    doc_id_1 = uuid4()
    doc_id_2 = uuid4()

    event = {
        "Records": [
            {
                "messageId": "msg-success-1",
                "body": json.dumps(
                    {
                        "Records": [
                            {
                                "eventVersion": "2.1",
                                "eventSource": "aws:s3",
                                "awsRegion": "us-east-1",
                                "eventTime": "2026-11-12T19:00:00Z",
                                "eventName": "ObjectCreated:Put",
                                "s3": {
                                    "bucket": {"name": "b"},
                                    "object": {
                                        "key": f"tenants/{ws_id}/documents/{doc_id_1}/ok.pdf",
                                        "size": 100,
                                    },
                                },
                            }
                        ]
                    }
                ),
            },
            {
                "messageId": "msg-transient-fail-2",
                "body": json.dumps(
                    {
                        "Records": [
                            {
                                "eventVersion": "2.1",
                                "eventSource": "aws:s3",
                                "awsRegion": "us-east-1",
                                "eventTime": "2026-11-12T19:00:00Z",
                                "eventName": "ObjectCreated:Put",
                                "s3": {
                                    "bucket": {"name": "b"},
                                    "object": {
                                        "key": f"tenants/{ws_id}/documents/{doc_id_2}/fail.pdf",
                                        "size": 200,
                                    },
                                },
                            }
                        ]
                    }
                ),
            },
        ]
    }

    mock_use_case.execute.side_effect = [
        MagicMock(status=ProcessingStatus.PROCESSED),
        RuntimeError("Database lock contention"),
    ]

    result = process_sqs_event(event=event, use_case=mock_use_case)

    # Solo el mensaje 2 se reporta a SQS para reintento individual
    assert result == {"batchItemFailures": [{"itemIdentifier": "msg-transient-fail-2"}]}


def test_process_sqs_event_with_url_encoded_key(
    sqlite_session: Session,
    sample_user_and_workspace: tuple[UserModel, WorkspaceModel],
) -> None:
    """Claves con espacios y caracteres codificados por S3 (+ y %20)
    se decodifican y procesan correctamente."""
    user, workspace = sample_user_and_workspace
    doc_id = uuid4()
    filename = "informe financiero 2026 (final).pdf"
    storage_key = f"tenants/{workspace.id}/documents/{doc_id}/{filename}"

    doc = DocumentModel(
        id=doc_id,
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_filename=filename,
        storage_key=storage_key,
        content_type="application/pdf",
        size_bytes=100,
        status=DocumentStatus.UPLOADED.value,
        technical_metadata={},
    )
    sqlite_session.add(doc)
    sqlite_session.commit()

    repo = SqlAlchemyDocumentRepository(sqlite_session)
    use_case = ProcessDocumentEventUseCase(document_repo=repo)

    event = build_sqs_s3_event(
        bucket_name="bucket-1",
        storage_key=storage_key,
        size_bytes=5000,
        etag="etag-encoded-key",
    )

    result = process_sqs_event(event=event, use_case=use_case)

    assert result == {"batchItemFailures": []}
    updated = repo.get_by_id(workspace_id=workspace.id, document_id=doc_id)
    assert updated is not None
    assert updated.status == DocumentStatus.READY
    assert updated.size_bytes == 5000


def test_process_sqs_event_invalid_s3_payload_discarded() -> None:
    """Mensajes con payload JSON no parseable o sin campos S3 obligatorios
    se descartan sin reintento para evitar veneno en la cola."""
    mock_use_case = MagicMock(spec=ProcessDocumentEventUseCase)

    event = {
        "Records": [
            {
                "messageId": "msg-corrupted-json",
                "body": "{ invalid json body",
            },
            {
                "messageId": "msg-missing-records",
                "body": json.dumps({"foo": "bar"}),
            },
        ]
    }

    result = process_sqs_event(event=event, use_case=mock_use_case)

    # No se envían a batchItemFailures para evitar envenenar la cola con 3 reintentos inútiles
    assert result == {"batchItemFailures": []}
    mock_use_case.execute.assert_not_called()
