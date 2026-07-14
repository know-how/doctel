"""
config_service.py — Unified DB-Backed Configuration Service

Provides CRUD operations for all configuration entities now stored in MySQL:
  - SystemConfig  (key/value app settings — replaces config.yaml + .env)
  - AIProvider    (provider registrations)
  - AIModel       (model catalogues)
  - TaskMapping   (task → model routing)
  - HealthRecord  (health ping history)
  - AuditLog      (governance trail)

Every function is async and expects an `AsyncSession` from ``app.db.database``.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from sqlalchemy import select, update, delete, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config_models import (
    SystemConfig,
    AIProvider,
    AIModel,
    TaskMapping,
    HealthRecord,
    SyncLog,
    AuditLog,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

async def get_config(key: str, db: AsyncSession) -> Optional[Any]:
    """Get a single config value by key."""
    res = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    row = res.scalar_one_or_none()
    return row.get_value() if row else None


async def get_config_str(key: str, db: AsyncSession, default: str = "") -> str:
    """Get config as string."""
    val = await get_config(key, db)
    return str(val) if val is not None else default


async def get_config_bool(key: str, db: AsyncSession, default: bool = False) -> bool:
    """Get config as boolean."""
    val = await get_config(key, db)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("1", "true", "yes", "on")


async def get_config_int(key: str, db: AsyncSession, default: int = 0) -> int:
    """Get config as integer."""
    val = await get_config(key, db)
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


async def set_config(key: str, value: Any, db: AsyncSession,
                     description: str = "") -> SystemConfig:
    """Upsert a single config key/value."""
    res = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    row = res.scalar_one_or_none()
    if row:
        row.value_json = json.dumps(value, default=str)
        if description:
            row.description = description
    else:
        row = SystemConfig.set_value(key, value, description)
        db.add(row)
    await db.commit()
    return row


async def get_all_config(db: AsyncSession) -> dict[str, Any]:
    """Return all config as a flat dict."""
    res = await db.execute(select(SystemConfig).order_by(SystemConfig.key))
    rows = res.scalars().all()
    return {r.key: r.get_value() for r in rows}


async def delete_config(key: str, db: AsyncSession) -> bool:
    """Delete a config entry. Returns True if existed."""
    res = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    row = res.scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()
        return True
    return False


async def get_config_by_prefix(prefix: str, db: AsyncSession) -> dict[str, Any]:
    """Get all config entries whose key starts with prefix."""
    res = await db.execute(
        select(SystemConfig).where(SystemConfig.key.startswith(prefix))
        .order_by(SystemConfig.key)
    )
    return {r.key: r.get_value() for r in res.scalars().all()}


async def get_config_section(section: str, db: AsyncSession) -> dict[str, Any]:
    """Get config keys nested under a section (e.g. 'app', 'api', 'storage')."""
    prefix = f"{section}."
    raw = await get_config_by_prefix(prefix, db)
    out = {}
    for key, value in raw.items():
        sub_key = key[len(prefix):]
        parts = sub_key.split(".")
        target = out
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
    return out


# ═══════════════════════════════════════════════════════════════════════════════
#  AI PROVIDERS
# ═══════════════════════════════════════════════════════════════════════════════

async def get_all_providers(db: AsyncSession) -> List[AIProvider]:
    """Get all providers ordered by sort_order."""
    res = await db.execute(
        select(AIProvider).order_by(AIProvider.sort_order, AIProvider.name)
    )
    return list(res.scalars().all())


async def get_provider_by_id(provider_id: str, db: AsyncSession) -> Optional[AIProvider]:
    """Get a single provider by its string provider_id."""
    res = await db.execute(
        select(AIProvider).where(AIProvider.provider_id == provider_id)
    )
    return res.scalar_one_or_none()


async def get_provider_by_pk(pk: int, db: AsyncSession) -> Optional[AIProvider]:
    """Get a single provider by its primary key (id)."""
    res = await db.execute(select(AIProvider).where(AIProvider.id == pk))
    return res.scalar_one_or_none()


async def add_provider(
    db: AsyncSession,
    provider_id: str,
    name: str,
    vendor: str = "",
    base_url: str = "",
    api_key_value: str = "",
    description: str = "",
    icon: str = "generic",
    sort_order: int = 0,
    provider_type: str = "openai",
    models_endpoint: str = "",
    chat_endpoint: str = "",
    messages_endpoint: str = "",
    embeddings_endpoint: str = "",
    health_endpoint: str = "",
    visible_to_users: bool = True,
) -> AIProvider:
    """Create a new provider with flexible endpoint configuration."""
    exists = await get_provider_by_id(provider_id, db)
    if exists:
        raise ValueError(f"Provider '{provider_id}' already exists")

    provider = AIProvider(
        provider_id=provider_id,
        name=name,
        vendor=vendor or name,
        base_url=base_url,
        api_key_value=api_key_value,
        status="disconnected",
        is_connected=False,
        description=description,
        icon=icon,
        sort_order=sort_order,
        provider_type=provider_type,
        models_endpoint=models_endpoint,
        chat_endpoint=chat_endpoint,
        messages_endpoint=messages_endpoint,
        embeddings_endpoint=embeddings_endpoint,
        health_endpoint=health_endpoint,
        visible_to_users=visible_to_users,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


async def update_provider(
    db: AsyncSession,
    provider_id: str,
    updates: dict,
) -> Optional[AIProvider]:
    """Update provider fields. `updates` maps column names to values."""
    provider = await get_provider_by_id(provider_id, db)
    if not provider:
        return None

    safe_fields = {
        "name", "vendor", "base_url", "api_key_value",
        "description", "icon", "sort_order", "status", "is_connected",
        "last_tested_at", "provider_type", "models_endpoint", "chat_endpoint",
        "messages_endpoint", "embeddings_endpoint", "health_endpoint",
    }
    for field, value in updates.items():
        if field in safe_fields:
            setattr(provider, field, value)

    await db.commit()
    await db.refresh(provider)
    return provider


async def update_provider_status(
    db: AsyncSession,
    provider_id: str,
    status: str,
    is_connected: bool = False,
    error_msg: str = "",
) -> Optional[AIProvider]:
    """Quick helper to update provider connection status."""
    return await update_provider(db, provider_id, {
        "status": status,
        "is_connected": is_connected,
    })


async def delete_provider(db: AsyncSession, provider_id: str) -> bool:
    """Delete a provider and its cascaded models."""
    provider = await get_provider_by_id(provider_id, db)
    if not provider:
        return False
    await db.delete(provider)
    await db.commit()
    return True


# ═══════════════════════════════════════════════════════════════════════════════
#  AI MODELS
# ═══════════════════════════════════════════════════════════════════════════════

async def get_models_by_provider(provider_pk: int, db: AsyncSession) -> List[AIModel]:
    """Get all models for a given provider (primary key)."""
    res = await db.execute(
        select(AIModel).where(AIModel.provider_id == provider_pk)
        .order_by(AIModel.model_id)
    )
    return list(res.scalars().all())


async def get_models_by_provider_id(provider_id_str: str, db: AsyncSession) -> List[AIModel]:
    """Get all models for a provider by its string provider_id."""
    provider = await get_provider_by_id(provider_id_str, db)
    if not provider:
        return []
    return await get_models_by_provider(provider.id, db)


async def get_model_by_model_id(provider_pk: int, model_id: str,
                                db: AsyncSession) -> Optional[AIModel]:
    """Get a specific model within a provider."""
    res = await db.execute(
        select(AIModel).where(
            AIModel.provider_id == provider_pk,
            AIModel.model_id == model_id,
        )
    )
    return res.scalar_one_or_none()


async def add_model(
    db: AsyncSession,
    provider_id_str: str,
    model_id: str,
    display_name: str,
    context_window: int = 4096,
    capabilities: Optional[dict[str, bool]] = None,
    state: str = "available",
    pricing_tier: str = "free",
    license: str = "Proprietary",
    allowed_roles: Optional[list] = None,
    department_restrictions: Optional[list] = None,
    for_tasks: Optional[list] = None,
    is_default: bool = False,
) -> AIModel:
    """Add a model to a provider by its string provider_id."""
    provider = await get_provider_by_id(provider_id_str, db)
    if not provider:
        raise ValueError(f"Provider '{provider_id_str}' not found")

    caps = capabilities or {}

    model = AIModel(
        provider_id=provider.id,
        model_id=model_id,
        display_name=display_name,
        context_window=context_window,
        supports_chat=caps.get("chat", True),
        supports_vision=caps.get("vision", False),
        supports_tools=caps.get("tools", False),
        supports_code=caps.get("code", False),
        supports_embedding=caps.get("embedding", False),
        supports_reasoning=caps.get("reasoning", False),
        supports_rag=caps.get("rag", False),
        supports_classification=caps.get("classification", False),
        supports_summary=caps.get("summary", False),
        supports_extraction=caps.get("extraction", False),
        supports_audio=caps.get("audio", False),
        supports_comparison=caps.get("comparison", False),
        state=state,
        is_default=is_default,
        pricing_tier=pricing_tier,
        license=license,
        allowed_roles=json.dumps(allowed_roles or []),
        department_restrictions=json.dumps(department_restrictions or []),
        for_tasks=json.dumps(for_tasks or []),
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


async def update_model(
    db: AsyncSession,
    provider_id_str: str,
    model_id: str,
    updates: dict,
) -> Optional[AIModel]:
    """Update model fields."""
    provider = await get_provider_by_id(provider_id_str, db)
    if not provider:
        return None
    model = await get_model_by_model_id(provider.id, model_id, db)
    if not model:
        return None

    safe_fields = {
        "display_name", "context_window", "state", "is_default", "pricing_tier", "license",
        "supports_chat", "supports_vision", "supports_tools", "supports_code",
        "supports_embedding", "supports_reasoning", "supports_rag",
        "supports_classification", "supports_summary", "supports_extraction",
        "supports_audio", "supports_comparison",
        "allowed_roles", "department_restrictions", "for_tasks",
        "visible_to_users",
    }
    for field, value in updates.items():
        if field in safe_fields:
            # Serialize list fields
            if field in ("allowed_roles", "department_restrictions", "for_tasks") and isinstance(value, list):
                value = json.dumps(value)
            setattr(model, field, value)

    await db.commit()
    await db.refresh(model)
    return model


async def delete_model(db: AsyncSession, provider_id_str: str, model_id: str) -> bool:
    """Delete a model."""
    provider = await get_provider_by_id(provider_id_str, db)
    if not provider:
        return False
    model = await get_model_by_model_id(provider.id, model_id, db)
    if not model:
        return False
    await db.delete(model)
    await db.commit()
    return True


async def get_all_enabled_chat_models(db: AsyncSession) -> List[dict]:
    """Get all models that support chat and are active."""
    res = await db.execute(
        select(AIModel).where(
            AIModel.supports_chat == True,  # noqa: E712
            AIModel.state.in_(['active', 'available']),  # Use state instead of enabled
        )
    )
    models = res.scalars().all()
    result = []
    for m in models:
        d = m.to_dict()
        # Include provider info
        prov_res = await db.execute(select(AIProvider).where(AIProvider.id == m.provider_id))
        prov = prov_res.scalar_one_or_none()
        if prov:
            d["providerName"] = prov.name
            d["providerId"] = prov.provider_id
        result.append(d)
    return result


async def get_all_enabled_models(db: AsyncSession) -> List[dict]:
    """Get all active/available models regardless of visibility."""
    res = await db.execute(
        select(AIModel).where(AIModel.state.in_(['active', 'available'])).order_by(AIModel.display_name)  # noqa: E712
    )
    return [m.to_dict() for m in res.scalars().all()]


# ═══════════════════════════════════════════════════════════════════════════════
#  TASK MAPPING
# ═══════════════════════════════════════════════════════════════════════════════

TASK_TYPES = [
    "chat", "summary", "extraction", "classification",
    "comparison", "vision", "embedding", "rag", "code_generation",
]


async def get_task_mapping(db: AsyncSession) -> dict[str, dict]:
    """Get all task mappings as {task_type: {providerId, modelId, ...}}."""
    res = await db.execute(select(TaskMapping))
    out = {}
    for row in res.scalars().all():
        out[row.task_type] = row.to_dict()
    return out


async def get_task_mapping_for(task_type: str, db: AsyncSession) -> Optional[dict]:
    """Get the model mapping for a specific task type."""
    res = await db.execute(
        select(TaskMapping).where(TaskMapping.task_type == task_type)
    )
    row = res.scalar_one_or_none()
    return row.to_dict() if row else None


async def set_task_mapping(
    db: AsyncSession,
    task_type: str,
    provider_id: str,
    model_id: str,
    is_active: bool = True,
) -> TaskMapping:
    """Upsert a task → model mapping."""
    res = await db.execute(
        select(TaskMapping).where(TaskMapping.task_type == task_type)
    )
    row = res.scalar_one_or_none()
    if row:
        row.provider_id_ref = provider_id
        row.model_id = model_id
        row.is_active = is_active
    else:
        row = TaskMapping(
            task_type=task_type,
            provider_id_ref=provider_id,
            model_id=model_id,
            is_active=is_active,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def delete_task_mapping(db: AsyncSession, task_type: str) -> bool:
    """Delete a task mapping."""
    res = await db.execute(
        select(TaskMapping).where(TaskMapping.task_type == task_type)
    )
    row = res.scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()
        return True
    return False


async def select_best_model_for_task(task_type: str, db: AsyncSession) -> Optional[dict]:
    """Select the best model for a task type using task mapping + fallback."""
    # 1. Check explicit task mapping
    mapping = await get_task_mapping_for(task_type, db)
    if mapping and mapping.get("isActive"):
        provider_id = mapping["providerId"]
        model_id = mapping["modelId"]
        provider = await get_provider_by_id(provider_id, db)
        if provider:
            model = await get_model_by_model_id(provider.id, model_id, db)
            if model and model.state in ('active', 'available'):
                return {
                    "providerId": provider_id,
                    "modelId": model_id,
                    "source": "task_mapping",
                }
    # 2. Fallback: find any enabled model supporting this task
    cap_map = {
        "chat": "supports_chat",
        "summary": "supports_summary",
        "extraction": "supports_extraction",
        "classification": "supports_classification",
        "comparison": "supports_comparison",
        "vision": "supports_vision",
        "embedding": "supports_embedding",
        "rag": "supports_rag",
        "code_generation": "supports_code",
    }
    col = cap_map.get(task_type)
    if col:
        col_attr = getattr(AIModel, col, None)
        if col_attr is not None:
            res = await db.execute(
                select(AIModel).where(
                    col_attr == True,  # noqa: E712
                    AIModel.state.in_(['active', 'available']),  # noqa: E712
                ).limit(1)
            )
            model = res.scalar_one_or_none()
            if model:
                prov_res = await db.execute(select(AIProvider).where(AIProvider.id == model.provider_id))
                prov = prov_res.scalar_one_or_none()
                if prov:
                    return {
                        "providerId": prov.provider_id,
                        "modelId": model.model_id,
                        "source": "capability_fallback",
                    }
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  HEALTH RECORDS
# ═══════════════════════════════════════════════════════════════════════════════

async def add_health_record(
    db: AsyncSession,
    provider_id: str,
    model_id: Optional[str] = None,
    latency_ms: Optional[float] = None,
    success: bool = True,
    tokens_used: int = 0,
    error_message: str = "",
) -> HealthRecord:
    """Record a health check result."""
    record = HealthRecord(
        provider_id=provider_id,
        model_id=model_id,
        latency_ms=latency_ms,
        success=success,
        tokens_used=tokens_used,
        error_message=error_message,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_health_history(
    db: AsyncSession,
    provider_id: Optional[str] = None,
    limit: int = 50,
) -> List[HealthRecord]:
    """Get recent health check records."""
    q = select(HealthRecord).order_by(HealthRecord.checked_at.desc())
    if provider_id:
        q = q.where(HealthRecord.provider_id == provider_id)
    q = q.limit(limit)
    res = await db.execute(q)
    return list(res.scalars().all())


async def get_health_summary(db: AsyncSession) -> dict:
    """Get a summary of latest health status per provider."""
    providers = await get_all_providers(db)
    summary = {}
    for prov in providers:
        records = await get_health_history(db, prov.provider_id, limit=5)
        latest = records[0] if records else None
        summary[prov.provider_id] = {
            "status": prov.status,
            "isConnected": prov.is_connected,
            "lastChecked": latest.checked_at.isoformat() if latest and latest.checked_at else None,
            "lastLatencyMs": latest.latency_ms if latest else None,
            "lastSuccess": latest.success if latest else None,
            "recentChecks": len(records),
        }
    return summary


# Alias for backward compatibility
record_health_check = add_health_record


# ═══════════════════════════════════════════════════════════════════════════════
#  SYNC LOG
# ═══════════════════════════════════════════════════════════════════════════════

async def add_sync_log(
    db: AsyncSession,
    provider_id: str,
    sync_type: str = "fetch",
    models_retrieved: int = 0,
    models_added: int = 0,
    models_removed: int = 0,
    models_updated: int = 0,
    models_unchanged: int = 0,
    status: str = "success",
    error_message: str = "",
) -> SyncLog:
    """Record a model synchronization event."""
    log = SyncLog(
        provider_id=provider_id,
        sync_type=sync_type,
        models_retrieved=models_retrieved,
        models_added=models_added,
        models_removed=models_removed,
        models_updated=models_updated,
        models_unchanged=models_unchanged,
        status=status,
        error_message=error_message,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_sync_history(
    db: AsyncSession,
    provider_id: Optional[str] = None,
    limit: int = 50,
) -> List[SyncLog]:
    """Get recent synchronization history."""
    q = select(SyncLog).order_by(SyncLog.synced_at.desc())
    if provider_id:
        q = q.where(SyncLog.provider_id == provider_id)
    q = q.limit(limit)
    res = await db.execute(q)
    return list(res.scalars().all())


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════════

async def add_audit_entry(
    db: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[dict] = None,
    user_id: str = "",
    user_name: str = "",
) -> AuditLog:
    """Record an auditable action."""
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details_json=json.dumps(details or {}, default=str),
        user_id=user_id,
        user_name=user_name,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def get_audit_log(
    db: AsyncSession,
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
) -> List[AuditLog]:
    """Get audit log entries."""
    q = select(AuditLog).order_by(AuditLog.created_at.desc())
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if action:
        q = q.where(AuditLog.action == action)
    q = q.limit(limit)
    res = await db.execute(q)
    return list(res.scalars().all())


# ═══════════════════════════════════════════════════════════════════════════════
#  REFERENCE DATA
# ═══════════════════════════════════════════════════════════════════════════════

VALID_CAPABILITIES = [
    "chat", "vision", "tools", "code", "reasoning",
    "embedding", "rag", "classification", "summary",
    "extraction", "audio", "comparison",
]

VALID_ROLES = [
    "super_admin", "admin", "manager", "engineer",
    "power_user", "general_user", "guest",
]

ZETDC_DEPARTMENTS = [
    "ict", "generation", "transmission", "distribution",
    "projects", "operations", "finance", "human_resources",
    "procurement", "customer_services",
]

MODEL_STATES = [
    "active", "inactive", "installed", "downloading",
    "error", "maintenance", "retired", "available",
]

HEALTH_STATUSES = ["healthy", "degraded", "unhealthy", "unknown"]
