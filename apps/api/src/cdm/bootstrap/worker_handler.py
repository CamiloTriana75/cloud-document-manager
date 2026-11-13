"""Handler para el worker de procesamiento asíncrono AWS Lambda (CDM-36 / AGENTS.md §6, §12).

Punto de entrada desencadenado por eventos de Amazon SQS provenientes de notificaciones S3.
Implementa el manejo de partial batch failure (ReportBatchItemFailures) para asegurar:
1. Reintento acotado de mensajes transitorios sin bloquear el lote entero.
2. Descarte controlado de mensajes permanentes corruptos para evitar veneno en la cola.
3. Idempotencia total en el procesamiento de eventos de documentos.
"""

from __future__ import annotations

import logging
from typing import Any

from cdm.adapters.outbound.persistence.engine import (
    create_db_engine,
    create_session_factory,
    unit_of_work,
)
from cdm.adapters.outbound.persistence.repositories import SqlAlchemyDocumentRepository
from cdm.application.use_cases.process_document_event import (
    ProcessDocumentEventUseCase,
)
from cdm.config.settings import Settings, load_settings
from cdm.domain.errors import InvalidS3EventError
from cdm.domain.events import parse_s3_event_records

logger = logging.getLogger(__name__)


def process_sqs_event(
    event: dict[str, Any],
    use_case: ProcessDocumentEventUseCase,
) -> dict[str, list[dict[str, str]]]:
    """Procesa un lote de mensajes SQS retornando fallos parciales (partial batch failure).

    Parámetros:
        event: Diccionario con la estructura de evento SQS de AWS Lambda.
        use_case: Instancia configurada de ProcessDocumentEventUseCase.

    Retorna:
        Diccionario con 'batchItemFailures' conteniendo los IDs de mensajes fallidos a reintentar.
    """
    batch_item_failures: list[dict[str, str]] = []
    records = event.get("Records", [])

    logger.info("Worker Lambda procesando lote de %d mensajes SQS.", len(records))

    for record in records:
        message_id = record.get("messageId", "")
        body = record.get("body", "")

        try:
            # 1. Parsear el evento S3 contenido en el cuerpo del mensaje SQS
            s3_records = parse_s3_event_records(body)

            # 2. Procesar cada registro S3 de forma idempotente
            for s3_rec in s3_records:
                use_case.execute(s3_rec)

        except InvalidS3EventError as exc:
            # Error permanente en la estructura del mensaje: no reintentar
            logger.error(
                "Mensaje SQS %s descartado por formato o clave inválida (error permanente): %s",
                message_id,
                exc,
            )
        except Exception as exc:
            # Error transitorio (p. ej. fallo de conexión a BD, timeout):
            # Agregar a batchItemFailures para que SQS reintente únicamente este mensaje
            logger.exception(
                "Fallo transitorio al procesar mensaje SQS %s: %s. Se programará reintento.",
                message_id,
                exc,
            )
            if message_id:
                batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}


def handler(event: dict[str, Any], context: Any) -> dict[str, list[dict[str, str]]]:
    """Punto de entrada oficial para AWS Lambda Trigger de SQS."""
    settings: Settings = load_settings()

    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)

    with unit_of_work(session_factory) as session:
        doc_repo = SqlAlchemyDocumentRepository(session)
        use_case = ProcessDocumentEventUseCase(
            document_repo=doc_repo,
            expected_bucket_name=getattr(settings, "documents_bucket_name", None),
        )
        return process_sqs_event(event=event, use_case=use_case)
