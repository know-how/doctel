"""
Standalone ChromaDB diagnostic script.
Opens the SAME path the app uses and tests count vs query.
"""
import chromadb
import random
import sys
from pathlib import Path

chroma_path = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
print(f"ChromaDB path: {chroma_path}")
print(f"Path exists: {Path(chroma_path).exists()}")
print(f"ChromaDB version: {chromadb.__version__}")

client = chromadb.PersistentClient(path=chroma_path)

# List all collections
collections = client.list_collections()
print(f"\nNumber of collections: {len(collections)}")
for c in collections:
    print(f"  Collection: '{c.name}' — count={c.count()}")

# Check project_3 specifically
try:
    coll = client.get_or_create_collection(name="project_3", metadata={"hnsw:space": "cosine"})
    cnt = coll.count()
    print(f"\nproject_3 count: {cnt}")

    if cnt > 0:
        # Try a random query with correct embedding dimension
        # nomic-embed-text is 768 dimensions
        test_vec = [random.gauss(0, 0.1) for _ in range(768)]
        res = coll.query(query_embeddings=[test_vec], n_results=min(5, cnt), include=["documents", "metadatas", "distances"])

        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]

        print(f"\nQuery results: ids={len(ids)}, docs={len(docs) if docs else 0}, metas={len(metas) if metas else 0}, distances={len(dists) if dists else 0}")

        if ids:
            for i in range(len(ids)):
                meta_str = str(metas[i]) if metas and i < len(metas) else "N/A"
                print(f"  [{i}] id={ids[i]}, dist={dists[i] if dists and i < len(dists) else 'N/A'}, meta={meta_str[:200]}")
        else:
            print("  EMPTY RESULTS — query returned 0 items!")

            # Try peek as alternative
            try:
                peek = coll.peek()
                print(f"\nPeek returned {len(peek.get('ids', []))} items")
                for i, pid in enumerate(peek.get("ids", [])):
                    print(f"  peek[{i}] id={pid}")
            except Exception as pe:
                print(f"Peek also failed: {pe}")

            # Try get as alternative
            try:
                get_all = coll.get(limit=5)
                print(f"\nGet returned {len(get_all.get('ids', []))} items")
                for i, pid in enumerate(get_all.get("ids", [])):
                    meta = get_all.get("metadatas", [])[i] if get_all.get("metadatas") else {}
                    print(f"  get[{i}] id={pid}, meta={meta}")
            except Exception as ge:
                print(f"Get also failed: {ge}")

        # Show metadata from first record
        if cnt > 0:
            try:
                get_one = coll.get(limit=1)
                if get_one.get("metadatas"):
                    print(f"\nSample metadata from get(): {get_one['metadatas'][0]}")
            except Exception as e:
                print(f"Get sample error: {e}")
    else:
        print("Collection is empty (count=0)")
except Exception as e:
    print(f"Error with project_3: {e}", file=sys.stderr)

# Also check if there are other project collections
print("\n--- Other collections ---")
for c in collections:
    if c.name != "project_3":
        try:
            c2 = client.get_collection(name=c.name)
            print(f"  '{c.name}' count={c2.count()}")
            # Try peek
            pk = c2.peek()
            print(f"    peek: {len(pk.get('ids', []))} items")
        except Exception as e2:
            print(f"  '{c.name}' error: {e2}")
