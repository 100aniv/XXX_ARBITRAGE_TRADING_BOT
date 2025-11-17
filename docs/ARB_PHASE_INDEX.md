ARB_PHASE_INDEX
현재 프로젝트는 PHASE 방식으로 개발된다.

PHASE A: 기본 구조, 실행 스크립트, 데이터 모델

PHASE B: Paper Trading 라이프사이클 완료 (완료됨)

PHASE C: Multi-Symbol + FX Normalization + Risk Tiering + Order Routing
  - MODULE C1: Multi-Symbol 구조 개편 ✅ ACCEPTED
  - MODULE C2: FX Normalization & TTL Caching ✅ ACCEPTED
  - MODULE C3: Order Routing & Slippage Model ✅ ACCEPTED
  - MODULE C4: Persistence & Metrics (DB/Redis & Docker-ready) ✅ ACCEPTED

PHASE D: Live Integration & Infra Hardening
  - MODULE D1: PostgresStorage Implementation & CSV → DB Migration ✅ ACCEPTED
  - MODULE D2: Redis Cache & Health Monitoring ✅ ACCEPTED
  - MODULE D3: Docker App Integration & Monitoring Skeleton ✅ ACCEPTED
  - MODULE D4: Live API Integration & Monitoring Stack ✅ ACCEPTED
  - MODULE D5: Real Upbit/Binance API & WebSocket ✅ ACCEPTED
  - MODULE D6: Real-time WebSocket + Live Trading Loop ✅ ACCEPTED
  - MODULE D7: Arbitrage Core Signal + Execution Loop ✅ ACCEPTED
  - MODULE D8: Real Trading Stabilization, Safety & Risk Guardrails ✅ ACCEPTED
  - MODULE D9: Full Real-Trading Mode Enablement & Position Management ✅ ACCEPTED
  - MODULE D10: Live Trading Switch, Telegram Integration, Ops & Monitoring ✅ ACCEPTED
  - MODULE D11: Stability & Ops Hardening ✅ ACCEPTED
  - MODULE D12: Long-Run Stability & Performance Optimization ✅ ACCEPTED
  - MODULE D13: Secrets Refactor + Advanced Risk Modeling ✅ ACCEPTED
  - MODULE D14: 72h Long-Run Stability + Advanced Position Management ✅ ACCEPTED
  - MODULE D15: ML-based Volatility + Portfolio Optimization + Risk Quant + Dashboard (진행 중)

PHASE E: GUI/CLI Dashboard + 배포

active_phase: D
active_module: D15
