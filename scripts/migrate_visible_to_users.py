"""
Migration: Add visible_to_users columns to ai_providers and ai_models.

Run with:
  python -m scripts.migrate_visible_to_users
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.database import engine


async def migrate():
    async with engine.begin() as conn:
        # Add visible_to_users to ai_providers
        try:
            await conn.execute(text(
                "ALTER TABLE ai_providers ADD COLUMN visible_to_users BOOLEAN NOT NULL DEFAULT TRUE"
            ))
            print("✓ Added visible_to_users to ai_providers")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print("○ visible_to_users already exists on ai_providers")
            else:
                raise

        # Add visible_to_users to ai_models
        try:
            await conn.execute(text(
                "ALTER TABLE ai_models ADD COLUMN visible_to_users BOOLEAN NOT NULL DEFAULT TRUE"
            ))
            print("✓ Added visible_to_users to ai_models")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print("○ visible_to_users already exists on ai_models")
            else:
                raise

    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
