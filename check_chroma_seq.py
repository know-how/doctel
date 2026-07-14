"""Check max_seq_id table and collection_metadata."""
import sqlite3

chroma_path = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
conn = sqlite3.connect(chroma_path + "\\chroma.sqlite3")

# Check max_seq_id table
print("=== max_seq_id table ===")
cur = conn.execute("PRAGMA table_info(max_seq_id)")
cols = [r[1] for r in cur]
print(f"  columns: {cols}")
cur = conn.execute("SELECT * FROM max_seq_id")
for r in cur:
    print(f"  {r}")

# Check collection_metadata
print("\n=== collection_metadata ===")
cur = conn.execute("PRAGMA table_info(collection_metadata)")
cols = [r[1] for r in cur]
print(f"  columns: {cols}")
cur = conn.execute("""
    SELECT cm.collection_id, c.name, cm.key, cm.str_value, cm.int_value, cm.float_value, cm.bool_value
    FROM collection_metadata cm
    JOIN collections c ON cm.collection_id = c.id
    ORDER BY c.name, cm.key
""")
for r in cur:
    val = r[3] if r[3] is not None else r[4] if r[4] is not None else r[5] if r[5] is not None else r[6]
    print(f"  coll={r[1]} key={r[2]} val={val}")

# Check embeddings_queue_config
print("\n=== embeddings_queue_config ===")
cur = conn.execute("PRAGMA table_info(embeddings_queue_config)")
cols = [r[1] for r in cur]
print(f"  columns: {cols}")
cur = conn.execute("SELECT * FROM embeddings_queue_config")
for r in cur:
    print(f"  {r}")

# Check maintenance_log
print("\n=== maintenance_log ===")
cur = conn.execute("PRAGMA table_info(maintenance_log)")
cols = [r[1] for r in cur]
print(f"  columns: {cols}")
cur = conn.execute("SELECT * FROM maintenance_log")
for r in cur:
    print(f"  {r}")

conn.close()
