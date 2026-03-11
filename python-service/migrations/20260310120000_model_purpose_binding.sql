-- Migration: model_purpose_binding
-- Created: 2026-03-10 12:00:00 UTC+8

-- migrate:up

CREATE TABLE provider_models (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID        NOT NULL REFERENCES llm_providers(id) ON DELETE CASCADE,
    model_id    TEXT        NOT NULL,
    purpose     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_provider_models UNIQUE (provider_id, model_id),
    CONSTRAINT chk_provider_models_purpose CHECK (purpose IS NULL OR purpose IN ('chat', 'title', 'worker'))
);

CREATE UNIQUE INDEX idx_provider_models_purpose ON provider_models (purpose) WHERE purpose IS NOT NULL;

INSERT INTO provider_models (provider_id, model_id, purpose)
SELECT lp.id, elem::text, NULL
FROM llm_providers lp,
     jsonb_array_elements_text(COALESCE(lp.models, '[]'::jsonb)) AS elem;

DROP TABLE provider_categories;

ALTER TABLE llm_providers DROP COLUMN models;

-- migrate:down

ALTER TABLE llm_providers ADD COLUMN models JSONB NOT NULL DEFAULT '[]';

UPDATE llm_providers lp
SET models = (
    SELECT COALESCE(jsonb_agg(pm.model_id ORDER BY pm.created_at), '[]'::jsonb)
    FROM provider_models pm
    WHERE pm.provider_id = lp.id
);

CREATE TABLE provider_categories (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID        NOT NULL REFERENCES llm_providers(id) ON DELETE CASCADE,
    category    TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_provider_categories UNIQUE (provider_id, category)
);

INSERT INTO provider_categories (provider_id, category)
SELECT provider_id, purpose
FROM provider_models
WHERE purpose IS NOT NULL;

DROP TABLE provider_models;
