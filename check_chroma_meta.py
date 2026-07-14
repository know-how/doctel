"""Quick ChromaDB metadata inspection."""
import sqlite3
from pathlib import Path

chroma_path = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
sqlite_file = Path(chroma_path) / "chroma.sqlite3"

conn = sqlite3.connect(str(sqlite_file))

# Document IDs
print("=== Document IDs in embedding_metadata ===")
cur = conn.execute("SELECT DISTINCT int_value FROM embedding_metadata WHERE key='document_id'")
for row in cur:
    print(f"  document_id={row[0]}")

# Embeddings table - which metadata segments have embeddings?
print("\n=== Embeddings by segment ===")
cur = conn.execute("""
    SELECT e.segment_id, s.type, s.collection, c.name, COUNT(*) as cnt
    FROM embeddings e
    JOIN segments s ON e.segment_id = s.id
    JOIN collections c ON s.collection = c.id
    GROUP BY e.segment_id
""")
for row in cur:
    print(f"  {row[4]} embeddings in {row[3]} ({row[1]})")

# Which metadata segments have NO embeddings?
print("\n=== Metadata segments with 0 embeddings ===")
cur = conn.execute("""
    SELECT s.id, c.name
    FROM segments s
    JOIN collections c ON s.collection = c.id
    WHERE s.type LIKE '%metadata%'
    AND s.id NOT IN (SELECT DISTINCT segment_id FROM embeddings)
""")
for row in cur:
    print(f"  {row[1]} (segment {row[0][:12]}...)")

# Check embedding_queue - how many pending operations?
print("\n=== Embeddings Queue ===")
cur = conn.execute("SELECT operation, COUNT(*) FROM embeddings_queue GROUP BY operation")
for row in cur:
    op = {0: "ADD", 1: "UPDATE", 2: "DELETE"}.get(row[0], f"UNKNOWN({row[0]})")
    print(f"  {op}: {row[1]} entries")

# Check queue config
print("\n=== Queue Config ===")
cur = conn.execute("SELECT * FROM embeddings_queue_config")
for row in cur:
    print(f"  {row}")

# Check embedding_metadata - how many for document_id=2 (Dunning Manual)?
print("\n=== Document 2 (Dunning Manual) metadata count ===")
cur = conn.execute("SELECT COUNT(*) FROM embedding_metadata WHERE id IN (SELECT id FROM embedding_metadata WHERE key='document_id' AND int_value=2)")
print(f"  {cur.fetchone()[0]} metadata entries")

# Check unique chunks for doc 2
print("\n=== Document 2 chunk count ===")
cur = conn.execute("""
    SELECT COUNT(DISTINCT int_value) FROM embedding_metadata 
    WHERE key='chunk_index' AND id IN (
        SELECT id FROM embedding_metadata WHERE key='document_id' AND int_value=2
    )
""")
print(f"  {cur.fetchone()[0]} unique chunks")

# Check chroma:document count
print("\n=== Chroma document entries ===")
cur = conn.execute("""
    SELECT COUNT(*) FROM embedding_metadata 
    WHERE key='chroma:document' AND id IN (
        SELECT id FROM embedding_metadata WHERE key='document_id' AND int_value=2
    )
""")
print(f"  Document 2: {cur.fetchone()[0]} full-text entries")

conn.close()
