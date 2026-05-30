CREATE TABLE IF NOT EXISTS area_nodes (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  parent_id TEXT REFERENCES area_nodes(id) ON DELETE RESTRICT,
  ha_area_ids TEXT[] NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS qr_templates (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  verification_code_hash TEXT NOT NULL,
  scope JSONB NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  default_ttl_seconds INTEGER NOT NULL,
  max_ttl_seconds INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS grants (
  id UUID PRIMARY KEY,
  template_id TEXT REFERENCES qr_templates(id) ON DELETE SET NULL,
  app_instance_id TEXT NOT NULL,
  device_public_key TEXT NOT NULL,
  scope JSONB NOT NULL,
  role TEXT NOT NULL DEFAULT 'guest',
  issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS grants_active_idx
  ON grants (expires_at, revoked_at)
  WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS ha_registry_snapshots (
  id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id),
  payload JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_events (
  id UUID PRIMARY KEY,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  target TEXT NOT NULL,
  details JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_events_created_at_idx ON audit_events (created_at DESC);

CREATE TABLE IF NOT EXISTS notifications (
  id BIGSERIAL PRIMARY KEY,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  delivered_at TIMESTAMPTZ
);

