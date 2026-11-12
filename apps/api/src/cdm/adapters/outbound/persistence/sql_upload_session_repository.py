"""Adaptador SQLAlchemy para el repositorio de sesiones de carga (CDM-29).

Implementa UploadSessionRepositoryPort asegurando filtrado estricto por tenant.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from cdm.adapters.outbound.persistence.models import UploadSessionModel
from cdm.application.ports.upload_session_repository import UploadSessionRepositoryPort
from cdm.domain.upload_session import UploadSession, UploadSessionStatus


class SqlAlchemyUploadSessionRepository(UploadSessionRepositoryPort):
    """Implementación de UploadSessionRepositoryPort con SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, session: UploadSession) -> UploadSession:
        """Persiste una sesión de carga prefirmada."""
        model = self._session.get(UploadSessionModel, session.id)
        if model is None:
            model = UploadSessionModel.from_domain(session)
            self._session.add(model)
        else:
            model.status = session.status.value
            model.updated_at = session.updated_at
            model.expires_at = session.expires_at
            model.expected_checksum_sha256 = session.expected_checksum_sha256
        self._session.flush()
        return model.to_domain()

    def get_by_id(self, session_id: UUID, workspace_id: UUID) -> UploadSession | None:
        """Busca una sesión por su ID dentro del tenant garantizando aislamiento."""
        stmt = select(UploadSessionModel).where(
            UploadSessionModel.id == session_id,
            UploadSessionModel.workspace_id == workspace_id,
        )
        model = self._session.scalar(stmt)
        return model.to_domain() if model else None

    def get_by_document_id(self, document_id: UUID, workspace_id: UUID) -> UploadSession | None:
        """Busca la sesión asociada a un documento dentro del tenant."""
        stmt = select(UploadSessionModel).where(
            UploadSessionModel.document_id == document_id,
            UploadSessionModel.workspace_id == workspace_id,
        )
        model = self._session.scalar(stmt)
        return model.to_domain() if model else None

    def list_expired(self, workspace_id: UUID | None = None) -> list[UploadSession]:
        """Lista sesiones en estado PENDING cuya caducidad ha vencido."""
        now = datetime.now(UTC)
        stmt = select(UploadSessionModel).where(
            UploadSessionModel.status == UploadSessionStatus.PENDING.value,
            UploadSessionModel.expires_at <= now,
        )
        if workspace_id is not None:
            stmt = stmt.where(UploadSessionModel.workspace_id == workspace_id)
        models = self._session.scalars(stmt).all()
        return [m.to_domain() for m in models]
