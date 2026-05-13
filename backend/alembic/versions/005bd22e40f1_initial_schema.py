"""Initial schema

Revision ID: 005bd22e40f1
Revises:
Create Date: 2026-01-08 00:00:00.000000

Backfilled in PLAN_NEW.md Phase 2 (2026-05-13).

Represents the canonical starting schema. Prior to this backfill the file
was a no-op `pass` stub; the real schema came from `postgres/init.sql`
plus implicit table creation via `Base.metadata.create_all` in the FastAPI
lifespan. Both of those secondary sources are being retired in this phase.

This migration creates:

- chats, messages, settings (with `theme`, dropped in a later Phase 2
  migration), chat_settings (from the original `init.sql`)
- projects, project_files (without `content`) — these had been getting
  created by `create_all` despite not being in `init.sql`. They belong
  before migration 20260111_2123 in the chain because that migration
  assumes both tables already exist.

Deliberate omissions:
- the `update_updated_at_column()` SQL trigger — `TimestampMixin`
  (`backend/app/db/base.py`) implements `onupdate=lambda: datetime.now(...)`
  at the ORM layer, which covers all writes through SQLAlchemy.
- the `chats_with_stats` SQL view — never referenced anywhere in the
  codebase.

Existing dev DBs should run `alembic stamp 005bd22e40f1` (or `head`) once
to mark themselves as up-to-date without re-running CREATE TABLE.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005bd22e40f1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- projects (no FK dependencies) ----
    op.create_table(
        "projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("custom_instructions", sa.Text(), nullable=True),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    # ---- chats (FK to projects) ----
    op.create_table(
        "chats",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("idx_chats_created_at", "chats", [sa.text("created_at DESC")])
    op.create_index("idx_chats_archived", "chats", ["is_archived"])

    # ---- messages (FK to chats) ----
    op.create_table(
        "messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "chat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="valid_message_role",
        ),
    )
    op.create_index("idx_messages_chat_id", "messages", ["chat_id"])
    op.create_index("idx_messages_created_at", "messages", [sa.text("created_at DESC")])
    op.create_index(
        "idx_messages_chat_created",
        "messages",
        ["chat_id", sa.text("created_at DESC")],
    )

    # ---- settings (singleton; `theme` will be dropped in a follow-up migration) ----
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "default_model",
            sa.String(100),
            server_default="qwen2.5-coder:14b",
            nullable=False,
        ),
        sa.Column(
            "default_temperature",
            sa.Float(),
            server_default=sa.text("0.7"),
            nullable=False,
        ),
        sa.Column(
            "default_max_tokens",
            sa.Integer(),
            server_default=sa.text("2048"),
            nullable=False,
        ),
        sa.Column(
            "theme",
            sa.String(20),
            server_default="dark",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="single_row_constraint"),
        sa.CheckConstraint(
            "default_temperature >= 0.0 AND default_temperature <= 2.0",
            name="valid_temperature",
        ),
        sa.CheckConstraint("default_max_tokens > 0", name="positive_tokens"),
        sa.CheckConstraint(
            "theme IN ('dark', 'light')",
            name="valid_theme",
        ),
    )

    # ---- chat_settings (per-chat overrides; FK to chats) ----
    op.create_table(
        "chat_settings",
        sa.Column(
            "chat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "temperature IS NULL OR (temperature >= 0.0 AND temperature <= 2.0)",
            name="valid_chat_temperature",
        ),
        sa.CheckConstraint(
            "max_tokens IS NULL OR max_tokens > 0",
            name="positive_chat_tokens",
        ),
    )

    # ---- project_files (FK to projects; `content` is added by 20260111_2123) ----
    op.create_table(
        "project_files",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("content_preview", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("project_files")
    op.drop_table("chat_settings")
    op.drop_table("settings")
    op.drop_index("idx_messages_chat_created", table_name="messages")
    op.drop_index("idx_messages_created_at", table_name="messages")
    op.drop_index("idx_messages_chat_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("idx_chats_archived", table_name="chats")
    op.drop_index("idx_chats_created_at", table_name="chats")
    op.drop_table("chats")
    op.drop_table("projects")
