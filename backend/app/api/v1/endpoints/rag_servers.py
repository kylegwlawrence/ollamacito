"""
API endpoints for managing user-owned RAG server entries.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.db.models import RagServer, User
from app.schemas.rag_server import (
    RagServerCreate,
    RagServerListResponse,
    RagServerResponse,
    RagServerTestRequest,
    RagServerTestResponse,
    RagServerUpdate,
)
from app.services.rag_service import rag_service

router = APIRouter()
logger = get_logger(__name__)


async def _get_owned_server_or_404(
    server_id: UUID,
    user: User,
    db: AsyncSession,
) -> RagServer:
    server = (
        await db.execute(
            select(RagServer).where(
                RagServer.id == server_id, RagServer.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="RAG server not found"
        )
    return server


@router.get("", response_model=RagServerListResponse)
async def list_rag_servers(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List the current user's RAG server entries."""
    rows = (
        (
            await db.execute(
                select(RagServer)
                .where(RagServer.user_id == current_user.id)
                .order_by(RagServer.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return RagServerListResponse(
        servers=[RagServerResponse.model_validate(r) for r in rows]
    )


@router.post(
    "", response_model=RagServerResponse, status_code=status.HTTP_201_CREATED
)
async def create_rag_server(
    body: RagServerCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new RAG server entry for the current user."""
    new_server = RagServer(
        user_id=current_user.id,
        name=body.name,
        url=body.url,
        corpus_id=body.corpus_id,
    )
    db.add(new_server)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A RAG server with that name already exists.",
        ) from e
    await db.refresh(new_server)
    logger.info(f"Created RAG server {new_server.id} for user {current_user.id}")
    return RagServerResponse.model_validate(new_server)


@router.post("/test", response_model=RagServerTestResponse)
async def test_rag_server(
    body: RagServerTestRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Test a (url, corpus_id) pair against the live RAG server.

    Calls /rag/info on the URL and reports whether the requested corpus
    appears in the server's published corpus list. Connection failures
    surface as 503 via the RagConnectionError handler.
    """
    info = await rag_service.get_info(body.url)
    corpora = info.get("corpora", []) or []
    available = [c.get("id", "") for c in corpora if c.get("id")]
    return RagServerTestResponse(
        server_name=info.get("server_name"),
        server_version=info.get("server_version"),
        description=info.get("description"),
        embedding_model=info.get("embedding_model"),
        embedding_dim=info.get("embedding_dim"),
        default_top_k=info.get("default_top_k"),
        max_top_k=info.get("max_top_k"),
        article_url_template=info.get("article_url_template"),
        available_corpora=available,
        corpus_found=body.corpus_id in available,
    )


@router.get("/{server_id}", response_model=RagServerResponse)
async def get_rag_server(
    server_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    server = await _get_owned_server_or_404(server_id, current_user, db)
    return RagServerResponse.model_validate(server)


@router.patch("/{server_id}", response_model=RagServerResponse)
async def update_rag_server(
    server_id: UUID,
    body: RagServerUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    server = await _get_owned_server_or_404(server_id, current_user, db)
    if body.name is not None:
        server.name = body.name
    if body.url is not None:
        server.url = body.url
    if body.corpus_id is not None:
        server.corpus_id = body.corpus_id
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A RAG server with that name already exists.",
        ) from e
    await db.refresh(server)
    logger.info(f"Updated RAG server {server.id}")
    return RagServerResponse.model_validate(server)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rag_server(
    server_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    server = await _get_owned_server_or_404(server_id, current_user, db)
    await db.delete(server)
    await db.flush()
    logger.info(f"Deleted RAG server {server_id}")
