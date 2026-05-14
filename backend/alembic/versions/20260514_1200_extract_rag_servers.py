"""Extract RAG server config to its own user-owned table

Revision ID: 20260514_1200_abc
Revises: 20260514_1100_abc
Create Date: 2026-05-14 12:00:00.000000

Replaces the per-project rag_server_url + rag_corpus_id columns with a FK
into a new user-owned `rag_servers` table. Each row in the new table is a
(name, url, corpus_id) tuple — i.e. one entry per corpus. Existing project
RAG configs are migrated by auto-creating entries and pointing the project's
new rag_server_id at them.
"""
from typing import Sequence, Union
from urllib.parse import urlparse

import sqlalchemy as sa
from alembic import op

revision: str = "20260514_1200_abc"
down_revision: Union[str, None] = "20260514_1100_abc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. New table.
    op.create_table(
        "rag_servers",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("corpus_id", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "name", name="uq_rag_servers_user_name"),
    )
    op.create_index("ix_rag_servers_user_id", "rag_servers", ["user_id"])

    # 2. New nullable FK column on projects (no constraint yet — added after backfill).
    op.add_column(
        "projects",
        sa.Column(
            "rag_server_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # 3. Backfill: for every project with a complete (url, corpus_id) pair,
    # find or create a rag_servers row for that user and link it.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, user_id, rag_server_url, rag_corpus_id "
            "FROM projects "
            "WHERE rag_server_url IS NOT NULL AND rag_corpus_id IS NOT NULL"
        )
    ).fetchall()

    for project_id, user_id, url, corpus_id in rows:
        normalized_url = (url or "").rstrip("/")
        existing = bind.execute(
            sa.text(
                "SELECT id FROM rag_servers "
                "WHERE user_id = :user_id AND url = :url AND corpus_id = :corpus_id "
                "LIMIT 1"
            ),
            {"user_id": user_id, "url": normalized_url, "corpus_id": corpus_id},
        ).fetchone()

        if existing:
            server_id = existing[0]
        else:
            base_name = corpus_id or "rag-server"
            host = urlparse(normalized_url).hostname or ""
            candidates = [base_name]
            if host:
                candidates.append(f"{base_name} ({host})")
            for i in range(2, 100):
                candidates.append(f"{base_name}-{i}")

            chosen_name = None
            for candidate in candidates:
                clash = bind.execute(
                    sa.text(
                        "SELECT 1 FROM rag_servers "
                        "WHERE user_id = :user_id AND name = :name LIMIT 1"
                    ),
                    {"user_id": user_id, "name": candidate},
                ).fetchone()
                if not clash:
                    chosen_name = candidate
                    break
            if chosen_name is None:
                # Extremely unlikely; fall back to a UUID-suffixed name.
                chosen_name = f"{base_name}-{op.inline_literal(str(project_id))}"

            new_id = bind.execute(
                sa.text(
                    "INSERT INTO rag_servers "
                    "(id, user_id, name, url, corpus_id, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :user_id, :name, :url, :corpus_id, "
                    "now(), now()) RETURNING id"
                ),
                {
                    "user_id": user_id,
                    "name": chosen_name,
                    "url": normalized_url,
                    "corpus_id": corpus_id,
                },
            ).fetchone()
            server_id = new_id[0]

        bind.execute(
            sa.text(
                "UPDATE projects SET rag_server_id = :server_id WHERE id = :project_id"
            ),
            {"server_id": server_id, "project_id": project_id},
        )

    # 4. Add FK + index now that the column is backfilled.
    op.create_foreign_key(
        "fk_projects_rag_server_id",
        "projects",
        "rag_servers",
        ["rag_server_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_projects_rag_server_id", "projects", ["rag_server_id"]
    )

    # 5. Drop the old columns from projects.
    op.drop_column("projects", "rag_corpus_id")
    op.drop_column("projects", "rag_server_url")


def downgrade() -> None:
    # 1. Re-add the old columns (nullable).
    op.add_column(
        "projects",
        sa.Column("rag_server_url", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("rag_corpus_id", sa.String(length=100), nullable=True),
    )

    # 2. Copy values back from the linked rag_servers row.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE projects p "
            "SET rag_server_url = r.url, rag_corpus_id = r.corpus_id "
            "FROM rag_servers r "
            "WHERE p.rag_server_id = r.id"
        )
    )

    # 3. Drop the FK + index + column.
    op.drop_index("ix_projects_rag_server_id", table_name="projects")
    op.drop_constraint("fk_projects_rag_server_id", "projects", type_="foreignkey")
    op.drop_column("projects", "rag_server_id")

    # 4. Drop the table.
    op.drop_index("ix_rag_servers_user_id", table_name="rag_servers")
    op.drop_table("rag_servers")
