# V2 Architecture - Engine-Centric Flow

**Version:** 1.0  
**Status:** DESIGN  
**Owner:** V2 Team

---

## 🎯 Design Goals

### 1. Engine-Centric (Not Script-Centric)
- ❌ **V1 Problem:** 65+ run_*.py scripts, 일회성 실험 난립
- ✅ **V2 Solution:** Single Engine + Adapter Pattern
- **Result:** 재사용성, 테스트 가능성 향상

### 2. Semantic Layer (Not Exchange-Specific)
- ❌ **V1 Problem:** 거래소별 payload 로직이 Runner에 혼재
- ✅ **V2 Solution:** OrderIntent → Adapter 분리
- **Result:** 의미(MARKET BUY) vs 구현(Upbit payload) 분리

### 3. Mock-First Testing
- ❌ **V1 Problem:** PAPER 모드도 실 API 호출 (느리고 불안정)
- ✅ **V2 Solution:** Mock/Stub Adapter로 로직 검증
- **Result:** 빠른 피드백, 실거래 리스크 제거

---

## 🏗️ Core Components

### 1. OrderIntent (Semantic Layer)

**Purpose:** 거래소 독립적인 주문 의도 표현

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass
class OrderIntent:
    """
    거래소 독립적인 주문 의도.
    
    MARKET 주문 규약:
    - BUY MARKET: quote_amount 필수 (KRW/USDT 등 매수 금액)
    - SELL MARKET: base_qty 필수 (BTC/ETH 등 매도 수량)
    """
    exchange: str               # "upbit", "binance" 등
    symbol: str                 # "BTC/KRW", "BTC/USDT" 등
    side: OrderSide             # BUY or SELL
    order_type: OrderType       # MARKET or LIMIT
    
    # MARKET 주문 파라미터
    base_qty: Optional[float] = None      # SELL MARKET 시 필수
    quote_amount: Optional[float] = None  # BUY MARKET 시 필수
    
    # LIMIT 주문 파라미터
    limit_price: Optional[float] = None   # LIMIT 시 필수
    
    # 메타데이터
    route_id: Optional[str] = None
    strategy_id: Optional[str] = None
    
    def validate(self):
        """의도의 유효성 검증"""
        if self.order_type == OrderType.MARKET:
            if self.side == OrderSide.BUY:
                if not self.quote_amount or self.quote_amount <= 0:
                    raise ValueError(
                        f"MARKET BUY requires positive quote_amount, "
                        f"got: {self.quote_amount}"
                    )
            elif self.side == OrderSide.SELL:
                if not self.base_qty or self.base_qty <= 0:
                    raise ValueError(
                        f"MARKET SELL requires positive base_qty, "
                        f"got: {self.base_qty}"
                    )
        elif self.order_type == OrderType.LIMIT:
            if not self.limit_price or self.limit_price <= 0:
                raise ValueError("LIMIT order requires positive limit_price")
            if self.side == OrderSide.BUY and not self.quote_amount:
                raise ValueError("LIMIT BUY requires quote_amount")
            if self.side == OrderSide.SELL and not self.base_qty:
                raise ValueError("LIMIT SELL requires base_qty")
```

**Key Design:**
- MARKET 의미 명확화: BUY=금액, SELL=수량
- Validation은 Adapter 전에 Engine에서 수행
- 거래소별 quirks는 Adapter가 처리

---

### 2. ExchangeAdapter (Implementation Layer)

**Purpose:** OrderIntent를 거래소 API payload로 변환

```python
from abc import ABC, abstractmethod
from typing import Dict, Any


