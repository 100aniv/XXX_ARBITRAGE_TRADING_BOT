# D79-5: Cross-Exchange Advanced Risk Management

**Status:** 🚧 **IN PROGRESS**  
**Date:** 2025-12-01  
**Owner:** Arbitrage Bot Team

---

## 📋 Summary

Cross-Exchange 아비트라지 전용 Risk Management 계층 구현.

**목표:**
1. ✅ CrossExchangeRiskGuard (5번째 Tier)
2. ✅ Cross-exposure limits
3. ✅ Inventory imbalance detection
4. ✅ Circuit breaker (Cross-Exchange 전용)
5. ✅ Dynamic thresholds
6. ✅ Alert/Metric hooks (D76/D77 연계)

---

## 🏗️ Architecture

### D75 4-Tier vs D79-5 CrossExchangeRiskGuard

**기존 D75 4-Tier RiskGuard (공용 인프라, DO NOT TOUCH):**

```
┌─────────────────────────────────────────────────┐
│         D75-5: FourTierRiskGuard                │
│                                                  │
│  Tier 1: ExchangeGuard (거래소 레벨)           │
│          - Health status (DOWN/FROZEN/DEGRADED) │
│          - Daily loss limit                     │
│          - Rate limit exhaustion                │
│                                                  │
│  Tier 2: RouteGuard (Route 레벨)               │
│          - Route score threshold                │
│          - Streak loss count                    │
│          - Abnormal spread                      │
│                                                  │
│  Tier 3: SymbolGuard (Symbol 레벨)             │
│          - Symbol exposure ratio                │
│          - Symbol drawdown                      │
│          - Volatility threshold                 │
│                                                  │
│  Tier 4: GlobalGuard (Portfolio 레벨)          │
│          - Global daily loss                    │
│          - Total exposure                       │
│          - Imbalance ratio (generic)            │
│                                                  │
│  → RiskGuardDecision                            │
│     (allow, degraded, cooldown, max_notional)   │
└─────────────────────────────────────────────────┘
```

**신규 D79-5: CrossExchangeRiskGuard (Cross-Exchange 전용, 5번째 Tier):**

```
┌─────────────────────────────────────────────────┐
│    D79-5: CrossExchangeRiskGuard (NEW)          │
│                                                  │
│  Role: D75 4-Tier의 래퍼 + Cross-Exchange 전용 │
│                                                  │
│  1. D75 4-Tier RiskGuard 호출 (1차 필터)       │
│     ↓ (BLOCK이면 즉시 반환)                     │
│                                                  │
│  2. CrossSync 기반 규칙 (Cross-Exchange 전용)  │
│     - Cross-exposure limits                     │
│     - Inventory imbalance detection             │
│     - Directional bias penalty                  │
│                                                  │
│  3. PositionManager 기반 규칙                   │
│     - Open positions count                      │
│     - POSITIVE/NEGATIVE 쏠림 방지               │
│                                                  │
│  4. Circuit Breaker (Cross-Exchange PnL 추적)  │
│     - Daily cross-exchange PnL limit            │
│     - Consecutive loss limit                    │
│                                                  │
│  5. Dynamic Thresholds                          │
│     - Volatility-based adjustment               │
│     - Market condition-based adjustment         │
│                                                  │
│  → CrossRiskDecision                            │
│     (allowed, tier, reason_code, details)       │
└─────────────────────────────────────────────────┘
```

### 전체 Risk 계층 구조도

