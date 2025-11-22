# D75-5: 4-Tier RiskGuard 설계 문서

**작성일:** 2025-11-22  
**작성자:** Windsurf AI  
**상태:** ✅ COMPLETED  
**Phase:** D75-5 (Domain Layer - RiskGuard)

---

## 📋 목차

1. [개요](#개요)
2. [요구사항](#요구사항)
3. [아키텍처](#아키텍처)
4. [Data Structures & Interfaces](#data-structures--interfaces)
5. [Tier별 Decision Logic](#tier별-decision-logic)
6. [Aggregation Logic](#aggregation-logic)
7. [Example Scenarios](#example-scenarios)
8. [Performance & Latency](#performance--latency)
9. [Acceptance Criteria & Test Plan](#acceptance-criteria--test-plan)
10. [향후 확장](#향후-확장)

---

## 개요

### 목적

D75-5는 **4-Tier RiskGuard** 를 구축하여 Arbitrage 전용 리스크 관리 계층을 완성합니다.  
Multi-exchange, Multi-symbol, Cross-exchange position 관리를 위한 **4개 독립적인 Risk Tier**를 구현하고,  
각 Tier의 결정을 **가장 보수적인 방향으로 aggregation** 하여 최종 결정을 내립니다.

### 설계 원칙

- ✅ **Core Engine 불변**: 기존 엔진 로직 0 line 수정
- ✅ **Plug-in 방식**: Domain Layer에 독립적으로 구축
- ✅ **Latency 제약**: 평가 함수 < 0.1ms (실측 0.0145ms)
- ✅ **D75-3/D75-4 연계**: HealthMonitor, ArbRoute, CrossSync 활용
- ✅ **확장 가능성**: Multi-exchange, Multi-symbol 확장 대비

---

## 요구사항

### Tier별 요구사항

#### Tier 1: ExchangeGuard

**목적:** 거래소 레벨 리스크 관리

**입력:**
- Exchange ID (UPBIT, BINANCE, ...)
- Health Status (D75-3 HealthMonitor)
- Rate Limit 사용량 (D75-3 RateLimiter)
- 일일 손실, Open trade 수

**규칙:**
- Health Status:
  - `DOWN` or `FROZEN` → **BLOCK**
  - `DEGRADED` → **DEGRADE** (거래 금액 축소)
- Rate Limit:
  - 잔여 < 20% → **DEGRADE** or **BLOCK**
- Daily Loss:
  - 일일 손실 > 한도 → **BLOCK**

#### Tier 2: RouteGuard

**목적:** Route(Exchange A ↔ Exchange B ↔ Symbol) 레벨 리스크 관리

**입력:**
- Route key `(exchange_a, exchange_b, symbol_a, symbol_b)`
- RouteScore (D75-4 ArbRoute)
- 거래 이력 (연속 손실, PnL)
- Spread 수준

**규칙:**
- RouteScore:
  - Score < 50 → **BLOCK**
- Streak Loss:
  - 연속 손실 ≥ 3회 → **BLOCK** + **COOLDOWN** (5분)
- Abnormal Spread:
  - Spread > 500 bps (비정상) → **DEGRADE** (의심스러운 기회)
- Inventory Penalty:
  - Inventory penalty < 50 → **DEGRADE**

#### Tier 3: SymbolGuard

**목적:** Symbol(자산) 레벨 리스크 관리

**입력:**
- Symbol (BTC, ETH, ...)
- Total exposure (USD)
- Drawdown
- Volatility proxy

**규칙:**
- Exposure:
  - Symbol exposure / Portfolio > 50% → **DEGRADE**
- Drawdown:
  - Intraday DD > 20% → **BLOCK**
- Volatility:
  - 고변동성 (> 10%) → **DEGRADE**

#### Tier 4: GlobalGuard

**목적:** Portfolio 전체 레벨 리스크 관리

**입력:**
- Total portfolio value
- Global daily loss
- Cross-exchange imbalance (D75-4 CrossSync)
- Cross-exchange exposure risk

**규칙:**
- Global Daily Loss:
  - 일일 손실 > $50k → **BLOCK** (신규 진입 금지)
- Total Exposure:
  - 총 exposure > $100k → **BLOCK**
- Cross-Exchange Imbalance:
  - `|imbalance| > 50%` → **BLOCK** (Rebalance 우선)
- Exposure Risk:
  - Risk > 80% → **DEGRADE**

---

## 아키텍처

### 전체 구조도

```
┌─────────────────────────────────────────────────────────────┐
│                    FourTierRiskGuard                        │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ ExchangeState│  │  RouteState  │  │ SymbolState  │      │
│  │  - Health    │  │  - Score     │  │  - Exposure  │      │
│  │  - RateLimit │  │  - Trades    │  │  - DD        │      │
│  │  - DailyLoss │  │  - Spread    │  │  - Volatility│      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │              │
│         ├─────────────────┴─────────────────┤              │
│         │                                   │              │
│  ┌──────▼───────┐  ┌──────────────┐  ┌─────▼─────────┐    │
│  │ Tier 1:      │  │ Tier 2:      │  │ Tier 3:       │    │
│  │ Exchange     │  │ Route        │  │ Symbol        │    │
│  │ Guard        │  │ Guard        │  │ Guard         │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘    │
│         │                 │                 │              │
│         │         ┌───────▼────────┐        │              │
│         │         │  GlobalState   │        │              │
│         │         │  - Portfolio   │        │              │
│         │         │  - Imbalance   │        │              │
│         │         │  - ExposureRisk│        │              │
│         │         └───────┬────────┘        │              │
│         │                 │                 │              │
│         │         ┌───────▼────────┐        │              │
│         │         │ Tier 4:        │        │              │
│         │         │ Global         │        │              │
│         │         │ Guard          │        │              │
│         │         └───────┬────────┘        │              │
│         │                 │                 │              │
│         └────────┬────────┴────────┬────────┘              │
│                  │                 │                       │
│           ┌──────▼─────────────────▼──────┐                │
│           │   Aggregation Logic            │                │
│           │   (Strictest Decision Wins)    │                │
│           └──────┬─────────────────────────┘                │
│                  │                                          │
│           ┌──────▼─────────────────────────┐                │
│           │   RiskGuardDecision            │                │
│           │   - allow: bool                │                │
│           │   - degraded: bool             │                │
│           │   - cooldown_seconds: float    │                │
│           │   - max_notional: float?       │                │
│           │   - tier_decisions: dict       │                │
│           └────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

### 데이터 흐름

```
Input States (Exchange, Route, Symbol, Global)
    ↓
Tier 1: ExchangeGuard → TierDecision (ALLOW/BLOCK/DEGRADE)
Tier 2: RouteGuard    → TierDecision (ALLOW/BLOCK/DEGRADE/COOLDOWN)
Tier 3: SymbolGuard   → TierDecision (ALLOW/BLOCK/DEGRADE)
Tier 4: GlobalGuard   → TierDecision (ALLOW/BLOCK/DEGRADE)
    ↓
Aggregation (Strictest Decision Wins)
    ↓
RiskGuardDecision (Final Decision)
```

---

## Data Structures & Interfaces

### Core Enums

```python
class GuardTier(Enum):
    EXCHANGE = "exchange"
    ROUTE = "route"
    SYMBOL = "symbol"
    GLOBAL = "global"

class GuardDecisionType(Enum):
    ALLOW = "allow"          # 허용
    BLOCK = "block"          # 차단
    DEGRADE = "degrade"      # 축소 허용
    COOLDOWN_ONLY = "cooldown_only"  # Cooldown 중

class GuardReasonCode(Enum):
    # Exchange reasons
    EXCHANGE_HEALTH_DOWN = "exchange_health_down"
    EXCHANGE_HEALTH_FROZEN = "exchange_health_frozen"
    EXCHANGE_HEALTH_DEGRADED = "exchange_health_degraded"
    EXCHANGE_DAILY_LOSS_LIMIT = "exchange_daily_loss_limit"
    EXCHANGE_RATE_LIMIT_EXHAUSTED = "exchange_rate_limit_exhausted"
    
    # Route reasons
    ROUTE_SCORE_LOW = "route_score_low"
    ROUTE_STREAK_LOSS = "route_streak_loss"
    ROUTE_SPREAD_ABNORMAL = "route_spread_abnormal"
    ROUTE_INVENTORY_PENALTY = "route_inventory_penalty"
    
    # Symbol reasons
    SYMBOL_EXPOSURE_HIGH = "symbol_exposure_high"
    SYMBOL_DD_HIGH = "symbol_dd_high"
    SYMBOL_VOLATILITY_HIGH = "symbol_volatility_high"
    
    # Global reasons
    GLOBAL_DD_LIMIT = "global_dd_limit"
    GLOBAL_EXPOSURE_LIMIT = "global_exposure_limit"
    GLOBAL_IMBALANCE_HIGH = "global_imbalance_high"
    
    OK = "ok"
```

### Decision Structures

```python
@dataclass
class TierDecision:
    """각 Tier의 결정"""
    tier: GuardTier
    decision: GuardDecisionType
    max_notional: Optional[float] = None
    cooldown_seconds: float = 0.0
    reasons: List[GuardReasonCode] = field(default_factory=list)
    details: str = ""

@dataclass
class RiskGuardDecision:
    """4-Tier RiskGuard 최종 결정"""
    allow: bool
    degraded: bool
    cooldown_seconds: float
    max_notional: Optional[float]
    tier_decisions: Dict[GuardTier, TierDecision] = field(default_factory=dict)
    timestamp: float = 0.0
    
    def get_reason_summary(self) -> str:
        """전체 이유 요약"""
        ...
```

### State Structures

```python
@dataclass
class ExchangeState:
    """거래소 레벨 상태"""
    exchange_name: str
    health_status: ExchangeHealthStatus
    health_metrics: HealthMetrics
    rate_limit_remaining_pct: float
    daily_loss_usd: float
    open_trade_count: int = 0

@dataclass
class RouteState:
    """Route 레벨 상태"""
    symbol_a: str
    symbol_b: str
    route_score: Optional[RouteScore] = None
    gross_spread_bps: float = 0.0
    recent_trades: List[float] = field(default_factory=list)
    last_trade_timestamp: float = 0.0

@dataclass
class SymbolState:
    """Symbol 레벨 상태"""
    symbol: str
    total_exposure_usd: float
    total_notional_usd: float
    unrealized_pnl_usd: float
    intraday_pnl_usd: float
    intraday_peak_usd: float
    volatility_proxy: float = 0.0

@dataclass
class GlobalState:
    """Global 레벨 상태"""
    total_portfolio_value_usd: float
    total_exposure_usd: float
    total_margin_used_usd: float
    global_daily_loss_usd: float
    global_cumulative_loss_usd: float
    cross_exchange_imbalance_ratio: float
    cross_exchange_exposure_risk: float
```

---

## Tier별 Decision Logic

### Tier 1: ExchangeGuard

**의사결정 순서:**
1. Health Status 확인
   - `DOWN` or `FROZEN` → **BLOCK**
   - `DEGRADED` → **DEGRADE**
2. Rate Limit 확인
   - 잔여 < 20% → **DEGRADE**
3. Daily Loss 확인
   - 손실 > 한도 → **BLOCK**

**코드 로직:**
```python
def _evaluate_exchange(self, exchange_states):
    for state in exchange_states.values():
        if state.health_status in (DOWN, FROZEN):
            decision_type = BLOCK
        elif state.health_status == DEGRADED:
            decision_type = DEGRADE
        
        if state.daily_loss_usd > config.max_daily_loss_usd:
            decision_type = BLOCK
        
        if state.rate_limit_remaining_pct < config.rate_limit_buffer_pct:
            decision_type = DEGRADE
    
    return TierDecision(tier=EXCHANGE, decision=decision_type, ...)
```

### Tier 2: RouteGuard

**의사결정 순서:**
1. Cooldown 확인
   - Cooldown 중 → **COOLDOWN_ONLY**
2. RouteScore 확인
   - Score < 50 → **BLOCK**
3. Streak Loss 확인
   - 연속 손실 ≥ 3회 → **BLOCK** + **COOLDOWN** (5분)
4. Abnormal Spread 확인
   - Spread > 500 bps → **DEGRADE**
5. Inventory Penalty 확인
   - Penalty < 50 → **DEGRADE**

**Cooldown 관리:**
- Route별 cooldown 추적: `Dict[(symbol_a, symbol_b), cooldown_until]`
- Streak loss 발생 시 cooldown 설정
- Cooldown 만료 시 자동 해제

### Tier 3: SymbolGuard

**의사결정 순서:**
1. Exposure Ratio 확인
   - Exposure / Portfolio > 50% → **DEGRADE**
2. Drawdown 확인
   - DD > 20% → **BLOCK**
3. Volatility 확인
   - Volatility > 10% → **DEGRADE**

**코드 로직:**
```python
def _evaluate_symbol(self, symbol_states, total_portfolio_value):
    for state in symbol_states.values():
        exposure_ratio = state.total_exposure_usd / total_portfolio_value
        if exposure_ratio > config.max_exposure_ratio:
            decision_type = DEGRADE
        
        dd_ratio = state.get_drawdown_ratio()
        if dd_ratio > config.max_dd_ratio:
            decision_type = BLOCK
        
        if state.volatility_proxy > config.high_volatility_threshold:
            decision_type = DEGRADE
    
    return TierDecision(tier=SYMBOL, decision=decision_type, ...)
```

### Tier 4: GlobalGuard

**의사결정 순서:**
1. Global Daily Loss 확인
   - 손실 > $50k → **BLOCK**
2. Total Exposure 확인
   - Exposure > $100k → **BLOCK**
3. Cross-Exchange Imbalance 확인
   - `|imbalance| > 50%` → **BLOCK** (Rebalance 우선)
4. Exposure Risk 확인
   - Risk > 80% → **DEGRADE**

**CrossSync 연계:**
```python
def _evaluate_global(self, global_state):
    if global_state.global_daily_loss_usd > config.max_global_daily_loss_usd:
        decision_type = BLOCK
    
    if global_state.total_exposure_usd > config.max_total_exposure_usd:
        decision_type = BLOCK
    
    if abs(global_state.cross_exchange_imbalance_ratio) > config.max_imbalance_ratio:
        decision_type = BLOCK  # Rebalance 우선
    
    if global_state.cross_exchange_exposure_risk > config.max_exposure_risk:
        decision_type = DEGRADE
    
    return TierDecision(tier=GLOBAL, decision=decision_type, ...)
```

---

## Aggregation Logic

### 우선순위 규칙

**Decision 우선순위 (엄격도 순):**
1. **BLOCK** (차단)
2. **COOLDOWN_ONLY** (Cooldown 중)
3. **DEGRADE** (축소 허용)
4. **ALLOW** (허용)

**Aggregation 규칙:**
- 가장 엄격한 Decision 선택
- Cooldown: 최대값 선택
- Max Notional: 최소값 선택 (DEGRADE 시)

### 코드 로직

```python
def _aggregate_decisions(self, tier_decisions):
    # Find strictest decision
    strictest_decision = ALLOW
    for tier_dec in tier_decisions.values():
        if priority[tier_dec.decision] > priority[strictest_decision]:
            strictest_decision = tier_dec.decision
    
    # Aggregate cooldown (max)
    max_cooldown = max(tier_dec.cooldown_seconds for tier_dec in tier_decisions.values())
    
    # Aggregate max_notional (min, if DEGRADE)
    max_notional = None
    if strictest_decision == DEGRADE:
        notionals = [tier_dec.max_notional for tier_dec in tier_decisions.values() if tier_dec.max_notional]
        if notionals:
            max_notional = min(notionals)
    
    # Final decision
    allow = (strictest_decision == ALLOW)
    degraded = (strictest_decision == DEGRADE)
    
    return RiskGuardDecision(
        allow=allow,
        degraded=degraded,
        cooldown_seconds=max_cooldown,
        max_notional=max_notional,
        tier_decisions=tier_decisions,
    )
```

---

## Example Scenarios

### Scenario 1: All Healthy → ALLOW

**상태:**
- Exchange: HEALTHY
- Route: Score = 80
- Symbol: Exposure = 30%
- Global: Daily loss = $150

**결과:**
- All Tiers → **ALLOW**
- Final: `allow=True, degraded=False`

### Scenario 2: Route Streak Loss → COOLDOWN

**상태:**
- Exchange: HEALTHY
- Route: 3회 연속 손실
- Symbol: OK
- Global: OK

**결과:**
- Route → **BLOCK** + **COOLDOWN** (300s)
- Final: `allow=False, cooldown_seconds=300`

### Scenario 3: Symbol Exposure High → DEGRADE

**상태:**
- Exchange: HEALTHY
- Route: OK
- Symbol: Exposure = 60% (> 50%)
- Global: OK

**결과:**
- Symbol → **DEGRADE**
- Final: `allow=False, degraded=True`

### Scenario 4: Global Daily Loss → BLOCK

**상태:**
- Exchange: HEALTHY
- Route: OK
- Symbol: OK
- Global: Daily loss = $55k (> $50k)

**결과:**
- Global → **BLOCK**
- Final: `allow=False, degraded=False`

### Scenario 5: Multiple Tiers (Aggregation)

**상태:**
- Exchange: **DEGRADED** → DEGRADE
- Route: **Low Score** → BLOCK
- Symbol: OK
- Global: OK

**결과:**
- Strictest = **BLOCK** (Route)
- Final: `allow=False, degraded=False`

---

## Performance & Latency

### Latency 측정 결과 (1000 iterations)

| Metric | Value |
|--------|-------|
| **Avg** | **0.0145 ms** |
| **Min** | 0.0085 ms |
| **Max** | 0.1015 ms |
| **P99** | 0.0242 ms |

**목표:**
- Target: < 0.1 ms
- Actual: 0.0145 ms
- **6.9배 우수** ✅

### Memory Overhead

- `FourTierRiskGuard`: ~500 bytes
- `RiskGuardDecision`: ~200 bytes/instance
- `TierDecision`: ~50 bytes/tier
- **Total: < 1 KB** ✅

### CPU Overhead

- 평가 함수 1회 호출: ~0.015 ms
- 초당 최대 호출 가능: ~66,000회
- **Loop latency 62ms에 미치는 영향: 무시 가능** ✅

---

## Acceptance Criteria & Test Plan

### Acceptance Criteria

| 항목 | 기준 | 실제값 | 결과 |
|------|------|--------|------|
| **기능/설계** | 4-Tier RiskGuard 구현 | ✅ | PASS |
| **엔진 격리** | Core engine 변경 0 lines | ✅ 0 lines | PASS |
| **Unit Tests** | 100% PASS | 11/11 (100%) | PASS |
| **Integration Tests** | 모든 시나리오 PASS | 4/4 (100%) | PASS |
| **Latency** | < 0.1 ms | 0.0145 ms | PASS (6.9배 우수) |
| **문서** | 설계 문서 완성 | ✅ | PASS |
| **Git** | Commit 완료 | ✅ | PASS |

**종합:** ✅ **7/7 PASS (100%)**

### Test Plan

#### Unit Tests (11 tests)

**ExchangeGuard (3 tests):**
- `test_exchange_health_down_blocks_trades`
- `test_exchange_daily_loss_limit_blocks_trades`
- `test_exchange_degraded_status_degrades_notional`

**RouteGuard (2 tests):**
- `test_route_streak_loss_triggers_cooldown`
- `test_route_score_low_blocks_trade`

**SymbolGuard (2 tests):**
- `test_symbol_exposure_high_degrades_notional`
- `test_symbol_dd_high_blocks_trade`

**GlobalGuard (2 tests):**
- `test_global_daily_loss_triggers_global_block`
- `test_global_imbalance_triggers_rebalance_only_mode`

**Aggregation (2 tests):**
- `test_four_tier_aggregation_picks_strictest_decision`
- `test_risk_guard_decision_serialization`

**결과:** ✅ **11/11 PASS (100%)**

#### Integration Tests (4 scenarios)

**Scenario 1:** All Healthy → ALLOW  
**Scenario 2:** Route Streak Loss → COOLDOWN  
**Scenario 3:** Symbol Exposure High → DEGRADE  
**Scenario 4:** Global Daily Loss → BLOCK

**결과:** ✅ **4/4 PASS (100%)**

#### Latency Test

**측정:** 1000 iterations  
**결과:** Avg 0.0145 ms (< 0.1 ms 목표) ✅

---

## 향후 확장

### D75-6: Multi-Exchange 확장

- 현재: 2개 거래소 (Upbit, Binance)
- 확장: 7+ 거래소 (Bybit, OKX, Bitget, Bithumb, Coinone)
- ExchangeGuard: Multi-exchange aggregation
- RouteGuard: Triangular arbitrage route 지원

### D76: WebSocket Integration

- HealthMonitor: WebSocket latency 추적
- ExchangeGuard: WebSocket health status 반영
- Real-time rate limit tracking

### D77~D78: Advanced Risk Models

- **Spread-based Risk Model** (Tier 2 확장)
  - Spread 변동성 분석
  - Execution probability 계산
- **Volatility-based Risk Model** (Tier 3 확장)
  - EWMA volatility 추정
  - Dynamic exposure limit
- **Correlation-based Risk Model** (Tier 4 확장)
  - Cross-exchange correlation 분석
  - Portfolio-level diversification

### D79~D80: Machine Learning Risk

- **Dynamic Threshold Learning**
  - Historical data 기반 threshold 최적화
  - Adaptive risk parameters
- **Anomaly Detection**
  - Abnormal spread detection (ML 기반)
  - Route health prediction

---

## 결론

### 달성 항목 ✅

- ✅ **4-Tier RiskGuard 구현**: Exchange/Route/Symbol/Global
- ✅ **Domain Layer 확장**: 650+ lines (risk_guard.py)
- ✅ **11개 Unit Tests**: 100% PASS
- ✅ **4개 Integration Tests**: 100% PASS
- ✅ **Latency 목표**: 0.0145ms (목표 0.1ms 대비 6.9배 우수)
- ✅ **Core Engine 불변**: 0 line 수정
- ✅ **D75-3/D75-4 연계**: HealthMonitor, ArbRoute, CrossSync 활용

### 설계 품질

- **Testability**: 11 unit + 4 integration tests
- **Extensibility**: Plug-in 방식, 쉬운 확장
- **Performance**: 0.0145ms latency, < 1KB memory
- **Maintainability**: 명확한 책임 분리, 문서화 완료

### TO-BE 18개 아키텍처 진행률

**Phase 1 (D75~D76) 중:**
- ✅ #2: Rate Limit Manager (D75-3 완료)
- ✅ #3: Exchange Health Monitor (D75-3 완료)
- ✅ #4: 4-Tier RiskGuard (D75-5 완료)

**Phase 2 (D77~D78) 중:**
- ✅ #6: ArbUniverse / ArbRoute (D75-4 완료)
- ✅ #7: Cross-Exchange Position Sync (D75-4 완료)

**진행률: 9/18 (50%)** 🎯

---

**문서 버전:** 1.0  
**최종 업데이트:** 2025-11-22 20:40  
**작성자:** Windsurf AI (High-Reasoning Mode)
