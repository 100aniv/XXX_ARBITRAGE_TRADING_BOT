# D73-3: Multi-Symbol RiskGuard Integration

**Status:** ✅ COMPLETED  
**Date:** 2025-11-21  
**Dependencies:** D73-2 (Multi-Symbol Engine Loop), D72-2 (Redis Keyspace)

---

## 📋 개요

### 목적

Multi-Symbol 환경에서 3-Tier Risk Management 계층을 구축하여 포트폴리오 전체 및 개별 심볼의 리스크를 체계적으로 관리합니다.

### 핵심 가치

1. **3-Tier Risk Architecture**
   - GlobalGuard: 전체 포트폴리오 한도 (total exposure, daily loss)
   - PortfolioGuard: 심볼별 자본 할당 및 밸런싱
   - SymbolGuard: 개별 심볼 리스크 (position size, cooldown, circuit breaker)

2. **순차적 평가 (Strict Order)**
   - Global → Portfolio → Symbol 순서로 평가
   - 하나라도 FAIL이면 거래 차단

3. **Config 기반 설정**
   - MultiSymbolRiskGuardConfig 추가
   - ArbitrageConfig에 통합

4. **MultiSymbolEngineRunner 통합**
   - RiskCoordinator가 자동으로 생성·연결됨
   - create_multi_symbol_runner() 헬퍼 함수에서 처리

---

## 🏗️ Architecture

### 3-Tier Risk Guard Hierarchy

```
MultiSymbolRiskCoordinator
├── GlobalGuard (Portfolio-level)
│   ├── max_total_exposure_usd: 10,000 USD
│   ├── max_daily_loss_usd: 500 USD
│   └── emergency_stop_loss_usd: 1,000 USD
│
├── PortfolioGuard (Capital Allocation)
│   ├── total_capital_usd: 10,000 USD
│   ├── max_symbol_allocation_pct: 30%
│   └── symbol_allocations: {BTC: 3000, ETH: 3000, BNB: 2000}
│
└── SymbolGuard[] (Per-Symbol Limits)
    ├── SymbolGuard[BTCUSDT]
    │   ├── max_position_size_usd: 1,000 USD
    │   ├── max_position_count: 3
    │   ├── cooldown_seconds: 60s
    │   ├── circuit_breaker_loss_count: 3
    │   └── circuit_breaker_duration: 300s
    ├── SymbolGuard[ETHUSDT]
    └── ...
```

### Evaluation Flow

```
거래 요청 (symbol, position_size)
    ↓
┌───────────────────────────────┐
│  1. GlobalGuard Check         │
│  - Total exposure limit?      │
│  - Daily loss limit?          │
│  - Emergency stop?            │
└───────────────────────────────┘
    ↓ OK
┌───────────────────────────────┐
│  2. PortfolioGuard Check      │
│  - Symbol allocation limit?   │
│  - Portfolio balance OK?      │
└───────────────────────────────┘
    ↓ OK
┌───────────────────────────────┐
│  3. SymbolGuard Check         │
│  - Position size OK?          │
│  - Position count OK?         │
│  - Not in cooldown?           │
│  - Circuit breaker OFF?       │
└───────────────────────────────┘
    ↓ OK
 ✅ Trade Allowed
```

---

## 🔧 구현 상세

### 1. GlobalGuard

**책임:**
- 전체 포트폴리오 노출 한도 관리
- 일일 최대 손실 추적
- 긴급 중단 (emergency stop) 트리거

**주요 메서드:**
```python
class GlobalGuard:
    def check_global_limits(self, additional_exposure_usd: float) -> RiskGuardDecision
    def update_exposure(self, delta_usd: float) -> None
    def update_daily_loss(self, loss_usd: float) -> None
```

**Decision Flow:**
1. Emergency stop 체크 (daily_loss >= emergency_stop_loss)
2. 일일 최대 손실 체크 (daily_loss >= max_daily_loss)
3. 전체 노출 한도 체크 (total_exposure + additional > max_total_exposure)

### 2. PortfolioGuard

**책임:**
- 심볼별 자본 할당 (가중치 기반)
- 심볼별 노출 추적
- 포트폴리오 리밸런싱

**주요 메서드:**
```python
class PortfolioGuard:
    def allocate_capital(self, symbols: List[str], weights: Optional[Dict[str, float]]) -> Dict[str, float]
    def check_symbol_allocation(self, symbol: str, additional_exposure_usd: float) -> RiskGuardDecision
    def update_symbol_exposure(self, symbol: str, delta_usd: float) -> None
```

