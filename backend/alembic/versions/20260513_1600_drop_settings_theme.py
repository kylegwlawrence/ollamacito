"""Drop settings.theme column

Revision ID: 20260513_1600_abc
Revises: 20260513_1500_abc
Create Date: 2026-05-13 16:00:00.000000

Light mode was scaffolded in the schema but never implemented in the
frontend. PLAN_NEW.md Phase 2 retires the half-built feature; if it ever
comes back it will be re-added deliberately.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260513_1600_abc"
down_revision: Union[str, None] = "20260513_1500_abc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("valid_theme", "settings", type_="check")
    op.drop_column("settings", "theme")


def downgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "theme",
            sa.String(20),
            server_default="dark",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "valid_theme",
        "settings",
        "theme IN ('dark', 'light')",
    )
