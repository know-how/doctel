import sqlite3
import os

chroma_dir = os.path.join('localai', 'data', 'chroma')
print(f'Chroma dir: {os.path.abspath(chroma_dir)}')
print()

# Check dir contents
print('=== Directory contents ===')
for item in os.listdir(chroma_dir):
    full = os.path.join(chroma_dir, item)
    typ = 'DIR' if os.path.isdir(full) else 'FILE'
    sz = os.path.getsize(full) if os.path.isfile(full) else ''
    print(f'  {typ}: {item} ({sz})')

db = sqlite3.connect(os.path.join(chroma_dir, 'chroma.sqlite3'))
cur = db.cursor()

# Check embeddings_queue
print()
print('=== Embeddings queue ===')
cur.execute('SELECT COUNT(*) FROM embeddings_queue')
count = cur.fetchone()[0]
print(f'  total queue entries: {count}')
if count > 0:
    cur.execute('SELECT seq_id, operation, collection_id, topic FROM embeddings_queue LIMIT 5')
    for r in cur.fetchall():
        print(f'  seq={r[0]} op={r[1]} coll={str(r[2])[:8]}... topic={r[3]}')

# Check embeddings
print()
print('=== Embeddings ===')
cur.execute('SELECT COUNT(*) FROM embeddings')
print(f'  total: {cur.fetchone()[0]}')
cur.execute('SELECT embedding_id, collection_id FROM embeddings LIMIT 5')
for r in cur.fetchall():
    print(f'  id={str(r[0])[:30]}... coll={str(r[1])[:8]}...')

# Check max_seq_id
print()
print('=== max_seq_id ===')
cur.execute('SELECT seq_id, collection_id, segment, topic FROM max_seq_id ORDER BY seq_id')
for r in cur.fetchall():
    print(f'  seq={r[0]} coll={str(r[1])[:8]}... seg={str(r[2])[:8]}... topic={r[3]}')

# Check segments
print()
print('=== Segments ===')
cur.execute('SELECT id, type, collection_id, scope FROM segments')
for r in cur.fetchall():
    cid = str(r[2])[:8] if r[2] else 'None'
    print(f'  id={str(r[0])[:8]}... type={r[1]} coll={cid} scope={r[3]}')

# Check segment_metadata for batch/sync params
print()
print('=== Segment metadata (hnsw params) ===')
cur.execute(
    'SELECT sm.segment_id, sm.key, sm.str_value, sm.int_value, sm.float_value '
    'FROM segment_metadata sm '
    'WHERE sm.key LIKE "hnsw:%" '
    'ORDER BY sm.segment_id, sm.key'
)
for r in cur.fetchall():
    val = r[2] or r[3] or r[4]
    print(f'  seg={str(r[0])[:8]}... key={r[1]} val={val}')

# Check VECTOR segments and their directories
print()
print('=== VECTOR segment directories ===')
cur.execute("SELECT id FROM segments WHERE type='VECTOR'")
all_seg_rows = cur.fetchall()
print(f'Total VECTOR segments in SQLite: {len(all_seg_rows)}')
for r in all_seg_rows:
    seg_id_uuid = str(r[0])
    seg_dir = os.path.join(chroma_dir, seg_id_uuid)
    exists = os.path.isdir(seg_dir)
    if exists:
        files = os.listdir(seg_dir)
    else:
        files = []
    print(f'  {seg_id_uuid[:8]}... dir_exists={exists} files={files}')

db.close()