```
CrossExchangeDecision (Entry/Exit 신호)
        ↓
┌──────────────────────────────────────┐
│  CrossExchangeExecutor._precheck()   │
│                                       │
│  1. Health check (HealthMonitor)     │
│  2. Secrets check (Settings)         │
│  3. CrossExchangeRiskGuard ← NEW!    │
└──────────────────────────────────────┘
        ↓
CrossExchangeRiskGuard.check_cross_exchange_trade()
        ↓
┌────────────────────────────────────────┐
│  Step 1: D75 4-Tier RiskGuard 호출    │
│                                        │
│  FourTierRiskGuard.check_trade()      │
│  → RiskGuardDecision                  │
│                                        │
│  if allow == False:                   │
│    즉시 CrossRiskDecision 반환 (BLOCK)│
└────────────────────────────────────────┘
        ↓ (ALLOW 시만)
┌────────────────────────────────────────┐
│  Step 2: CrossSync 규칙               │
│                                        │
│  - get_exposure(symbol_pair)          │
│  - get_imbalance_ratio()              │
│                                        │
│  Rule:                                 │
│  - exposure > EXPO_LIMIT → BLOCK      │
│  - |imbalance| > IMBALANCE_LIMIT      │
│    → BLOCK                             │
└────────────────────────────────────────┘
        ↓
┌────────────────────────────────────────┐
│  Step 3: PositionManager 규칙         │
│                                        │
│  - list_open_positions()              │
│  - get_inventory()                    │
│                                        │
│  Rule:                                 │
│  - POSITIVE 쏠림 > 70% and            │
│    new POSITIVE entry → BLOCK         │
│  - NEGATIVE 쏠림 > 70% and            │
│    new NEGATIVE entry → BLOCK         │
└────────────────────────────────────────┘
        ↓
┌────────────────────────────────────────┐
│  Step 4: Circuit Breaker              │
│                                        │
│  - Cross-Exchange PnL tracking        │
│  - Daily loss / Consecutive loss      │
│                                        │
│  Rule:                                 │
│  - Daily PnL < -DAILY_LOSS_LIMIT      │
│    → BLOCK ALL                         │
│  - Consecutive loss > MAX_LOSS_COUNT  │
│    → COOLDOWN (15min)                  │
└────────────────────────────────────────┘
        ↓
┌────────────────────────────────────────┐
│  Step 5: Dynamic Thresholds           │
│                                        │
│  - Market volatility adjustment       │
│  - Global risk state adjustment       │
│                                        │
│  if high_volatility:                  │
│    EXPO_LIMIT *= 0.7  # 30% 강화     │
│    IMBALANCE_LIMIT *= 0.8  # 20% 강화│
└────────────────────────────────────────┘
        ↓
CrossRiskDecision (Final)
```

---

## 📊 Data Sources

### 1. D75 4-Tier RiskGuard (기존)

**파일:** `arbitrage/domain/risk_guard.py`

**Input:** Route/Symbol/Exchange 정보  
**Output:** `RiskGuardDecision`
- `allow: bool`
- `degraded: bool`
- `cooldown_seconds: float`
- `max_notional: Optional[float]`
- `tier_decisions: Dict[GuardTier, TierDecision]`

**사용 방식:**
```python
# D75 RiskGuard 호출 (읽기 전용, DO NOT MODIFY)
core_decision = four_tier_risk_guard.check_trade(
    exchange_name="upbit",
    route_id="upbit_binance_btc",
    symbol="KRW-BTC",
    notional=100_000_000,
)

if not core_decision.allow:
    # D75에서 BLOCK → CrossRiskDecision 즉시 반환
    return CrossRiskDecision(
        allowed=False,
        tier=core_decision.tier_decisions[...].tier.value,
        reason_code=...,
        details=...,
    )
```

### 2. D75-4 CrossSync (기존)

**파일:** `arbitrage/domain/cross_sync.py`

**Input:** Inventory A, Inventory B  
**Output:**
- `imbalance_ratio: float` (-1.0 ~ 1.0)
- `exposure_risk: float` (0.0 ~ 1.0)
- `RebalanceSignal`

**사용 방식:**
```python
# CrossSync를 통한 exposure/imbalance 조회
inventory_tracker = InventoryTracker()
inventory_tracker.update_inventory(inventory_a, inventory_b)

rebalance_signal = inventory_tracker.evaluate_rebalance(base_price)

if abs(rebalance_signal.imbalance_ratio) > IMBALANCE_LIMIT:
    # Inventory imbalance 초과 → BLOCK
    return CrossRiskDecision(
        allowed=False,
        tier="cross_exchange",
        reason_code="INVENTORY_IMBALANCE",
        details={"imbalance_ratio": rebalance_signal.imbalance_ratio},
    )
```

### 3. D79-2 CrossExchangePositionManager (기존)

**파일:** `arbitrage/cross_exchange/position_manager.py`

**Input:** Redis (Position SSOT)  
**Output:**
- `list_open_positions() -> List[CrossExchangePosition]`
- `get_inventory() -> Dict[str, Any]`

