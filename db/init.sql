CREATE TABLE IF NOT EXISTS activity_records (
    id BIGSERIAL PRIMARY KEY,
    order_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    action TEXT,
    reason TEXT,
    event_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_records_order_id
    ON activity_records(order_id);

CREATE INDEX IF NOT EXISTS idx_activity_records_created_at
    ON activity_records(created_at);
CREATE TABLE IF NOT EXISTS decisions (
    id BIGSERIAL PRIMARY KEY,
    order_id TEXT NOT NULL,
    event_id TEXT,
    provider TEXT,
    model TEXT,
    action TEXT,
    reason TEXT,
    prompt_tokens INT DEFAULT 0,
    completion_tokens INT DEFAULT 0,
    latency_ms NUMERIC(10,1) DEFAULT 0,
    fallback_used BOOLEAN DEFAULT FALSE,
    trace_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decisions_order ON decisions(order_id);

CREATE TABLE IF NOT EXISTS supervisor_configs (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    base_instruction TEXT NOT NULL,
    allowed_actions TEXT[] NOT NULL DEFAULT '{}',
    default_wake_minutes INT NOT NULL DEFAULT 60,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS final_outputs (
    id BIGSERIAL PRIMARY KEY,
    order_id TEXT UNIQUE NOT NULL,
    summary TEXT,
    actions_taken JSONB,
    learnings JSONB,
    feedback JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
