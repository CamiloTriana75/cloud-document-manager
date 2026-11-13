"""Entorno Alembic: URL configurable desde Config o Settings (CDM_DATABASE_URL)."""

from alembic import context
from sqlalchemy import Engine, create_engine

from cdm.adapters.outbound.persistence.models import Base
from cdm.config.settings import load_settings

config = context.config
target_metadata = Base.metadata


def _get_url() -> str:
    cfg_url = config.get_main_option("sqlalchemy.url")
    if cfg_url and cfg_url.strip():
        return cfg_url.strip()
    return load_settings().database_url


def _engine() -> Engine:
    return create_engine(_get_url())


def run_migrations_offline() -> None:
    """Genera SQL sin conexión (--sql)."""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica migraciones contra la base de datos configurada."""
    connection = config.attributes.get("connection", None)
    if connection is not None:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    with _engine().connect() as conn:
        context.configure(
            connection=conn,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
