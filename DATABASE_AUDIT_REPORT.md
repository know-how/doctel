# Database Architecture Audit Report

## Executive Summary

**Date:** 2026-07-08  
**Database:** MySQL via SQLAlchemy  
**Status:** ⚠️ ISSUES FOUND - Migration Required

---

## Current Schema Overview

### Tables Audited

| Table | Purpose | Status |
|-------|---------|--------|
| `ai_providers` | AI Provider registrations | ✅ Good |
| `ai_models` | Model catalogue per provider | ✅ Good |
| `task_mappings` | Task-to-model assignments | ⚠️ Issues Found |
| `health_records` | Health ping history | ⚠️ Issues Found |
| `sync_logs` | Synchronization history | ⚠️ Issues Found |
| `audit_logs` | Governance audit trail | ✅ Good |
| `system_config` | Key/value configuration | ✅ Good |

---

## Detailed Findings

### 1. AIProvider Table ✅ GOOD

```sql
CREATE TABLE ai_providers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    provider_id VARCHAR(128) UNIQUE NOT NULL,  -- Business key
    name VARCHAR(255) NOT NULL,
    vendor VARCHAR(128) DEFAULT '',
    base_url VARCHAR(512) DEFAULT '',
    api_key_value VARCHAR(1024) DEFAULT '',  -- SOLE credential source (replaced api_key_env)
    status VARCHAR(50) DEFAULT 'disconnected',
    is_connected BOOLEAN DEFAULT FALSE,
    description TEXT DEFAULT '',
    icon VARCHAR(64) DEFAULT 'generic',
    sort_order INT DEFAULT 0,
    provider_type VARCHAR(64) DEFAULT 'openai',
    models_endpoint VARCHAR(512) DEFAULT '',
    chat_endpoint VARCHAR(512) DEFAULT '',
    messages_endpoint VARCHAR(512) DEFAULT '',
    embeddings_endpoint VARCHAR(512) DEFAULT '',
    health_endpoint VARCHAR(512) DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_provider_id (provider_id)
);
```

**Assessment:**
- ✅ Primary key exists (id)
- ✅ Unique constraint on provider_id
- ✅ Proper indexing
- ✅ All required fields present

---

### 2. AIModel Table ✅ GOOD

```sql
CREATE TABLE ai_models (
    id INT PRIMARY KEY AUTO_INCREMENT,
    provider_id INT NOT NULL,
    model_id VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    context_window INT DEFAULT 4096,
    supports_chat BOOLEAN DEFAULT TRUE,
    supports_vision BOOLEAN DEFAULT FALSE,
    supports_tools BOOLEAN DEFAULT FALSE,
    supports_code BOOLEAN DEFAULT FALSE,
    supports_embedding BOOLEAN DEFAULT FALSE,
    supports_reasoning BOOLEAN DEFAULT FALSE,
    supports_rag BOOLEAN DEFAULT FALSE,
    supports_classification BOOLEAN DEFAULT FALSE,
    supports_summary BOOLEAN DEFAULT FALSE,
    supports_extraction BOOLEAN DEFAULT FALSE,
    supports_audio BOOLEAN DEFAULT FALSE,
    supports_comparison BOOLEAN DEFAULT FALSE,
    state VARCHAR(50) DEFAULT 'available',
    is_default BOOLEAN DEFAULT FALSE,
    endpoint_type VARCHAR(32) DEFAULT 'chat',
    pricing_tier VARCHAR(64) DEFAULT 'free',
    license VARCHAR(128) DEFAULT 'Proprietary',
    allowed_roles TEXT DEFAULT '[]',
    department_restrictions TEXT DEFAULT '[]',
    for_tasks TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (provider_id) REFERENCES ai_providers(id) ON DELETE CASCADE,
    UNIQUE KEY uq_provider_model (provider_id, model_id),
    INDEX idx_provider_id (provider_id)
);
```

**Assessment:**
- ✅ Primary key exists
- ✅ Foreign key to ai_providers.id with CASCADE
- ✅ Unique constraint on (provider_id, model_id)
- ✅ Proper indexing
- ✅ ORM relationship configured: `provider = relationship("AIProvider", back_populates="models")`

---

