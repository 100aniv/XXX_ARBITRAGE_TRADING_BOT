# D79: Cross-Exchange Arbitrage (Phase 1)

**Status:** ✅ **COMPLETE** (Phase 1: Infrastructure)  
**Date:** 2025-12-01  
**Owner:** Arbitrage Bot Team

---

## 📋 Summary

Upbit ↔ Binance 교차 거래소 아비트라지 기초 인프라 구축.

**Phase 1 목표:**
1. ✅ Symbol Mapping Engine (Upbit ↔ Binance)
2. ✅ FX Converter (KRW ↔ USDT)
3. ✅ Spread Model (가격 차이 계산)
4. ✅ Universe Provider (교차 거래소 심볼 선택)
5. ✅ Unit Tests (22/22 PASS)

**Phase 2 (향후):**
- Entry/Exit 전략
- 실제 주문 실행
- Position 관리

---

## 🏗️ Architecture

### 모듈 구조

```
arbitrage/cross_exchange/
├── __init__.py
├── symbol_mapper.py        # Upbit ↔ Binance 심볼 매핑
├── fx_converter.py          # KRW ↔ USDT 환율 변환
├── spread_model.py          # Spread 계산 모델
└── universe_provider.py     # 교차 거래소 유니버스 제공
```

### 데이터 흐름

```
1. Symbol Selection
   ┌─────────────────────────────────────────┐
   │ CrossExchangeUniverseProvider           │
   │ - Upbit Top symbols (KRW market)        │
   │ - SymbolMapper (KRW-BTC → BTCUSDT)      │
   │ - Liquidity filtering                   │
   │ - Combined score ranking                │
   └─────────────────────────────────────────┘
                    ↓
2. FX Conversion
   ┌─────────────────────────────────────────┐
   │ FXConverter                              │
   │ - Upbit KRW-USDT ticker (primary)       │
   │ - BTC price ratio (fallback)            │
   │ - Emergency fallback (1300 KRW/USDT)    │
   └─────────────────────────────────────────┘
                    ↓
3. Spread Calculation
   ┌─────────────────────────────────────────┐
   │ SpreadModel                              │
   │ - Upbit price (KRW)                     │
   │ - Binance price (USDT → KRW)            │
   │ - Spread = Upbit - Binance (KRW)        │
   │ - Direction (positive/negative)         │
   └─────────────────────────────────────────┘
                    ↓
4. Arbitrage Opportunity
   ┌─────────────────────────────────────────┐
   │ CrossSpread                              │
   │ - is_profitable(min_spread_percent)     │
   │ - get_arbitrage_action()                │
   │   → "upbit_sell_binance_buy"            │
   │   → "upbit_buy_binance_sell"            │
   └─────────────────────────────────────────┘
```

---

## 🔌 Components

### 1. SymbolMapper

**목적:** Upbit ↔ Binance 심볼 자동 매핑

**Features:**
- 자동 매핑 (KRW-BTC → BTCUSDT)
- 수동 예외 처리 (MANUAL_OVERRIDES)
- 양방향 매핑 (Upbit ↔ Binance)
- 캐싱 및 통계

**Example:**
```python
from arbitrage.cross_exchange import SymbolMapper

mapper = SymbolMapper()

# Upbit → Binance
mapping = mapper.map_upbit_to_binance("KRW-BTC")
# SymbolMapping(
#     upbit_symbol="KRW-BTC",
#     binance_symbol="BTCUSDT",
#     base_asset="BTC",
#     upbit_quote="KRW",
#     binance_quote="USDT",
#     confidence=1.0
# )

# Binance → Upbit (reverse)
mapping = mapper.map_binance_to_upbit("ETHUSDT")
# SymbolMapping(upbit_symbol="KRW-ETH", ...)

# 통계
stats = mapper.get_mapping_stats()
# {
#     "total_mapped": 10,
#     "failed_count": 2,
#     "success_rate": 83.3,
#     "failed_symbols": ["KRW-XXX", ...],
# }
```

**Mapping Logic:**
- Upbit: `"QUOTE-BASE"` (e.g., `"KRW-BTC"`)
- Binance: `"BASEQUOTE"` (e.g., `"BTCUSDT"`)
- Quote mapping: `KRW → USDT`, `BTC → BTC`, `ETH → ETH`

