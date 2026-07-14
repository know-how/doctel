"""Check ChromaDB state after ingestion."""
import chromadb

c = chromadb.PersistentClient(path='data/chroma')
cols = c.list_collections()
print(f'Collections: {cols}')
for col in cols:
    count = col.count()
    print(f'  {col.name}: {count} items')
    if count > 0:
        results = col.peek()
        print(f'  First 3 IDs: {results["ids"][:3]}')
        print(f'  First doc preview: {results["documents"][0][:100] if results["documents"] else "None"}')
