"""Temporary script to check document ingestion status."""
import asyncio
import sys
sys.path.insert(0, '.')
from app.db.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as s:
        # Chunk columns
        r = await s.execute(text('SELECT name FROM pragma_table_info("chunks")'))
        cols = r.fetchall()
        print('=== CHUNKS COLUMNS ===')
        for c in cols:
            print(f'  {c[0]}')
        
        # Chunk count
        r = await s.execute(text('SELECT count(*) FROM chunks'))
        print(f'Total chunks: {r.scalar()}')
        
        r = await s.execute(text('SELECT id, document_id, chunk_index, length(text) as txt_len FROM chunks LIMIT 5'))
        rows = r.fetchall()
        if rows:
            for row in rows:
                print(f'  ID={row[0]}, doc_id={row[1]}, chunk_index={row[2]}, text_len={row[3]}')
        
        # Doc analysis count
        r = await s.execute(text('SELECT count(*) FROM doc_analysis'))
        analysis_count = r.scalar()
        print(f'Doc analysis records: {analysis_count}')
        
        if analysis_count > 0:
            r = await s.execute(text('SELECT id, document_id FROM doc_analysis LIMIT 5'))
            rows = r.fetchall()
            for row in rows:
                print(f'  Analysis ID={row[0]}, doc_id={row[1]}')
        
        # Document details
        r = await s.execute(text('''
            SELECT d.id, d.filename, d.status, d.ingestion_completed, 
                   d.ingestion_failed, d.ingest_step, d.ingest_percent
            FROM documents d
        '''))
        rows = r.fetchall()
        print(f'\n=== DOCUMENT INGESTION STATUS ===')
        for row in rows:
            print(f'  ID={row[0]}, file={row[1][:50]}')
            print(f'    status={row[2]}, completed={row[3]}, failed={row[4]}')
            print(f'    step={row[5]}, percent={row[6]}')

asyncio.run(check())
