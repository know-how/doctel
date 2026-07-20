"""
config_models.py — DocTel Unified Configuration Database Models

Replaces the three-way config split (config.yaml, model_management.json, .env)
with a single PostgreSQL-backed configuration store.

Tables:
  - SystemConfig        Flat key/value config (replaces config.yaml + .env keys)
  - AIProvider          AI provider registrations
  - AIModel             Model catalogue per provider
  - TaskMapping         Task-type → model assignments
  - HealthRecord        Health ping history per provider/model
  - SyncLog             Model synchronization history
  - AuditLog            Governance audit trail
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime,
    ForeignKey, JSON, UniqueConstraint, Index, UUID,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


# ─────────────────────────────────────────────────────────────────────────────
# SystemConfig — Unified key/value configuration
# ─────────────────────────────────────────────────────────────────────────────

class SystemConfig(Base):
    """Unified key/value configuration store.
    
    Replaces config.yaml sections, .env variables, and system settings.
    Keys are namespaced (e.g. 'app.offline_only', 'api.gemini_key').
    """
    __tablename__ = "system_config"

    key = Column(String(255), primary_key=True)
    value_json = Column(Text, nullable=False, default="null")
    description = Column(String(512), default="")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def get_value(self):
        """Deserialize the stored JSON value."""
        try:
            return json.loads(self.value_json) if self.value_json else None
        except (json.JSONDecodeError, TypeError):
            return self.value_json

    @classmethod
    def set_value(cls, key: str, value, description: str = "") -> "SystemConfig":
        """Create a config entry with a JSON-serialized value."""
        return cls(
            key=key,
            value_json=json.dumps(value, default=str),
            description=description,
        )

    def to_dict(self):
        return {
            "key": self.key,
            "value": self.get_value(),
            "description": self.description,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# AIProvider — Provider registrations
# ─────────────────────────────────────────────────────────────────────────────

class AIProvider(Base):
    """Registered AI provider (e.g. Ollama, OpenCode Zen, Google Gemini)."""
    __tablename__ = "ai_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    vendor = Column(String(128), default="")
    base_url = Column(String(512), default="")
    api_key_value = Column(String(1024), default="")    # stored key (encrypted at rest in future)
    status = Column(String(50), default="disconnected")  # connected | disconnected | error
    visible_to_users = Column(Boolean, default=True, nullable=False)
    is_connected = Column(Boolean, default=False)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, default="")
    icon = Column(String(64), default="generic")
    sort_order = Column(Integer, default=0)
    
    # Provider Type & Endpoints (for flexible provider architecture)
    provider_type = Column(String(64), default="openai")  # openai | anthropic | custom
    models_endpoint = Column(String(512), default="")  # /models endpoint
    chat_endpoint = Column(String(512), default="")    # /chat/completions endpoint
    messages_endpoint = Column(String(512), default="")  # /messages endpoint (Anthropic-style)
    embeddings_endpoint = Column(String(512), default="")  # /embeddings endpoint
    health_endpoint = Column(String(512), default="")  # Health check endpoint
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    models = relationship("AIModel", back_populates="provider", cascade="all, delete-orphan",
                          lazy="selectin")

    def to_dict(self, include_models: bool = True, include_key: bool = False) -> dict:
        d = {
            "id": self.provider_id,
            "name": self.name,
            "vendor": self.vendor,
            "base_url": self.base_url,
            "status": self.status,
            "visibleToUsers": self.visible_to_users,
            "isConnected": self.is_connected,
            "lastTestedAt": self.last_tested_at.isoformat() if self.last_tested_at else None,
            "description": self.description,
            "icon": self.icon,
            "order": self.sort_order,
            "providerType": self.provider_type,
            "modelsEndpoint": self.models_endpoint,
            "chatEndpoint": self.chat_endpoint,
            "messagesEndpoint": self.messages_endpoint,
            "embeddingsEndpoint": self.embeddings_endpoint,
            "healthEndpoint": self.health_endpoint,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_key:
            d["api_key_value"] = self.api_key_value
        if include_models and self.models:
            d["models"] = [m.to_dict() for m in self.models]
        else:
            d["models"] = []
        return d


# ─────────────────────────────────────────────────────────────────────────────
# AIModel — Model catalogue entries
# ─────────────────────────────────────────────────────────────────────────────

class AIModel(Base):
    """A single model within an AI provider's catalogue."""
    __tablename__ = "ai_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(Integer, ForeignKey("ai_providers.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    model_id = Column(String(255), nullable=False)         # e.g. "deepseek-v4-flash-free"
    display_name = Column(String(255), nullable=False)      # e.g. "DeepSeek V4 Flash (Free)"
    context_window = Column(Integer, default=4096)

    # Capability flags
    supports_chat = Column(Boolean, default=True)
    supports_vision = Column(Boolean, default=False)
    supports_tools = Column(Boolean, default=False)
    supports_code = Column(Boolean, default=False)
    supports_embedding = Column(Boolean, default=False)
    supports_reasoning = Column(Boolean, default=False)
    supports_rag = Column(Boolean, default=False)
    supports_classification = Column(Boolean, default=False)
    supports_summary = Column(Boolean, default=False)
    supports_extraction = Column(Boolean, default=False)
    supports_audio = Column(Boolean, default=False)
    supports_comparison = Column(Boolean, default=False)
    supports_image_generation = Column(Boolean, default=False)

    # Activation & state
    state = Column(String(50), default="available")  # available | installed | active | retired | ...
    visible_to_users = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False)

    # Endpoint routing (for flexible provider architecture)
    endpoint_type = Column(String(32), default="chat")  # chat | messages | custom

    # Metadata
    pricing_tier = Column(String(64), default="free")
    license = Column(String(128), default="Proprietary")
    allowed_roles = Column(Text, default="[]")       # JSON array of role strings
    department_restrictions = Column(Text, default="[]")  # JSON array of department strings
    for_tasks = Column(Text, default="[]")           # JSON array of task types this model excels at

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    provider = relationship("AIProvider", back_populates="models")

    __table_args__ = (
        UniqueConstraint("provider_id", "model_id", name="uq_provider_model"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.model_id,
            "name": self.display_name,
            "contextWindow": self.context_window,
            "supportsChat": self.supports_chat,
            "supportsVision": self.supports_vision,
            "supportsTools": self.supports_tools,
            "supportsCode": self.supports_code,
            "supportsEmbedding": self.supports_embedding,
            "supportsReasoning": self.supports_reasoning,
            "supportsRag": self.supports_rag,
            "supportsClassification": self.supports_classification,
            "supportsSummary": self.supports_summary,
            "supportsExtraction": self.supports_extraction,
            "supportsAudio": self.supports_audio,
            "supportsComparison": self.supports_comparison,
            "supportsImageGeneration": self.supports_image_generation,
            "state": self.state,
            "visibleToUsers": self.visible_to_users,
            "isDefault": self.is_default,
            "endpointType": self.endpoint_type,
            "pricingTier": self.pricing_tier,
            "license": self.license,
            "allowedRoles": json.loads(self.allowed_roles) if self.allowed_roles else [],
            "departmentRestrictions": json.loads(self.department_restrictions) if self.department_restrictions else [],
            "forTasks": json.loads(self.for_tasks) if self.for_tasks else [],
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# TaskMapping — Task type → model assignments
# ─────────────────────────────────────────────────────────────────────────────

class TaskMapping(Base):
    """Maps a task type (chat, summary, vision, etc.) to a specific provider+model."""
    __tablename__ = "task_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(64), unique=True, nullable=False, index=True)
    provider_id_ref = Column(String(128), nullable=False)   # provider.provider_id
    model_id = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "taskType": self.task_type,
            "providerId": self.provider_id_ref,
            "modelId": self.model_id,
            "isActive": self.is_active,
        }


# ─────────────────────────────────────────────────────────────────────────────
# HealthRecord — Health ping history
# ─────────────────────────────────────────────────────────────────────────────

class HealthRecord(Base):
    """Records a single health check ping for a provider/model.

    The database table was created by the M10 migration with:
      provider_id_ref VARCHAR(128) NOT NULL  (maps to provider.provider_id)
      status VARCHAR(50) DEFAULT 'unknown'

    The ORM model also includes the original ORM-native columns
    (provider_id, success, tokens_used) that were created by
    Base.metadata.create_all() on the old MySQL schema.
    Both sets coexist until a cleanup migration is written.
    """
    __tablename__ = "health_records"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ── M10 migration columns ────────────────────────────────────────────
    provider_id_ref = Column(String(128), nullable=False, index=True)
    status = Column(String(50), default="unknown")

    # ── ORM-native columns (legacy) ──────────────────────────────────────
    provider_id = Column(String(128), nullable=False, index=True)
    model_id = Column(String(255), nullable=True)
    latency_ms = Column(Float, nullable=True)
    success = Column(Boolean, default=True)
    tokens_used = Column(Integer, default=0)
    error_message = Column(Text, default="")
    checked_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_health_provider_model", "provider_id", "model_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "providerId": self.provider_id,
            "modelId": self.model_id,
            "latencyMs": self.latency_ms,
            "success": self.success,
            "tokensUsed": self.tokens_used,
            "errorMessage": self.error_message,
            "checkedAt": self.checked_at.isoformat() if self.checked_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# SyncLog — Model synchronization history
# ─────────────────────────────────────────────────────────────────────────────

class SyncLog(Base):
    """Records model catalog synchronization events.

    The database table was created by the M10 migration with:
      provider_id_ref VARCHAR(128) NOT NULL  (maps to provider.provider_id)
      action VARCHAR(64) DEFAULT ''

    The ORM model also includes the original ORM-native columns
    (provider_id, sync_type, models_retrieved, etc.) that were
    created by Base.metadata.create_all() on the old MySQL schema.
    Both sets coexist until a cleanup migration is written.
    """
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ── M10 migration columns ────────────────────────────────────────────
    provider_id_ref = Column(String(128), nullable=False, index=True)

    # ── ORM-native columns (legacy) ──────────────────────────────────────
    provider_id = Column(String(128), nullable=False, index=True)
    sync_type = Column(String(32), default="fetch")  # fetch | import | manual
    models_retrieved = Column(Integer, default=0)
    models_added = Column(Integer, default=0)
    models_removed = Column(Integer, default=0)
    models_updated = Column(Integer, default=0)
    models_unchanged = Column(Integer, default=0)
    status = Column(String(32), default="success")  # success | failed | partial
    error_message = Column(Text, default="")
    synced_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_sync_provider_time", "provider_id", "synced_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "providerId": self.provider_id,
            "syncType": self.sync_type,
            "modelsRetrieved": self.models_retrieved,
            "modelsAdded": self.models_added,
            "modelsRemoved": self.models_removed,
            "modelsUpdated": self.models_updated,
            "modelsUnchanged": self.models_unchanged,
            "status": self.status,
            "errorMessage": self.error_message,
            "syncedAt": self.synced_at.isoformat() if self.synced_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# AuditLog — Governance audit trail
# ─────────────────────────────────────────────────────────────────────────────

class AuditLog(Base):
    """Immutable audit log for all model management operations."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(64), nullable=False, index=True)   # created | updated | deleted | tested | health_check
    entity_type = Column(String(64), nullable=False)           # provider | model | task_mapping | config
    entity_id = Column(String(255), nullable=True)
    details_json = Column(Text, default="{}")
    user_id = Column(String(128), default="")
    user_name = Column(String(255), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_audit_action", "action"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "action": self.action,
            "entityType": self.entity_type,
            "entityId": self.entity_id,
            "details": json.loads(self.details_json) if self.details_json else {},
            "userId": self.user_id,
            "userName": self.user_name,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# LOOKUP TABLES — Database-driven configuration (replaces hardcoded enums)
# ═══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# Role — User roles lookup table
# ─────────────────────────────────────────────────────────────────────────────

class Role(Base):
    """User roles lookup table (replaces VALID_ROLES hardcoded array).

    NOTE: id uses UUID to match the industrial schema `roles` table.
    """
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    is_system = Column(Boolean, default=False)  # System roles cannot be deleted
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "isSystem": self.is_system,
            "isActive": self.is_active,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Department — Organization departments lookup table
# ─────────────────────────────────────────────────────────────────────────────

class Department(Base):
    """Organization departments lookup table (replaces ZETDC_DEPARTMENTS hardcoded array).

    NOTE: id uses UUID to match the industrial schema `departments` table.
    """
    __tablename__ = "departments"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "isActive": self.is_active,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# TaskType — AI task types lookup table
# ─────────────────────────────────────────────────────────────────────────────

class TaskType(Base):
    """AI task types lookup table (replaces TASK_TYPES hardcoded array)."""
    __tablename__ = "task_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "displayOrder": self.display_order,
            "isActive": self.is_active,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# ModelStatus — Model status lookup table
# ─────────────────────────────────────────────────────────────────────────────

class ModelStatus(Base):
    """Model status lookup table (replaces MODEL_STATES hardcoded array)."""
    __tablename__ = "model_statuses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    is_selectable = Column(Boolean, default=True)  # Can users select models in this status?
    is_visible = Column(Boolean, default=True)     # Is this status visible in dropdowns?
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "isSelectable": self.is_selectable,
            "isVisible": self.is_visible,
            "displayOrder": self.display_order,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT SUGGESTIONS — Dynamic rotating prompt suggestions for New Chat
# ═══════════════════════════════════════════════════════════════════════════════

class PromptSuggestion(Base):
    """Dynamic prompt suggestions for the New Chat page.
    
    Replaces hardcoded prompt buttons with database-driven suggestions
    that can be managed by administrators and rotate dynamically.
    """
    __tablename__ = "prompt_suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)  # Display text (e.g., "Explain ZETDC net metering policy")
    prompt_text = Column(Text, nullable=False)   # Actual prompt sent to model
    category = Column(String(64), default="general")  # policy | safety | reports | languages | general
    enabled = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    icon = Column(String(64), default="💬")  # Emoji or icon identifier
    requires_capability = Column(String(64), nullable=True)  # Optional: vision | audio | video | code
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_prompt_suggestions_category", "category"),
        Index("idx_prompt_suggestions_enabled", "enabled", "display_order"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "prompt_text": self.prompt_text,
            "category": self.category,
            "enabled": self.enabled,
            "display_order": self.display_order,
            "icon": self.icon,
            "requires_capability": self.requires_capability,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
