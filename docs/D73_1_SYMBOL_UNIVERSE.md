# D73-1: Symbol Universe Provider

**Status:** ✅ COMPLETED  
**Date:** 2025-11-21  
**Author:** D73-1 Implementation Team

---

## 📋 개요

### 목적

Multi-Symbol Arbitrage Engine의 **심볼 선택/필터링 계층**을 독립 모듈로 구현합니다.

기존 단일 심볼 구조를 유지하면서, 향후 멀티심볼 확장을 위한 기반을 마련합니다.

### Multi-Symbol To-BE에서의 역할

```
┌─────────────────────────────────────────────────────────┐
│                  Arbitrage Engine                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │      D73-2: Per-Symbol Engine Loop                │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  for symbol in universe.get_symbols():      │  │  │
│  │  │      await run_symbol_engine(symbol, ...)   │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
│                         ↑                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │      D73-1: Symbol Universe Provider             │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  get_symbols() -> List[str]                 │  │  │
│  │  │  - SINGLE: ["BTCUSDT"]                      │  │  │
│  │  │  - FIXED_LIST: ["BTC", "ETH", "BNB"]        │  │  │
│  │  │  - TOP_N: Top-20 by volume                  │  │  │
│  │  │  - FULL_MARKET: All filtered symbols        │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 핵심 가치

1. **분리된 책임 (Separation of Concerns)**
   - Engine: 거래 로직 실행
   - Universe: 심볼 선택/필터링

2. **기존 구조 100% 하위 호환**
   - SINGLE 모드 = 기존 단일 심볼 방식과 완전히 동일

3. **확장 가능성**
   - D73-2+에서 실제 거래소 API 통합
   - D73-3+에서 Multi-Symbol RiskGuard 통합

---

## 🏗️ 모듈 설계

### 주요 컴포넌트

#### 1. SymbolUniverseMode (Enum)

4가지 심볼 선택 모드:

| Mode | 설명 | Use Case |
|------|------|----------|
| `SINGLE` | 단일 심볼 | 기존 방식, 테스트, 단일 페어 집중 |
| `FIXED_LIST` | 고정 리스트 | 수동 선택 심볼 (whitelist 기반) |
| `TOP_N` | 상위 N개 (거래량 기준) | 동적 심볼 선택 (Top-20 자동) |
| `FULL_MARKET` | 전체 시장 (필터링 후) | 모든 심볼 동시 거래 (고급) |

#### 2. SymbolUniverseConfig (Dataclass)

Universe 설정 모델:

```python
@dataclass
class SymbolUniverseConfig:
    # Mode
    mode: SymbolUniverseMode = SymbolUniverseMode.SINGLE
    
    # Exchange
    exchange: str = "binance_futures"
    
    # SINGLE mode
    single_symbol: Optional[str] = "BTCUSDT"
    
    # FIXED_LIST mode
    whitelist: List[str] = field(default_factory=list)
    
    # TOP_N mode
    top_n: Optional[int] = None
    
    # Filtering (TOP_N, FULL_MARKET 공통)
    base_quote: str = "USDT"
    blacklist: List[str] = field(default_factory=list)
    min_24h_quote_volume: Optional[float] = None
```

#### 3. SymbolInfo (Dataclass)

심볼 메타데이터:

```python
@dataclass
class SymbolInfo:
    symbol: str
    base_asset: str
    quote_asset: str
    is_margin: Optional[bool] = None
    is_perpetual: Optional[bool] = None
    volume_24h_quote: Optional[float] = None
```

#### 4. AbstractSymbolSource (Protocol)

거래소별 심볼 소스 인터페이스:

```python
class AbstractSymbolSource(Protocol):
    def get_all_symbols(self) -> List[SymbolInfo]:
        ...
```

**구현체:**
- `DummySymbolSource`: 테스트용 샘플 데이터 (D73-1)
- `BinanceSymbolSource`: Binance API 연동 (D73-2 예정)
- `UpbitSymbolSource`: Upbit API 연동 (D73-2 예정)

#### 5. SymbolUniverse (핵심 클래스)

최종 심볼 리스트 생성:

```python
class SymbolUniverse:
    def __init__(self, config: SymbolUniverseConfig, source: AbstractSymbolSource):
        ...
    
    def get_symbols(self) -> List[str]:
        """Mode에 따라 필터/정렬 후 심볼 리스트 반환"""
        ...
