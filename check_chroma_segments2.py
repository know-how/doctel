"""Fix segment metadata query and check max_seq_id."""
import sqlite3

chroma_path = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
conn = sqlite3.connect(chroma_path + "\\chroma.sqlite3")

# Check segment_metadata columns
cur = conn.execute("PRAGMA table_info(segment_metadata)")
cols = [r[1] for r in cur]
print(f"segment_metadata columns: {cols}")

# Check all data in segment_metadata
cur = conn.execute("SELECT * FROM segment_metadata")
rows = cur.fetchall()
print(f"\nsegment_metadata rows ({len(rows)}):")
for r in rows[:50]:
    print(f"  {r}")

# Now match segments to collections
print("\n=== Segment to collection mapping ===")
cur = conn.execute("""
    SELECT s.id, c.name, s.scope, s.type
    FROM segments s
    JOIN collections c ON s.collection = c.id
    ORDER BY c.name, s.scope
""")
for r in cur:
    # Get metadata
    meta_cur = conn.execute(
        "SELECT key, bool_value, str_value, int_value, float_value FROM segment_metadata WHERE segment_id = ?",
        (r[0],)
    )
    meta_rows = meta_cur.fetchall()
    meta = {}
    for mr in meta_rows:
        key = mr[0]
        val = mr[1] if mr[1] is not None else mr[2] if mr[2] is not None else mr[3] if mr[3] is not None else mr[4]
        meta[key] = val
    max_seq = meta.get("max_seq_id", "?")
    print(f"  seg={r[0][:12]} coll={r[1]} scope={r[2]} type={r[3]} max_seq={max_seq}")

conn.close()
