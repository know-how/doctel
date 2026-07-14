"""Check ChromaDB operation codes and queue details."""
import chromadb
import sqlite3
from pathlib import Path

print(f"ChromaDB version: {chromadb.__version__}")

# Check operation code definitions
try:
    from chromadb.api.types import Operation
    print(f"Operation from api.types: {list(Operation)}")
except Exception as e:
    print(f"No Operation enum in api.types: {e}")

try:
    from chromadb.types import Operation
    print(f"Operation from types: {list(Operation)}")
except Exception as e:
    print(f"No Operation enum in types: {e}")

# Check for operation constants
try:
    from chromadb.api.types import ADD, UPDATE, UPSERT, DELETE
    print(f"ADD={ADD}, UPDATE={UPDATE}, UPSERT={UPSERT}, DELETE={DELETE}")
except Exception as e:
    print(f"No operation constants: {e}")

try:
    from chromadb.types import ADD, UPDATE, UPSERT, DELETE
    print(f"ADD={ADD}, UPDATE={UPDATE}, UPSERT={UPSERT}, DELETE={DELETE}")
except Exception as e:
    print(f"No operation constants in types: {e}")

# Search for the operation definitions
import chromadb.types as ct
print(f"\nchromadb.types module: {dir(ct)}")

import chromadb.api.types as cat
print(f"chromadb.api.types module: {dir(cat)}")

# Now check queue
chroma_path = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
conn = sqlite3.connect(str(Path(chroma_path) / "chroma.sqlite3"))

print("\n=== Queue topics and seq ranges ===")
cur = conn.execute("""
    SELECT operation, topic, MIN(seq_id), MAX(seq_id), COUNT(*) 
    FROM embeddings_queue 
    GROUP BY operation, topic 
    ORDER BY MIN(seq_id)
""")
for r in cur:
    topic_short = r[1].split("/")[-1][:12]
    print(f"  op={r[0]} topic={topic_short}... seq={r[2]}-{r[3]} count={r[4]}")

print("\n=== Collection -> UUID mapping ===")
cur = conn.execute("SELECT id, name FROM collections")
for r in cur:
    print(f"  {r[1]} = {r[0]}")

# Get all queue entries ordered by seq_id to see the sequence
print("\n=== First 30 queue entries (seq order) ===")
cur = conn.execute("""
    SELECT seq_id, operation, topic, created_at 
    FROM embeddings_queue 
    ORDER BY seq_id 
    LIMIT 30
""")
for r in cur:
    topic_short = r[2].split("/")[-1][:12]
    print(f"  seq={r[0]:>4} op={r[1]} collection={topic_short}... time={r[3]}")

# Last 10
print("\n=== Last 10 queue entries (seq order) ===")
cur = conn.execute("""
    SELECT seq_id, operation, topic, created_at 
    FROM embeddings_queue 
    ORDER BY seq_id DESC 
    LIMIT 10
""")
for r in reversed(cur.fetchall()):
    topic_short = r[2].split("/")[-1][:12]
    print(f"  seq={r[0]:>4} op={r[1]} collection={topic_short}... time={r[3]}")

# Check if --reload is in the environment
import os
print(f"\n=== Environment ===")
print(f"UVICORN_RELOAD: {os.environ.get('UVICORN_RELOAD', 'not set')}")

conn.close()
