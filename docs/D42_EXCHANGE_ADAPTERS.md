# D42 Exchange Adapter Layer Guide

**Document Version:** 1.0  
**Date:** 2025-11-17  
**Status:** ✅ Foundation Layer  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [핵심 인터페이스](#핵심-인터페이스)
4. [구현된 어댑터](#구현된-어댑터)
5. [사용 방법](#사용-방법)
6. [안전 정책](#안전-정책)

---

## 개요

D42는 **실거래로 이어지는 거래소 어댑터 레이어**입니다.

### 특징

- ✅ 공통 인터페이스 (BaseExchange)
- ✅ Upbit Spot 어댑터
- ✅ Binance Futures 어댑터
- ✅ Paper (모의) 거래 모드
- ✅ 100% mock 기반 테스트
- ✅ API 키 보안 (환경 변수 기반)
- ✅ 실거래 활성화 제어

### 목적

- D37 ArbitrageEngine을 실제 거래소와 연결
- 로컬 PC + Docker Desktop 환경에서 단일 봇 v1 구현
- Upbit 현물 vs Binance 선물 아비트라지 거래

---

## 아키텍처

### 레이어 구조

```
┌─────────────────────────────────────┐
│   D37 ArbitrageEngine               │
│   (전략 로직, 백테스트)              │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   D42 Exchange Adapter Layer         │
│   (거래소 통합 인터페이스)            │
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────┬──────────┐
    │          │          │          │
┌───▼──┐  ┌───▼──┐  ┌───▼──┐  ┌───▼──┐
│Paper │  │Upbit │  │Binance  │ (추가)
│(Mock)│  │Spot  │  │Futures  │
└──────┘  └──────┘  └─────────┘
```

### 거래 흐름

```
로컬 PC (Docker Desktop)
    │
    ├─ D37 ArbitrageEngine
    │   ├─ 매수 신호 → Upbit Spot
    │   ├─ 매도 신호 → Binance Futures
    │   └─ 결과 수집
    │
    └─ D42 Exchange Adapter
        ├─ PaperExchange (테스트/모의)
        ├─ UpbitSpotExchange (실거래)
        └─ BinanceFuturesExchange (실거래)
```

---

## 핵심 인터페이스

### BaseExchange

모든 거래소 어댑터가 상속받는 추상 클래스.

```python
class BaseExchange(ABC):
    @abstractmethod
    def get_orderbook(self, symbol: str) -> OrderBookSnapshot:
        """호가 정보 조회"""
    
    @abstractmethod
    def get_balance(self) -> Dict[str, Balance]:
        """자산 잔고 조회"""
    
    @abstractmethod
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.LIMIT,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ) -> OrderResult:
        """주문 생성"""
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """주문 취소"""
    
    @abstractmethod
    def get_open_positions(self) -> List[Position]:
        """미결제 포지션 조회 (선물용)"""
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderResult:
        """주문 상태 조회"""
```

### 공통 데이터 구조

#### OrderBookSnapshot
```python
@dataclass
class OrderBookSnapshot:
    symbol: str
    timestamp: float
    bids: List[tuple]  # [(price, qty), ...]
    asks: List[tuple]  # [(price, qty), ...]
```

#### OrderResult
```python
@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: OrderSide
    qty: float
    price: Optional[float]
    order_type: OrderType
    status: OrderStatus
    filled_qty: float = 0.0
```

#### Balance
```python
@dataclass
class Balance:
    asset: str
    free: float
    locked: float
    
    @property
    def total(self) -> float:
        return self.free + self.locked
```

---

## 구현된 어댑터

### 1. PaperExchange (모의 거래)

**특징:**
- 실제 API 호출 없음
- 메모리 상에서 주문/체결/포지션 시뮬레이션
- 테스트 및 로컬 개발용

**사용 예:**
```python
from arbitrage.exchanges import PaperExchange

exchange = PaperExchange(
    initial_balance={"KRW": 1000000.0, "BTC": 0.0}
)

# 호가 설정 (테스트용)
from arbitrage.exchanges.base import OrderBookSnapshot
snapshot = OrderBookSnapshot(
    symbol="BTC-KRW",
    timestamp=time.time(),
    bids=[(100000.0, 1.0)],
    asks=[(101000.0, 1.0)],
)
exchange.set_orderbook("BTC-KRW", snapshot)

# 주문
order = exchange.create_order(
    symbol="BTC-KRW",
    side=OrderSide.BUY,
    qty=1.0,
    price=100000.0,
)

# 잔고 확인
balance = exchange.get_balance()
print(balance["KRW"].free)  # 900000.0
```

### 2. UpbitSpotExchange (Upbit 현물)

**특징:**
- Upbit REST API 기반
- KRW 마켓 위주
- 현물 거래만 (포지션 없음)
- 실거래 활성화 제어

**설정:**
```yaml
# configs/live/upbit_example.yaml
exchange:
  name: upbit
  type: spot

api:
  key: ${UPBIT_API_KEY}
  secret: ${UPBIT_API_SECRET}
  base_url: https://api.upbit.com
  timeout: 10

trading:
  live_enabled: false  # 실거래 비활성화 (기본값)
```

**사용 예:**
```python
from arbitrage.exchanges import UpbitSpotExchange

config = {
    "api_key": os.getenv("UPBIT_API_KEY"),
    "api_secret": os.getenv("UPBIT_API_SECRET"),
    "live_enabled": False,  # 테스트 모드
}

exchange = UpbitSpotExchange(config)

# 호가 조회
orderbook = exchange.get_orderbook("BTC-KRW")

# 잔고 조회
balance = exchange.get_balance()

# 주문 (live_enabled=False이면 RuntimeError 발생)
# order = exchange.create_order(...)
```

### 3. BinanceFuturesExchange (Binance 선물)

**특징:**
- Binance USDT-M Futures REST API 기반
- 선물/마진 거래
- 포지션 관리
- 레버리지 설정

**설정:**
```yaml
# configs/live/binance_futures_example.yaml
exchange:
  name: binance
  type: futures

api:
  key: ${BINANCE_API_KEY}
  secret: ${BINANCE_API_SECRET}
  base_url: https://fapi.binance.com
  timeout: 10

trading:
  live_enabled: false  # 실거래 비활성화 (기본값)
  leverage: 1
```

**사용 예:**
```python
from arbitrage.exchanges import BinanceFuturesExchange

config = {
    "api_key": os.getenv("BINANCE_API_KEY"),
    "api_secret": os.getenv("BINANCE_API_SECRET"),
    "leverage": 1,
    "live_enabled": False,  # 테스트 모드
}

exchange = BinanceFuturesExchange(config)

# 호가 조회
orderbook = exchange.get_orderbook("BTCUSDT")

# 포지션 조회
positions = exchange.get_open_positions()
```

---

## 사용 방법

### 1. 환경 변수 설정

```bash
# .env 파일 또는 쉘 환경 변수
export UPBIT_API_KEY="your_upbit_key"
export UPBIT_API_SECRET="your_upbit_secret"
export BINANCE_API_KEY="your_binance_key"
export BINANCE_API_SECRET="your_binance_secret"
```

### 2. 로컬 테스트 (Paper 모드)

```python
from arbitrage.exchanges import PaperExchange
from arbitrage.exchanges.base import OrderSide

# Paper 모드 (실거래 없음)
exchange = PaperExchange(
    initial_balance={"KRW": 1000000.0}
)

# 주문
order = exchange.create_order(
    symbol="BTC-KRW",
    side=OrderSide.BUY,
    qty=1.0,
    price=100000.0,
)

print(f"Order: {order.order_id}, Status: {order.status}")
```

### 3. 실거래 (Upbit/Binance)

```python
import os
from arbitrage.exchanges import UpbitSpotExchange

# 실거래 활성화
config = {
    "api_key": os.getenv("UPBIT_API_KEY"),
    "api_secret": os.getenv("UPBIT_API_SECRET"),
    "live_enabled": True,  # ⚠️ 실거래 활성화
}

exchange = UpbitSpotExchange(config)

# 주문 (실제 거래소로 전송)
order = exchange.create_order(
    symbol="BTC-KRW",
    side=OrderSide.BUY,
    qty=0.01,
    price=100000.0,
)
```

---

## 안전 정책

### API 키 관리

❌ **절대 금지:**
```python
# 하드코딩 금지
config = {
    "api_key": "abc123def456",  # ❌ 위험!
    "api_secret": "xyz789",      # ❌ 위험!
}
```

✅ **권장:**
```python
import os

# 환경 변수에서 읽기
config = {
    "api_key": os.getenv("UPBIT_API_KEY"),
    "api_secret": os.getenv("UPBIT_API_SECRET"),
}

# 또는 별도 보안 저장소
# - AWS Secrets Manager
# - HashiCorp Vault
# - 로컬 암호화 파일
```

### 실거래 활성화 제어

기본값: `live_enabled: false`

```python
# 테스트 모드 (기본값)
exchange = UpbitSpotExchange({"live_enabled": False})
exchange.create_order(...)  # RuntimeError 발생

# 실거래 모드 (명시적 활성화 필요)
exchange = UpbitSpotExchange({"live_enabled": True})
exchange.create_order(...)  # 실제 거래소로 전송
```

### 테스트 정책

- 모든 테스트는 **100% mock 기반**
- 실제 네트워크 호출 없음
- PaperExchange는 네트워크 불필요
- Upbit/Binance 테스트는 `unittest.mock.patch` 사용

---

## 다음 단계 (D43+)

### D43: ArbitrageEngine ↔ Exchange 통합

- D37 ArbitrageEngine을 D42 Exchange Adapter와 연결
- 실시간 호가 수집 → 신호 생성 → 주문 실행

### D44: 실시간 모니터링 & 대시보드

- 거래 상태 모니터링
- 포지션 추적
- 수익률 계산

### D45: 자동화 & 배포

- Docker 컨테이너화
- 자동 시작/중지
- 로그 및 알림

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-17  
**상태:** ✅ Foundation Layer (실거래 준비 완료)
