-- ============================================================================
-- MIGRATION: Add Prompt Suggestions Table
-- ============================================================================
-- Creates the prompt_suggestions table for dynamic rotating prompt suggestions
-- on the New Chat page. Replaces hardcoded prompt buttons.
-- ============================================================================

-- Create prompt_suggestions table
CREATE TABLE IF NOT EXISTS prompt_suggestions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    prompt_text TEXT NOT NULL,
    category VARCHAR(64) DEFAULT 'general',
    enabled BOOLEAN DEFAULT TRUE,
    display_order INT DEFAULT 0,
    icon VARCHAR(64) DEFAULT '💬',
    requires_capability VARCHAR(64) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_prompt_suggestions_category (category),
    INDEX idx_prompt_suggestions_enabled (enabled, display_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Seed default prompt suggestions
INSERT INTO prompt_suggestions (title, prompt_text, category, icon, display_order, enabled) VALUES
-- Policy category
('Explain ZETDC net metering policy', 'Explain the ZETDC net metering policy in detail. What are the requirements, benefits, and process for customers who want to install solar panels?', 'policy', '📋', 1, TRUE),
('What are customer connection requirements?', 'What are the requirements for a new customer to get electricity connection from ZETDC? List all necessary documents, fees, and steps.', 'policy', '📋', 2, TRUE),
('Explain billing categories', 'Explain the different ZETDC billing categories (domestic, commercial, industrial). What are the tariff rates and how is consumption calculated?', 'policy', '📋', 3, TRUE),

-- Safety category
('Summarize ZETDC safety procedures', 'Summarize the key ZETDC safety procedures for electrical work. Include lockout/tagout, PPE requirements, and working near live equipment.', 'safety', '🏗️', 4, TRUE),
('Explain lockout tagout process', 'Explain the ZETDC lockout/tagout (LOTO) process in detail. What are the steps, who is authorized, and what documentation is required?', 'safety', '🔒', 5, TRUE),
('Explain PPE requirements', 'What are the PPE requirements for ZETDC field staff? List required equipment for different types of electrical work.', 'safety', '🦺', 6, TRUE),

-- Reports category
('Create a monthly outage report', 'Create a template for a monthly power outage report. Include sections for: outage duration, affected areas, cause analysis, and restoration time.', 'reports', '📊', 7, TRUE),
('Summarize incident reports', 'Summarize how to write effective incident reports for ZETDC. What information must be included and what is the reporting timeline?', 'reports', '📊', 8, TRUE),
('Generate maintenance report', 'Create a maintenance report template for ZETDC equipment. Include inspection checklist, findings, recommendations, and follow-up actions.', 'reports', '📊', 9, TRUE),

-- Languages category
('Summarize in Shona', 'Summarize the following document in Shona language. Use clear and simple language that non-technical customers can understand.', 'languages', '🇿🇼', 10, TRUE),
('Translate to Ndebele', 'Translate the following text to Ndebele. Maintain technical accuracy while using accessible language.', 'languages', '🇿🇼', 11, TRUE),
('Convert to business English', 'Convert the following technical document to professional business English suitable for corporate communication.', 'languages', '📝', 12, TRUE),

-- Vision category (requires vision capability)
('Analyze an image', 'Analyze this image and describe what you see. If it contains technical equipment, identify components and explain their function.', 'vision', '🖼️', 13, TRUE),
('Extract text from image', 'Extract all text visible in this image. Format it clearly and indicate if any text is unclear or ambiguous.', 'vision', '🖼️', 14, TRUE),

-- General category
('ZETDC outage reporting process', 'Explain the ZETDC outage reporting process. How do customers report outages and what information should they provide?', 'general', '⚡', 15, TRUE),
('Troubleshoot common issues', 'List common electrical issues customers face and provide troubleshooting steps before calling ZETDC.', 'general', '🔧', 16, TRUE),
('Energy saving tips', 'Provide practical energy saving tips for ZETDC customers to reduce their electricity bills.', 'general', '💡', 17, TRUE);

-- Update capabilities for vision prompts
UPDATE prompt_suggestions SET requires_capability = 'vision' WHERE category = 'vision';

-- ============================================================================
-- Migration complete
-- ============================================================================
SELECT CONCAT('Created ', COUNT(*), ' default prompt suggestions') AS result FROM prompt_suggestions;
