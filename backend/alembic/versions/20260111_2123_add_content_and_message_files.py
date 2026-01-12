"""Add content to project_files and create message_files junction table

Revision ID: 20260111_2123_abc
Revises: 005bd22e40f1
Create Date: 2026-01-11 21:23:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260111_2123_abc'
down_revision: Union[str, None] = '005bd22e40f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add content column to project_files
    op.add_column('project_files', sa.Column('content', sa.Text(), nullable=True))

    # Create message_files junction table
    op.create_table('message_files',
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['project_files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('message_id', 'file_id')
    )


def downgrade() -> None:
    # Drop message_files junction table
    op.drop_table('message_files')

    # Remove content column from project_files
    op.drop_column('project_files', 'content')
