"""Add memory column to projects

Revision ID: 20260514_1100_abc
Revises: 20260514_1000_abc
Create Date: 2026-05-14 11:00:00.000000

Adds:
- projects.memory (text, nullable) — user-curated project memory document.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260514_1100_abc"
down_revision: Union[str, None] = "20260514_1000_abc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("memory", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "memory")
