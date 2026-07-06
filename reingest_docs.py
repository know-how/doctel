"""Re-ingest all documents for project_4 (RAG)."""
import asyncio, aiohttp, json

TOKEN = "Wa4ZCQca2yUSAK4k7Emle5QfwylqeOU_yj92EGB4bk0"

async def main():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
        # Re-ingest all 5 documents
        for doc_id in [1, 2, 3, 4, 5]:
            print(f"--- Retrying doc {doc_id} ---")
            async with session.post(
                "http://127.0.0.1:8000/api/ingest/retry",
                json={"document_id": doc_id},
                headers={"Authorization": f"Bearer {TOKEN}"},
            ) as r:
                txt = await r.text()
                print(f"  Status: {r.status}, Response: {txt}")

        # Wait for ingestion to progress
        print("\nWaiting 15 seconds for ingestion to process...")
        await asyncio.sleep(15)

        # Check current document statuses
        print("\n=== CURRENT DOC STATUSES ===")
        async with session.get(
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
                    f'  Doc {d.get("id")}: {d.get("filename","?")} -> '
                    f'status={d.get("status")}, step={d.get("ingest_step")}, '
                    f'pct={d.get("ingest_percent")}'
                )

        # Also check chroma and chunk counts
        print("\n=== CHUNKS COUNT ===")
        async with session.get(
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
                did = d.get("id")
                # Get chunk count for this doc
                async with session.get(
                    f"http://127.0.0.1:8000/api/ingest/status",
                    headers={"Authorization": f"Bearer {TOKEN}"},
                ) as r2:
                    pass  # just keeping session alive

        print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
