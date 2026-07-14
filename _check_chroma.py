import sqlite3
import chromadb
from app.config import settings

# Check SQLite
conn = sqlite3.connect('data/chroma/chroma.sqlite3')
cols = conn.execute("PRAGMA table_info(collections)").fetchall()
print("collections table columns:", cols)
rows = conn.execute("SELECT * FROM collections").fetchall()
print("collections:", rows)

# Check via API
c = chromadb.PersistentClient(path='data/chroma')
print("API collections:", [col.name for col in c.list_collections()])

# Check settings
print("settings.chroma_path:", settings.chroma_path)
conn.close()
