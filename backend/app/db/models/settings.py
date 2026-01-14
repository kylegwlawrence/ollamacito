"""
Database models for application and chat settings.
"""
import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings as app_settings
from app.db.base import Base, TimestampMixin


class Settings(Base, TimestampMixin):
    """Global settings model (single row)."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    default_model: Mapped[str] = mapped_column(
        String(100),
        default=lambda: app_settings.default_model,
        nullable=False,
    )
    conversation_summarization_model: Mapped[str] = mapped_column(
        String(100),
        default=lambda: app_settings.title_generation_model,
        nullable=False,
    )
    default_temperature: Mapped[float] = mapped_column(
        Float,
        default=0.7,
        nullable=False,
    )
    default_max_tokens: Mapped[int] = mapped_column(
        Integer,
        default=2048,
        nullable=False,
    )
    num_ctx: Mapped[int] = mapped_column(
        Integer,
        default=2048,
        nullable=False,
    )
    theme: Mapped[str] = mapped_column(
        String(20),
        default="dark",
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="single_row_constraint"),
        CheckConstraint(
            "default_temperature >= 0.0 AND default_temperature <= 2.0",
            name="valid_temperature",
        ),
        CheckConstraint("default_max_tokens > 0", name="positive_tokens"),
        CheckConstraint("num_ctx > 0", name="positive_num_ctx"),
        CheckConstraint("theme IN ('dark', 'light')", name="valid_theme"),
    )

    def __repr__(self) -> str:
        return (
            f"<Settings(model={self.default_model}, "
            f"temp={self.default_temperature}, theme={self.theme})>"
        )


class ChatSettings(Base, TimestampMixin):
    """Per-chat settings model for overriding global defaults."""

    __tablename__ = "chat_settings"

    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        primary_key=True,
    )
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    chat: Mapped["Chat"] = relationship("Chat", back_populates="settings")

    __table_args__ = (
        CheckConstraint(
            "temperature IS NULL OR (temperature >= 0.0 AND temperature <= 2.0)",
            name="valid_chat_temperature",
        ),
        CheckConstraint(
            "max_tokens IS NULL OR max_tokens > 0",
            name="positive_chat_tokens",
        ),
    )

    def __repr__(self) -> str:
        return f"<ChatSettings(chat_id={self.chat_id}, temp={self.temperature})>"
