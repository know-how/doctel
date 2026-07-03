"""
cache_service.py — DocTel Caching Layer

Provides in-memory caching with TTL support, with optional Redis backend.
Used to avoid database reads on every screen load for frequently-accessed data.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ── Cache Entry ─────────────────────────────────────────────────────────────

@dataclass
class CacheEntry:
    """A single cache entry with TTL."""
    value: Any
    expires_at: float
    tags: list[str] = field(default_factory=list)

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at


# ── In-Memory Cache ─────────────────────────────────────────────────────────

class MemoryCache:
    """Thread-safe in-memory cache with TTL, tagging, and max size."""

    def __init__(self, default_ttl_seconds: int = 300, max_entries: int = 1000):
        self._default_ttl = default_ttl_seconds
        self._max_entries = max_entries
        self._store: Dict[str, CacheEntry] = {}
        self._tag_index: Dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache. Returns None if not found or expired."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.expired:
                await self._evict(key)
                self._misses += 1
                return None
            self._hits += 1
            return entry.value

    async def set(
        self, key: str, value: Any,
        ttl_seconds: Optional[int] = None,
        tags: Optional[list[str]] = None,
    ) -> None:
        """Set a value in cache with optional TTL and tags."""
        async with self._lock:
            # Evict oldest if at capacity
            if len(self._store) >= self._max_entries:
                await self._evict_lru()

            ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
            entry = CacheEntry(
                value=value,
                expires_at=time.time() + ttl,
                tags=tags or [],
            )
            self._store[key] = entry

            # Update tag index
            for tag in entry.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(key)

    async def delete(self, key: str) -> bool:
        """Remove a key from cache."""
        async with self._lock:
            return await self._evict(key)

    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all cache entries with a given tag."""
        async with self._lock:
            keys = self._tag_index.pop(tag, set())
            count = 0
            for key in keys:
                if await self._evict(key):
                    count += 1
            return count

    async def invalidate_by_tags(self, tags: list[str]) -> int:
        """Invalidate all cache entries matching any of the given tags."""
        total = 0
        for tag in tags:
            total += await self.invalidate_by_tag(tag)
        return total

    async def clear(self) -> None:
        """Clear entire cache."""
        async with self._lock:
            self._store.clear()
            self._tag_index.clear()
            self._hits = 0
            self._misses = 0

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        async with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "size": len(self._store),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": round(hit_rate, 1),
                "default_ttl_seconds": self._default_ttl,
                "tags": len(self._tag_index),
            }

    async def _evict(self, key: str) -> bool:
        """Remove a key and its tag references."""
        entry = self._store.pop(key, None)
        if entry is None:
            return False
        for tag in entry.tags:
            tag_set = self._tag_index.get(tag)
            if tag_set:
                tag_set.discard(key)
                if not tag_set:
                    del self._tag_index[tag]
        return True

    async def _evict_lru(self) -> None:
        """Evict the oldest entry (by expiration time)."""
        if not self._store:
            return
        oldest_key = min(self._store.keys(), key=lambda k: self._store[k].expires_at)
        await self._evict(oldest_key)

    async def get_or_compute(
        self, key: str, compute: Callable[[], Any],
        ttl_seconds: Optional[int] = None,
        tags: Optional[list[str]] = None,
    ) -> Any:
        """Get from cache or compute and store."""
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await compute() if asyncio.iscoroutinefunction(compute) else compute()
        await self.set(key, value, ttl_seconds=ttl_seconds, tags=tags)
        return value


# ── Global Cache Instance ───────────────────────────────────────────────────

# Singleton cache instance used throughout the application
cache = MemoryCache(default_ttl_seconds=300, max_entries=2000)


# ── Cache Tag Constants ─────────────────────────────────────────────────────

class CacheTags:
    """Standard cache tags for invalidation."""
    SETTINGS = "settings"
    MODELS = "models"
    PROVIDERS = "providers"
    PROMPTS = "prompts"
    TASK_MAPPING = "task_mapping"
    HEALTH = "health"
    CHAT_MODELS = "chat_models"
    BOOTSTRAP = "bootstrap"


# ── Cache Warmer ────────────────────────────────────────────────────────────

class CacheWarmer:
    """Pre-warms cache with frequently accessed data after startup."""

    def __init__(self):
        self._tasks: list[tuple[str, Callable, int, list[str]]] = []
        self._warmed = False

    def register(
        self, key: str, loader: Callable,
        ttl_seconds: int = 300, tags: Optional[list[str]] = None,
    ) -> None:
        """Register a cache entry to be pre-warmed."""
        self._tasks.append((key, loader, ttl_seconds, tags or []))

    async def warm_all(self) -> None:
        """Execute all registered warm-up tasks."""
        if self._warmed:
            return
        logger.info("Cache warmer: warming %d entries...", len(self._tasks))
        for key, loader, ttl, tags in self._tasks:
            try:
                value = await loader() if asyncio.iscoroutinefunction(loader) else loader()
                await cache.set(key, value, ttl_seconds=ttl, tags=tags)
                logger.debug("Cache warmer: loaded '%s'", key)
            except Exception as e:
                logger.warning("Cache warmer: failed to load '%s': %s", key, e)
        self._warmed = True
        logger.info("Cache warmer: completed")


cache_warmer = CacheWarmer()
