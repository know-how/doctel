"""
COMPREHENSIVE CHROMADB STATE DIAGNOSTIC v2
Fixes the column name issues.
"""

import sqlite3
import os
import re
import sys

CHROMA_DIR = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
DB_PATH = os.path.join(CHROMA_DIR, "chroma.sqlite3")

print("=" * 70)
print("CHROMADB COMPREHENSIVE DIAGNOSTIC v2")
print("=" * 70)
print(f"Chroma dir: {CHROMA_DIR}")
print(f"DB exists: {os.path.exists(DB_PATH)}")
print(f"DB size: {os.path.getsize(DB_PATH)} bytes")
print()

# ── Connect ──────────────────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ── 0. Table schemas ────────────────────────────────────────────────────
print("--- Step 0: Table schemas ---")
for tbl in ['collections', 'segments', 'segment_metadata', 'embeddings', 'embeddings_queue', 'max_seq_id']:
    try:
        cur.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{tbl}'")
        r = cur.fetchone()
        if r:
            print(f"  {tbl}: {r[0]}")
    except Exception as e:
        print(f"  {tbl}: ERROR {e}")
print()

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
cur.execute("SELECT * FROM collections ORDER BY id")
col_columns = [d[0] for d in cur.description]
print(f"  columns: {col_columns}")
for r in cur.fetchall():
    row = dict(r)
    cid = row.get('id', '?')
    name = row.get('name', '?')
    meta = str(row.get('metadata_json_str', row.get('metadata_json', '')) or '')
    # extract batch_size / sync_threshold if present
    bs = "?"
    st = "?"
    if 'batch_size' in meta:
        m = re.search(r'batch_size[^0-9]*(\d+)', meta)
        if m: bs = m.group(1)
        m = re.search(r'sync_threshold[^0-9]*(\d+)', meta)
        if m: st = m.group(1)
    print(f"  {cid} | name={name} | batch={bs} sync={st}")
    # print(f"    meta={meta[:200]}")
print()

# ── 3. Segments ────────────────────────────────────────────────────────────
print("--- Step 3: Segments ---")
try:
    cur.execute("""
        SELECT s.id, s.type, s.scope, s.collection_id,
               COALESCE(m.batch_size, -1) as batch_size,
               COALESCE(m.sync_threshold, -1) as sync_threshold
        FROM segments s
        LEFT JOIN segment_metadata m ON s.id = m.segment_id
        ORDER BY s.type, s.id
    """)
    seg_columns = [d[0] for d in cur.description]
    print(f"  columns: {seg_columns}")
    segments = cur.fetchall()
    for r in segments:
        d = dict(r)
        print(f"  type={str(d['type']):7s} scope={str(d['scope']):12s} | seg_id={d['id']} | "
              f"coll_id={str(d['collection_id'])[:16]} | batch={d['batch_size']} sync={d['sync_threshold']}")
    print(f"  TOTAL: {len(segments)} segments")
except Exception as e:
    print(f"  ERROR: {e}")
print()

# ── 4. VECTOR segment directories on disk ────────────────────────────────
print("--- Step 4: VECTOR segment dirs on disk ---")
try:
    cur.execute("SELECT id, collection_id FROM segments WHERE type='VECTOR'")
    vec_segs = cur.fetchall()
    for r in vec_segs:
        d = dict(r)
        seg_dir = os.path.join(CHROMA_DIR, d['id'])
        exists = os.path.isdir(seg_dir)
        files = []
        if exists:
            files = os.listdir(seg_dir)
        print(f"  seg={d['id']} coll={str(d['collection_id'])[:16]} dir_exists={exists} files={files}")
except Exception as e:
    print(f"  ERROR: {e}")
print()

# ── 5. HNSW file check ──────────────────────────────────────────────────
print("--- Step 5: HNSW file check ---")
try:
    cur.execute("SELECT id FROM segments WHERE type='VECTOR'")
    for r in cur.fetchall():
        d = dict(r)
        seg_dir = os.path.join(CHROMA_DIR, d['id'])
        if os.path.isdir(seg_dir):
            for fname in ["header.bin", "link_lists.bin"]:
                fpath = os.path.join(seg_dir, fname)
                sz = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
                print(f"  {d['id'][:16]}/{fname}: {sz} bytes")
        else:
            print(f"  {d['id'][:16]}/ (NO SEGMENT DIR)")
except Exception as e:
    print(f"  ERROR: {e}")
print()

# ── 6. Embeddings count per segment ─────────────────────────────────────
print("--- Step 6: Embedding counts by segment ---")
try:
    cur.execute("""
        SELECT s.collection_id, c.name, s.id as seg_id, COUNT(e.id) as emb_count
        FROM segments s
        LEFT JOIN embeddings e ON e.segment_id = s.id
        LEFT JOIN collections c ON s.collection_id = c.id
        WHERE s.type = 'VECTOR'
        GROUP BY s.collection_id, s.id
    """)
    for r in cur.fetchall():
        d = dict(r)
        print(f"  coll={str(d['collection_id'])[:16]} name={str(d['name'])[:20]} seg={d['seg_id'][:16]} emb_count={d['emb_count']}")
except Exception as e:
    print(f"  ERROR: {e}")
print()

# ── 7. Queue ─────────────────────────────────────────────────────────────
print("--- Step 7: Embeddings Queue ---")
try:
    cur.execute("SELECT COUNT(*) as cnt FROM embeddings_queue")
    cnt = cur.fetchone()['cnt']
    if cnt > 0:
        cur.execute("SELECT MIN(seq_id) as min_s, MAX(seq_id) as max_s FROM embeddings_queue")
        r2 = cur.fetchone()
        print(f"  queue entries: {cnt}  (seq_id range: {r2['min_s']} - {r2['max_s']})")
    else:
        print(f"  queue entries: {cnt}")
except Exception as e:
    print(f"  ERROR: {e}")
print()

# ── 8. max_seq_id ───────────────────────────────────────────────────────
print("--- Step 8: max_seq_id ---")
try:
    cur.execute("SELECT segment_id, seq_id FROM max_seq_id")
    for r in cur.fetchall():
        d = dict(r)
        print(f"  segment={d['segment_id'][:24]} seq_id={d['seq_id']}")
except Exception as e:
    print(f"  ERROR: {e}")
print()

# ── 9. Embeddings sample ────────────────────────────────────────────────
print("--- Step 9: Embeddings sample (first 5 rows) ---")
try:
    cur.execute("SELECT id, segment_id, seq_id, embedding_id FROM embeddings LIMIT 5")
    for r in cur.fetchall():
        d = dict(r)
        print(f"  id={d['id']} seg={str(d['segment_id'])[:16]} seq_id={d['seq_id']} emb_id={d['embedding_id']}")
except Exception as e:
    print(f"  ERROR: {e}")
print()

conn.close()
