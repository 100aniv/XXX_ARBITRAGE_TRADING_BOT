# D73-2: Multi-Symbol Engine Loop

**Status:** ✅ COMPLETED  
**Date:** 2025-11-21  
**Author:** D73-2 Implementation Team

---

## 📋 개요

### 목적

Per-symbol coroutine 구조로 멀티심볼 동시 처리 기반을 구축합니다.

**D73-1 Symbol Universe Provider**에서 제공하는 심볼 리스트를 받아, 각 심볼별로 독립적인 엔진 코루틴을 생성·실행하는 **오케스트레이션 레이어**를 추가합니다.

### 핵심 가치

1. **기존 단일 심볼 엔진 재사용**
   - ArbitrageLiveRunner를 그대로 활용
   - 새로운 엔진을 만들지 않고 상단에 orchestration layer만 추가

2. **Single event loop**
   - `asyncio.run()` 한 번만 호출
   - Per-symbol task는 `asyncio.create_task()`로 생성

3. **Config 기반 모드 전환**
   - `engine.mode = "single"` → 기존 단일 심볼 방식
   - `engine.mode = "multi"` → 멀티심볼 방식
   - 기본값은 `"single"`로 100% 하위 호환

4. **확장 가능한 구조**
   - D73-3: Multi-Symbol RiskGuard 통합
   - D73-4: Small-Scale Integration Test (Top-10)
   - D74: Performance Optimization (Top-20/50)

---

## 🏗️ Architecture

### 전체 구조

```
┌─────────────────────────────────────────────────────────┐
│            MultiSymbolEngineRunner                      │
│  ┌───────────────────────────────────────────────────┐  │
│  │  async def run_multi():                           │  │
│  │      symbols = universe.get_symbols()             │  │
│  │      tasks = [                                    │  │
│  │          create_task(run_for_symbol(symbol, ...)) │  │
│  │          for symbol in symbols                    │  │
│  │      ]                                            │  │
│  │      await gather(*tasks)                         │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
     run_for_symbol  run_for_symbol  run_for_symbol
      (BTCUSDT)       (ETHUSDT)       (BNBUSDT)
          │              │              │
     (Existing       (Existing      (Existing
      Single          Single         Single
      Engine)         Engine)        Engine)
```

### 주요 컴포넌트

#### 1. MultiSymbolEngineRunner

멀티심볼 엔진 오케스트레이터 클래스.

**Responsibilities:**
- Universe에서 심볼 리스트 조회
- 각 심볼별 독립 코루틴 생성 및 관리
- Shared context (Portfolio, RiskGuard) 관리
- Graceful shutdown / error handling

**Public API:**
```python
class MultiSymbolEngineRunner:
    def __init__(
        self,
        universe: SymbolUniverse,
        exchange_a: BaseExchange,
        exchange_b: BaseExchange,
        engine_config: ArbitrageConfig,
        live_config: ArbitrageLiveConfig,
        ...
    ):
        ...
    
    async def run_multi(self) -> None:
        """Multi-Symbol Engine 실행"""
        ...
    
    def stop(self) -> None:
        """Multi-Symbol Engine 중지"""
        ...
    
    def get_stats(self) -> Dict[str, Any]:
        """Multi-Symbol Engine 통계"""
        ...
```

#### 2. create_multi_symbol_runner()

Helper function for easy instantiation.

```python
def create_multi_symbol_runner(
    config: ArbitrageConfig,
    exchange_a: BaseExchange,
    exchange_b: BaseExchange,
    **kwargs
) -> MultiSymbolEngineRunner:
    """
    ArbitrageConfig (통합 설정)에서 MultiSymbolEngineRunner 생성.
    
    Args:
        config: ArbitrageConfig (D72-1 통합 설정)
        exchange_a: Exchange A
        exchange_b: Exchange B
        **kwargs: 추가 인자 (market_data_provider, metrics_collector, state_store 등)
    
    Returns:
        MultiSymbolEngineRunner instance
    """
    ...
```

#### 3. EngineConfig

```python
@dataclass(frozen=True)
class EngineConfig:
    """Engine 실행 모드 설정 (D73-2)"""
    
    mode: str = 'single'  # 'single' (default), 'multi'
    multi_symbol_enabled: bool = False
    per_symbol_isolation: bool = True
```

**Added to ArbitrageConfig:**
```python
@dataclass(frozen=True)
class ArbitrageConfig:
    ...
    engine: EngineConfig = field(default_factory=lambda: EngineConfig())
```

---

## 🎯 동작 예시

### 1. SINGLE 모드 (기존 방식, 하위 호환)

