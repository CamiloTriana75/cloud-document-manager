"""Entorno Alembic: URL desde Settings (CDM_DATABASE_URL), nunca hardcoded."""

from alembic import context
from sqlalchemy import Engine

from cdm.adapters.outbound.persistence.engine import create_db_engine
from cdm.adapters.outbound.persistence.models import Base
from cdm.config.settings import load_settings

config = context.config
target_metadata = Base.metadata


def _engine() -> Engine:
    return create_db_engine(load_settings())


def run_migrations_offline() -> None:
    """Genera SQL sin conexión (--sql)."""
    context.configure(
        url=load_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica migraciones contra PostgreSQL real."""
    with _engine().connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
