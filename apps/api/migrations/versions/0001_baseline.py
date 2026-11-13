"""Base vacía: el esquema de dominio se define en CDM-40.

Revision ID: 0001
Revises:
Create Date: 2026-11-12
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Marca el punto de partida del ciclo de migraciones."""
    pass


def downgrade() -> None:
    pass
