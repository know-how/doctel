"""Check raw DB contents directly."""
import sqlite3

conn = sqlite3.connect("localai/db/app.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== DOCUMENTS ===")
cur.execute("SELECT id, project_id, status, ingest_step, ingest_percent, ingest_message, error_message, ingestion_started, ingestion_completed, ingestion_failed FROM documents")
for row in cur.fetchall():
    print(dict(row))

print("\n=== CHUNKS ===")
cur.execute("SELECT COUNT(*) as cnt FROM chunks")
print(f"Total chunks: {cur.fetchone()['cnt']}")

print("\n=== EMBEDDINGS ===")
cur.execute("SELECT COUNT(*) as cnt FROM embeddings")
print(f"Total embeddings: {cur.fetchone()['cnt']}")

print("\n=== DOC_ANALYSIS ===")
cur.execute("SELECT COUNT(*) as cnt FROM doc_analysis")
print(f"Total doc_analysis: {cur.fetchone()['cnt']}")

print("\n=== CHUNKS TABLE SCHEMA ===")
cur.execute("PRAGMA table_info(chunks)")
for row in cur.fetchall():
    print(dict(row))

print("\n=== EMBEDDINGS TABLE SCHEMA ===")
cur.execute("PRAGMA table_info(embeddings)")
for row in cur.fetchall():
    print(dict(row))

print("\n=== EMBEDDINGS SAMPLE ===")
cur.execute("SELECT * FROM embeddings LIMIT 5")
for row in cur.fetchall():
    print(dict(row))

print("\n=== CHUNKS SAMPLE ===")
cur.execute("SELECT * FROM chunks LIMIT 5")
for row in cur.fetchall():
    print(dict(row))

conn.close()
