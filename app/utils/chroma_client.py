import chromadb
from app.config import settings

class ChromaClient:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.chroma_path)

    def get_collection(self, project_id: str):
        return self.client.get_or_create_collection(
            name=f"project_{project_id}",
            metadata={"hnsw:space": "cosine"}
        )

    def upsert(self, project_id: str, ids: list[str], documents: list[str], embeddings: list[list[float]], metadatas: list[dict] = None):
        collection = self.get_collection(project_id)
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def query(self, project_id: str, query_embedding: list[float], top_k: int = 6, where: dict | None = None):
        collection = self.get_collection(project_id)
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
            where=where
        )

    def delete_where(self, project_id: str, where: dict):
        collection = self.get_collection(project_id)
        collection.delete(where=where)

chroma = ChromaClient()
