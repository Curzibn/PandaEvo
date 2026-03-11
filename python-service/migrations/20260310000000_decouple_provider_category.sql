-- Migration: decouple_provider_category
-- Created: 2026-03-10 00:00:00 UTC+8

-- migrate:up

CREATE TABLE provider_categories (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID        NOT NULL REFERENCES llm_providers(id) ON DELETE CASCADE,
    category    TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_provider_categories UNIQUE (provider_id, category)
);

CREATE INDEX idx_provider_categories_category ON provider_categories(category);

INSERT INTO provider_categories (provider_id, category)
SELECT id, category FROM llm_providers;

ALTER TABLE llm_providers DROP COLUMN category;

-- migrate:down

ALTER TABLE llm_providers ADD COLUMN category TEXT NOT NULL DEFAULT 'chat';

UPDATE llm_providers lp
SET category = COALESCE(
    (SELECT pc.category FROM provider_categories pc
     WHERE pc.provider_id = lp.id
     ORDER BY pc.created_at LIMIT 1),
    'chat'
);

DROP TABLE provider_categories;
