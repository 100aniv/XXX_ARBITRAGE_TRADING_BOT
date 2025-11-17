# D49.5 설계 문서: WebSocket Exchange Adapters

**작성일:** 2025-11-17  
**상태:** 설계 단계

---

## 📋 Executive Summary

D49.5는 **Upbit/Binance WebSocket 어댑터**를 구현합니다.

**핵심 목표:**
- Upbit WebSocket orderbook 메시지 → OrderbookSnapshot 변환
- Binance WebSocket depth 메시지 → OrderbookSnapshot 변환
- WebSocketMarketDataProvider와 연결
- REST fallback 설계 유지

---

## 🏗️ 아키텍처

### D49 구조 (기존)

```
BaseWebSocketClient (추상)
    ↓
UpbitWebSocketAdapter (D49.5)
BinanceWebSocketAdapter (D49.5)
    ↓
WebSocketMarketDataProvider
    ↓
LiveRunner (변경 없음)
```

### 메시지 흐름

```
Upbit WebSocket 스트림
    ↓
UpbitWebSocketAdapter.on_message()
    ↓
메시지 파싱 (orderbook_units)
    ↓
OrderbookSnapshot 생성
    ↓
WebSocketMarketDataProvider._update_snapshot()
    ↓
메모리 버퍼 (최신)
    ↓
LiveRunner.get_latest_snapshot()
```

---

## 📊 메시지 포맷

### Upbit WebSocket

**구독 메시지:**
```json
{
  "type": "orderbook",
  "codes": ["KRW-BTC"]
}
```

**수신 메시지:**
```json
{
  "type": "orderbook",
  "code": "KRW-BTC",
  "timestamp": 1710000000000,
  "orderbook_units": [
    {
      "ask_price": 100.1,
      "bid_price": 99.9,
      "ask_size": 1.2,
      "bid_size": 1.1
    },
    ...
  ]
}
```

**변환 규칙:**
- `bids`: bid_price, bid_size 쌍 (상위 10개)
- `asks`: ask_price, ask_size 쌍 (상위 10개)
- `timestamp`: ms 단위 (정규화)
- `exchange`: "upbit"
- `symbol`: code (예: "KRW-BTC")

### Binance WebSocket

**구독 메시지:**
```json
{
  "method": "SUBSCRIBE",
  "params": ["btcusdt@depth20@100ms"],
  "id": 1
}
```

**수신 메시지:**
```json
{
  "stream": "btcusdt@depth20@100ms",
  "data": {
    "E": 1710000000000,
    "b": [
      ["50000.0", "1.0"],
      ["49999.0", "2.0"],
      ...
    ],
    "a": [
      ["50001.0", "1.0"],
      ["50002.0", "2.0"],
      ...
    ]
  }
}
```

**변환 규칙:**
- `bids`: data.b (상위 20개, 이미 정렬됨)
- `asks`: data.a (상위 20개, 이미 정렬됨)
- `timestamp`: E (ms 단위)
- `exchange`: "binance"
- `symbol`: stream에서 추출 (예: "BTCUSDT")
- float 변환: `float(price), float(size)`

---

## 🔧 구현 구조

### UpbitWebSocketAdapter

