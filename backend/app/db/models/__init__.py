"""
Database models package.
Import all models here for Alembic to detect them.
"""

from app.db.models.chat import Chat, Message
from app.db.models.project import Project, ProjectFile
from app.db.models.rag_server import RagServer
from app.db.models.settings import ChatSettings, Settings
from app.db.models.user import DEFAULT_USER_EMAIL, DEFAULT_USER_ID, User

__all__ = [
    "Chat",
    "ChatSettings",
    "DEFAULT_USER_EMAIL",
    "DEFAULT_USER_ID",
    "Message",
    "Project",
    "ProjectFile",
    "RagServer",
    "Settings",
    "User",
]