**자본 할당 로직:**
- 가중치 없으면 균등 분배
- 가중치 있으면 비율에 따라 분배
- max_symbol_allocation_pct로 심볼당 최대 비율 제한 (기본 30%)

### 3. SymbolGuard

**책임:**
- 개별 심볼의 포지션 크기/수 제한
- 진입 후 쿨다운 강제
- 연속 손실 시 Circuit Breaker 발동

**주요 메서드:**
```python
class SymbolGuard:
    def check_symbol_limits(self, position_size_usd: float) -> RiskGuardDecision
    def on_entry(self, position_size_usd: float) -> None
    def on_exit(self, pnl_usd: float) -> None
```

**Circuit Breaker 로직:**
- 연속 `circuit_breaker_loss_count`회 손실 발생 시 발동
- `circuit_breaker_duration` 동안 해당 심볼 거래 차단
- 이익 발생 시 연속 손실 카운터 리셋

### 4. MultiSymbolRiskCoordinator

**책임:**
- 3-Tier Guard 조정 및 통합
- 진입/청산 이벤트 전파
- 통계 집계

**주요 메서드:**
```python
class MultiSymbolRiskCoordinator:
    def check_trade_allowed(self, symbol: str, position_size_usd: float) -> RiskGuardDecision
    def on_trade_entry(self, symbol: str, position_size_usd: float) -> None
    def on_trade_exit(self, symbol: str, position_size_usd: float, pnl_usd: float) -> None
    def get_stats(self) -> Dict[str, Any]
```

---

## 📦 Config Integration

### MultiSymbolRiskGuardConfig

```python
@dataclass(frozen=True)
class MultiSymbolRiskGuardConfig:
    """Multi-Symbol RiskGuard 설정 (D73-3)"""
    
    # Global Guard
    max_total_exposure_usd: float = 10000.0
    max_daily_loss_usd: float = 500.0
    emergency_stop_loss_usd: float = 1000.0
    
    # Portfolio Guard
    total_capital_usd: float = 10000.0
    max_symbol_allocation_pct: float = 0.3
    
    # Symbol Guard (공통 설정)
    max_position_size_usd: float = 1000.0
    max_position_count: int = 3
    cooldown_seconds: float = 60.0
    max_symbol_daily_loss_usd: float = 200.0
    circuit_breaker_loss_count: int = 3
    circuit_breaker_duration: float = 300.0
```

### ArbitrageConfig 통합

```python
@dataclass(frozen=True)
class ArbitrageConfig:
    ...
    multi_symbol_risk_guard: MultiSymbolRiskGuardConfig = field(
        default_factory=lambda: MultiSymbolRiskGuardConfig()
    )
```

---

## 🎯 사용 예시

### 1. Config 기반 생성

```python
from config.base import ArbitrageConfig, EngineConfig, MultiSymbolRiskGuardConfig
from arbitrage.multi_symbol_engine import create_multi_symbol_runner

config = ArbitrageConfig(
    ...
    engine=EngineConfig(mode="multi"),
    multi_symbol_risk_guard=MultiSymbolRiskGuardConfig(
        max_total_exposure_usd=5000.0,
        max_daily_loss_usd=250.0,
        total_capital_usd=5000.0,
        max_position_size_usd=500.0,
    ),
)

# RiskCoordinator는 자동 생성됨
runner = create_multi_symbol_runner(
    config=config,
    exchange_a=exchange_a,
    exchange_b=exchange_b,
)
```

### 2. 수동 생성

```python
from arbitrage.risk import (
    GlobalGuard,
    PortfolioGuard,
    MultiSymbolRiskCoordinator,
)

global_guard = GlobalGuard(
    max_total_exposure_usd=10000.0,
    max_daily_loss_usd=500.0,
)

portfolio_guard = PortfolioGuard(
    total_capital_usd=10000.0,
    max_symbol_allocation_pct=0.3,
)

symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
portfolio_guard.allocate_capital(symbols)

coordinator = MultiSymbolRiskCoordinator(
    global_guard=global_guard,
    portfolio_guard=portfolio_guard,
    symbols=symbols,
)

# 거래 허용 체크
decision = coordinator.check_trade_allowed("BTCUSDT", 500.0)
if decision == RiskGuardDecision.OK:
    coordinator.on_trade_entry("BTCUSDT", 500.0)
```

---

