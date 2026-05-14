"""Set default num_ctx to 4096

Revision ID: 20260513_1900_abc
Revises: 20260513_1800_abc
Create Date: 2026-05-13 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "20260513_1900_abc"
down_revision = "20260513_1800_abc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("settings", "num_ctx", server_default="4096")
    op.execute("UPDATE settings SET num_ctx = 4096 WHERE num_ctx = 2048")


def downgrade() -> None:
    op.alter_column("settings", "num_ctx", server_default="2048")
    op.execute("UPDATE settings SET num_ctx = 2048 WHERE num_ctx = 4096")
