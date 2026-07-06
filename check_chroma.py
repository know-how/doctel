"""Check ChromaDB state."""
import chromadb

c = chromadb.PersistentClient(path="C:/LocalAI/data/chroma/")
for col in c.list_collections():
    print(f"{col.name}: {col.count()} items")
    if col.count() > 0:
        items = col.peek()
        print(f"  Sample: {items}")
