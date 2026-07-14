-- ============================================================================
-- MIGRATION: DocTel Vision 2.0 Enterprise Schema Expansion
-- ============================================================================
-- Implements database tables for pillars 3, 4, 6, 9, 10, 11, 12, 13, 14, 15, 17, 20
-- ============================================================================
-- NOTE: This migration contains ALL new tables so they can be created
-- in a single transaction. Each table has IF NOT EXISTS guards for safety.
-- ============================================================================

-- ============================================================================
-- PILLAR 3 — Regeneratable Document Intelligence
-- ============================================================================
CREATE TABLE IF NOT EXISTS doc_analysis_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    version INT NOT NULL DEFAULT 1,
    analysis_type VARCHAR(32) NOT NULL COMMENT 'summary | extraction | classification',
    executive_summary TEXT DEFAULT '',
    detailed_summary TEXT DEFAULT '',
    entities_json TEXT DEFAULT '[]',
    topics_json TEXT DEFAULT '[]',
    actions_json TEXT DEFAULT '[]',
    decisions_json TEXT DEFAULT '[]',
    categories_json TEXT DEFAULT '[]',
    sentiment VARCHAR(64) DEFAULT '',
    risk_score FLOAT DEFAULT NULL,
    model_id VARCHAR(255) DEFAULT '',
    provider_id VARCHAR(128) DEFAULT '',
    prompt_version INT DEFAULT NULL,
    duration_ms INT DEFAULT NULL,
    token_count INT DEFAULT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    status VARCHAR(32) DEFAULT 'completed' COMMENT 'pending | running | completed | failed',
    error_message TEXT DEFAULT '',
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id),
    UNIQUE KEY uq_doc_analysis_version (document_id, analysis_type, version),
    INDEX idx_doc_analysis_active (document_id, analysis_type, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- PILLAR 4 — Verified Citations & Quotations
-- ============================================================================
CREATE TABLE IF NOT EXISTS quotation_spans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    message_id INT NOT NULL,
    document_id INT DEFAULT NULL,
    chunk_id INT DEFAULT NULL,
    filename VARCHAR(512) DEFAULT '',
    quote_text TEXT NOT NULL,
    source_location VARCHAR(255) DEFAULT '' COMMENT 'e.g. Page 3, Paragraph 2',
    character_offset INT DEFAULT NULL,
    citation_ref VARCHAR(255) DEFAULT '',
    confidence FLOAT DEFAULT 1.0,
    verified BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL,
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE SET NULL,
    INDEX idx_quotation_message (message_id),
    INDEX idx_quotation_document (document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- PILLAR 6 — Enterprise Knowledge Graph
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    node_id VARCHAR(128) NOT NULL UNIQUE,
    node_type VARCHAR(64) NOT NULL COMMENT 'person | topic | entity | decision | project | document | action | policy | meeting',
    label VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '{}',
    source_document_id INT DEFAULT NULL,
    source_project_id INT DEFAULT NULL,
    importance FLOAT DEFAULT 0.0 COMMENT '0.0 - 1.0 centrality score',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (source_document_id) REFERENCES documents(id) ON DELETE SET NULL,
    FOREIGN KEY (source_project_id) REFERENCES projects(id) ON DELETE SET NULL,
    INDEX idx_node_type (node_type),
    INDEX idx_node_type_importance (node_type, importance)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS knowledge_edges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_node_id INT NOT NULL,
    target_node_id INT NOT NULL,
    relation VARCHAR(128) NOT NULL COMMENT 'appears_in | references | linked_to | responsible_for | part_of | impacts',
    weight FLOAT DEFAULT 1.0,
    source_document_id INT DEFAULT NULL,
    metadata_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_node_id) REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_node_id) REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (source_document_id) REFERENCES documents(id) ON DELETE SET NULL,
    UNIQUE KEY uq_knowledge_edge (source_node_id, target_node_id, relation),
    INDEX idx_edge_source (source_node_id, relation),
    INDEX idx_edge_target (target_node_id, relation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- PILLAR 9 — Document Version Intelligence
-- ============================================================================
CREATE TABLE IF NOT EXISTS document_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    version_number VARCHAR(32) NOT NULL COMMENT '1.0, 2.0, 2.1',
    version_label VARCHAR(255) DEFAULT '' COMMENT 'Original, Amendment 3',
    file_path VARCHAR(512) DEFAULT '',
    file_hash VARCHAR(64) DEFAULT '',
    file_size INT DEFAULT NULL,
    change_summary TEXT DEFAULT '',
    is_superseded BOOLEAN DEFAULT FALSE,
    superseded_by_version VARCHAR(32) DEFAULT NULL,
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id),
    UNIQUE KEY uq_doc_version (document_id, version_number),
    INDEX idx_doc_version_active (document_id, is_superseded)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- PILLAR 10 — Agent Framework
