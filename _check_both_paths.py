"""Check both ChromaDB paths"""
import chromadb, os

# Check the ACTUAL path from config.yaml
actual_path = r'C:\Users\ze9167523\IdeaProjects\doctel\localai\data\chroma'
print(f'Actual path exists: {os.path.isdir(actual_path)}')
if os.path.isdir(actual_path):
    print(f'Contents: {os.listdir(actual_path)}')
    c = chromadb.PersistentClient(path=actual_path)
    all_cols = c.list_collections()
    print(f'Collections at ACTUAL path:')
    for col in all_cols:
        print(f'  {col.name}: {col.count()} items')
    try:
        col = c.get_collection('project_3')
        count = col.count()
        print(f'  -> project_3 count: {count}')
        if count > 0:
            results = col.peek()
            print(f'  Sample IDs: {results["ids"][:3]}')
    except Exception as e:
        print(f'  project_3 error: {e}')
else:
    print('ACTUAL path does NOT exist!')

# Also check C:\\LocalAI\\data\\chroma
old_path = r'C:\LocalAI\data\chroma'
print(f'\nOLD path exists: {os.path.isdir(old_path)}')
if os.path.isdir(old_path):
    c2 = chromadb.PersistentClient(path=old_path)
    all_cols2 = c2.list_collections()
    print(f'Collections at OLD path:')
    for col in all_cols2:
        print(f'  {col.name}: {col.count()} items')
    try:
        col2 = c2.get_collection('project_3')
        print(f'  project_3 count: {col2.count()}')
    except Exception as e:
        print(f'  project_3 error: {e}')

# Check what the settings actually resolve to
import sys
sys.path.insert(0, r'c:\Users\ze9167523\IdeaProjects\doctel')
from app.config import settings
print(f'\nSettings base_dir: {settings.base_dir}')
print(f'Settings chroma_path: {settings.chroma_path}')