### 3. TaskMapping Table ⚠️ CRITICAL ISSUES

**Current Schema:**
```sql
CREATE TABLE task_mappings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    task_type VARCHAR(64) UNIQUE NOT NULL,
    provider_id_ref VARCHAR(128) NOT NULL,  -- ❌ NO FOREIGN KEY!
    model_id VARCHAR(255) NOT NULL,         -- ❌ NO FOREIGN KEY!
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_task_type (task_type)
);
```

**Issues Found:**
1. ❌ **NO FOREIGN KEY to ai_providers** - Uses String `provider_id_ref` instead of Integer FK
2. ❌ **NO FOREIGN KEY to ai_models** - Uses String `model_id` instead of Integer FK
3. ⚠️ **Risk of orphaned records** - No referential integrity
4. ⚠️ **No cascade delete** - Deleting a provider won't clean up task mappings

**Impact:**
- Task mappings can reference non-existent providers/models
- No database-level integrity enforcement
- Requires application-level validation (prone to bugs)

---

### 4. HealthRecord Table ⚠️ ISSUES

**Current Schema:**
```sql
CREATE TABLE health_records (
    id INT PRIMARY KEY AUTO_INCREMENT,
    provider_id VARCHAR(128) NOT NULL,  -- ❌ NO FOREIGN KEY!
    model_id VARCHAR(255) NULL,         -- ❌ NO FOREIGN KEY!
    latency_ms FLOAT NULL,
    success BOOLEAN DEFAULT TRUE,
    tokens_used INT DEFAULT 0,
    error_message TEXT DEFAULT '',
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_health_provider_model (provider_id, model_id)
);
```

**Issues Found:**
1. ❌ **NO FOREIGN KEY to ai_providers**
2. ❌ **NO FOREIGN KEY to ai_models**
3. Uses String columns instead of Integer FKs

**Impact:**
- Historical health data may reference deleted providers/models
- Cannot use JOINs for efficient queries
- Data integrity not enforced at database level

---

### 5. SyncLog Table ⚠️ ISSUES

**Current Schema:**
```sql
CREATE TABLE sync_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    provider_id VARCHAR(128) NOT NULL,  -- ❌ NO FOREIGN KEY!
    sync_type VARCHAR(32) DEFAULT 'fetch',
    models_retrieved INT DEFAULT 0,
    models_added INT DEFAULT 0,
    models_removed INT DEFAULT 0,
    models_updated INT DEFAULT 0,
    models_unchanged INT DEFAULT 0,
    status VARCHAR(32) DEFAULT 'success',
    error_message TEXT DEFAULT '',
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sync_provider_time (provider_id, synced_at)
);
```

**Issues Found:**
1. ❌ **NO FOREIGN KEY to ai_providers**
2. Uses String column instead of Integer FK

---

## Relationship Analysis

### Expected Relationships

```
┌─────────────────┐         ┌─────────────────┐
│   ai_providers  │         │   ai_models     │
│─────────────────│         │─────────────────│
│ id (PK)         │◄────────┤ provider_id(FK) │
│ provider_id     │    1:N  │ model_id        │
│ name            │         │ display_name    │
│ ...             │         │ state           │
└─────────────────┘         └─────────────────┘
         │                           ▲
         │                           │
         │         ┌─────────────────┘
         │         │
         │    ┌────┴────────────────┐
         │    │   task_mappings     │
         │    │─────────────────────│
         └───►│ provider_id (FK)    │  ❌ MISSING!
              │ model_id (FK)       │  ❌ MISSING!
              │ task_type           │
              └─────────────────────┘
```

### Current State

- ✅ **ai_providers ↔ ai_models**: Proper 1:N relationship with FK
- ❌ **ai_providers ↔ task_mappings**: NO relationship (String column only)
- ❌ **ai_models ↔ task_mappings**: NO relationship (String column only)
- ❌ **ai_providers ↔ health_records**: NO relationship
- ❌ **ai_providers ↔ sync_logs**: NO relationship

---

## Query Analysis

### Current Model Loading Query (config_service.py)

```python
async def get_all_providers(db: AsyncSession) -> List[AIProvider]:
    res = await db.execute(
        select(AIProvider).order_by(AIProvider.sort_order, AIProvider.name)
    )
    return list(res.scalars().all())
```

