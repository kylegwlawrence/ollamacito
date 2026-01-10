"""
Database models package.
Import all models here for Alembic to detect them.
"""
from app.db.models.chat import Chat, Message
from app.db.models.settings import ChatSettings, Settings

__all__ = ["Chat", "Message", "Settings", "ChatSettings"]
