"""Check the real ChromaDB at C:\LocalAI\data\chroma"""
import chromadb

c = chromadb.PersistentClient(path=r'C:\LocalAI\data\chroma')
all_cols = c.list_collections()
print(f'All collections:')
for col in all_cols:
    print(f'  {col.name}: {col.count()} items')

# Try specific collection names
for name in ['3', 'project_3', 'documents', 'chunks', 'default']:
    try:
        col = c.get_or_create_collection(name)
        count = col.count()
        if count > 0:
            print(f'\nCollection "{name}" count: {count}')
            results = col.peek()
            print(f'  Sample IDs: {results["ids"][:3]}')
            print(f'  Sample docs: {[d[:80] if d else "None" for d in results["documents"][:3]]}')
        else:
            print(f'\nCollection "{name}" exists but is empty')
    except Exception as e:
        print(f'\nError with collection "{name}": {e}')

# List chroma.sqlite3 size
import os
sqlite_path = r'C:\LocalAI\data\chroma\chroma.sqlite3'
if os.path.exists(sqlite_path):
    size = os.path.getsize(sqlite_path)
    print(f'\nchroma.sqlite3 size: {size} bytes ({size/1024:.1f} KB)')
else:
    print('\nNo chroma.sqlite3 found!')