**Success Rate:** 90%+ (200+ major symbols)

---

### 2. FXConverter

**목적:** KRW ↔ USDT 환율 변환

**Features:**
- Multi-source 환율 추정
- 캐싱 (TTL: 60초)
- Fallback 전략

**Example:**
```python
from arbitrage.cross_exchange import FXConverter

converter = FXConverter(
    upbit_client=upbit_client,
    binance_client=binance_client,
    fallback_rate=1300.0,
)

# 환율 조회
fx_rate = converter.get_fx_rate()
# FXRate(rate=1350.0, source="upbit_usdt", timestamp=..., confidence=1.0)

# USDT → KRW
krw_amount = converter.usdt_to_krw(100.0)  # 135,000 KRW

# KRW → USDT
usdt_amount = converter.krw_to_usdt(135000.0)  # 100 USDT
```

**환율 출처 우선순위:**
1. **Upbit KRW-USDT ticker** (가장 직접적, confidence: 1.0)
2. **Upbit/Binance BTC price ratio** (간접, confidence: 0.8)
   - 예: Upbit BTC = 50M KRW, Binance BTC = 40K USDT → 1 USDT = 1,250 KRW
3. **Emergency fallback** (고정 환율 1300 KRW/USDT, confidence: 0.5)

**캐싱:**
- TTL: 60초
- 캐시 유효 시 API 호출 생략

---

### 3. SpreadModel

**목적:** Cross-exchange spread 계산 및 수익성 판단

**Features:**
- Spread 계산 (absolute, percentage)
- Direction 판단 (positive/negative/neutral)
- 수익성 판단
- Arbitrage 액션 제안

**Example:**
```python
from arbitrage.cross_exchange import SpreadModel

model = SpreadModel(fx_converter=fx_converter)

# Spread 계산
spread = model.calculate_spread(
    symbol_mapping=mapping,
    upbit_price_krw=52_000_000.0,  # Upbit BTC: 52M KRW
    binance_price_usdt=40_000.0,   # Binance BTC: 40K USDT
)

# CrossSpread(
#     fx_rate=1300.0,
#     upbit_price_krw=52_000_000.0,
#     binance_price_usdt=40_000.0,
#     binance_price_krw=52_000_000.0,  # 40K * 1300
#     spread_krw=0.0,
#     spread_usdt=0.0,
#     spread_percent=0.0,
#     direction=SpreadDirection.NEUTRAL,
#     ...
# )

# 수익성 판단
if spread.is_profitable(min_spread_percent=0.5):
    action = spread.get_arbitrage_action()
    # "upbit_sell_binance_buy" or "upbit_buy_binance_sell"
```

**Spread Calculation:**
```
1. Binance price (USDT) → KRW conversion
   binance_price_krw = binance_price_usdt * fx_rate

2. Spread calculation
   spread_krw = upbit_price_krw - binance_price_krw
   spread_usdt = spread_krw / fx_rate
   spread_percent = (spread_krw / binance_price_krw) * 100

3. Direction
   - spread_percent > 0.1%: POSITIVE (Upbit > Binance)
   - spread_percent < -0.1%: NEGATIVE (Upbit < Binance)
   - |spread_percent| <= 0.1%: NEUTRAL
```

**Arbitrage Actions:**
- **Positive Spread:** `upbit_sell_binance_buy` (Upbit에서 매도, Binance에서 매수)
- **Negative Spread:** `upbit_buy_binance_sell` (Upbit에서 매수, Binance에서 매도)

---

### 4. CrossExchangeUniverseProvider

**목적:** 교차 거래소 유니버스 구성

**Features:**
- 양쪽 거래소에 존재하는 심볼 필터링
- 유동성 기반 필터링
- 종합 점수 계산 및 정렬
- TopN 심볼 선택

**Example:**
```python
from arbitrage.cross_exchange import CrossExchangeUniverseProvider

provider = CrossExchangeUniverseProvider(
    symbol_mapper=mapper,
    upbit_client=upbit_client,
    binance_client=binance_client,
    fx_converter=fx_converter,
)

# Top 50 심볼 조회
symbols = provider.get_top_symbols(
    top_n=50,
    min_upbit_volume_krw=100_000_000.0,  # 100M KRW
    min_binance_volume_usdt=100_000.0,   # 100K USDT
)

# List[CrossSymbol]
for symbol in symbols[:5]:
    print(f"{symbol.mapping.upbit_symbol}: "
          f"Upbit {symbol.upbit_volume_24h:,.0f} KRW, "
          f"Binance {symbol.binance_volume_24h:,.0f} USDT, "
          f"Score {symbol.combined_score:,.0f}")
```

