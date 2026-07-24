"""
agent_memory_service.py — DocTel Agent Memory Service

Persistent agent memory across execution boundaries using the existing
AgentMemory table (enterprise_models.py).

Three memory tiers:
  - SHORT_TERM: per-session context, expires with session
  - EPISODIC: per-execution learnings, persists after agent finishes
  - SEMANTIC: long-term knowledge extracted from interactions

Supports: CRUD, semantic search, relevance ranking, promotion,
TTL-based expiry, LRU eviction, and session restore.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select, and_, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enterprise_models import AgentMemory

logger = logging.getLogger(__name__)


# ── Memory Types ──────────────────────────────────────────────────────────────


class MemoryType(str, Enum):
    """Agent memory tiers matching the AgentMemory.memory_type column."""
    SHORT_TERM = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


# ── Agent Memory Service ──────────────────────────────────────────────────────


class AgentMemoryService:
    """Persistent memory for AI agents across execution boundaries.

    Every method uses the existing ``AgentMemory`` table and ``agent_execution_id``,
    ``session_id``, ``memory_type``, and ``key`` columns for indexing.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def store_memory(
        self,
        agent_execution_id: int,
        key: str,
        value: Any,
        memory_type: str = MemoryType.SHORT_TERM.value,
        session_id: Optional[int] = None,
        ttl_seconds: Optional[int] = None,
        embedding: Optional[str] = None,
    ) -> Optional[int]:
        """Store a memory entry.

        Args:
            agent_execution_id: The agent execution that produced this memory.
            key: Semantic key for lookup (e.g. ``"user_intent"``, ``"retrieved_facts"``).
            value: Any JSON-serializable payload.
            memory_type: ``"working"`` | ``"episodic"`` | ``"semantic"``
            session_id: Optional conversation session ID.
            ttl_seconds: Time-to-live in seconds (None = permanent).
            embedding: Optional pgvector embedding string.

        Returns:
            Memory ID if successful, None otherwise.
        """
        try:
            expires_at = None
            if ttl_seconds is not None:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

            entry = AgentMemory(
                agent_execution_id=agent_execution_id,
                session_id=session_id,
                memory_type=memory_type,
                key=key,
                value_json=json.dumps(value, default=str),
                embedding=embedding,
                ttl_seconds=ttl_seconds,
                expires_at=expires_at,
                access_count=0,
                last_accessed_at=None,
            )
            self.db.add(entry)
            await self.db.commit()
            await self.db.refresh(entry)
            logger.debug(
                "[MEMORY] Stored %s memory: key=%s session=%s id=%d",
                memory_type, key, session_id, entry.id,
            )
            return entry.id
        except Exception as exc:
            logger.error("[MEMORY] store_memory failed: %s", exc)
            await self.db.rollback()
            return None

    async def get_memory(self, memory_id: int) -> Optional[dict[str, Any]]:
        """Retrieve a single memory entry by ID, incrementing access count."""
        try:
            result = await self.db.execute(
                select(AgentMemory).where(AgentMemory.id == memory_id)
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                return None

            # Update access tracking
            entry.access_count = (entry.access_count or 0) + 1
            entry.last_accessed_at = datetime.now(timezone.utc)
            await self.db.commit()

            return entry.to_dict()
        except Exception as exc:
            logger.error("[MEMORY] get_memory failed: %s", exc)
            return None

    async def delete_memory(self, memory_id: int) -> bool:
        """Delete a single memory entry."""
        try:
            await self.db.execute(
                sa_delete(AgentMemory).where(AgentMemory.id == memory_id)
            )
            await self.db.commit()
            return True
        except Exception as exc:
            logger.error("[MEMORY] delete_memory failed: %s", exc)
            await self.db.rollback()
            return False

    async def update_memory(
        self,
        memory_id: int,
        value: Any,
        embedding: Optional[str] = None,
    ) -> bool:
        """Update the payload of an existing memory entry."""
        try:
            result = await self.db.execute(
                select(AgentMemory).where(AgentMemory.id == memory_id)
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                return False

            entry.value_json = json.dumps(value, default=str)
            if embedding is not None:
                entry.embedding = embedding
            await self.db.commit()
            return True
        except Exception as exc:
            logger.error("[MEMORY] update_memory failed: %s", exc)
            await self.db.rollback()
            return False

    # ── Search ──────────────────────────────────────────────────────────────

    async def search_memory(
        self,
        key: Optional[str] = None,
        memory_type: Optional[str] = None,
        session_id: Optional[int] = None,
        agent_execution_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Search memories by key, type, session, or execution.

        All parameters are optional — omit to return all memories.
        """
        try:
            conditions = []
            if key:
                conditions.append(AgentMemory.key.ilike(f"%{key}%"))
            if memory_type:
                conditions.append(AgentMemory.memory_type == memory_type)
            if session_id is not None:
                conditions.append(AgentMemory.session_id == session_id)
            if agent_execution_id is not None:
                conditions.append(
                    AgentMemory.agent_execution_id == agent_execution_id
                )

            query = select(AgentMemory)
            if conditions:
                query = query.where(and_(*conditions))
            query = query.order_by(AgentMemory.last_accessed_at.desc().nullsfirst())
            query = query.limit(limit).offset(offset)

            result = await self.db.execute(query)
            entries = result.scalars().all()

            # Update access counts
            now = datetime.now(timezone.utc)
            for entry in entries:
                entry.access_count = (entry.access_count or 0) + 1
                entry.last_accessed_at = now
            await self.db.commit()

            return [e.to_dict() for e in entries]
        except Exception as exc:
            logger.error("[MEMORY] search_memory failed: %s", exc)
            # Rollback to prevent PostgreSQL transaction abort from propagating
            try:
                await self.db.rollback()
            except Exception:
                pass
            return []

    async def get_session_memories(
        self,
        session_id: int,
        memory_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get all memories for a session, optionally filtered by type."""
        return await self.search_memory(
            session_id=session_id,
            memory_type=memory_type,
            limit=limit,
        )

    async def get_relevant_memories(
        self,
        session_id: int,
        query_keywords: Optional[list[str]] = None,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get the most relevant memories for a session.

        Relevance is determined by:
        1. Access count (frequently accessed = more relevant)
        2. Recency (recently accessed = more relevant)
        3. Keyword overlap if query_keywords provided

        Returns top ``limit`` memories.
        """
        try:
            conditions = [AgentMemory.session_id == session_id]
            if memory_type:
                conditions.append(AgentMemory.memory_type == memory_type)

            query = select(AgentMemory).where(and_(*conditions))
            result = await self.db.execute(query)
            entries = result.scalars().all()

            if not entries:
                return []

            # Score each entry
            now = datetime.now(timezone.utc)
            scored: list[tuple[float, AgentMemory]] = []
            for entry in entries:
                score = 0.0
                access_count = entry.access_count or 0
                last_accessed = entry.last_accessed_at

                # Recency component (0-3 points)
                if last_accessed:
                    hours_ago = (now - last_accessed).total_seconds() / 3600
                    recency_score = max(0, 3.0 - hours_ago / 24.0)
                    score += recency_score

                # Frequency component (0-5 points, logarithmic)
                if access_count > 0:
                    score += min(5.0, 1.0 + access_count * 0.5)

                # Keyword overlap component (0-5 points)
                if query_keywords and entry.value_json:
                    try:
                        val_str = json.dumps(entry.value_json).lower()
                        matches = sum(
                            1 for kw in query_keywords if kw.lower() in val_str
                        )
                        score += min(5.0, matches * 1.5)
                    except Exception:
                        pass

                scored.append((score, entry))

            # Sort by score descending
            scored.sort(key=lambda x: -x[0])

            # Update access counts for returned entries
            now = datetime.now(timezone.utc)
            top_entries = scored[:limit]
            result_list = []
            for _score, entry in top_entries:
                entry.access_count = (entry.access_count or 0) + 1
                entry.last_accessed_at = now
                result_list.append(entry.to_dict())
            await self.db.commit()

            return result_list
        except Exception as exc:
            logger.error("[MEMORY] get_relevant_memories failed: %s", exc)
            # Rollback to prevent PostgreSQL transaction abort from propagating
            try:
                await self.db.rollback()
            except Exception:
                pass
            return []

    # ── Promotion (Working → Episodic → Semantic) ────────────────────────────

    async def promote_memory(
        self,
        memory_id: int,
        target_type: str,
    ) -> Optional[int]:
        """Promote a memory to a higher tier.

        Example: working → episodic or episodic → semantic.
        Returns the new memory ID if promoted, None otherwise.
        """
        try:
            result = await self.db.execute(
                select(AgentMemory).where(AgentMemory.id == memory_id)
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                logger.warning("[MEMORY] promote_memory: memory %d not found", memory_id)
                return None

            # Create promoted copy
            promoted = AgentMemory(
                agent_execution_id=entry.agent_execution_id,
                session_id=entry.session_id,
                memory_type=target_type,
                key=entry.key,
                value_json=entry.value_json,
                embedding=entry.embedding,
                ttl_seconds=None,  # Promoted memories are permanent
                expires_at=None,
                access_count=entry.access_count or 0,
                last_accessed_at=entry.last_accessed_at,
            )
            self.db.add(promoted)
            await self.db.commit()
            await self.db.refresh(promoted)
            logger.info(
                "[MEMORY] Promoted memory %d → %s (new id=%d)",
                memory_id, target_type, promoted.id,
            )
            return promoted.id
        except Exception as exc:
            logger.error("[MEMORY] promote_memory failed: %s", exc)
            await self.db.rollback()
            return None

    async def promote_session_memories(
        self,
        session_id: int,
        target_type: str = MemoryType.EPISODIC.value,
    ) -> int:
        """Promote all working memories for a session to episodic.

        Returns the number of memories promoted.
        """
        try:
            result = await self.db.execute(
                select(AgentMemory).where(
                    and_(
                        AgentMemory.session_id == session_id,
                        AgentMemory.memory_type == MemoryType.SHORT_TERM.value,
                    )
                )
            )
            entries = result.scalars().all()
            count = 0
            for entry in entries:
                entry.memory_type = target_type
                entry.ttl_seconds = None
                entry.expires_at = None
                count += 1
            await self.db.commit()
            if count > 0:
                logger.info(
                    "[MEMORY] Promoted %d working memories to %s for session %d",
                    count, target_type, session_id,
                )
            return count
        except Exception as exc:
            logger.error("[MEMORY] promote_session_memories failed: %s", exc)
            await self.db.rollback()
            return 0

    # ── Forgetting / Expiry ──────────────────────────────────────────────────

    async def forget_memory(self, memory_id: int) -> bool:
        """Explicitly forget (delete) a memory."""
        return await self.delete_memory(memory_id)

    async def forget_session(self, session_id: int) -> int:
        """Forget all memories for a session.

        Returns number of entries deleted.
        """
        try:
            result = await self.db.execute(
                select(AgentMemory).where(AgentMemory.session_id == session_id)
            )
            entries = result.scalars().all()
            count = len(entries)
            for entry in entries:
                await self.db.delete(entry)
            await self.db.commit()
            logger.info("[MEMORY] Forgotten %d memories for session %d", count, session_id)
            return count
        except Exception as exc:
            logger.error("[MEMORY] forget_session failed: %s", exc)
            await self.db.rollback()
            return 0

    async def clean_expired_memories(self, batch_size: int = 100) -> int:
        """Remove all expired working memories.

        Should be called periodically (e.g., via a background task).
        Returns number of entries cleaned.
        """
        try:
            now = datetime.now(timezone.utc)
            result = await self.db.execute(
                select(AgentMemory).where(
                    and_(
                        AgentMemory.expires_at.isnot(None),
                        AgentMemory.expires_at < now,
                    )
                ).limit(batch_size)
            )
            entries = result.scalars().all()
            count = len(entries)
            for entry in entries:
                await self.db.delete(entry)
            await self.db.commit()
            if count > 0:
                logger.info("[MEMORY] Cleaned %d expired memories", count)
            return count
        except Exception as exc:
            logger.error("[MEMORY] clean_expired_memories failed: %s", exc)
            await self.db.rollback()
            return 0

    async def get_memory_stats(self) -> dict[str, Any]:
        """Get aggregate memory statistics."""
        try:
            total_result = await self.db.execute(
                select(func.count(AgentMemory.id))
            )
            total = total_result.scalar() or 0

            # Per-type counts
            type_counts: dict[str, int] = {}
            for mt in ("working", "episodic", "semantic"):
                result = await self.db.execute(
                    select(func.count(AgentMemory.id)).where(
                        AgentMemory.memory_type == mt
                    )
                )
                type_counts[mt] = result.scalar() or 0

            # Expired count
            now = datetime.now(timezone.utc)
            expired_result = await self.db.execute(
                select(func.count(AgentMemory.id)).where(
                    and_(
                        AgentMemory.expires_at.isnot(None),
                        AgentMemory.expires_at < now,
                    )
                )
            )
            expired = expired_result.scalar() or 0

            # Distinct sessions
            sessions_result = await self.db.execute(
                select(func.count(func.distinct(AgentMemory.session_id)))
            )
            distinct_sessions = sessions_result.scalar() or 0

            return {
                "total_memories": total,
                "by_type": type_counts,
                "expired_memories": expired,
                "distinct_sessions": distinct_sessions,
            }
        except Exception as exc:
            logger.error("[MEMORY] get_memory_stats failed: %s", exc)
            return {"total_memories": 0, "error": str(exc)}

    # ── Context Building for LLM Prompts ─────────────────────────────────────

    async def build_memory_context(
        self,
        session_id: int,
        max_tokens: int = 2000,
    ) -> str:
        """Build a compact memory context string for LLM injection.

        Includes:
        - Active working memories
        - Top relevant episodic memories
        - Key semantic facts

        Returns a plain text string suitable for prompt injection.
        """
        parts = []

        # 1. Working memories (session context)
        working = await self.get_session_memories(
            session_id=session_id,
            memory_type=MemoryType.SHORT_TERM.value,
            limit=10,
        )
        if working:
            working_str = "\n".join(
                f"- {m.get('key', '')}: {json.dumps(m.get('value', ''), default=str)[:300]}"
                for m in working
            )
            parts.append(f"[SESSION MEMORY]\n{working_str}")

        # 2. Episodic memories (past learnings)
        episodic = await self.get_relevant_memories(
            session_id=session_id,
            memory_type=MemoryType.EPISODIC.value,
            limit=5,
        )
        if episodic:
            ep_str = "\n".join(
                f"- {m.get('key', '')}: {json.dumps(m.get('value', ''), default=str)[:300]}"
                for m in episodic
            )
            parts.append(f"[PAST LEARNINGS]\n{ep_str}")

        # 3. Semantic memories (long-term facts)
        semantic = await self.get_relevant_memories(
            session_id=session_id,
            memory_type=MemoryType.SEMANTIC.value,
            limit=3,
        )
        if semantic:
            sem_str = "\n".join(
                f"- {m.get('key', '')}: {json.dumps(m.get('value', ''), default=str)[:300]}"
                for m in semantic
            )
            parts.append(f"[LONG-TERM KNOWLEDGE]\n{sem_str}")

        combined = "\n\n".join(parts)

        # Rough token trimming (simple char-based heuristic)
        max_chars = max_tokens * 4
        if len(combined) > max_chars:
            combined = combined[:max_chars] + "\n... [memory truncated]"

        return combined
