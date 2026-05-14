"""Add per-project RAG config and per-message RAG citations

Revision ID: 20260513_2000_abc
Revises: 20260513_1900_abc
Create Date: 2026-05-13 20:00:00.000000

Adds:
- projects.rag_enabled (bool, default false)
- projects.rag_server_url (varchar 512, nullable)
- projects.rag_corpus_id (varchar 100, nullable)
- projects.rag_top_k (int, nullable, CHECK 1..50)
- messages.rag_citations (jsonb, nullable)

See LOCAL_WIKIPEDIA_API.md for the RAG-server wire contract this enables.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260513_2000_abc"
down_revision: Union[str, None] = "20260513_1900_abc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Project RAG configuration
    op.add_column(
        "projects",
        sa.Column(
            "rag_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.alter_column("projects", "rag_enabled", server_default=None)

    op.add_column(
        "projects",
        sa.Column("rag_server_url", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("rag_corpus_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("rag_top_k", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "valid_project_rag_top_k",
        "projects",
        "rag_top_k IS NULL OR (rag_top_k BETWEEN 1 AND 50)",
    )

    # Message RAG citations (JSONB)
    op.add_column(
        "messages",
        sa.Column("rag_citations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "rag_citations")
    op.drop_constraint("valid_project_rag_top_k", "projects", type_="check")
    op.drop_column("projects", "rag_top_k")
    op.drop_column("projects", "rag_corpus_id")
    op.drop_column("projects", "rag_server_url")
    op.drop_column("projects", "rag_enabled")