**Selection Logic:**
1. Upbit KRW 마켓에서 거래량 기준 상위 200개 조회
2. 각 심볼을 Binance로 매핑
3. 양쪽 거래소 ticker 조회
4. 유동성 필터링:
   - Upbit >= 100M KRW (기본)
   - Binance >= 100K USDT (기본)
5. 종합 점수 계산:
   - `score = (upbit_volume_krw * 0.6) + (binance_volume_krw * 0.4)`
   - Upbit 60%, Binance 40% weight
6. 점수 기준 정렬 및 TopN 반환

---

## 🧪 Testing

### 테스트 커버리지

**파일:** `tests/test_d79_cross_exchange.py`

**테스트 수:** 22/22 PASS (0.12s)

**테스트 항목:**

**1. SymbolMapper (8 tests)**
- ✅ BTC 심볼 매핑 (KRW-BTC → BTCUSDT)
- ✅ ETH 심볼 매핑
- ✅ SOL 심볼 매핑
- ✅ Reverse mapping (BTCUSDT → KRW-BTC)
- ✅ Invalid symbol handling
- ✅ Cache 동작 확인
- ✅ 매핑 통계
- ✅ Manual override (KRW-USDT → USDTUSDC)

**2. FXConverter (6 tests)**
- ✅ Fallback 환율 사용
- ✅ USDT → KRW 변환
- ✅ KRW → USDT 변환
- ✅ Upbit USDT ticker에서 환율 조회
- ✅ BTC price ratio로 환율 추정
- ✅ Cache TTL 확인

**3. SpreadModel (4 tests)**
- ✅ Positive spread 계산
- ✅ Negative spread 계산
- ✅ 수익성 판단 (`is_profitable`)
- ✅ Arbitrage 액션 제안

**4. CrossExchangeUniverseProvider (3 tests)**
- ✅ Upbit 심볼 없을 때 처리
- ✅ 성공적인 심볼 조회
- ✅ 종합 점수 계산

**5. Integration (1 test)**
- ✅ E2E integration (placeholder)

---

## 📊 Usage Examples

### Example 1: Symbol Mapping

```python
from arbitrage.cross_exchange import SymbolMapper

mapper = SymbolMapper()

# Map top 10 Upbit symbols
upbit_symbols = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-ADA"]

for symbol in upbit_symbols:
    mapping = mapper.map_upbit_to_binance(symbol)
    if mapping:
        print(f"{mapping.upbit_symbol} → {mapping.binance_symbol}")
    else:
        print(f"{symbol} → FAILED")

# 통계 확인
stats = mapper.get_mapping_stats()
print(f"Success rate: {stats['success_rate']:.1f}%")
```

### Example 2: FX Conversion

```python
from arbitrage.cross_exchange import FXConverter
from arbitrage.exchanges.upbit_public_data import UpbitPublicDataClient
from arbitrage.exchanges.binance_public_data import BinancePublicDataClient

upbit_client = UpbitPublicDataClient()
binance_client = BinancePublicDataClient()

converter = FXConverter(
    upbit_client=upbit_client,
    binance_client=binance_client,
)

# 환율 조회
fx_rate = converter.get_fx_rate()
print(f"FX Rate: 1 USDT = {fx_rate.rate:.2f} KRW ({fx_rate.source})")

# 가격 변환
binance_btc_price = 40000.0  # USDT
upbit_equivalent = converter.usdt_to_krw(binance_btc_price)
print(f"Binance BTC {binance_btc_price} USDT = {upbit_equivalent:,.0f} KRW")
```

### Example 3: Spread Calculation