**사용 방식:**
```python
# PositionManager를 통한 inventory 조회
positions = position_manager.list_open_positions()
inventory = position_manager.get_inventory()

# POSITIVE/NEGATIVE 쏠림 계산
positive_count = sum(1 for p in positions if p.entry_side == "positive")
negative_count = sum(1 for p in positions if p.entry_side == "negative")

if positive_count > negative_count * 3:  # 3:1 이상 쏠림
    if decision.action == CrossExchangeAction.ENTRY_POSITIVE:
        # 추가 POSITIVE 진입 차단
        return CrossRiskDecision(
            allowed=False,
            tier="cross_exchange",
            reason_code="DIRECTIONAL_BIAS",
            details={"positive_ratio": positive_count / (positive_count + negative_count)},
        )
```

---

## 🎯 Decision Model

### Input: CrossExchangeDecision

**파일:** `arbitrage/cross_exchange/integration.py`

```python
@dataclass
class CrossExchangeDecision:
    action: CrossExchangeAction  # ENTRY_POSITIVE, ENTRY_NEGATIVE, EXIT_*
    symbol_upbit: str
    symbol_binance: str
    notional_krw: float
    spread_percent: float
    reason: str
    timestamp: float
    entry_side: Optional[str]  # "positive" or "negative"
    exit_pnl_krw: Optional[float]
    position_holding_time: Optional[float]
```

### Output: CrossRiskDecision

**파일:** `arbitrage/cross_exchange/risk_guard.py` (NEW)

```python
@dataclass
class CrossRiskDecision:
    """
    Cross-Exchange Risk 결정.
    
    D75 RiskGuardDecision과 유사하지만,
    Cross-Exchange 전용 tier/reason_code 추가.
    """
    allowed: bool  # 허용 여부
    tier: Literal[
        "none",           # Risk check 통과
        "exchange",       # D75 Tier 1 BLOCK
        "route",          # D75 Tier 2 BLOCK
        "symbol",         # D75 Tier 3 BLOCK
        "global",         # D75 Tier 4 BLOCK
        "cross_exchange"  # D79-5 NEW Tier BLOCK
    ]
    reason_code: str  # 상세 이유 코드 (아래 참조)
    details: Dict[str, Any]  # 임계값/실측값/심볼/경로 등
    cooldown_until: Optional[float] = None  # Cooldown 종료 시각 (timestamp)
    max_notional_override: Optional[float] = None  # 축소 허용 시 최대 금액
```

### Reason Codes (Cross-Exchange 전용)

```python
class CrossRiskReasonCode(Enum):
    """Cross-Exchange Risk 이유 코드"""
    
    # D75 pass-through (tier="exchange", "route", "symbol", "global")
    # → D75 RiskGuard의 reason_code를 그대로 전달
    
    # Cross-Exchange 전용 (tier="cross_exchange")
    CROSS_EXPOSURE_LIMIT = "cross_exposure_limit"
    CROSS_INVENTORY_IMBALANCE = "cross_inventory_imbalance"
    CROSS_DIRECTIONAL_BIAS = "cross_directional_bias"
    CROSS_DAILY_LOSS_LIMIT = "cross_daily_loss_limit"
    CROSS_CONSECUTIVE_LOSS_LIMIT = "cross_consecutive_loss_limit"
    CROSS_CIRCUIT_BREAKER = "cross_circuit_breaker"
    CROSS_HIGH_VOLATILITY = "cross_high_volatility"
    
    # OK
    OK = "ok"
```

---

## 🛡️ Risk Rules

### Rule 1: Cross-Exposure Limit

**목적:** 특정 심볼에 대한 cross-exchange 노출도 제한

**데이터 소스:** CrossSync

**규칙:**
```python
# Exposure = |Inventory_A - Inventory_B| (normalized)
exposure = cross_sync.get_exposure(symbol_pair)

if exposure > config.max_cross_exposure:
    return CrossRiskDecision(
        allowed=False,
        tier="cross_exchange",
        reason_code="CROSS_EXPOSURE_LIMIT",
        details={
            "exposure": exposure,
            "limit": config.max_cross_exposure,
            "symbol_upbit": decision.symbol_upbit,
            "symbol_binance": decision.symbol_binance,
        },
    )
```

**기본 임계값:**
- `max_cross_exposure = 0.6` (60% 이상 한쪽 거래소 집중 시 BLOCK)

### Rule 2: Inventory Imbalance

**목적:** Upbit ↔ Binance 간 잔고 불균형 방지

**데이터 소스:** CrossSync

