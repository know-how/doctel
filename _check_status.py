"""Check document status quickly."""
import asyncio
import sys
sys.path.insert(0, r'c:\Users\ze9167523\IdeaProjects\doctel')
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine('mysql+aiomysql://root:@localhost:3306/doctel')
    async with engine.connect() as conn:
        row = (await conn.execute(
            text('SELECT id, filename, status, ingest_step, ingest_percent, ingest_message, error_message, ingestion_started, ingestion_completed, ingestion_failed, updated_at FROM documents WHERE id=2')
        )).first()
        if row:
            print(dict(row._mapping))
        else:
            print('Doc 2 not found')
    await engine.dispose()

asyncio.run(main())
