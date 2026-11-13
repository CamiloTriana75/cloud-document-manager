"""Adaptador inbound HTTP: Endpoints de Documentos y Tenant (CDM-27 / AGENTS.md §11).

Rutas montadas en /api/v1/workspaces/{workspace_id}/documents.
Todas las operaciones exigen la resolución y validación de TenantContext.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from pydantic import BaseModel, Field

from cdm.adapters.inbound.http.dependencies import (
    get_authorize_document_download_use_case,
    get_complete_document_upload_use_case,
    get_create_document_record_use_case,
    get_delete_document_use_case,
    get_document_detail_use_case,
    get_list_documents_use_case,
    get_retry_document_processing_use_case,
    get_tenant_context,
)
from cdm.adapters.inbound.http.errors import ERROR_RESPONSES
from cdm.adapters.inbound.http.pagination import PaginationMeta, PaginationParams
from cdm.application.use_cases.documents import (
    AuthorizeDocumentDownloadUseCase,
    CompleteDocumentUploadUseCase,
    CreateDocumentRecordUseCase,
    DeleteDocumentUseCase,
    GetDocumentDetailUseCase,
    ListDocumentsUseCase,
    RetryDocumentProcessingUseCase,
)
from cdm.domain.document import DocumentQueryFilter, DocumentStatus
from cdm.domain.tenant import TenantContext

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/documents", tags=["documents"])


# --- Schemas de Entrada ---


class CreateDocumentRequest(BaseModel):
    """Payload para registrar metadatos de un nuevo documento en el tenant."""

    original_filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nombre original del archivo",
        examples=["reporte_financiero_2026.pdf"],
    )
    storage_key: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Clave de almacenamiento opaca en S3 generada por servidor",
        examples=["workspaces/123/docs/abc-456.pdf"],
    )
    content_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Tipo MIME verificado",
        examples=["application/pdf"],
    )
    size_bytes: int = Field(
        ...,
        ge=0,
        description="Tamaño en bytes del archivo binario",
        examples=[1048576],
    )
    checksum_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        description="Checksum SHA-256 opcional",
    )
    technical_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos técnicos adicionales extensibles",
    )


# --- Schemas de Salida ---


class DocumentResponse(BaseModel):
    """Representación pública de un documento."""

    id: UUID
    workspace_id: UUID
    uploaded_by: UUID
    original_filename: str
    storage_key: str | None = Field(
        default=None,
        description="Clave de almacenamiento interna (omitida en respuestas públicas)",
    )
    content_type: str
    size_bytes: int
    checksum_sha256: str | None
    status: DocumentStatus
    technical_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    failure_reason: str | None = None
    retry_count: int = 0


class DownloadUrlRequest(BaseModel):
    """Parámetros opcionales para la generación de la URL temporal de descarga."""

    expires_in_seconds: int = Field(
        default=900,
        ge=60,
        le=3600,
        description="Tiempo de vida en segundos de la URL prefirmada (mínimo 60s, máximo 3600s)",
        examples=[900],
    )


class DownloadUrlResponse(BaseModel):
    """Detalle de la URL prefirmada de descarga temporal."""

    document_id: UUID
    original_filename: str
    download_url: str
    expires_in_seconds: int


class EnvelopeDocument(BaseModel):
    """Envelope de respuesta para un único documento."""

    data: DocumentResponse


class EnvelopeDocumentList(BaseModel):
    """Envelope de respuesta para la lista de documentos."""

    data: list[DocumentResponse]
    pagination: PaginationMeta


class EnvelopeDownloadUrl(BaseModel):
    """Envelope de respuesta para la URL de descarga temporal."""

    data: DownloadUrlResponse


class EnvelopeDelete(BaseModel):
    """Envelope de respuesta para eliminación exitosa."""

    data: dict[str, str]


# --- Endpoints ---


@router.get(
    "",
    response_model=EnvelopeDocumentList,
    summary="Listar catálogo de documentos",
    description="Retorna el catálogo de documentos activos pertenecientes al tenant verificado.",
    responses=ERROR_RESPONSES,
)
def list_documents(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    pagination: Annotated[PaginationParams, Depends()],
    use_case: Annotated[ListDocumentsUseCase, Depends(get_list_documents_use_case)],
    status: Annotated[
        DocumentStatus | None, Query(description="Filtrar por estado del documento")
    ] = None,
    search: Annotated[
        str | None,
        Query(
            description="Buscar término en el nombre original del archivo (case-insensitive)",
            max_length=255,
        ),
    ] = None,
    content_type: Annotated[
        str | None,
        Query(
            description="Filtrar por tipo MIME (ej: application/pdf, image/png)",
            max_length=100,
        ),
    ] = None,
    uploaded_by: Annotated[
        UUID | None,
        Query(description="Filtrar por ID del usuario creador/autor"),
    ] = None,
    created_after: Annotated[
        datetime | None,
        Query(description="Filtrar documentos creados en o después de esta fecha (ISO-8601)"),
    ] = None,
    created_before: Annotated[
        datetime | None,
        Query(description="Filtrar documentos creados en o antes de esta fecha (ISO-8601)"),
    ] = None,
) -> EnvelopeDocumentList:
    doc_filter = DocumentQueryFilter(
        status=status,
        content_type=content_type,
        search_term=search,
        uploaded_by=uploaded_by,
        created_after=created_after,
        created_before=created_before,
        include_deleted=False,
    )
    result = use_case.execute(
        tenant=tenant,
        limit=pagination.limit,
        offset=pagination.offset,
        status=status,
        filters=doc_filter,
    )
    return EnvelopeDocumentList(
        data=[
            DocumentResponse(
                id=d.id,
                workspace_id=d.workspace_id,
                uploaded_by=d.uploaded_by,
                original_filename=d.original_filename,
                storage_key=d.storage_key,
                content_type=d.content_type,
                size_bytes=d.size_bytes,
                checksum_sha256=d.checksum_sha256,
                status=d.status,
                technical_metadata=d.technical_metadata,
                created_at=d.created_at,
                updated_at=d.updated_at,
                failure_reason=d.failure_reason,
                retry_count=d.retry_count,
            )
            for d in result.items
        ],
        pagination=PaginationMeta.build(
            total=result.total,
            limit=pagination.limit,
            offset=pagination.offset,
        ),
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=EnvelopeDocument,
    summary="Registrar metadatos de documento",
    description=(
        "Registra metadatos de documento en el tenant verificado (requiere rol MEMBER o superior)."
    ),
    responses=ERROR_RESPONSES,
)
def create_document(
    payload: CreateDocumentRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    use_case: Annotated[CreateDocumentRecordUseCase, Depends(get_create_document_record_use_case)],
) -> EnvelopeDocument:
    doc = use_case.execute(
        tenant=tenant,
        original_filename=payload.original_filename,
        storage_key=payload.storage_key,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        checksum_sha256=payload.checksum_sha256,
        technical_metadata=payload.technical_metadata,
    )
    return EnvelopeDocument(
        data=DocumentResponse(
            id=doc.id,
            workspace_id=doc.workspace_id,
            uploaded_by=doc.uploaded_by,
            original_filename=doc.original_filename,
            storage_key=doc.storage_key,
            content_type=doc.content_type,
            size_bytes=doc.size_bytes,
            checksum_sha256=doc.checksum_sha256,
            status=doc.status,
            technical_metadata=doc.technical_metadata,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            failure_reason=doc.failure_reason,
            retry_count=doc.retry_count,
        )
    )


@router.get(
    "/{document_id}",
    response_model=EnvelopeDocument,
    summary="Detalle de documento",
    description=(
        "Retorna el detalle de un documento exigiendo pertenencia al tenant "
        "(prevención estricta de IDOR)."
    ),
    responses=ERROR_RESPONSES,
)
def get_document_detail(
    document_id: Annotated[UUID, Path(description="Identificador del documento")],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    use_case: Annotated[GetDocumentDetailUseCase, Depends(get_document_detail_use_case)],
) -> EnvelopeDocument:
    doc = use_case.execute(tenant=tenant, document_id=document_id)
    return EnvelopeDocument(
        data=DocumentResponse(
            id=doc.id,
            workspace_id=doc.workspace_id,
            uploaded_by=doc.uploaded_by,
            original_filename=doc.original_filename,
            storage_key=doc.storage_key,
            content_type=doc.content_type,
            size_bytes=doc.size_bytes,
            checksum_sha256=doc.checksum_sha256,
            status=doc.status,
            technical_metadata=doc.technical_metadata,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            failure_reason=doc.failure_reason,
            retry_count=doc.retry_count,
        )
    )


@router.post(
    "/{document_id}/download-url",
    response_model=EnvelopeDownloadUrl,
    summary="Generar URL temporal de descarga",
    description="Autoriza y genera una URL prefirmada HTTPS para la descarga del binario privado.",
    responses=ERROR_RESPONSES,
)
def generate_download_url(
    document_id: Annotated[UUID, Path(description="Identificador del documento")],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    use_case: Annotated[
        AuthorizeDocumentDownloadUseCase, Depends(get_authorize_document_download_use_case)
    ],
    payload: DownloadUrlRequest | None = None,
) -> EnvelopeDownloadUrl:
    expires_in = payload.expires_in_seconds if payload is not None else 900
    download_info = use_case.execute(
        tenant=tenant,
        document_id=document_id,
        expires_in_seconds=expires_in,
    )
    return EnvelopeDownloadUrl(
        data=DownloadUrlResponse(
            document_id=download_info.document_id,
            original_filename=download_info.original_filename,
            download_url=download_info.download_url,
            expires_in_seconds=download_info.expires_in_seconds,
        )
    )


@router.delete(
    "/{document_id}",
    response_model=EnvelopeDelete,
    summary="Eliminar documento lógicamente",
    description="Marca un documento como eliminado. Requiere rol EDITOR, ADMIN o OWNER (ADR-0001).",
    responses=ERROR_RESPONSES,
)
def delete_document(
    document_id: Annotated[UUID, Path(description="Identificador del documento")],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    use_case: Annotated[DeleteDocumentUseCase, Depends(get_delete_document_use_case)],
) -> EnvelopeDelete:
    use_case.execute(tenant=tenant, document_id=document_id)
    return EnvelopeDelete(data={"message": "Documento eliminado lógicamente de forma exitosa."})


@router.post(
    "/{document_id}/complete",
    response_model=EnvelopeDocument,
    summary="Confirmar carga y reconciliar objeto S3",
    description=(
        "Confirma la subida directa a S3, reconciliando presencia física y metadatos. "
        "Transiciona el estado de PENDING_UPLOAD a UPLOADED de forma atómica e idempotente. "
        "Requiere rol MEMBER o superior."
    ),
    responses=ERROR_RESPONSES,
)
def complete_document_upload(
    document_id: Annotated[UUID, Path(description="Identificador del documento a confirmar")],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    use_case: Annotated[
        CompleteDocumentUploadUseCase, Depends(get_complete_document_upload_use_case)
    ],
) -> EnvelopeDocument:
    doc = use_case.execute(tenant=tenant, document_id=document_id)
    return EnvelopeDocument(
        data=DocumentResponse(
            id=doc.id,
            workspace_id=doc.workspace_id,
            uploaded_by=doc.uploaded_by,
            original_filename=doc.original_filename,
            storage_key=doc.storage_key,
            content_type=doc.content_type,
            size_bytes=doc.size_bytes,
            checksum_sha256=doc.checksum_sha256,
            status=doc.status,
            technical_metadata=doc.technical_metadata,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            failure_reason=doc.failure_reason,
            retry_count=doc.retry_count,
        )
    )


@router.post(
    "/{document_id}/retry",
    response_model=EnvelopeDocument,
    summary="Reintentar procesamiento de documento fallido",
    description=(
        "Permite reiniciar de forma controlada el procesamiento de un documento en estado FAILED. "
        "Requiere rol ADMIN o OWNER (ADR-0001, CDM-39). Acotado a un máximo de 3 reintentos."
    ),
    responses=ERROR_RESPONSES,
)
def retry_document_processing(
    document_id: Annotated[UUID, Path(description="Identificador del documento a reintentar")],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    use_case: Annotated[
        RetryDocumentProcessingUseCase, Depends(get_retry_document_processing_use_case)
    ],
) -> EnvelopeDocument:
    doc = use_case.execute(tenant=tenant, document_id=document_id)
    return EnvelopeDocument(
        data=DocumentResponse(
            id=doc.id,
            workspace_id=doc.workspace_id,
            uploaded_by=doc.uploaded_by,
            original_filename=doc.original_filename,
            storage_key=doc.storage_key,
            content_type=doc.content_type,
            size_bytes=doc.size_bytes,
            checksum_sha256=doc.checksum_sha256,
            status=doc.status,
            technical_metadata=doc.technical_metadata,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            failure_reason=doc.failure_reason,
            retry_count=doc.retry_count,
        )
    )
