-- ============================================================================
-- MIGRATION: Add Lookup Tables for Configuration-Driven Enums
-- ============================================================================
-- This migration creates database tables to replace hardcoded enums:
--   - VALID_ROLES → roles table
--   - ZETDC_DEPARTMENTS → departments table  
--   - TASK_TYPES → task_types table
--   - MODEL_STATES → model_statuses table
-- ============================================================================

-- ============================================================================
-- 1. CREATE LOOKUP TABLES
-- ============================================================================

-- Roles lookup table
CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    description TEXT DEFAULT '',
    is_system BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_roles_code (code),
    INDEX idx_roles_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Departments lookup table
CREATE TABLE IF NOT EXISTS departments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    description TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_departments_code (code),
    INDEX idx_departments_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Task types lookup table
CREATE TABLE IF NOT EXISTS task_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    description TEXT DEFAULT '',
    display_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_task_types_code (code),
    INDEX idx_task_types_active (is_active),
    INDEX idx_task_types_order (display_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Model statuses lookup table
CREATE TABLE IF NOT EXISTS model_statuses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    description TEXT DEFAULT '',
    is_selectable BOOLEAN DEFAULT TRUE,
    is_visible BOOLEAN DEFAULT TRUE,
    display_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_model_statuses_code (code),
    INDEX idx_model_statuses_selectable (is_selectable),
    INDEX idx_model_statuses_visible (is_visible)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 2. SEED DATA FROM HARDCODED ENUMS
-- ============================================================================

-- Insert roles (from VALID_ROLES)
INSERT INTO roles (code, name, description, is_system, is_active) VALUES
('super_admin', 'Super Administrator', 'Full system access and control', TRUE, TRUE),
('admin', 'Administrator', 'System administration privileges', TRUE, TRUE),
('manager', 'Manager', 'Department or team management', TRUE, TRUE),
('engineer', 'Engineer', 'Technical engineering staff', TRUE, TRUE),
('power_user', 'Power User', 'Advanced user with extended permissions', TRUE, TRUE),
('general_user', 'General User', 'Standard system user', TRUE, TRUE),
('guest', 'Guest', 'Limited access guest user', TRUE, TRUE)
ON DUPLICATE KEY UPDATE 
    name = VALUES(name),
    description = VALUES(description),
    is_system = VALUES(is_system),
    is_active = VALUES(is_active);

-- Insert departments (from ZETDC_DEPARTMENTS)
INSERT INTO departments (code, name, description, is_active) VALUES
('ict', 'ICT', 'Information and Communication Technology', TRUE),
('generation', 'Generation', 'Power Generation Department', TRUE),
('transmission', 'Transmission', 'Power Transmission Department', TRUE),
('distribution', 'Distribution', 'Power Distribution Department', TRUE),
('projects', 'Projects', 'Projects and Infrastructure', TRUE),
('operations', 'Operations', 'Operations and Maintenance', TRUE),
('finance', 'Finance', 'Finance and Accounting', TRUE),
('human_resources', 'Human Resources', 'HR and Personnel Management', TRUE),
('procurement', 'Procurement', 'Procurement and Supply Chain', TRUE),
('customer_services', 'Customer Services', 'Customer Support and Services', TRUE)
ON DUPLICATE KEY UPDATE 
    name = VALUES(name),
    description = VALUES(description),
    is_active = VALUES(is_active);

-- Insert task types (from TASK_TYPES)
INSERT INTO task_types (code, name, description, display_order, is_active) VALUES
('chat', 'Chat', 'General conversational AI chat', 1, TRUE),
('summary', 'Summary', 'Document and text summarization', 2, TRUE),
('extraction', 'Extraction', 'Information extraction from documents', 3, TRUE),
('classification', 'Classification', 'Document and content classification', 4, TRUE),
('comparison', 'Comparison', 'Compare documents or content', 5, TRUE),
('vision', 'Vision', 'Image understanding and analysis', 6, TRUE),
('embedding', 'Embedding', 'Text embedding generation', 7, TRUE),
('rag', 'RAG', 'Retrieval-Augmented Generation', 8, TRUE),
('code_generation', 'Code Generation', 'Generate and analyze code', 9, TRUE)
ON DUPLICATE KEY UPDATE 
    name = VALUES(name),
    description = VALUES(description),
    display_order = VALUES(display_order),
    is_active = VALUES(is_active);

-- Insert model statuses (from MODEL_STATES)
INSERT INTO model_statuses (code, name, description, is_selectable, is_visible, display_order) VALUES
('active', 'Active', 'Model is active and available for use', TRUE, TRUE, 1),
('inactive', 'Inactive', 'Model is temporarily inactive', FALSE, FALSE, 2),
('installed', 'Installed', 'Model is installed locally', TRUE, TRUE, 3),
('downloading', 'Downloading', 'Model is currently being downloaded', FALSE, TRUE, 4),
('error', 'Error', 'Model has an error state', FALSE, TRUE, 5),
('maintenance', 'Maintenance', 'Model is under maintenance', FALSE, TRUE, 6),
('retired', 'Retired', 'Model has been retired', FALSE, FALSE, 7)
ON DUPLICATE KEY UPDATE 
    name = VALUES(name),
    description = VALUES(description),
    is_selectable = VALUES(is_selectable),
    is_visible = VALUES(is_visible),
    display_order = VALUES(display_order);

-- ============================================================================
-- 3. MIGRATION COMPLETE
-- ============================================================================

-- Verify data insertion
SELECT 'Roles inserted:' as message, COUNT(*) as count FROM roles;
SELECT 'Departments inserted:' as message, COUNT(*) as count FROM departments;
SELECT 'Task types inserted:' as message, COUNT(*) as count FROM task_types;
SELECT 'Model statuses inserted:' as message, COUNT(*) as count FROM model_statuses;
