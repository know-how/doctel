"""Check what documents are indexed in the system."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text as sa_text

async def main():
    engine = create_async_engine('mysql+aiomysql://root:@localhost:3306/doctel')
    async with engine.connect() as conn:
        # First DESCRIBE the table
        cols = (await conn.execute(sa_text('DESCRIBE documents'))).fetchall()
        print('=== DOCUMENTS COLUMNS ===')
        for c in cols:
            print(dict(c._mapping))
        
        # List all documents
        rows = (await conn.execute(
            sa_text('SELECT id, filename, project_id, embedding_model, embedding_provider FROM documents ORDER BY id')
        )).fetchall()
        print('\n=== DOCUMENTS ===')
        for r in rows:
            print(dict(r._mapping))
        
        # Count chunks per document
        rows2 = (await conn.execute(
            sa_text('SELECT d.id AS doc_id, d.filename, COUNT(c.id) AS chunk_count FROM documents d LEFT JOIN chunks c ON c.document_id = d.id GROUP BY d.id ORDER BY d.id')
        )).fetchall()
        print('\n=== CHUNK COUNTS ===')
        for r in rows2:
            print(dict(r._mapping))
        
        # Check if there's a "Dunning" document
        rows3 = (await conn.execute(
            sa_text("SELECT id, filename FROM documents WHERE filename LIKE '%Dunning%' OR filename LIKE '%dunning%'")
        )).fetchall()
        print('\n=== DUNNING DOCUMENTS ===')
        for r in rows3:
            print(dict(r._mapping))
        if not rows3:
            print("(none found)")
        
        # Check projects
        rows4 = (await conn.execute(
            sa_text('SELECT id, name FROM projects ORDER BY id')
        )).fetchall()
        print('\n=== PROJECTS ===')
        for r in rows4:
            print(dict(r._mapping))
    
    await engine.dispose()

asyncio.run(main())
