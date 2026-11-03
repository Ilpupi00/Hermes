"""Persist the effective chunk size for each execution.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "esecuzione",
        sa.Column(
            "chunk_size",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1000"),
        ),
    )
    op.create_check_constraint(
        "ck_esecuzione_chunk_size",
        "esecuzione",
        "chunk_size > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_esecuzione_chunk_size", "esecuzione", type_="check"
    )
    op.drop_column("esecuzione", "chunk_size")
