"""Check which embedding_ids map to which collections."""
import sqlite3
from pathlib import Path

chroma_path = r"C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma"
conn = sqlite3.connect(str(Path(chroma_path) / "chroma.sqlite3"))

# Get all collections with their names
print("=== Collections ===")
cur = conn.execute("SELECT id, name, dimension FROM collections")
for row in cur:
    print(f"  {row[1]} ({row[0][:12]}...) dim={row[2]}")

# Get all vector segments
print("\n=== Vector Segments -> Collections ===")
cur = conn.execute("""
    SELECT s.id, s.collection, c.name 
    FROM segments s 
    JOIN collections c ON s.collection = c.id
    WHERE s.type LIKE '%vector%'
""")
for row in cur:
    print(f"  segment={row[0][:12]}... -> {row[2]}")

# Get all metadata segments
print("\n=== Metadata Segments -> Collections ===")
cur = conn.execute("""
    SELECT s.id, s.collection, c.name 
    FROM segments s 
    JOIN collections c ON s.collection = c.id
    WHERE s.type LIKE '%metadata%'
""")
for row in cur:
    print(f"  segment={row[0][:12]}... -> {row[2]}")

# Embeddings in metadata segments
print("\n=== Embeddings by metadata segment ===")
cur = conn.execute("""
    SELECT e.segment_id, e.embedding_id, c.name
    FROM embeddings e
    JOIN segments s ON e.segment_id = s.id
    JOIN collections c ON s.collection = c.id
    ORDER BY c.name, e.embedding_id
""")
count = 0
for row in cur:
    print(f"  {row[2]}: {row[1]}")
    count += 1
print(f"  [{count} total embeddings]")

# Check chroma:document text for each collection
print("\n=== Sample documents ===")
for coll_name in ["project_1", "project_4", "test_direct"]:
    cur = conn.execute("""
        SELECT e.embedding_id, em.string_value 
        FROM embeddings e
        JOIN embedding_metadata em ON e.id = em.id
        JOIN segments s ON e.segment_id = s.id
        JOIN collections c ON s.collection = c.id
        WHERE em.key = 'chroma:document'
        AND c.name = ?
        LIMIT 1
    """, (coll_name,))
    row = cur.fetchone()
    if row:
        print(f"  {coll_name}: {row[0]} -> '{row[1][:100]}...'")
    else:
        print(f"  {coll_name}: NO DOCUMENTS FOUND")

# Check document_id metadata
print("\n=== document_id metadata ===")
cur = conn.execute("""
    SELECT e.embedding_id, em.int_value, c.name
    FROM embeddings e
    JOIN embedding_metadata em ON e.id = em.id
    JOIN segments s ON e.segment_id = s.id
    JOIN collections c ON s.collection = c.id
    WHERE em.key = 'document_id'
    ORDER BY c.name, e.embedding_id
""")
for row in cur:
    print(f"  {row[2]}: doc_id={row[1]} embedding={row[0]}")

conn.close()
