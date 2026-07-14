import pymysql
from datetime import datetime

conn = pymysql.connect(host='127.0.0.1', user='root', password='', database='doctel')
cur = conn.cursor()

# Check doc 2 - all its details
cur.execute('SELECT id, filename, status, ingest_step, ingest_percent, embedding_provider, embedding_model, error_message, updated_at, created_at, ingestion_started, ingestion_completed, ingestion_failed FROM documents WHERE id=2')
r = cur.fetchone()
if r:
    print(f'doc 2:')
    print(f'  filename: {r[1]}')
    print(f'  status: {r[2]}')
    print(f'  ingest_step: {r[3]}')
    print(f'  ingest_percent: {r[4]}')
    print(f'  embedding_provider: {r[5]}')
    print(f'  embedding_model: {r[6]}')
    print(f'  error_message: {r[7]}')
    print(f'  updated_at: {r[8]}')
    print(f'  created_at: {r[9]}')
    print(f'  ingestion_started: {r[10]}')
    print(f'  ingestion_completed: {r[11]}')
    print(f'  ingestion_failed: {r[12]}')

# Check how many docs are in the DB
cur.execute('SELECT id, filename, status, ingest_percent, updated_at FROM documents ORDER BY id')
print('\n=== All documents ===')
for r in cur.fetchall():
    print(f'  doc {r[0]}: filename="{r[1]}" status={r[2]} pct={r[3]} updated={r[4]}')

# Check embeddings in MySQL
cur.execute('SELECT COUNT(*) FROM embeddings')
cnt = cur.fetchone()[0]
print(f'\nMySQL embedding_records: {cnt}')
cur.execute('SELECT id, document_id, chunk_index FROM embeddings LIMIT 5')
for r in cur.fetchall():
    print(f'  emb_id={r[0]} doc_id={r[1]} chunk_idx={r[2]}')

conn.close()
