"""Add agent mode toggle and per-message tool calls

Revision ID: 20260514_1000_abc
Revises: 20260513_2000_abc
Create Date: 2026-05-14 10:00:00.000000

Adds:
- chats.agent_mode_enabled (bool, default false)
- messages.tool_calls (jsonb, nullable)

Enables the agentic chat flow where the model decides when to call
search_wikipedia rather than the backend pre-injecting RAG hits.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260514_1000_abc"
down_revision: Union[str, None] = "20260513_2000_abc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column(
            "agent_mode_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.alter_column("chats", "agent_mode_enabled", server_default=None)

    op.add_column(
        "messages",
        sa.Column(
            "tool_calls",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("messages", "tool_calls")
    op.drop_column("chats", "agent_mode_enabled")
