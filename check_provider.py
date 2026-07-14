"""Check embedding TaskMapping and Ollama provider config."""
import asyncio
import sys
sys.path.insert(0, '.')
from app.db.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        # Check TaskMapping for embedding
        r = await db.execute(text("SELECT * FROM task_mappings WHERE task_type = 'embedding'"))
        row = r.fetchone()
        if row:
            print(f'TaskMapping: {dict(row._mapping)}')
        else:
            print('No TaskMapping for embedding')
            # Show all task mappings
            r = await db.execute(text("SELECT * FROM task_mappings"))
            rows = r.fetchall()
            for row in rows:
                print(f'TaskMapping: {dict(row._mapping)}')
        
        # Check providers
        r = await db.execute(text("SELECT id, provider_id, name, vendor, api_key_value FROM ai_providers"))
        rows = r.fetchall()
        for row in rows:
            m = dict(row._mapping)
            key_preview = m['api_key_value'][:10] if m.get('api_key_value') else '(empty)'
            print(f'Provider: id={m["id"]}, provider_id={m["provider_id"]}, name={m["name"]}, vendor={m["vendor"]}, api_key={key_preview}')
        
        # Check what model is used for embedding via AIModel
        r = await db.execute(text("SELECT id, model_id, provider_id, provider_id_ref FROM ai_models WHERE model_id LIKE '%nomic%' OR model_id LIKE '%embed%'"))
        rows = r.fetchall()
        if rows:
            for row in rows:
                print(f'AIModel: {dict(row._mapping)}')
        else:
            r = await db.execute(text("SELECT id, model_id, provider_id, provider_id_ref FROM ai_models LIMIT 10"))
            rows = r.fetchall()
            for row in rows:
                print(f'AIModel: {dict(row._mapping)}')

asyncio.run(main())
