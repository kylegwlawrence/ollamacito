"""
Database model for user-owned RAG server entries.

Each row pairs a (url, corpus_id) so a user can pre-define every corpus they
want to query and pick one per project from a dropdown — instead of typing the
URL + corpus into every project's settings.
"""

import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.project import Project
    from app.db.models.user import User


class RagServer(Base, TimestampMixin):
    """A saved RAG server + corpus pair owned by a single user."""

    __tablename__ = "rag_servers"

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
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    corpus_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="rag_servers")
    projects: Mapped[List["Project"]] = relationship(
        "Project",
        back_populates="rag_server",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_rag_servers_user_name"),
    )

    def __repr__(self) -> str:
        return f"<RagServer(id={self.id}, name={self.name}, corpus_id={self.corpus_id})>"
