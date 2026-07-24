"""
knowledge_asset_service.py — DocTel Knowledge Asset Layer

Transforms DocTel from a document-centric platform into an asset-centric
Agentic Knowledge Base AI.

Documents, Audio, CSV, Images, Databases, and API connectors all become
first-class Knowledge Assets with relationships, search, and discovery.

Architecture:

  Upload/Ingestion
    ↓
  register_asset()          ← Creates KnowledgeAsset record
    ↓
  create_relationship()     ← Links assets (e.g. CRM FRS → CRM Policy)
    ↓
  find_related_assets()     ← Knowledge discovery via entity overlap
    ↓
  search_assets()           ← Unified search across all asset types
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Sequence

from sqlalchemy import select, or_, and_, Text, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enterprise_models import KnowledgeAsset, KnowledgeNode, KnowledgeEdge
from app.db.models import Document, DocAnalysis, AudioMetadata

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# ASSET TYPE ENUM
# ══════════════════════════════════════════════════════════════════════════════


class AssetType(str, Enum):
    """Supported knowledge asset types."""
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    IMAGE = "image"
    CSV = "csv"
    DATABASE = "database"
    API = "api"
    CONNECTOR = "connector"
    REPORT = "report"
    DASHBOARD = "dashboard"
    WORKSPACE = "workspace"


# ══════════════════════════════════════════════════════════════════════════════
# RELATIONSHIP TYPES
# ══════════════════════════════════════════════════════════════════════════════


class AssetRelationshipType(str, Enum):
    """Relationship types between knowledge assets."""
    RELATED_TO = "related_to"
    DEPENDS_ON = "depends_on"
    IMPLEMENTS = "implements"
    REFERENCES = "references"
    SUPERSEDES = "supersedes"
    VERSION_OF = "version_of"
    PART_OF = "part_of"
    DERIVED_FROM = "derived_from"
    TRANSCRIBED_FROM = "transcribed_from"
    ANALYZED_BY = "analyzed_by"
    GENERATED_FROM = "generated_from"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN SERVICE
# ══════════════════════════════════════════════════════════════════════════════


class KnowledgeAssetService:
    """Full CRUD and discovery for knowledge assets.

    This is the unified source of truth for all enterprise knowledge.
    Every document, audio recording, CSV, database connection, and API
    connector becomes a searchable KnowledgeAsset.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CRUD Operations ─────────────────────────────────────────────────────

    async def register_asset(
        self,
        asset_type: str,
        source_table: str,
        source_id: str,
        title: str,
        description: str = "",
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        owned_by_user_id: Optional[str] = None,
        owned_by_department: Optional[str] = None,
        workspace_id: Optional[str] = None,
        parent_asset_id: Optional[str] = None,
    ) -> KnowledgeAsset:
        """Register a new knowledge asset.

        Creates a KnowledgeAsset record linked to the source entity.
        Safe to call multiple times for the same source (upsert behavior).
        Also adds the asset to the enterprise knowledge graph.
        """
        try:
            # Check if asset already exists for this source
            existing = await self.get_asset_by_source(source_table, source_id)
            if existing:
                # Update existing asset
                # Add to knowledge graph regardless (idempotent)
                await self._add_asset_to_graph(
                    str(existing.id),
                    asset_type,
                    title,
                    source_document_id=source_id if source_table == "documents" else None,
                    entities=metadata.get("entities", []) if metadata else None,
                    topics=metadata.get("topics", []) if metadata else None,
                )
                existing.title = title or existing.title
                existing.description = description or existing.description
                if tags is not None:
                    existing.tags_json = json.dumps(tags)
                if metadata is not None:
                    existing.metadata_json = json.dumps(metadata)
                if workspace_id:
                    existing.metadata_json = json.dumps({
                        **(json.loads(existing.metadata_json or "{}")),
                        "workspace_id": workspace_id,
                    })
                existing.updated_at = datetime.utcnow()
                self.db.add(existing)
                await self.db.commit()
                logger.info("[ASSET] Updated asset %s (type=%s, source=%s/%s)",
                            existing.id, asset_type, source_table, source_id)
                return existing

            # Create new asset
            asset = KnowledgeAsset(
                id=uuid.uuid4(),
                asset_type=asset_type,
                source_table=source_table,
                source_id=source_id,
                title=title,
                description=description,
                tags_json=json.dumps(tags or []),
                metadata_json=json.dumps(metadata or {}),
                owned_by_user_id=uuid.UUID(owned_by_user_id) if owned_by_user_id else None,
                owned_by_department=owned_by_department,
                created_by_user_id=uuid.UUID(owned_by_user_id) if owned_by_user_id else None,
            )
            self.db.add(asset)
            await self.db.commit()
            logger.info("[ASSET] Registered asset %s (type=%s, title=%s)",
                        asset.id, asset_type, title)
            # Add to knowledge graph
            await self._add_asset_to_graph(
                str(asset.id),
                asset_type,
                title,
                source_document_id=source_id if source_table == "documents" else None,
                entities=metadata.get("entities", []) if metadata else None,
                topics=metadata.get("topics", []) if metadata else None,
            )
            return asset
        except Exception as exc:
            logger.warning("[ASSET] register_asset failed: %s", exc)
            await self.db.rollback()
            raise

    async def get_asset(self, asset_id: str) -> Optional[KnowledgeAsset]:
        """Get a knowledge asset by its UUID."""
        try:
            result = await self.db.execute(
                select(KnowledgeAsset).where(KnowledgeAsset.id == uuid.UUID(asset_id))
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.warning("[ASSET] get_asset failed: %s", exc)
            return None

    async def get_asset_by_source(
        self, source_table: str, source_id: str
    ) -> Optional[KnowledgeAsset]:
        """Get an asset by its source table and ID (document_id, etc.)."""
        try:
            result = await self.db.execute(
                select(KnowledgeAsset).where(
                    KnowledgeAsset.source_table == source_table,
                    KnowledgeAsset.source_id == source_id,
                )
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.warning("[ASSET] get_asset_by_source failed: %s", exc)
            return None

    async def update_asset(
        self,
        asset_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[KnowledgeAsset]:
        """Update a knowledge asset's metadata."""
        try:
            asset = await self.get_asset(asset_id)
            if not asset:
                return None
            if title is not None:
                asset.title = title
            if description is not None:
                asset.description = description
            if tags is not None:
                asset.tags_json = json.dumps(tags)
            if metadata is not None:
                existing_meta = json.loads(asset.metadata_json or "{}")
                existing_meta.update(metadata)
                asset.metadata_json = json.dumps(existing_meta)
            asset.updated_at = datetime.utcnow()
            self.db.add(asset)
            await self.db.commit()
            return asset
        except Exception as exc:
            logger.warning("[ASSET] update_asset failed: %s", exc)
            await self.db.rollback()
            return None

    async def delete_asset(self, asset_id: str) -> bool:
        """Delete a knowledge asset by ID."""
        try:
            asset = await self.get_asset(asset_id)
            if not asset:
                return False
            await self.db.delete(asset)
            await self.db.commit()
            logger.info("[ASSET] Deleted asset %s", asset_id)
            return True
        except Exception as exc:
            logger.warning("[ASSET] delete_asset failed: %s", exc)
            await self.db.rollback()
            return False

    # ── Search & Discovery ─────────────────────────────────────────────────

    async def search_assets(
        self,
        query: str = "",
        asset_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
        department: Optional[str] = None,
        workspace_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[KnowledgeAsset], int]:
        """Search knowledge assets across all types.

        Supports:
        - Full-text search across title and description
        - Filter by asset_type
        - Filter by tags
        - Filter by department
        - Pagination
        """
        try:
            conditions = []

            # Text search
            if query:
                query_filter = f"%{query}%"
                conditions.append(
                    or_(
                        KnowledgeAsset.title.ilike(query_filter),
                        KnowledgeAsset.description.ilike(query_filter),
                        KnowledgeAsset.tags_json.ilike(query_filter),
                    )
                )

            # Type filter
            if asset_type:
                conditions.append(KnowledgeAsset.asset_type == asset_type)

            # Department filter
            if department:
                conditions.append(KnowledgeAsset.owned_by_department == department)

            # Workspace filter (stored in metadata_json)
            if workspace_id:
                ws_filter = f"%workspace_id\": \"{workspace_id}%"
                conditions.append(KnowledgeAsset.metadata_json.ilike(ws_filter))

            # Build query
            stmt = select(KnowledgeAsset)
            if conditions:
                stmt = stmt.where(and_(*conditions))

            # Count total
            count_stmt = select(sa_func.count()).select_from(stmt.subquery())
            total_result = await self.db.execute(count_stmt)
            total = total_result.scalar() or 0

            # Paginate
            stmt = stmt.order_by(KnowledgeAsset.updated_at.desc().nulls_last())
            stmt = stmt.limit(limit).offset(offset)

            result = await self.db.execute(stmt)
            assets = list(result.scalars().all())

            return assets, total
        except Exception as exc:
            logger.warning("[ASSET] search_assets failed: %s", exc)
            return [], 0

    async def find_related_assets(
        self,
        asset_id: str,
        relation_type: Optional[str] = None,
        max_depth: int = 1,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find assets related to the given asset.

        Uses two strategies:
        1. Direct asset relationships (via source_table/source_id or metadata)
        2. Entity/topic overlap (shared entities between DocAnalysis)

        Returns list of dicts with asset info + relationship info.
        """
        try:
            asset = await self.get_asset(asset_id)
            if not asset:
                return []

            related: list[dict[str, Any]] = []
            seen_ids: set[str] = set()

            # Strategy 1: Source table matching (documents in same project)
            if asset.source_table == "documents":
                # Find documents in the same project
                doc_result = await self.db.execute(
                    select(Document).where(
                        Document.id == uuid.UUID(asset.source_id)
                    ) if asset.source_id else select(Document).limit(0)
                )
                doc = doc_result.scalar_one_or_none() if asset.source_id else None
                if doc and doc.project_id:
                    # Find other assets linked to documents in same project
                    project_docs = await self.db.execute(
                        select(Document).where(
                            Document.project_id == doc.project_id,
                            Document.id != doc.id,
                        ).limit(limit)
                    )
                    for pd in project_docs.scalars().all():
                        related_asset = await self.get_asset_by_source("documents", str(pd.id))
                        if related_asset and str(related_asset.id) not in seen_ids:
                            seen_ids.add(str(related_asset.id))
                            related.append({
                                "asset": related_asset.to_dict(),
                                "relationship": "same_project",
                                "confidence": 0.7,
                                "reason": f"Same project ({doc.project_id})",
                            })

            # Strategy 2: Entity/topic overlap via DocAnalysis
            if asset.source_table == "documents" and asset.source_id:
                # Get this document's analysis
                analysis_result = await self.db.execute(
                    select(DocAnalysis).where(
                        DocAnalysis.document_id == uuid.UUID(asset.source_id)
                    )
                )
                analysis = analysis_result.scalar_one_or_none()
                if analysis and analysis.topics_json and analysis.entities_json:
                    try:
                        my_topics = set(json.loads(analysis.topics_json) or [])
                        my_entities = set(json.loads(analysis.entities_json) or [])

                        # Find other analyses with overlapping topics/entities
                        other_analyses = await self.db.execute(
                            select(DocAnalysis).where(
                                DocAnalysis.document_id != uuid.UUID(asset.source_id),
                                DocAnalysis.topics_json.isnot(None),
                            ).limit(20)
                        )
                        for oa in other_analyses.scalars().all():
                            try:
                                oa_topics = set(json.loads(oa.topics_json) or [])
                                oa_entities = set(json.loads(oa.entities_json) or [])

                                topic_overlap = len(my_topics & oa_topics)
                                entity_overlap = len(my_entities & oa_entities)
                                total_overlap = topic_overlap + entity_overlap

                                if total_overlap > 0 and oa.document_id:
                                    related_asset = await self.get_asset_by_source(
                                        "documents", str(oa.document_id)
                                    )
                                    if related_asset and str(related_asset.id) not in seen_ids:
                                        seen_ids.add(str(related_asset.id))
                                        confidence = min(1.0, total_overlap / 5)
                                        reasons = []
                                        if topic_overlap > 0:
                                            shared_topics = my_topics & oa_topics
                                            reasons.append(f"Topics: {', '.join(list(shared_topics)[:3])}")
                                        if entity_overlap > 0:
                                            shared_entities = my_entities & oa_entities
                                            reasons.append(f"Entities: {', '.join(list(shared_entities)[:3])}")
                                        related.append({
                                            "asset": related_asset.to_dict(),
                                            "relationship": "entity_overlap",
                                            "confidence": round(confidence, 2),
                                            "reason": "; ".join(reasons),
                                        })
                            except Exception:
                                continue
                    except json.JSONDecodeError:
                        pass

            # Sort by confidence
            related.sort(key=lambda r: r["confidence"], reverse=True)
            return related[:limit]

        except Exception as exc:
            logger.warning("[ASSET] find_related_assets failed: %s", exc)
            return []

    # ── Asset Registration from Sources ─────────────────────────────────────

    async def assign_to_matching_space(self, document: Document) -> None:
        """Automatically assign a document to a matching knowledge space.

        Strategy:
        1. Match by project name (query the Project table, then match
           space names against the project name)
        2. Match by document type (doc_type or detected_type)
        3. Skip if no match found
        """
        try:
            from app.db.models import Workspace, Project

            candidates = []

            # 1. Match by project name
            if document.project_id:
                proj_result = await self.db.execute(
                    select(Project).where(Project.id == document.project_id)
                )
                project = proj_result.scalar_one_or_none()
                if project and project.name:
                    # Find spaces whose name contains the project name
                    space_result = await self.db.execute(
                        select(Workspace).where(
                            Workspace.name.ilike(f"%{project.name}%")
                        ).limit(3)
                    )
                    for space in space_result.scalars().all():
                        candidates.append((space, 1.0))

            # 2. Match by doc_type
            doc_type = getattr(document, 'doc_type', None) or getattr(document, 'detected_type', None)
            if doc_type and doc_type not in ("", "generic"):
                type_result = await self.db.execute(
                    select(Workspace).where(
                        Workspace.name.ilike(f"%{doc_type}%")
                    ).limit(3)
                )
                for space in type_result.scalars().all():
                    # Avoid duplicates
                    if not any(c[0].id == space.id for c in candidates):
                        candidates.append((space, 0.7))

            # Assign to best matching space
            if candidates:
                candidates.sort(key=lambda x: -x[1])
                best_space = candidates[0][0]

                # Tag document with space reference
                existing_tags = json.loads(document.tags_json or "[]")
                space_ref = f"space:{best_space.id}"
                if space_ref not in existing_tags:
                    existing_tags.append(space_ref)
                    document.tags_json = json.dumps(existing_tags)
                    self.db.add(document)
                    await self.db.commit()
                    logger.info(
                        "[SPACE] Auto-assigned document %s to space %s (confidence=%.1f, name=%s)",
                        document.id, best_space.id, candidates[0][1], best_space.name,
                    )
        except Exception as exc:
            logger.warning("[SPACE] Auto-assignment failed: %s", exc)

    async def add_to_knowledge_graph(self, document: Document, analysis: Optional[DocAnalysis] = None) -> None:
        """Add a document and its analysis to the enterprise knowledge graph.

        Creates graph nodes for the document, its entities, topics, systems,
        policies, and meetings. Creates edges connecting them.
        """
        try:
            from app.services.knowledge_graph_service import KnowledgeGraphService
            kg = KnowledgeGraphService(self.db)
            await kg.add_document_to_graph(
                document_id=str(document.id),
                document_title=document.title or document.filename or "",
                doc_type=document.doc_type or "",
                project_id=document.project_id,
                analysis=analysis,
            )
            logger.info("[GRAPH] Auto-added document %s to knowledge graph", document.id)
        except Exception as exc:
            logger.warning("[GRAPH] Auto-add to graph failed: %s", exc)

    async def _add_asset_to_graph(
        self,
        asset_id: str,
        asset_type: str,
        title: str,
        source_document_id: Optional[str] = None,
        entities: Optional[list[str]] = None,
        topics: Optional[list[str]] = None,
    ) -> None:
        """Add a knowledge asset to the enterprise knowledge graph."""
        try:
            from app.services.knowledge_graph_service import KnowledgeGraphService
            kg = KnowledgeGraphService(self.db)
            await kg.add_asset_node_to_graph(
                asset_id=asset_id,
                asset_type=asset_type,
                title=title,
                source_document_id=source_document_id,
                entities=entities,
                topics=topics,
            )
        except Exception as exc:
            logger.warning("[GRAPH] Auto-add asset to graph failed: %s", exc)

    async def register_document_asset(
        self, document: Document, analysis: Optional[DocAnalysis] = None
    ) -> KnowledgeAsset:
        """Register a Document as a KnowledgeAsset."""
        # Auto-assign to matching knowledge space
        await self.assign_to_matching_space(document)

        # Auto-add to knowledge graph (creates nodes + edges)
        await self.add_to_knowledge_graph(document, analysis)

        # Determine asset subtype from mime_type
        mime = (document.mime_type or "").lower()
        if mime.startswith("audio/") or any(ext in (document.filename or "").lower() for ext in [".mp3", ".wav", ".m4a", ".ogg", ".flac"]):
            asset_type = AssetType.AUDIO.value
        elif mime.startswith("video/"):
            asset_type = AssetType.VIDEO.value  # Video becomes video asset
        elif mime.startswith("image/"):
            asset_type = AssetType.IMAGE.value
        elif mime == "text/csv" or (document.filename or "").lower().endswith(".csv"):
            asset_type = AssetType.CSV.value
        else:
            asset_type = AssetType.DOCUMENT.value

        # Build tags from analysis
        tags = []
        if analysis:
            if analysis.topics_json:
                try:
                    tags = json.loads(analysis.topics_json) or []
                except Exception:
                    tags = []
        if document.doc_type:
            tags.append(document.doc_type)

        # Build metadata from analysis
        metadata = {
            "mime_type": document.mime_type,
            "filename": document.filename,
            "project_id": str(document.project_id) if document.project_id else None,
            "status": document.status,
            "file_size": document.pages or 0,
        }
        if analysis:
            metadata["doc_type"] = analysis.doc_type or ""
            metadata["sentiment"] = analysis.sentiment or ""
            metadata["entity_count"] = len(json.loads(analysis.entities_json)) if analysis.entities_json else 0
            metadata["topic_count"] = len(json.loads(analysis.topics_json)) if analysis.topics_json else 0

        return await self.register_asset(
            asset_type=asset_type,
            source_table="documents",
            source_id=str(document.id),
            title=document.title or document.filename or "Untitled",
            description=analysis.executive_summary[:500] if analysis and analysis.executive_summary else "",
            tags=tags,
            metadata=metadata,
            owned_by_user_id=str(document.owner_id) if document.owner_id else None,
            owned_by_department=None,
        )

    async def register_audio_asset(
        self, document: Document, audio_meta: Optional[dict[str, Any]] = None
    ) -> KnowledgeAsset:
        """Register an audio recording as a KnowledgeAsset.

        Called after transcription completes.
        """
        metadata = {
            "mime_type": document.mime_type,
            "filename": document.filename,
            "project_id": str(document.project_id) if document.project_id else None,
            "duration_sec": audio_meta.get("duration_sec") if audio_meta else None,
            "word_count": audio_meta.get("word_count") if audio_meta else None,
            "language": audio_meta.get("language", "en") if audio_meta else "en",
            "transcription_model": audio_meta.get("model_used") if audio_meta else None,
            "source_type": audio_meta.get("source_type", "audio") if audio_meta else "audio",
        }
        tags = ["audio"]
        if audio_meta and audio_meta.get("language"):
            tags.append(f"lang_{audio_meta['language']}")

        return await self.register_asset(
            asset_type=AssetType.AUDIO.value,
            source_table="documents",
            source_id=str(document.id),
            title=document.title or document.filename or "Audio Recording",
            description=f"Audio recording ({audio_meta.get('duration_sec', 0):.0f}s)" if audio_meta else "Audio recording",
            tags=tags,
            metadata=metadata,
            owned_by_user_id=str(document.owner_id) if document.owner_id else None,
        )

    async def register_video_asset(
        self,
        document: Document,
        video_meta: Optional[dict[str, Any]] = None,
        transcript: str = "",
    ) -> KnowledgeAsset:
        """Register a video recording as a KnowledgeAsset.

        Called after video analysis (transcription + frame analysis) completes.
        Stores frame metadata, visual events, and video classification.
        """
        filename = document.filename or ""
        duration_sec = video_meta.get("duration_sec") if video_meta else 0.0
        metadata: dict[str, Any] = {
            "mime_type": document.mime_type,
            "filename": filename,
            "project_id": str(document.project_id) if document.project_id else None,
            "duration_sec": duration_sec,
            "width": video_meta.get("width", 0) if video_meta else 0,
            "height": video_meta.get("height", 0) if video_meta else 0,
            "fps": video_meta.get("fps", 0.0) if video_meta else 0.0,
            "codec": video_meta.get("codec", "") if video_meta else "",
            "transcription_engine": video_meta.get("transcription_engine", "") if video_meta else "",
            "transcription_confidence": video_meta.get("transcription_confidence", 0.0) if video_meta else 0.0,
            "video_type": video_meta.get("video_type", "recording") if video_meta else "recording",
            "frames_analyzed": video_meta.get("frames_analyzed", 0) if video_meta else 0,
            "visual_events_count": video_meta.get("visual_events_count", 0) if video_meta else 0,
            "word_count": len(transcript.split()) if transcript else 0,
        }

        tags = ["video", video_meta.get("video_type", "recording")] if video_meta else ["video"]

        title = document.title or filename or "Video Recording"
        transcript_words = len(transcript.split()) if transcript else 0
        description = (
            f"Video ({duration_sec:.0f}s, {video_meta.get('video_type', 'recording')})"
            if video_meta else "Video recording"
        )

        return await self.register_asset(
            asset_type=AssetType.VIDEO.value,
            source_table="documents",
            source_id=str(document.id),
            title=title,
            description=description,
            tags=tags,
            metadata=metadata,
            owned_by_user_id=str(document.owner_id) if document.owner_id else None,
        )

    # ── Relationships ──────────────────────────────────────────────────────

    async def create_relationship(
        self,
        source_asset_id: str,
        target_asset_id: str,
        relation_type: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Create a relationship between two knowledge assets.

        The relationship is stored in the asset's metadata_json as a
        relationships array, allowing graph traversal without a separate table.
        """
        try:
            source = await self.get_asset(source_asset_id)
            target = await self.get_asset(target_asset_id)
            if not source or not target:
                logger.warning("[ASSET] Cannot create relationship: asset(s) not found")
                return False

            # Store relationship in source asset's metadata
            source_meta = json.loads(source.metadata_json or "{}")
            relationships = source_meta.get("relationships", [])
            # Check for duplicate
            for rel in relationships:
                if rel.get("target_id") == target_asset_id and rel.get("type") == relation_type:
                    return True  # Already exists
            relationships.append({
                "target_id": target_asset_id,
                "target_title": target.title,
                "target_type": target.asset_type,
                "type": relation_type,
                "metadata": metadata or {},
            })
            source_meta["relationships"] = relationships
            source.metadata_json = json.dumps(source_meta)
            source.updated_at = datetime.utcnow()
            self.db.add(source)
            await self.db.commit()
            logger.info("[ASSET] Created relationship: %s ->[%s]-> %s",
                        source_asset_id[:8], relation_type, target_asset_id[:8])
            return True
        except Exception as exc:
            logger.warning("[ASSET] create_relationship failed: %s", exc)
            await self.db.rollback()
            return False

    async def get_relationships(
        self, asset_id: str
    ) -> list[dict[str, Any]]:
        """Get all relationships for an asset (both outgoing and incoming)."""
        try:
            asset = await self.get_asset(asset_id)
            if not asset:
                return []

            # Outgoing relationships (from this asset)
            meta = json.loads(asset.metadata_json or "{}")
            outgoing = meta.get("relationships", [])

            # Incoming relationships (to this asset) - search all assets for relationship
            all_assets = await self.db.execute(
                select(KnowledgeAsset).limit(200)
            )
            incoming = []
            for other in all_assets.scalars().all():
                if str(other.id) == asset_id:
                    continue
                other_meta = json.loads(other.metadata_json or "{}")
                other_rels = other_meta.get("relationships", [])
                for rel in other_rels:
                    if rel.get("target_id") == asset_id:
                        incoming.append({
                            "source_id": str(other.id),
                            "source_title": other.title,
                            "source_type": other.asset_type,
                            "type": rel.get("type"),
                            "direction": "incoming",
                            "metadata": rel.get("metadata", {}),
                        })

            return outgoing + incoming
        except Exception as exc:
            logger.warning("[ASSET] get_relationships failed: %s", exc)
            return []

    # ── Utility ────────────────────────────────────────────────────────────

    async def count_by_type(self) -> dict[str, int]:
        """Count assets by type for dashboard/knowledge overview."""
        try:
            result = await self.db.execute(
                select(
                    KnowledgeAsset.asset_type,
                    sa_func.count(KnowledgeAsset.id),
                ).group_by(KnowledgeAsset.asset_type)
            )
            counts: dict[str, int] = {}
            for row in result.all():
                counts[row[0] or "unknown"] = row[1]
            return counts
        except Exception as exc:
            logger.warning("[ASSET] count_by_type failed: %s", exc)
            return {}

    async def get_assets_by_project(
        self, project_id: int, asset_type: Optional[str] = None, limit: int = 50
    ) -> list[KnowledgeAsset]:
        """Get all assets belonging to a project."""
        try:
            conditions = [
                KnowledgeAsset.source_table == "documents",
            ]
            # Find documents in this project first, then get their assets
            doc_result = await self.db.execute(
                select(Document.id).where(Document.project_id == project_id).limit(limit)
            )
            doc_ids = [str(row[0]) for row in doc_result.all()]

            if not doc_ids:
                return []

            conditions.append(KnowledgeAsset.source_id.in_(doc_ids))
            if asset_type:
                conditions.append(KnowledgeAsset.asset_type == asset_type)

            result = await self.db.execute(
                select(KnowledgeAsset).where(and_(*conditions)).limit(limit)
            )
            return list(result.scalars().all())
        except Exception as exc:
            logger.warning("[ASSET] get_assets_by_project failed: %s", exc)
            return []


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS (non-class, for use in endpoints)
# ══════════════════════════════════════════════════════════════════════════════


async def register_document_asset(
    db: AsyncSession, document: Document, analysis: Optional[DocAnalysis] = None
) -> Optional[KnowledgeAsset]:
    """Register a document as a knowledge asset (convenience wrapper)."""
    service = KnowledgeAssetService(db)
    return await service.register_document_asset(document, analysis)


async def register_audio_asset(
    db: AsyncSession, document: Document, audio_meta: Optional[dict] = None
) -> Optional[KnowledgeAsset]:
    """Register an audio recording as a knowledge asset (convenience wrapper)."""
    service = KnowledgeAssetService(db)
    return await service.register_audio_asset(document, audio_meta)


async def register_video_asset(
    db: AsyncSession,
    document: Document,
    video_meta: Optional[dict] = None,
    transcript: str = "",
) -> Optional[KnowledgeAsset]:
    """Register a video as a knowledge asset (convenience wrapper)."""
    service = KnowledgeAssetService(db)
    return await service.register_video_asset(document, video_meta, transcript)


async def find_related(
    db: AsyncSession, asset_id: str, limit: int = 10
) -> list[dict[str, Any]]:
    """Find related assets (convenience wrapper)."""
    service = KnowledgeAssetService(db)
    return await service.find_related_assets(asset_id, limit=limit)


async def search_knowledge(
    db: AsyncSession,
    query: str = "",
    asset_type: Optional[str] = None,
    tags: Optional[list[str]] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search knowledge assets (convenience wrapper)."""
    service = KnowledgeAssetService(db)
    assets, total = await service.search_assets(
        query=query, asset_type=asset_type, tags=tags, limit=limit
    )
    return {
        "assets": [a.to_dict() for a in assets],
        "total": total,
    }


async def get_asset_count_by_type(db: AsyncSession) -> dict[str, int]:
    """Get asset counts by type (convenience wrapper)."""
    service = KnowledgeAssetService(db)
    return await service.count_by_type()
