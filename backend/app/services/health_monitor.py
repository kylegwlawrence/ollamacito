"""
Health monitoring service for Ollama servers.
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.ollama_server import OllamaServer
from app.db.session import AsyncSessionLocal
from app.services.ollama_service import ollama_service

logger = get_logger(__name__)


class HealthMonitor:
    """Background service to monitor Ollama server health."""

    def __init__(self, check_interval_seconds: int = 45):
        """
        Initialize health monitor.

        Args:
            check_interval_seconds: Time between health checks (default: 45s)
        """
        self.check_interval = check_interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start the health monitoring background task."""
        if self._running:
            logger.warning("Health monitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Health monitor started (interval: {self.check_interval}s)")

    async def stop(self):
        """Stop the health monitoring background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop that runs continuously."""
        while self._running:
            try:
                await self._check_all_servers()
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")

            # Wait before next check
            await asyncio.sleep(self.check_interval)

    async def _check_all_servers(self):
        """Check health of all active servers."""
        async with AsyncSessionLocal() as session:
            try:
                # Get all active servers
                result = await session.execute(
                    select(OllamaServer).where(OllamaServer.is_active == True)
                )
                servers = result.scalars().all()

                if not servers:
                    logger.debug("No active servers to check")
                    return

                logger.info(f"Checking health of {len(servers)} server(s)")

                # Check each server
                for server in servers:
                    await self._check_server(session, server)

                # Commit all changes
                await session.commit()

            except Exception as e:
                logger.error(f"Error checking servers: {e}")
                await session.rollback()

    async def _check_server(self, session: AsyncSession, server: OllamaServer):
        """
        Check health of a single server and update database.

        Args:
            session: Database session
            server: OllamaServer instance to check
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Perform health check
            is_healthy, error_msg = await ollama_service.check_health(server.tailscale_url)

            if is_healthy:
                # Get model count
                try:
                    models = await ollama_service.get_models(server.tailscale_url)
                    models_count = len(models)
                except Exception as e:
                    logger.warning(f"Could not fetch models for {server.name}: {e}")
                    models_count = 0

                # Calculate response time
                response_time_ms = int(
                    (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                )

                # Update server status to online
                server.status = "online"
                server.last_error = None
                server.models_count = models_count
                server.last_checked_at = datetime.now(timezone.utc)
                server.average_response_time_ms = response_time_ms

                logger.info(
                    f"✓ {server.name}: online ({models_count} models, {response_time_ms}ms)"
                )
            else:
                # Server is not healthy
                server.status = "offline"
                server.last_error = error_msg
                server.last_checked_at = datetime.now(timezone.utc)

                logger.warning(f"✗ {server.name}: offline - {error_msg}")

        except Exception as e:
            # Unexpected error during health check
            server.status = "error"
            server.last_error = str(e)
            server.last_checked_at = datetime.now(timezone.utc)
            logger.error(f"✗ {server.name}: error - {e}")


# Global instance
health_monitor = HealthMonitor(check_interval_seconds=45)
