"""
API endpoints for Ollama server management.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger
from app.db.models.ollama_server import OllamaServer
from app.schemas.ollama_server import (
    OllamaServerCreate,
    OllamaServerListResponse,
    OllamaServerResponse,
    OllamaServerUpdate,
)
from app.services.ollama_service import ollama_service

router = APIRouter()
logger = get_logger(__name__)


@router.get("", response_model=OllamaServerListResponse)
async def list_servers(
    include_inactive: bool = Query(False, description="Include inactive servers"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of all Ollama servers with their health status.

    Args:
        include_inactive: Whether to include inactive servers
        db: Database session

    Returns:
        OllamaServerListResponse: List of servers
    """
    query = select(OllamaServer)
    if not include_inactive:
        query = query.where(OllamaServer.is_active == True)
    query = query.order_by(OllamaServer.name)

    result = await db.execute(query)
    servers = result.scalars().all()

    return OllamaServerListResponse(
        servers=[OllamaServerResponse.model_validate(s) for s in servers]
    )


@router.get("/{server_id}", response_model=OllamaServerResponse)
async def get_server(
    server_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get specific server details.

    Args:
        server_id: Server UUID
        db: Database session

    Returns:
        OllamaServerResponse: Server details

    Raises:
        HTTPException: If server not found
    """
    result = await db.execute(select(OllamaServer).where(OllamaServer.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Server not found"
        )

    return OllamaServerResponse.model_validate(server)


@router.post("", response_model=OllamaServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(
    server_data: OllamaServerCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create new Ollama server configuration.

    Args:
        server_data: Server creation data
        db: Database session

    Returns:
        OllamaServerResponse: Created server

    Raises:
        HTTPException: If server name already exists
    """
    # Check for duplicate name
    existing = await db.execute(
        select(OllamaServer).where(OllamaServer.name == server_data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server with this name already exists",
        )

    # Create server
    new_server = OllamaServer(
        name=server_data.name,
        tailscale_url=server_data.tailscale_url,
        description=server_data.description,
        is_active=server_data.is_active,
    )

    db.add(new_server)
    await db.flush()
    await db.refresh(new_server)

    # Test connection immediately
    logger.info(f"Testing connection to new server '{new_server.name}'")
    is_healthy, error = await ollama_service.check_health(new_server.tailscale_url)
    new_server.status = "online" if is_healthy else "offline"
    new_server.last_checked_at = datetime.now(timezone.utc)
    if not is_healthy:
        new_server.last_error = error
        logger.warning(f"New server '{new_server.name}' is not healthy: {error}")
    else:
        # Get model count if healthy
        try:
            models = await ollama_service.get_models(new_server.tailscale_url)
            new_server.models_count = len(models)
            logger.info(
                f"New server '{new_server.name}' is healthy with {len(models)} models"
            )
        except Exception as e:
            logger.warning(f"Could not fetch models for new server: {e}")

    await db.commit()
    await db.refresh(new_server)

    return OllamaServerResponse.model_validate(new_server)


@router.patch("/{server_id}", response_model=OllamaServerResponse)
async def update_server(
    server_id: UUID,
    server_data: OllamaServerUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update server configuration.

    Args:
        server_id: Server UUID
        server_data: Server update data
        db: Database session

    Returns:
        OllamaServerResponse: Updated server

    Raises:
        HTTPException: If server not found or name already exists
    """
    result = await db.execute(select(OllamaServer).where(OllamaServer.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Server not found"
        )

    # Check for duplicate name if name is being updated
    if server_data.name is not None and server_data.name != server.name:
        existing = await db.execute(
            select(OllamaServer).where(OllamaServer.name == server_data.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Server with this name already exists",
            )
        server.name = server_data.name

    # Update fields
    if server_data.tailscale_url is not None:
        server.tailscale_url = server_data.tailscale_url
        # Re-check health after URL change
        logger.info(f"URL changed for server '{server.name}', checking health")
        is_healthy, error = await ollama_service.check_health(server.tailscale_url)
        server.status = "online" if is_healthy else "offline"
        server.last_error = error
        server.last_checked_at = datetime.now(timezone.utc)

    if server_data.description is not None:
        server.description = server_data.description

    if server_data.is_active is not None:
        server.is_active = server_data.is_active

    await db.commit()
    await db.refresh(server)

    return OllamaServerResponse.model_validate(server)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete server (sets associated chats' server_id to NULL).

    Args:
        server_id: Server UUID
        db: Database session

    Raises:
        HTTPException: If server not found
    """
    result = await db.execute(select(OllamaServer).where(OllamaServer.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Server not found"
        )

    logger.info(f"Deleting server '{server.name}'")
    await db.delete(server)
    await db.commit()


@router.post("/{server_id}/check-health", response_model=OllamaServerResponse)
async def check_server_health(
    server_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger health check for specific server.

    Args:
        server_id: Server UUID
        db: Database session

    Returns:
        OllamaServerResponse: Updated server with health status

    Raises:
        HTTPException: If server not found
    """
    result = await db.execute(select(OllamaServer).where(OllamaServer.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Server not found"
        )

    # Perform health check
    logger.info(f"Manual health check for server '{server.name}'")
    start_time = datetime.now(timezone.utc)
    is_healthy, error = await ollama_service.check_health(server.tailscale_url)

    server.status = "online" if is_healthy else "offline"
    server.last_checked_at = datetime.now(timezone.utc)
    server.last_error = error

    if is_healthy:
        # Calculate response time
        response_time_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )
        server.average_response_time_ms = response_time_ms

        # Get models count
        try:
            models = await ollama_service.get_models(server.tailscale_url)
            server.models_count = len(models)
        except Exception as e:
            logger.warning(f"Could not fetch models: {e}")

    await db.commit()
    await db.refresh(server)

    return OllamaServerResponse.model_validate(server)


@router.get("/{server_id}/models")
async def list_server_models(
    server_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of models available on specific server.

    Args:
        server_id: Server UUID
        db: Database session

    Returns:
        dict: Dictionary with 'models' list

    Raises:
        HTTPException: If server not found or unavailable
    """
    result = await db.execute(select(OllamaServer).where(OllamaServer.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Server not found"
        )

    try:
        models = await ollama_service.get_models(server.tailscale_url)
        return {"models": models}
    except Exception as e:
        logger.error(f"Error retrieving models from server '{server.name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to retrieve models: {str(e)}",
        )