```

---

## 🎯 동작 예시

### 1. SINGLE 모드 (기존 방식)

```python
config = SymbolUniverseConfig(
    mode=SymbolUniverseMode.SINGLE,
    single_symbol="BTCUSDT"
)
universe = SymbolUniverse(config, DummySymbolSource())
symbols = universe.get_symbols()

# Result: ["BTCUSDT"]
```

### 2. FIXED_LIST 모드 (수동 선택)

```python
config = SymbolUniverseConfig(
    mode=SymbolUniverseMode.FIXED_LIST,
    whitelist=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
    blacklist=["BUSDUSDT"]  # Stablecoin 제외
)
universe = SymbolUniverse(config, DummySymbolSource())
symbols = universe.get_symbols()

# Result: ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
```

### 3. TOP_N 모드 (거래량 상위 N개)

```python
config = SymbolUniverseConfig(
    mode=SymbolUniverseMode.TOP_N,
    top_n=20,
    base_quote="USDT",
    min_24h_quote_volume=1_000_000_000.0,  # 1B 이상만
    blacklist=["BUSDUSDT", "USDCUSDT"]  # Stablecoins 제외
)
universe = SymbolUniverse(config, DummySymbolSource())
symbols = universe.get_symbols()

# Result: 상위 20개 (필터링 + 정렬 후)
# ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", ...]
```

### 4. FULL_MARKET 모드 (전체 시장)

```python
config = SymbolUniverseConfig(
    mode=SymbolUniverseMode.FULL_MARKET,
    base_quote="USDT",
    min_24h_quote_volume=500_000_000.0,  # 500M 이상만
    blacklist=["BUSDUSDT", "USDCUSDT", "BTCBULL", "BTCBEAR"]
)
universe = SymbolUniverse(config, DummySymbolSource())
symbols = universe.get_symbols()

# Result: 필터링 후 전체 심볼 (volume 기준 정렬)
# ["BTCUSDT", "ETHUSDT", "BNBUSDT", ..., "LINKUSDT"]
```

---

## 📊 필터링 파이프라인

SymbolUniverse는 다음 순서로 필터링/정렬을 수행합니다:

```
1. Source에서 전체 심볼 조회
   └─> source.get_all_symbols() -> List[SymbolInfo]

2. Quote asset 필터
   └─> base_quote="USDT" 인 심볼만

3. Blacklist 제외
   └─> blacklist에 포함된 심볼 제거

4. Whitelist 적용 (있는 경우)
   └─> whitelist에 포함된 심볼만 (TOP_N, FULL_MARKET에서는 optional)

5. Volume threshold 필터
   └─> volume_24h_quote >= min_24h_quote_volume

6. Volume 기준 정렬 (내림차순)
   └─> TOP_N: 상위 N개 선택
   └─> FULL_MARKET: 전체 반환
```

---

## 🔧 Config 통합

### ArbitrageConfig에 universe 필드 추가

```python
@dataclass(frozen=True)
class ArbitrageConfig:
    # ...
    
    # D73-1: Symbol Universe (멀티심볼 지원)
    universe: SymbolUniverseConfig = field(
        default_factory=lambda: SymbolUniverseConfig()
    )
```

### YAML 설정 예시

```yaml
# configs/development.yml

universe:
  mode: TOP_N
  exchange: binance_futures
  top_n: 20
  base_quote: USDT
  blacklist:
    - BUSDUSDT
    - USDCUSDT
  min_24h_quote_volume: 1000000000.0  # 1B
