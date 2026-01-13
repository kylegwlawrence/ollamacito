"""
Database model for Ollama servers.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.chat import Chat


class OllamaServer(Base, TimestampMixin):
    """Ollama server configuration and health status."""

    __tablename__ = "ollama_servers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    tailscale_url: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Health monitoring fields
    status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    models_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    chats: Mapped[List["Chat"]] = relationship(
        "Chat",
        back_populates="ollama_server",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('online', 'offline', 'unknown', 'error')",
            name="valid_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<OllamaServer(id={self.id}, name={self.name}, status={self.status})>"