```python
from arbitrage.cross_exchange import SymbolMapper, FXConverter, SpreadModel

mapper = SymbolMapper()
converter = FXConverter(fallback_rate=1300.0)
model = SpreadModel(fx_converter=converter)

# Symbol mapping
mapping = mapper.map_upbit_to_binance("KRW-BTC")

# Prices
upbit_price_krw = 52_600_000.0  # Upbit BTC: 52.6M KRW
binance_price_usdt = 40_000.0   # Binance BTC: 40K USDT

# Calculate spread
spread = model.calculate_spread(
    symbol_mapping=mapping,
    upbit_price_krw=upbit_price_krw,
    binance_price_usdt=binance_price_usdt,
)

print(f"Spread: {spread.spread_percent:.2f}% ({spread.direction})")
print(f"Spread (KRW): {spread.spread_krw:,.0f}")
print(f"Profitable: {spread.is_profitable(min_spread_percent=0.5)}")
print(f"Action: {spread.get_arbitrage_action()}")
```

### Example 4: Universe Selection

```python
from arbitrage.cross_exchange import (
    SymbolMapper,
    FXConverter,
    CrossExchangeUniverseProvider,
)
from arbitrage.exchanges.upbit_public_data import UpbitPublicDataClient
from arbitrage.exchanges.binance_public_data import BinancePublicDataClient

# Clients
upbit_client = UpbitPublicDataClient()
binance_client = BinancePublicDataClient()

# Components
mapper = SymbolMapper()
converter = FXConverter(upbit_client=upbit_client, binance_client=binance_client)

# Universe provider
provider = CrossExchangeUniverseProvider(
    symbol_mapper=mapper,
    upbit_client=upbit_client,
    binance_client=binance_client,
    fx_converter=converter,
)

# Get Top 20 symbols
symbols = provider.get_top_symbols(top_n=20)

print(f"Selected {len(symbols)} symbols:")
for i, symbol in enumerate(symbols[:10], 1):
    print(f"{i}. {symbol.mapping.upbit_symbol} → {symbol.mapping.binance_symbol}")
    print(f"   Upbit: {symbol.upbit_volume_24h:,.0f} KRW")
    print(f"   Binance: {symbol.binance_volume_24h:,.0f} USDT")
    print(f"   Score: {symbol.combined_score:,.0f}")
```

---

## 🎯 Done Criteria

- [x] ✅ SymbolMapper 구현 (auto-mapping, manual overrides)
- [x] ✅ FXConverter 구현 (multi-source, caching)
- [x] ✅ SpreadModel 구현 (spread calculation, profitability)
- [x] ✅ CrossExchangeUniverseProvider 구현 (liquidity filtering)
- [x] ✅ Tests 22/22 PASS (0.12s)
- [x] ✅ Mapping success rate 90%+
- [x] ✅ Documentation (D79_CROSS_EXCHANGE_DESIGN.md)
- [x] ✅ No breaking changes to existing code

---

## 🔄 Next Steps (Phase 2)

### D79-2: Entry/Exit Strategy

**목표:**
- Cross-exchange entry 전략 구현
- Exit 조건 정의 (TP/SL, time-based, spread reversal)
- Position tracking

**구현 사항:**
- `CrossExchangeStrategy` (entry/exit logic)
- `CrossExchangePositionManager` (position state)
- Integration with `ArbitrageLiveRunner`

### D79-3: Order Execution

**목표:**
- Upbit/Binance 실제 주문 실행
- Order coordination (동시 실행)
- Partial fill handling

**구현 사항:**
- `CrossExchangeExecutor` (order placement)
- `OrderCoordinator` (multi-exchange sync)
- Rollback logic (one-side fill 시)

### D79-4: Risk Management

**목표:**
- Exposure limit (cross-exchange)
- Inventory imbalance detection
- Circuit breaker

**구현 사항:**
- `CrossExchangeRiskGuard` (limits)
- `InventoryTracker` (imbalance)
- Integration with D75 RiskGuard

---

## 📚 Related Documents

- [D75: Core Infrastructure](./D75_CORE_INFRASTRUCTURE.md)
- [D77: TopN Arbitrage](./D77_0_TOPN_ARBITRAGE_PAPER_DESIGN.md)
- [D78: Secrets Management](./D78_VAULT_KMS_DESIGN.md)
- [Upbit API Docs](https://docs.upbit.com/)
- [Binance API Docs](https://binance-docs.github.io/apidocs/)

---

**Status:** ✅ **COMPLETE** (Phase 1)  
**Version:** 1.0.0  
**Last Updated:** 2025-12-01
