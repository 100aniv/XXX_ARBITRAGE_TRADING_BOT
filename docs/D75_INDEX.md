# D75 문서 인덱스 (Arbitrage Core v1)

**작성일:** 2025-11-22  
**Phase:** D75 (Core Infrastructure v1)  
**목적:** D75 단계에서 작성된 모든 설계/리포트 문서 통합 인덱스

---

## 📋 목차

1. [개요](#개요)
2. [문서 목록](#문서-목록)
3. [문서 간 관계도](#문서-간-관계도)
4. [참고 자료](#참고-자료)

---

## 개요

D75 Phase는 **Arbitrage Core v1 Infrastructure Layer** 구축 단계로,  
아래 6개의 설계/리포트 문서가 작성되었습니다.

**D75-1:** Async 변환 및 병목 분석 (초기 Phase, Async 전환 시도)  
**D75-2:** Core Optimization (Orderbook 캐싱 등 성능 최적화)  
**D75-3:** Rate Limit Manager + Exchange Health Monitor  
**D75-4:** ArbRoute / ArbUniverse / Cross-Exchange Sync  
**D75-5:** 4-Tier RiskGuard (Exchange/Route/Symbol/Global)  
**D75-6:** Documentation & Roadmap Consolidation (본 인덱스 포함)

---

## 문서 목록

### 1. D75_1_ASYNC_ANALYSIS.md

**경로:** `docs/D75_1_ASYNC_ANALYSIS.md`

**한 줄 요약:**  
Async 변환 시도 및 병목 분석 (Loop latency 62ms → 목표 10ms 비현실적 판단)

**주요 내용:**
- `run_once()` async def 변환
- `time.sleep()` → `asyncio.sleep()` 전환
- 병목 분석: build_snapshot (20ms), process_snapshot (30ms), execute_trades (10ms)
- 결론: Async는 동시성용이지 속도 개선용 아님, 목표 재조정 필요

**작성일:** 2025-11-22

**관계:**
- D75-2 Core Optimization의 사전 분석 단계

---

### 2. D75_2_CORE_OPTIMIZATION_REPORT.md

**경로:** `docs/D75_2_CORE_OPTIMIZATION_REPORT.md`

**한 줄 요약:**  
Core Engine 성능 최적화 (Orderbook 캐싱 100ms TTL)

**주요 내용:**
- Orderbook 캐싱 (100ms TTL)
- Balance 조회 캐싱 (200ms TTL)
- Integration benchmark 결과 (60.02s runtime, CPU 5.90%, Memory 43.91MB)
- 예상 latency 감소: -5~8ms

**작성일:** 2025-11-22

**관계:**
- D75-1 분석 결과를 기반으로 최적화 구현
- D75-3/4/5는 이 baseline 위에서 인프라 계층 추가

---

### 3. D75_2_PHASE_2_3_RESULTS.md

**경로:** `docs/D75_2_PHASE_2_3_RESULTS.md`

**한 줄 요약:**  
Core Optimization Phase 2/3 결과 (process_snapshot, execute_trades 최적화)

**주요 내용:**
- Phase 2: process_snapshot() 최적화 (Spread validation 캐싱, Position sizing table)
- Phase 3: execute_trades() 최적화 (RiskGuard batching, Order pooling)
- Integration test 결과 (60.02s runtime, 19,342 filled orders)

**작성일:** 2025-11-22

**관계:**
- D75_2_CORE_OPTIMIZATION_REPORT의 후속 Phase

---

### 4. D75_3_RATE_LIMIT_HEALTH_DESIGN.md

**경로:** `docs/D75_3_RATE_LIMIT_HEALTH_DESIGN.md`

**한 줄 요약:**  
Rate Limit Manager + Exchange Health Monitor 설계 및 구현

**주요 내용:**
- Rate Limit Manager: Token bucket / Sliding window 방식
- Upbit/Binance rate limit 프로파일 (600 req/min, 1200 req/min)
- Exchange Health Monitor: Health status (HEALTHY/DEGRADED/DOWN/FROZEN)
- 추적 지표: REST latency, error ratio, orderbook freshness
- Failover 기준 설정

**작성일:** 2025-11-22

**테스트:**
- 단위 테스트: 17 tests (rate_limiter: 8, exchange_health: 9)
- Latency: < 0.01ms

**관계:**
- D75-4 (ArbRoute health_score), D75-5 (ExchangeGuard health_status) 입력 제공

---

### 5. D75_4_ROUTE_UNIVERSE_DESIGN.md

**경로:** `docs/D75_4_ROUTE_UNIVERSE_DESIGN.md`

**한 줄 요약:**  
ArbRoute / ArbUniverse / Cross-Exchange Sync 설계 및 구현

**주요 내용:**
- ArbRoute: RouteScore 4차원 구조 (spread 40%, health 30%, fee 20%, inventory 10%)
- ArbUniverse: Universe 모드 (TOP_N, ALL_SYMBOLS, CUSTOM_LIST)
- CrossSync: Imbalance ratio, exposure risk 계산, Rebalance 판단
- MarketSpec: FX 정규화 (KRW ↔ USDT)
- FeeModel: Maker/Taker fee, VIP tier

**작성일:** 2025-11-22

**테스트:**
- 단위 테스트: 33 tests (arb_route: 11, arb_universe: 9, cross_sync: 13)
- Integration tests: 5 scenarios
- Latency: 0.12ms (5 symbols, 목표 1ms 대비 8.3배 우수)

**관계:**
- **입력:** D75-3 Health Monitor (health_score 계산)
- **출력:** D75-5 GlobalGuard (cross_exchange_imbalance, exposure_risk)

---

### 6. D75_5_4TIER_RISKGUARD_DESIGN.md

**경로:** `docs/D75_5_4TIER_RISKGUARD_DESIGN.md`

**한 줄 요약:**  
4-Tier RiskGuard (Exchange/Route/Symbol/Global) 설계 및 구현

**주요 내용:**
- Tier 1 (ExchangeGuard): Health status, daily loss, rate limit
- Tier 2 (RouteGuard): RouteScore, streak loss cooldown, abnormal spread
- Tier 3 (SymbolGuard): Exposure ratio, drawdown, volatility
- Tier 4 (GlobalGuard): Global daily loss, total exposure, cross-exchange imbalance
- Aggregation Logic: BLOCK > COOLDOWN > DEGRADE > ALLOW (strictest wins)

**작성일:** 2025-11-22

**테스트:**
- 단위 테스트: 11 tests
- Integration tests: 4 scenarios
- Latency: 0.0145ms (목표 0.1ms 대비 6.9배 우수)

**관계:**
- **입력:** D75-3 (Health status, rate_limit_remaining), D75-4 (RouteScore, imbalance, exposure_risk)
- **출력:** 최종 리스크 결정 (allow/block, cooldown, max_notional)

---

### 7. D75_ARBITRAGE_CORE_OVERVIEW.md

**경로:** `docs/D75_ARBITRAGE_CORE_OVERVIEW.md`

**한 줄 요약:**  
D75 전체 인프라 계층 통합 요약 (Core v1 Overview)

**주요 내용:**
- D75-2 ~ D75-5 구성요소 통합 요약
- 성능 특성 (latency, memory overhead)
- 테스트 커버리지 (61 unit tests, 9 integration tests)
- TO-BE 18개 아키텍처 연계 포인트
- D76 Alerting Infrastructure 준비

**작성일:** 2025-11-22

**관계:**
- D75 전체 문서의 **상위 개요 문서** (Entry point)

---

### 8. D75_INDEX.md (본 문서)

**경로:** `docs/D75_INDEX.md`

**한 줄 요약:**  
D75 설계/리포트 문서 통합 인덱스

**목적:**
- D75 단계에서 작성된 문서를 한 눈에 찾기
- 문서 간 관계 및 순서 이해

**작성일:** 2025-11-22

---

## 문서 간 관계도

```
[D75-1: Async Analysis]
    ↓ (병목 분석 → 최적화 방향 결정)
[D75-2: Core Optimization]
    ├─ [D75_2_PHASE_2_3_RESULTS.md] (Phase 2/3 후속 최적화)
    ↓ (Baseline 성능 확보)
[D75-3: Rate Limit + Health Monitor]
    ↓ (Infrastructure Layer 구축)
    ├─→ [D75-4: ArbRoute/Universe/CrossSync] (health_score 입력)
    └─→ [D75-5: 4-Tier RiskGuard] (health_status, rate_limit 입력)
         ↑
[D75-4: ArbRoute/Universe/CrossSync]
    ├─→ RouteScore → [D75-5 RouteGuard]
    └─→ Imbalance/Exposure → [D75-5 GlobalGuard]

[D75-5: 4-Tier RiskGuard]
    ↓ (최종 리스크 결정)
[D75-6: Documentation & Roadmap]
    ├─ [D75_ARBITRAGE_CORE_OVERVIEW.md] (통합 요약)
    └─ [D75_INDEX.md] (본 인덱스)
         ↓
[D76: Alerting Infrastructure]
    - D75 Core 이벤트 소스 활용
    - Rate Limit / Health / Route / CrossSync / RiskGuard 알림
```

### 데이터 흐름 요약

1. **D75-3 → D75-4:**
   - `HealthMonitor.get_status()` → `ArbRoute.evaluate(health_score)`

2. **D75-4 → D75-5:**
   - `ArbRoute.evaluate().route_score` → `RouteGuard.evaluate()`
   - `CrossSync.calculate_imbalance()` → `GlobalGuard.evaluate()`
   - `CrossSync.calculate_exposure_risk()` → `GlobalGuard.evaluate()`

3. **D75-3 → D75-5:**
   - `HealthMonitor.get_status()` → `ExchangeGuard.evaluate(health_status)`
   - `RateLimiter.get_remaining_pct()` → `ExchangeGuard.evaluate(rate_limit_remaining_pct)`

4. **D75-5 → D76:**
   - `RiskGuard.evaluate()` → `AlertManager.send_alert()` (BLOCK/COOLDOWN 시)

---

## 참고 자료

### 코드 파일 위치

**Infrastructure Layer:**
- `arbitrage/infrastructure/rate_limiter.py`
- `arbitrage/infrastructure/exchange_health.py`

**Domain Layer:**
- `arbitrage/domain/market_spec.py`
- `arbitrage/domain/fee_model.py`
- `arbitrage/domain/arb_route.py`
- `arbitrage/domain/arb_universe.py`
- `arbitrage/domain/cross_sync.py`
- `arbitrage/domain/risk_guard.py`

**테스트 파일:**
- `tests/test_rate_limiter.py` (8 tests)
- `tests/test_exchange_health.py` (9 tests)
- `tests/test_arb_route.py` (11 tests)
- `tests/test_arb_universe.py` (9 tests)
- `tests/test_cross_sync.py` (13 tests)
- `tests/test_risk_guard.py` (11 tests)

**통합 테스트 스크립트:**
- `scripts/run_d75_4_integration.py` (5 scenarios)
- `scripts/run_d75_5_riskguard_demo.py` (4 scenarios)

### 관련 Roadmap 섹션

- `D_ROADMAP.md` → "D75 – Core Optimization & Production Readiness"
  - D75-1: Async 변환 및 병목 분석
  - D75-2: Core Optimization Plan
  - D75-3: Rate Limit & Health Monitor
  - D75-4: ArbRoute / ArbUniverse & Cross-Exchange Sync
  - D75-5: 4-Tier RiskGuard 재설계
  - D75-6: 문서화 및 Roadmap 업데이트 (현재)

### TO-BE 18개 아키텍처

- D75-3 완료: #2 Rate Limit Manager, #3 Exchange Health Monitor
- D75-4 완료: #6 ArbUniverse/ArbRoute, #7 Cross-Exchange Position Sync
- D75-5 완료: #4 4-Tier RiskGuard
- **진행률: 9/18 (50%)**

---

**문서 버전:** 1.0  
**최종 업데이트:** 2025-11-22  
**작성자:** Windsurf AI
