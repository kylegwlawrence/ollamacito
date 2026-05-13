"""
User model.

Per PLAN_NEW.md Phase 3, this is the FK shape that lets later phases drop
multi-user auth in cleanly. Until Phase 7 wires real login, the
`get_current_user` dependency returns a singleton "default user" row (id =
`DEFAULT_USER_ID` below) so all existing single-user behavior keeps working.
"""
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.chat import Chat
    from app.db.models.project import Project
    from app.db.models.settings import Settings


# Stable UUID used to seed the singleton "default user" when AUTH_ENABLED=false.
# Keeping it as a constant means migrations and the runtime agree on a single ID.
DEFAULT_USER_ID: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_EMAIL: str = "default@local"


class User(Base, TimestampMixin):
    """An application user.

    With AUTH_ENABLED=false (default) only the singleton default user exists
    and every endpoint resolves to it. Phase 7 will add real signup / login
    and use the `hashed_password` field.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # Nullable so the seeded default user can exist without a credential
    # while AUTH_ENABLED=false. Phase 7 will populate it on first real login.
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    chats: Mapped[List["Chat"]] = relationship(
        "Chat",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    projects: Mapped[List["Project"]] = relationship(
        "Project",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    settings: Mapped[Optional["Settings"]] = relationship(
        "Settings",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, active={self.is_active})>"