**Assessment:**
- ✅ Uses proper ORM relationship loading
- ✅ `relationship("AIModel", back_populates="provider", lazy="selectin")` loads models efficiently
- ✅ Provider → Models relationship works correctly

### Current Task Mapping Query

```python
async def get_task_mapping(db: AsyncSession) -> Dict[str, Any]:
    res = await db.execute(select(TaskMapping))
    rows = res.scalars().all()
    out = {}
    for r in rows:
        out[r.task_type] = {
            "providerId": r.provider_id_ref,  # String reference
            "modelId": r.model_id,            # String reference
            "isActive": r.is_active,
        }
    return out
```

**Assessment:**
- ❌ Returns String references instead of actual FKs
- ❌ No validation that referenced providers/models exist
- ❌ Requires manual lookup to get provider/model details

---

## Orphaned Record Check

### Query to Find Orphaned Task Mappings

```sql
-- Task mappings referencing non-existent providers
SELECT tm.* 
FROM task_mappings tm
LEFT JOIN ai_providers p ON tm.provider_id_ref = p.provider_id
WHERE p.id IS NULL;

-- Task mappings referencing non-existent models
SELECT tm.* 
FROM task_mappings tm
LEFT JOIN ai_models m ON tm.model_id = m.model_id
LEFT JOIN ai_providers p ON m.provider_id = p.id
WHERE m.id IS NULL;
```

### Query to Find Orphaned Health Records

```sql
-- Health records for non-existent providers
SELECT hr.* 
FROM health_records hr
LEFT JOIN ai_providers p ON hr.provider_id = p.provider_id
WHERE p.id IS NULL;
```

---

## Duplicate Check

### Current Protection

```sql
-- ai_models has:
UNIQUE KEY uq_provider_model (provider_id, model_id)

-- This prevents duplicate model_id within same provider
```

**Assessment:**
- ✅ ai_models has proper unique constraint
- ❌ task_mappings has no duplicate protection for (task_type, provider_id_ref, model_id)

---

## Required Fixes

### Priority 1: Fix TaskMapping Table

**Problem:** No foreign keys, uses String references

**Solution Options:**

#### Option A: Add Foreign Keys (Recommended)

```sql
-- Add proper foreign key columns
ALTER TABLE task_mappings 
ADD COLUMN ai_provider_id INT NULL AFTER id,
ADD COLUMN ai_model_id INT NULL AFTER ai_provider_id;

-- Add foreign key constraints
ALTER TABLE task_mappings
ADD FOREIGN KEY (ai_provider_id) REFERENCES ai_providers(id) ON DELETE CASCADE,
ADD FOREIGN KEY (ai_model_id) REFERENCES ai_models(id) ON DELETE CASCADE;

-- Migrate existing data
UPDATE task_mappings tm
JOIN ai_providers p ON tm.provider_id_ref = p.provider_id
JOIN ai_models m ON tm.model_id = m.model_id AND m.provider_id = p.id
SET tm.ai_provider_id = p.id,
    tm.ai_model_id = m.id;

-- Make new columns NOT NULL after migration
ALTER TABLE task_mappings 
MODIFY ai_provider_id INT NOT NULL,
MODIFY ai_model_id INT NOT NULL;

-- Add unique constraint
ALTER TABLE task_mappings 
ADD UNIQUE KEY uq_task_mapping (ai_provider_id, ai_model_id, task_type);
```

#### Option B: Keep String References, Add Validation

Add database-level CHECK constraints (if using MySQL 8.0.16+) or triggers to validate references.

**Recommendation:** Use Option A for proper relational integrity.

---

### Priority 2: Fix HealthRecord Table

```sql
-- Add foreign key columns
ALTER TABLE health_records 
ADD COLUMN ai_provider_id INT NULL AFTER id,
ADD COLUMN ai_model_id INT NULL AFTER ai_provider_id;

-- Add foreign keys (ON DELETE SET NULL to preserve history)
ALTER TABLE health_records
ADD FOREIGN KEY (ai_provider_id) REFERENCES ai_providers(id) ON DELETE SET NULL,
ADD FOREIGN KEY (ai_model_id) REFERENCES ai_models(id) ON DELETE SET NULL;

-- Add index for efficient lookups
ALTER TABLE health_records 
ADD INDEX idx_health_provider_model_id (ai_provider_id, ai_model_id);
```

