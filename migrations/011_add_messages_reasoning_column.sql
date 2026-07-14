-- Migration 011: Add reasoning column to messages table
-- 
-- The 'reasoning' column stores chain-of-thought / reasoning output from AI models.
-- It was added to the SQLAlchemy Message model in Python but never migrated to MySQL,
-- causing OperationalError (1054) "Unknown column 'reasoning' in 'field list'".
--
-- Apply:
--   mysql -u root doctel < migrations/011_add_messages_reasoning_column.sql
--
-- Or run from MySQL CLI:
--   USE doctel;
--   SOURCE migrations/011_add_messages_reasoning_column.sql;

ALTER TABLE messages
  ADD COLUMN reasoning TEXT NULL
  COMMENT 'Model chain-of-thought reasoning output'
  AFTER content;