-- ============================================================================
CREATE TABLE IF NOT EXISTS agents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_id VARCHAR(128) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    agent_type VARCHAR(64) NOT NULL COMMENT 'policy | engineering | compliance | project | research | procurement | hr | operations',
    description TEXT DEFAULT '',
    system_prompt TEXT DEFAULT '',
    model_id VARCHAR(255) DEFAULT '',
    provider_id VARCHAR(128) DEFAULT '',
    temperature FLOAT DEFAULT 0.7,
    max_tokens INT DEFAULT 4096,
    allow_delegation BOOLEAN DEFAULT FALSE,
    allowed_tools_json TEXT DEFAULT '[]',
    config_json TEXT DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    owner_role VARCHAR(64) DEFAULT 'admin',
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id),
    INDEX idx_agent_type (agent_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS agent_executions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_id INT NOT NULL,
    session_id INT DEFAULT NULL,
    user_id INT DEFAULT NULL,
    input_text TEXT DEFAULT '',
    output_text TEXT DEFAULT '',
    reasoning_text TEXT DEFAULT '',
    tool_calls_json TEXT DEFAULT '[]',
    status VARCHAR(32) DEFAULT 'running' COMMENT 'running | completed | failed | needs_review',
    duration_ms INT DEFAULT NULL,
    token_count INT DEFAULT NULL,
    cost FLOAT DEFAULT NULL,
    error_message TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL DEFAULT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_agent_exec_user (user_id),
    INDEX idx_agent_exec_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- PILLAR 11 — Human Review Workflows
-- ============================================================================
CREATE TABLE IF NOT EXISTS human_reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    review_type VARCHAR(64) NOT NULL COMMENT 'summary | decision | report | policy_output | extraction | classification | agent_output',
    entity_type VARCHAR(64) NOT NULL COMMENT 'doc_analysis | agent_execution | message',
    entity_id INT NOT NULL,
    content_before TEXT DEFAULT '',
    content_after TEXT DEFAULT '',
    status VARCHAR(32) DEFAULT 'pending' COMMENT 'pending | approved | rejected | changes_requested',
    reviewer_id INT DEFAULT NULL,
    review_comment TEXT DEFAULT '',
    approved_at TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reviewer_id) REFERENCES users(id),
    INDEX idx_review_entity (entity_type, entity_id),
    INDEX idx_review_status (status),
    INDEX idx_review_reviewer (reviewer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- PILLAR 12 — Prompt Governance
-- ============================================================================
CREATE TABLE IF NOT EXISTS prompt_templates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    template_id VARCHAR(128) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    task_type VARCHAR(64) NOT NULL COMMENT 'chat | summary | extraction | classification | comparison | diagram | code | custom',
    current_version INT DEFAULT 1,
    owner VARCHAR(128) DEFAULT '',
    department VARCHAR(64) DEFAULT '',
    approval_status VARCHAR(32) DEFAULT 'draft' COMMENT 'draft | pending_approval | approved | rejected | deprecated',
    effective_date TIMESTAMP NULL DEFAULT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id),
    INDEX idx_prompt_task_type (task_type, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS prompt_template_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    template_id INT NOT NULL,
    version INT NOT NULL,
    content TEXT NOT NULL,
    change_notes TEXT DEFAULT '',
    approved_by INT DEFAULT NULL,
    approved_at TIMESTAMP NULL DEFAULT NULL,
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id) REFERENCES prompt_templates(id) ON DELETE CASCADE,
    FOREIGN KEY (approved_by) REFERENCES users(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    UNIQUE KEY uq_prompt_version (template_id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- PILLAR 13 — Model Evaluation Framework
-- ============================================================================
CREATE TABLE IF NOT EXISTS benchmark_runs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    model_id VARCHAR(255) NOT NULL,
    provider_id VARCHAR(128) NOT NULL,
    dataset_name VARCHAR(255) DEFAULT '',
    total_queries INT DEFAULT 0,
    successful_queries INT DEFAULT 0,
    status VARCHAR(32) DEFAULT 'pending' COMMENT 'pending | running | completed | failed',
    started_at TIMESTAMP NULL DEFAULT NULL,
    completed_at TIMESTAMP NULL DEFAULT NULL,
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS benchmark_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    query TEXT NOT NULL,
    expected_output TEXT DEFAULT '',
    actual_output TEXT DEFAULT '',
    accuracy_score FLOAT DEFAULT NULL,
    citation_quality FLOAT DEFAULT NULL,
    hallucination_rate FLOAT DEFAULT NULL,
    latency_ms INT DEFAULT NULL,
    token_count INT DEFAULT NULL,
    cost FLOAT DEFAULT NULL,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES benchmark_runs(id) ON DELETE CASCADE,
    INDEX idx_benchmark_run (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- PILLAR 14 — Cost Governance
-- ============================================================================
CREATE TABLE IF NOT EXISTS cost_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_type VARCHAR(32) NOT NULL COMMENT 'message | agent_execution | analysis | benchmark | embedding',
    source_id INT DEFAULT NULL,
    provider_id VARCHAR(128) NOT NULL,
    model_id VARCHAR(255) NOT NULL,
    user_id INT DEFAULT NULL,
    project_id INT DEFAULT NULL,
    department VARCHAR(64) DEFAULT '',
    tokens_input INT DEFAULT 0,
    tokens_output INT DEFAULT 0,
    tokens_total INT DEFAULT 0,
    cost_per_token FLOAT DEFAULT 0.0,
    total_cost FLOAT DEFAULT 0.0,
    currency VARCHAR(8) DEFAULT 'USD',
    duration_ms INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL,
    INDEX idx_cost_provider (provider_id, created_at),
    INDEX idx_cost_user (user_id, created_at),
    INDEX idx_cost_department (department, created_at),
    INDEX idx_cost_project (project_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS budget_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    scope_type VARCHAR(32) NOT NULL COMMENT 'department | project | user | global',
    scope_id VARCHAR(128) DEFAULT NULL COMMENT 'department code, project id, user id, or *',
    budget_amount FLOAT NOT NULL,
    currency VARCHAR(8) DEFAULT 'USD',
    period VARCHAR(16) DEFAULT 'monthly' COMMENT 'daily | weekly | monthly | quarterly | yearly',
    current_spend FLOAT DEFAULT 0.0,
    alert_threshold_pct FLOAT DEFAULT 80.0 COMMENT 'Alert at % of budget',
    is_active BOOLEAN DEFAULT TRUE,
    last_alert_sent_at TIMESTAMP NULL DEFAULT NULL,
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id),
    UNIQUE KEY uq_budget_scope (scope_type, scope_id, period)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- PILLAR 15 — Trust & Confidence Scoring
-- ============================================================================
CREATE TABLE IF NOT EXISTS confidence_scores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_type VARCHAR(32) NOT NULL COMMENT 'message | agent_execution | analysis | summary',
    source_id INT NOT NULL,
    overall_score FLOAT NOT NULL DEFAULT 0.0,
    citation_coverage FLOAT DEFAULT NULL,
    retrieval_relevance FLOAT DEFAULT NULL,
    model_confidence FLOAT DEFAULT NULL,
    source_agreement FLOAT DEFAULT NULL,
    reasoning_coherence FLOAT DEFAULT NULL,
    limited_evidence BOOLEAN DEFAULT FALSE,
    contradictory_sources BOOLEAN DEFAULT FALSE,
    low_model_confidence BOOLEAN DEFAULT FALSE,
    details_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_confidence_source (source_type, source_id),
    INDEX idx_confidence_score (overall_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- PILLAR 17 — Security & Governance (Expanded)
-- ============================================================================
CREATE TABLE IF NOT EXISTS department_restrictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    department VARCHAR(64) NOT NULL,
    restriction_type VARCHAR(32) NOT NULL COMMENT 'provider | model | task',
    restriction_id VARCHAR(128) NOT NULL,
    is_allowed BOOLEAN DEFAULT TRUE,
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id),
    UNIQUE KEY uq_dept_restriction (department, restriction_type, restriction_id),
    INDEX idx_dept_restriction (department)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- PILLAR 20 — Full Auditability (Interaction Audit Trail)
-- ============================================================================
CREATE TABLE IF NOT EXISTS interaction_audits (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT DEFAULT NULL,
    message_id INT DEFAULT NULL,
    user_id INT DEFAULT NULL,
    department VARCHAR(64) DEFAULT '',
    prompt_text TEXT DEFAULT '',
    system_prompt TEXT DEFAULT '',
    prompt_template_version INT DEFAULT NULL,
    provider_id VARCHAR(128) NOT NULL,
    model_id VARCHAR(255) NOT NULL,
    vendor VARCHAR(64) DEFAULT '',
    response_text TEXT DEFAULT '',
    reasoning_text TEXT DEFAULT '',
    citations_json TEXT DEFAULT '[]',
    quotations_json TEXT DEFAULT '[]',
    retrieved_chunks_json TEXT DEFAULT '[]',
    retrieval_strategy VARCHAR(32) DEFAULT 'vector' COMMENT 'vector | hybrid | kg | keyword',
    duration_ms INT DEFAULT NULL,
    tokens_input INT DEFAULT NULL,
    tokens_output INT DEFAULT NULL,
    tokens_total INT DEFAULT NULL,
    cost FLOAT DEFAULT NULL,
    confidence_score FLOAT DEFAULT NULL,
    human_reviewed BOOLEAN DEFAULT FALSE,
    review_status VARCHAR(32) DEFAULT 'not_reviewed' COMMENT 'approved | rejected | not_reviewed',
    error_message TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_audit_user_time (user_id, created_at),
    INDEX idx_audit_provider_time (provider_id, created_at),
    INDEX idx_audit_model_time (model_id, created_at),
    INDEX idx_audit_department_time (department, created_at),
    INDEX idx_audit_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- Seed Data — Default prompt templates for governance
-- ============================================================================
INSERT INTO prompt_templates (template_id, name, description, task_type, owner, department, approval_status, is_active)
VALUES
    ('chat-default', 'Default Chat', 'Standard chat Q&A prompt template', 'chat', 'system', 'engineering', 'approved', TRUE),
    ('summary-default', 'Default Summary', 'General document summarization template', 'summary', 'system', 'engineering', 'approved', TRUE),
    ('extraction-default', 'Default Extraction', 'Entity and information extraction template', 'extraction', 'system', 'engineering', 'approved', TRUE),
    ('classification-default', 'Default Classification', 'Document classification template', 'classification', 'system', 'engineering', 'approved', TRUE),
    ('comparison-default', 'Default Comparison', 'Document comparison and diff template', 'comparison', 'system', 'engineering', 'approved', TRUE),
    ('diagram-default', 'Default Diagram', 'Mermaid diagram generation template', 'diagram', 'system', 'engineering', 'approved', TRUE),
    ('policy-chat', 'Policy Expert', 'ZETDC policy knowledge base Q&A', 'chat', 'system', 'policy', 'approved', TRUE),
    ('safety-summary', 'Safety Summary', 'Safety procedure summaries', 'summary', 'system', 'safety', 'approved', TRUE),
    ('reports-default', 'Report Generator', 'Technical report generation', 'chat', 'system', 'reports', 'approved', TRUE),
    ('translation-default', 'Translation', 'Language translation template', 'custom', 'system', 'engineering', 'approved', TRUE)
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- Insert default version for each template
INSERT INTO prompt_template_versions (template_id, version, content, change_notes, created_by)
SELECT pt.id, 1, 'You are a helpful AI assistant for ZETDC (Zimbabwe Electricity Transmission and Distribution Company). Answer questions accurately and concisely based on the provided context. Always cite your sources using the document references provided.', 'Initial version', NULL
FROM prompt_templates pt WHERE pt.template_id = 'chat-default'
ON DUPLICATE KEY UPDATE content = VALUES(content);

INSERT INTO prompt_template_versions (template_id, version, content, change_notes, created_by)
SELECT pt.id, 1, 'Summarize the following document clearly and concisely. Capture key points, decisions, and action items. Format the summary with sections for: Overview, Key Points, Decisions, Action Items.', 'Initial version', NULL
FROM prompt_templates pt WHERE pt.template_id = 'summary-default'
ON DUPLICATE KEY UPDATE content = VALUES(content);

INSERT INTO prompt_template_versions (template_id, version, content, change_notes, created_by)
SELECT pt.id, 1, 'Extract structured information from the following document. Identify: entities (people, organizations, locations), key topics, actions taken, and decisions made. Return the results in a structured JSON format.', 'Initial version', NULL
FROM prompt_templates pt WHERE pt.template_id = 'extraction-default'
ON DUPLICATE KEY UPDATE content = VALUES(content);


-- ============================================================================
-- Migration complete
-- ============================================================================
