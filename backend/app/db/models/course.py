"""
Database model for generated course outlines.

A Course is a single generated educational outline scoped to a Project. The
Project carries the RAG-server config (corpus + URL + top_k) used by the
agent's `search_wikipedia` tool during the research phase of generation, so a
Course implicitly inherits its source corpus from its Project.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.project import Project
    from app.db.models.user import User


class CourseStatus(str, enum.Enum):
    """Lifecycle states for a generated course outline."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETE = "complete"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class Course(Base, TimestampMixin):
    """A generated course outline scoped to a Project."""

    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[CourseStatus] = mapped_column(
        SAEnum(CourseStatus, name="course_status"),
        nullable=False,
        default=CourseStatus.PENDING,
    )

    # Serialized CourseGenerationRequest. Persisted at creation time and reused
    # on regenerate. Treated as opaque JSONB at the DB layer; validated against
    # the Pydantic schema in the service layer.
    input: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Serialized CourseOutline. Null until generation completes (or until a
    # regenerate resets the row back to pending).
    outline: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # List of {path, msg} dicts surfaced by `validate_outline`. Non-empty
    # entries set status=needs_review rather than rejecting the result.
    validation_errors: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    model_used: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships (unidirectional; User/Project don't need a courses list today)
    user: Mapped["User"] = relationship("User")
    project: Mapped["Project"] = relationship("Project")

    def __repr__(self) -> str:
        return f"<Course(id={self.id}, title={self.title}, status={self.status.value})>"
