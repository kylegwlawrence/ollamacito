"""Add ollama_servers table and chat server relationship

Revision ID: 20260113_1500_abc
Revises: 20260111_2200_abc
Create Date: 2026-01-13 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260113_1500_abc'
down_revision: Union[str, None] = '20260111_2200_abc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ollama_servers table
    op.create_table(
        'ollama_servers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('tailscale_url', sa.String(512), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('status', sa.String(20), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('models_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('average_response_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create constraints
    op.create_unique_constraint('uq_ollama_servers_name', 'ollama_servers', ['name'])
    op.create_check_constraint(
        'valid_status',
        'ollama_servers',
        "status IN ('online', 'offline', 'unknown', 'error')"
    )

    # Add ollama_server_id column to chats table
    op.add_column(
        'chats',
        sa.Column('ollama_server_id', postgresql.UUID(as_uuid=True), nullable=True)
    )

    # Create foreign key constraint
    op.create_foreign_key(
        'fk_chats_ollama_server',
        'chats',
        'ollama_servers',
        ['ollama_server_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Drop foreign key
    op.drop_constraint('fk_chats_ollama_server', 'chats', type_='foreignkey')

    # Drop column from chats
    op.drop_column('chats', 'ollama_server_id')

    # Drop constraints from ollama_servers
    op.drop_constraint('valid_status', 'ollama_servers', type_='check')
    op.drop_constraint('uq_ollama_servers_name', 'ollama_servers', type_='unique')

    # Drop table
    op.drop_table('ollama_servers')
