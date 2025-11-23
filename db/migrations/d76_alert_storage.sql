-- D76 Alert Storage Migration
-- Create alert_history table with indexes

CREATE TABLE IF NOT EXISTS alert_history (
    id SERIAL PRIMARY KEY,
    severity VARCHAR(10) NOT NULL,
    source VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_alert_history_severity ON alert_history(severity);
CREATE INDEX IF NOT EXISTS idx_alert_history_source ON alert_history(source);
CREATE INDEX IF NOT EXISTS idx_alert_history_timestamp ON alert_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alert_history_created_at ON alert_history(created_at DESC);

-- Comments
COMMENT ON TABLE alert_history IS 'D76 Alerting System - Alert History Storage';
COMMENT ON COLUMN alert_history.severity IS 'Alert severity: P0, P1, P2, P3';
COMMENT ON COLUMN alert_history.source IS 'Alert source: rate_limiter, exchange_health, etc.';
COMMENT ON COLUMN alert_history.metadata IS 'Additional alert metadata in JSON format';
COMMENT ON COLUMN alert_history.timestamp IS 'Alert occurrence timestamp';
COMMENT ON COLUMN alert_history.created_at IS 'Record insertion timestamp';

-- Verification query
SELECT 
    COUNT(*) as table_exists,
    (SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'alert_history') as index_count
FROM information_schema.tables 
WHERE table_name = 'alert_history';
