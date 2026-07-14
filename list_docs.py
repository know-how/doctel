"""List all documents to find Dunning Manual doc_id"""
import asyncio, aiohttp, json

TOKEN = "Wa4ZCQca2yUSAK4k7Emle5QfwylqeOU_yj92EGB4bk0"

async def main():
    async with aiohttp.ClientSession() as s:
        async with s.get(
            "http://127.0.0.1:8000/api/documents",
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
                    f'Doc {d.get("id")}: {d.get("filename","?")} -> '
                    f'project={d.get("project_id","?")} status={d.get("status")}'
                )

asyncio.run(main())
