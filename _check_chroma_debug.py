"""Debug ChromaDB - check project_3 and all collections"""
import chromadb, os, sqlite3

path = r'C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma'
db_path = os.path.join(path, 'chroma.sqlite3')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Check collections with dimensions
print("=== COLLECTIONS ===")
cur.execute("SELECT id, name, dimension FROM collections")
for row in cur.fetchall():
    print(f"  name={row[1]} dim={row[2]}")

# Check segments DDL
print("\n=== SEGMENTS DDL ===")
cur.execute("SELECT sql FROM sqlite_master WHERE name='segments'")
print(f"  {cur.fetchone()[0]}")

conn.close()

# Now check via ChromaDB client
print("\n=== CHROMADB CLIENT ===")
c = chromadb.PersistentClient(path=path)
for col in c.list_collections():
    print(f"  {col.name}: count={col.count()}, meta={col.metadata}")

# Check project_3 specifically
print("\n=== PROJECT_3 DETAILS ===")
try:
    col3 = c.get_collection("project_3")
    print(f"  name: {col3.name}")
    print(f"  count: {col3.count()}")
    print(f"  metadata: {col3.metadata}")
    all_data = col3.get()
    print(f"  ids in get(): {len(all_data['ids'])} items")
except Exception as e:
    print(f"  Error: {e}")
