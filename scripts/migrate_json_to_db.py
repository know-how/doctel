#!/usr/bin/env python3
"""
migrate_json_to_db.py -- DocTel JSON -> MySQL Migration Script

Reads all local JSON configuration files and imports their data into
the MySQL-backed configuration database using the existing config_service
async CRUD functions.

Source files:
  - localai/data/model_management.json   PRIMARY provider/model/task config
  - app/data/providers.json              SECONDARY OpenCode provider config
  - localai/data/model_audit.json        Audit log entries
  - localai/data/model_health.json       Health check history (currently empty)
  - app/config.yaml                      System config key/values (migrated as SystemConfig)

Usage:
  python scripts/migrate_json_to_db.py [--dry-run] [--db-url mysql+aiomysql://...]

If --db-url is omitted, the script reads DOCINTEL_DATABASE_URL env var or
constructs the URL from DOCINTEL_MYSQL_* env vars (same logic as app.config).
"""

import argparse
import asyncio
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add project root to sys.path so we can import app modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


# ──────────────────────────────────────────────────────────────────────
#  DDL for config tables (CREATE IF NOT EXISTS to be idempotent)
# ──────────────────────────────────────────────────────────────────────

DDL_STATEMENTS = [
    # 1. system_config — key/value store
    """CREATE TABLE IF NOT EXISTS system_config (
        `key` VARCHAR(255) NOT NULL PRIMARY KEY,
        value_json TEXT NOT NULL DEFAULT 'null',
        description VARCHAR(512) DEFAULT '',
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # 2. ai_providers — provider registrations
    """CREATE TABLE IF NOT EXISTS ai_providers (
        id INT AUTO_INCREMENT PRIMARY KEY,
        provider_id VARCHAR(128) NOT NULL,
        name VARCHAR(255) NOT NULL,
        vendor VARCHAR(128) DEFAULT '',
        base_url VARCHAR(512) DEFAULT '',
        api_key_value VARCHAR(1024) DEFAULT '',
        status VARCHAR(50) DEFAULT 'disconnected',
        is_connected TINYINT(1) DEFAULT 0,
        last_tested_at DATETIME NULL,
        description TEXT DEFAULT NULL,
        icon VARCHAR(64) DEFAULT 'generic',
        sort_order INT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_provider_id (provider_id),
        INDEX idx_provider_id (provider_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # 3. ai_models — model catalogue per provider
    """CREATE TABLE IF NOT EXISTS ai_models (
        id INT AUTO_INCREMENT PRIMARY KEY,
        provider_id INT NOT NULL,
        model_id VARCHAR(255) NOT NULL,
        display_name VARCHAR(255) NOT NULL,
        context_window INT DEFAULT 4096,
        supports_chat TINYINT(1) DEFAULT 1,
        supports_vision TINYINT(1) DEFAULT 0,
        supports_tools TINYINT(1) DEFAULT 0,
        supports_code TINYINT(1) DEFAULT 0,
        supports_embedding TINYINT(1) DEFAULT 0,
        supports_reasoning TINYINT(1) DEFAULT 0,
        supports_rag TINYINT(1) DEFAULT 0,
        supports_classification TINYINT(1) DEFAULT 0,
        supports_summary TINYINT(1) DEFAULT 0,
        supports_extraction TINYINT(1) DEFAULT 0,
        supports_audio TINYINT(1) DEFAULT 0,
        supports_comparison TINYINT(1) DEFAULT 0,
        enabled TINYINT(1) DEFAULT 1,
        visible_to_users TINYINT(1) DEFAULT 1,
        state VARCHAR(50) DEFAULT 'available',
        is_default TINYINT(1) DEFAULT 0,
        pricing_tier VARCHAR(64) DEFAULT 'free',
        license VARCHAR(128) DEFAULT 'Proprietary',
        allowed_roles TEXT DEFAULT '[]',
        department_restrictions TEXT DEFAULT '[]',
        for_tasks TEXT DEFAULT '[]',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (provider_id) REFERENCES ai_providers(id) ON DELETE CASCADE,
        UNIQUE KEY uq_provider_model (provider_id, model_id),
        INDEX idx_provider_id (provider_id),
        INDEX idx_model_id (model_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # 4. task_mappings -- task type -> model assignments
    """CREATE TABLE IF NOT EXISTS task_mappings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        task_type VARCHAR(64) NOT NULL,
        provider_id_ref VARCHAR(128) NOT NULL,
        model_id VARCHAR(255) NOT NULL,
        is_active TINYINT(1) DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_task_type (task_type),
        INDEX idx_task_type (task_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # 5. health_records — health ping history
    """CREATE TABLE IF NOT EXISTS health_records (
        id INT AUTO_INCREMENT PRIMARY KEY,
        provider_id VARCHAR(128) NOT NULL,
        model_id VARCHAR(255) NULL,
        latency_ms FLOAT NULL,
        success TINYINT(1) DEFAULT 1,
        tokens_used INT DEFAULT 0,
        error_message TEXT DEFAULT '',
        checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_health_provider (provider_id),
        INDEX idx_health_provider_model (provider_id, model_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # 6. audit_logs — governance audit trail
    """CREATE TABLE IF NOT EXISTS audit_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        action VARCHAR(255) NOT NULL,
        entity_type VARCHAR(128) NOT NULL,
        entity_id VARCHAR(255) NULL,
        details_json TEXT DEFAULT NULL,
        user_id VARCHAR(128) DEFAULT '',
        user_name VARCHAR(255) DEFAULT '',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_audit_entity (entity_type, entity_id),
        INDEX idx_audit_action (action),
        INDEX idx_audit_created (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]


# ──────────────────────────────────────────────────────────────────────
#  Paths to source files
# ──────────────────────────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "localai" / "data"
APP_DATA_DIR = PROJECT_ROOT / "app" / "data"
CONFIG_YAML = PROJECT_ROOT / "app" / "config.yaml"

PATHS = {
    "model_management": DATA_DIR / "model_management.json",
    "providers": APP_DATA_DIR / "providers.json",
    "model_audit": DATA_DIR / "model_audit.json",
    "model_health": DATA_DIR / "model_health.json",
}


# ──────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> Any:
    """Load and return JSON content."""
    if not path.exists():
        print(f"  [WARN] File not found: {path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [WARN] Error reading {path}: {e}")
        return None


def _build_db_url(args_db_url: Optional[str]) -> str:
    """Construct the database URL from args, env var, or defaults."""
    if args_db_url:
        return args_db_url
    env_url = os.getenv("DOCINTEL_DATABASE_URL", "")
    if env_url:
        return env_url
    user = os.getenv("DOCINTEL_MYSQL_USER", "root")
    pwd = os.getenv("DOCINTEL_MYSQL_PASSWORD", "")
    host = os.getenv("DOCINTEL_MYSQL_HOST", "127.0.0.1")
    port = os.getenv("DOCINTEL_MYSQL_PORT", "3306")
    db = os.getenv("DOCINTEL_MYSQL_DATABASE", "doctel")
    return f"mysql+aiomysql://{user}:{pwd}@{host}:{port}/{db}"


def _capabilities_from_model(mm: dict) -> dict[str, bool]:
    """Build capabilities dict from model_management.json model entry."""
    return {
        "chat": mm.get("supportsChat", True),
        "vision": mm.get("supportsVision", False),
        "tools": mm.get("supportsTools", False),
        "code": mm.get("supportsCode", False),
        "embedding": mm.get("supportsEmbedding", False),
        "reasoning": mm.get("supportsReasoning", False),
        "rag": mm.get("supportsRag", False),
        "classification": mm.get("supportsClassification", False),
        "summary": mm.get("supportsSummary", False),
        "extraction": mm.get("supportsExtraction", False),
        "audio": mm.get("supportsAudio", False),
        "comparison": mm.get("supportsComparison", False),
    }


def _capabilities_from_providers_json(pm: dict) -> dict[str, bool]:
    """Build capabilities dict from providers.json model entry."""
    return {
        "chat": True,
        "vision": pm.get("vision", False),
        "tools": pm.get("toolCalling", False),
        "code": True,
        "embedding": False,
        "reasoning": True,
        "rag": True,
        "classification": True,
        "summary": True,
        "extraction": True,
        "audio": False,
        "comparison": False,
    }


# ──────────────────────────────────────────────────────────────────────
#  Migration logic
# ──────────────────────────────────────────────────────────────────────

class Migration:
    """Encapsulates the migration, tracking counters per table."""

    def __init__(self, db_url: str, dry_run: bool = False):
        self.db_url = db_url
        self.dry_run = dry_run
        self.engine = create_async_engine(db_url, echo=False, pool_size=5, max_overflow=2)
        self.Session = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.counts: dict[str, int] = {
            "system_config": 0,
            "providers": 0,
            "models": 0,
            "task_mappings": 0,
            "audit_entries": 0,
            "health_records": 0,
            "skipped_providers": 0,
            "skipped_models": 0,
            "skipped_task_mappings": 0,
        }

    async def close(self):
        await self.engine.dispose()

    # ── helpers ──────────────────────────────────────────────────────

    async def _provider_exists(self, db: AsyncSession, provider_id: str) -> bool:
        """Check if a provider (by business key) already exists."""
        res = await db.execute(
            sa_text("SELECT 1 FROM ai_providers WHERE provider_id = :pid").bindparams(pid=provider_id)
        )
        return res.first() is not None

    async def _provider_pk(self, db: AsyncSession, provider_id: str) -> Optional[int]:
        """Get the integer PK of a provider by its business key."""
        res = await db.execute(
            sa_text("SELECT id FROM ai_providers WHERE provider_id = :pid").bindparams(pid=provider_id)
        )
        row = res.first()
        return row[0] if row else None

    async def _model_exists_by_pk(self, db: AsyncSession, provider_pk: int, model_id: str) -> bool:
        """Check if a model already exists for a given provider PK."""
        res = await db.execute(
            sa_text(
                "SELECT 1 FROM ai_models WHERE provider_id = :ppk AND model_id = :mid"
            ).bindparams(ppk=provider_pk, mid=model_id)
        )
        return res.first() is not None

    async def _task_mapping_exists(self, db: AsyncSession, task_type: str) -> bool:
        """Check if a task mapping already exists."""
        res = await db.execute(
            sa_text("SELECT 1 FROM task_mappings WHERE task_type = :tt").bindparams(tt=task_type)
        )
        return res.first() is not None

    # ── SystemConfig from config.yaml ────────────────────────────────

    async def _migrate_system_config(self, db: AsyncSession):
        """Migrate key settings from config.yaml into system_config table."""
        if not CONFIG_YAML.exists():
            print("  [INFO] config.yaml not found, skipping SystemConfig migration.")
            return

        import yaml
        with open(CONFIG_YAML, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        if not isinstance(cfg, dict):
            return

        # Flatten top-level keys + nested sections as JSON blobs
        inserts = 0
        for key, value in cfg.items():
            if isinstance(value, dict):
                # Store nested sections as JSON under their section key
                # e.g. "security", "rbac", "performance_targets", "ui"
                section_val = json.dumps(value, default=str)
                res = await db.execute(
                    sa_text("SELECT 1 FROM system_config WHERE `key` = :k").bindparams(k=key)
                )
                if res.first() is None:
                    desc = f"Migrated from config.yaml section '{key}'"
                    await db.execute(
                        sa_text(
                            "INSERT INTO system_config (`key`, value_json, description) "
                            "VALUES (:k, :v, :d)"
                        ).bindparams(k=key, v=section_val, d=desc)
                    )
                    inserts += 1
            elif isinstance(value, list):
                section_val = json.dumps(value, default=str)
                res = await db.execute(
                    sa_text("SELECT 1 FROM system_config WHERE `key` = :k").bindparams(k=key)
                )
                if res.first() is None:
                    desc = f"Migrated from config.yaml key '{key}'"
                    await db.execute(
                        sa_text(
                            "INSERT INTO system_config (`key`, value_json, description) "
                            "VALUES (:k, :v, :d)"
                        ).bindparams(k=key, v=section_val, d=desc)
                    )
                    inserts += 1
            else:
                # Scalar values
                val_json = json.dumps(value)
                res = await db.execute(
                    sa_text("SELECT 1 FROM system_config WHERE `key` = :k").bindparams(k=key)
                )
                if res.first() is None:
                    desc = f"Migrated from config.yaml key '{key}'"
                    await db.execute(
                        sa_text(
                            "INSERT INTO system_config (`key`, value_json, description) "
                            "VALUES (:k, :v, :d)"
                        ).bindparams(k=key, v=val_json, d=desc)
                    )
                    inserts += 1

        self.counts["system_config"] += inserts
        print(f"  [OK] SystemConfig: {inserts} keys inserted")

    # ── Providers & Models from model_management.json ────────────────

    async def _migrate_model_management(self, db: AsyncSession):
        """Migrate providers and models from model_management.json (PRIMARY source)."""
        data = _load_json(PATHS["model_management"])
        if data is None:
            return

        providers = data.get("providers", [])
        print(f"  [INFO] Found {len(providers)} providers in model_management.json")

        for prov in providers:
            pid = prov.get("id", "").strip()
            if not pid:
                continue

            exists = await self._provider_exists(db, pid)
            if exists:
                self.counts["skipped_providers"] += 1
                # Still migrate models even if provider already exists
                provider_pk = await self._provider_pk(db, pid)
            else:
                provider_pk = await self._insert_provider(prov, db)
                if provider_pk:
                    self.counts["providers"] += 1
                else:
                    continue

            # Migrate models for this provider
            models = prov.get("models", [])
            for m in models:
                mid = m.get("id", "").strip()
                if not mid:
                    continue

                model_exists = await self._model_exists_by_pk(db, provider_pk, mid)
                if model_exists:
                    self.counts["skipped_models"] += 1
                    continue

                await self._insert_model(pid, m, db)
                self.counts["models"] += 1

        # Migrate task mappings
        tm = data.get("taskMapping", {})
        print(f"  [INFO] Found {len(tm)} task mappings in model_management.json")
        for task_type, mapping in tm.items():
            if await self._task_mapping_exists(db, task_type):
                self.counts["skipped_task_mappings"] += 1
                continue
            prov_id = mapping.get("providerId", "")
            model_id = mapping.get("modelId", "")
            if prov_id and model_id:
                # Use raw SQL insert for simplicity
                await db.execute(
                    sa_text(
                        "INSERT INTO task_mappings (task_type, provider_id_ref, model_id, is_active) "
                        "VALUES (:tt, :pid, :mid, 1)"
                    ).bindparams(tt=task_type, pid=prov_id, mid=model_id)
                )
                self.counts["task_mappings"] += 1

    async def _insert_provider(self, prov: dict, db: AsyncSession) -> Optional[int]:
        """Insert a single provider. Returns the new PK or None."""
        pid = prov["id"]
        status = prov.get("status", "disconnected")
        is_connected = status == "connected"

        try:
            await db.execute(
                sa_text(
                    """INSERT INTO ai_providers
                       (provider_id, name, vendor, base_url, api_key_value, status,
                        is_connected, description, icon, sort_order)
                       VALUES (:pid, :nm, :vd, :url, :akv, :st, :conn, :desc, :ico, :ord)"""
                ).bindparams(
                    pid=pid,
                    nm=prov.get("name", pid),
                    vd=prov.get("vendor", ""),
                    url=prov.get("base_url", ""),
                    akv=prov.get("api_key_value", ""),
                    st=status,
                    conn=is_connected,
                    desc=prov.get("description", ""),
                    ico=prov.get("icon", "generic"),
                    ord=prov.get("order", 0),
                )
            )
            # Fetch the PK
            return await self._provider_pk(db, pid)
        except Exception as e:
            print(f"  [WARN] Failed to insert provider '{pid}': {e}")
            return None

    async def _insert_model(self, provider_id_str: str, m: dict, db: AsyncSession):
        """Insert a single model using raw SQL."""
        caps = _capabilities_from_model(m)
        allowed_roles = json.dumps(m.get("allowedRoles", []))
        dept_restrictions = json.dumps(m.get("departmentRestrictions", []))
        for_tasks = json.dumps(m.get("forTasks", []))

        await db.execute(
            sa_text(
                """INSERT INTO ai_models
                   (provider_id, model_id, display_name, context_window,
                    supports_chat, supports_vision, supports_tools, supports_code,
                    supports_embedding, supports_reasoning, supports_rag,
                    supports_classification, supports_summary, supports_extraction,
                    supports_audio, supports_comparison,
                    enabled, visible_to_users, state, is_default,
                    pricing_tier, `license`, allowed_roles, department_restrictions, for_tasks)
                   VALUES (
                     (SELECT id FROM ai_providers WHERE provider_id = :ppid),
                     :mid, :nm, :cw,
                     :schat, :svision, :stools, :scode,
                     :semb, :sreason, :srag,
                     :sclass, :ssum, :sextract,
                     :saudio, :scomp,
                     :en, :vis, :st, :isdef,
                     :pt, :lic, :aroles, :drest, :ftasks
                   )"""
            ).bindparams(
                ppid=provider_id_str,
                mid=m["id"],
                nm=m.get("name", m["id"]),
                cw=m.get("contextWindow", 4096),
                schat=caps.get("chat", True),
                svision=caps.get("vision", False),
                stools=caps.get("tools", False),
                scode=caps.get("code", False),
                semb=caps.get("embedding", False),
                sreason=caps.get("reasoning", False),
                srag=caps.get("rag", False),
                sclass=caps.get("classification", False),
                ssum=caps.get("summary", False),
                sextract=caps.get("extraction", False),
                saudio=caps.get("audio", False),
                scomp=caps.get("comparison", False),
                en=m.get("enabled", True),
                vis=m.get("visibleToUsers", True),
                st=m.get("state", "available"),
                isdef=m.get("isDefault", False),
                pt=m.get("pricingTier", "free"),
                lic=m.get("license", "Proprietary"),
                aroles=allowed_roles,
                drest=dept_restrictions,
                ftasks=for_tasks,
            )
        )

    # ── Secondary: providers.json ────────────────────────────────────

    async def _migrate_providers_json(self, db: AsyncSession):
        """Migrate providers from app/data/providers.json (SECONDARY source).

        Only inserts providers that don't already exist. Models from this
        source use a simpler capability profile.
        """
        data = _load_json(PATHS["providers"])
        if data is None:
            return

        if not isinstance(data, list):
            print(f"  [WARN] providers.json is not a list (got {type(data).__name__})")
            return

        print(f"  [INFO] Found {len(data)} providers in providers.json")

        for prov in data:
            pid_raw = prov.get("name", "").strip()
            if not pid_raw:
                continue
            # Normalise to a short business key
            pid = pid_raw.lower().replace(" ", "-").replace("_", "-")

            exists = await self._provider_exists(db, pid)
            if exists:
                self.counts["skipped_providers"] += 1
                provider_pk = await self._provider_pk(db, pid)
            else:
                api_key_value = prov.get("apiKey", "")

                try:
                    await db.execute(
                        sa_text(
                            """INSERT INTO ai_providers
                               (provider_id, name, vendor, base_url, api_key_value, status, is_connected)
                               VALUES (:pid, :nm, :vd, :url, :akv, 'disconnected', 0)"""
                        ).bindparams(
                            pid=pid,
                            nm=prov.get("name", pid),
                            vd=prov.get("vendor", ""),
                            url="",
                            akv=api_key_value,
                        )
                    )
                    provider_pk = await self._provider_pk(db, pid)
                    self.counts["providers"] += 1
                except Exception as e:
                    print(f"  [WARN] Failed to insert provider '{pid}': {e}")
                    continue

            if not provider_pk:
                continue

            # Migrate models
            models = prov.get("models", [])
            for m in models:
                mid = m.get("id", "").strip()
                if not mid:
                    continue

                model_exists = await self._model_exists_by_pk(db, provider_pk, mid)
                if model_exists:
                    self.counts["skipped_models"] += 1
                    continue

                caps = _capabilities_from_providers_json(m)
                max_in = m.get("maxInputTokens", 4096)
                max_out = m.get("maxOutputTokens", 1024)
                context = max(max_in, max_out)

                await db.execute(
                    sa_text(
                        """INSERT INTO ai_models
                           (provider_id, model_id, display_name, context_window,
                            supports_chat, supports_vision, supports_tools, supports_code,
                            supports_embedding, supports_reasoning, supports_rag,
                            supports_classification, supports_summary, supports_extraction,
                            supports_audio, supports_comparison,
                            enabled, visible_to_users, state, is_default,
                            pricing_tier, `license`, allowed_roles, department_restrictions, for_tasks)
                           VALUES (
                             :ppk, :mid, :nm, :cw,
                             :schat, :svision, :stools, :scode,
                             :semb, :sreason, :srag,
                             :sclass, :ssum, :sextract,
                             :saudio, :scomp,
                             1, 1, 'available', 0,
                             'free', 'Proprietary', '[]', '[]', '[]'
                           )"""
                    ).bindparams(
                        ppk=provider_pk,
                        mid=mid,
                        nm=m.get("name", mid),
                        cw=context,
                        schat=caps.get("chat", True),
                        svision=caps.get("vision", False),
                        stools=caps.get("tools", False),
                        scode=caps.get("code", False),
                        semb=caps.get("embedding", False),
                        sreason=caps.get("reasoning", False),
                        srag=caps.get("rag", False),
                        sclass=caps.get("classification", False),
                        ssum=caps.get("summary", False),
                        sextract=caps.get("extraction", False),
                        saudio=caps.get("audio", False),
                        scomp=caps.get("comparison", False),
                    )
                )
                self.counts["models"] += 1

    # ── Audit log ─────────────────────────────────────────────────────

    async def _migrate_audit_log(self, db: AsyncSession):
        """Migrate entries from model_audit.json."""
        data = _load_json(PATHS["model_audit"])
        if data is None:
            return

        if not isinstance(data, list):
            print(f"  [WARN] model_audit.json is not a list")
            return

        print(f"  [INFO] Found {len(data)} audit entries in model_audit.json")
        inserted = 0
        for entry in data:
            action = entry.get("action", "unknown")
            entity_type = entry.get("entityType", "")
            entity_id = entry.get("entityId")
            details = entry.get("details", {})
            user_id = entry.get("userId", "")
            user_name = entry.get("userName", "")
            ts = entry.get("timestamp")
            details_json = json.dumps(details, default=str)

            await db.execute(
                sa_text(
                    """INSERT INTO audit_logs
                       (action, entity_type, entity_id, details_json, user_id, user_name, created_at)
                       VALUES (:act, :et, :eid, :dj, :uid, :un, :ts)"""
                ).bindparams(
                    act=action,
                    et=entity_type,
                    eid=entity_id,
                    dj=details_json,
                    uid=user_id,
                    un=user_name,
                    ts=ts,
                )
            )
            inserted += 1

        self.counts["audit_entries"] += inserted
        print(f"  [OK] AuditLog: {inserted} entries inserted")

    # ── Health records (currently empty, but handle gracefully) ──────

    async def _migrate_health_records(self, db: AsyncSession):
        """Migrate health check history from model_health.json."""
        data = _load_json(PATHS["model_health"])
        if data is None:
            return

        providers = data.get("providers", {})
        models = data.get("models", {})
        total = len(providers) + len(models)
        if total == 0:
            print("  [INFO] model_health.json is empty - no health records to migrate.")
            return

        print(f"  [INFO] Found {total} health entries in model_health.json")
        inserted = 0

        # providers keyed by provider_id → {success, latencyMs, errorMessage, ...}
        for prov_id, health in providers.items():
            await db.execute(
                sa_text(
                    """INSERT INTO health_records
                       (provider_id, model_id, latency_ms, success, error_message, checked_at)
                       VALUES (:pid, NULL, :lat, :suc, :err, :ts)"""
                ).bindparams(
                    pid=prov_id,
                    lat=health.get("latencyMs"),
                    suc=health.get("success", True),
                    err=health.get("errorMessage", ""),
                    ts=health.get("timestamp", datetime.utcnow().isoformat()),
                )
            )
            inserted += 1

        for model_key, health in models.items():
            # model_key may be "provider_id:model_id" or just "model_id"
            parts = model_key.split(":", 1)
            prov_id = parts[0]
            model_id = parts[1] if len(parts) > 1 else None
            await db.execute(
                sa_text(
                    """INSERT INTO health_records
                       (provider_id, model_id, latency_ms, success, error_message, checked_at)
                       VALUES (:pid, :mid, :lat, :suc, :err, :ts)"""
                ).bindparams(
                    pid=prov_id,
                    mid=model_id,
                    lat=health.get("latencyMs"),
                    suc=health.get("success", True),
                    err=health.get("errorMessage", ""),
                    ts=health.get("timestamp", datetime.utcnow().isoformat()),
                )
            )
            inserted += 1

        self.counts["health_records"] += inserted
        print(f"  [OK] HealthRecords: {inserted} records inserted")

    # ── Main entry point ─────────────────────────────────────────────

    async def run(self):
        print(f"\n{'='*60}")
        print(f"  DocTel JSON -> MySQL Migration")
        print(f"  DB URL: {self.db_url.replace(':', '***', 1)}")
        print(f"  Dry run: {self.dry_run}")
        print(f"{'='*60}\n")

        # Create tables if they don't exist (idempotent)
        print("  Creating tables if not present...")
        async with self.engine.begin() as conn:
            for ddl in DDL_STATEMENTS:
                await conn.execute(sa_text(ddl))
        print("  [OK] Tables ready.\n")

        async with self.Session() as db:
            async with db.begin():
                try:
                    await self._migrate_system_config(db)
                    await self._migrate_model_management(db)
                    await self._migrate_providers_json(db)
                    await self._migrate_audit_log(db)
                    await self._migrate_health_records(db)
                except Exception:
                    traceback.print_exc()
                    print("\n[ERROR] Migration failed - rolling back.")
                    raise

        print(f"\n{'='*60}")
        print(f"  MIGRATION SUMMARY")
        print(f"{'='*60}")
        print(f"  SystemConfig keys inserted:    {self.counts['system_config']}")
        print(f"  Providers inserted:            {self.counts['providers']}")
        print(f"  Models inserted:               {self.counts['models']}")
        print(f"  Task mappings inserted:        {self.counts['task_mappings']}")
        print(f"  Audit entries inserted:        {self.counts['audit_entries']}")
        print(f"  Health records inserted:       {self.counts['health_records']}")
        print(f"  ─────────────────────────────────────────")
        print(f"  Providers skipped (exists):    {self.counts['skipped_providers']}")
        print(f"  Models skipped (exists):       {self.counts['skipped_models']}")
        print(f"  Task mappings skipped (exists): {self.counts['skipped_task_mappings']}")
        print(f"{'='*60}\n")

        if self.dry_run:
            print("  [WARN] DRY RUN - no changes were committed.\n")


# ──────────────────────────────────────────────────────────────────────
#  CLI entry point
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="DocTel JSON -> MySQL configuration migration"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Roll back all changes (useful for validation)",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="Full database URL (e.g. mysql+aiomysql://user:pass@host:3306/doctel)",
    )
    args = parser.parse_args()

    db_url = _build_db_url(args.db_url)

    migration = Migration(db_url, dry_run=args.dry_run)
    try:
        asyncio.run(migration.run())
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        asyncio.run(migration.close())


if __name__ == "__main__":
    main()
