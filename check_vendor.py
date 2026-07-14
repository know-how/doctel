"""Quick script to check provider vendor."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text as sa_text

async def main():
    engine = create_async_engine("mysql+aiomysql://root:@localhost:3306/doctel")
    async with engine.connect() as conn:
        rows = (await conn.execute(sa_text("SELECT id, name, vendor, base_url, api_key_value FROM ai_providers"))).fetchall()
        print("=== ai_providers ===")
        for r in rows:
            print(dict(r._mapping))
        
        rows2 = (await conn.execute(sa_text("SELECT id, model_id, provider_id FROM ai_models WHERE model_id LIKE '%nomic%' OR model_id LIKE '%embed%'"))).fetchall()
        print("\n=== embedding models ===")
        for r in rows2:
            print(dict(r._mapping))
        
        rows3 = (await conn.execute(sa_text("SELECT * FROM task_mappings WHERE task_type='embedding'"))).fetchall()
        print("\n=== task_mappings ===")
        for r in rows3:
            print(dict(r._mapping))
    await engine.dispose()

asyncio.run(main())
