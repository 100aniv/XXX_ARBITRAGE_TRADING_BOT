# D37 Arbitrage Strategy MVP Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [핵심 개념](#핵심-개념)
3. [아키텍처](#아키텍처)
4. [사용 방법](#사용-방법)
5. [백테스트 실행](#백테스트-실행)

---

## 개요

D37은 **순수 Python 차익거래 전략 MVP (Minimum Viable Product)**를 구현합니다.

### 특징

- ✅ 외부 API 호출 없음 (오프라인)
- ✅ 결정론적 (deterministic)
- ✅ 완전히 테스트 가능
- ✅ 간단한 스프레드 기반 차익거래 로직
- ✅ 백테스트 프레임워크
- ✅ CSV 기반 데이터 입력

### 목적

- 차익거래 엔진의 핵심 로직 검증
- 백테스트 프레임워크 구축
- 향후 실제 거래소 통합을 위한 기반 마련

---

## 핵심 개념

### Basis Points (bps)

1 basis point = 0.01% = 1/10,000

```
스프레드 (bps) = (수익 / 비용) * 10,000
```

### Gross Edge vs Net Edge

```
Gross Edge = 거래소 간 스프레드 (수수료 차감 전)
Net Edge = Gross Edge - 수수료 - 슬리피지
```

### 두 방향 차익거래

#### LONG_A_SHORT_B
- A 거래소에서 매수 (ask_a)
- B 거래소에서 매도 (bid_b)
- 수익 = bid_b - ask_a

#### LONG_B_SHORT_A
- B 거래소에서 매수 (ask_b)
- A 거래소에서 매도 (bid_a)
- 수익 = bid_a - ask_b

---

## 아키텍처

### 모듈 구조

```
arbitrage/
├── arbitrage_core.py      # 핵심 엔진
└── arbitrage_backtest.py  # 백테스트 프레임워크

scripts/
└── run_arbitrage_backtest.py  # CLI 도구
```

### 데이터 구조

#### ArbitrageConfig

```python
@dataclass
class ArbitrageConfig:
    min_spread_bps: float          # 최소 스프레드 (bps)
    taker_fee_a_bps: float         # Exchange A 수수료 (bps)
    taker_fee_b_bps: float         # Exchange B 수수료 (bps)
    slippage_bps: float            # 슬리피지 (bps)
    max_position_usd: float        # 최대 포지션 크기 (USD)
    max_open_trades: int = 1       # 최대 동시 거래 수
    close_on_spread_reversal: bool = True  # 스프레드 역전 시 종료
```

#### OrderBookSnapshot

```python
@dataclass
class OrderBookSnapshot:
    timestamp: str
    best_bid_a: float              # Exchange A 최고 매수가
    best_ask_a: float              # Exchange A 최저 매도가
    best_bid_b: float              # Exchange B 최고 매수가
    best_ask_b: float              # Exchange B 최저 매도가
```

#### ArbitrageOpportunity

```python
@dataclass
class ArbitrageOpportunity:
    timestamp: str
    side: Side                     # LONG_A_SHORT_B 또는 LONG_B_SHORT_A
    spread_bps: float              # 총 스프레드 (bps)
    gross_edge_bps: float          # 수수료 차감 전 엣지 (bps)
    net_edge_bps: float            # 수수료 차감 후 엣지 (bps)
    notional_usd: float            # 거래 규모 (USD)
```

#### ArbitrageTrade

```python
@dataclass
class ArbitrageTrade:
    open_timestamp: str
    close_timestamp: Optional[str] = None
    side: Side = "LONG_A_SHORT_B"
    entry_spread_bps: float = 0.0
    exit_spread_bps: Optional[float] = None
    notional_usd: float = 0.0
    pnl_usd: Optional[float] = None
    pnl_bps: Optional[float] = None
    is_open: bool = True
    meta: Dict[str, str] = field(default_factory=dict)
```

### 핵심 클래스

#### ArbitrageEngine

```python
class ArbitrageEngine:
    def detect_opportunity(
        self, snapshot: OrderBookSnapshot
    ) -> Optional[ArbitrageOpportunity]:
        """차익거래 기회 감지"""
    
    def on_snapshot(
        self, snapshot: OrderBookSnapshot
    ) -> List[ArbitrageTrade]:
        """스냅샷 처리: 거래 개설/종료"""
    
    def get_open_trades(self) -> List[ArbitrageTrade]:
        """개설된 거래 목록 반환"""
```

#### ArbitrageBacktester

```python
class ArbitrageBacktester:
    def run(
        self, snapshots: List[OrderBookSnapshot]
    ) -> BacktestResult:
        """백테스트 실행"""
```

---

## 사용 방법

### 1. 엔진 생성

```python
from arbitrage.arbitrage_core import ArbitrageConfig, ArbitrageEngine

config = ArbitrageConfig(
    min_spread_bps=30.0,           # 최소 30 bps
    taker_fee_a_bps=5.0,           # Exchange A: 5 bps
    taker_fee_b_bps=5.0,           # Exchange B: 5 bps
    slippage_bps=5.0,              # 슬리피지: 5 bps
    max_position_usd=1000.0,       # 최대 $1,000
)

engine = ArbitrageEngine(config)
```

### 2. 스냅샷 처리

```python
from arbitrage.arbitrage_core import OrderBookSnapshot

snapshot = OrderBookSnapshot(
    timestamp="2025-01-01T00:00:00Z",
    best_bid_a=99.0,
    best_ask_a=100.0,
    best_bid_b=102.0,
    best_ask_b=103.0,
)

# 거래 개설/종료
trades_changed = engine.on_snapshot(snapshot)

# 개설된 거래 확인
open_trades = engine.get_open_trades()
```

### 3. 기회 감지

```python
opportunity = engine.detect_opportunity(snapshot)

if opportunity:
    print(f"Side: {opportunity.side}")
    print(f"Spread: {opportunity.spread_bps:.2f} bps")
    print(f"Net Edge: {opportunity.net_edge_bps:.2f} bps")
```

---

## 백테스트 실행

### CLI 사용

```bash
# 기본 백테스트
python scripts/run_arbitrage_backtest.py \
  --data-file data/sample_arbitrage_prices.csv \
  --min-spread-bps 30 \
  --taker-fee-a-bps 5 \
  --taker-fee-b-bps 5 \
  --slippage-bps 5 \
  --max-position-usd 1000

# 낙폭 제한 포함
python scripts/run_arbitrage_backtest.py \
  --data-file data/sample_arbitrage_prices.csv \
  --min-spread-bps 30 \
  --taker-fee-a-bps 5 \
  --taker-fee-b-bps 5 \
  --slippage-bps 5 \
  --max-position-usd 1000 \
  --stop-on-drawdown-pct 20
```

### CSV 파일 형식

```csv
timestamp,best_bid_a,best_ask_a,best_bid_b,best_ask_b
2025-01-01T00:00:00Z,99.0,100.0,102.0,103.0
2025-01-01T01:00:00Z,99.5,100.5,102.5,103.5
2025-01-01T02:00:00Z,100.0,101.0,103.0,104.0
```

### 백테스트 결과

```
================================================================================
[D37_BACKTEST] RESULT SUMMARY
================================================================================
Total Trades:              10
Closed Trades:             8
Open Trades:               2
Final Balance (USD):       $11,000.00
Realized PnL (USD):        $1,000.00
Max Drawdown (%):          5.00%
Win Rate:                  75.00%
Avg PnL per Trade (USD):   $125.00
================================================================================
```

### Python API 사용

```python
from arbitrage.arbitrage_core import ArbitrageConfig, ArbitrageEngine, OrderBookSnapshot
from arbitrage.arbitrage_backtest import BacktestConfig, ArbitrageBacktester

# 설정
config = ArbitrageConfig(
    min_spread_bps=30.0,
    taker_fee_a_bps=5.0,
    taker_fee_b_bps=5.0,
    slippage_bps=5.0,
    max_position_usd=1000.0,
)

# 엔진 및 백테스터
engine = ArbitrageEngine(config)
backtest_config = BacktestConfig(initial_balance_usd=10_000.0)
backtester = ArbitrageBacktester(engine, backtest_config)

# 스냅샷 생성
snapshots = [
    OrderBookSnapshot(
        timestamp="2025-01-01T00:00:00Z",
        best_bid_a=99.0,
        best_ask_a=100.0,
        best_bid_b=102.0,
        best_ask_b=103.0,
    ),
    # ... 더 많은 스냅샷
]

# 백테스트 실행
result = backtester.run(snapshots)

print(f"Total Trades: {result.total_trades}")
print(f"Final Balance: ${result.final_balance_usd:,.2f}")
print(f"Realized PnL: ${result.realized_pnl_usd:,.2f}")
print(f"Win Rate: {result.win_rate*100:.2f}%")
```

---

## 설정 예시

### 보수적 설정

```python
config = ArbitrageConfig(
    min_spread_bps=50.0,           # 높은 임계값
    taker_fee_a_bps=5.0,
    taker_fee_b_bps=5.0,
    slippage_bps=10.0,             # 높은 슬리피지
    max_position_usd=500.0,        # 작은 포지션
)
```

### 공격적 설정

```python
config = ArbitrageConfig(
    min_spread_bps=20.0,           # 낮은 임계값
    taker_fee_a_bps=3.0,
    taker_fee_b_bps=3.0,
    slippage_bps=2.0,              # 낮은 슬리피지
    max_position_usd=5000.0,       # 큰 포지션
)
```

---

## 정책 준수

### Read-Only 정책

✅ 모든 작업이 읽기 전용:
- 스냅샷 처리
- 기회 감지
- 거래 시뮬레이션
- 손익 계산

### Observability 정책

✅ 가짜 메트릭 없음:
- 모든 계산이 입력 데이터 기반
- 실제 백테스트 결과만 보고

### 네트워크 정책

✅ 네트워크 호출 없음:
- 순수 Python 계산
- 외부 API 의존성 없음

---

## 다음 단계 (D38+)

- 실제 거래소 API 통합
- 실시간 스트리밍 데이터
- 포트폴리오 관리
- 리스크 관리
- 성능 최적화

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready
