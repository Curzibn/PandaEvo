-- Migration: add_category_to_llm_providers
-- Created: 2026-03-09 12:00:00 UTC+8

-- migrate:up

ALTER TABLE llm_providers ADD COLUMN category TEXT NOT NULL DEFAULT 'chat';

-- migrate:down

ALTER TABLE llm_providers DROP COLUMN category;
