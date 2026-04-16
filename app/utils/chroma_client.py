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
        # Filter out entries with empty or inconsistent embeddings
        if embeddings:
            expected_dim = len(embeddings[0]) if embeddings[0] else 0
            valid = []
            for i in range(len(ids)):
                emb = embeddings[i] if i < len(embeddings) else []
                if emb and len(emb) == expected_dim:
                    valid.append(i)
            if len(valid) < len(ids):
                ids = [ids[i] for i in valid]
                documents = [documents[i] for i in valid]
                embeddings = [embeddings[i] for i in valid]
                if metadatas:
                    metadatas = [metadatas[i] for i in valid]
        if not ids:
            return
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