```python
class UpbitWebSocketAdapter(BaseWebSocketClient):
    """
    Upbit WebSocket 어댑터
    
    책임:
    - Upbit WebSocket 연결
    - orderbook 메시지 구독
    - 메시지 파싱 → OrderbookSnapshot 변환
    - 콜백 기반 업데이트
    """
    
    def __init__(self, symbols: List[str], callback: Callable):
        super().__init__(url="wss://api.upbit.com/websocket/v1")
        self.symbols = symbols
        self.callback = callback
    
    async def subscribe(self, channels: List[str]):
        """orderbook 채널 구독"""
        message = {
            "type": "orderbook",
            "codes": channels
        }
        await self.send_message(message)
    
    def on_message(self, message: dict):
        """메시지 핸들러"""
        if message.get("type") == "orderbook":
            snapshot = self._parse_message(message)
            if snapshot:
                self.callback(snapshot)
    
    def _parse_message(self, message: dict) -> Optional[OrderbookSnapshot]:
        """Upbit 메시지 → OrderbookSnapshot"""
        try:
            code = message.get("code")
            timestamp = message.get("timestamp", 0)
            units = message.get("orderbook_units", [])
            
            bids = []
            asks = []
            
            for unit in units[:10]:  # 상위 10개
                bid_price = unit.get("bid_price")
                bid_size = unit.get("bid_size")
                ask_price = unit.get("ask_price")
                ask_size = unit.get("ask_size")
                
                if bid_price and bid_size:
                    bids.append((float(bid_price), float(bid_size)))
                if ask_price and ask_size:
                    asks.append((float(ask_price), float(ask_size)))
            
            return OrderbookSnapshot(
                exchange="upbit",
                symbol=code,
                timestamp=timestamp,
                bids=bids,
                asks=asks,
            )
        except Exception as e:
            logger.error(f"[D49.5_UPBIT] Parse error: {e}")
            return None
```

### BinanceWebSocketAdapter

```python
class BinanceWebSocketAdapter(BaseWebSocketClient):
    """
    Binance WebSocket 어댑터
    
    책임:
    - Binance WebSocket 연결
    - depth 메시지 구독
    - 메시지 파싱 → OrderbookSnapshot 변환
    - 콜백 기반 업데이트
    """
    
    def __init__(self, symbols: List[str], callback: Callable):
        super().__init__(url="wss://fstream.binance.com/stream")
        self.symbols = symbols
        self.callback = callback
    
    async def subscribe(self, channels: List[str]):
        """depth 채널 구독"""
        message = {
            "method": "SUBSCRIBE",
            "params": channels,
            "id": 1
        }
        await self.send_message(message)
    
    def on_message(self, message: dict):
        """메시지 핸들러"""
        data = message.get("data", {})
        if "b" in data and "a" in data:  # depth 메시지
            snapshot = self._parse_message(message)
            if snapshot:
                self.callback(snapshot)
    
    def _parse_message(self, message: dict) -> Optional[OrderbookSnapshot]:
        """Binance 메시지 → OrderbookSnapshot"""
        try:
            stream = message.get("stream", "")
            data = message.get("data", {})
            
            # stream에서 symbol 추출 (예: "btcusdt@depth20@100ms" → "BTCUSDT")
            symbol = stream.split("@")[0].upper()
            
            timestamp = data.get("E", 0)
            bids_raw = data.get("b", [])
            asks_raw = data.get("a", [])
            
            # 상위 20개
            bids = [(float(p), float(s)) for p, s in bids_raw[:20]]
            asks = [(float(p), float(s)) for p, s in asks_raw[:20]]
            
            return OrderbookSnapshot(
                exchange="binance",
                symbol=symbol,
                timestamp=timestamp,
                bids=bids,
                asks=asks,
            )
        except Exception as e:
            logger.error(f"[D49.5_BINANCE] Parse error: {e}")
            return None
```

---

## 🔄 WebSocketMarketDataProvider 업데이트

```python
class WebSocketMarketDataProvider(MarketDataProvider):
    """
    WebSocket 기반 호가 데이터 제공자
    
    업데이트:
    - snapshot_upbit, snapshot_binance 분리 관리
    - get_latest_snapshot(exchange) 메서드 추가
    - 콜백 기반 스냅샷 업데이트
    """
    
    def __init__(self, ws_adapters: Dict[str, any]):
        self.ws_adapters = ws_adapters
        self._is_running = False
        self.snapshot_upbit: Optional[OrderbookSnapshot] = None
        self.snapshot_binance: Optional[OrderbookSnapshot] = None
    
    def get_latest_snapshot(self, symbol: str) -> Optional[OrderbookSnapshot]:
        """
        심볼 기반 최신 스냅샷 반환
        
        Args:
            symbol: "KRW-BTC" (Upbit) 또는 "BTCUSDT" (Binance)
        
        Returns:
            OrderbookSnapshot 또는 None
        """
        if "-" in symbol:  # Upbit
            return self.snapshot_upbit
        elif symbol.endswith("USDT"):  # Binance
            return self.snapshot_binance
        else:
            return None
    
    def _on_upbit_snapshot(self, snapshot: OrderbookSnapshot):
        """Upbit 스냅샷 콜백"""
        self.snapshot_upbit = snapshot
    
    def _on_binance_snapshot(self, snapshot: OrderbookSnapshot):
        """Binance 스냅샷 콜백"""
        self.snapshot_binance = snapshot
    
    def start(self):
        """WebSocket 연결 시작"""
        self._is_running = True
        # 실제 구현: asyncio 루프에서 어댑터 시작
    
    def stop(self):
        """WebSocket 연결 종료"""
        self._is_running = False
```

