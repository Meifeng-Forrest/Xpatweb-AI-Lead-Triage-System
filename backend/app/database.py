import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request

from app.config import Settings

logger = logging.getLogger("lead_triage.database")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS leads (
    lead_id TEXT PRIMARY KEY,
    sender_name TEXT NOT NULL,
    email_address TEXT NOT NULL,
    contact_number TEXT,
    email_domain TEXT NOT NULL,
    visa_category TEXT,
    lead_type TEXT,
    current_visa TEXT,
    pr_route TEXT,
    nationality TEXT,
    is_first_world BOOLEAN,
    job_title TEXT,
    net_worth_indicator TEXT,
    has_job_offer BOOLEAN,
    qualifying_work_visa_years NUMERIC,
    annual_salary_zar NUMERIC,
    pbs_total_score_below_100 BOOLEAN,
    relationship_duration TEXT,
    marriage_type TEXT,
    rejection_date TEXT,
    urgency_flag BOOLEAN,
    multi_visa_flag BOOLEAN,
    email_coherence TEXT,
    additional_info TEXT,
    extracted_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    extracted_at TIMESTAMPTZ,
    extraction_provider TEXT,
    extraction_model TEXT,
    extraction_temperature NUMERIC,
    lead_score TEXT,
    dnq_reason TEXT,
    risk_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    score_confidence TEXT,
    score_rationale TEXT,
    escalation_flag BOOLEAN NOT NULL DEFAULT FALSE,
    soft_dnq_warning TEXT,
    score_provider TEXT,
    score_model TEXT,
    score_temperature NUMERIC,
    scored_at TIMESTAMPTZ,
    email_draft TEXT,
    whatsapp_draft TEXT,
    phone_script TEXT,
    internal_whatsapp_post TEXT,
    draft_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    draft_provider TEXT,
    draft_model TEXT,
    draft_temperature NUMERIC,
    drafted_at TIMESTAMPTZ,
    source_box TEXT NOT NULL,
    lead_source TEXT,
    assigned_consultant TEXT,
    raw_message TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_status_created_at ON leads (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_source_box_created_at ON leads (source_box, created_at DESC);

ALTER TABLE leads ADD COLUMN IF NOT EXISTS lead_type TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS current_visa TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS pr_route TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS nationality TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS is_first_world BOOLEAN;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS job_title TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS net_worth_indicator TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS has_job_offer BOOLEAN;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS qualifying_work_visa_years NUMERIC;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS annual_salary_zar NUMERIC;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS pbs_total_score_below_100 BOOLEAN;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS relationship_duration TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS marriage_type TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS rejection_date TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS urgency_flag BOOLEAN;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS multi_visa_flag BOOLEAN;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS email_coherence TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS additional_info TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS extracted_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS extracted_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS extraction_provider TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS extraction_model TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS extraction_temperature NUMERIC;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS lead_score TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS dnq_reason TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS risk_flags JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS score_confidence TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS score_rationale TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS escalation_flag BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS soft_dnq_warning TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS score_provider TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS score_model TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS score_temperature NUMERIC;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS scored_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS email_draft TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS whatsapp_draft TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS phone_script TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS internal_whatsapp_post TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS draft_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS draft_provider TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS draft_model TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS draft_temperature NUMERIC;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS drafted_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS assigned_consultant TEXT;

CREATE INDEX IF NOT EXISTS idx_leads_email_coherence_created_at
    ON leads (email_coherence, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_score_created_at
    ON leads (lead_score, created_at DESC);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id BIGSERIAL PRIMARY KEY,
    lead_id TEXT NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_events_lead_id_created_at
    ON audit_events (lead_id, created_at DESC);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, role)
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles (role);

CREATE TABLE IF NOT EXISTS routing_rules (
    category TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (category, user_id)
);

CREATE INDEX IF NOT EXISTS idx_routing_rules_category ON routing_rules (category);

-- 角色从“权限+路由信箱”收敛为纯权限。这里先插新角色再删除旧角色，
-- 避免同一用户同时有 lead_agent/team_lead 时直接 UPDATE 撞主键。
INSERT INTO user_roles (user_id, role)
    SELECT user_id, 'agent' FROM user_roles WHERE role IN ('lead_agent', 'team_lead')
    ON CONFLICT DO NOTHING;
INSERT INTO user_roles (user_id, role)
    SELECT user_id, 'reviewer' FROM user_roles WHERE role IN ('escalation_handler', 'visa_verifier')
    ON CONFLICT DO NOTHING;
DELETE FROM user_roles WHERE role IN ('lead_agent', 'team_lead', 'escalation_handler', 'visa_verifier');

-- 角色按职责重切：admin 改名为 superadmin，业务审批另由 approver 承担。
-- 保留 user_roles 多对多表结构，只在服务层限制一人一角色，方便未来放开。
INSERT INTO user_roles (user_id, role)
    SELECT user_id, 'superadmin' FROM user_roles WHERE role = 'admin'
    ON CONFLICT DO NOTHING;
DELETE FROM user_roles WHERE role = 'admin';

CREATE TABLE IF NOT EXISTS user_audit_events (
    event_id BIGSERIAL PRIMARY KEY,
    target_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_audit_events_target_created_at
    ON user_audit_events (target_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS research_briefs (
    lead_id TEXT PRIMARY KEY REFERENCES leads(lead_id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    task_id TEXT,
    brief JSONB,
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_type TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_research_briefs_status_updated_at
    ON research_briefs (status, updated_at DESC);
"""


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


async def create_pool(settings: Settings) -> asyncpg.Pool:
    safe_url = normalize_database_url(settings.database_url)
    logger.info("[db/pool] enter %s", {"database_url_configured": bool(settings.database_url)})
    pool = await asyncpg.create_pool(dsn=safe_url, min_size=1, max_size=5)
    logger.info("[db/pool] success %s", {"min_size": 1, "max_size": 5})
    return pool


async def init_schema(pool: asyncpg.Pool) -> None:
    logger.info("[db/schema] enter %s", {"operation": "create_if_missing"})
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    logger.info(
        "[db/schema] success %s",
        {"tables": ["leads", "audit_events", "users", "user_roles", "routing_rules", "user_audit_events", "research_briefs"]},
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    pool = await create_pool(settings)
    app.state.db_pool = pool
    await init_schema(pool)
    from app.services.auth import seed_default_users

    await seed_default_users(pool, settings)
    try:
        yield
    finally:
        logger.info("[db/pool] close %s", {"status": "closing"})
        await pool.close()


def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool
