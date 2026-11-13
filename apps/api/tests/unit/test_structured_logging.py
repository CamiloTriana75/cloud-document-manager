"""Pruebas unitarias para logging estructurado y correlación CloudWatch (CDM-52 / AGENTS.md).

Verifica:
1. Serialización JSON estructurada con campos estándar (timestamp, level, logger, message).
2. Propagación de identificadores de correlación (request_id, tenant_id, document_id).
3. Middleware de trazabilidad HTTP (CorrelationIdMiddleware) y cabeceras X-Request-ID.
4. Limpieza adecuada de contextvars para evitar fugas de contexto entre peticiones.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cdm.adapters.inbound.http.correlation import CorrelationIdMiddleware
from cdm.bootstrap.worker_handler import process_sqs_event
from cdm.config.logging import (
    StructuredJsonFormatter,
    clear_log_context,
    current_request_id,
    set_log_context,
)


class TestStructuredJsonFormatter:
    """Verifica el formato JSON y la inyección de identificadores de correlación."""

    def test_structured_formatter_produces_valid_json(self) -> None:
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="cdm.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Procesando documento de prueba",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["level"] == "INFO"
        assert data["logger"] == "cdm.test"
        assert data["message"] == "Procesando documento de prueba"
        assert "timestamp" in data

    def test_structured_formatter_injects_contextvars(self) -> None:
        req_id = "req-12345"
        ten_id = str(uuid4())
        doc_id = str(uuid4())

        set_log_context(request_id=req_id, tenant_id=ten_id, document_id=doc_id)
        try:
            formatter = StructuredJsonFormatter()
            record = logging.LogRecord(
                name="cdm.application",
                level=logging.WARNING,
                pathname=__file__,
                lineno=20,
                msg="Alerta de procesamiento",
                args=(),
                exc_info=None,
            )

            formatted = formatter.format(record)
            data = json.loads(formatted)

            assert data["request_id"] == req_id
            assert data["tenant_id"] == ten_id
            assert data["document_id"] == doc_id
        finally:
            clear_log_context()

    def test_structured_formatter_sanitizes_bearer_and_presigned_urls(self) -> None:
        formatter = StructuredJsonFormatter()
        sensitive_msg = (
            "Auth token: Bearer mock.jwt.secret.token.12345 and URL "
            "https://my-bucket.s3.amazonaws.com/doc.pdf?X-Amz-Signature=abcd1234"
        )
        record = logging.LogRecord(
            name="cdm.security",
            level=logging.INFO,
            pathname=__file__,
            lineno=30,
            msg=sensitive_msg,
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert "mock.jwt.secret" not in data["message"]
        assert "Bearer [REDACTED]" in data["message"]
        assert "X-Amz-Signature" not in data["message"]
        assert "https://[S3_PRESIGNED_URL_REDACTED]" in data["message"]

    def test_structured_formatter_includes_exception_traceback(self) -> None:
        formatter = StructuredJsonFormatter()
        try:
            raise ValueError("Fallo simulado de prueba")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="cdm.error",
            level=logging.ERROR,
            pathname=__file__,
            lineno=40,
            msg="Ocurrió un error inesperado",
            args=(),
            exc_info=exc_info,
        )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert "exception" in data
        assert "ValueError: Fallo simulado de prueba" in data["exception"]


class TestCorrelationIdMiddleware:
    """Verifica que las peticiones HTTP conserven o generen X-Request-ID y se limpie el contexto."""

    def test_middleware_generates_request_id_if_not_present(self) -> None:
        app = FastAPI()
        app.add_middleware(CorrelationIdMiddleware)

        @app.get("/test")
        def endpoint() -> dict[str, str | None]:
            return {"active_request_id": current_request_id.get()}

        client = TestClient(app)
        res = client.get("/test")

        assert res.status_code == 200
        req_id = res.headers.get("x-request-id")
        assert req_id is not None
        assert len(req_id) > 10
        # El contextvar dentro de la petición capturó el ID
        assert res.json()["active_request_id"] == req_id
        # Fuera de la petición, el contexto fue limpiado
        assert current_request_id.get() is None

    def test_middleware_propagates_incoming_request_id(self) -> None:
        app = FastAPI()
        app.add_middleware(CorrelationIdMiddleware)

        @app.get("/test")
        def endpoint() -> dict[str, str | None]:
            return {"active_request_id": current_request_id.get()}

        client = TestClient(app)
        custom_id = "client-trace-abc-123"
        res = client.get("/test", headers={"x-request-id": custom_id})

        assert res.status_code == 200
        assert res.headers.get("x-request-id") == custom_id
        assert res.json()["active_request_id"] == custom_id
        assert current_request_id.get() is None


class TestWorkerLoggingCorrelation:
    """Verifica que el procesador SQS Lambda correlacione los mensajes con el contexto de logs."""

    def test_process_sqs_event_sets_and_clears_correlation_context(self) -> None:
        captured_contexts: list[str | None] = []

        mock_use_case = MagicMock()

        def side_effect(_: object) -> None:
            captured_contexts.append(current_request_id.get())

        mock_use_case.execute.side_effect = side_effect

        msg_body = json.dumps(
            {
                "Records": [
                    {
                        "s3": {
                            "bucket": {"name": "test-bucket"},
                            "object": {
                                "key": f"workspaces/{uuid4()}/documents/{uuid4()}/test.pdf",
                                "size": 1024,
                            },
                        }
                    }
                ]
            }
        )

        event = {
            "Records": [
                {
                    "messageId": "sqs-msg-unique-999",
                    "body": msg_body,
                }
            ]
        }

        res = process_sqs_event(event, mock_use_case)
        assert res == {"batchItemFailures": []}

        # Verificamos que durante la ejecución el request_id correspondía al messageId de SQS
        assert len(captured_contexts) == 1
        assert captured_contexts[0] == "sqs-msg-unique-999"

        # Al terminar, el contexto queda limpio
        assert current_request_id.get() is None