**규칙:**
```python
# Imbalance ratio = -1.0 ~ 1.0 (A 많음 ← 0 → B 많음)
imbalance_ratio = cross_sync.get_imbalance_ratio()

if abs(imbalance_ratio) > config.max_imbalance_ratio:
    # 불균형 방향과 진입 방향이 일치하면 BLOCK
    if imbalance_ratio > 0 and decision.action == ENTRY_POSITIVE:
        # Upbit 잔고 많음 + Upbit SELL 진입 → 추가 불균형
        return CrossRiskDecision(
            allowed=False,
            tier="cross_exchange",
            reason_code="CROSS_INVENTORY_IMBALANCE",
            details={
                "imbalance_ratio": imbalance_ratio,
                "limit": config.max_imbalance_ratio,
            },
        )
```

**기본 임계값:**
- `max_imbalance_ratio = 0.5` (±50% 이상 불균형 시 추가 진입 BLOCK)

### Rule 3: Directional Bias

**목적:** POSITIVE/NEGATIVE 포지션 쏠림 방지

**데이터 소스:** PositionManager

**규칙:**
```python
positions = position_manager.list_open_positions()

positive_count = sum(1 for p in positions if p.entry_side == "positive")
negative_count = sum(1 for p in positions if p.entry_side == "negative")
total_count = positive_count + negative_count

if total_count > 0:
    positive_ratio = positive_count / total_count
    
    if positive_ratio > config.max_directional_bias:
        if decision.action in [ENTRY_POSITIVE]:
            # 추가 POSITIVE 진입 차단
            return CrossRiskDecision(
                allowed=False,
                tier="cross_exchange",
                reason_code="CROSS_DIRECTIONAL_BIAS",
                details={
                    "positive_ratio": positive_ratio,
                    "limit": config.max_directional_bias,
                    "positive_count": positive_count,
                    "negative_count": negative_count,
                },
            )
```

**기본 임계값:**
- `max_directional_bias = 0.7` (70% 이상 쏠림 시 추가 진입 BLOCK)

### Rule 4: Circuit Breaker (Cross-Exchange PnL)

**목적:** Cross-Exchange 전략 손실 제한

**데이터 소스:** CrossExchangePnLTracker (신규, in-memory or Redis)

**규칙:**
```python
pnl_tracker = CrossExchangePnLTracker()

# Daily PnL
daily_pnl = pnl_tracker.get_daily_pnl()

if daily_pnl < -config.max_daily_loss_krw:
    return CrossRiskDecision(
        allowed=False,
        tier="cross_exchange",
        reason_code="CROSS_DAILY_LOSS_LIMIT",
        details={
            "daily_pnl_krw": daily_pnl,
            "limit": -config.max_daily_loss_krw,
        },
        cooldown_until=time.time() + 3600,  # 1시간 쿨다운
    )

# Consecutive Loss
consecutive_loss = pnl_tracker.get_consecutive_loss_count()

if consecutive_loss >= config.max_consecutive_loss:
    return CrossRiskDecision(
        allowed=False,
        tier="cross_exchange",
        reason_code="CROSS_CONSECUTIVE_LOSS_LIMIT",
        details={
            "consecutive_loss": consecutive_loss,
            "limit": config.max_consecutive_loss,
        },
        cooldown_until=time.time() + 900,  # 15분 쿨다운
    )
```

**기본 임계값:**
- `max_daily_loss_krw = 5_000_000` (500만원 일일 손실 시 BLOCK)
- `max_consecutive_loss = 5` (연속 5회 손실 시 COOLDOWN)

### Rule 5: Dynamic Thresholds

**목적:** 시장 변동성/상태에 따른 임계값 조정

**데이터 소스:** HealthMonitor, SpreadModel volatility

**규칙:**
```python
# Volatility adjustment
volatility = spread_model.get_volatility(symbol_pair)

if volatility > config.high_volatility_threshold:
    # 고변동성 → 임계값 강화
    adjusted_exposure_limit = config.max_cross_exposure * 0.7  # 30% 강화
    adjusted_imbalance_limit = config.max_imbalance_ratio * 0.8  # 20% 강화
else:
    adjusted_exposure_limit = config.max_cross_exposure
    adjusted_imbalance_limit = config.max_imbalance_ratio

# 조정된 임계값으로 Rule 1, 2 재평가
```

