import sqlite3

conn = sqlite3.connect("data/chroma/chroma.sqlite3")
print("=== TABLES ===")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    print(t)

print("\n=== COLLECTIONS ===")
cols = conn.execute("PRAGMA table_info(collections)").fetchall()
print("columns:", cols)
rows = conn.execute("SELECT * FROM collections").fetchall()
print("data:", rows)

print("\n=== SEGMENTS ===")
segcols = conn.execute("PRAGMA table_info(segments)").fetchall()
print("columns:", segcols)
rows = conn.execute("SELECT * FROM segments").fetchall()
print("data:", rows)

print("\n=== EMBEDDINGS (first 5) ===")
try:
    rows = conn.execute("SELECT * FROM embeddings LIMIT 5").fetchall()
    print("data:", rows)
except Exception as e:
    print("Error:", e)

conn.close()
