"""
Database models package.
Import all models here for Alembic to detect them.
"""
from app.db.models.chat import Chat, Message
from app.db.models.ollama_server import OllamaServer
from app.db.models.project import Project, ProjectFile
from app.db.models.settings import ChatSettings, Settings

__all__ = [
    "Chat",
    "Message",
    "OllamaServer",
    "Settings",
    "ChatSettings",
    "Project",
    "ProjectFile",
]
