-- Migration: create_llm_providers
-- Created: 2026-03-09 00:00:00 UTC+8

-- migrate:up

CREATE TABLE llm_providers (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT        UNIQUE NOT NULL,
    api_key    TEXT        NOT NULL DEFAULT '',
    api_base   TEXT,
    models     JSONB       NOT NULL DEFAULT '[]',
    enabled    BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- migrate:down

DROP TABLE IF EXISTS llm_providers;
