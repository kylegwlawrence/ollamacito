"""Add model settings to projects

Revision ID: 20260111_2200_abc
Revises: 20260111_2123_abc
Create Date: 2026-01-11 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260111_2200_abc'
down_revision: Union[str, None] = '20260111_2123_abc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add project-specific model settings columns
    op.add_column('projects', sa.Column('default_model', sa.String(100), nullable=True))
    op.add_column('projects', sa.Column('temperature', sa.Float(), nullable=True))
    op.add_column('projects', sa.Column('max_tokens', sa.Integer(), nullable=True))

    # Add constraints
    op.create_check_constraint(
        'valid_project_temperature',
        'projects',
        'temperature IS NULL OR (temperature >= 0.0 AND temperature <= 2.0)'
    )
    op.create_check_constraint(
        'positive_project_tokens',
        'projects',
        'max_tokens IS NULL OR max_tokens > 0'
    )


def downgrade() -> None:
    # Drop constraints
    op.drop_constraint('positive_project_tokens', 'projects', type_='check')
    op.drop_constraint('valid_project_temperature', 'projects', type_='check')

    # Drop columns
    op.drop_column('projects', 'max_tokens')
    op.drop_column('projects', 'temperature')
    op.drop_column('projects', 'default_model')
