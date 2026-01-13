#!/usr/bin/env python3
"""
Script to check and update the default_model in the settings table.
Run this from the backend directory.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import Settings
from app.core.config import settings as app_settings


async def check_and_update_settings():
    """Check current settings and optionally update them."""
    async with AsyncSessionLocal() as session:
        # Check current value
        result = await session.execute(select(Settings).where(Settings.id == 1))
        settings = result.scalar_one_or_none()

        if not settings:
            print("❌ No settings record found in database!")
            print(f"Creating new settings with default_model: {app_settings.default_model}")

            settings = Settings(
                id=1,
                default_model=app_settings.default_model,
                default_temperature=0.7,
                default_max_tokens=2048,
                theme="dark",
            )
            session.add(settings)
            await session.commit()
            print("✅ Created new settings record")
        else:
            print(f"Current default_model in database: {settings.default_model}")
            print(f"Config default_model (config.py): {app_settings.default_model}")

            if settings.default_model != app_settings.default_model:
                print(f"\n⚠️  Mismatch detected!")
                print(f"   Database has: {settings.default_model}")
                print(f"   Config has:   {app_settings.default_model}")

                response = input(f"\nUpdate database to '{app_settings.default_model}'? (y/n): ")
                if response.lower() == 'y':
                    settings.default_model = app_settings.default_model
                    await session.commit()
                    print(f"✅ Updated default_model to: {app_settings.default_model}")
                else:
                    print("❌ No changes made")
            else:
                print("✅ Database and config are in sync!")


if __name__ == "__main__":
    asyncio.run(check_and_update_settings())
