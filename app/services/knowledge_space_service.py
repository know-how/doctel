"""
knowledge_space_service.py — DocTel Knowledge Space Layer

Transforms workspaces into Knowledge Spaces — the primary containers
for enterprise knowledge.

A Knowledge Space contains:
  Documents, Audio, Video, Images, CSV, Dashboards, Reports,
  Database Assets, and Knowledge Assets.

Architecture:

  Workspace (existing DB table)
    ↓
  KnowledgeSpaceService (this file)
    ├─ CRUD: create / get / update / delete
    ├─ Asset management: add_asset / remove_asset / get_assets
    ├─ Discovery: search_spaces / find_related_spaces
    └─ Knowledge Graph: space_nodes / space_graph

  Planner Integration:
    Question → Knowledge Space Search → Asset Discovery → Execution Plan
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, or_, and_, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Workspace, WorkspaceMember, Document, DocAnalysis

logger = logging.getLogger(__name__)


class KnowledgeSpaceService:
    """Full CRUD, asset management, and discovery for Knowledge Spaces.

    Wraps the existing Workspace table as the primary container for
    enterprise knowledge. Each space can hold documents, audio, video,
    CSV, and other knowledge assets.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CRUD ─────────────────────────────────────────────────────────────

    async def create_space(
        self,
        name: str,
        description: str = "",
        department: str = "",
        tags: Optional[list[str]] = None,
        owner_id: Optional[str] = None,
    ) -> Workspace:
        """Create a new knowledge space."""
        space = Workspace(
            id=uuid.uuid4(),
            name=name,
            description=description,
            owner_id=uuid.UUID(owner_id) if owner_id else None,
            is_active=True,
        )
        self.db.add(space)

        # Store department + tags in workspace metadata (workspace has no
        # dedicated department/tags column, so we extend via description/metadata)
        if department or tags:
            meta = {
                "department": department or "",
                "tags": tags or [],
                "created_from": "knowledge_space_service",
            }
            # Use a convention: prefix description with JSON metadata block
            meta_block = json.dumps(meta)
            space.description = f"{description}\n__meta__:{meta_block}"

        await self.db.commit()
        await self.db.refresh(space)
        logger.info("[SPACE] Created space %s (name=%s, department=%s)",
                     space.id, name, department)
        return space

    async def get_space(self, space_id: str) -> Optional[Workspace]:
        """Get a knowledge space by ID with member info."""
        try:
            result = await self.db.execute(
                select(Workspace)
                .where(Workspace.id == uuid.UUID(space_id))
                .options(selectinload(Workspace.members))
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.warning("[SPACE] get_space failed: %s", exc)
            return None

    async def update_space(
        self,
        space_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        department: Optional[str] = None,
        tags: Optional[list[str]] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Workspace]:
        """Update a knowledge space's metadata."""
        try:
            space = await self.get_space(space_id)
            if not space:
                return None

            if name is not None:
                space.name = name
            if description is not None:
                space.description = description
            if is_active is not None:
                space.is_active = is_active

            # Update metadata embedded in description
            if department is not None or tags is not None:
                existing_meta = self._extract_meta(space.description)
                if department is not None:
                    existing_meta["department"] = department
                if tags is not None:
                    existing_meta["tags"] = tags
                base_desc = self._strip_meta(space.description)
                meta_block = json.dumps(existing_meta)
                space.description = f"{base_desc}\n__meta__:{meta_block}"

            space.updated_at = datetime.utcnow()
            self.db.add(space)
            await self.db.commit()
            return space
        except Exception as exc:
            logger.warning("[SPACE] update_space failed: %s", exc)
            await self.db.rollback()
            return None

    async def delete_space(self, space_id: str) -> bool:
        """Delete a knowledge space."""
        try:
            space = await self.get_space(space_id)
            if not space:
                return False
            # Soft-delete by marking inactive
            space.is_active = False
            space.deleted_at = datetime.utcnow()
            space.updated_at = datetime.utcnow()
            self.db.add(space)
            await self.db.commit()
            logger.info("[SPACE] Deleted space %s", space_id)
            return True
        except Exception as exc:
            logger.warning("[SPACE] delete_space failed: %s", exc)
            await self.db.rollback()
            return False

    # ── Search & Discovery ───────────────────────────────────────────────

    async def search_spaces(
        self,
        query: str = "",
        department: Optional[str] = None,
        is_active: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Workspace], int]:
        """Search knowledge spaces across name and description."""
        try:
            conditions = [Workspace.is_active == is_active]

            if query:
                q_filter = f"%{query}%"
                conditions.append(
                    or_(
                        Workspace.name.ilike(q_filter),
                        Workspace.description.ilike(q_filter),
                    )
                )

            if department:
                # Build reliable JSON substring match for department in metadata
                dept_fragment = json.dumps({"department": department})[1:-1]  # "department": "value"
                dept_filter = f"%{dept_fragment}%"
                conditions.append(Workspace.description.ilike(dept_filter))

            stmt = select(Workspace).where(and_(*conditions))

            # Count
            count_stmt = select(sa_func.count()).select_from(stmt.subquery())
            total_result = await self.db.execute(count_stmt)
            total = total_result.scalar() or 0

            # Paginate
            stmt = stmt.order_by(Workspace.updated_at.desc().nulls_last())
            stmt = stmt.limit(limit).offset(offset)

            result = await self.db.execute(stmt)
            spaces = list(result.scalars().all())

            return spaces, total
        except Exception as exc:
            logger.warning("[SPACE] search_spaces failed: %s", exc)
            return [], 0

    async def find_related_spaces(
        self, space_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Find spaces related to this one via shared topics/entities.

        Uses DocAnalysis data from documents in each space to compute
        topical overlap between spaces.
        """
        try:
            space = await self.get_space(space_id)
            if not space:
                return []

            # Get topics/entities of documents in this space
            my_topics, my_entities = await self._get_space_analysis(space_id)

            if not my_topics and not my_entities:
                return []

            # Search other spaces
            other_spaces, _ = await self.search_spaces(limit=50)
            related: list[dict[str, Any]] = []

            for other in other_spaces:
                if str(other.id) == space_id:
                    continue

                other_topics, other_entities = await self._get_space_analysis(
                    str(other.id)
                )

                topic_overlap = len(my_topics & other_topics)
                entity_overlap = len(my_entities & other_entities)
                total_overlap = topic_overlap + entity_overlap

                if total_overlap > 0:
                    confidence = min(1.0, total_overlap / 5)
                    reasons = []
                    if topic_overlap > 0:
                        shared = list(my_topics & other_topics)[:3]
                        reasons.append(f"Topics: {', '.join(shared)}")
                    if entity_overlap > 0:
                        shared = list(my_entities & other_entities)[:3]
                        reasons.append(f"Entities: {', '.join(shared)}")

                    related.append({
                        "space_id": str(other.id),
                        "name": other.name,
                        "description": self._strip_meta(other.description),
                        "confidence": round(confidence, 2),
                        "reason": "; ".join(reasons),
                    })

            related.sort(key=lambda r: r["confidence"], reverse=True)
            return related[:limit]

        except Exception as exc:
            logger.warning("[SPACE] find_related_spaces failed: %s", exc)
            return []

    # ── Asset Management ─────────────────────────────────────────────────

    async def get_space_assets(
        self,
        space_id: str,
        asset_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get all assets belonging to a knowledge space.

        Finds documents linked to this space (currently via project_id).
        Future: direct space_id FK on KnowledgeAsset or Document.
        """
        try:
            space = await self.get_space(space_id)
            if not space:
                return [], 0

            # Assets are documents in projects that belong to this space.
            # For now, use a convention: space description contains a
            # project_id reference, or we search by department.
            meta = self._extract_meta(space.description)
            department = meta.get("department", "")

            if department:
                # Find by matching department in document analysis entities
                dept_assets = await self._find_department_assets(
                    department, asset_type
                )
                total_found = len(dept_assets)
                return dept_assets[:limit], total_found

            # Fallback: find documents tagged with this space reference
            space_ref = f"space:{space_id}"
            result = await self.db.execute(
                select(Document).where(
                    Document.tags_json.ilike(f"%{space_ref}%")
                ).limit(limit).offset(offset)
            )
            docs = list(result.scalars().all())

            assets = []
            for doc in docs:
                a_type = self._detect_asset_type(doc)
                assets.append({
                    "asset_id": str(doc.id),
                    "title": doc.title or doc.filename or "Untitled",
                    "asset_type": a_type,
                    "filename": doc.filename,
                    "mime_type": doc.mime_type,
                    "status": doc.status,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "source_table": "documents",
                    "source_id": str(doc.id),
                })

            return assets, len(assets)

        except Exception as exc:
            logger.warning("[SPACE] get_space_assets failed: %s", exc)
            return [], 0

    async def get_space_asset_counts(self, space_id: str) -> dict[str, int]:
        """Get asset counts by type for a knowledge space."""
        assets, total = await self.get_space_assets(space_id, limit=500)
        counts: dict[str, int] = {}
        for asset in assets:
            a_type = asset.get("asset_type", "unknown")
            counts[a_type] = counts.get(a_type, 0) + 1
        counts["total"] = total
        return counts

    async def add_asset_to_space(
        self, space_id: str, document_id: str
    ) -> bool:
        """Associate a document with a knowledge space.

        Updates the document's project or adds a reference.
        In production, a dedicated space_assets mapping table would be ideal.
        """
        try:
            space = await self.get_space(space_id)
            if not space:
                return False

            result = await self.db.execute(
                select(Document).where(Document.id == uuid.UUID(document_id))
            )
            doc = result.scalar_one_or_none()
            if not doc:
                return False

            # For now: tag the document description with the space reference
            existing_tags = []
            try:
                existing_tags = json.loads(doc.tags_json or "[]")
            except Exception:
                pass
            space_ref = f"space:{space_id}"
            if space_ref not in existing_tags:
                existing_tags.append(space_ref)
                doc.tags_json = json.dumps(existing_tags)
                self.db.add(doc)
                await self.db.commit()

            logger.info("[SPACE] Added document %s to space %s", document_id[:8], space_id[:8])
            return True
        except Exception as exc:
            logger.warning("[SPACE] add_asset_to_space failed: %s", exc)
            await self.db.rollback()
            return False

    async def remove_asset_from_space(
        self, space_id: str, document_id: str
    ) -> bool:
        """Remove a document from a knowledge space."""
        try:
            result = await self.db.execute(
                select(Document).where(Document.id == uuid.UUID(document_id))
            )
            doc = result.scalar_one_or_none()
            if not doc:
                return False

            existing_tags = []
            try:
                existing_tags = json.loads(doc.tags_json or "[]")
            except Exception:
                pass
            space_ref = f"space:{space_id}"
            if space_ref in existing_tags:
                existing_tags.remove(space_ref)
                doc.tags_json = json.dumps(existing_tags)
                self.db.add(doc)
                await self.db.commit()

            logger.info("[SPACE] Removed document %s from space %s", document_id[:8], space_id[:8])
            return True
        except Exception as exc:
            logger.warning("[SPACE] remove_asset_from_space failed: %s", exc)
            await self.db.rollback()
            return False

    # ── Space Stats ──────────────────────────────────────────────────────

    async def get_space_insights(self, space_id: str) -> dict[str, Any]:
        """Get comprehensive insights for a single knowledge space.

        Consolidates asset counts, recent assets, related spaces,
        and media asset breakdowns into one response.
        """
        try:
            space = await self.get_space(space_id)
            if not space:
                return {"error": "space_not_found"}

            # Asset counts by type
            counts = await self.get_space_asset_counts(space_id)

            # Recent assets (last 10)
            assets, total = await self.get_space_assets(space_id, limit=10)

            # Related spaces
            related = await self.find_related_spaces(space_id, limit=5)

            # Media asset breakdown
            media_types = {"audio": 0, "video": 0, "image": 0, "csv": 0, "document": 0}
            for a_type, count in counts.items():
                if a_type in media_types:
                    media_types[a_type] = count

            # Latest activity (recent assets with dates)
            recent = [
                {
                    "asset_id": a["asset_id"],
                    "title": a["title"],
                    "asset_type": a["asset_type"],
                    "created_at": a.get("created_at"),
                }
                for a in assets[:5] if a.get("created_at")
            ]

            meta = self._extract_meta(space.description)

            return {
                "space_id": space_id,
                "name": space.name,
                "description": self._strip_meta(space.description),
                "department": meta.get("department", ""),
                "tags": meta.get("tags", []),
                "is_active": space.is_active,
                "asset_counts": counts,
                "media_breakdown": media_types,
                "recent_assets": recent,
                "total_assets": total,
                "related_spaces": related,
            }
        except Exception as exc:
            logger.warning("[SPACE] get_space_insights failed: %s", exc)
            return {"error": str(exc)}

    async def get_space_stats(self) -> dict[str, Any]:
        """Get overall knowledge space statistics."""
        try:
            result = await self.db.execute(
                select(Workspace).where(Workspace.is_active == True)
            )
            spaces = list(result.scalars().all())

            total_spaces = len(spaces)
            total_assets = 0
            type_counts: dict[str, int] = {}

            for space in spaces:
                counts = await self.get_space_asset_counts(str(space.id))
                total_assets += counts.get("total", 0)
                for atype, count in counts.items():
                    if atype != "total":
                        type_counts[atype] = type_counts.get(atype, 0) + count

            return {
                "total_spaces": total_spaces,
                "total_assets": total_assets,
                "asset_type_counts": type_counts,
            }
        except Exception as exc:
            logger.warning("[SPACE] get_space_stats failed: %s", exc)
            return {"total_spaces": 0, "total_assets": 0, "asset_type_counts": {}}

    # ── Planner Integration ──────────────────────────────────────────────

    async def discover_by_question(
        self, question: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Discover knowledge spaces relevant to a user question.

        Used by the orchestrator to search spaces BEFORE building
        the execution plan. Returns spaces with relevance scores.
        """
        # Search spaces by name/description
        spaces, total = await self.search_spaces(query=question, limit=limit)

        results = []
        for space in spaces:
            meta = self._extract_meta(space.description)
            counts = await self.get_space_asset_counts(str(space.id))
            results.append({
                "space_id": str(space.id),
                "name": space.name,
                "description": self._strip_meta(space.description),
                "department": meta.get("department", ""),
                "tags": meta.get("tags", []),
                "asset_counts": counts,
                "relevance_score": self._compute_relevance(
                    question, space.name, space.description
                ),
            })

        # Sort by relevance
        results.sort(key=lambda r: r["relevance_score"], reverse=True)
        return results

    # ── Internal Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _extract_meta(description: str) -> dict[str, Any]:
        """Extract metadata JSON block from description string."""
        if not description:
            return {}
        try:
            marker = "__meta__:"
            idx = description.find(marker)
            if idx >= 0:
                return json.loads(description[idx + len(marker):].strip())
        except (json.JSONDecodeError, IndexError):
            pass
        return {}

    @staticmethod
    def _strip_meta(description: str) -> str:
        """Remove metadata block from description, returning clean text."""
        if not description:
            return ""
        marker = "__meta__:"
        idx = description.find(marker)
        if idx >= 0:
            return description[:idx].strip()
        return description

    async def _get_space_analysis(
        self, space_id: str
    ) -> tuple[set[str], set[str]]:
        """Collect all topics and entities from documents in a space."""
        topics: set[str] = set()
        entities: set[str] = set()

        try:
            # Get documents tagged with this space
            space_ref = f"space:{space_id}"
            result = await self.db.execute(
                select(Document).limit(100)
            )
            docs = list(result.scalars().all())
            doc_ids = []
            for doc in docs:
                try:
                    tags = json.loads(doc.tags_json or "[]")
                    if space_ref in tags:
                        doc_ids.append(doc.id)
                except Exception:
                    continue

            if not doc_ids:
                return topics, entities

            analyses = await self.db.execute(
                select(DocAnalysis).where(
                    DocAnalysis.document_id.in_(doc_ids)
                )
            )
            for analysis in analyses.scalars().all():
                if analysis.topics_json:
                    try:
                        topics.update(json.loads(analysis.topics_json))
                    except Exception:
                        pass
                if analysis.entities_json:
                    try:
                        entities.update(json.loads(analysis.entities_json))
                    except Exception:
                        pass
        except Exception as exc:
            logger.warning("[SPACE] _get_space_analysis failed: %s", exc)

        return topics, entities

    async def _find_department_assets(
        self,
        department: str,
        asset_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Find assets matching a department via document analysis."""
        assets = []
        try:
            # Find documents with this department in their analysis entities
            dept_filter = f"%{department}%"
            analysis_result = await self.db.execute(
                select(DocAnalysis)
                .where(DocAnalysis.entities_json.ilike(dept_filter))
                .limit(limit)
            )
            for analysis in analysis_result.scalars().all():
                if not analysis.document_id:
                    continue
                doc_result = await self.db.execute(
                    select(Document).where(Document.id == analysis.document_id)
                )
                doc = doc_result.scalar_one_or_none()
                if not doc:
                    continue

                a_type = self._detect_asset_type(doc)
                if asset_type and a_type != asset_type:
                    continue

                assets.append({
                    "asset_id": str(doc.id),
                    "title": doc.title or doc.filename or "Untitled",
                    "asset_type": a_type,
                    "filename": doc.filename,
                    "mime_type": doc.mime_type,
                    "status": doc.status,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "source_table": "documents",
                    "source_id": str(doc.id),
                })
        except Exception as exc:
            logger.warning("[SPACE] _find_department_assets failed: %s", exc)

        return assets

    @staticmethod
    def _detect_asset_type(doc: Document) -> str:
        """Detect KnowledgeAsset type from document metadata."""
        mime = (doc.mime_type or "").lower()
        filename = (doc.filename or "").lower()
        if mime.startswith("audio/") or any(ext in filename for ext in
            [".mp3", ".wav", ".m4a", ".ogg", ".flac"]):
            return "audio"
        if mime.startswith("video/") or any(ext in filename for ext in
            [".mp4", ".avi", ".mov", ".mkv", ".wmv"]):
            return "video"
        if mime.startswith("image/"):
            return "image"
        if mime == "text/csv" or filename.endswith(".csv"):
            return "csv"
        return "document"

    @staticmethod
    def _compute_relevance(question: str, name: str, description: str) -> float:
        """Compute relevance score between a question and a space."""
        q_lower = question.lower()
        score = 0.0

        # Name match (weighted higher)
        name_lower = name.lower()
        name_words = set(name_lower.split())
        q_words = set(q_lower.split())
        overlap = len(name_words & q_words)
        if overlap > 0:
            score += overlap * 2.0

        # Description match
        desc_lower = (description or "").lower()
        word_matches = sum(1 for w in q_words if w in desc_lower and len(w) > 2)
        score += word_matches * 0.5

        # Boost for exact phrase match
        if q_lower in name_lower:
            score += 5.0
        if q_lower in desc_lower:
            score += 3.0

        return min(score, 10.0)


# ── Convenience Functions ────────────────────────────────────────────────


async def get_knowledge_space_service(
    db: AsyncSession,
) -> KnowledgeSpaceService:
    """Get a KnowledgeSpaceService instance (factory)."""
    return KnowledgeSpaceService(db)


async def search_knowledge_spaces(
    db: AsyncSession,
    query: str = "",
    department: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search knowledge spaces (convenience wrapper)."""
    service = KnowledgeSpaceService(db)
    spaces, total = await service.search_spaces(
        query=query, department=department, limit=limit
    )
    return [
        {
            "space_id": str(s.id),
            "name": s.name,
            "description": service._strip_meta(s.description),
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in spaces
    ]


async def discover_spaces_for_question(
    db: AsyncSession,
    question: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Discover spaces relevant to a question (convenience wrapper)."""
    service = KnowledgeSpaceService(db)
    return await service.discover_by_question(question, limit=limit)