## ✅ 테스트 결과

### 테스트 커버리지

| Test Case | 결과 |
|-----------|------|
| GlobalGuard 한도 체크 | ✅ PASS |
| PortfolioGuard 자본 할당 | ✅ PASS |
| SymbolGuard 필터링 | ✅ PASS |
| MultiSymbolRiskCoordinator 3-tier 평가 | ✅ PASS |
| Config Integration | ✅ PASS |
| D73-1 회귀 테스트 | ✅ PASS |
| D73-2 회귀 테스트 | ✅ PASS |

**Total: 7/7 PASS (100%)**

### 실행 방법

```bash
# D73-3 테스트
python scripts/test_d73_3_multi_symbol_risk_guard.py

# 회귀 테스트
python scripts/test_d73_1_symbol_universe.py
python scripts/test_d73_2_multi_symbol_engine.py
```

---

## 🚀 D73-4+ 확장 포인트

### D73-4: Small-Scale Integration Test

**목표:**
- Top-10 심볼 PAPER 모드 통합 테스트
- 5분 캠페인 실행 (Entry/Exit/PnL 검증)
- RiskGuard 실시간 동작 확인

**테스트 시나리오:**
```python
config = ArbitrageConfig(
    engine=EngineConfig(mode="multi"),
    universe=SymbolUniverseConfig(mode=SymbolUniverseMode.TOP_N, top_n=10),
    multi_symbol_risk_guard=MultiSymbolRiskGuardConfig(...),
)

runner = create_multi_symbol_runner(config, ...)
asyncio.run(runner.run_multi())

# 검증
- 10개 심볼 모두 정상 실행
- GlobalGuard/PortfolioGuard/SymbolGuard 트리거 확인
- Per-symbol PnL 집계 정확성
```

### D74: Performance Optimization

**성능 목표:**
- Loop latency: <10ms (avg), <25ms (p99)
- 동시 심볼 수: 20-50
- CPU usage: <70%

**최적화 항목:**
- RiskGuard check 최적화 (캐싱)
- State update 배치 처리
- Redis pipeline 사용

---

## 📁 생성된 파일

| 파일 | 라인 수 | 설명 |
|------|---------|------|
| `arbitrage/risk/__init__.py` | 26 | Risk 모듈 init |
| `arbitrage/risk/multi_symbol_risk_guard.py` | ~700 | 3-Tier RiskGuard 구현 |
| `config/base.py` | +28 | MultiSymbolRiskGuardConfig 추가 |
| `arbitrage/multi_symbol_engine.py` | +70 | RiskCoordinator 통합 |
| `scripts/test_d73_3_multi_symbol_risk_guard.py` | ~450 | 통합 테스트 |
| `docs/D73_3_MULTI_SYMBOL_RISK_GUARD.md` | ~500 | 본 문서 |

**Total: ~1,774 lines (코드 + 문서)**

---

## 🎓 핵심 학습 내용

### 설계 원칙

1. **Layered Defense**
   - Global → Portfolio → Symbol 순차 평가
   - 각 계층은 독립적으로 동작하지만 상호 조정됨

2. **Fail-Fast**
   - 가장 빠른 단계(Global)에서 먼저 차단
   - 불필요한 downstream 평가 방지

3. **Config-Driven**
   - 모든 한도는 Config에서 관리
   - 런타임에 변경 가능 (future work)

### Circuit Breaker Pattern

- 연속 손실 발생 시 자동 차단
- 일정 시간 후 자동 해제
- 이익 발생 시 카운터 리셋

### Capital Allocation

- 가중치 기반 자본 분배
- max_symbol_allocation_pct로 집중 리스크 방지
- 리밸런싱 지원 (향후 자동화 예정)

---

## 📝 Acceptance Criteria (D73-3)

- ✅ 3-Tier Risk Guard 계층 구현 (Global/Portfolio/Symbol)
- ✅ MultiSymbolRiskCoordinator 통합
- ✅ Config 기반 설정 (MultiSymbolRiskGuardConfig)
- ✅ MultiSymbolEngineRunner 통합 (create_multi_symbol_runner)
- ✅ 테스트 7/7 PASS (100%)
- ✅ 문서화 완료
- ✅ D73-1, D73-2 회귀 없음

---

**Status:** ✅ D73-3 COMPLETED  
**Next:** D73-4 Small-Scale Integration Test (Top-10 PAPER)

**Author:** D73-3 Implementation Team  
**Date:** 2025-11-21
