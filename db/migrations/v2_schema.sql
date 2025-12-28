-- ============================================================================
-- V2 Database Schema SSOT
-- ============================================================================
-- 목적: V2 Paper/LIVE 실행 시 주문/체결/거래 기록
-- 원칙: V1 테이블 직접 수정 금지, V2 전용 스키마 사용
-- 실행: psql -U arbitrage -d arbitrage -f db/migrations/v2_schema.sql
-- Rollback: psql -U arbitrage -d arbitrage -f db/migrations/v2_schema_rollback.sql

-- ============================================================================
-- 1. v2_orders (주문 기록)
-- ============================================================================

CREATE TABLE IF NOT EXISTS v2_orders (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,                   -- Paper/LIVE 실행 ID
    order_id VARCHAR(64) NOT NULL UNIQUE,          -- 주문 ID (거래소 반환값)
    timestamp TIMESTAMPTZ NOT NULL,                -- 주문 생성 시각
    exchange VARCHAR(32) NOT NULL,                 -- upbit, binance 등
    symbol VARCHAR(32) NOT NULL,                   -- BTC/KRW, BTC/USDT 등
    side VARCHAR(8) NOT NULL,                      -- BUY, SELL
    order_type VARCHAR(16) NOT NULL,               -- MARKET, LIMIT
    quantity NUMERIC(20, 8),                       -- 주문 수량 (base asset)
    price NUMERIC(20, 8),                          -- 주문 가격 (quote asset)
    status VARCHAR(16) NOT NULL,                   -- pending, filled, canceled, failed
    
    -- 메타데이터
    route_id VARCHAR(64),                          -- 차익거래 route ID
    strategy_id VARCHAR(32),                       -- 전략 ID (v2_engine 등)
    
    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_v2_orders_run_id ON v2_orders(run_id);
CREATE INDEX IF NOT EXISTS idx_v2_orders_timestamp ON v2_orders(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_v2_orders_exchange_symbol ON v2_orders(exchange, symbol);
CREATE INDEX IF NOT EXISTS idx_v2_orders_status ON v2_orders(status);
CREATE INDEX IF NOT EXISTS idx_v2_orders_route_id ON v2_orders(route_id);

-- 주석
COMMENT ON TABLE v2_orders IS 'V2 주문 기록 (Paper/LIVE 모두 기록)';
COMMENT ON COLUMN v2_orders.run_id IS '실행 세션 ID (d204_2_YYYYMMDD_HHMM 형식)';
COMMENT ON COLUMN v2_orders.order_id IS '거래소 반환 주문 ID (고유)';
COMMENT ON COLUMN v2_orders.quantity IS 'MARKET BUY: quote_amount(KRW), MARKET SELL: base_qty(BTC)';
COMMENT ON COLUMN v2_orders.status IS 'pending(대기), filled(체결), canceled(취소), failed(실패)';

-- ============================================================================
-- 2. v2_fills (체결 기록)
-- ============================================================================

CREATE TABLE IF NOT EXISTS v2_fills (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    order_id VARCHAR(64) NOT NULL,                 -- v2_orders.order_id 참조
    fill_id VARCHAR(64) NOT NULL UNIQUE,           -- 체결 ID (거래소 반환값)
    timestamp TIMESTAMPTZ NOT NULL,                -- 체결 시각
    exchange VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,
    
    -- 체결 세부사항
    filled_quantity NUMERIC(20, 8) NOT NULL,       -- 체결 수량
    filled_price NUMERIC(20, 8) NOT NULL,          -- 체결 가격
    fee NUMERIC(20, 8) NOT NULL,                   -- 수수료
    fee_currency VARCHAR(16) NOT NULL,             -- 수수료 통화 (KRW, USDT, BTC 등)
    
    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_v2_fills_run_id ON v2_fills(run_id);
CREATE INDEX IF NOT EXISTS idx_v2_fills_order_id ON v2_fills(order_id);
CREATE INDEX IF NOT EXISTS idx_v2_fills_timestamp ON v2_fills(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_v2_fills_exchange_symbol ON v2_fills(exchange, symbol);

-- 외래 키 (optional, 성능상 제거 가능)
-- ALTER TABLE v2_fills ADD CONSTRAINT fk_v2_fills_order_id 
--     FOREIGN KEY (order_id) REFERENCES v2_orders(order_id) ON DELETE CASCADE;

-- 주석
COMMENT ON TABLE v2_fills IS 'V2 체결 기록 (1개 주문 → N개 체결 가능)';
COMMENT ON COLUMN v2_fills.filled_quantity IS '체결된 수량 (부분 체결 가능)';
COMMENT ON COLUMN v2_fills.fee IS '체결 수수료 (taker fee 기준)';

-- ============================================================================
-- 3. v2_trades (차익거래 기록)
-- ============================================================================

CREATE TABLE IF NOT EXISTS v2_trades (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    trade_id VARCHAR(64) NOT NULL UNIQUE,          -- 차익거래 ID (자체 생성)
    timestamp TIMESTAMPTZ NOT NULL,                -- 거래 시작 시각
    
    -- Entry (진입)
    entry_exchange VARCHAR(32) NOT NULL,           -- 진입 거래소
    entry_symbol VARCHAR(32) NOT NULL,             -- 진입 심볼
    entry_side VARCHAR(8) NOT NULL,                -- BUY or SELL
    entry_order_id VARCHAR(64) NOT NULL,           -- 진입 주문 ID
    entry_quantity NUMERIC(20, 8) NOT NULL,        -- 진입 수량
    entry_price NUMERIC(20, 8) NOT NULL,           -- 진입 평균 가격
    entry_timestamp TIMESTAMPTZ NOT NULL,          -- 진입 체결 시각
    
    -- Exit (청산)
    exit_exchange VARCHAR(32),                     -- 청산 거래소
    exit_symbol VARCHAR(32),                       -- 청산 심볼
    exit_side VARCHAR(8),                          -- BUY or SELL
    exit_order_id VARCHAR(64),                     -- 청산 주문 ID
    exit_quantity NUMERIC(20, 8),                  -- 청산 수량
    exit_price NUMERIC(20, 8),                     -- 청산 평균 가격
    exit_timestamp TIMESTAMPTZ,                    -- 청산 체결 시각
    
    -- PnL (손익)
    realized_pnl NUMERIC(20, 8),                   -- 실현 손익 (USD 기준)
    unrealized_pnl NUMERIC(20, 8),                 -- 미실현 손익
    total_fee NUMERIC(20, 8),                      -- 총 수수료
    
    -- 상태
    status VARCHAR(16) NOT NULL,                   -- open, closed, failed
    
    -- 메타데이터
    route_id VARCHAR(64),                          -- 차익거래 route
    strategy_id VARCHAR(32),                       -- 전략 ID
    
    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_v2_trades_run_id ON v2_trades(run_id);
CREATE INDEX IF NOT EXISTS idx_v2_trades_timestamp ON v2_trades(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_v2_trades_status ON v2_trades(status);
CREATE INDEX IF NOT EXISTS idx_v2_trades_route_id ON v2_trades(route_id);
CREATE INDEX IF NOT EXISTS idx_v2_trades_entry_exit ON v2_trades(entry_exchange, exit_exchange);

-- 주석
COMMENT ON TABLE v2_trades IS 'V2 차익거래 기록 (Entry → Exit 페어)';
COMMENT ON COLUMN v2_trades.trade_id IS '차익거래 고유 ID (format: trade_{run_id}_{seq})';
COMMENT ON COLUMN v2_trades.status IS 'open(진입만), closed(청산 완료), failed(실패)';
COMMENT ON COLUMN v2_trades.realized_pnl IS '실현 손익 = (exit_price - entry_price) * quantity - fee';

-- ============================================================================
-- 4. v2_ledger (원장 기록, 집계용)
-- ============================================================================

CREATE TABLE IF NOT EXISTS v2_ledger (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- 거래 요약
    exchange VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,                      -- BUY, SELL
    
    -- 금액
    quantity NUMERIC(20, 8) NOT NULL,              -- 거래 수량
    price NUMERIC(20, 8) NOT NULL,                 -- 거래 가격
    value NUMERIC(20, 8) NOT NULL,                 -- 거래 금액 (quantity * price)
    fee NUMERIC(20, 8) NOT NULL,                   -- 수수료
    
    -- 참조
    order_id VARCHAR(64),                          -- v2_orders.order_id
    trade_id VARCHAR(64),                          -- v2_trades.trade_id
    
    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_v2_ledger_run_id ON v2_ledger(run_id);
CREATE INDEX IF NOT EXISTS idx_v2_ledger_timestamp ON v2_ledger(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_v2_ledger_exchange_symbol ON v2_ledger(exchange, symbol);

-- 주석
COMMENT ON TABLE v2_ledger IS 'V2 원장 기록 (PnL 집계용, 단순화된 뷰)';
COMMENT ON COLUMN v2_ledger.value IS '거래 금액 = quantity * price';

-- ============================================================================
-- 5. v2_pnl_daily (일별 손익 집계)
-- ============================================================================

CREATE TABLE IF NOT EXISTS v2_pnl_daily (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,                     -- 집계 날짜
    
    -- 손익
    total_pnl NUMERIC(20, 8) NOT NULL DEFAULT 0,   -- 총 손익
    realized_pnl NUMERIC(20, 8) NOT NULL DEFAULT 0,-- 실현 손익
    unrealized_pnl NUMERIC(20, 8) NOT NULL DEFAULT 0, -- 미실현 손익
    
    -- 거래 통계
    num_trades INT NOT NULL DEFAULT 0,             -- 거래 수
    num_wins INT NOT NULL DEFAULT 0,               -- 수익 거래 수
    num_losses INT NOT NULL DEFAULT 0,             -- 손실 거래 수
    winrate_pct NUMERIC(5, 2),                     -- 승률 (%)
    
    -- 리스크 지표
    max_drawdown_pct NUMERIC(5, 2),                -- 최대 낙폭 (%)
    sharpe_ratio NUMERIC(10, 4),                   -- 샤프 비율
    
    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_v2_pnl_daily_date ON v2_pnl_daily(date DESC);

-- 주석
COMMENT ON TABLE v2_pnl_daily IS 'V2 일별 PnL 집계 (리포팅용)';
COMMENT ON COLUMN v2_pnl_daily.winrate_pct IS '승률 = (num_wins / num_trades) * 100';
COMMENT ON COLUMN v2_pnl_daily.sharpe_ratio IS '샤프 비율 (annualized)';

-- ============================================================================
-- 뷰 (Views)
-- ============================================================================

-- 최근 거래 요약 뷰
CREATE OR REPLACE VIEW v2_recent_trades AS
SELECT 
    t.trade_id,
    t.timestamp,
    t.entry_exchange || ' → ' || t.exit_exchange AS route,
    t.entry_symbol,
    t.realized_pnl,
    t.status,
    t.created_at
FROM v2_trades t
ORDER BY t.timestamp DESC
LIMIT 100;

COMMENT ON VIEW v2_recent_trades IS '최근 100개 거래 요약';

-- ============================================================================
-- 권한 (Permissions)
-- ============================================================================

-- arbitrage 사용자에게 권한 부여
GRANT SELECT, INSERT, UPDATE, DELETE ON v2_orders TO arbitrage;
GRANT SELECT, INSERT, UPDATE, DELETE ON v2_fills TO arbitrage;
GRANT SELECT, INSERT, UPDATE, DELETE ON v2_trades TO arbitrage;
GRANT SELECT, INSERT, UPDATE, DELETE ON v2_ledger TO arbitrage;
GRANT SELECT, INSERT, UPDATE, DELETE ON v2_pnl_daily TO arbitrage;
GRANT SELECT ON v2_recent_trades TO arbitrage;

-- Sequence 권한
GRANT USAGE, SELECT ON SEQUENCE v2_orders_id_seq TO arbitrage;
GRANT USAGE, SELECT ON SEQUENCE v2_fills_id_seq TO arbitrage;
GRANT USAGE, SELECT ON SEQUENCE v2_trades_id_seq TO arbitrage;
GRANT USAGE, SELECT ON SEQUENCE v2_ledger_id_seq TO arbitrage;
GRANT USAGE, SELECT ON SEQUENCE v2_pnl_daily_id_seq TO arbitrage;

-- ============================================================================
-- 완료
-- ============================================================================

\echo 'V2 Schema 생성 완료'
\echo '테이블: v2_orders, v2_fills, v2_trades, v2_ledger, v2_pnl_daily'
\echo '뷰: v2_recent_trades'
