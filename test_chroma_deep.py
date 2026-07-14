"""
Deep ChromaDB SQLite inspection to understand the HNSW index state.
"""
import sqlite3
from pathlib import Path

chroma_path = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
sqlite_file = Path(chroma_path) / "chroma.sqlite3"

print(f"SQLite file: {sqlite_file}")
print(f"SQLite file size: {sqlite_file.stat().st_size} bytes\n")

conn = sqlite3.connect(str(sqlite_file))

# Dump ALL table schemas
print("=== ALL Table Schemas ===")
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
for t in tables:
    tname = t[0]
    cursor2 = conn.execute(f"PRAGMA table_info(\"{tname}\")")
    cols = cursor2.fetchall()
    cursor3 = conn.execute(f"SELECT COUNT(*) FROM \"{tname}\"")
    count = cursor3.fetchone()[0]
    print(f"\n  {tname}: {count} rows")
    for c in cols:
        print(f"    {c}")

# Dump ALL data from collections
print("\n\n=== ALL Collection Data ===")
try:
    cursor = conn.execute("SELECT * FROM collections")
    for row in cursor:
        print(f"  {row}")
except Exception as e:
    print(f"  Error: {e}")

# Dump segments 
print("\n\n=== ALL Segment Data ===")
try:
    cursor = conn.execute("SELECT * FROM segments")
    for row in cursor:
        print(f"  {row}")
except Exception as e:
    print(f"  Error: {e}")

# Dump embedding metadata
print("\n\n=== ALL Embedding Metadata ===")
try:
    cursor = conn.execute("SELECT * FROM embedding_metadata")
    for row in cursor:
        print(f"  {row}")
except Exception as e:
    print(f"  Error: {e}")

# Check segment files on disk
print("\n\n=== Segment Files on Disk ===")
for seg_dir in sorted(Path(chroma_path).iterdir()):
    if seg_dir.is_dir():
        segment_id = seg_dir.name
        files = list(seg_dir.iterdir())
        for f in sorted(files):
            print(f"  {segment_id[:12]}.../{f.name}  size={f.stat().st_size}")

conn.close()
