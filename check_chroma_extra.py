"""Additional ChromaDB diagnostics"""
import sqlite3, os

chroma_path = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
db_path = os.path.join(chroma_path, "chroma.sqlite3")
db = sqlite3.connect(db_path)

print("=== segment_metadata (batch_size/sync_threshold) ===")
rows = db.execute("""
    SELECT segment_id, key, int_value, str_value, float_value
    FROM segment_metadata
    WHERE key IN ('batch_size', 'sync_threshold')
    ORDER BY segment_id, key
""").fetchall()
for r in rows:
    val = r[2] if r[2] is not None else (r[3] if r[3] else r[4])
    print(f"  seg={r[0][:8]}...  {r[1]}={val}")

print("\n=== All segment_metadata ===")
rows = db.execute("SELECT segment_id, key, int_value, str_value, float_value FROM segment_metadata ORDER BY segment_id").fetchall()
for r in rows:
    val = r[2] if r[2] is not None else (r[3] if r[3] else r[4])
    print(f"  seg={r[0][:8]}...  {r[1]}={val}")

print("\n=== Check ChromaDB segment start logic ===")
chroma_dir = r"C:\Users\ze9167523\IdeaProjects\doctel\.venv\Lib\site-packages\chromadb"
segment_dir = os.path.join(chroma_dir, "segment", "impl", "vector")

# Check if local_persistent_hnsw.py exists
files = os.listdir(segment_dir) if os.path.exists(segment_dir) else []
print(f"  Vector segment impl files: {files}")

# Read the local_persistent_hnsw.py start method
hnsw_persistent = os.path.join(segment_dir, "local_persistent_hnsw.py")
if os.path.exists(hnsw_persistent):
    with open(hnsw_persistent) as f:
        content = f.read()
    # Find start and __init__ methods
    import re
    init_match = re.search(r'def __init__\(self, system, segment\):(.*?)(?=def |\Z)', content, re.DOTALL)
    start_match = re.search(r'def start\(self\):(.*?)(?=def |\Z)', content, re.DOTALL)
    stop_match = re.search(r'def stop\(self\):(.*?)(?=def |\Z)', content, re.DOTALL)
    if init_match:
        print(f"\n  __init__:\n{init_match.group(1)[:1500]}")
    if start_match:
        print(f"\n  start:\n{start_match.group(1)[:1000]}")
    if stop_match:
        print(f"\n  stop:\n{stop_match.group(1)[:1000]}")

# Also check local_hnsw.py
hnsw_local = os.path.join(segment_dir, "local_hnsw.py")
if os.path.exists(hnsw_local):
    with open(hnsw_local) as f:
        content = f.read()
    init_match = re.search(r'def __init__\(self, system, segment\):(.*?)(?=def |\Z)', content, re.DOTALL)
    start_match = re.search(r'def start\(self\):(.*?)(?=def |\Z)', content, re.DOTALL)
    stop_match = re.search(r'def stop\(self\):(.*?)(?=def |\Z)', content, re.DOTALL)
    if init_match:
        print(f"\n  LocalHnswSegment.__init__:\n{init_match.group(1)[:1000]}")
    if start_match:
        print(f"\n  LocalHnswSegment.start:\n{start_match.group(1)[:1000]}")
    if stop_match:
        print(f"\n  LocalHnswSegment.stop:\n{stop_match.group(1)[:1000]}")

db.close()
