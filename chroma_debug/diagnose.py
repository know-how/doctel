"""
COMPREHENSIVE CHROMADB STATE DIAGNOSTIC

Investigates WHY segment directories don't exist despite successful ingestion.
"""

import sqlite3
import os
import sys

CHROMA_DIR = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
DB_PATH = os.path.join(CHROMA_DIR, "chroma.sqlite3")

print("=" * 70)
print("CHROMADB COMPREHENSIVE DIAGNOSTIC")
print("=" * 70)
print(f"Chroma dir: {CHROMA_DIR}")
print(f"DB exists: {os.path.exists(DB_PATH)}")
print(f"DB size: {os.path.getsize(DB_PATH)} bytes")
print()

# ── Connect ──────────────────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ── 1. List all directories in chroma path ────────────────────────────────
print("--- Step 1: Files/Dirs in chroma path ---")
for entry in sorted(os.listdir(CHROMA_DIR)):
    full = os.path.join(CHROMA_DIR, entry)
    kind = "DIR" if os.path.isdir(full) else "FILE"
    sz = os.path.getsize(full) if os.path.isfile(full) else 0
    print(f"  [{kind:4s}] {entry} (size={sz})")
print()

# ── 2. Collections ────────────────────────────────────────────────────────
print("--- Step 2: Collections ---")
cur.execute("SELECT id, name, topic, metadata_json_str FROM collections ORDER BY id")
for r in cur.fetchall():
    seg_uuid = r["id"][:8] if r["id"] else "N/A"
    meta = r["metadata_json_str"] or ""
    # extract batch_size / sync_threshold if present
    bs = "?"
    st = "?"
    if 'batch_size' in meta:
        import re
        m = re.search(r'batch_size[^0-9]*(\d+)', meta)
        if m: bs = m.group(1)
        m = re.search(r'sync_threshold[^0-9]*(\d+)', meta)
        if m: st = m.group(1)
    print(f"  {r['id']} | name={r['name']:15s} | topic={str(r['topic']):20s} | batch={bs} sync={st}")
    # print(f"    meta={meta[:120]}")

print()

# ── 3. Segments ────────────────────────────────────────────────────────────
print("--- Step 3: Segments ---")
cur.execute("""
    SELECT s.id, s.type, s.scope, s.collection_id, s.topic, 
           m.batch_size, m.sync_threshold
    FROM segments s
    LEFT JOIN segment_metadata m ON s.id = m.segment_id
    ORDER BY s.type, s.id
""")
segments = cur.fetchall()
for r in segments:
    print(f"  type={str(r['type']):7s} scope={str(r['scope']):12s} | seg_id={r['id']} | coll_id={str(r['collection_id'])[:12]} | batch={r['batch_size']} sync={r['sync_threshold']}")
print(f"  TOTAL: {len(segments)} segments")
print()

# ── 4. VECTOR segment directories on disk ────────────────────────────────
print("--- Step 4: VECTOR segment dirs on disk ---")
cur.execute("SELECT id, collection_id, topic FROM segments WHERE type='VECTOR'")
vec_segs = cur.fetchall()
for r in vec_segs:
    seg_dir = os.path.join(CHROMA_DIR, r['id'])
    exists = os.path.isdir(seg_dir)
    files = []
    if exists:
        files = os.listdir(seg_dir)
    print(f"  seg={r['id']} coll={str(r['collection_id'])[:12]} dir_exists={exists} files={files}")
print()

# ── 5. HNSW file check ──────────────────────────────────────────────────
print("--- Step 5: HNSW file check ---")
for r in vec_segs:
    seg_dir = os.path.join(CHROMA_DIR, r['id'])
    if os.path.isdir(seg_dir):
        for fname in ["header.bin", "link_lists.bin"]:
            fpath = os.path.join(seg_dir, fname)
            sz = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
            print(f"  {r['id'][:12]}/{fname}: {sz} bytes")
    else:
        print(f"  {r['id'][:12]}/ (NO SEGMENT DIR)")
print()

# ── 6. Embeddings count per collection via topic ─────────────────────────
print("--- Step 6: Embedding counts by collection topic ---")
cur.execute("""
    SELECT s.collection_id, c.name, c.topic, COUNT(e.id) as emb_count
    FROM segments s
    LEFT JOIN embeddings e ON e.segment_id = s.id
    LEFT JOIN collections c ON s.collection_id = c.id
    WHERE s.type = 'VECTOR'
    GROUP BY s.collection_id
""")
for r in cur.fetchall():
    print(f"  coll={str(r['collection_id'])[:12]} name={str(r['name']):15s} topic={str(r['topic']):20s} emb_count={r['emb_count']}")
print()

# ── 7. Queue (should be 0 after fix, check anyway) ──────────────────────
print("--- Step 7: Embeddings Queue ---")
cur.execute("SELECT COUNT(*) as cnt FROM embeddings_queue")
cnt = cur.fetchone()["cnt"]
cur.execute("SELECT MIN(seq_id) as min_s, MAX(seq_id) as max_s FROM embeddings_queue")
r2 = cur.fetchone()
print(f"  queue entries: {cnt}  (seq_id range: {r2['min_s']} - {r2['max_s']})")
print()

# ── 8. max_seq_id table ─────────────────────────────────────────────────
print("--- Step 8: max_seq_id ---")
cur.execute("SELECT segment_id, seq_id FROM max_seq_id")
for r in cur.fetchall():
    print(f"  segment={r['segment_id'][:24]} seq_id={r['seq_id']}")
print()

# ── 9. Server PID and runtime info ──────────────────────────────────────
print("--- Step 9: Server Process Check ---")
try:
    import psutil
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            cmd = proc.info['cmdline']
            if cmd and ('uvicorn' in str(cmd).lower() or 'main.py' in str(cmd).lower() or 'docintel' in str(cmd).lower()):
                import datetime
                ct = datetime.datetime.fromtimestamp(proc.info['create_time'])
                print(f"  PID {proc.info['pid']}: cmd={cmd[:3]}... started={ct}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
except ImportError:
    print("  (psutil not available)")
print()

conn.close()
