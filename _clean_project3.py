"""Clean test document from project_3 collection."""
import chromadb
from app.config import settings

client = chromadb.PersistentClient(path=settings.chroma_path)
col = client.get_collection('project_3')
count = col.count()
print(f'project_3 count: {count}')

if count > 0:
    data = col.get()
    ids = data['ids']
    print(f'Total IDs: {len(ids)}')
    print(f'First 10 IDs: {ids[:10]}')
    
    # Find and delete test documents
    test_ids = [id for id in ids if id.startswith('test_')]
    if test_ids:
        print(f'Deleting test IDs: {test_ids}')
        col.delete(ids=test_ids)
        print(f'Count after delete: {col.count()}')
    else:
        print('No test documents found')
else:
    print('Collection is empty - need to re-ingest')
