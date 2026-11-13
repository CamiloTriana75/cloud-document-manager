"""Adaptador inbound HTTP: Endpoints de Sesiones de Carga Prefirmada (CDM-29 / AGENTS.md §11).

Montado en /api/v1/workspaces/{workspace_id}/upload-sessions.
Valida identidad, pertenencia al tenant, políticas de archivo (CDM-30) y roles.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, Field

from cdm.adapters.inbound.http.dependencies import (
    get_cancel_upload_session_use_case,
    get_cleanup_expired_upload_sessions_use_case,
    get_create_upload_session_use_case,
    get_tenant_context,
)
from cdm.adapters.inbound.http.errors import ERROR_RESPONSES
from cdm.adapters.inbound.http.rate_limit import rate_limit_dependency
from cdm.application.use_cases.upload_sessions import (
    CancelUploadSessionUseCase,
    CleanupExpiredUploadSessionsUseCase,
    CreateUploadSessionUseCase,
)
from cdm.domain.tenant import TenantContext
from cdm.domain.workspace import WorkspaceRole

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/upload-sessions",
    tags=["upload-sessions"],
)


# --- Schemas de Entrada ---


class CreateUploadSessionRequest(BaseModel):
    """Payload para iniciar una sesión de carga prefirmada directa a S3."""

    original_filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nombre original del archivo con extensión válida",
        examples=["reporte_anual_2026.pdf"],
    )
    content_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Tipo MIME verificado de la allowlist",
        examples=["application/pdf"],
    )
    size_bytes: int = Field(
        ...,
        gt=0,
        description="Tamaño exacto en bytes del archivo binario a cargar",
        examples=[2097152],
    )
    checksum_sha256: str | None = Field(
        default=None,
        max_length=128,
        description="Checksum SHA-256 opcional para verificación de integridad",
        examples=["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
    )


# --- Schemas de Salida ---


class UploadSessionResponse(BaseModel):
    """Metadatos de la sesión de carga y URL prefirmada devuelta al navegador."""

    upload_session_id: UUID
    document_id: UUID
    upload_url: str
    storage_key: str
    expires_in_seconds: int
    required_headers: dict[str, str]


class EnvelopeUploadSession(BaseModel):
    """Envelope estándar de respuesta para una sesión de carga."""

    data: UploadSessionResponse


class EnvelopeMessage(BaseModel):
    """Envelope para mensajes de confirmación de acción."""

    data: dict[str, str]


class CleanupReportResponse(BaseModel):
    """Métricas resultantes del barrido de limpieza de sesiones y objetos huérfanos."""

    expired_sessions_count: int
    cleaned_objects_count: int
    skipped_confirmed_documents_count: int


class EnvelopeCleanupReport(BaseModel):
    """Envelope de respuesta para el reporte de limpieza."""

    data: CleanupReportResponse


# --- Endpoints ---


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=EnvelopeUploadSession,
    summary="Iniciar sesión de carga prefirmada",
    description=(
        "Solicita una sesión de carga y una URL prefirmada temporal para transferir "
        "el binario directamente a S3 sin intermediación de la API "
        "(requiere rol MEMBER o superior)."
    ),
    responses=ERROR_RESPONSES,
    dependencies=[Depends(rate_limit_dependency())],
)
def create_upload_session(
    payload: CreateUploadSessionRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    use_case: Annotated[CreateUploadSessionUseCase, Depends(get_create_upload_session_use_case)],
) -> EnvelopeUploadSession:
    result = use_case.execute(
        tenant=tenant,
        original_filename=payload.original_filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        checksum_sha256=payload.checksum_sha256,
    )
    return EnvelopeUploadSession(
        data=UploadSessionResponse(
            upload_session_id=result.upload_session_id,
            document_id=result.document_id,
            upload_url=result.upload_url,
            storage_key=result.storage_key,
            expires_in_seconds=result.expires_in_seconds,
            required_headers=result.required_headers,
        )
    )


@router.post(
    "/{session_id}/cancel",
    response_model=EnvelopeMessage,
    summary="Cancelar sesión de carga prefirmada",
    description="Cancela una sesión de carga en curso y purga objetos temporales huérfanos en S3.",
    responses=ERROR_RESPONSES,
)
def cancel_upload_session(
    session_id: Annotated[UUID, Path(description="Identificador de la sesión de carga a cancelar")],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    use_case: Annotated[CancelUploadSessionUseCase, Depends(get_cancel_upload_session_use_case)],
) -> EnvelopeMessage:
    use_case.execute(tenant=tenant, upload_session_id=session_id)
    return EnvelopeMessage(data={"message": "Sesión de carga cancelada exitosamente."})


@router.post(
    "/cleanup",
    response_model=EnvelopeCleanupReport,
    summary="Limpiar sesiones expiradas y objetos huérfanos",
    description=(
        "Expira sesiones vencidas y purga objetos temporales huérfanos en S3. "
        "Garantiza que nunca se eliminan documentos confirmados (UPLOADED, PROCESSING, READY). "
        "Requiere rol ADMIN o superior."
    ),
    responses=ERROR_RESPONSES,
)
def cleanup_expired_upload_sessions(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    use_case: Annotated[
        CleanupExpiredUploadSessionsUseCase, Depends(get_cleanup_expired_upload_sessions_use_case)
    ],
) -> EnvelopeCleanupReport:
    tenant.require_role(WorkspaceRole.ADMIN)
    report = use_case.execute(workspace_id=tenant.workspace_id)
    return EnvelopeCleanupReport(
        data=CleanupReportResponse(
            expired_sessions_count=report.expired_sessions_count,
            cleaned_objects_count=report.cleaned_objects_count,
            skipped_confirmed_documents_count=report.skipped_confirmed_documents_count,
        )
    )
