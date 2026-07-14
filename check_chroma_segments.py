"""Check embeddings segment distribution and segment metadata."""
import sqlite3

chroma_path = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
conn = sqlite3.connect(chroma_path + "\\chroma.sqlite3")

# Check which segments have embeddings
print("=== Embeddings per segment ===")
cur = conn.execute("SELECT segment_id, COUNT(*) FROM embeddings GROUP BY segment_id")
for r in cur:
    print(f"  segment={r[0][:12]}... count={r[1]}")

# Check segment metadata
print("\n=== Segments metadata ===")
# First check columns
cur = conn.execute("PRAGMA table_info(segments)")
cols = [r[1] for r in cur]
print(f"  Columns: {cols}")

# Get all segments with collection mapping
cur = conn.execute("""
    SELECT s.id, s.collection, c.name, s.scope, s.type
    FROM segments s
    JOIN collections c ON s.collection = c.id
    ORDER BY c.name, s.scope
""")
for r in cur:
    # Check if metadata exists as a separate table or column
    # Try reading from segment_metadata table
    meta_cur = conn.execute(
        "SELECT key, value FROM segment_metadata WHERE segment_id = ?", 
        (r[0],)
    )
    meta = dict(meta_cur.fetchall())
    max_seq = meta.get("max_seq_id", "?")
    print(f"  seg={r[0][:12]} coll={r[2]} scope={r[3]} type={r[4]} max_seq={max_seq}")

# List all segment metadata tables
print("\n=== All tables in DB ===")
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for r in cur:
    print(f"  {r[0]}")

conn.close()