```python
from config.base import ArbitrageConfig, EngineConfig

config = ArbitrageConfig(
    ...
    engine=EngineConfig(mode="single")  # Default
)

# 기존 ArbitrageLiveRunner 그대로 사용
runner = ArbitrageLiveRunner(...)
runner.run()
```

### 2. MULTI 모드 (멀티심볼, TOP_N)

```python
from config.base import ArbitrageConfig, EngineConfig, SymbolUniverseConfig
from arbitrage.symbol_universe import SymbolUniverseMode
from arbitrage.multi_symbol_engine import create_multi_symbol_runner

config = ArbitrageConfig(
    ...
    engine=EngineConfig(mode="multi", multi_symbol_enabled=True),
    universe=SymbolUniverseConfig(
        mode=SymbolUniverseMode.TOP_N,
        top_n=5,
        base_quote="USDT",
        blacklist=["BUSDUSDT", "USDCUSDT"]
    )
)

# MultiSymbolEngineRunner 생성
runner = create_multi_symbol_runner(
    config=config,
    exchange_a=exchange_a,
    exchange_b=exchange_b
)

# Async 실행
import asyncio
asyncio.run(runner.run_multi())
```

### 3. MULTI 모드 (FIXED_LIST)

```python
config = ArbitrageConfig(
    ...
    engine=EngineConfig(mode="multi"),
    universe=SymbolUniverseConfig(
        mode=SymbolUniverseMode.FIXED_LIST,
        whitelist=["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    )
)

runner = create_multi_symbol_runner(config, exchange_a, exchange_b)
asyncio.run(runner.run_multi())
```

---

## 🔧 Per-Symbol Config Mapping

MultiSymbolEngineRunner는 각 심볼에 대해 별도의 ArbitrageLiveConfig를 생성합니다.

**매핑 로직:**
```python
def _create_symbol_config(self, symbol: str) -> ArbitrageLiveConfig:
    """
    USDT 페어 → KRW 페어 매핑
    
    예: "BTCUSDT" → symbol_a="KRW-BTC", symbol_b="BTCUSDT"
    """
    if symbol.endswith("USDT"):
        base = symbol[:-4]  # "BTCUSDT" → "BTC"
        symbol_a = f"KRW-{base}"  # "KRW-BTC"
        symbol_b = symbol  # "BTCUSDT"
    else:
        # Fallback
        symbol_a = self.live_config.symbol_a
        symbol_b = symbol
    
    # Create new config with updated symbols
    symbol_config = copy.copy(self.live_config)
    symbol_config.symbol_a = symbol_a
    symbol_config.symbol_b = symbol_b
    
    return symbol_config
```

**결과:**
- `BTCUSDT` → `symbol_a="KRW-BTC", symbol_b="BTCUSDT"`
- `ETHUSDT` → `symbol_a="KRW-ETH", symbol_b="ETHUSDT"`
- `BNBUSDT` → `symbol_a="KRW-BNB", symbol_b="BNBUSDT"`

---

## ✅ 테스트 결과

### 테스트 커버리지

| Test Case | 결과 |
|-----------|------|
| MultiSymbolEngineRunner 생성 | ✅ PASS |
| Per-symbol runner 매핑 | ✅ PASS |
| Config Integration (engine 필드) | ✅ PASS |
| SINGLE vs MULTI 모드 호환성 | ✅ PASS |
| Multi-Symbol async 구조 | ✅ PASS |

**Total: 5/5 PASS (100%)**

### 실행 방법

```bash
# D73-2 테스트
python scripts/test_d73_2_multi_symbol_engine.py

# D73-1 회귀 테스트
python scripts/test_d73_1_symbol_universe.py
```

### 테스트 출력 예시

```
======================================================================
D73-2: Multi-Symbol Engine Loop 테스트 시작
======================================================================

Test 1: MultiSymbolEngineRunner 생성 검증
✅ PASS: Runner created successfully
  Universe mode: FIXED_LIST
  Symbols: ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']

Test 2: Per-symbol runner 매핑 검증
Universe symbols (TOP_N=5): ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']
  BTCUSDT → symbol_a=KRW-BTC, symbol_b=BTCUSDT
  ETHUSDT → symbol_a=KRW-ETH, symbol_b=ETHUSDT
  BNBUSDT → symbol_a=KRW-BNB, symbol_b=BNBUSDT
  SOLUSDT → symbol_a=KRW-SOL, symbol_b=SOLUSDT
  XRPUSDT → symbol_a=KRW-XRP, symbol_b=XRPUSDT
✅ PASS: Per-symbol config mapping successful

...

총 5개 테스트 중 5개 통과
✅ 모든 테스트 통과!
```

---

