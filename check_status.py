"""Check document and ChromaDB status after re-ingestion."""
import asyncio, aiohttp, chromadb

TOKEN = "Wa4ZCQca2yUSAK4k7Emle5QfwylqeOU_yj92EGB4bk0"

async def main():
    # Check ChromaDB
    print("=== CHROMADB COLLECTIONS ===")
    c = chromadb.PersistentClient(path="localai/data/chroma/")
    for col in c.list_collections():
        print(f"  {col.name}: {col.count()} items")
    
    # Check document statuses
    print("\n=== DOCUMENT STATUSES ===")
    async with aiohttp.ClientSession() as s:
        async with s.get(
            "http://127.0.0.1:8000/api/documents?project_id=4",
            headers={"Authorization": f"Bearer {TOKEN}"},
        ) as r:
            data = await r.json()
            docs = (
                data.get("documents", data.get("results", []))
                if isinstance(data, dict)
                else data
            )
            for d in docs:
                print(
                    f'  Doc {d["id"]}: {d.get("filename","?")} -> '
                    f'status={d.get("status")} '
                    f'step={d.get("ingest_step")} '
                    f'pct={d.get("ingest_percent")} '
                    f'msg={d.get("ingest_message","")} '
                    f'err={d.get("error_message","")}'
                )


if __name__ == "__main__":
    asyncio.run(main())
