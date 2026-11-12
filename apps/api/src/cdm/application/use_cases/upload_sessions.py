"""Casos de uso para sesiones de carga prefirmada (CDM-29 / AGENTS.md §8, §12).

Orquesta la validación de políticas de archivos (CDM-30), permisos de rol,
generación de URL prefirmada PUT para S3 y persistencia segura de metadatos provisionales.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from cdm.application.ports.document_repository import DocumentRepositoryPort
from cdm.application.ports.storage import StoragePort
from cdm.application.ports.upload_session_repository import UploadSessionRepositoryPort
from cdm.domain.document import Document
from cdm.domain.errors import PermissionDeniedError
from cdm.domain.file_policy import (
    generate_storage_key,
    validate_and_sanitize_filename,
    validate_checksum,
    validate_file_size,
    validate_file_type,
)
from cdm.domain.tenant import TenantContext
from cdm.domain.upload_session import UploadSession
from cdm.domain.workspace import WorkspaceRole


@dataclass(frozen=True)
class UploadSessionResult:
    """Resultado devuelto al cliente para iniciar la subida directa a S3."""

    upload_session_id: UUID
    document_id: UUID
    upload_url: str
    storage_key: str
    expires_in_seconds: int
    required_headers: dict[str, str]


class CreateUploadSessionUseCase:
    """Caso de uso: Solicitar una sesión de carga y obtener una URL prefirmada (CDM-29)."""

    def __init__(
        self,
        document_repo: DocumentRepositoryPort,
        upload_session_repo: UploadSessionRepositoryPort,
        storage: StoragePort,
        max_upload_size_bytes: int = 52428800,
        expires_in_seconds: int = 900,
    ) -> None:
        self._document_repo = document_repo
        self._upload_session_repo = upload_session_repo
        self._storage = storage
        self._max_upload_size_bytes = max_upload_size_bytes
        self._expires_in_seconds = expires_in_seconds

    def execute(
        self,
        tenant: TenantContext,
        original_filename: str,
        content_type: str,
        size_bytes: int,
        checksum_sha256: str | None = None,
    ) -> UploadSessionResult:
        """Ejecuta la creación de una sesión de carga prefirmada."""
        # 1. Autorización: Solo OWNER, ADMIN, EDITOR y MEMBER pueden subir archivos
        if tenant.role == WorkspaceRole.VIEWER:
            raise PermissionDeniedError(
                "El rol VIEWER no tiene permisos para solicitar sesiones de carga de documentos."
            )

        # 2. Validación y saneamiento del nombre de archivo (anti-path traversal)
        clean_filename = validate_and_sanitize_filename(original_filename)

        # 3. Validación de allowlist de tipo MIME y correspondencia con extensión
        clean_content_type, extension = validate_file_type(clean_filename, content_type)

        # 4. Validación de límites de tamaño
        verified_size = validate_file_size(size_bytes, self._max_upload_size_bytes)

        # 5. Validación de formato de checksum si fue provisto
        verified_checksum = validate_checksum(checksum_sha256)

        # 6. Generación de IDs y clave S3 opaca bajo prefijo de tenant
        document_id = uuid4()
        storage_key = generate_storage_key(tenant.workspace_id, document_id, extension)

        # 7. Generación de URL prefirmada para PUT directo en S3
        upload_url = self._storage.generate_upload_url(
            storage_key=storage_key,
            content_type=clean_content_type,
            size_bytes=verified_size,
            expires_in_seconds=self._expires_in_seconds,
        )

        # 8. Persistencia de registro de documento en PENDING_UPLOAD
        document = Document.create(
            workspace_id=tenant.workspace_id,
            uploaded_by=tenant.user_id,
            original_filename=clean_filename,
            storage_key=storage_key,
            content_type=clean_content_type,
            size_bytes=verified_size,
            checksum_sha256=verified_checksum,
            document_id=document_id,
        )
        self._document_repo.save(document)

        # 9. Persistencia de sesión de carga en PENDING
        upload_session = UploadSession.create(
            workspace_id=tenant.workspace_id,
            user_id=tenant.user_id,
            document_id=document_id,
            storage_key=storage_key,
            expected_size_bytes=verified_size,
            expected_content_type=clean_content_type,
            expires_in_seconds=self._expires_in_seconds,
            expected_checksum_sha256=verified_checksum,
        )
        saved_session = self._upload_session_repo.save(upload_session)

        # 10. Retorno sin credenciales AWS
        return UploadSessionResult(
            upload_session_id=saved_session.id,
            document_id=document_id,
            upload_url=upload_url,
            storage_key=storage_key,
            expires_in_seconds=self._expires_in_seconds,
            required_headers={"Content-Type": clean_content_type},
        )
