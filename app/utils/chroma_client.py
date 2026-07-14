import chromadb
import logging
import sqlite3
import os
from app.config import settings

logger = logging.getLogger(__name__)

class ChromaClient:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.chroma_path)
        logger.info("ChromaClient initialized with path: %s", settings.chroma_path)

    def _get_chromadb_sysdb_path(self) -> str:
        """Return the path to ChromaDB's SQLite sysdb."""
        return os.path.join(settings.chroma_path, "chroma.sqlite3")

    def _propagate_to_segment_metadata(self, collection_name: str) -> None:
        """
        Directly UPDATE/INSERT hnsw params into segment_metadata so the
        VECTOR segments pick them up even without a server restart.

        ChromaDB stores per-segment overrides in the segment_metadata table.
        The VECTOR segment reads from segment['metadata'] at __init__ time
        which is a merge of `segments.metadata` + `segment_metadata` rows.

        NOTE: segment_metadata uses typed columns for values, NOT a generic
        `value` column. Integer params (batch_size, sync_threshold) MUST
        use the `int_value` column.
        """
        db_path = self._get_chromadb_sysdb_path()
        if not os.path.isfile(db_path):
            logger.warning("chroma.sqlite3 not found at %s – cannot propagate segment metadata", db_path)
            return
        try:
            with sqlite3.connect(db_path) as conn:
                # Find the collection UUID for this collection name
                row = conn.execute(
                    "SELECT id FROM collections WHERE name = ?", (collection_name,)
                ).fetchone()
                if not row:
                    logger.warning("Collection %s not found in sysdb", collection_name)
                    return
                collection_id = row[0]

                # Find VECTOR segment(s) for this collection.
                # Column name is `collection` (not `collection_id`).
                segments = conn.execute(
                    "SELECT id FROM segments WHERE collection = ? AND scope = 'VECTOR'",
                    (collection_id,),
                ).fetchall()
                if not segments:
                    logger.warning("No VECTOR segments found for collection %s", collection_name)
                    return

                for (seg_id,) in segments:
                    for key, int_val in (("hnsw:batch_size", 5), ("hnsw:sync_threshold", 10)):
                        existing = conn.execute(
                            "SELECT 1 FROM segment_metadata WHERE segment_id = ? AND key = ?",
                            (seg_id, key),
                        ).fetchone()
                        if existing:
                            # Use int_value column for integer params
                            conn.execute(
                                "UPDATE segment_metadata SET int_value = ? WHERE segment_id = ? AND key = ?",
                                (int_val, seg_id, key),
                            )
                        else:
                            # Use int_value column for integer params
                            conn.execute(
                                "INSERT INTO segment_metadata (segment_id, key, int_value) VALUES (?, ?, ?)",
                                (seg_id, key, int_val),
                            )
                conn.commit()
                logger.info(
                    "Propagated hnsw params to segment_metadata for %s (%d VECTOR segments)",
                    collection_name, len(segments),
                )
        except Exception as e:
            logger.error("Failed to propagate segment metadata: %s", e)

    def get_collection(self, project_id: str):
        """
        Get or create a ChromaDB collection for the given project.

        NEW collections get low sync_threshold/batch_size so the HNSW
        vector index is persisted to disk even with small datasets.

        IMPORTANT: We NEVER call collection.modify() on EXISTING collections
        because ChromaDB's modify() can corrupt internal segment state
        (e.g. losing hnsw:space from metadata, stale configuration_json).
        Instead we write hnsw thresholds directly to the segment_metadata
        table via SQLite, which is the safe way to influence HNSW behavior
        without touching the collection object's fragile internal state.
        """
        collection_name = f"project_{project_id}"
        metadata_full = {
            "hnsw:space": "cosine",
            "hnsw:batch_size": 5,
            "hnsw:sync_threshold": 10,
        }
        # Step 1 — try to get the existing collection first
        try:
            collection = self.client.get_collection(name=collection_name)
            logger.info(
                "get_collection: existing collection project_%s found, meta=%s",
                project_id, collection.metadata,
            )
        except Exception:
            # Collection doesn't exist yet — create it with full metadata
            # (hnsw:space is required at creation time)
            collection = self.client.create_collection(
                name=collection_name,
                metadata=metadata_full,
            )
            logger.info(
                "get_collection: created new collection project_%s with meta=%s",
                project_id, metadata_full,
            )

        # Always propagate low thresholds directly to segment_metadata.
        # This is safe for BOTH new and existing collections — it writes
        # the correct int_value to the segment_metadata table, which
        # ChromaDB's HNSW segment reads at init time. We do NOT use
        # collection.modify() because it can silently corrupt state.
        self._propagate_to_segment_metadata(collection_name)
        return collection

    def upsert(self, project_id: str, ids: list[str], documents: list[str], embeddings: list[list[float]], metadatas: list[dict] = None):
        print(f"CHROMA_CLIENT_UPSERT: ENTERED with project_id={project_id}, ids={len(ids)}, docs={len(documents)}, emb={len(embeddings)}", flush=True)
        collection = self.get_collection(project_id)
        print(f"CHROMA_CLIENT_UPSERT: got collection project_{project_id}", flush=True)
        logger.info("upsert called: collection=project_%s, path=%s, ids=%d, embeddings=%d",
                     project_id, settings.chroma_path, len(ids), len(embeddings))
        # Log embedding dimension info before filter
        if embeddings:
            dims = set(len(e) for e in embeddings if e)
            logger.info("upsert: embedding dimension set=%s, total=%d", dims, len(embeddings))
            print(f"CHROMA_CLIENT_UPSERT: dimensions={dims}, total={len(embeddings)}", flush=True)
        else:
            logger.warning("upsert: embeddings list is EMPTY!")
            print("CHROMA_CLIENT_UPSERT: EMPTY embeddings!", flush=True)
        # Filter out entries with empty or inconsistent embeddings
        if embeddings:
            expected_dim = len(embeddings[0]) if embeddings[0] else 0
            valid = []
            for i in range(len(ids)):
                emb = embeddings[i] if i < len(embeddings) else []
                if emb and len(emb) == expected_dim:
                    valid.append(i)
                else:
                    logger.warning("upsert: filtering out idx=%s emb_len=%s expected_dim=%s", i, len(emb) if emb else 0, expected_dim)
                    print(f"CHROMA_CLIENT_UPSERT: FILTERING idx={i} emb_len={len(emb) if emb else 0} expected_dim={expected_dim}", flush=True)
            if len(valid) < len(ids):
                logger.warning("upsert: filtered %d/%d items due to dimension mismatch", len(ids) - len(valid), len(ids))
                print(f"CHROMA_CLIENT_UPSERT: filtered {len(ids)-len(valid)}/{len(ids)} items", flush=True)
                ids = [ids[i] for i in valid]
                documents = [documents[i] for i in valid]
                embeddings = [embeddings[i] for i in valid]
                if metadatas:
                    metadatas = [metadatas[i] for i in valid]
        if not ids:
            logger.warning("upsert: NO ITEMS to upsert after filtering!")
            print("CHROMA_CLIENT_UPSERT: NO ITEMS LEFT after filtering!", flush=True)
            return
        # Log collection state BEFORE upsert
        try:
            count_before = collection.count()
            logger.info("upsert: collection count BEFORE upsert: %d", count_before)
            print(f"CHROMA_CLIENT_UPSERT: count BEFORE={count_before}", flush=True)
        except Exception as ce:
            logger.warning("upsert: could not get count before upsert: %s", ce)
        logger.info("upsert: about to upsert %d items to project_%s", len(ids), project_id)
        print(f"CHROMA_CLIENT_UPSERT: calling collection.upsert() with {len(ids)} items", flush=True)
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
        print("CHROMA_CLIENT_UPSERT: collection.upsert() returned without exception", flush=True)
        # Log collection state AFTER upsert
        try:
            count_after = collection.count()
            logger.info("upsert: collection count AFTER upsert: %d", count_after)
            print(f"CHROMA_CLIENT_UPSERT: count AFTER={count_after}", flush=True)
        except Exception as ce:
            logger.warning("upsert: could not get count after upsert: %s", ce)

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