## 🚀 D73-3+ 확장 포인트

### D73-3: Multi-Symbol RiskGuard 통합

**RiskGuard 계층 구조:**
```
GlobalGuard (전체 포트폴리오)
├── PortfolioGuard (max_total_exposure)
├── SymbolGuard[BTCUSDT] (max_symbol_position, cooldown)
├── SymbolGuard[ETHUSDT]
└── ...
```

**통합 방법:**
```python
class MultiSymbolEngineRunner:
    def __init__(self, ...):
        # D73-3: Multi-Symbol RiskGuard
        self._shared_risk_guard = MultiSymbolRiskGuard(
            symbols=self.universe.get_symbols(),
            global_limits=...
        )
    
    async def _run_for_symbol(self, symbol: str) -> None:
        # Symbol-specific guard
        symbol_guard = self._shared_risk_guard.get_symbol_guard(symbol)
        
        runner = ArbitrageLiveRunner(
            ...,
            risk_guard=symbol_guard  # Per-symbol guard
        )
        ...
```

### D73-4: Small-Scale Integration Test

**목표:**
- Top-10 심볼 PAPER 모드 통합 테스트
- 5분 캠페인 실행 (Entry/Exit/PnL 검증)
- Multi-symbol snapshot 저장/복원 테스트

**테스트 시나리오:**
```python
# Top-10 PAPER 테스트
config = ArbitrageConfig(
    engine=EngineConfig(mode="multi"),
    universe=SymbolUniverseConfig(
        mode=SymbolUniverseMode.TOP_N,
        top_n=10,
        blacklist=["BUSDUSDT", "USDCUSDT"]
    ),
    session=SessionConfig(
        mode="paper",
        max_runtime_seconds=300  # 5분
    )
)

runner = create_multi_symbol_runner(config, ...)
asyncio.run(runner.run_multi())

# 검증
stats = runner.get_stats()
assert stats['num_symbols'] == 10
assert len(runner._symbol_runners) == 10
```

### D74: Performance Optimization

**목표:**
- Top-20/50 심볼 동시 처리 성능 검증
- Event loop 단일화 검증
- Per-symbol metrics collection
- Graceful shutdown / cancellation handling 강화

**성능 목표:**
| 지표 | 목표 |
|------|------|
| Loop latency (avg) | <10ms |
| Loop latency (p99) | <25ms |
| 동시 심볼 수 | 20-50 |
| CPU usage (20 symbols) | <70% |

---

## 📁 생성된 파일

| 파일 | 라인 수 | 설명 |
|------|---------|------|
| `arbitrage/multi_symbol_engine.py` | ~360 | Multi-Symbol Engine Runner |
| `arbitrage/symbol_universe.py` | +32 | build_symbol_universe() 추가 |
| `config/base.py` | +17 | EngineConfig 추가 |
| `scripts/test_d73_2_multi_symbol_engine.py` | ~360 | 통합 테스트 스크립트 |
| `docs/D73_2_MULTI_SYMBOL_ENGINE.md` | ~500 | 본 문서 |

**Total: ~1,269 lines (코드 + 문서)**

---

## 🎓 핵심 학습 내용

### 설계 원칙

1. **Reuse over Reinvent**
   - 기존 ArbitrageLiveRunner 재사용
   - Orchestration layer만 추가

2. **Single Event Loop**
   - `asyncio.run()` 한 번만
   - `asyncio.create_task()` + `asyncio.gather()`

3. **Config-Driven**
   - `engine.mode` 필드로 single/multi 전환
   - 기본값은 "single" (100% 하위 호환)

### 하위 호환성 보장

- `engine.mode = "single"` (기본값) → 기존 방식 그대로
- D73-1 Symbol Universe 테스트 모두 통과
- 기존 ArbitrageLiveRunner API 변경 없음

### 확장성

- D73-3: Multi-Symbol RiskGuard 통합 준비 완료
- D73-4: Small-Scale Integration Test 설계 완료
- D74: Performance Optimization 목표 설정 완료

---

## 📝 Acceptance Criteria (D73-2)

- ✅ Per-symbol coroutine 구조 구현
- ✅ Universe → MultiSymbolEngine 통합
- ✅ Config 기반 single/multi 모드 전환
- ✅ Per-symbol runner 생성/매핑
- ✅ 테스트 5/5 PASS (100%)
- ✅ 문서화 완료
- ✅ 기존 D73-1 테스트 회귀 없음

---

**Status:** ✅ D73-2 COMPLETED  
**Next:** D73-3 Multi-Symbol RiskGuard 통합

**Author:** D73-2 Implementation Team  
**Date:** 2025-11-21
