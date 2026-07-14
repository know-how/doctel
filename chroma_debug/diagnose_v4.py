"""
DIAGNOSTIC v4 — Fixes the VECTOR type check (uses full URN string in segments.type)
and properly checks for segment directories.
"""

import sqlite3
import os
import re

CHROMA_DIR = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
DB_PATH = os.path.join(CHROMA_DIR, "chroma.sqlite3")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# First, dump the actual type values
cur.execute("SELECT DISTINCT type FROM segments")
print("Segment types in DB:")
for r in cur.fetchall():
    print(f"  '{r['type']}'")
print()

# Use the actual type string
VECTOR_TYPE_URN = "urn:chroma:segment/vector/hnsw-local-persisted"

# ── 1. Files/Dirs in chroma path ────────────────────────────────────────
print("--- All files/dirs in chroma path ---")
for entry in sorted(os.listdir(CHROMA_DIR)):
    full = os.path.join(CHROMA_DIR, entry)
    kind = "DIR" if os.path.isdir(full) else "FILE"
    sz = os.path.getsize(full) if os.path.isfile(full) else 0
    print(f"  [{kind:4s}] {entry} (size={sz})")
print()

# ── 2. VECTOR segment dirs ──────────────────────────────────────────────
print("--- VECTOR segment directories on disk ---")
cur.execute("SELECT id, collection FROM segments WHERE type=?", (VECTOR_TYPE_URN,))
vec_segs = cur.fetchall()
print(f"  Found {len(vec_segs)} VECTOR segments in DB")
for r in vec_segs:
    d = dict(r)
    seg_dir = os.path.join(CHROMA_DIR, d['id'])
    exists = os.path.isdir(seg_dir)
    files = os.listdir(seg_dir) if exists else []
    if exists:
        sz_h = os.path.getsize(os.path.join(seg_dir, 'header.bin')) if os.path.isfile(os.path.join(seg_dir, 'header.bin')) else 0
        sz_l = os.path.getsize(os.path.join(seg_dir, 'link_lists.bin')) if os.path.isfile(os.path.join(seg_dir, 'link_lists.bin')) else 0
        sz_d = os.path.getsize(os.path.join(seg_dir, 'id_to_label.h5')) if os.path.isfile(os.path.join(seg_dir, 'id_to_label.h5')) else 0
        print(f"  EXISTS: seg={d['id']} coll={d['collection']} files={files}")
        print(f"    header.bin={sz_h} link_lists.bin={sz_l} id_to_label.h5={sz_d}")
    else:
        print(f"  MISSING: seg={d['id']} coll={d['collection']} (directory NOT found)")
print()

# ── 3. Embedding counts by VECTOR segment ──────────────────────────────
print("--- Embedding counts by VECTOR segment ---")
cur.execute("""
    SELECT s.id as seg_id, s.collection, c.name, COUNT(e.id) as emb_count
    FROM segments s
    LEFT JOIN embeddings e ON e.segment_id = s.id
    LEFT JOIN collections c ON s.collection = c.id
    WHERE s.type = ?
    GROUP BY s.id
""", (VECTOR_TYPE_URN,))
for r in cur.fetchall():
    d = dict(r)
    print(f"  seg={d['seg_id'][:16]} coll={d['collection'][:16]} name={str(d['name'])[:20]} emb_count={d['emb_count']}")
print()

# ── 4. max_seq_id ───────────────────────────────────────────────────────
print("--- max_seq_id ---")
cur.execute("""
    SELECT m.segment_id, m.seq_id, s.collection, c.name
    FROM max_seq_id m
    LEFT JOIN segments s ON m.segment_id = s.id
    LEFT JOIN collections c ON s.collection = c.id
""")
for r in cur.fetchall():
    d = dict(r)
    print(f"  segment={d['segment_id'][:24]} seq_id={d['seq_id']} coll={str(d['collection'])[:16]} name={str(d['name'])[:16]}")
print()

# ── 5. Which VECTOR segments' directories exist? ──────────────────────
print("--- Check if ANY UUID dirs exist anywhere under chroma path ---")
for entry in os.listdir(CHROMA_DIR):
    full = os.path.join(CHROMA_DIR, entry)
    if os.path.isdir(full):
        # Check if it looks like a UUID
        print(f"  UUID-looking dir: {entry}")
        for f in os.listdir(full):
            fpath = os.path.join(full, f)
            print(f"    {f} (size={os.path.getsize(fpath) if os.path.isfile(fpath) else 'dir'})")

# Recursive search for any UUID patterns
print("\n--- Recursive search for UUID directories ---")
import uuid
for root, dirs, files in os.walk(CHROMA_DIR):
    for d in dirs:
        try:
            uuid.UUID(d)
            dirpath = os.path.join(root, d)
            print(f"  UUID dir: {dirpath}")
            for f in os.listdir(dirpath):
                fp = os.path.join(dirpath, f)
                print(f"    {f} (size={os.path.getsize(fp) if os.path.isfile(fp) else 'dir'})")
        except (ValueError, AttributeError):
            pass

conn.close()
