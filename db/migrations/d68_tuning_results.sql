-- D68: Parameter Tuning Results Table
-- 파라미터 튜닝 결과를 저장하는 테이블

CREATE TABLE IF NOT EXISTS tuning_results (
    run_id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,  -- 튜닝 세션 ID (같은 실행 그룹)
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- 파라미터 조합 (JSON)
    param_set JSONB NOT NULL,
    
    -- 성능 메트릭
    total_pnl DECIMAL(20, 8) NOT NULL,
    total_trades INTEGER NOT NULL,
    total_entries INTEGER NOT NULL,
    total_exits INTEGER NOT NULL,
    winning_trades INTEGER NOT NULL,
    losing_trades INTEGER NOT NULL,
    winrate DECIMAL(10, 4),  -- Percentage
    avg_pnl_per_trade DECIMAL(20, 8),
    max_drawdown DECIMAL(20, 8),
    sharpe_ratio DECIMAL(10, 4),
    
    -- 실행 정보
    campaign_id VARCHAR(50),  -- C1/C2/C3/M1/M2/M3/P1/P2/P3
    duration_seconds INTEGER NOT NULL,
    test_mode VARCHAR(20) NOT NULL,  -- 'paper' | 'backtest'
    symbols TEXT,  -- 심볼 리스트 (쉼표 구분)
    
    -- 추가 메타데이터
    notes TEXT,
    error_message TEXT
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_tuning_session ON tuning_results(session_id);
CREATE INDEX IF NOT EXISTS idx_tuning_created ON tuning_results(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tuning_winrate ON tuning_results(winrate DESC);
CREATE INDEX IF NOT EXISTS idx_tuning_pnl ON tuning_results(total_pnl DESC);
CREATE INDEX IF NOT EXISTS idx_tuning_campaign ON tuning_results(campaign_id);

-- GIN 인덱스 (JSONB 파라미터 검색용)
CREATE INDEX IF NOT EXISTS idx_tuning_params ON tuning_results USING GIN (param_set);

COMMENT ON TABLE tuning_results IS 'D68 Parameter Tuning Results Storage';
COMMENT ON COLUMN tuning_results.session_id IS 'Grouping identifier for related tuning runs';
COMMENT ON COLUMN tuning_results.param_set IS 'JSON object containing parameter combinations';
COMMENT ON COLUMN tuning_results.winrate IS 'Win rate percentage (0-100)';