class ExchangeAdapter(ABC):
    """
    거래소 어댑터 인터페이스.
    
    Responsibility:
    1. OrderIntent → Exchange Payload 변환
    2. Exchange Response → Standard Response 변환
    3. Exchange-specific validation
    """
    
    @abstractmethod
    def translate_intent(self, intent: OrderIntent) -> Dict[str, Any]:
        """
        OrderIntent를 거래소별 payload로 변환.
        
        Args:
            intent: 거래소 독립적 주문 의도
            
        Returns:
            거래소 API 호출용 payload
            
        Raises:
            ValueError: intent가 해당 거래소에서 지원 불가능한 경우
        """
        pass
    
    @abstractmethod
    def submit_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        실제 API 호출 (또는 Mock).
        
        Args:
            payload: translate_intent()의 출력
            
        Returns:
            거래소 응답 (raw)
        """
        pass
    
    @abstractmethod
    def parse_response(self, response: Dict[str, Any]) -> 'OrderResult':
        """
        거래소 응답을 표준 형식으로 변환.
        
        Args:
            response: submit_order()의 출력
            
        Returns:
            표준 OrderResult
        """
        pass


@dataclass
class OrderResult:
    """표준 주문 결과"""
    success: bool
    order_id: Optional[str] = None
    filled_qty: Optional[float] = None
    filled_price: Optional[float] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
```

**Example: Upbit Adapter**

```python
class UpbitAdapter(ExchangeAdapter):
    """
    Upbit 거래소 어댑터.
    
    Upbit API 규칙:
    - MARKET BUY: 'price' (KRW 금액) 필수, 'volume' 금지
    - MARKET SELL: 'volume' (코인 수량) 필수, 'price' 금지
    """
    
    def translate_intent(self, intent: OrderIntent) -> Dict[str, Any]:
        intent.validate()  # Engine에서 한 번 더 검증
        
        payload = {
            "market": intent.symbol.replace("/", "-"),  # BTC/KRW → BTC-KRW
            "side": intent.side.value.lower(),          # BUY → buy
            "ord_type": intent.order_type.value.lower() # MARKET → market
        }
        
        if intent.order_type == OrderType.MARKET:
            if intent.side == OrderSide.BUY:
                # Upbit: MARKET BUY는 'price' (KRW 금액)
                payload["price"] = str(int(intent.quote_amount))
            elif intent.side == OrderSide.SELL:
                # Upbit: MARKET SELL은 'volume' (코인 수량)
                payload["volume"] = str(intent.base_qty)
        
        elif intent.order_type == OrderType.LIMIT:
            payload["price"] = str(intent.limit_price)
            if intent.side == OrderSide.BUY:
                payload["volume"] = str(intent.quote_amount / intent.limit_price)
            else:
                payload["volume"] = str(intent.base_qty)
        
        return payload
    
    def submit_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # V2: 기본은 Mock/Stub
        return {"uuid": "mock-12345", "state": "done"}
    
    def parse_response(self, response: Dict[str, Any]) -> OrderResult:
        return OrderResult(
            success=True,
            order_id=response.get("uuid"),
            raw_response=response
        )
```

---

### 3. ArbitrageEngine (Orchestrator)

**Purpose:** 차익거래 로직 + OrderIntent 생성

```python
class ArbitrageEngine:
    """
    V2 차익거래 엔진.
    
    Responsibility:
    1. 시장 데이터 수집 (L2 orderbook)
    2. 차익 기회 탐지
    3. OrderIntent 생성
    4. Adapter 호출
    5. 결과 집계
    """
    
    def __init__(
        self,
        adapters: Dict[str, ExchangeAdapter],
        config: 'EngineConfig'
    ):
        self.adapters = adapters
        self.config = config
    
    def run_arbitrage_cycle(self):
        """한 사이클 실행"""
        # 1. 시장 데이터 수집
        market_data = self._fetch_market_data()
        
        # 2. 차익 기회 탐지
        opportunities = self._detect_opportunities(market_data)
        
        # 3. OrderIntent 생성
        intents = self._create_intents(opportunities)
        
        # 4. Adapter 실행
        results = []
        for intent in intents:
            adapter = self.adapters[intent.exchange]
            
            # Translate
            payload = adapter.translate_intent(intent)
            
            # Submit (Mock in V2)
            response = adapter.submit_order(payload)
            
            # Parse
            result = adapter.parse_response(response)
            results.append(result)
        
        # 5. 결과 집계
        return self._aggregate_results(results)
```

---

## 🔄 V2 Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    ArbitrageEngine                          │
│  - Market data collection                                   │
│  - Opportunity detection                                    │
│  - Risk checks                                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ Create OrderIntent
                   ▼
          ┌────────────────┐
          │  OrderIntent   │  (Semantic: "BUY MARKET 5000 KRW")
          │  - exchange    │
          │  - symbol      │
          │  - side        │
          │  - order_type  │
          │  - quote_amount│
          └────────┬───────┘
                   │
                   │ Validate
                   ▼
          ┌─────────────────┐
          │ ExchangeAdapter │
          │  .translate()   │ → Upbit Payload: {price: "5000"}
          │  .submit()      │ → API Call (or Mock)
          │  .parse()       │ → OrderResult
          └─────────────────┘
```

---

## 🧪 Testing Strategy

### 1. Unit Tests (Fast)
- **OrderIntent:** validation logic
- **Adapter:** translate_intent() 로직 (Mock submit)
- **Engine:** opportunity detection (Mock market data)

### 2. Integration Tests (Medium)
- **Engine + Mock Adapters:** 전체 플로우 검증
- **Adapter + Real API (READ_ONLY):** payload 검증

### 3. Smoke Tests (Slow)
- **End-to-End with Mock:** 실행 가능성 검증
- **Paper Mode (Real Data, Mock Order):** 실전 시뮬레이션

---

## 📦 Module Structure

```
arbitrage/v2/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── order_intent.py       # OrderIntent, OrderSide, OrderType
│   ├── adapter.py            # ExchangeAdapter, OrderResult
│   └── engine.py             # ArbitrageEngine
├── adapters/
│   ├── __init__.py
│   ├── mock_adapter.py       # MockAdapter (테스트용)
│   ├── upbit_adapter.py      # UpbitAdapter
│   └── binance_adapter.py    # BinanceAdapter
├── harness/
│   ├── __init__.py
│   └── smoke_runner.py       # Smoke 진입점 (스크립트 대체)
└── tests/
    ├── __init__.py
    ├── test_order_intent.py
    ├── test_adapters.py
    └── test_engine.py
```

---

## 🚀 Migration Path (V1 → V2)

### Phase 0: 뼈대 구축 (현재)
- ✅ OrderIntent, Adapter, Engine 타입 정의
- ✅ MockAdapter 구현
- ✅ Smoke Harness 1개 작성

### Phase 1: Upbit Adapter 검증
- V1 upbit_spot.py 참조하여 V2 UpbitAdapter 구현
- PAPER 모드로 payload 검증
- D48 테스트 케이스 V2로 마이그레이션

### Phase 2: Binance Adapter 추가
- BinanceAdapter 구현
- Cross-exchange arbitrage 재현

### Phase 3: V1 Deprecation
- V2 안정화 후 V1 코드 deprecated 마킹
- 3개월 유예 후 V1 제거

---

## 🔐 Safety Guarantees

### 1. 실거래 차단 (V2 기본)
- Adapter.submit_order() 기본 구현: Mock 리턴
- READ_ONLY 플래그 강제 (실거래는 명시적 Override 필요)

### 2. Validation 계층화
- **Engine:** OrderIntent.validate() (의미 검증)
- **Adapter:** translate_intent() (거래소 규칙 검증)

### 3. 증거 기반 개발
- 모든 실행은 logs/evidence/v2_*/ 저장
- Payload, Response, Decision 전수 로깅

---

## 📚 References

- `docs/v2/SSOT_RULES.md` - V2 개발 규칙
- `D_ROADMAP.md` - 프로젝트 로드맵
- `docs/D106/D106_4_1_FINAL_REPORT.md` - V1 마지막 핫픽스
- `arbitrage/exchanges/upbit_spot.py` - V1 Upbit 구현 참고

---

**이 아키텍처는 V2 개발의 북극성(North Star)입니다.**
