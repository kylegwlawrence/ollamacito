"""Standalone Courses: drop project_id, add rag_server_id + rag_top_k

Revision ID: 1c4873313a79
Revises: eb4ed9f2203a
Create Date: 2026-05-15 20:04:42.714602

Decouples Course from Project. Each Course now carries its own
rag_server_id + rag_top_k. Existing rows are backfilled from their
project's RAG config before the project_id column is dropped; any row
whose project lacked RAG config is deleted (its FK becomes
unsatisfiable). The new rag_server_id FK uses ON DELETE RESTRICT —
you cannot delete a RAG server that any course depends on.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "1c4873313a79"
down_revision: Union[str, None] = "eb4ed9f2203a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1+2: Add the new columns as nullable so we can backfill.
    op.add_column(
        "courses",
        sa.Column("rag_server_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("courses", sa.Column("rag_top_k", sa.Integer(), nullable=True))

    # 3: Backfill from project.
    op.execute(
        """
        UPDATE courses
        SET rag_server_id = p.rag_server_id,
            rag_top_k = p.rag_top_k
        FROM projects p
        WHERE p.id = courses.project_id
        """
    )

    # 4: Orphans — any row whose project lacked RAG config can't satisfy the
    # NOT NULL constraint. Drop them.
    op.execute("DELETE FROM courses WHERE rag_server_id IS NULL OR rag_top_k IS NULL")

    # 5+6: Now enforce NOT NULL.
    op.alter_column("courses", "rag_server_id", nullable=False)
    op.alter_column("courses", "rag_top_k", nullable=False)

    # 7: FK with ON DELETE RESTRICT. SET NULL conflicts with NOT NULL; we
    # surface "RAG server in use" as a 4xx from the API rather than orphaning
    # the course row.
    op.create_foreign_key(
        "fk_courses_rag_server",
        "courses",
        "rag_servers",
        ["rag_server_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_courses_rag_server_id", "courses", ["rag_server_id"], unique=False
    )

    # 9-11: Drop the project_id column + its index + its FK.
    op.drop_index("ix_courses_project_id", table_name="courses")
    op.drop_constraint("courses_project_id_fkey", "courses", type_="foreignkey")
    op.drop_column("courses", "project_id")


def downgrade() -> None:
    # Restore project_id as nullable — we can't reliably reconstruct project
    # ownership from rag_server_id alone.
    op.add_column(
        "courses",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "courses_project_id_fkey",
        "courses",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_courses_project_id", "courses", ["project_id"], unique=False)

    op.drop_index("ix_courses_rag_server_id", table_name="courses")
    op.drop_constraint("fk_courses_rag_server", "courses", type_="foreignkey")
    op.drop_column("courses", "rag_top_k")
    op.drop_column("courses", "rag_server_id")
