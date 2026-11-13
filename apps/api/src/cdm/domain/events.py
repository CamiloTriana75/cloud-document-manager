"""Modelos de dominio y contratos para eventos S3 y SQS (CDM-35 / AGENTS.md §6, §12).

Módulo puro de dominio: sin dependencias de frameworks ni de AWS SDK (boto3).
Define la estructura, tipado y parseo seguro de eventos `s3:ObjectCreated:*` recibidos
a través de Amazon SQS por el worker de procesamiento asíncrono (CDM-36).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote_plus
from uuid import UUID

from cdm.domain.errors import InvalidS3EventError

# Patrón canónico de almacenamiento particionado por tenant:
# tenants/<workspace_id>/documents/<document_id>/<opaque_key>.<ext>
_TENANT_DOCUMENT_KEY_REGEX = re.compile(
    r"^tenants/([a-fA-F0-9\-]{36})/documents/([a-fA-F0-9\-]{36})/(.+)$"
)


@dataclass(frozen=True)
class S3ObjectNotificationRecord:
    """Representación inmutable de una notificación de objeto S3 (ObjectCreated)."""

    event_version: str
    event_source: str
    event_name: str
    event_time: datetime | None
    bucket_name: str
    storage_key: str
    size_bytes: int
    etag: str | None = None
    version_id: str | None = None
    sequencer: str | None = None

    @property
    def is_tenant_document_event(self) -> bool:
        """Verifica si la clave pertenece al prefijo estándar de documentos de un tenant."""
        return bool(_TENANT_DOCUMENT_KEY_REGEX.match(self.storage_key))

    @property
    def workspace_id(self) -> UUID:
        """Extrae el workspace_id de la clave de almacenamiento.

        Lanza:
            InvalidS3EventError: Si la clave no sigue el esquema canónico del tenant.
        """
        match = _TENANT_DOCUMENT_KEY_REGEX.match(self.storage_key)
        if not match:
            raise InvalidS3EventError(
                f"La clave '{self.storage_key}' no sigue el formato de partición de tenant."
            )
        try:
            return UUID(match.group(1))
        except ValueError as exc:
            raise InvalidS3EventError(f"El UUID del tenant en la clave es inválido: {exc}") from exc

    @property
    def document_id(self) -> UUID:
        """Extrae el document_id de la clave de almacenamiento.

        Lanza:
            InvalidS3EventError: Si la clave no sigue el esquema canónico del tenant.
        """
        match = _TENANT_DOCUMENT_KEY_REGEX.match(self.storage_key)
        if not match:
            raise InvalidS3EventError(
                f"La clave '{self.storage_key}' no sigue el formato de partición de documento."
            )
        try:
            return UUID(match.group(2))
        except ValueError as exc:
            raise InvalidS3EventError(
                f"El UUID del documento en la clave es inválido: {exc}"
            ) from exc


@dataclass(frozen=True)
class SQSMessageEnvelope:
    """Envoltorio inmutable de un mensaje SQS que transporta una notificación S3."""

    message_id: str
    receipt_handle: str
    body: str
    approximate_receive_count: int = 1
    event_source_arn: str | None = None


def parse_s3_event_records(payload: dict[str, Any] | str) -> list[S3ObjectNotificationRecord]:
    """Parsea y valida la carga útil de una notificación de eventos S3.

    Descodifica claves URL-encoded (reemplazo de '+' por espacio y decodificación porcentual)
    según la especificación de AWS S3 Event Notifications.

    Parámetros:
        payload: Diccionario o cadena JSON de la notificación S3.

    Retorna:
        Lista de registros de eventos de objetos validados.

    Lanza:
        InvalidS3EventError: Si el payload no es JSON válido o carece de la estructura esperada.
    """
    if isinstance(payload, str):
        try:
            raw_data = json.loads(payload)
        except Exception as exc:
            raise InvalidS3EventError(
                f"El payload del evento S3 no es un JSON válido: {exc}"
            ) from exc
    elif isinstance(payload, dict):
        raw_data = payload
    else:
        raise InvalidS3EventError(f"Tipo de payload no soportado: {type(payload).__name__}")

    if not isinstance(raw_data, dict) or "Records" not in raw_data:
        raise InvalidS3EventError("El evento S3 debe ser un diccionario que contenga 'Records'.")

    records_list = raw_data["Records"]
    if not isinstance(records_list, list):
        raise InvalidS3EventError("El campo 'Records' del evento S3 debe ser una lista.")

    parsed_records: list[S3ObjectNotificationRecord] = []

    for idx, item in enumerate(records_list):
        if not isinstance(item, dict):
            raise InvalidS3EventError(f"El registro S3 en índice {idx} no es un diccionario.")

        s3_payload = item.get("s3")
        if not isinstance(s3_payload, dict):
            raise InvalidS3EventError(f"El registro en índice {idx} no contiene el bloque 's3'.")

        bucket_payload = s3_payload.get("bucket", {})
        object_payload = s3_payload.get("object", {})

        bucket_name = bucket_payload.get("name")
        raw_key = object_payload.get("key")

        if not bucket_name or not isinstance(bucket_name, str):
            raise InvalidS3EventError(
                f"El registro en índice {idx} carece de un 'bucket.name' válido."
            )

        if not raw_key or not isinstance(raw_key, str):
            raise InvalidS3EventError(
                f"El registro en índice {idx} carece de un 'object.key' válido."
            )

        # AWS S3 codifica las claves de objeto con quote_plus (espacios como '+')
        decoded_key = unquote_plus(raw_key)

        # Parseo seguro de fecha
        event_time_str = item.get("eventTime")
        event_time: datetime | None = None
        if event_time_str and isinstance(event_time_str, str):
            try:
                event_time = datetime.fromisoformat(event_time_str.replace("Z", "+00:00"))
            except ValueError:
                event_time = datetime.now(UTC)

        size_bytes = object_payload.get("size", 0)
        if not isinstance(size_bytes, int) or size_bytes < 0:
            size_bytes = 0

        parsed_records.append(
            S3ObjectNotificationRecord(
                event_version=str(item.get("eventVersion", "2.1")),
                event_source=str(item.get("eventSource", "aws:s3")),
                event_name=str(item.get("eventName", "ObjectCreated:Put")),
                event_time=event_time,
                bucket_name=bucket_name,
                storage_key=decoded_key,
                size_bytes=size_bytes,
                etag=object_payload.get("eTag"),
                version_id=object_payload.get("versionId"),
                sequencer=object_payload.get("sequencer"),
            )
        )

    return parsed_records


def parse_sqs_event_to_s3_records(sqs_event: dict[str, Any]) -> list[S3ObjectNotificationRecord]:
    """Extrae y parsea eventos S3 contenidos dentro de un evento de lote SQS de Lambda.

    Parámetros:
        sqs_event: Diccionario con la estructura de evento de AWS Lambda para desencadenador SQS.

    Retorna:
        Lista consolidada de S3ObjectNotificationRecord extraídos de los cuerpos SQS.
    """
    if not isinstance(sqs_event, dict) or "Records" not in sqs_event:
        raise InvalidS3EventError("El evento SQS de Lambda debe contener el campo 'Records'.")

    all_s3_records: list[S3ObjectNotificationRecord] = []

    for sqs_record in sqs_event["Records"]:
        body_str = sqs_record.get("body")
        if not body_str or not isinstance(body_str, str):
            continue

        s3_records = parse_s3_event_records(body_str)
        all_s3_records.extend(s3_records)

    return all_s3_records
