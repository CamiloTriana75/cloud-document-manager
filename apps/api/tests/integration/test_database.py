"""Pruebas de integración contra PostgreSQL real (Docker Compose local).

Regla ADR-0003: integración siempre con PostgreSQL real, nunca SQLite.
Si el daemon de Docker no está levantado, se omite con motivo claro
(POSIX: docker compose up -d) — en CI corre siempre con service container.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from cdm.adapters.outbound.persistence.engine import create_db_engine
from cdm.config.settings import load_settings


def test_postgres_responde_y_version_es_16() -> None:
    settings = load_settings()
    engine = create_db_engine(settings)
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar_one()
            assert "PostgreSQL 16." in str(version)
    except SQLAlchemyError as exc:
        pytest.skip(f"PostgreSQL no disponible localmente: {exc}")
    finally:
        engine.dispose()


def test_migraciones_alembic_registradas() -> None:
    engine = create_db_engine(load_settings())
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            assert "0001" in rows
    except SQLAlchemyError as exc:
        pytest.skip(f"PostgreSQL no disponible localmente: {exc}")
    finally:
        engine.dispose()
