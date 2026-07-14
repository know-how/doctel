"""Check queue timeline by day."""
import sqlite3

chroma_path = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
conn = sqlite3.connect(chroma_path + "\\chroma.sqlite3")

# Check embeddings count per collection
print("=== Embeddings per collection ===")
cur = conn.execute("""
    SELECT c.name, COUNT(e.id)
    FROM collections c
    LEFT JOIN embeddings e ON e.segment_id = (
        SELECT s.id FROM segments s WHERE s.collection = c.id AND s.scope = 'VECTOR' LIMIT 1
    )
    GROUP BY c.id
    ORDER BY c.name
""")
for r in cur:
    print(f"  {r[0]}: {r[1]} embeddings")

# Queue summary by date and operation
print("\n=== Queue entries by date ===")
cur = conn.execute("""
    SELECT DATE(created_at) as day, operation, COUNT(*) as cnt
    FROM embeddings_queue
    GROUP BY day, operation
    ORDER BY day, operation
""")
for r in cur:
    op_type = "UPSERT" if r[1] == 2 else ("DELETE" if r[1] == 3 else f"UNKNOWN({r[1]})")
    print(f"  {r[0]}: {op_type} x {r[2]}")

# Check embeddings table directly
print("\n=== Direct embeddings check ===")
cur = conn.execute("SELECT COUNT(*) FROM embeddings")
print(f"  Total rows in embeddings table: {cur.fetchone()[0]}")

cur = conn.execute("SELECT COUNT(*) FROM embedding_metadata")
print(f"  Total rows in embedding_metadata: {cur.fetchone()[0]}")

# Check the segment metadata for max_seq_id per collection
print("\n=== Segment metadata (per collection processing status) ===")
cur = conn.execute("""
    SELECT s.id, s.collection, c.name, s.scope, 
           json_extract(s.metadata, '$.max_seq_id') as max_seq_id
    FROM segments s
    JOIN collections c ON s.collection = c.id
    ORDER BY c.name, s.scope
""")
for r in cur:
    print(f"  coll={r[2]} scope={r[3]} max_seq_id={r[4]}")
    # max_seq_id tells us how far the background thread got!

conn.close()