**기본 임계값:**
- `high_volatility_threshold = 0.05` (5% 이상 변동성 시 강화)

---

## 🔧 Implementation

### 파일 구조

```
arbitrage/cross_exchange/
├── risk_guard.py (NEW)
│   ├── CrossRiskDecision
│   ├── CrossRiskReasonCode
│   ├── CrossExchangeRiskGuardConfig
│   ├── CrossExchangePnLTracker
│   └── CrossExchangeRiskGuard
│
├── executor.py (MODIFY)
│   └── _precheck() 수정 (CrossExchangeRiskGuard 통합)
│
└── __init__.py (MODIFY)
    └── CrossExchangeRiskGuard, CrossRiskDecision export
```

### CrossExchangeRiskGuard 시그니처

```python
class CrossExchangeRiskGuard:
    """
    Cross-Exchange 아비트라지 전용 Risk Guard.
    
    D75 4-Tier RiskGuard + CrossSync + PositionManager를
    composition으로 사용하여 5번째 Tier 구현.
    """
    
    def __init__(
        self,
        four_tier_risk_guard: FourTierRiskGuard,  # D75-5
        inventory_tracker: InventoryTracker,  # D75-4 CrossSync
        position_manager: CrossExchangePositionManager,  # D79-2
        config: CrossExchangeRiskGuardConfig,
        pnl_tracker: Optional[CrossExchangePnLTracker] = None,
    ):
        self.four_tier_risk_guard = four_tier_risk_guard
        self.inventory_tracker = inventory_tracker
        self.position_manager = position_manager
        self.config = config
        self.pnl_tracker = pnl_tracker or CrossExchangePnLTracker()
    
    def check_cross_exchange_trade(
        self,
        decision: CrossExchangeDecision,
    ) -> CrossRiskDecision:
        """
        Cross-Exchange 아비트라지 진입/청산 전 최종 Risk Gate.
        
        Args:
            decision: CrossExchangeDecision (from Integration layer)
        
        Returns:
            CrossRiskDecision (allow, tier, reason_code, details)
        
        Flow:
            1. D75 4-Tier RiskGuard 호출 (1차 필터)
            2. CrossSync 기반 규칙 (exposure/imbalance)
            3. PositionManager 기반 규칙 (directional bias)
            4. Circuit Breaker (PnL tracking)
            5. Dynamic Thresholds 적용
        """
        # Step 1: D75 4-Tier RiskGuard
        core_decision = self._check_core_risk_guard(decision)
        if not core_decision.allowed:
            return core_decision
        
        # Step 2: CrossSync 규칙
        cross_sync_decision = self._check_cross_sync_rules(decision)
        if not cross_sync_decision.allowed:
            return cross_sync_decision
        
        # Step 3: PositionManager 규칙
        position_decision = self._check_position_rules(decision)
        if not position_decision.allowed:
            return position_decision
        
        # Step 4: Circuit Breaker
        circuit_decision = self._check_circuit_breaker(decision)
        if not circuit_decision.allowed:
            return circuit_decision
        
        # Step 5: Dynamic Thresholds (통합 재평가)
        # (현재 버전에서는 기본 임계값 사용, 향후 확장)
        
        # All checks passed
        return CrossRiskDecision(
            allowed=True,
            tier="none",
            reason_code="OK",
            details={},
        )
    
    def _check_core_risk_guard(self, decision) -> CrossRiskDecision:
        """D75 4-Tier RiskGuard 호출"""
        ...
    
    def _check_cross_sync_rules(self, decision) -> CrossRiskDecision:
        """CrossSync 기반 exposure/imbalance 규칙"""
        ...
    
    def _check_position_rules(self, decision) -> CrossRiskDecision:
        """PositionManager 기반 directional bias 규칙"""
        ...
    
    def _check_circuit_breaker(self, decision) -> CrossRiskDecision:
        """Circuit Breaker (PnL tracking)"""
        ...
```

---

## 🔔 Alert / Metric Hooks

### D76/D77 연계 원칙

**중요:**
- D79-5는 **이벤트 정의 + Hook 호출**만 구현
- 실제 AlertManager / Prometheus Exporter는 D76/D77에서 관리
- 새로운 텔레그램/슬랙 클라이언트 생성 금지
- 새로운 Prometheus HTTP 서버 띄우기 금지

### Alert Events (D76 연계)

