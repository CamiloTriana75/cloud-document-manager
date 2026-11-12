"""Dependencias de FastAPI: persistencia, contexto de tenant y casos de uso (CDM-26/27).

Permite composición desacoplada y override trivial en pruebas unitarias e integración.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Path
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from cdm.adapters.inbound.http.auth import get_current_user
from cdm.adapters.outbound.persistence.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyMembershipRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWorkspaceRepository,
)
from cdm.adapters.outbound.persistence.sql_upload_session_repository import (
    SqlAlchemyUploadSessionRepository,
)
from cdm.adapters.outbound.storage.s3_storage import S3StorageAdapter
from cdm.application.ports.storage import StoragePort
from cdm.application.use_cases.documents import (
    AuthorizeDocumentDownloadUseCase,
    CreateDocumentRecordUseCase,
    DeleteDocumentUseCase,
    GetDocumentDetailUseCase,
    ListDocumentsUseCase,
)
from cdm.application.use_cases.upload_sessions import (
    CreateUploadSessionUseCase,
)
from cdm.application.use_cases.workspaces import (
    AddWorkspaceMemberUseCase,
    CreateWorkspaceUseCase,
    ListUserWorkspacesUseCase,
    ListWorkspaceMembersUseCase,
)
from cdm.config.settings import Settings, load_settings
from cdm.domain.errors import WorkspaceNotFoundError
from cdm.domain.identity import AuthenticatedUser
from cdm.domain.tenant import TenantContext
from cdm.domain.workspace import MembershipStatus


@lru_cache
def _get_engine(database_url: str) -> Engine:
    """Crea y cachea un engine por URL de base de datos."""
    is_sqlite = database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    return create_engine(
        database_url,
        pool_pre_ping=not is_sqlite,
        pool_size=5 if not is_sqlite else None,
        max_overflow=5 if not is_sqlite else None,
        pool_recycle=300 if not is_sqlite else -1,
        connect_args=connect_args,
    )


def get_db_session(
    settings: Annotated[Settings, Depends(load_settings)],
) -> Iterator[Session]:
    """Generador de sesión SQLAlchemy transaccional por request."""
    engine = _get_engine(settings.database_url)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_tenant_context(
    workspace_id: Annotated[UUID, Path(description="Identificador único del workspace")],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> TenantContext:
    """Resuelve y verifica la pertenencia del usuario al workspace.

    CRITICAL RULE (CDM-27 / AGENTS.md §3.1):
    tenant_id se obtiene de una membresía verificada en base de datos.
    Si el usuario no es miembro activo del workspace especificado, se lanza
    WorkspaceNotFoundError (404), impidiendo la divulgación de recursos o existencia (anti-IDOR).
    """
    user_repo = SqlAlchemyUserRepository(session)
    membership_repo = SqlAlchemyMembershipRepository(session)

    user = user_repo.get_by_cognito_sub(current_user.cognito_sub)
    if user is None:
        raise WorkspaceNotFoundError(
            "El espacio de trabajo solicitado no existe o no tiene acceso a él."
        )

    membership = membership_repo.get_by_workspace_and_user(
        workspace_id=workspace_id, user_id=user.id
    )
    if membership is None or membership.status != MembershipStatus.ACTIVE:
        raise WorkspaceNotFoundError(
            "El espacio de trabajo solicitado no existe o no tiene acceso a él."
        )

    return TenantContext(
        workspace_id=workspace_id,
        user_id=user.id,
        user_email=user.email,
        role=membership.role,
        status=membership.status,
    )


def get_storage_port(
    settings: Annotated[Settings, Depends(load_settings)],
) -> StoragePort:
    """Fábrica para el adaptador de almacenamiento S3."""
    return S3StorageAdapter(
        bucket_name=settings.s3_bucket_name,
        region=settings.s3_region,
    )


# --- Fábricas de Casos de Uso: Workspaces ---


def get_create_workspace_use_case(
    session: Annotated[Session, Depends(get_db_session)],
) -> CreateWorkspaceUseCase:
    return CreateWorkspaceUseCase(
        workspace_repo=SqlAlchemyWorkspaceRepository(session),
        membership_repo=SqlAlchemyMembershipRepository(session),
        user_repo=SqlAlchemyUserRepository(session),
    )


def get_list_user_workspaces_use_case(
    session: Annotated[Session, Depends(get_db_session)],
) -> ListUserWorkspacesUseCase:
    return ListUserWorkspacesUseCase(
        workspace_repo=SqlAlchemyWorkspaceRepository(session),
        membership_repo=SqlAlchemyMembershipRepository(session),
        user_repo=SqlAlchemyUserRepository(session),
    )


def get_list_workspace_members_use_case(
    session: Annotated[Session, Depends(get_db_session)],
) -> ListWorkspaceMembersUseCase:
    return ListWorkspaceMembersUseCase(
        workspace_repo=SqlAlchemyWorkspaceRepository(session),
        membership_repo=SqlAlchemyMembershipRepository(session),
        user_repo=SqlAlchemyUserRepository(session),
    )


def get_add_workspace_member_use_case(
    session: Annotated[Session, Depends(get_db_session)],
) -> AddWorkspaceMemberUseCase:
    return AddWorkspaceMemberUseCase(
        workspace_repo=SqlAlchemyWorkspaceRepository(session),
        membership_repo=SqlAlchemyMembershipRepository(session),
        user_repo=SqlAlchemyUserRepository(session),
    )


# --- Fábricas de Casos de Uso: Documentos ---


def get_list_documents_use_case(
    session: Annotated[Session, Depends(get_db_session)],
) -> ListDocumentsUseCase:
    return ListDocumentsUseCase(
        document_repo=SqlAlchemyDocumentRepository(session),
    )


def get_document_detail_use_case(
    session: Annotated[Session, Depends(get_db_session)],
) -> GetDocumentDetailUseCase:
    return GetDocumentDetailUseCase(
        document_repo=SqlAlchemyDocumentRepository(session),
    )


def get_authorize_document_download_use_case(
    session: Annotated[Session, Depends(get_db_session)],
    storage: Annotated[StoragePort, Depends(get_storage_port)],
) -> AuthorizeDocumentDownloadUseCase:
    return AuthorizeDocumentDownloadUseCase(
        document_repo=SqlAlchemyDocumentRepository(session),
        storage_service=storage,
    )


def get_delete_document_use_case(
    session: Annotated[Session, Depends(get_db_session)],
) -> DeleteDocumentUseCase:
    return DeleteDocumentUseCase(
        document_repo=SqlAlchemyDocumentRepository(session),
    )


def get_create_document_record_use_case(
    session: Annotated[Session, Depends(get_db_session)],
) -> CreateDocumentRecordUseCase:
    return CreateDocumentRecordUseCase(
        document_repo=SqlAlchemyDocumentRepository(session),
    )


def get_create_upload_session_use_case(
    session: Annotated[Session, Depends(get_db_session)],
    storage: Annotated[StoragePort, Depends(get_storage_port)],
    settings: Annotated[Settings, Depends(load_settings)],
) -> CreateUploadSessionUseCase:
    return CreateUploadSessionUseCase(
        document_repo=SqlAlchemyDocumentRepository(session),
        upload_session_repo=SqlAlchemyUploadSessionRepository(session),
        storage=storage,
        max_upload_size_bytes=settings.max_upload_size_bytes,
        expires_in_seconds=settings.upload_url_expires_in_seconds,
    )
