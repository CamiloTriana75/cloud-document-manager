"""Creación de tabla upload_sessions para sesiones de carga prefirmada (CDM-29 / AGENTS.md §10).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("expected_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("expected_content_type", sa.String(length=100), nullable=False),
        sa.Column("expected_checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_upload_sessions_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_upload_sessions_user_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_upload_sessions_document_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_upload_sessions"),
        sa.UniqueConstraint("storage_key", name="uq_upload_sessions_storage_key"),
    )
    op.create_index(
        "ix_upload_sessions_workspace_id", "upload_sessions", ["workspace_id"], unique=False
    )
    op.create_index("ix_upload_sessions_user_id", "upload_sessions", ["user_id"], unique=False)
    op.create_index(
        "ix_upload_sessions_document_id", "upload_sessions", ["document_id"], unique=False
    )
    op.create_index(
        "ix_upload_sessions_expires_at", "upload_sessions", ["expires_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_upload_sessions_expires_at", table_name="upload_sessions")
    op.drop_index("ix_upload_sessions_document_id", table_name="upload_sessions")
    op.drop_index("ix_upload_sessions_user_id", table_name="upload_sessions")
    op.drop_index("ix_upload_sessions_workspace_id", table_name="upload_sessions")
    op.drop_table("upload_sessions")