**파일:** `arbitrage/alerting/alert_manager.py` (가정, 기존)

**신규 AlertType:**
```python
class AlertType(Enum):
    # ... 기존 타입들 ...
    
    # D79-5 Cross-Exchange Risk (NEW)
    CROSS_EXPOSURE_LIMIT = "cross_exposure_limit"
    CROSS_INVENTORY_IMBALANCE = "cross_inventory_imbalance"
    CROSS_CIRCUIT_BREAKER = "cross_circuit_breaker"
    CROSS_CONSECUTIVE_LOSS = "cross_consecutive_loss"
    CROSS_DIRECTIONAL_BIAS = "cross_directional_bias"
```

**사용 방식 (CrossExchangeRiskGuard 내부):**
```python
class CrossExchangeRiskGuard:
    def __init__(
        self,
        ...,
        alert_manager: Optional[AlertManager] = None,
    ):
        self.alert_manager = alert_manager
    
    def _check_circuit_breaker(self, decision) -> CrossRiskDecision:
        daily_pnl = self.pnl_tracker.get_daily_pnl()
        
        if daily_pnl < -self.config.max_daily_loss_krw:
            # Alert 전송
            if self.alert_manager:
                self.alert_manager.send_alert(
                    alert_type=AlertType.CROSS_CIRCUIT_BREAKER,
                    severity="P1",  # Critical
                    message=(
                        f"[CROSS_CIRCUIT_BREAKER] Daily PnL: {daily_pnl:,.0f} KRW "
                        f"(Limit: {-self.config.max_daily_loss_krw:,.0f} KRW)"
                    ),
                    details={
                        "daily_pnl_krw": daily_pnl,
                        "limit": -self.config.max_daily_loss_krw,
                    },
                )
            
            return CrossRiskDecision(...)
```

### Metrics (D77 Prometheus 연계)

**파일:** `arbitrage/metrics/` (가정, 기존)

**신규 Metrics:**
```python
# Counter
cross_exchange_risk_block_total = Counter(
    "cross_exchange_risk_block_total",
    "Total number of cross-exchange trades blocked by risk guard",
    ["reason_code", "tier"],
)

# Gauge
cross_exchange_exposure_ratio = Gauge(
    "cross_exchange_exposure_ratio",
    "Current cross-exchange exposure ratio",
    ["symbol_upbit", "symbol_binance"],
)

cross_exchange_imbalance_ratio = Gauge(
    "cross_exchange_imbalance_ratio",
    "Current cross-exchange inventory imbalance ratio",
    ["symbol_pair"],
)

cross_exchange_daily_pnl_krw = Gauge(
    "cross_exchange_daily_pnl_krw",
    "Current daily PnL for cross-exchange strategy (KRW)",
)

cross_exchange_directional_bias = Gauge(
    "cross_exchange_directional_bias",
    "POSITIVE position ratio (0.0 ~ 1.0)",
)
```

**사용 방식 (CrossExchangeRiskGuard 내부):**
```python
class CrossExchangeRiskGuard:
    def check_cross_exchange_trade(self, decision) -> CrossRiskDecision:
        result = self._execute_checks(decision)
        
        # Metric 업데이트
        if not result.allowed:
            cross_exchange_risk_block_total.labels(
                reason_code=result.reason_code,
                tier=result.tier,
            ).inc()
        
        # Exposure/Imbalance metric 업데이트
        exposure = self.inventory_tracker.get_exposure(...)
        cross_exchange_exposure_ratio.labels(
            symbol_upbit=decision.symbol_upbit,
            symbol_binance=decision.symbol_binance,
        ).set(exposure)
        
        return result
```

---

## 🧪 Testing Strategy

### 테스트 파일

**파일:** `tests/test_d79_5_risk_guard.py` (NEW)

### 테스트 시나리오 (최소 15개)

**1. 기본 동작 (3 tests)**
- ✅ Health/Secrets OK, D75 ALLOW, Cross-Exchange 규칙 OK → allowed=True
- ✅ CrossExchangeRiskGuard 초기화
- ✅ 전체 플로우 통과 (no blocks)

**2. D75 4-Tier RiskGuard BLOCK (4 tests)**
- ✅ ExchangeGuard BLOCK → tier="exchange"
- ✅ RouteGuard BLOCK → tier="route"
- ✅ SymbolGuard BLOCK → tier="symbol"
- ✅ GlobalGuard BLOCK → tier="global"

