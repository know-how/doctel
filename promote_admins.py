"""Promote a user to admin directly in the database."""
import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal, init_db
from app.db.models import User

async def main():
    await init_db()
    async with AsyncSessionLocal() as db:
        # List all non-admin users
        result = await db.execute(select(User).where(User.role != "admin"))
        users = result.scalars().all()
        
        if not users:
            print("All users are already admins.")
            return
        
        print("Non-admin users:")
        for u in users:
            print(f"  id={u.id} username={u.username} role={u.role}")
        
        # Promote all to admin
        for u in users:
            u.role = "admin"
            db.add(u)
            print(f"Promoted {u.username} (id={u.id}) to admin")
        
        await db.commit()
        print("\nDone! All users are now admins.")
        
        # Verify
        result2 = await db.execute(select(User))
        all_users = result2.scalars().all()
        print("\nAll users:")
        for u in all_users:
            print(f"  id={u.id} username={u.username} role={u.role}")

asyncio.run(main())
