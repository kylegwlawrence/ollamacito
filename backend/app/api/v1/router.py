"""
API v1 router combining all endpoint routers.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import chats, messages, models, settings

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(chats.router, prefix="/chats", tags=["chats"])
api_router.include_router(messages.router, prefix="/chats", tags=["messages"])
api_router.include_router(models.router, prefix="/ollama", tags=["ollama"])
api_router.include_router(settings.router, tags=["settings"])
