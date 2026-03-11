-- Migration: purpose_models_many_to_many
-- Created: 2026-03-10 15:00:00 UTC+8

-- migrate:up

CREATE TABLE purpose_models (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    purpose     TEXT        NOT NULL CHECK (purpose IN ('chat', 'title', 'worker')),
    provider_id UUID        NOT NULL REFERENCES llm_providers(id) ON DELETE CASCADE,
    model_id    TEXT        NOT NULL,
    sort_order  INTEGER     NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_purpose_models UNIQUE (purpose, provider_id, model_id)
);

CREATE INDEX idx_purpose_models_lookup ON purpose_models (purpose, sort_order);

INSERT INTO purpose_models (purpose, provider_id, model_id, sort_order)
SELECT purpose, provider_id, model_id, 0
FROM provider_models
WHERE purpose IS NOT NULL;

DROP INDEX idx_provider_models_purpose;

ALTER TABLE provider_models DROP CONSTRAINT chk_provider_models_purpose;

ALTER TABLE provider_models DROP COLUMN purpose;

-- migrate:down

ALTER TABLE provider_models ADD COLUMN purpose TEXT;

ALTER TABLE provider_models ADD CONSTRAINT chk_provider_models_purpose
    CHECK (purpose IS NULL OR purpose IN ('chat', 'title', 'worker'));

UPDATE provider_models pm
SET purpose = pm2.purpose
FROM (
    SELECT DISTINCT ON (purpose) purpose, provider_id, model_id
    FROM purpose_models
    ORDER BY purpose, sort_order
) pm2
WHERE pm.provider_id = pm2.provider_id AND pm.model_id = pm2.model_id;

CREATE UNIQUE INDEX idx_provider_models_purpose ON provider_models (purpose) WHERE purpose IS NOT NULL;

DROP INDEX idx_purpose_models_lookup;

DROP TABLE purpose_models;
