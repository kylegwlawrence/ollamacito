"""Add auto_attach_all_files to projects

Revision ID: 20260513_1800_abc
Revises: 20260513_1700_abc
Create Date: 2026-05-13 18:00:00.000000

PLAN_NEW.md Phase 6 — selective per-message file attachment.

A project may opt into "auto-attach all files" (frontend UX: pre-select
all files on every new message). Default false for ALL projects (existing
+ new) per the plan: every project migrates to selective by default.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260513_1800_abc"
down_revision: Union[str, None] = "20260513_1700_abc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "auto_attach_all_files",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    # Drop the server_default once existing rows are backfilled; the ORM
    # provides the value going forward.
    op.alter_column("projects", "auto_attach_all_files", server_default=None)


def downgrade() -> None:
    op.drop_column("projects", "auto_attach_all_files")
