"""Add override_model, override_temperature, override_num_ctx to courses

Revision ID: a3f1e2b4c5d6
Revises: 1c4873313a79
Create Date: 2026-05-15 21:00:00.000000

Nullable columns — existing courses inherit global user settings at
generation time (the service falls back to user_settings.* when null).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a3f1e2b4c5d6"
down_revision: Union[str, None] = "1c4873313a79"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("override_model", sa.String(128), nullable=True))
    op.add_column(
        "courses", sa.Column("override_temperature", sa.Float(), nullable=True)
    )
    op.add_column(
        "courses", sa.Column("override_num_ctx", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("courses", "override_num_ctx")
    op.drop_column("courses", "override_temperature")
    op.drop_column("courses", "override_model")
