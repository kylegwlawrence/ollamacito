"""Add conversation_summarization_model and num_ctx to settings

Revision ID: 20260113_0000_abc
Revises: 20260111_2200_abc
Create Date: 2026-01-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260113_0000_abc'
down_revision: Union[str, None] = '20260111_2200_abc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add conversation_summarization_model column
    op.add_column('settings', sa.Column('conversation_summarization_model', sa.String(100), nullable=False, server_default='llama3.2:3b-instruct-q4_K_M'))

    # Add num_ctx column
    op.add_column('settings', sa.Column('num_ctx', sa.Integer(), nullable=False, server_default='2048'))

    # Add constraint for num_ctx
    op.create_check_constraint(
        'positive_num_ctx',
        'settings',
        'num_ctx > 0'
    )

    # Remove server defaults after adding columns with values
    op.alter_column('settings', 'conversation_summarization_model', server_default=None)
    op.alter_column('settings', 'num_ctx', server_default=None)


def downgrade() -> None:
    # Drop constraint
    op.drop_constraint('positive_num_ctx', 'settings', type_='check')

    # Drop columns
    op.drop_column('settings', 'num_ctx')
    op.drop_column('settings', 'conversation_summarization_model')
