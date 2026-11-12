"""Persistencia: fábrica de engine y sesiones SQLAlchemy (adaptador outbound).

Los casos de uso nunca ven SQLAlchemy: solo los puertos. Este módulo vive
exclusivamente en la capa de adaptadores.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from cdm.config.settings import Settings


def create_db_engine(settings: Settings, **kwargs: object) -> Engine:
    """Engine con pool razonable para API en Lambda (conexiones efímeras)."""
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=300,
        **kwargs,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Session factory transaccional: el caso de uso decide el límite."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def unit_of_work(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Delimita una transacción: commit al salir bien, rollback ante error."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
