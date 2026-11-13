"""Caso de uso: Procesamiento asíncrono e idempotente de eventos de documentos (CDM-36).

Orquesta la recepción de notificaciones S3 ObjectCreated entregadas por SQS.
Garantiza:
1. Validación estricta de bucket y prefijo de tenant.
2. Idempotencia: eventos repetidos no alteran documentos ya en estado READY.
3. Transición segura de ciclo de vida (UPLOADED -> PROCESSING -> READY).
4. Enriquecimiento de metadatos técnicos (ETag, versión, tamaño real, timestamp).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from cdm.application.ports.document_repository import DocumentRepositoryPort
from cdm.application.ports.storage import StoragePort
from cdm.domain.content_inspection import validate_content_consistency
from cdm.domain.document import DocumentStatus
from cdm.domain.events import S3ObjectNotificationRecord

logger = logging.getLogger(__name__)


class ProcessingStatus(str, Enum):
    """Resultado del procesamiento de un evento individual."""

    PROCESSED = "PROCESSED"
    ALREADY_PROCESSED = "ALREADY_PROCESSED"
    SKIPPED_NON_TENANT = "SKIPPED_NON_TENANT"
    SKIPPED_NOT_FOUND = "SKIPPED_NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"


@dataclass(frozen=True)
class ProcessResult:
    """Resultado estructurado de la ejecución de procesamiento de un evento."""

    status: ProcessingStatus
    workspace_id: UUID | None
    document_id: UUID | None
    storage_key: str
    message: str


class ProcessDocumentEventUseCase:
    """Caso de uso para procesar eventos S3 ObjectCreated de forma idempotente."""

    def __init__(
        self,
        document_repo: DocumentRepositoryPort,
        storage: StoragePort | None = None,
        expected_bucket_name: str | None = None,
    ) -> None:
        self._document_repo = document_repo
        self._storage = storage
        self._expected_bucket_name = expected_bucket_name

    def execute(self, record: S3ObjectNotificationRecord) -> ProcessResult:
        """Ejecuta el procesamiento de un registro de evento S3."""
        # 1. Validación de bucket esperado si está configurado
        if (
            self._expected_bucket_name
            and record.bucket_name.strip() != self._expected_bucket_name.strip()
        ):
            logger.warning(
                "Evento ignorado: bucket '%s' no coincide con el configurado '%s'.",
                record.bucket_name,
                self._expected_bucket_name,
            )
            return ProcessResult(
                status=ProcessingStatus.SKIPPED_NON_TENANT,
                workspace_id=None,
                document_id=None,
                storage_key=record.storage_key,
                message=f"Bucket '{record.bucket_name}' no esperado.",
            )

        # 2. Validación de clave con prefijo canónico de tenant
        if not record.is_tenant_document_event:
            logger.info(
                "Evento ignorado: clave '%s' no pertenece a documentos de tenant.",
                record.storage_key,
            )
            return ProcessResult(
                status=ProcessingStatus.SKIPPED_NON_TENANT,
                workspace_id=None,
                document_id=None,
                storage_key=record.storage_key,
                message="La clave no sigue la convención tenants/<ws>/documents/<doc>.",
            )

        workspace_id = record.workspace_id
        document_id = record.document_id

        # 3. Consulta del documento en base de datos
        document = self._document_repo.get_by_id(
            workspace_id=workspace_id,
            document_id=document_id,
            include_deleted=True,
        )

        if document is None:
            logger.warning(
                "Documento no encontrado para evento S3: ws=%s doc=%s key=%s",
                workspace_id,
                document_id,
                record.storage_key,
            )
            return ProcessResult(
                status=ProcessingStatus.SKIPPED_NOT_FOUND,
                workspace_id=workspace_id,
                document_id=document_id,
                storage_key=record.storage_key,
                message="Documento no registrado en base de datos.",
            )

        # 4. Invariante de Idempotencia: Si ya está en READY, no repetir ni mutar
        if document.status == DocumentStatus.READY:
            logger.info(
                "Documento ya en estado READY (idempotencia): ws=%s doc=%s",
                workspace_id,
                document_id,
            )
            return ProcessResult(
                status=ProcessingStatus.ALREADY_PROCESSED,
                workspace_id=workspace_id,
                document_id=document_id,
                storage_key=record.storage_key,
                message="El documento ya fue procesado previamente (idempotente).",
            )

        # 5. Transición de estado segura y progresiva
        updated_doc = document

        # Si aún estaba en PENDING_UPLOAD (p. ej. evento S3 llegó antes del POST complete)
        if updated_doc.status == DocumentStatus.PENDING_UPLOAD:
            updated_doc = updated_doc.transition_to(DocumentStatus.UPLOADED)

        # Transición a PROCESSING
        if updated_doc.status == DocumentStatus.UPLOADED:
            updated_doc = updated_doc.transition_to(DocumentStatus.PROCESSING)

        # 6. Inspección de contenido y validación técnica (CDM-38)
        tech_meta: dict[str, Any] = dict(updated_doc.technical_metadata)
        tech_meta.update(
            {
                "s3_etag": record.etag,
                "s3_version_id": record.version_id,
                "s3_event_name": record.event_name,
                "s3_event_time": record.event_time.isoformat() if record.event_time else None,
                "s3_size_bytes": record.size_bytes,
                "processed_at": datetime.now(UTC).isoformat(),
            }
        )

        final_size = record.size_bytes if record.size_bytes > 0 else updated_doc.size_bytes
        computed_checksum = updated_doc.checksum_sha256

        # Si el almacenamiento está disponible, inspeccionar bytes para consistencia
        if self._storage is not None:
            object_bytes = self._storage.get_object_bytes(record.storage_key)

            if object_bytes is None:
                # Objeto no encontrado en el bucket S3
                updated_doc = updated_doc.mark_failed(
                    "El objeto binario no se encuentra en el almacenamiento."
                )
                self._document_repo.save(updated_doc)
                return ProcessResult(
                    status=ProcessingStatus.VALIDATION_FAILED,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    storage_key=record.storage_key,
                    message="Objeto no encontrado en S3 durante la inspección.",
                )

            # Validar consistencia técnica del contenido sin ejecutarlo ni renderizarlo
            validation = validate_content_consistency(
                data=object_bytes,
                declared_mime=updated_doc.content_type,
                original_filename=updated_doc.original_filename,
                expected_checksum=updated_doc.checksum_sha256,
            )

            if not validation.is_valid:
                # Fallo permanente de validación: marcar como FAILED
                updated_doc = updated_doc.mark_failed(
                    validation.failure_reason or "Discrepancia técnica en el archivo."
                )
                fail_meta = dict(updated_doc.technical_metadata)
                fail_meta.update(
                    {
                        "s3_etag": record.etag,
                        "s3_size_bytes": record.size_bytes,
                        "mime_detected": validation.detected_mime,
                        "validation_status": "FAILED",
                    }
                )
                updated_doc = replace(updated_doc, technical_metadata=fail_meta)
                self._document_repo.save(updated_doc)

                logger.warning(
                    "Validación fallida para documento ws=%s doc=%s: %s",
                    workspace_id,
                    document_id,
                    validation.failure_reason,
                )
                return ProcessResult(
                    status=ProcessingStatus.VALIDATION_FAILED,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    storage_key=record.storage_key,
                    message=validation.failure_reason or "Error de consistencia técnica.",
                )

            # Si es válido, enriquecer con metadatos extraídos
            if validation.extracted_metadata:
                tech_meta.update(validation.extracted_metadata)
            computed_checksum = validation.computed_checksum

        updated_doc = replace(
            updated_doc,
            size_bytes=final_size,
            checksum_sha256=computed_checksum,
            technical_metadata=tech_meta,
        )

        # Transición final a READY
        updated_doc = updated_doc.transition_to(DocumentStatus.READY)

        # 7. Persistir documento enriquecido y listo
        self._document_repo.save(updated_doc)

        logger.info(
            "Documento procesado exitosamente a READY: ws=%s doc=%s size=%s",
            workspace_id,
            document_id,
            final_size,
        )

        return ProcessResult(
            status=ProcessingStatus.PROCESSED,
            workspace_id=workspace_id,
            document_id=document_id,
            storage_key=record.storage_key,
            message="Documento procesado exitosamente a estado READY.",
        )
