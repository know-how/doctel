"""Check current ChromaDB state comprehensively"""
import sqlite3
import os

base = r'C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma'
db_path = os.path.join(base, 'chroma.sqlite3')
conn = sqlite3.connect(db_path)

# === 1. Segment metadata ===
cur = conn.execute("""
    SELECT sm.key, sm.int_value, sm.str_value, s.id, c.name 
    FROM segment_metadata sm
    JOIN segments s ON s.id = sm.segment_id
    LEFT JOIN collections c ON c.id = s.collection
    WHERE s.scope='VECTOR'
    ORDER BY c.name, sm.key
""")
rows = cur.fetchall()
print(f'=== VECTOR SEGMENT METADATA ({len(rows)} rows) ===')
for r in rows:
    print(f'  {r[4]}: {r[0]} = int={r[1]} str={r[2]}  (seg={str(r[3])[:8]})')

# === 2. Queue count ===
cur = conn.execute('SELECT COUNT(*) FROM embeddings_queue')
print(f'\nembeddings_queue: {cur.fetchone()[0]} rows')

# === 3. VECTOR dirs ===
cur = conn.execute("SELECT id FROM segments WHERE scope='VECTOR'")
seg_ids = [r[0] for r in cur.fetchall()]
existing = set(os.listdir(base)) & set(seg_ids)
missing = set(seg_ids) - set(os.listdir(base))
print(f'\nVECTOR dirs existing: {len(existing)}')
print(f'VECTOR dirs missing: {len(missing)}')

for sid in sorted(existing):
    ll = os.path.join(base, sid, 'link_lists.bin')
    hb = os.path.join(base, sid, 'header.bin')
    ll_sz = os.path.getsize(ll) if os.path.exists(ll) else -1
    hb_sz = os.path.getsize(hb) if os.path.exists(hb) else -1
    print(f'  {sid[:8]}... link_lists={ll_sz}B header={hb_sz}B')

# === 4. max_seq_id for VECTOR segments ===
cur = conn.execute("""
    SELECT ms.segment_id, ms.seq_id FROM max_seq_id ms
    JOIN segments s ON s.id = ms.segment_id
    WHERE s.scope='VECTOR'
""")
vec_seq = cur.fetchall()
print(f'\nVECTOR max_seq_id entries: {len(vec_seq)}')
for r in vec_seq:
    print(f'  {str(r[0])[:8]}... seq_id={r[1]}')

# === 5. Collection hnsw metadata ===
cur = conn.execute("""
    SELECT c.name, cm.key, cm.str_value 
    FROM collection_metadata cm 
    JOIN collections c ON c.id = cm.collection_id 
    WHERE cm.key LIKE 'hnsw:%'
""")
print('\n=== Collection hnsw metadata ===')
for r in cur.fetchall():
    print(f'  {r[0]}: {r[1]} = {r[2]}')

# === 6. Missing dirs with collection names ===
if missing:
    print(f'\n=== MISSING VECTOR dirs ({len(missing)}) ===')
    for mid in missing:
        cur = conn.execute("""
            SELECT c.name, c.id FROM collections c
            JOIN segments s ON s.collection = c.id
            WHERE s.id = ?
        """, (mid,))
        row = cur.fetchone()
        cname = row[0] if row else 'UNKNOWN'
        print(f'  {mid[:8]}... -> collection={cname}')

conn.close()
