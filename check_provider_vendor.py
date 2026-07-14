"""Check provider vendor values in database."""
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text as sa_text

async def main():
    engine = create_async_engine("mysql+aiomysql://root:root@localhost:3306/doctel")
    async with engine.connect() as conn:
        # Check ai_providers
        rows = (await conn.execute(sa_text("SELECT id, name, vendor, base_url, api_key_value FROM ai_providers"))).fetchall()
        print("=== ai_providers ===")
        for r in rows:
            print(dict(r._mapping))
        
        # Check task_mappings for embedding
        try:
            rows3 = (await conn.execute(sa_text("SELECT * FROM task_mappings WHERE task_type='embedding'"))).fetchall()
            print("\n=== task_mappings (embedding) ===")
            for r in rows3:
                print(dict(r._mapping))
        except Exception as e:
            print(f"\nError querying task_mappings: {e}")
            # Try task_mapping (singular)
            try:
                rows3 = (await conn.execute(sa_text("SELECT * FROM task_mapping WHERE task_type='embedding'"))).fetchall()
                print("\n=== task_mapping (singular, embedding) ===")
                for r in rows3:
                    print(dict(r._mapping))
            except Exception as e2:
                print(f"Also error with task_mapping: {e2}")
        
        # Check ai_models for embedding
        try:
            rows2 = (await conn.execute(sa_text("SELECT id, model_id, provider_id, provider_id_ref FROM ai_models WHERE model_id LIKE '%embed%' OR model_id LIKE '%nomic%'"))).fetchall()
            print("\n=== embedding models ===")
            for r in rows2:
                print(dict(r._mapping))
        except Exception as e:
            print(f"\nError querying ai_models: {e}")
        
        # Check all models to see provider_id_ref column
        try:
            cols = (await conn.execute(sa_text("SHOW COLUMNS FROM ai_models"))).fetchall()
            print("\n=== ai_models columns ===")
            for c in cols:
                print(dict(c._mapping))
        except Exception as e:
            print(f"\nError showing columns: {e}")
    
    await engine.dispose()

asyncio.run(main())
