"""Check project_3 collection specifically"""
import chromadb

c = chromadb.PersistentClient(path=r'C:\LocalAI\data\chroma')
# Just check project_3
try:
    col = c.get_collection("project_3")
    count = col.count()
    print(f'project_3 count: {count}')
    if count > 0:
        results = col.peek()
        print(f'Sample IDs: {results["ids"][:3]}')
        print(f'Sample docs: {[d[:100] if d else "None" for d in results["documents"][:3]]}')
        print(f'Sample metadata: {results["metadatas"][:3]}')
    else:
        print('Collection is EMPTY!')
except Exception as e:
    print(f'Error: {e}')
    # Try listing all to see what's there
    all_cols = c.list_collections()
    print(f'All collections: {[(col.name, col.count()) for col in all_cols]}')

# Also check chroma.sqlite3 directly
import sqlite3
import os
db_path = r'C:\LocalAI\data\chroma\chroma.sqlite3'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f'\nSQLite tables: {[t[0] for t in tables]}')
    
    # Check collections table - get available columns first
    cursor.execute("PRAGMA table_info(collections)")
    cols = cursor.fetchall()
    print(f'\n>>> collections columns: {[(c[1], c[2]) for c in cols]}')
    
    cursor.execute("SELECT * FROM collections")
    rows = cursor.fetchall()
    print(f'>>> Collections:')
    for row in rows:
        print(f'  {row}')
    
    conn.close()
