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