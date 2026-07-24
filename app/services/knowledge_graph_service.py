"""
knowledge_graph_service.py — DocTel Enterprise Knowledge Graph Layer

Connects assets, entities, people, systems, workflows, policies, meetings,
videos, and reports into a connected enterprise knowledge network.

Uses existing tables: KnowledgeNode, KnowledgeEdge (enterprise_models.py)

Architecture:

  Asset Registered / Document Analyzed
    ↓
  auto_build_graph_from_analysis()
    ├─ Creates nodes: document, entities, topics, systems, people
    └─ Creates edges: MENTIONS, RELATED_TO, PART_OF, DISCUSSES, GOVERNS
    ↓
  Graph Store (KnowledgeNode + KnowledgeEdge)
    ↓
  Graph Discovery API
    ├─ find_related_entities()
    ├─ find_related_assets()
    ├─ find_dependency_path()
    └─ find_assets_by_entity()
    ↓
  Planner Integration
    └─ KNOWLEDGE_GRAPH tool → graph search → asset discovery → execution plan
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select, or_, and_, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enterprise_models import KnowledgeNode, KnowledgeEdge
from app.db.models import Document, DocAnalysis, Project

logger = logging.getLogger(__name__)


# ── Node Types ───────────────────────────────────────────────────────────


class GraphNodeType(str, Enum):
    """Supported knowledge graph node types."""
    ASSET = "asset"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    CSV = "csv"
    IMAGE = "image"
    SYSTEM = "system"
    APPLICATION = "application"
    WORKFLOW = "workflow"
    PROCESS = "process"
    POLICY = "policy"
    MEETING = "meeting"
    PERSON = "person"
    TEAM = "team"
    DEPARTMENT = "department"
    PROJECT = "project"
    DASHBOARD = "dashboard"
    REPORT = "report"
    ENTITY = "entity"
    TOPIC = "topic"
    DECISION = "decision"
    ACTION = "action"


class GraphEdgeType(str, Enum):
    """Supported knowledge graph edge types."""
    RELATED_TO = "related_to"
    REFERENCES = "references"
    DEPENDS_ON = "depends_on"
    IMPLEMENTS = "implements"
    SUPERSEDES = "supersedes"
    PART_OF = "part_of"
    MENTIONS = "mentions"
    GENERATED_FROM = "generated_from"
    TRANSCRIBED_FROM = "transcribed_from"
    ANALYZED_BY = "analyzed_by"
    OWNS = "owns"
    USES = "uses"
    DISCUSSES = "discusses"
    AFFECTS = "affects"
    GOVERNS = "governs"
    APPEARS_IN = "appears_in"
    LINKED_TO = "linked_to"
    RESPONSIBLE_FOR = "responsible_for"


# ── Main Service ─────────────────────────────────────────────────────────


class KnowledgeGraphService:
    """Enterprise Knowledge Graph service.

    Manages the graph lifecycle: node/edge CRUD, auto-ingestion from
    document analysis, discovery queries, dependency path finding,
    and planner integration.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Node CRUD ────────────────────────────────────────────────────────

    async def create_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        description: str = "",
        metadata: Optional[dict[str, Any]] = None,
        source_document_id: Optional[str] = None,
        source_project_id: Optional[int] = None,
        importance: float = 0.5,
    ) -> KnowledgeNode:
        """Create a knowledge graph node."""
        try:
            # Check if node already exists
            existing = await self.get_node(node_id)
            if existing:
                existing.label = label or existing.label
                existing.description = description or existing.description
                existing.importance = max(existing.importance, importance)
                if metadata:
                    existing_meta = json.loads(existing.metadata_json or "{}")
                    existing_meta.update(metadata)
                    existing.metadata_json = json.dumps(existing_meta)
                existing.updated_at = datetime.utcnow()
                self.db.add(existing)
                await self.db.commit()
                return existing

            node = KnowledgeNode(
                node_id=node_id,
                node_type=node_type,
                label=label,
                description=description,
                metadata_json=json.dumps(metadata or {}),
                source_document_id=uuid.UUID(source_document_id) if source_document_id else None,
                source_project_id=source_project_id,
                importance=importance,
                is_active=True,
            )
            self.db.add(node)
            await self.db.commit()
            logger.info("[GRAPH] Created node %s (type=%s, label=%s)", node_id, node_type, label)
            return node
        except Exception as exc:
            logger.warning("[GRAPH] create_node failed: %s", exc)
            await self.db.rollback()
            raise

    async def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """Get a node by its string node_id."""
        try:
            result = await self.db.execute(
                select(KnowledgeNode).where(KnowledgeNode.node_id == node_id)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.warning("[GRAPH] get_node failed: %s", exc)
            return None

    async def get_node_by_db_id(self, db_id: int) -> Optional[KnowledgeNode]:
        """Get a node by its database primary key."""
        try:
            result = await self.db.execute(
                select(KnowledgeNode).where(KnowledgeNode.id == db_id)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.warning("[GRAPH] get_node_by_db_id failed: %s", exc)
            return None

    async def search_nodes(
        self,
        query: str = "",
        node_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[KnowledgeNode], int]:
        """Search nodes by type and label."""
        try:
            conditions = [KnowledgeNode.is_active == True]

            if query:
                q_filter = f"%{query}%"
                conditions.append(
                    or_(
                        KnowledgeNode.label.ilike(q_filter),
                        KnowledgeNode.description.ilike(q_filter),
                    )
                )

            if node_type:
                conditions.append(KnowledgeNode.node_type == node_type)

            stmt = select(KnowledgeNode).where(and_(*conditions))

            count_stmt = select(sa_func.count()).select_from(stmt.subquery())
            total = (await self.db.execute(count_stmt)).scalar() or 0

            stmt = stmt.order_by(KnowledgeNode.importance.desc().nulls_last())
            stmt = stmt.limit(limit).offset(offset)

            result = await self.db.execute(stmt)
            nodes = list(result.scalars().all())
            return nodes, total
        except Exception as exc:
            logger.warning("[GRAPH] search_nodes failed: %s", exc)
            return [], 0

    async def delete_node(self, node_id: str) -> bool:
        """Soft-delete a node."""
        try:
            node = await self.get_node(node_id)
            if not node:
                return False
            node.is_active = False
            self.db.add(node)
            await self.db.commit()
            return True
        except Exception as exc:
            logger.warning("[GRAPH] delete_node failed: %s", exc)
            await self.db.rollback()
            return False

    # ── Edge CRUD ────────────────────────────────────────────────────────

    async def create_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        relation: str,
        weight: float = 1.0,
        source_document_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Create a directed edge between two nodes."""
        try:
            source = await self.get_node(source_node_id)
            target = await self.get_node(target_node_id)
            if not source or not target:
                logger.warning("[GRAPH] Cannot create edge: node(s) not found (%s -> %s)",
                               source_node_id, target_node_id)
                return False

            # Check for duplicate
            existing_result = await self.db.execute(
                select(KnowledgeEdge).where(
                    KnowledgeEdge.source_node_id == source.id,
                    KnowledgeEdge.target_node_id == target.id,
                    KnowledgeEdge.relation == relation,
                )
            )
            if existing_result.scalar_one_or_none():
                return True  # Already exists

            edge = KnowledgeEdge(
                source_node_id=source.id,
                target_node_id=target.id,
                relation=relation,
                weight=weight,
                source_document_id=uuid.UUID(source_document_id) if source_document_id else None,
                metadata_json=json.dumps(metadata or {}),
            )
            self.db.add(edge)
            await self.db.commit()
            logger.info("[GRAPH] Created edge: %s -[%s]-> %s", source_node_id, relation, target_node_id)
            return True
        except Exception as exc:
            logger.warning("[GRAPH] create_edge failed: %s", exc)
            await self.db.rollback()
            return False

    async def get_edges(
        self, node_id: str, direction: str = "both", limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get all edges for a node (outgoing, incoming, or both)."""
        try:
            node = await self.get_node(node_id)
            if not node:
                return []

            edges: list[dict[str, Any]] = []

            if direction in ("outgoing", "both"):
                result = await self.db.execute(
                    select(KnowledgeEdge).where(
                        KnowledgeEdge.source_node_id == node.id
                    ).limit(limit)
                )
                for edge in result.scalars().all():
                    target = await self.get_node_by_db_id(edge.target_node_id)
                    edges.append({
                        "edge_id": edge.id,
                        "source_node_id": node_id,
                        "source_label": node.label,
                        "target_node_id": target.node_id if target else "unknown",
                        "target_label": target.label if target else "Unknown",
                        "relation": edge.relation,
                        "weight": edge.weight,
                        "direction": "outgoing",
                    })

            if direction in ("incoming", "both"):
                result = await self.db.execute(
                    select(KnowledgeEdge).where(
                        KnowledgeEdge.target_node_id == node.id
                    ).limit(limit)
                )
                for edge in result.scalars().all():
                    source = await self.get_node_by_db_id(edge.source_node_id)
                    edges.append({
                        "edge_id": edge.id,
                        "source_node_id": source.node_id if source else "unknown",
                        "source_label": source.label if source else "Unknown",
                        "target_node_id": node_id,
                        "target_label": node.label,
                        "relation": edge.relation,
                        "weight": edge.weight,
                        "direction": "incoming",
                    })

            return edges
        except Exception as exc:
            logger.warning("[GRAPH] get_edges failed: %s", exc)
            return []

    # ── Graph Discovery ──────────────────────────────────────────────────

    async def _bfs_traverse(
        self,
        start_node: KnowledgeNode,
        max_depth: int = 2,
        max_nodes: int = 50,
    ) -> list[dict[str, Any]]:
        """BFS traversal of the graph from a starting node.

        Returns all nodes and edges reachable within max_depth hops.
        """
        visited: set[int] = set()
        queue: list[tuple[int, int, str]] = [(start_node.id, 0, "")]  # (node_db_id, depth, relation)
        results: list[dict[str, Any]] = []

        while queue and len(results) < max_nodes:
            current_id, depth, incoming_relation = queue.pop(0)

            if current_id in visited:
                continue
            visited.add(current_id)

            current = await self.get_node_by_db_id(current_id)
            if not current:
                continue

            if depth > 0:
                results.append({
                    "node_id": current.node_id,
                    "label": current.label,
                    "type": current.node_type,
                    "depth": depth,
                    "relation": incoming_relation or "related_to",
                })

            if depth >= max_depth:
                continue

            # Outgoing edges
            result = await self.db.execute(
                select(KnowledgeEdge).where(
                    KnowledgeEdge.source_node_id == current_id
                ).limit(10)
            )
            for edge in result.scalars().all():
                if edge.target_node_id not in visited:
                    queue.append((edge.target_node_id, depth + 1, edge.relation))

            # Incoming edges
            result = await self.db.execute(
                select(KnowledgeEdge).where(
                    KnowledgeEdge.target_node_id == current_id
                ).limit(10)
            )
            for edge in result.scalars().all():
                if edge.source_node_id not in visited:
                    queue.append((edge.source_node_id, depth + 1, edge.relation))

        return results

    async def find_related_entities(
        self,
        entity_name: str,
        max_depth: int = 2,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Find all graph nodes related to a given entity via BFS traversal.

        Performs multi-hop traversal from matching entity nodes to discover
        connected assets, systems, policies, people, etc.

        Example: "CRM" → policies → workflows → meetings → dashboards
        """
        try:
            # Find the entity node(s)
            entity_nodes, _ = await self.search_nodes(query=entity_name, limit=5)
            if not entity_nodes:
                return []

            results: list[dict[str, Any]] = []
            seen_node_ids: set[str] = set()

            for start_node in entity_nodes:
                if start_node.node_id in seen_node_ids:
                    continue
                seen_node_ids.add(start_node.node_id)

                # BFS traversal from this node
                discovered = await self._bfs_traverse(
                    start_node, max_depth=max_depth, max_nodes=limit
                )

                # Get edges between start node and discovered nodes
                for d in discovered:
                    node_id = d["node_id"]
                    if node_id not in seen_node_ids:
                        seen_node_ids.add(node_id)
                        # Determine the relationship via edge lookup
                        edges = await self.get_edges(start_node.node_id, direction="outgoing", limit=20)
                        relation = "related_to"
                        for e in edges:
                            if e["target_node_id"] == node_id:
                                relation = e["relation"]
                                break
                        # Also check incoming edges
                        if relation == "related_to":
                            in_edges = await self.get_edges(start_node.node_id, direction="incoming", limit=20)
                            for e in in_edges:
                                if e["source_node_id"] == node_id:
                                    relation = e["relation"]
                                    break

                        results.append({
                            "source_entity": entity_name,
                            "source_node_id": start_node.node_id,
                            "source_type": start_node.node_type,
                            "related_node_id": node_id,
                            "related_label": d["label"],
                            "relation": relation,
                            "depth": d["depth"],
                        })

            return results[:limit]
        except Exception as exc:
            logger.warning("[GRAPH] find_related_entities failed: %s", exc)
            return []

    async def find_related_assets(
        self,
        node_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Find knowledge assets connected to a graph node."""
        try:
            node = await self.get_node(node_id)
            if not node:
                return []

            # Get edges from this node
            edges = await self.get_edges(node_id, direction="outgoing", limit=limit)
            assets = []

            for edge in edges:
                target = await self.get_node(edge["target_node_id"])
                if target and target.node_type in (
                    "document", "audio", "video", "csv", "image",
                    "dashboard", "report",
                ):
                    assets.append({
                        "node_id": target.node_id,
                        "label": target.label,
                        "type": target.node_type,
                        "relation": edge["relation"],
                        "description": target.description,
                    })

            return assets[:limit]
        except Exception as exc:
            logger.warning("[GRAPH] find_related_assets failed: %s", exc)
            return []

    async def find_dependency_path(
        self,
        source_node_id: str,
        target_node_id: str,
        max_depth: int = 5,
    ) -> list[list[dict[str, Any]]]:
        """BFS-based path finding between two nodes."""
        try:
            source = await self.get_node(source_node_id)
            target = await self.get_node(target_node_id)
            if not source or not target:
                return []

            # BFS
            visited: set[int] = set()
            queue: list[tuple[int, list[dict[str, Any]]]] = [
                (source.id, [])
            ]
            paths: list[list[dict[str, Any]]] = []

            while queue and len(paths) < 3:
                current_id, path = queue.pop(0)

                if current_id in visited:
                    continue
                visited.add(current_id)

                if current_id == target.id:
                    paths.append(path)
                    continue

                if len(path) >= max_depth:
                    continue

                # Get outgoing edges
                result = await self.db.execute(
                    select(KnowledgeEdge).where(
                        KnowledgeEdge.source_node_id == current_id
                    )
                )
                for edge in result.scalars().all():
                    if edge.target_node_id not in visited:
                        edge_target = await self.get_node_by_db_id(edge.target_node_id)
                        queue.append((
                            edge.target_node_id,
                            path + [{
                                "from_node": edge_target.node_id if edge_target else "unknown",
                                "from_label": edge_target.label if edge_target else "Unknown",
                                "relation": edge.relation,
                                "to_node": "",
                                "to_label": "",
                            }],
                        ))

            return paths
        except Exception as exc:
            logger.warning("[GRAPH] find_dependency_path failed: %s", exc)
            return []

    async def find_assets_by_entity(
        self,
        entity_name: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Find all knowledge assets connected to a named entity."""
        related = await self.find_related_entities(entity_name, max_depth=2, limit=limit)
        asset_results = []

        for rel in related:
            node = await self.get_node(rel["related_node_id"])
            if node and node.node_type in (
                "document", "audio", "video", "csv", "image",
                "dashboard", "report", "policy", "meeting",
            ):
                asset_results.append({
                    "node_id": node.node_id,
                    "label": node.label,
                    "type": node.node_type,
                    "relation": rel["relation"],
                    "description": node.description[:200] if node.description else "",
                })
            # Also check source
            source_node = await self.get_node(rel["source_node_id"])
            if source_node and source_node.node_type in (
                "document", "audio", "video", "csv", "image",
                "dashboard", "report", "policy", "meeting",
            ) and source_node.node_id != entity_name:
                asset_results.append({
                    "node_id": source_node.node_id,
                    "label": source_node.label,
                    "type": source_node.node_type,
                    "relation": rel["relation"],
                    "description": source_node.description[:200] if source_node.description else "",
                })

        # Deduplicate
        seen: set[str] = set()
        deduped = []
        for a in asset_results:
            if a["node_id"] not in seen:
                seen.add(a["node_id"])
                deduped.append(a)

        return deduped[:limit]

    async def explore_graph(
        self,
        query: str = "",
        node_type: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Explore the graph — returns nodes + edges for visualization."""
        nodes, total = await self.search_nodes(query=query, node_type=node_type, limit=limit)
        node_ids = [n.id for n in nodes]

        # Get all edges between these nodes
        result = await self.db.execute(
            select(KnowledgeEdge).where(
                or_(
                    KnowledgeEdge.source_node_id.in_(node_ids),
                    KnowledgeEdge.target_node_id.in_(node_ids),
                )
            ).limit(limit * 3)
        )
        edges = list(result.scalars().all())

        # Build response
        edge_list = []
        for edge in edges:
            source = await self.get_node_by_db_id(edge.source_node_id)
            target = await self.get_node_by_db_id(edge.target_node_id)
            edge_list.append({
                "source": source.node_id if source else "unknown",
                "target": target.node_id if target else "unknown",
                "relation": edge.relation,
                "weight": edge.weight,
            })

        return {
            "nodes": [n.to_dict() for n in nodes],
            "edges": edge_list,
            "total_nodes": total,
            "total_edges_shown": len(edge_list),
        }

    # ── Auto-Ingestion from Document Analysis ────────────────────────────

    async def add_document_to_graph(
        self,
        document_id: str,
        document_title: str,
        doc_type: str = "",
        project_id: Optional[int] = None,
        analysis: Optional[DocAnalysis] = None,
    ) -> None:
        """Automatically build graph nodes and edges from a document and its analysis.

        Creates:
        - A DOCUMENT/ASSET node for the document itself
        - Entity nodes for each extracted entity
        - Topic nodes for each extracted topic
        - System/policy/meeting nodes based on doc_type + entities
        - Edges connecting document → entities, document → topics
        """
        try:
            # 1. Create document node
            safe_id = _sanitize_node_id(f"doc:{document_id}")
            doc_node_type = self._map_doc_type_to_node_type(doc_type)
            await self.create_node(
                node_id=safe_id,
                node_type=doc_node_type,
                label=document_title or f"Document {document_id[:8]}",
                description=f"Auto-created from document {document_id}",
                source_document_id=document_id,
                source_project_id=project_id,
                importance=1.0,
            )

            if not analysis:
                return

            entities = []
            try:
                entities = json.loads(analysis.entities_json or "[]")
            except Exception:
                pass

            topics = []
            try:
                topics = json.loads(analysis.topics_json or "[]")
            except Exception:
                pass

            # 2. Create entity nodes
            for entity_name in entities:
                if not entity_name or len(entity_name.strip()) < 2:
                    continue
                ent_id = _sanitize_node_id(f"entity:{entity_name.lower()}")
                await self.create_node(
                    node_id=ent_id,
                    node_type=GraphNodeType.ENTITY.value,
                    label=entity_name.strip(),
                    source_document_id=document_id,
                    source_project_id=project_id,
                    importance=0.6,
                )
                # Edge: document MENTIONS entity
                await self.create_edge(
                    source_node_id=safe_id,
                    target_node_id=ent_id,
                    relation=GraphEdgeType.MENTIONS.value,
                    source_document_id=document_id,
                )

            # 3. Create topic nodes
            for topic_name in topics:
                if not topic_name or len(topic_name.strip()) < 2:
                    continue
                topic_id = _sanitize_node_id(f"topic:{topic_name.lower()}")
                await self.create_node(
                    node_id=topic_id,
                    node_type=GraphNodeType.TOPIC.value,
                    label=topic_name.strip(),
                    source_document_id=document_id,
                    source_project_id=project_id,
                    importance=0.5,
                )
                # Edge: document DISCUSSES topic
                await self.create_edge(
                    source_node_id=safe_id,
                    target_node_id=topic_id,
                    relation=GraphEdgeType.DISCUSSES.value,
                    source_document_id=document_id,
                )

            # 4. Detect system/application entities and create typed nodes
            system_keywords = ["crm", "oms", "erp", "scada", "billing", "zums",
                              "ndpm", "hrms", "payroll", "eap", "portal",
                              "dashboard", "analytics", "reporting"]
            for entity_name in entities:
                lower = entity_name.lower().strip()
                if lower in system_keywords or any(kw in lower for kw in system_keywords):
                    sys_id = _sanitize_node_id(f"system:{lower}")
                    await self.create_node(
                        node_id=sys_id,
                        node_type=GraphNodeType.SYSTEM.value,
                        label=entity_name.strip(),
                        source_document_id=document_id,
                        source_project_id=project_id,
                        importance=0.7,
                    )
                    # Edge: document USES system
                    await self.create_edge(
                        source_node_id=safe_id,
                        target_node_id=sys_id,
                        relation=GraphEdgeType.USES.value,
                        source_document_id=document_id,
                    )

            # 5. Create policy node if doc_type is policy
            if doc_type == "policy" or any("policy" in t.lower() for t in topics):
                policy_id = _sanitize_node_id(f"policy:{document_title.lower()[:50]}")
                await self.create_node(
                    node_id=policy_id,
                    node_type=GraphNodeType.POLICY.value,
                    label=document_title or "Policy",
                    description=analysis.executive_summary[:300] if analysis.executive_summary else "",
                    source_document_id=document_id,
                    source_project_id=project_id,
                    importance=0.9,
                )
                # Edge: document IS_A policy
                await self.create_edge(
                    source_node_id=safe_id,
                    target_node_id=policy_id,
                    relation=GraphEdgeType.REFERENCES.value,
                    source_document_id=document_id,
                )

            # 6. Create meeting node if doc_type is meeting
            if doc_type == "meeting" or any("meeting" in t.lower() for t in topics):
                meeting_id = _sanitize_node_id(f"meeting:{document_title.lower()[:50]}")
                await self.create_node(
                    node_id=meeting_id,
                    node_type=GraphNodeType.MEETING.value,
                    label=document_title or "Meeting",
                    source_document_id=document_id,
                    source_project_id=project_id,
                    importance=0.8,
                )
                await self.create_edge(
                    source_node_id=safe_id,
                    target_node_id=meeting_id,
                    relation=GraphEdgeType.PART_OF.value,
                    source_document_id=document_id,
                )

            # 7. Create cross-document edges (entity-based linking)
            # Link related documents via shared entities/topics using
            # multiple edge types (MENTIONS, DISCUSSES, USES)
            _ENTITY_RELATIONS = [
                GraphEdgeType.MENTIONS.value,
                GraphEdgeType.DISCUSSES.value,
                GraphEdgeType.USES.value,
            ]
            for entity_name in entities:
                entity_lower = entity_name.lower().strip()
                if len(entity_lower) < 2:
                    continue
                ent_node_id = _sanitize_node_id(f"entity:{entity_lower}")
                ent_node = await self.get_node(ent_node_id)
                if ent_node:
                    edge_result = await self.db.execute(
                        select(KnowledgeEdge).where(
                            KnowledgeEdge.target_node_id == ent_node.id,
                            KnowledgeEdge.relation.in_(_ENTITY_RELATIONS),
                            KnowledgeEdge.source_node_id != node.id,
                        ).limit(10)
                    )
                    for edge in edge_result.scalars().all():
                        other_doc_node = await self.get_node_by_db_id(edge.source_node_id)
                        if other_doc_node:
                            # Determine edge type based on document types
                            other_type = await self._get_node_type_by_db_id(other_doc_node.id)
                            is_policy = doc_type == "policy" or any("policy" in t.lower() for t in topics)
                            is_meeting = doc_type == "meeting" or any("meeting" in t.lower() for t in topics)
                            is_workflow = other_type in (GraphNodeType.WORKFLOW.value, GraphNodeType.PROCESS.value)
                            if is_policy and is_workflow:
                                edge_relation = GraphEdgeType.GOVERNS.value
                            elif is_meeting and is_workflow:
                                edge_relation = GraphEdgeType.DISCUSSES.value
                            else:
                                edge_relation = GraphEdgeType.RELATED_TO.value
                            await self.create_edge(
                                source_node_id=safe_id,
                                target_node_id=other_doc_node.node_id,
                                relation=edge_relation,
                                source_document_id=document_id,
                                metadata={
                                    "shared_entity": entity_name,
                                    "reason": f"Related via entity: {entity_name}",
                                },
                            )
                            break  # One cross-doc edge per entity is enough

            logger.info(
                "[GRAPH] Added document %s to graph: %d entities, %d topics",
                document_id, len(entities), len(topics),
            )

        except Exception as exc:
            logger.warning("[GRAPH] add_document_to_graph failed: %s", exc)

    async def add_asset_node_to_graph(
        self,
        asset_id: str,
        asset_type: str,
        title: str,
        source_document_id: Optional[str] = None,
        entities: Optional[list[str]] = None,
        topics: Optional[list[str]] = None,
    ) -> None:
        """Add a knowledge asset node to the graph.

        Creates a node for the asset and links it to:
        - Source document (if available)
        - Entity nodes (if provided)
        - Topic nodes (if provided)
        """
        try:
            safe_id = _sanitize_node_id(f"asset:{asset_type}:{asset_id}")
            await self.create_node(
                node_id=safe_id,
                node_type=asset_type,
                label=title or f"{asset_type.upper()} Asset",
                source_document_id=source_document_id,
                importance=0.8,
            )

            # Link to source document
            if source_document_id:
                doc_node_id = _sanitize_node_id(f"doc:{source_document_id}")
                await self.create_edge(
                    source_node_id=doc_node_id,
                    target_node_id=safe_id,
                    relation=GraphEdgeType.GENERATED_FROM.value,
                    source_document_id=source_document_id,
                    metadata={"asset_type": asset_type},
                )

            # Link to entities
            for entity_name in (entities or []):
                if not entity_name or len(entity_name.strip()) < 2:
                    continue
                ent_id = _sanitize_node_id(f"entity:{entity_name.lower()}")
                await self.create_edge(
                    source_node_id=safe_id,
                    target_node_id=ent_id,
                    relation=GraphEdgeType.MENTIONS.value,
                    source_document_id=source_document_id,
                )

            # Link to topics
            for topic_name in (topics or []):
                if not topic_name or len(topic_name.strip()) < 2:
                    continue
                topic_id = _sanitize_node_id(f"topic:{topic_name.lower()}")
                await self.create_edge(
                    source_node_id=safe_id,
                    target_node_id=topic_id,
                    relation=GraphEdgeType.DISCUSSES.value,
                    source_document_id=source_document_id,
                )

            logger.info("[GRAPH] Added %s asset %s to graph", asset_type, asset_id[:8])
        except Exception as exc:
            logger.warning("[GRAPH] add_asset_to_graph failed: %s", exc)

    # ── Planner Integration ──────────────────────────────────────────────

    async def discover_for_question(
        self, question: str, limit: int = 10
    ) -> dict[str, Any]:
        """Discover graph knowledge relevant to a user question.

        Used by the orchestrator to search the knowledge graph BEFORE
        executing tools. Returns discovered entities, assets, and paths.

        Steps:
        1. Search nodes matching the question
        2. Find related entities for each matching node
        3. Find related assets for each matching entity
        4. Return consolidated results
        """
        # Step 1: Search nodes
        nodes, total = await self.search_nodes(query=question, limit=limit)

        discovered_entities: list[str] = []
        discovered_assets: list[dict[str, Any]] = []
        discovered_paths: list[list[dict[str, Any]]] = []

        for node in nodes[:5]:
            # Step 2: Related entities
            related = await self.find_related_entities(node.label, max_depth=1, limit=5)
            for rel in related:
                if rel["related_label"] not in discovered_entities:
                    discovered_entities.append(rel["related_label"])

            # Step 3: Related assets
            assets = await self.find_related_assets(node.node_id, limit=5)
            discovered_assets.extend(assets)

        # Consolidate asset types
        asset_types = set()
        for asset in discovered_assets:
            a_type = asset.get("type", "")
            if a_type in ("audio", "video", "csv", "image", "document",
                          "dashboard", "report", "policy", "meeting"):
                asset_types.add(a_type)

        return {
            "matched_nodes": [n.to_dict() for n in nodes],
            "matched_node_count": total,
            "discovered_entities": discovered_entities[:10],
            "discovered_assets": discovered_assets[:10],
            "asset_types": list(asset_types),
            "graph_summary": f"Found {total} nodes, {len(discovered_entities)} entities, {len(discovered_assets)} assets",
        }

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _map_doc_type_to_node_type(doc_type: str) -> str:
        """Map document type to graph node type."""
        type_map = {
            "policy": GraphNodeType.POLICY.value,
            "frs": GraphNodeType.DOCUMENT.value,
            "meeting": GraphNodeType.MEETING.value,
            "sop": GraphNodeType.PROCESS.value,
            "contract": GraphNodeType.DOCUMENT.value,
            "report": GraphNodeType.REPORT.value,
            "training": GraphNodeType.DOCUMENT.value,
        }
        return type_map.get(doc_type.lower(), GraphNodeType.DOCUMENT.value)

    async def _get_node_type_by_db_id(self, db_id: int) -> Optional[str]:
        """Helper: get a node's type by its database PK.

        Uses self.db (existing session) to avoid creating
        a separate database connection.
        """
        try:
            result = await self.db.execute(
                select(KnowledgeNode.node_type).where(KnowledgeNode.id == db_id)
            )
            return result.scalar_one_or_none()
        except Exception:
            return None

    # ── Stats ────────────────────────────────────────────────────────────

    async def get_graph_stats(self) -> dict[str, Any]:
        """Get overall graph statistics."""
        try:
            # Node counts by type
            node_result = await self.db.execute(
                select(
                    KnowledgeNode.node_type,
                    sa_func.count(KnowledgeNode.id),
                ).where(
                    KnowledgeNode.is_active == True
                ).group_by(KnowledgeNode.node_type)
            )
            node_counts: dict[str, int] = {}
            for row in node_result.all():
                node_counts[row[0]] = row[1]

            # Edge counts by relation
            edge_result = await self.db.execute(
                select(
                    KnowledgeEdge.relation,
                    sa_func.count(KnowledgeEdge.id),
                ).group_by(KnowledgeEdge.relation)
            )
            edge_counts: dict[str, int] = {}
            for row in edge_result.all():
                edge_counts[row[0]] = row[1]

            total_nodes = sum(node_counts.values())
            total_edges = sum(edge_counts.values())

            return {
                "total_nodes": total_nodes,
                "total_edges": total_edges,
                "node_type_counts": node_counts,
                "edge_type_counts": edge_counts,
            }
        except Exception as exc:
            logger.warning("[GRAPH] get_graph_stats failed: %s", exc)
            return {"total_nodes": 0, "total_edges": 0}


# ── Utility ──────────────────────────────────────────────────────────────


def _sanitize_node_id(raw: str) -> str:
    """Sanitize a string for use as a graph node_id.

    Replaces non-alphanumeric characters, truncates to 120 chars.
    """
    # Replace non-alphanumeric with underscores
    safe = re.sub(r'[^a-zA-Z0-9_\-:]', '_', raw)
    # Collapse multiple underscores
    safe = re.sub(r'_+', '_', safe)
    # Truncate
    safe = safe[:120]
    return safe
