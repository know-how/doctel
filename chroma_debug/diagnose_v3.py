"""
COMPREHENSIVE CHROMADB STATE DIAGNOSTIC v3
Fixes the column name issues (collection not collection_id).
"""

import sqlite3
import os
import re

CHROMA_DIR = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
DB_PATH = os.path.join(CHROMA_DIR, "chroma.sqlite3")

print("=" * 70)
print("CHROMADB DIAGNOSTIC v3")
print("=" * 70)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ── 1. Segments table ────────────────────────────────────────────────────
print("\n--- Segments ---")
cur.execute("SELECT * FROM segments ORDER BY type, id")
seg_columns = [d[0] for d in cur.description]
print(f"  columns: {seg_columns}")
segs = cur.fetchall()
seg_map = {}
for r in segs:
    d = dict(r)
    seg_map[d['id']] = d
    # Look up metadata
    cur.execute("SELECT key, int_value FROM segment_metadata WHERE segment_id=?", (d['id'],))
    meta = {row['key']: row['int_value'] for row in cur.fetchall()}
    print(f"  type={d['type']:7s} scope={str(d['scope']):12s} seg={d['id']} coll={d['collection']} meta={meta}")

# ── 2. VECTOR segment directories ──────────────────────────────────────
print("\n--- VECTOR segment directories on disk ---")
for r in segs:
    d = dict(r)
    if d['type'] != 'VECTOR':
        continue
    seg_dir = os.path.join(CHROMA_DIR, d['id'])
    exists = os.path.isdir(seg_dir)
    files = os.listdir(seg_dir) if exists else []
    sz_h = os.path.getsize(os.path.join(seg_dir, 'header.bin')) if exists and os.path.isfile(os.path.join(seg_dir, 'header.bin')) else 0
    sz_l = os.path.getsize(os.path.join(seg_dir, 'link_lists.bin')) if exists and os.path.isfile(os.path.join(seg_dir, 'link_lists.bin')) else 0
    sz_d = os.path.getsize(os.path.join(seg_dir, 'id_to_label.h5')) if exists and os.path.isfile(os.path.join(seg_dir, 'id_to_label.h5')) else 0
    print(f"  seg={d['id']} coll={d['collection']} dir_exists={exists} files={files}")
    if exists:
        print(f"    header.bin={sz_h} link_lists.bin={sz_l} id_to_label.h5={sz_d}")

# ── 3. Embedding counts by segment ─────────────────────────────────────
print("\n--- Embedding counts by segment ---")
cur.execute("""
    SELECT s.id as seg_id, s.collection, c.name, COUNT(e.id) as emb_count
    FROM segments s
    LEFT JOIN embeddings e ON e.segment_id = s.id
    LEFT JOIN collections c ON s.collection = c.id
    WHERE s.type = 'VECTOR'
    GROUP BY s.id
""")
for r in cur.fetchall():
    d = dict(r)
    print(f"  seg={d['seg_id'][:16]} coll={str(d['collection'])[:16]} name={str(d['name'])[:20]} emb_count={d['emb_count']}")

# ── 4. max_seq_id ───────────────────────────────────────────────────────
print("\n--- max_seq_id ---")
cur.execute("SELECT segment_id, seq_id FROM max_seq_id")
for r in cur.fetchall():
    d = dict(r)
    # Look up which collection this segment belongs to
    cur.execute("SELECT collection FROM segments WHERE id=?", (d['segment_id'],))
    seg_r = cur.fetchone()
    coll = seg_r['collection'] if seg_r else 'UNKNOWN'
    print(f"  segment={d['segment_id'][:24]} seq_id={d['seq_id']} coll={str(coll)[:16]}")

# ── 5. Embeddings sample ────────────────────────────────────────────────
print("\n--- Embeddings sample ---")
cur.execute("SELECT id, segment_id, seq_id, embedding_id FROM embeddings ORDER BY id")
all_emb = cur.fetchall()
print(f"  total: {len(all_emb)}")
# Group by segment_id
from collections import Counter
seg_counts = Counter(dict(r)['segment_id'] for r in all_emb)
for seg_id, cnt in seg_counts.most_common():
    print(f"  seg={seg_id[:24]} count={cnt}")
print()
# Show some samples
for r in all_emb[:5]:
    d = dict(r)
    print(f"  id={d['id']} seg={str(d['segment_id'])[:16]} seq_id={d['seq_id'].hex() if isinstance(d['seq_id'], bytes) else d['seq_id']} emb_id={d['embedding_id']}")

conn.close()
