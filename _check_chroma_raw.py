import sqlite3
import chromadb
import os

# Check SQLite
db_path = 'data/chroma/chroma.sqlite3'
print(f"SQLite DB size: {os.path.getsize(db_path)} bytes")
conn = sqlite3.connect(db_path)
cols = conn.execute("PRAGMA table_info(collections)").fetchall()
print("collections table columns:", cols)
rows = conn.execute("SELECT id, name, metadata FROM collections").fetchall()
print("collections:", rows)

# Check segments
segs = conn.execute("SELECT id, type, scope, collection, metadata FROM segments LIMIT 10").fetchall()
print("segments:", segs)

# Check via API
c = chromadb.PersistentClient(path='data/chroma')
print("API collections:", [col.name for col in c.list_collections()])

conn.close()
