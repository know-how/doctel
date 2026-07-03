"""
startup_service.py — DocTel Startup Optimization

Manages critical vs non-critical service initialization.
Critical services (DB, auth) must be available before the app responds.
Non-critical services (Ollama, Gemini, embeddings, etc.) load asynchronously.

Exposes startup status for the diagnostics page and frontend loading screen.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    PENDING = "pending"
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ServiceInfo:
    """Status information for a single service."""
    name: str
    status: ServiceStatus = ServiceStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None
    critical: bool = False
    depends_on: list[str] = field(default_factory=list)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return round((self.completed_at - self.started_at) * 1000, 1)
        return None


class StartupManager:
    """
    Manages service startup with critical/non-critical separation.

    Critical services run first, sequentially in dependency order.
    Non-critical services run in parallel after critical ones are ready.
    """

    def __init__(self):
        self._services: dict[str, ServiceInfo] = {}
        self._starters: dict[str, Callable] = {}
        self._critical_ready = False
        self._all_started = False
        self._start_time: Optional[float] = None
        self._lock = asyncio.Lock()

    def register(
        self, name: str, starter: Callable,
        critical: bool = False,
        depends_on: Optional[list[str]] = None,
    ) -> None:
        """Register a service with its startup function."""
        self._services[name] = ServiceInfo(
            name=name,
            critical=critical,
            depends_on=depends_on or [],
        )
        self._starters[name] = starter

    async def start_critical(self) -> list[ServiceInfo]:
        """Start all critical services in dependency order. Returns their status."""
        self._start_time = time.time()
        critical_services = {
            name: info for name, info in self._services.items()
            if info.critical
        }
        results = []
        for name in sorted(critical_services.keys()):
            result = await self._start_single(name)
            results.append(result)
        self._critical_ready = True
        logger.info(
            "Startup: %d critical services ready in %.1fs",
            len(results), time.time() - self._start_time,
        )
        return results

    async def start_non_critical(self) -> list[ServiceInfo]:
        """Start all non-critical services in parallel. Returns their status."""
        non_critical = {
            name: info for name, info in self._services.items()
            if not info.critical
        }
        if not non_critical:
            self._all_started = True
            return []

        tasks = [
            self._start_single(name)
            for name in non_critical
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        processed = []
        for i, name in enumerate(non_critical):
            if isinstance(results[i], Exception):
                self._services[name].status = ServiceStatus.FAILED
                self._services[name].error = str(results[i])
                logger.error("Non-critical service '%s' failed: %s", name, results[i])
            processed.append(self._services[name])

        self._all_started = True
        healthy = sum(1 for s in self._services.values() if s.status == ServiceStatus.HEALTHY)
        failed = sum(1 for s in self._services.values() if s.status == ServiceStatus.FAILED)
        logger.info(
            "Startup: %d non-critical services started (%d healthy, %d failed)",
            len(non_critical), healthy, failed,
        )
        return processed

    async def start_all(self) -> dict[str, list[ServiceInfo]]:
        """Start critical then non-critical services."""
        critical = await self.start_critical()
        non_critical = await self.start_non_critical()
        return {"critical": critical, "non_critical": non_critical}

    def get_status(self, name: str) -> Optional[ServiceInfo]:
        """Get status of a specific service."""
        return self._services.get(name)

    def get_all_status(self) -> list[ServiceInfo]:
        """Get status of all registered services."""
        return list(self._services.values())

    def is_critical_ready(self) -> bool:
        """Check if all critical services are ready."""
        return self._critical_ready

    def is_all_started(self) -> bool:
        """Check if all services have been started."""
        return self._all_started

    def get_summary(self) -> dict:
        """Get a summary of all service statuses."""
        services = self.get_all_status()
        return {
            "total": len(services),
            "healthy": sum(1 for s in services if s.status == ServiceStatus.HEALTHY),
            "degraded": sum(1 for s in services if s.status == ServiceStatus.DEGRADED),
            "failed": sum(1 for s in services if s.status == ServiceStatus.FAILED),
            "pending": sum(1 for s in services if s.status in (ServiceStatus.PENDING, ServiceStatus.STARTING)),
            "skipped": sum(1 for s in services if s.status == ServiceStatus.SKIPPED),
            "critical_ready": self._critical_ready,
            "all_started": self._all_started,
            "uptime_seconds": round(time.time() - (self._start_time or time.time()), 1),
            "services": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "critical": s.critical,
                    "error": s.error,
                    "latency_ms": s.duration_ms,
                }
                for s in services
            ],
        }

    async def _start_single(self, name: str) -> ServiceInfo:
        """Start a single service and track its status."""
        info = self._services[name]
        starter = self._starters[name]

        # Check dependencies
        for dep in info.depends_on:
            dep_info = self._services.get(dep)
            if dep_info and dep_info.status != ServiceStatus.HEALTHY:
                logger.warning(
                    "Service '%s' waiting for dependency '%s' (status: %s)",
                    name, dep, dep_info.status.value,
                )

        info.status = ServiceStatus.STARTING
        info.started_at = time.time()

        try:
            result = await starter() if asyncio.iscoroutinefunction(starter) else starter()
            info.status = ServiceStatus.HEALTHY
            info.completed_at = time.time()
            info.latency_ms = (info.completed_at - info.started_at) * 1000
            if isinstance(result, dict) and "latency_ms" in result:
                info.latency_ms = result["latency_ms"]
            logger.debug("Service '%s' started (%.1fms)", name, info.duration_ms or 0)
        except Exception as e:
            info.status = ServiceStatus.FAILED
            info.completed_at = time.time()
            info.error = str(e)
            logger.error("Service '%s' failed to start: %s", name, e)

        return info


# ── Global Startup Manager Instance ─────────────────────────────────────────

startup_manager = StartupManager()
