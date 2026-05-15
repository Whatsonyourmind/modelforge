-- Supabase initial schema: tenants + members + workbooks metadata.
--
-- Apply via Supabase SQL Editor (free tier) or psql:
--   psql "$SUPABASE_DB_URL" -f migrations/001_supabase_init.sql
--
-- Mirrors the SQLite shape in modelforge/saas/tenant.py so the dev-mode
-- (SQLite) and prod-mode (Postgres+RLS) layers behave identically.

-- =============================================================================
-- 1. Core entities
-- =============================================================================

CREATE TABLE IF NOT EXISTS tenants (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    plan         TEXT NOT NULL DEFAULT 'free',
    seats        INTEGER NOT NULL DEFAULT 1,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deactivated  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS tenant_members (
    tenant_id    TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    email        TEXT,
    role         TEXT NOT NULL DEFAULT 'member',
    joined_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_member_user ON tenant_members(user_id);

-- Workbook registry — one row per uploaded/built workbook
CREATE TABLE IF NOT EXISTS workbooks (
    id              TEXT PRIMARY KEY,        -- sha256[:16]
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    uploaded_by     UUID NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
    spec_sha256     TEXT,
    workbook_sha256 TEXT NOT NULL,
    sources_sha256  TEXT,
    bytes_size      BIGINT NOT NULL,
    storage_path    TEXT NOT NULL,           -- relative to tenant storage root
    template        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wb_tenant ON workbooks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_wb_spec ON workbooks(spec_sha256);

-- Audit log slice surfaced to the SaaS UI (separate from local audit DB)
CREATE TABLE IF NOT EXISTS audit_events_saas (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    actor_id    UUID REFERENCES auth.users(id),
    action      TEXT NOT NULL,
    resource    TEXT,
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_events_saas(tenant_id, created_at DESC);

-- Billing events (Stripe webhook hits land here)
CREATE TABLE IF NOT EXISTS billing_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_event_id TEXT UNIQUE NOT NULL,
    tenant_id       TEXT REFERENCES tenants(id),
    user_id         UUID REFERENCES auth.users(id),
    event_type      TEXT NOT NULL,
    amount_cents    BIGINT,
    currency        TEXT,
    plan            TEXT,
    raw_payload     JSONB NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_billing_tenant ON billing_events(tenant_id, received_at DESC);

-- =============================================================================
-- 2. Row-level security policies
-- =============================================================================

ALTER TABLE tenants            ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_members     ENABLE ROW LEVEL SECURITY;
ALTER TABLE workbooks          ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events_saas  ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_events     ENABLE ROW LEVEL SECURITY;

-- Tenants: every member can read own tenant; only owner can update
CREATE POLICY tenants_member_read ON tenants
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM tenant_members
             WHERE tenant_members.tenant_id = tenants.id
               AND tenant_members.user_id = auth.uid()
        )
    );

CREATE POLICY tenants_owner_update ON tenants
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM tenant_members
             WHERE tenant_members.tenant_id = tenants.id
               AND tenant_members.user_id = auth.uid()
               AND tenant_members.role = 'owner'
        )
    );

-- Members: visible to other members of the same tenant
CREATE POLICY members_visible_to_tenant ON tenant_members
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM tenant_members AS m
             WHERE m.tenant_id = tenant_members.tenant_id
               AND m.user_id = auth.uid()
        )
    );

-- Owners + admins manage members
CREATE POLICY members_admin_manage ON tenant_members
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM tenant_members AS m
             WHERE m.tenant_id = tenant_members.tenant_id
               AND m.user_id = auth.uid()
               AND m.role IN ('owner', 'admin')
        )
    );

-- Workbooks: tenant members can read; uploader (or admin/owner) can write
CREATE POLICY wb_tenant_read ON workbooks
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM tenant_members
             WHERE tenant_members.tenant_id = workbooks.tenant_id
               AND tenant_members.user_id = auth.uid()
        )
    );

CREATE POLICY wb_owner_or_admin_write ON workbooks
    FOR ALL USING (
        uploaded_by = auth.uid()
     OR EXISTS (
            SELECT 1 FROM tenant_members
             WHERE tenant_members.tenant_id = workbooks.tenant_id
               AND tenant_members.user_id = auth.uid()
               AND tenant_members.role IN ('owner', 'admin')
        )
    );

-- Audit events: read-only for tenant members; insert via service role only
CREATE POLICY audit_tenant_read ON audit_events_saas
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM tenant_members
             WHERE tenant_members.tenant_id = audit_events_saas.tenant_id
               AND tenant_members.user_id = auth.uid()
        )
    );

-- Billing: owners only (sensitive data)
CREATE POLICY billing_owner_read ON billing_events
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM tenant_members
             WHERE tenant_members.tenant_id = billing_events.tenant_id
               AND tenant_members.user_id = auth.uid()
               AND tenant_members.role = 'owner'
        )
    );

-- =============================================================================
-- 3. Triggers — auto-create tenant on user signup
-- =============================================================================

-- When a new auth.user is created, automatically provision a personal tenant.
-- This is the path that gives every signup a working tenant immediately;
-- enterprise tenants are created via the SaaS UI after the user signs in.
CREATE OR REPLACE FUNCTION provision_personal_tenant()
RETURNS TRIGGER AS $$
DECLARE
    new_tid TEXT;
BEGIN
    new_tid := 'tenant_' || replace(gen_random_uuid()::text, '-', '');
    INSERT INTO tenants (id, name, plan, seats)
        VALUES (new_tid, COALESCE(NEW.email, 'Personal'), 'free', 1);
    INSERT INTO tenant_members (tenant_id, user_id, email, role)
        VALUES (new_tid, NEW.id, NEW.email, 'owner');
    -- Stash the tenant_id in user_metadata so JWT claims expose it
    UPDATE auth.users
       SET raw_user_meta_data = jsonb_set(
               COALESCE(raw_user_meta_data, '{}'::jsonb),
               '{tenant_id}',
               to_jsonb(new_tid)
           )
     WHERE id = NEW.id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE TRIGGER trg_provision_tenant_on_signup
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION provision_personal_tenant();

-- =============================================================================
-- 4. Verification
-- =============================================================================
-- After applying:
--   SELECT tablename FROM pg_tables WHERE schemaname='public'
--     AND tablename IN ('tenants','tenant_members','workbooks',
--                       'audit_events_saas','billing_events');
-- Should return 5 rows. RLS active for all 5.
