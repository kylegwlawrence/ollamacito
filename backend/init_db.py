#!/usr/bin/env python3
"""
Database initialization script.
Creates all tables in the database.
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.core.config import settings


async def init_db():
    """Create all database tables."""
    # Create async engine
    engine = create_async_engine(settings.database_url, echo=True)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("✓ Database tables created successfully")

    # Close engine
    await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(init_db())
        sys.exit(0)
    except Exception as e:
        print(f"✗ Error initializing database: {e}", file=sys.stderr)
        sys.exit(1)
