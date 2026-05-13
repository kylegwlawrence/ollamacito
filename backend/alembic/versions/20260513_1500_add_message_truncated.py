"""Add truncated column to messages

Revision ID: 20260513_1500_abc
Revises: 20260113_0000_abc
Create Date: 2026-05-13 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260513_1500_abc'
down_revision: Union[str, None] = '20260113_0000_abc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add truncated column with server_default for existing rows
    op.add_column(
        'messages',
        sa.Column('truncated', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    # Drop the server_default once existing rows are backfilled;
    # the application supplies the value going forward.
    op.alter_column('messages', 'truncated', server_default=None)


def downgrade() -> None:
    op.drop_column('messages', 'truncated')
