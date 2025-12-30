-- D205-1 Reporting Schema (PnL + Ops Metrics)
--
-- Purpose: Daily PnL and Operational metrics for V2 Paper/LIVE execution
-- SSOT: D_ROADMAP.md (D205-1)
-- Pattern: db/migrations/v2_schema.sql (idempotent, indexed, granted)
--
-- Author: arbitrage-lite V2
-- Date: 2025-12-30

-- ============================================================================
-- v2_pnl_daily: Daily PnL Aggregation
-- ============================================================================

CREATE TABLE IF NOT EXISTS v2_pnl_daily (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    
    -- PnL Metrics
    gross_pnl NUMERIC(20, 8) NOT NULL DEFAULT 0,
    net_pnl NUMERIC(20, 8) NOT NULL DEFAULT 0,
    fees NUMERIC(20, 8) NOT NULL DEFAULT 0,
    volume NUMERIC(20, 8) NOT NULL DEFAULT 0,
    
    -- Trade Counts
    trades_count INT NOT NULL DEFAULT 0,
    wins INT NOT NULL DEFAULT 0,
    losses INT NOT NULL DEFAULT 0,
    winrate_pct NUMERIC(5, 2),
    
    -- Risk Metrics
    avg_spread NUMERIC(10, 4),
    max_drawdown NUMERIC(10, 4),
    sharpe_ratio NUMERIC(10, 4),
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_v2_pnl_daily_date ON v2_pnl_daily(date DESC);

COMMENT ON TABLE v2_pnl_daily IS 'D205-1: Daily PnL aggregation (Performance metrics)';
COMMENT ON COLUMN v2_pnl_daily.gross_pnl IS 'Gross PnL before fees';
COMMENT ON COLUMN v2_pnl_daily.net_pnl IS 'Net PnL after fees';
COMMENT ON COLUMN v2_pnl_daily.fees IS 'Total fees paid';
COMMENT ON COLUMN v2_pnl_daily.volume IS 'Total trading volume (quote currency)';
COMMENT ON COLUMN v2_pnl_daily.winrate_pct IS 'Win rate percentage (wins / total trades)';
COMMENT ON COLUMN v2_pnl_daily.avg_spread IS 'Average spread captured';
COMMENT ON COLUMN v2_pnl_daily.max_drawdown IS 'Maximum drawdown (%)';
COMMENT ON COLUMN v2_pnl_daily.sharpe_ratio IS 'Sharpe ratio (if calculable)';

-- Grant permissions to arbitrage user
GRANT SELECT, INSERT, UPDATE, DELETE ON v2_pnl_daily TO arbitrage;
GRANT USAGE, SELECT ON SEQUENCE v2_pnl_daily_id_seq TO arbitrage;

-- ============================================================================
-- v2_ops_daily: Daily Operational Metrics
-- ============================================================================

CREATE TABLE IF NOT EXISTS v2_ops_daily (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    
    -- Order/Fill Counts
    orders_count INT NOT NULL DEFAULT 0,
    fills_count INT NOT NULL DEFAULT 0,
    rejects_count INT NOT NULL DEFAULT 0,
    fill_rate_pct NUMERIC(5, 2),
    
    -- Execution Quality (TCA)
    avg_slippage_bps NUMERIC(10, 4),
    latency_p50_ms NUMERIC(10, 2),
    latency_p95_ms NUMERIC(10, 2),
    
    -- Ops/Risk
    api_errors INT NOT NULL DEFAULT 0,
    rate_limit_hits INT NOT NULL DEFAULT 0,
    reconnects INT NOT NULL DEFAULT 0,
    
    -- System Resources (optional, for LIVE)
    avg_cpu_pct NUMERIC(5, 2),
    avg_memory_mb NUMERIC(10, 2),
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_v2_ops_daily_date ON v2_ops_daily(date DESC);

COMMENT ON TABLE v2_ops_daily IS 'D205-1: Daily operational metrics (Execution Quality + Ops/Risk)';
COMMENT ON COLUMN v2_ops_daily.orders_count IS 'Total orders placed';
COMMENT ON COLUMN v2_ops_daily.fills_count IS 'Total fills received';
COMMENT ON COLUMN v2_ops_daily.rejects_count IS 'Total order rejections';
COMMENT ON COLUMN v2_ops_daily.fill_rate_pct IS 'Fill rate percentage (fills / orders)';
COMMENT ON COLUMN v2_ops_daily.avg_slippage_bps IS 'Average slippage in basis points';
COMMENT ON COLUMN v2_ops_daily.latency_p50_ms IS 'P50 latency in milliseconds';
COMMENT ON COLUMN v2_ops_daily.latency_p95_ms IS 'P95 latency in milliseconds';
COMMENT ON COLUMN v2_ops_daily.api_errors IS 'Total API errors';
COMMENT ON COLUMN v2_ops_daily.rate_limit_hits IS 'Total rate limit hits (429 errors)';
COMMENT ON COLUMN v2_ops_daily.reconnects IS 'Total WebSocket reconnects';

-- Grant permissions to arbitrage user
GRANT SELECT, INSERT, UPDATE, DELETE ON v2_ops_daily TO arbitrage;
GRANT USAGE, SELECT ON SEQUENCE v2_ops_daily_id_seq TO arbitrage;

-- ============================================================================
-- End of D205-1 Reporting Schema
-- ============================================================================
