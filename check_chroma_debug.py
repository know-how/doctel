"""Check current ChromaDB state — segment dirs, SQLite linkage, process info"""
import sqlite3, os, sys

chroma_path = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
db_path = os.path.join(chroma_path, "chroma.sqlite3")

print(f"Python: {sys.version}")
print(f"Chroma path: {chroma_path}")
print(f"DB exists: {os.path.exists(db_path)}")

# Check segment directories
print("\n=== Segment directories ===")
for item in os.listdir(chroma_path):
    full = os.path.join(chroma_path, item)
    if os.path.isdir(full):
        print(f"  DIR: {item}/")

if not any(os.path.isdir(os.path.join(chroma_path, x)) for x in os.listdir(chroma_path)):
    print("  *** NO segment directories exist! ***")

# Check UUID dirs recursively
print("\n=== Recursive UUID dir search ===")
import re
uuid_pat = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
found = []
for root, dirs, files in os.walk(chroma_path):
    for d in dirs:
        if uuid_pat.match(d):
            found.append(os.path.join(root, d))
if found:
    for f in found:
        print(f"  {f}")
        print(f"    Contents: {os.listdir(f)}")
else:
    print("  NO UUID-named directories found anywhere under chroma path")

# SQLite checks
print("\n=== SQLite checks ===")
db = sqlite3.connect(db_path)

# Embeddings per segment
print("\nEmbeddings per segment (with collection name):")
rows = db.execute("""
    SELECT e.segment_id, s.type, c.name, COUNT(*) as cnt
    FROM embeddings e
    JOIN segments s ON e.segment_id = s.id
    JOIN collections c ON s.collection = c.id
    GROUP BY e.segment_id
""").fetchall()
for r in rows:
    print(f"  seg={r[0][:8]}...  type={r[1][:60]:60s}  coll={r[2]:20s}  cnt={r[3]}")

# All segments
print("\nAll segments:")
rows = db.execute("""
    SELECT id, type, scope, collection,
        (SELECT name FROM collections WHERE id = segments.collection) as cname
    FROM segments ORDER BY type
""").fetchall()
for r in rows:
    print(f"  id={r[0][:8]}...  type={r[1][:60]:60s}  scope={r[2]:10s}  coll={r[3][:8]}...({r[4]})")

# VECTOR segment embeddings count
print("\nVECTOR segment embedding counts:")
rows = db.execute("""
    SELECT s.id, c.name,
        (SELECT COUNT(*) FROM embeddings e WHERE e.segment_id = s.id) as emb_count
    FROM segments s
    JOIN collections c ON s.collection = c.id
    WHERE s.type = 'urn:chroma:segment/vector/hnsw-local-persisted'
    ORDER BY c.name
""").fetchall()
for r in rows:
    print(f"  seg={r[0][:8]}...  coll={r[1]:20s}  emb_count={r[2]}")

# max_seq_id
print("\nmax_seq_id:")
rows = db.execute("""
    SELECT m.segment_id, s.type, m.seq_id
    FROM max_seq_id m
    JOIN segments s ON m.segment_id = s.id
""").fetchall()
for r in rows:
    print(f"  seg={r[0][:8]}...  type={r[1][:60]:60s}  seq_id={r[2]}")

# Counts
print(f"\nTotal embeddings: {db.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0]}")
print(f"Emb queue: {db.execute('SELECT COUNT(*) FROM embeddings_queue').fetchone()[0]}")
print(f"Collections: {db.execute('SELECT COUNT(*) FROM collections').fetchone()[0]}")

# Check segment_metadata
print("\nsegment_metadata (key fields):")
rows = db.execute("""
    SELECT segment_id, key, value
    FROM segment_metadata
    WHERE key IN ('batch_size', 'sync_threshold')
    ORDER BY segment_id, key
""").fetchall()
for r in rows:
    print(f"  seg={r[0][:8]}...  {r[1]}={r[2]}")

db.close()
