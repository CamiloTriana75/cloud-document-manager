"""Dependencias de FastAPI para inyección de persistencia y casos de uso (CDM-26).

Permite composición desacoplada y override trivial en pruebas unitarias e integración.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from cdm.adapters.outbound.persistence.repositories import (
    SqlAlchemyMembershipRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWorkspaceRepository,
)
from cdm.application.use_cases.workspaces import (
    AddWorkspaceMemberUseCase,
    CreateWorkspaceUseCase,
    ListUserWorkspacesUseCase,
    ListWorkspaceMembersUseCase,
)
from cdm.config.settings import Settings, load_settings


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


def get_create_workspace_use_case(
    session: Annotated[Session, Depends(get_db_session)],
) -> CreateWorkspaceUseCase:
    """Fábrica de dependencias para CreateWorkspaceUseCase."""
    return CreateWorkspaceUseCase(
        workspace_repo=SqlAlchemyWorkspaceRepository(session),
        membership_repo=SqlAlchemyMembershipRepository(session),
        user_repo=SqlAlchemyUserRepository(session),
    )


def get_list_user_workspaces_use_case(
    session: Annotated[Session, Depends(get_db_session)],
) -> ListUserWorkspacesUseCase:
    """Fábrica de dependencias para ListUserWorkspacesUseCase."""
    return ListUserWorkspacesUseCase(
        workspace_repo=SqlAlchemyWorkspaceRepository(session),
        membership_repo=SqlAlchemyMembershipRepository(session),
        user_repo=SqlAlchemyUserRepository(session),
    )


def get_list_workspace_members_use_case(
    session: Annotated[Session, Depends(get_db_session)],
) -> ListWorkspaceMembersUseCase:
    """Fábrica de dependencias para ListWorkspaceMembersUseCase."""
    return ListWorkspaceMembersUseCase(
        workspace_repo=SqlAlchemyWorkspaceRepository(session),
        membership_repo=SqlAlchemyMembershipRepository(session),
        user_repo=SqlAlchemyUserRepository(session),
    )


def get_add_workspace_member_use_case(
    session: Annotated[Session, Depends(get_db_session)],
) -> AddWorkspaceMemberUseCase:
    """Fábrica de dependencias para AddWorkspaceMemberUseCase."""
    return AddWorkspaceMemberUseCase(
        workspace_repo=SqlAlchemyWorkspaceRepository(session),
        membership_repo=SqlAlchemyMembershipRepository(session),
        user_repo=SqlAlchemyUserRepository(session),
    )
