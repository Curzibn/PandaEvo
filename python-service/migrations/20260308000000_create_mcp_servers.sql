-- Migration: create_mcp_servers
-- Created: 2026-03-08 00:00:00 UTC+8

-- migrate:up

CREATE TABLE mcp_servers (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT        UNIQUE NOT NULL,
    command    TEXT,
    args       JSONB       NOT NULL DEFAULT '[]',
    env        JSONB,
    url        TEXT,
    headers    JSONB,
    enabled    BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- migrate:down

DROP TABLE IF EXISTS mcp_servers;