**3. Cross-Exchange 규칙 BLOCK (5 tests)**
- ✅ Exposure limit 초과 → tier="cross_exchange", reason="CROSS_EXPOSURE_LIMIT"
- ✅ Inventory imbalance 초과 → reason="CROSS_INVENTORY_IMBALANCE"
- ✅ Directional bias (POSITIVE 쏠림) → reason="CROSS_DIRECTIONAL_BIAS"
- ✅ Directional bias (NEGATIVE 쏠림) → reason="CROSS_DIRECTIONAL_BIAS"
- ✅ Circuit breaker (daily loss) → reason="CROSS_DAILY_LOSS_LIMIT"

**4. Executor 통합 (2 tests)**
- ✅ Executor._precheck() → CrossExchangeRiskGuard 호출 → BLOCK → 주문 0건
- ✅ Executor._precheck() → CrossExchangeRiskGuard 호출 → ALLOW → 주문 정상 실행

**5. Alert/Metric Hook (2 tests)**
- ✅ Circuit breaker 발생 → AlertManager.send_alert() 호출 확인
- ✅ Exposure limit 발생 → Metric counter 증가 확인

**6. PnLTracker (2 tests)**
- ✅ Daily PnL 누적 및 조회
- ✅ Consecutive loss 카운팅 및 리셋

**7. Cooldown (1 test)**
- ✅ Cooldown 상태에서 재호출 → BLOCK 유지

---

## 📝 Acceptance Criteria

D79-5가 "상용 초과 품질"로 완료되려면 아래 모든 조건 만족:

- [ ] ✅ **설계**
  - [ ] docs/D79_5_CROSS_EXCHANGE_RISKGUARD.md 작성
  - [ ] D75/D79 문맥과 일관된 설계

- [ ] ✅ **구현**
  - [ ] arbitrage/cross_exchange/risk_guard.py 구현
  - [ ] CrossExchangeRiskGuard, CrossRiskDecision, CrossExchangePnLTracker
  - [ ] D75 RiskGuard / CrossSync / PositionManager composition (Core 수정 없음)

- [ ] ✅ **통합**
  - [ ] CrossExchangeExecutor._precheck() 에 CrossExchangeRiskGuard 통합
  - [ ] BLOCK 시 실제 주문 호출 0건 보장 (테스트 검증)

- [ ] ✅ **Alert/Metric Hook**
  - [ ] D76/D77 Alert/Metric 인프라와 연결 가능한 Hook 구현
  - [ ] 이벤트/카운터 수준 (실제 텔레그램/Prometheus 서버는 D76/D77에서 관리)

- [ ] ✅ **테스트**
  - [ ] tests/test_d79_5_risk_guard.py 최소 15개 시나리오
  - [ ] 기존 D75/D79 테스트 포함 타깃 pytest 전체 PASS

- [ ] ✅ **문서 & Roadmap**
  - [ ] D_ROADMAP.md 에 D79-5 상태 반영
  - [ ] D79-2/3/4/5 간 구조도/플로우 일관성 유지

---

## 🚀 Next Steps (D79-6)

### D79-6: Real-time Monitoring & Advanced Metrics

**목표:**
- Grafana dashboard (Cross-Exchange 전용)
- Real-time exposure/imbalance visualization
- Trade execution latency tracking
- PnL attribution analysis

---

## 📚 Related Documents

- [D75-5: 4-Tier RiskGuard](./D75_5_4TIER_RISKGUARD_DESIGN.md)
- [D75-4: Route/Universe/CrossSync](./D75_4_ROUTE_UNIVERSE_DESIGN.md)
- [D79-2: Entry/Exit Strategy](./D79_CROSS_EXCHANGE_STRATEGY_DESIGN.md)
- [D79-3: Engine Integration (Paper)](./D79_3_CROSS_EXCHANGE_ENGINE_INTEGRATION.md)
- [D79-4: Real Order Execution](./D79_4_CROSS_EXCHANGE_EXECUTION.md)
- [D76: Alerting Infrastructure](./D76_ALERTING_INFRA_SKETCH.md) (TBD)
- [D77: Prometheus Metrics](./D77_METRICS_DESIGN.md) (TBD)

---

**Status:** 🚧 **IN PROGRESS**  
**Version:** 0.1.0 (Draft)  
**Last Updated:** 2025-12-01