```

---

## ✅ 테스트 결과

### 테스트 커버리지

| Test Case | 결과 |
|-----------|------|
| SINGLE 모드 | ✅ PASS |
| FIXED_LIST 모드 (whitelist) | ✅ PASS |
| FIXED_LIST 모드 (whitelist + blacklist) | ✅ PASS |
| TOP_N 모드 (필터 없음) | ✅ PASS |
| TOP_N 모드 (blacklist) | ✅ PASS |
| TOP_N 모드 (volume threshold) | ✅ PASS |
| FULL_MARKET 모드 (전체) | ✅ PASS |
| FULL_MARKET 모드 (blacklist) | ✅ PASS |
| FULL_MARKET 모드 (volume threshold) | ✅ PASS |
| Config Validation (SINGLE) | ✅ PASS |
| Config Validation (FIXED_LIST) | ✅ PASS |
| Config Validation (TOP_N) | ✅ PASS |
| Config Integration | ✅ PASS |

**Total: 13/13 PASS (100%)**

### 실행 방법

```bash
python scripts/test_d73_1_symbol_universe.py
```

---

## 🚀 향후 확장 포인트

### D73-2: Per-Symbol Engine Loop

- SymbolUniverse를 Engine loop에 통합
- 심볼별 독립 코루틴 구조 구현

```python
async def run_multi_symbol_engine():
    symbols = universe.get_symbols()
    tasks = [
        asyncio.create_task(
            run_symbol_engine(symbol, shared_portfolio, shared_guard)
        )
        for symbol in symbols
    ]
    await asyncio.gather(*tasks)
```

### D73-2: 실제 거래소 API 통합

**BinanceSymbolSource 구현:**
```python
class BinanceSymbolSource:
    async def get_all_symbols(self) -> List[SymbolInfo]:
        # Binance API /fapi/v1/exchangeInfo 호출
        # 24h ticker 데이터로 volume 채우기
        pass
```

**UpbitSymbolSource 구현:**
```python
class UpbitSymbolSource:
    async def get_all_symbols(self) -> List[SymbolInfo]:
        # Upbit API /v1/market/all 호출
        # 24h ticker 데이터로 volume 채우기
        pass
```

### D73-3: Multi-Symbol RiskGuard 통합

- SymbolUniverse → RiskGuard 연동
- 심볼별 리스크 한도 자동 분배

```python
class MultiSymbolRiskGuard:
    def __init__(self, symbols: List[str], total_capital: float):
        # Per-symbol capital allocation
        self.symbol_limits = self._allocate_capital(symbols, total_capital)
```

### D73-4: Small-Scale Integration Test

- Top-10 심볼 PAPER 모드 통합 테스트
- 5분 캠페인 실행 (Entry/Exit/PnL 검증)
- Multi-symbol snapshot 저장/복원 테스트

---

## 📁 생성된 파일

| 파일 | 라인 수 | 설명 |
|------|---------|------|
| `arbitrage/symbol_universe.py` | ~500 | Symbol Universe 핵심 모듈 |
| `config/base.py` | +28 | SymbolUniverseConfig 추가 |
| `scripts/test_d73_1_symbol_universe.py` | ~350 | 통합 테스트 스크립트 |
| `docs/D73_1_SYMBOL_UNIVERSE.md` | ~400 | 본 문서 |

**Total: ~1,278 lines (코드 + 문서)**

---

## 🎓 핵심 학습 내용

### 설계 원칙

1. **Single Responsibility Principle**
   - Universe는 오직 심볼 선택만 책임
   - 거래 로직은 Engine에서 처리

2. **Open/Closed Principle**
   - AbstractSymbolSource로 확장 가능
   - 새 거래소 추가 시 기존 코드 수정 불필요

3. **Dependency Inversion**
   - SymbolUniverse는 추상화에 의존
   - 구체 구현은 DI로 주입

### 하위 호환성 보장

- SINGLE 모드 = 기존 단일 심볼 방식과 100% 동일
- Config 기본값으로 기존 동작 유지
- 기존 Engine 코드 변경 없음 (D73-2에서 연동)

### 테스트 주도 개발

- 구현 전 테스트 케이스 설계
- 외부 API 의존 없는 DummySymbolSource
- 6개 테스트 그룹, 13개 테스트 케이스, 100% 통과

---

## 📝 Acceptance Criteria (D73-1)

- ✅ 4가지 모드 모두 동작 (config 기반 전환)
- ✅ Top-20 심볼 리스트 실시간 조회 가능 (DummySymbolSource 기준)
- ✅ 심볼 변경 시 엔진 재시작 없이 적용 가능 (설계 완료, D73-2에서 통합)
- ✅ Config 통합 (ArbitrageConfig.universe)
- ✅ 테스트 100% 통과
- ✅ 문서화 완료

---

**Status:** ✅ D73-1 COMPLETED  
**Next:** D73-2 Per-Symbol Engine Loop 구현

**Author:** D73-1 Implementation Team  
**Date:** 2025-11-21
