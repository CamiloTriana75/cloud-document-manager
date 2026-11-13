"""Configuración global de pruebas para CDM API (CDM-49 / AGENTS.md §15).

Establece:
1. Variables de entorno deterministas para AWS (sin credenciales reales).
2. Protección estricta contra llamadas de red externas accidentales (anti-leak).
3. Fixtures para conexión y rollback transaccional con PostgreSQL real (ADR-0003).
4. Fábricas deterministas de entidades de dominio.
"""

from __future__ import annotations

import socket
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from cdm.adapters.outbound.persistence.engine import create_db_engine
from cdm.config.settings import load_settings
from cdm.domain.document import Document, DocumentStatus
from cdm.domain.upload_session import UploadSession, UploadSessionStatus
from cdm.domain.workspace import (
    MembershipStatus,
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
)

# --- 1. Variables de entorno seguras para pruebas (Autouse) ---


@pytest.fixture(autouse=True)
def safe_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Garantiza que ninguna credencial real de AWS sea leída durante los tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing-mock-access-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing-mock-secret-key")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing-mock-security-token")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing-mock-session-token")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("CDM_ENV", "test")
    monkeypatch.setenv("CDM_DOCUMENTS_BUCKET", "test-cdm-documents-bucket")


# --- 2. Bloqueo de llamadas de red externas accidentales (Autouse) ---


@pytest.fixture(autouse=True)
def guard_against_external_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Previene que la suite ejecute llamadas de red salientes no locales.

    Solo permite conexiones a localhost (127.0.0.1, ::1, 0.0.0.0) requeridas para
    PostgreSQL local y servidores ASGI de test. Cualquier intento hacia AWS o internet
    eleva un RuntimeError inmediato.
    """
    orig_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: Any) -> None:
        host: str = ""
        if isinstance(address, tuple) and len(address) > 0:
            host = str(address[0])
        elif isinstance(address, str):
            host = address

        # Permitir localhost, sockets UNIX, y loopback IPv4/IPv6
        allowed_hosts = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
        if host not in allowed_hosts and not host.startswith("/") and not host.startswith("\\"):
            raise RuntimeError(f"[SEGURIDAD CDM] Llamada de red bloqueada hacia: {host}:{address}")
        return orig_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


# --- 3. Fixtures para PostgreSQL real con aislamiento transaccional ---


@pytest.fixture(scope="session")
def postgres_engine() -> Generator[Engine, None, None]:
    """Crea el engine conectado a PostgreSQL real (Docker Compose o CI).

    Si la base de datos no está disponible, omite los tests de integración con un mensaje claro.
    """
    settings = load_settings()
    engine = create_db_engine(settings, connect_args={"connect_timeout": 3})
    try:
        with engine.connect():
            pass
    except SQLAlchemyError as exc:
        pytest.skip(f"PostgreSQL real no disponible para tests de integración: {exc}")

    yield engine
    engine.dispose()


@pytest.fixture
def postgres_session(postgres_engine: Engine) -> Generator[Session, None, None]:
    """Provee una sesión de SQLAlchemy sobre una transacción que siempre se revierte (rollback).

    Garantiza aislamiento total entre pruebas: los datos insertados en un test
    desaparecen al finalizar el test, manteniendo la base de datos limpia.
    """
    connection = postgres_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, autoflush=False, expire_on_commit=False)

    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


# --- 4. Fábricas deterministas de entidades de dominio ---


@pytest.fixture
def user_factory() -> Any:
    """Fábrica de entidades User para pruebas."""

    def _make(
        user_id: UUID | None = None,
        cognito_sub: str | None = None,
        email: str | None = None,
        display_name: str | None = None,
    ) -> User:
        uid = user_id or uuid4()
        return User(
            id=uid,
            cognito_sub=cognito_sub or f"sub-test-{uid}",
            email=email or f"user-{uid}@example.com",
            display_name=display_name or f"User {uid}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    return _make


@pytest.fixture
def workspace_factory(user_factory: Any) -> Any:
    """Fábrica de entidades Workspace para pruebas."""

    def _make(
        workspace_id: UUID | None = None,
        name: str | None = None,
        slug: str | None = None,
        created_by: UUID | None = None,
    ) -> Workspace:
        wid = workspace_id or uuid4()
        creator_id = created_by or uuid4()
        return Workspace(
            id=wid,
            name=name or f"Workspace {wid}",
            slug=slug or f"workspace-{wid}",
            created_by=creator_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    return _make


@pytest.fixture
def membership_factory() -> Any:
    """Fábrica de entidades WorkspaceMembership para pruebas."""

    def _make(
        membership_id: UUID | None = None,
        workspace_id: UUID | None = None,
        user_id: UUID | None = None,
        role: WorkspaceRole = WorkspaceRole.MEMBER,
        status: MembershipStatus = MembershipStatus.ACTIVE,
    ) -> WorkspaceMembership:
        return WorkspaceMembership(
            id=membership_id or uuid4(),
            workspace_id=workspace_id or uuid4(),
            user_id=user_id or uuid4(),
            role=role,
            status=status,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    return _make


@pytest.fixture
def document_factory() -> Any:
    """Fábrica de entidades Document para pruebas."""

    def _make(
        document_id: UUID | None = None,
        workspace_id: UUID | None = None,
        uploaded_by: UUID | None = None,
        original_filename: str = "documento_test.pdf",
        storage_key: str | None = None,
        content_type: str = "application/pdf",
        size_bytes: int = 1024,
        status: DocumentStatus = DocumentStatus.READY,
        technical_metadata: dict[str, Any] | None = None,
        checksum_sha256: str | None = None,
    ) -> Document:
        did = document_id or uuid4()
        wid = workspace_id or uuid4()
        return Document(
            id=did,
            workspace_id=wid,
            uploaded_by=uploaded_by or uuid4(),
            original_filename=original_filename,
            storage_key=storage_key or f"tenants/{wid}/documents/{did}/{original_filename}",
            content_type=content_type,
            size_bytes=size_bytes,
            status=status,
            technical_metadata=technical_metadata or {"page_count": 5, "pdf_version": "1.7"},
            checksum_sha256=checksum_sha256,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    return _make


@pytest.fixture
def upload_session_factory() -> Any:
    """Fábrica de entidades UploadSession para pruebas."""

    def _make(
        session_id: UUID | None = None,
        workspace_id: UUID | None = None,
        user_id: UUID | None = None,
        document_id: UUID | None = None,
        storage_key: str | None = None,
        status: UploadSessionStatus = UploadSessionStatus.PENDING,
        expected_size_bytes: int = 2048,
        expected_content_type: str = "application/pdf",
        expires_at: datetime | None = None,
    ) -> UploadSession:
        sid = session_id or uuid4()
        wid = workspace_id or uuid4()
        did = document_id or uuid4()
        return UploadSession(
            id=sid,
            workspace_id=wid,
            user_id=user_id or uuid4(),
            document_id=did,
            storage_key=storage_key or f"tenants/{wid}/documents/{did}/upload.pdf",
            expected_size_bytes=expected_size_bytes,
            expected_content_type=expected_content_type,
            status=status,
            expires_at=expires_at or (datetime.now(UTC) + timedelta(minutes=15)),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    return _make
