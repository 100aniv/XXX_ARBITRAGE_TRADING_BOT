-- ============================================================
-- D72-4: Logging & Monitoring MVP - Database Schema
-- ============================================================

-- Create system_logs table for persistent log storage
CREATE TABLE IF NOT EXISTS system_logs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    level VARCHAR(20) NOT NULL,
    component VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    json_payload JSONB,
    session_id VARCHAR(100),
    
    -- Indexes for common queries
    CONSTRAINT level_check CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'))
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level);
CREATE INDEX IF NOT EXISTS idx_system_logs_component ON system_logs(component);
CREATE INDEX IF NOT EXISTS idx_system_logs_category ON system_logs(category);
CREATE INDEX IF NOT EXISTS idx_system_logs_session_id ON system_logs(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_system_logs_payload_gin ON system_logs USING GIN (json_payload);

-- Create composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_system_logs_level_time ON system_logs(level, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_category_time ON system_logs(category, created_at DESC);

-- View: Recent errors
CREATE OR REPLACE VIEW v_recent_errors AS
SELECT 
    id,
    created_at,
    level,
    component,
    category,
    message,
    json_payload,
    session_id
FROM system_logs
WHERE level IN ('ERROR', 'CRITICAL')
ORDER BY created_at DESC
LIMIT 100;

-- View: Error summary by component
CREATE OR REPLACE VIEW v_error_summary AS
SELECT 
    component,
    category,
    level,
    COUNT(*) as error_count,
    MAX(created_at) as last_error_time
FROM system_logs
WHERE level IN ('ERROR', 'CRITICAL')
    AND created_at > NOW() - INTERVAL '1 day'
GROUP BY component, category, level
ORDER BY error_count DESC;

-- View: Log volume by hour
CREATE OR REPLACE VIEW v_log_volume_hourly AS
SELECT 
    DATE_TRUNC('hour', created_at) as hour,
    level,
    component,
    category,
    COUNT(*) as log_count
FROM system_logs
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', created_at), level, component, category
ORDER BY hour DESC, log_count DESC;

-- Function: Clean old logs (retention policy)
CREATE OR REPLACE FUNCTION cleanup_old_logs(days_to_keep INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete logs older than specified days
    -- Keep ERROR and CRITICAL logs longer (30 days)
    DELETE FROM system_logs
    WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep
        AND level NOT IN ('ERROR', 'CRITICAL');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Delete old errors (30 days)
    DELETE FROM system_logs
    WHERE created_at < NOW() - INTERVAL '30 days'
        AND level IN ('ERROR', 'CRITICAL');
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function: Get log statistics
CREATE OR REPLACE FUNCTION get_log_statistics(hours_back INTEGER DEFAULT 24)
RETURNS TABLE (
    level VARCHAR,
    category VARCHAR,
    log_count BIGINT,
    latest_log TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sl.level,
        sl.category,
        COUNT(*) as log_count,
        MAX(sl.created_at) as latest_log
    FROM system_logs sl
    WHERE sl.created_at > NOW() - INTERVAL '1 hour' * hours_back
    GROUP BY sl.level, sl.category
    ORDER BY log_count DESC;
END;
$$ LANGUAGE plpgsql;

-- Function: Search logs by keyword
CREATE OR REPLACE FUNCTION search_logs(
    search_term TEXT,
    limit_count INTEGER DEFAULT 100
)
RETURNS TABLE (
    id BIGINT,
    created_at TIMESTAMP,
    level VARCHAR,
    component VARCHAR,
    category VARCHAR,
    message TEXT,
    json_payload JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sl.id,
        sl.created_at,
        sl.level::VARCHAR,
        sl.component::VARCHAR,
        sl.category::VARCHAR,
        sl.message,
        sl.json_payload
    FROM system_logs sl
    WHERE 
        sl.message ILIKE '%' || search_term || '%'
        OR sl.json_payload::TEXT ILIKE '%' || search_term || '%'
    ORDER BY sl.created_at DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Set table autovacuum settings for frequent writes
ALTER TABLE system_logs SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02,
    autovacuum_vacuum_cost_delay = 10
);

-- Comments
COMMENT ON TABLE system_logs IS 'Persistent storage for system logs (D72-4)';
COMMENT ON COLUMN system_logs.json_payload IS 'Structured payload data in JSONB format';
COMMENT ON FUNCTION cleanup_old_logs IS 'Remove logs older than specified days (default 7, errors kept for 30)';
COMMENT ON FUNCTION get_log_statistics IS 'Get log count statistics by level and category';
COMMENT ON FUNCTION search_logs IS 'Search logs by keyword in message or payload';

-- Verification queries
DO $$
BEGIN
    RAISE NOTICE '=== D72-4 Migration Complete ===';
    RAISE NOTICE 'Table created: system_logs';
    RAISE NOTICE 'Indexes created: 8';
    RAISE NOTICE 'Views created: 3 (v_recent_errors, v_error_summary, v_log_volume_hourly)';
    RAISE NOTICE 'Functions created: 3 (cleanup_old_logs, get_log_statistics, search_logs)';
END $$;