---

## 🧪 테스트 전략

### 1. UpbitWebSocketAdapter 테스트

```python
def test_upbit_parse_orderbook():
    """Upbit 메시지 파싱"""
    message = {
        "type": "orderbook",
        "code": "KRW-BTC",
        "timestamp": 1710000000000,
        "orderbook_units": [
            {"ask_price": 100.1, "bid_price": 99.9, "ask_size": 1.2, "bid_size": 1.1},
            ...
        ]
    }
    
    adapter = UpbitWebSocketAdapter(["KRW-BTC"], callback=mock_callback)
    snapshot = adapter._parse_message(message)
    
    assert snapshot.exchange == "upbit"
    assert snapshot.symbol == "KRW-BTC"
    assert len(snapshot.bids) <= 10
    assert len(snapshot.asks) <= 10
```

### 2. BinanceWebSocketAdapter 테스트

```python
def test_binance_parse_depth():
    """Binance 메시지 파싱"""
    message = {
        "stream": "btcusdt@depth20@100ms",
        "data": {
            "E": 1710000000000,
            "b": [["50000.0", "1.0"], ...],
            "a": [["50001.0", "1.0"], ...]
        }
    }
    
    adapter = BinanceWebSocketAdapter(["btcusdt@depth20@100ms"], callback=mock_callback)
    snapshot = adapter._parse_message(message)
    
    assert snapshot.exchange == "binance"
    assert snapshot.symbol == "BTCUSDT"
    assert len(snapshot.bids) <= 20
    assert len(snapshot.asks) <= 20
```

### 3. WebSocketMarketDataProvider 통합 테스트

```python
def test_ws_provider_snapshot_management():
    """스냅샷 관리"""
    provider = WebSocketMarketDataProvider({})
    
    # Upbit 스냅샷 업데이트
    upbit_snapshot = OrderbookSnapshot(...)
    provider._on_upbit_snapshot(upbit_snapshot)
    
    # Binance 스냅샷 업데이트
    binance_snapshot = OrderbookSnapshot(...)
    provider._on_binance_snapshot(binance_snapshot)
    
    # 조회
    assert provider.get_latest_snapshot("KRW-BTC") == upbit_snapshot
    assert provider.get_latest_snapshot("BTCUSDT") == binance_snapshot
```

---

## 📝 파일 구조

```
arbitrage/exchanges/
├── ws_client.py                    # D49 (기존)
├── upbit_ws_adapter.py             # NEW: Upbit WS 어댑터
├── binance_ws_adapter.py           # NEW: Binance WS 어댑터
├── market_data_provider.py         # MODIFIED: WebSocketMarketDataProvider 업데이트
└── ...

tests/
├── test_d49_5_upbit_ws_adapter.py          # NEW
├── test_d49_5_binance_ws_adapter.py        # NEW
├── test_d49_5_market_data_provider_ws.py   # NEW
└── ...

docs/
├── D49_5_WS_EXCHANGE_ADAPTER_DESIGN.md     # NEW (본 문서)
└── D49_5_FINAL_REPORT.md                   # NEW
```

---

**설계 문서 완료. 구현 단계로 진행.**
