CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    owner_user_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    settings JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_organizations_tenant_slug ON organizations (tenant_id, slug);
CREATE INDEX IF NOT EXISTS ix_organizations_tenant_id ON organizations (tenant_id);

CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    organization_id TEXT NOT NULL,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_teams_organization_tenant ON teams (organization_id, tenant_id);
CREATE INDEX IF NOT EXISTS ix_teams_slug ON teams (tenant_id, slug);

CREATE TABLE IF NOT EXISTS departments (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    organization_id TEXT NOT NULL,
    team_id TEXT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_departments_organization_tenant ON departments (organization_id, tenant_id);
CREATE INDEX IF NOT EXISTS ix_departments_team ON departments (team_id);

CREATE TABLE IF NOT EXISTS organization_memberships (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    user_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    team_id TEXT,
    department_id TEXT,
    role TEXT NOT NULL DEFAULT 'member',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_org_membership_user_tenant ON organization_memberships (tenant_id, user_id);
CREATE INDEX IF NOT EXISTS ix_org_membership_org ON organization_memberships (organization_id);

CREATE TABLE IF NOT EXISTS organization_approvals (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    organization_id TEXT,
    request_type TEXT NOT NULL DEFAULT 'create',
    requested_by TEXT NOT NULL,
    approver_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT,
    metadata JSON,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_org_approval_tenant ON organization_approvals (tenant_id, status);

CREATE TABLE IF NOT EXISTS tenant_configurations (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    organization_id TEXT,
    config JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_tenant_config_unique ON tenant_configurations (tenant_id);

CREATE TABLE IF NOT EXISTS tenant_limits (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    organization_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    limit_value DOUBLE PRECISION NOT NULL DEFAULT 0,
    period TEXT NOT NULL DEFAULT 'monthly',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_tenant_limits_tenant_metric ON tenant_limits (tenant_id, organization_id, metric_name, period);

CREATE TABLE IF NOT EXISTS tenant_usage (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    organization_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    current_usage DOUBLE PRECISION NOT NULL DEFAULT 0,
    period TEXT NOT NULL DEFAULT 'monthly',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_tenant_usage_tenant_metric ON tenant_usage (tenant_id, organization_id, metric_name, period);
