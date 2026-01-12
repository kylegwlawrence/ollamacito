"""Initial schema

Revision ID: 005bd22e40f1
Revises:
Create Date: 2026-01-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005bd22e40f1'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration represents the existing database schema
    # No operations needed as tables already exist
    pass


def downgrade() -> None:
    # Not implemented - this is the initial migration
    pass