---

### Priority 3: Fix SyncLog Table

```sql
-- Add foreign key column
ALTER TABLE sync_logs 
ADD COLUMN ai_provider_id INT NULL AFTER id;

-- Add foreign key
ALTER TABLE sync_logs
ADD FOREIGN KEY (ai_provider_id) REFERENCES ai_providers(id) ON DELETE SET NULL;

-- Add index
ALTER TABLE sync_logs 
ADD INDEX idx_sync_provider_id (ai_provider_id, synced_at);
```

---

## ORM Model Updates Required

### TaskMapping Model Changes

```python
class TaskMapping(Base):
    __tablename__ = "task_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(64), unique=True, nullable=False, index=True)
    
    # OLD: String references (keep for backward compatibility during migration)
    provider_id_ref = Column(String(128), nullable=False)
    model_id = Column(String(255), nullable=False)
    
    # NEW: Proper foreign keys
    ai_provider_id = Column(Integer, ForeignKey("ai_providers.id", ondelete="CASCADE"), nullable=False)
    ai_model_id = Column(Integer, ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    provider = relationship("AIProvider", back_populates="task_mappings")
    model = relationship("AIModel", back_populates="task_mappings")

    __table_args__ = (
        UniqueConstraint("ai_provider_id", "ai_model_id", "task_type", name="uq_task_mapping"),
    )
```

---

## Migration Script

See `database_migration_script.sql` for complete migration commands.

---

## Root Cause Analysis

### Why Dropdowns Show Inconsistent Models

1. **TaskMapping uses String references** - Not actual FKs
   - Application queries TaskMapping independently
   - Then looks up providers/models separately
   - Race conditions possible between queries

2. **No referential integrity** - Deleted providers don't clean up task mappings
   - Task mappings may reference deleted providers
   - UI shows "ghost" entries

3. **Different query paths** - New Chat vs Task Mapping use different loading logic
   - New Chat: Uses `/api/models/available` → queries ai_models directly
   - Task Mapping: Uses `/api/models/v2/catalog` → uses v2GetCatalog()
   - Both should use same source but filters differ

### Recommended Fix

**Immediate (Code-level):**
- Ensure both endpoints use same base query
- Add application-level validation for task mapping integrity

**Long-term (Database-level):**
- Implement migration to add proper FKs
- Update ORM models with relationships
- Simplify queries to use JOINs

---

## Validation Checklist

After migration, verify:

- [ ] Every task mapping has valid provider FK
- [ ] Every task mapping has valid model FK
- [ ] No orphaned task mappings exist
- [ ] Provider deletion cascades to task mappings
- [ ] Model deletion cascades to task mappings
- [ ] Queries use JOINs for efficient loading
- [ ] New Chat and Task Mapping show identical model lists
- [ ] Foreign keys are enforced at database level

---

## Appendix: Current Database Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        ai_providers                         │
├─────────────────────────────────────────────────────────────┤
│ id (PK) ◄────────────────────┐                              │
│ provider_id (UK)             │                              │
│ name                         │                              │
│ status                       │                              │
│ ...                          │                              │
└──────────────────────────────┼──────────────────────────────┘
                               │ 1:N
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                         ai_models                           │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                                     │
│ provider_id (FK) ────────────┐                              │
│ model_id                     │                              │
│ display_name                 │                              │
│ state                        │                              │
│ ...                          │                              │
└──────────────────────────────┴──────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                       task_mappings                         │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                                     │
│ task_type (UK)                                              │
│ provider_id_ref ───► NO FK! (String)                        │
│ model_id ──────────► NO FK! (String)                        │
│ is_active                                                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                       health_records                        │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                                     │
│ provider_id ───────► NO FK! (String)                        │
│ model_id ──────────► NO FK! (String)                        │
│ ...                                                         │
└─────────────────────────────────────────────────────────────┘
```

**Legend:**
- PK = Primary Key
- UK = Unique Key
- FK = Foreign Key (with proper constraint)
- NO FK = String reference without database constraint
