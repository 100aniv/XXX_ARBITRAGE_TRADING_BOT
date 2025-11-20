-- D70: State Persistence & Recovery Tables
-- 상태 영속화 및 복원을 위한 스냅샷 테이블들

-- ============================================================================
-- 1. session_snapshots: 세션 메타데이터 및 스냅샷 관리
-- ============================================================================
CREATE TABLE IF NOT EXISTS session_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- 세션 메타데이터
    session_start_time TIMESTAMP NOT NULL,
    mode VARCHAR(20) NOT NULL,  -- 'paper' | 'live' | 'backtest'
    paper_campaign_id VARCHAR(50),
    config JSONB NOT NULL,
    
    -- 세션 상태
    loop_count INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL,  -- 'running' | 'stopped' | 'crashed'
    
    -- 스냅샷 타입
    snapshot_type VARCHAR(20) NOT NULL,  -- 'initial' | 'periodic' | 'on_trade' | 'on_stop'
    
    UNIQUE(session_id, created_at)
);

CREATE INDEX IF NOT EXISTS idx_session_snapshots_session ON session_snapshots(session_id);
CREATE INDEX IF NOT EXISTS idx_session_snapshots_created ON session_snapshots(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_snapshots_status ON session_snapshots(status);

COMMENT ON TABLE session_snapshots IS 'D70 Session state snapshots for recovery';
COMMENT ON COLUMN session_snapshots.session_id IS 'Unique session identifier';
COMMENT ON COLUMN session_snapshots.snapshot_type IS 'Snapshot trigger type';
COMMENT ON COLUMN session_snapshots.status IS 'Session status at snapshot time';

-- ============================================================================
-- 2. position_snapshots: 포지션 상태 스냅샷
-- ============================================================================
CREATE TABLE IF NOT EXISTS position_snapshots (
    snapshot_id INTEGER REFERENCES session_snapshots(snapshot_id) ON DELETE CASCADE,
    position_key VARCHAR(50) NOT NULL,  -- trade.open_timestamp or position_id
    
    -- 거래 정보 (JSONB)
    trade_data JSONB NOT NULL,
    order_a_data JSONB,
    order_b_data JSONB,
    
    -- Paper 모드 추가 정보
    position_open_time TIMESTAMP,
    
    -- 생성 시간
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (snapshot_id, position_key)
);

CREATE INDEX IF NOT EXISTS idx_position_snapshots_snapshot ON position_snapshots(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_position_snapshots_open_time ON position_snapshots(position_open_time);

COMMENT ON TABLE position_snapshots IS 'D70 Active positions at snapshot time';
COMMENT ON COLUMN position_snapshots.position_key IS 'Unique position identifier';
COMMENT ON COLUMN position_snapshots.trade_data IS 'ArbitrageTrade object as JSON';

-- ============================================================================
-- 3. metrics_snapshots: 메트릭 상태 스냅샷
-- ============================================================================
CREATE TABLE IF NOT EXISTS metrics_snapshots (
    snapshot_id INTEGER PRIMARY KEY REFERENCES session_snapshots(snapshot_id) ON DELETE CASCADE,
    
    -- 전체 메트릭
    total_trades_opened INTEGER NOT NULL DEFAULT 0,
    total_trades_closed INTEGER NOT NULL DEFAULT 0,
    total_winning_trades INTEGER NOT NULL DEFAULT 0,
    total_pnl_usd DECIMAL(20, 8) NOT NULL DEFAULT 0,
    max_dd_usd DECIMAL(20, 8) NOT NULL DEFAULT 0,
    
    -- 멀티심볼 메트릭 (JSONB)
    per_symbol_pnl JSONB,
    per_symbol_trades_opened JSONB,
    per_symbol_trades_closed JSONB,
    per_symbol_winning_trades JSONB,
    
    -- 포트폴리오
    portfolio_initial_capital DECIMAL(20, 8) NOT NULL DEFAULT 10000.0,
    portfolio_equity DECIMAL(20, 8) NOT NULL DEFAULT 10000.0,
    
    -- 생성 시간
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE metrics_snapshots IS 'D70 Trade metrics at snapshot time';
COMMENT ON COLUMN metrics_snapshots.per_symbol_pnl IS 'Per-symbol PnL as JSON object';

-- ============================================================================
-- 4. risk_guard_snapshots: 리스크 가드 상태 스냅샷
-- ============================================================================
CREATE TABLE IF NOT EXISTS risk_guard_snapshots (
    snapshot_id INTEGER PRIMARY KEY REFERENCES session_snapshots(snapshot_id) ON DELETE CASCADE,
    
    -- 리스크 가드 상태
    session_start_time TIMESTAMP NOT NULL,
    daily_loss_usd DECIMAL(20, 8) NOT NULL DEFAULT 0,
    
    -- 멀티심볼 리스크 (JSONB)
    per_symbol_loss JSONB,
    per_symbol_trades_rejected JSONB,
    per_symbol_trades_allowed JSONB,
    per_symbol_capital_used JSONB,
    per_symbol_position_count JSONB,
    
    -- 생성 시간
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE risk_guard_snapshots IS 'D70 RiskGuard state at snapshot time';
COMMENT ON COLUMN risk_guard_snapshots.daily_loss_usd IS 'Accumulated daily loss in USD';
COMMENT ON COLUMN risk_guard_snapshots.per_symbol_loss IS 'Per-symbol loss as JSON object';

-- ============================================================================
-- 유틸리티 뷰: 최신 스냅샷 조회
-- ============================================================================
CREATE OR REPLACE VIEW v_latest_snapshots AS
SELECT DISTINCT ON (session_id)
    snapshot_id,
    session_id,
    created_at,
    session_start_time,
    mode,
    paper_campaign_id,
    loop_count,
    status,
    snapshot_type
FROM session_snapshots
ORDER BY session_id, created_at DESC;

COMMENT ON VIEW v_latest_snapshots IS 'Latest snapshot for each session';

-- ============================================================================
-- 정리 함수: 오래된 스냅샷 삭제 (7일 이상)
-- ============================================================================
CREATE OR REPLACE FUNCTION cleanup_old_snapshots(days_to_keep INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM session_snapshots
    WHERE created_at < NOW() - (days_to_keep || ' days')::INTERVAL
      AND status IN ('stopped', 'crashed');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_snapshots IS 'Delete snapshots older than N days (only stopped/crashed sessions)';
