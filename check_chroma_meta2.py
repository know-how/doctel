"""Diagnose metadata storage and WAL state."""
import sqlite3
import os
import json

chroma_path = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
conn = sqlite3.connect(chroma_path + "\\chroma.sqlite3")

# All tables
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print("=== All tables ===")
for r in cur:
    # count rows
    cnt = conn.execute(f"SELECT COUNT(*) FROM \"{r[0]}\"").fetchone()[0]
    print(f"  {r[0]}: {cnt} rows")

# Collections config
print("\n=== Collections config ===")
cur = conn.execute("SELECT name, dimension, database_id, config_json_str FROM collections ORDER BY name")
for r in cur:
    cfg = r[3]
    if cfg and len(cfg) > 80:
        cfg = cfg[:80] + "..."
    print(f"  {r[0]}: dim={r[1]} db={r[2][:8]}... config={cfg}")

# Check segment_metadata more carefully - maybe it uses different column names
print("\n=== segment_metadata raw data ===")
cur = conn.execute("SELECT * FROM segment_metadata LIMIT 20")
cols = [d[0] for d in cur.description]
print(f"  columns: {cols}")
for r in cur:
    print(f"  {r}")

# Check if metadata is embedded in collections.config_json_str
print("\n=== Parsed config_json_str ===")
cur = conn.execute("SELECT name, config_json_str FROM collections ORDER BY name")
for r in cur:
    if r[1]:
        try:
            parsed = json.loads(r[1])
            print(f"  {r[0]}: {json.dumps(parsed, indent=2)[:200]}")
        except:
            print(f"  {r[0]}: (invalid json) {r[1][:100]}")
    else:
        print(f"  {r[0]}: (empty)")

# Check the embeddings segment metadata stored in the VECTOR segment config
print("\n=== VECTOR segments config config_json_str ===")
cur = conn.execute("""
    SELECT c.name, s.scope, s.type
    FROM segments s
    JOIN collections c ON s.collection = c.id
    WHERE s.scope = 'VECTOR'
    ORDER BY c.name
""")
# Try to find where the segment stores its metadata
cur2 = conn.execute("PRAGMA table_info(segments)")
print("segments columns:", [r[1] for r in cur2])

# Check if segments table has hidden columns
cur2 = conn.execute("SELECT * FROM segments LIMIT 5")
print("\nSegments full data:")
for r in cur2:
    print(f"  {r}")

# WAL state
print("\n=== WAL state ===")
cur = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
print(f"  checkpoint: {cur.fetchone()}")

# Walk dirs for empty index files
print("\n=== Index files check ===")
for root, dirs, files in os.walk(chroma_path):
    for f in files:
        if f in ('link_lists.bin', 'header.bin'):
            fp = os.path.join(root, f)
            size = os.path.getsize(fp)
            status = "EMPTY" if size == 0 else f"{size} bytes"
            if size < 100:
                print(f"  {status}: {os.path.relpath(fp, chroma_path)}")

conn.close()
