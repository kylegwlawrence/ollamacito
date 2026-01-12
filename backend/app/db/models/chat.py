"""
Database models for chats and messages.
"""
import uuid
from typing import List, Optional

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


# Junction table for many-to-many relationship between messages and files
message_files = Table(
    "message_files",
    Base.metadata,
    Column("message_id", UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    Column("file_id", UUID(as_uuid=True), ForeignKey("project_files.id", ondelete="CASCADE"), primary_key=True, nullable=False),
)


class Chat(Base, TimestampMixin):
    """Chat model representing a conversation."""

    __tablename__ = "chats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Relationships
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    settings: Mapped[Optional["ChatSettings"]] = relationship(
        "ChatSettings",
        back_populates="chat",
        cascade="all, delete-orphan",
        uselist=False,
    )
    project: Mapped[Optional["Project"]] = relationship(
        "Project",
        back_populates="chats",
    )

    def __repr__(self) -> str:
        return f"<Chat(id={self.id}, title={self.title}, model={self.model})>"


class Message(Base, TimestampMixin):
    """Message model representing a single message in a chat."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")
    attached_files: Mapped[List["ProjectFile"]] = relationship(
        "ProjectFile",
        secondary=message_files,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role}, chat_id={self.chat_id})>"
