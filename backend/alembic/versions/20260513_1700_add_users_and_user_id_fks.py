"""Add users table, user_id FKs on chats/projects, refactor settings to per-user

Revision ID: 20260513_1700_abc
Revises: 20260513_1600_abc
Create Date: 2026-05-13 17:00:00.000000

PLAN_NEW.md Phase 3 — auth scaffold. Multi-user-ready FK shape, with all
existing single-user data preserved by backfilling to a seeded "default
user" identified by a stable UUID.

`AUTH_ENABLED` defaults to false; `get_current_user` returns this default
user until Phase 7 wires real login. From the database's point of view we
are already multi-user.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260513_1700_abc"
down_revision: Union[str, None] = "20260513_1600_abc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Must agree with app.db.models.user.DEFAULT_USER_ID. Hardcoded here so the
# migration is self-contained (Alembic should not import app code that may
# change between revisions).
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_USER_EMAIL = "default@local"


def upgrade() -> None:
    # ---- 1) users table ----
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
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
    op.create_index("ix_users_email", "users", ["email"])

    # ---- 2) seed the default user so we can backfill FKs against it ----
    op.execute(
        sa.text(
            "INSERT INTO users (id, email, is_active) "
            "VALUES (CAST(:uid AS uuid), :email, true) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(uid=DEFAULT_USER_ID, email=DEFAULT_USER_EMAIL)
    )

    # ---- 3) chats.user_id (nullable add → backfill → NOT NULL) ----
    op.add_column(
        "chats",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text("UPDATE chats SET user_id = CAST(:uid AS uuid) WHERE user_id IS NULL").bindparams(
            uid=DEFAULT_USER_ID
        )
    )
    op.alter_column("chats", "user_id", nullable=False)
    op.create_foreign_key(
        "chats_user_id_fkey",
        "chats",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_chats_user_id", "chats", ["user_id"])

    # ---- 4) projects.user_id (same pattern) ----
    op.add_column(
        "projects",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text("UPDATE projects SET user_id = CAST(:uid AS uuid) WHERE user_id IS NULL").bindparams(
            uid=DEFAULT_USER_ID
        )
    )
    op.alter_column("projects", "user_id", nullable=False)
    op.create_foreign_key(
        "projects_user_id_fkey",
        "projects",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])

    # ---- 5) settings: drop the singleton, key by user_id instead ----
    #
    # 5a) Add user_id column nullable, backfill the existing singleton row
    op.add_column(
        "settings",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text("UPDATE settings SET user_id = CAST(:uid AS uuid) WHERE user_id IS NULL").bindparams(
            uid=DEFAULT_USER_ID
        )
    )
    op.alter_column("settings", "user_id", nullable=False)

    # 5b) Drop the singleton CHECK and the integer-id primary key
    op.drop_constraint("single_row_constraint", "settings", type_="check")
    op.drop_constraint("settings_pkey", "settings", type_="primary")
    op.drop_column("settings", "id")

    # 5c) Promote user_id to PK + FK to users
    op.create_primary_key("settings_pkey", "settings", ["user_id"])
    op.create_foreign_key(
        "settings_user_id_fkey",
        "settings",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # 5c reverse
    op.drop_constraint("settings_user_id_fkey", "settings", type_="foreignkey")
    op.drop_constraint("settings_pkey", "settings", type_="primary")

    # 5b reverse — restore integer id column + PK + singleton CHECK
    op.add_column(
        "settings",
        sa.Column(
            "id",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    # collapse all per-user rows back into a singleton, keeping the first one
    op.execute(
        sa.text(
            "DELETE FROM settings WHERE user_id != "
            "(SELECT user_id FROM settings ORDER BY created_at ASC LIMIT 1)"
        )
    )
    op.create_primary_key("settings_pkey", "settings", ["id"])
    op.create_check_constraint("single_row_constraint", "settings", "id = 1")

    # 5a reverse
    op.drop_column("settings", "user_id")

    # 4 reverse
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_constraint("projects_user_id_fkey", "projects", type_="foreignkey")
    op.drop_column("projects", "user_id")

    # 3 reverse
    op.drop_index("ix_chats_user_id", table_name="chats")
    op.drop_constraint("chats_user_id_fkey", "chats", type_="foreignkey")
    op.drop_column("chats", "user_id")

    # 1 reverse (the seeded default user is dropped along with the table)
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
