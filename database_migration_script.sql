-- ============================================================
-- Database Migration Script
-- Fix Foreign Key Relationships for Provider/Model Management
-- ============================================================
-- Run this script against your MySQL database to:
-- 1. Add proper foreign keys to task_mappings
-- 2. Add proper foreign keys to health_records
-- 3. Add proper foreign keys to sync_logs
-- 4. Migrate existing data
-- 5. Add constraints and indexes
-- ============================================================

-- ============================================================
-- STEP 1: Fix task_mappings table
-- ============================================================

-- Add new foreign key columns
ALTER TABLE task_mappings 
ADD COLUMN ai_provider_id INT NULL AFTER id,
ADD COLUMN ai_model_id INT NULL AFTER ai_provider_id;

-- Migrate existing data from String references to Integer FKs
-- This joins on provider_id (business key) and model_id to find the correct FKs
UPDATE task_mappings tm
JOIN ai_providers p ON tm.provider_id_ref = p.provider_id
LEFT JOIN ai_models m ON tm.model_id = m.model_id 
    AND m.provider_id = p.id
SET tm.ai_provider_id = p.id,
    tm.ai_model_id = COALESCE(m.id, 0);

-- Handle orphaned records (task mappings with no matching model)
-- Option A: Delete orphaned task mappings (if model was deleted)
-- DELETE FROM task_mappings WHERE ai_model_id = 0 OR ai_model_id IS NULL;

-- Option B: Keep but mark as inactive (safer for existing data)
UPDATE task_mappings 
SET is_active = FALSE 
WHERE ai_model_id = 0 OR ai_model_id IS NULL;

-- Add foreign key constraints
ALTER TABLE task_mappings
ADD CONSTRAINT fk_task_mapping_provider 
    FOREIGN KEY (ai_provider_id) REFERENCES ai_providers(id) ON DELETE CASCADE,
ADD CONSTRAINT fk_task_mapping_model 
    FOREIGN KEY (ai_model_id) REFERENCES ai_models(id) ON DELETE CASCADE;

-- Make columns NOT NULL after ensuring data integrity
ALTER TABLE task_mappings 
MODIFY ai_provider_id INT NOT NULL,
MODIFY ai_model_id INT NOT NULL;

-- Add unique constraint to prevent duplicate task mappings
ALTER TABLE task_mappings 
ADD CONSTRAINT uq_task_mapping 
    UNIQUE KEY (ai_provider_id, ai_model_id, task_type);

-- Add index for efficient lookups
ALTER TABLE task_mappings 
ADD INDEX idx_task_mapping_provider (ai_provider_id),
ADD INDEX idx_task_mapping_model (ai_model_id);

-- ============================================================
-- STEP 2: Fix health_records table
-- ============================================================

-- Add new foreign key columns
ALTER TABLE health_records 
ADD COLUMN ai_provider_id INT NULL AFTER id,
ADD COLUMN ai_model_id INT NULL AFTER ai_provider_id;

-- Migrate existing data
UPDATE health_records hr
JOIN ai_providers p ON hr.provider_id = p.provider_id
LEFT JOIN ai_models m ON hr.model_id = m.model_id 
    AND m.provider_id = p.id
SET hr.ai_provider_id = p.id,
    hr.ai_model_id = m.id;

-- Add foreign key constraints (SET NULL to preserve history when provider/model deleted)
ALTER TABLE health_records
ADD CONSTRAINT fk_health_provider 
    FOREIGN KEY (ai_provider_id) REFERENCES ai_providers(id) ON DELETE SET NULL,
ADD CONSTRAINT fk_health_model 
    FOREIGN KEY (ai_model_id) REFERENCES ai_models(id) ON DELETE SET NULL;

-- Add indexes
ALTER TABLE health_records 
ADD INDEX idx_health_provider_id (ai_provider_id),
ADD INDEX idx_health_model_id (ai_model_id);

-- ============================================================
-- STEP 3: Fix sync_logs table
-- ============================================================

-- Add new foreign key column
ALTER TABLE sync_logs 
ADD COLUMN ai_provider_id INT NULL AFTER id;

-- Migrate existing data
UPDATE sync_logs sl
JOIN ai_providers p ON sl.provider_id = p.provider_id
SET sl.ai_provider_id = p.id;

-- Add foreign key constraint
ALTER TABLE sync_logs
ADD CONSTRAINT fk_sync_provider 
    FOREIGN KEY (ai_provider_id) REFERENCES ai_providers(id) ON DELETE SET NULL;

-- Add index
ALTER TABLE sync_logs 
ADD INDEX idx_sync_provider_id (ai_provider_id);

-- ============================================================
-- STEP 4: Verification Queries (Run these to verify migration)
-- ============================================================

-- Check for orphaned task mappings (should return 0 rows)
SELECT COUNT(*) as orphaned_task_mappings
FROM task_mappings tm
LEFT JOIN ai_providers p ON tm.ai_provider_id = p.id
WHERE p.id IS NULL;

-- Check for orphaned health records (should return 0 rows with non-null ai_provider_id)
SELECT COUNT(*) as orphaned_health_records
FROM health_records hr
LEFT JOIN ai_providers p ON hr.ai_provider_id = p.id
WHERE hr.ai_provider_id IS NOT NULL AND p.id IS NULL;

-- Verify foreign keys are working (this should fail if FKs not created)
-- Try to insert invalid FK (should raise error):
-- INSERT INTO task_mappings (task_type, ai_provider_id, ai_model_id, is_active) 
-- VALUES ('test', 99999, 99999, TRUE);

-- ============================================================
-- STEP 5: Cleanup (Optional - after verification)
-- ============================================================

-- After confirming migration works, you can optionally drop old String columns:
-- (Keep them initially for rollback safety)

-- ALTER TABLE task_mappings DROP COLUMN provider_id_ref;
-- ALTER TABLE task_mappings DROP COLUMN model_id;
-- ALTER TABLE health_records DROP COLUMN provider_id;
-- ALTER TABLE health_records DROP COLUMN model_id;
-- ALTER TABLE sync_logs DROP COLUMN provider_id;

-- ============================================================
-- ROLLBACK SCRIPT (If you need to undo)
-- ============================================================
/*
-- Remove foreign keys
ALTER TABLE task_mappings 
DROP FOREIGN KEY fk_task_mapping_provider,
DROP FOREIGN KEY fk_task_mapping_model;

ALTER TABLE health_records 
DROP FOREIGN KEY fk_health_provider,
DROP FOREIGN KEY fk_health_model;

ALTER TABLE sync_logs 
DROP FOREIGN KEY fk_sync_provider;

-- Remove columns
ALTER TABLE task_mappings 
DROP COLUMN ai_provider_id,
DROP COLUMN ai_model_id;

ALTER TABLE health_records 
DROP COLUMN ai_provider_id,
DROP COLUMN ai_model_id;

ALTER TABLE sync_logs 
DROP COLUMN ai_provider_id;
*/
