"""Create an admin session directly (bypass AD auth)."""
import asyncio
import secrets
from datetime import datetime, timezone
from sqlalchemy import select
from app.db.database import AsyncSessionLocal, init_db
from app.db.models import User
from app.services.auth_service import create_session

async def main():
    await init_db()
    async with AsyncSessionLocal() as db:
        # Find admin user
        result = await db.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()
        if not user:
            result = await db.execute(select(User).where(User.role == "admin"))
            user = result.scalar_one_or_none()
        if not user:
            result = await db.execute(select(User).limit(1))
            user = result.scalar_one_or_none()
        if user:
            print(f"Found user: id={user.id} username={user.username} role={user.role}")
            token = await create_session(user.id, user.display_name or user.username, "direct", user.ec_number or user.username)
            print(f"TOKEN: {token}")
            print(f"\nUse: curl.exe -s http://127.0.0.1:8000/api/team -H 'Authorization: Bearer {token}'")
        else:
            print("No users found. Creating admin...")
            user = User(username="admin", ec_number="admin", role="admin", display_name="Admin")
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"Created admin user: id={user.id}")
            token = await create_session(user.id, "Admin", "direct", "admin")
            print(f"TOKEN: {token}")

asyncio.run(main())
