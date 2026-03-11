-- Version:     20260308000001
-- Description: create_plans
-- Created:     2026-03-08 00:00 UTC+8

-- migrate:up

CREATE TABLE plans (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tasks      JSONB       NOT NULL DEFAULT '[]',
    status     TEXT        NOT NULL DEFAULT 'running',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_plans_session ON plans (session_id, created_at);

-- migrate:down

DROP TABLE IF EXISTS plans;
