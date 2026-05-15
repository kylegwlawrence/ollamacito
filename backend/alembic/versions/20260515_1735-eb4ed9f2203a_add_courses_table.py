"""Add courses table

Revision ID: eb4ed9f2203a
Revises: 20260514_1200_abc
Create Date: 2026-05-15 17:35:12.849963

Adds the `courses` table backing the Course-generator feature. A Course is
scoped to a Project (FK), which carries the RAG-server config used by the
research-phase agent loop. The input (CourseGenerationRequest) is persisted as
JSONB so we can regenerate from saved parameters; the generated outline
(CourseOutline) is persisted as JSONB once generation completes.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "eb4ed9f2203a"
down_revision: Union[str, None] = "20260514_1200_abc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "GENERATING",
                "COMPLETE",
                "NEEDS_REVIEW",
                "FAILED",
                name="course_status",
            ),
            nullable=False,
        ),
        sa.Column(
            "input",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "outline",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "validation_errors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_courses_project_id"), "courses", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_courses_user_id"), "courses", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_courses_user_id"), table_name="courses")
    op.drop_index(op.f("ix_courses_project_id"), table_name="courses")
    op.drop_table("courses")
    # Drop the enum type that was implicitly created by sa.Enum above.
    sa.Enum(name="course_status").drop(op.get_bind(), checkfirst=False)
