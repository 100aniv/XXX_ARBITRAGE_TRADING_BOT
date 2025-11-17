# D43 Arbitrage Live Runner Guide

**Document Version:** 1.0  
**Date:** 2025-11-17  
**Status:** ✅ Paper-First Foundation  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [핵심 개념](#핵심-개념)
4. [사용 방법](#사용-방법)
5. [Paper 모드](#paper-모드)
6. [테스트](#테스트)

---

## 개요

D43는 **ArbitrageEngine + Exchange Adapter를 연결하는 실시간 루프**입니다.

### 특징

- ✅ D37 ArbitrageEngine 그대로 사용
- ✅ D42 Exchange Adapter 그대로 사용
- ✅ Paper 모드 100% 우선 (실거래 X)
- ✅ 실시간 호가 폴링 및 신호 생성
- ✅ 주문 실행 및 포지션 관리
- ✅ 통계 및 모니터링
- ✅ 100% mock 기반 테스트

### 목적

- Upbit 현물 vs Binance 선물 아비트라지 **실시간 시뮬레이션**
- 로컬 PC + Docker Desktop에서 실행 가능
- 실거래 전 Paper 모드로 완전 검증

---

## 아키텍처

### 실시간 루프 구조

```
┌─────────────────────────────────────────┐
│   ArbitrageLiveRunner.run_forever()     │
└──────────────┬──────────────────────────┘
               │
    ┌──────────▼──────────┐
    │  1. build_snapshot()│
    │  (호가 수집)         │
    └──────────┬──────────┘
               │
    ┌──────────▼──────────────────┐
    │  2. process_snapshot()      │
    │  (엔진 신호 생성)            │
    └──────────┬──────────────────┘
               │
    ┌──────────▼──────────────────┐
    │  3. execute_trades()        │
    │  (주문 실행)                 │
    └──────────┬──────────────────┘
               │
    ┌──────────▼──────────────────┐
    │  sleep(poll_interval)       │
    │  (대기)                      │
    └──────────┬──────────────────┘
               │
        (반복 또는 종료)
```

### 거래 흐름

```
Exchange A (Upbit 역할)          Exchange B (Binance 역할)
    │                                 │
    ├─ get_orderbook()                ├─ get_orderbook()
    │                                 │
    └─────────────┬───────────────────┘
                  │
         ┌────────▼────────┐
         │ OrderBookSnapshot│
         └────────┬────────┘
                  │
         ┌────────▼──────────────┐
         │ ArbitrageEngine       │
         │ .on_snapshot()        │
         └────────┬──────────────┘
                  │
         ┌────────▼──────────────┐
         │ ArbitrageTrade[]      │
         │ (신규/종료 거래)       │
         └────────┬──────────────┘
                  │
    ┌─────────────┴──────────────┐
    │                            │
┌───▼────────┐          ┌───────▼──┐
│create_order│          │create_order
│(Exchange A)│          │(Exchange B)
└────────────┘          └───────────┘
```

---

## 핵심 개념

### ArbitrageLiveConfig

Live Runner 설정:

```python
@dataclass
class ArbitrageLiveConfig:
    symbol_a: str                    # "KRW-BTC"
    symbol_b: str                    # "BTCUSDT"
    min_spread_bps: float = 30.0    # 최소 스프레드
    taker_fee_a_bps: float = 5.0    # 수수료 A
    taker_fee_b_bps: float = 5.0    # 수수료 B
    slippage_bps: float = 5.0       # 슬리피지
    max_position_usd: float = 1000.0 # 최대 거래 규모
    poll_interval_seconds: float = 1.0  # 폴링 간격
    mode: str = "paper"             # "paper" | "live"
    max_runtime_seconds: Optional[int] = None  # 최대 런타임
```

### ArbitrageLiveRunner

핵심 메서드:

```python
class ArbitrageLiveRunner:
    def build_snapshot() -> OrderBookSnapshot:
        """두 거래소 호가 수집"""
    
    def process_snapshot(snapshot) -> List[ArbitrageTrade]:
        """엔진 신호 생성"""
    
    def execute_trades(trades) -> None:
        """주문 실행"""
    
    def run_once() -> bool:
        """1회 루프"""
    
    def run_forever() -> None:
        """무한 루프 (또는 max_runtime_seconds)"""
    
    def get_stats() -> Dict:
        """통계 조회"""
```

---

## 사용 방법

### 1. 설정 파일 준비

```yaml
# configs/live/arbitrage_live_paper_example.yaml
exchanges:
  type_a: "paper"
  type_b: "paper"
  initial_balance_a:
    KRW: 1000000.0
  initial_balance_b:
    USDT: 10000.0

symbols:
  symbol_a: "KRW-BTC"
  symbol_b: "BTCUSDT"

engine:
  min_spread_bps: 30.0
  taker_fee_a_bps: 5.0
  taker_fee_b_bps: 5.0
  slippage_bps: 5.0
  max_position_usd: 1000.0

live:
  poll_interval_seconds: 1.0
  max_runtime_seconds: 60
```

### 2. CLI 실행 (Paper 모드)

```bash
# 기본 실행
python -m scripts.run_arbitrage_live \
  --config configs/live/arbitrage_live_paper_example.yaml \
  --mode paper

# 런타임 제한
python -m scripts.run_arbitrage_live \
  --config configs/live/arbitrage_live_paper_example.yaml \
  --mode paper \
  --max-runtime-seconds 60

# 디버그 로그
python -m scripts.run_arbitrage_live \
  --config configs/live/arbitrage_live_paper_example.yaml \
  --mode paper \
  --log-level DEBUG
```

### 3. Python API 사용

```python
from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig
from arbitrage.exchanges import PaperExchange
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig

# 엔진 생성
engine = ArbitrageEngine(
    ArbitrageConfig(
        min_spread_bps=30.0,
        taker_fee_a_bps=5.0,
        taker_fee_b_bps=5.0,
        slippage_bps=5.0,
        max_position_usd=1000.0,
    )
)

# Paper 거래소 생성
exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})

# 설정
config = ArbitrageLiveConfig(
    symbol_a="KRW-BTC",
    symbol_b="BTCUSDT",
    poll_interval_seconds=1.0,
    max_runtime_seconds=60,
)

# Runner 생성
runner = ArbitrageLiveRunner(
    engine=engine,
    exchange_a=exchange_a,
    exchange_b=exchange_b,
    config=config,
)

# 실행
runner.run_forever()

# 통계 조회
stats = runner.get_stats()
print(f"Total PnL: ${stats['total_pnl_usd']:.2f}")
```

---

## Paper 모드

### 특징

- ✅ 실제 API 호출 없음
- ✅ 메모리 기반 거래 시뮬레이션
- ✅ 즉시 체결 (Market Order)
- ✅ 완전 재현 가능한 테스트
- ✅ 네트워크 지연 없음

### 동작 방식

```python
# Paper 거래소 두 개 생성
exchange_a = PaperExchange(initial_balance={"KRW": 1000000.0})
exchange_b = PaperExchange(initial_balance={"USDT": 10000.0})

# 호가 설정 (테스트용)
from arbitrage.exchanges.base import OrderBookSnapshot
snapshot_a = OrderBookSnapshot(
    symbol="KRW-BTC",
    timestamp=time.time(),
    bids=[(100000.0, 1.0)],
    asks=[(101000.0, 1.0)],
)
exchange_a.set_orderbook("KRW-BTC", snapshot_a)

# 주문 생성 (즉시 체결)
order = exchange_a.create_order(
    symbol="KRW-BTC",
    side=OrderSide.BUY,
    qty=1.0,
    price=100000.0,
)

# 잔고 확인
balance = exchange_a.get_balance()
print(balance["KRW"].free)  # 900000.0 (1,000,000 - 100,000)
```

---

## 테스트

### 테스트 실행

```bash
# D43 테스트만
python -m pytest tests/test_d43_live_runner.py -v

# 모든 테스트 (D37~D43)
python -m pytest tests/ -v

# 특정 테스트
python -m pytest tests/test_d43_live_runner.py::TestBuildSnapshot -v
```

### 테스트 시나리오

1. **build_snapshot**: 호가 수집 검증
2. **process_snapshot**: 엔진 신호 생성 검증
3. **execute_trades**: 주문 실행 검증
4. **run_once**: 1회 루프 파이프라인 검증
5. **run_forever**: 최대 런타임 준수 검증
6. **no_network_calls**: Paper 모드에서 네트워크 호출 없음 검증

---

## 제한사항 (D43)

### 현재 지원하지 않음

- ❌ 실거래 모드 (D44에서 추가)
- ❌ 고급 리스크 관리 (D44에서 확장)
- ❌ 실시간 모니터링 대시보드 (D44에서 추가)
- ❌ 자동 매개변수 조정 (D45에서 추가)
- ❌ 여러 거래 쌍 동시 실행 (D45에서 확장)

### Paper 모드 제약

- 모든 주문이 즉시 체결 (실제 시장 조건 미반영)
- 호가 변동 없음 (고정 호가)
- 네트워크 지연 없음
- 부분 체결 없음

---

## 다음 단계 (D44+)

### D44: Live Runner 확장

- 실거래 모드 활성화 (Upbit/Binance 실 API)
- 고급 리스크 관리 (일일 손실 제한, 포지션 크기 조정)
- 실시간 모니터링 (대시보드, 알림)

### D45: 자동화 & 배포

- Docker 컨테이너화
- 자동 시작/중지
- 로그 및 메트릭 수집
- 여러 거래 쌍 동시 실행

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-17  
**상태:** ✅ Paper-First Foundation (실거래 준비 중)
