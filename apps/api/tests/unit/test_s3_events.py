"""Pruebas unitarias para parseo y validación de eventos S3 y SQS (CDM-35).

Criterios verificados:
- Parseo correcto de notificaciones S3 ObjectCreated en formatos dict y JSON string.
- Decodificación segura de claves URL-encoded (incluyendo '+' como espacio).
- Extracción tipada de workspace_id y document_id a partir de claves particionadas por tenant.
- Rechazo defensivo de payloads malformados o inválidos mediante InvalidS3EventError.
- Extracción de registros S3 anidados dentro de lotes de eventos SQS de AWS Lambda.
"""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cdm.domain.errors import InvalidS3EventError
from cdm.domain.events import (
    S3ObjectNotificationRecord,
    parse_s3_event_records,
    parse_sqs_event_to_s3_records,
)


def test_parse_valid_s3_event_dict():
    """Parsea un evento S3 estándar con metadatos completos."""
    ws_id = uuid4()
    doc_id = uuid4()
    raw_key = f"tenants/{ws_id}/documents/{doc_id}/reporte_financiero.pdf"

    payload = {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": "us-east-1",
                "eventTime": "2026-11-12T19:30:00.000Z",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "s3SchemaVersion": "1.0",
                    "configurationId": "sqs-event-rule",
                    "bucket": {
                        "name": "cdm-dev-docs-123456",
                        "arn": "arn:aws:s3:::cdm-dev-docs-123456",
                    },
                    "object": {
                        "key": raw_key,
                        "size": 1048576,
                        "eTag": "d41d8cd98f00b204e9800998ecf8427e",
                        "versionId": "v123",
                        "sequencer": "0055AED6DCD90281E5",
                    },
                },
            }
        ]
    }

    records = parse_s3_event_records(payload)

    assert len(records) == 1
    record = records[0]
    assert isinstance(record, S3ObjectNotificationRecord)
    assert record.bucket_name == "cdm-dev-docs-123456"
    assert record.storage_key == raw_key
    assert record.size_bytes == 1048576
    assert record.etag == "d41d8cd98f00b204e9800998ecf8427e"
    assert record.version_id == "v123"
    assert record.is_tenant_document_event is True
    assert record.workspace_id == ws_id
    assert record.document_id == doc_id
    assert record.event_time == datetime(2026, 11, 12, 19, 30, tzinfo=UTC)


def test_parse_s3_event_url_encoded_key():
    """Descodifica correctamente caracteres URL-encoded y '+' como espacios en la clave."""
    ws_id = uuid4()
    doc_id = uuid4()
    # En S3, "informe anual (2026).pdf" se envía como "informe+anual+%282026%29.pdf"
    encoded_key = f"tenants/{ws_id}/documents/{doc_id}/informe+anual+%282026%29.pdf"

    payload = {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": encoded_key, "size": 2048},
                },
            }
        ]
    }

    records = parse_s3_event_records(payload)
    assert len(records) == 1
    assert records[0].storage_key == f"tenants/{ws_id}/documents/{doc_id}/informe anual (2026).pdf"
    assert records[0].workspace_id == ws_id
    assert records[0].document_id == doc_id


def test_parse_s3_event_from_json_string():
    """Acepta cadenas serializadas en JSON."""
    payload = {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "tenants/ws/documents/doc/file.txt", "size": 50},
                },
            }
        ]
    }

    json_str = json.dumps(payload)
    records = parse_s3_event_records(json_str)
    assert len(records) == 1
    assert records[0].bucket_name == "test-bucket"
    assert records[0].size_bytes == 50


def test_non_tenant_key_properties():
    """Claves fuera de tenants/{ws}/{doc} marcan is_tenant_document_event=False."""
    record = S3ObjectNotificationRecord(
        event_version="2.1",
        event_source="aws:s3",
        event_name="ObjectCreated:Put",
        event_time=None,
        bucket_name="test-bucket",
        storage_key="temp/session-123/archivo.pdf",
        size_bytes=100,
    )

    assert record.is_tenant_document_event is False
    with pytest.raises(InvalidS3EventError) as exc_ws:
        _ = record.workspace_id
    assert "no sigue el formato de partición de tenant" in str(exc_ws.value)

    with pytest.raises(InvalidS3EventError) as exc_doc:
        _ = record.document_id
    assert "no sigue el formato de partición de documento" in str(exc_doc.value)


def test_parse_invalid_payloads_raises_error():
    """Rechaza cargas inválidas: no dict, sin Records, clave ausente o JSON roto."""
    with pytest.raises(InvalidS3EventError):
        parse_s3_event_records("{malformed json")

    with pytest.raises(InvalidS3EventError):
        parse_s3_event_records([])  # type: ignore[arg-type]

    with pytest.raises(InvalidS3EventError):
        parse_s3_event_records({"other": "field"})

    with pytest.raises(InvalidS3EventError):
        parse_s3_event_records({"Records": [{"no_s3": 1}]})

    with pytest.raises(InvalidS3EventError):
        parse_s3_event_records({"Records": [{"s3": {"bucket": {}, "object": {}}}]})


def test_parse_sqs_event_to_s3_records():
    """Extrae eventos S3 contenidos en mensajes SQS entregados a AWS Lambda."""
    ws_id = uuid4()
    doc_id = uuid4()
    s3_inner_payload = {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": "bucket-lambda"},
                    "object": {
                        "key": f"tenants/{ws_id}/documents/{doc_id}/data.json",
                        "size": 500,
                    },
                },
            }
        ]
    }

    sqs_lambda_event = {
        "Records": [
            {
                "messageId": "msg-001",
                "receiptHandle": "handle-001",
                "body": json.dumps(s3_inner_payload),
                "attributes": {"ApproximateReceiveCount": "1"},
                "eventSource": "aws:sqs",
            }
        ]
    }

    records = parse_sqs_event_to_s3_records(sqs_lambda_event)
    assert len(records) == 1
    assert records[0].bucket_name == "bucket-lambda"
    assert records[0].workspace_id == ws_id
    assert records[0].document_id == doc_id
    assert records[0].size_bytes == 500
