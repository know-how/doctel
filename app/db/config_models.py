"""
config_models.py — DocTel Unified Configuration Database Models

Replaces the three-way config split (config.yaml, model_management.json, .env)
with a single MySQL-backed configuration store.

Tables:
  - SystemConfig        Flat key/value config (replaces config.yaml + .env keys)
  - AIProvider          AI provider registrations
  - AIModel             Model catalogue per provider
  - TaskMapping         Task-type → model assignments
  - HealthRecord        Health ping history per provider/model
  - AuditLog            Governance audit trail
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime,
    ForeignKey, JSON, UniqueConstraint, Index,
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
    api_key_env = Column(String(128), default="")      # env var name for key
    api_key_value = Column(String(1024), default="")    # stored key (encrypted at rest in future)
    status = Column(String(50), default="disconnected")  # connected | disconnected | error
    is_connected = Column(Boolean, default=False)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, default="")
    icon = Column(String(64), default="generic")
    sort_order = Column(Integer, default=0)
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
            "api_key_env": self.api_key_env,
            "status": self.status,
            "isConnected": self.is_connected,
            "lastTestedAt": self.last_tested_at.isoformat() if self.last_tested_at else None,
            "description": self.description,
            "icon": self.icon,
            "order": self.sort_order,
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

    # Visibility & state
    enabled = Column(Boolean, default=True)
    visible_to_users = Column(Boolean, default=True)
    state = Column(String(50), default="available")  # available | installed | active | retired | ...
    is_default = Column(Boolean, default=False)

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
            "enabled": self.enabled,
            "visibleToUsers": self.visible_to_users,
            "state": self.state,
            "isDefault": self.is_default,
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
    """Records a single health check ping for a provider/model."""
    __tablename__ = "health_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
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
