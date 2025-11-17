# D50 설계 문서: LiveRunner 통합 & 모니터링 레이어

**작성일:** 2025-11-17  
**상태:** 설계 단계

---

## 📋 Executive Summary

D50은 **LiveRunner와 MarketDataProvider 통합**, 그리고 **기본 모니터링 레이어**를 구축합니다.

**핵심 목표:**
1. LiveRunner에 MarketDataProvider DI 통합
2. `data_source: "rest" | "ws"` 설정 기반 선택
3. 최소 모니터링/메트릭 레이어 추가
4. 기존 트레이딩 로직 변경 없음

---

## 🏗️ 아키텍처

### 현재 (D49.5)

```
LiveRunner
  ├── get_orderbook(symbol) → REST API 직접 호출
  ├── ArbitrageEngine 호출
  ├── 주문 실행
  └── 리스크 체크
```

### 목표 (D50)

```
LiveRunner
  ├── MarketDataProvider (DI)
  │   ├── RestMarketDataProvider (data_source="rest")
  │   │   └── exchange.get_orderbook() → REST API
  │   └── WebSocketMarketDataProvider (data_source="ws")
  │       └── 메모리 버퍼 (최신 스냅샷)
  ├── ArbitrageEngine 호출 (변경 없음)
  ├── 주문 실행 (변경 없음)
  ├── 리스크 체크 (변경 없음)
  └── MetricsCollector 업데이트 (경량)
```

### 메트릭 수집 흐름

```
LiveRunner (각 루프)
  ├── loop_time_ms 측정
  ├── trades_opened 카운트
  ├── spread 값 기록
  ├── data_source 상태
  ├── ws_status (connected/reconnecting)
  └── ws_reconnects 카운트
    ↓
MetricsCollector (메모리 버퍼)
  ├── 최근 N개 루프 기록
  ├── 평균/최대/최소 계산
  └── 시계열 데이터 유지
    ↓
MetricsServer (HTTP)
  ├── GET /health → JSON
  ├── GET /metrics → Prometheus 또는 JSON
  └── 포트 8001 (기본값)
```

---

## 📊 설정 구조

### 기본 설정 (arbitrage_live_upbit_binance_trading.yaml)

```yaml
# D50: 데이터 소스 선택
data_source: "rest"  # 기본값: rest (안전)

# WebSocket 설정 (data_source="ws"일 때만 사용)
ws:
  enabled: false
  use_for_orderbook: true
  reconnect_backoff:
    initial: 1.0
    max: 30.0
    multiplier: 2.0
  
  upbit:
    enabled: true
    max_depth: 10
    heartbeat_interval: 30.0
  
  binance:
    enabled: true
    max_depth: 20
    heartbeat_interval: 30.0

# 모니터링 설정
monitoring:
  enabled: true
  metrics_port: 8001
  metrics_format: "prometheus"  # "prometheus" 또는 "json"
  buffer_size: 300  # 최근 300개 루프 기록
```

### 설정 로드 로직

```python
# arbitrage/config.py 또는 live_runner.py에서
def create_market_data_provider(config: ArbitrageLiveConfig) -> MarketDataProvider:
    """설정에 따라 MarketDataProvider 생성"""
    
    if config.data_source == "rest":
        return RestMarketDataProvider(exchanges={
            "a": upbit_exchange,
            "b": binance_exchange,
        })
    
    elif config.data_source == "ws":
        # WebSocket 어댑터 생성
        upbit_adapter = UpbitWebSocketAdapter(
            symbols=["KRW-BTC", "KRW-ETH"],
            callback=ws_provider.on_upbit_snapshot,
        )
        binance_adapter = BinanceWebSocketAdapter(
            symbols=["btcusdt", "ethusdt"],
            callback=ws_provider.on_binance_snapshot,
        )
        
        ws_provider = WebSocketMarketDataProvider(ws_adapters={
            "upbit": upbit_adapter,
            "binance": binance_adapter,
        })
        
        return ws_provider
    
    else:
        raise ValueError(f"Unknown data_source: {config.data_source}")
```

---

## 📈 메트릭 수집 항목

### 주요 메트릭

| 메트릭 | 타입 | 설명 |
|--------|------|------|
| `loop_time_ms` | Gauge | 최근 루프 실행 시간 (ms) |
| `loop_time_avg_ms` | Gauge | 평균 루프 시간 (최근 N개) |
| `loop_time_max_ms` | Gauge | 최대 루프 시간 |
| `loop_time_min_ms` | Gauge | 최소 루프 시간 |
| `trades_opened_total` | Counter | 누적 체결 횟수 |
| `trades_opened_recent` | Gauge | 최근 1분 체결 횟수 |
| `spread_bps` | Gauge | 최근 스프레드 (bps) |
| `spread_avg_bps` | Gauge | 평균 스프레드 |
| `data_source` | Label | "rest" 또는 "ws" |
| `ws_connected` | Gauge | 1=connected, 0=disconnected |
| `ws_reconnect_count` | Counter | 재연결 횟수 |

### 메트릭 수집 인터페이스

```python
class MetricsCollector:
    """메트릭 수집 및 관리"""
    
    def __init__(self, buffer_size: int = 300):
        self.buffer_size = buffer_size
        self.loop_times: deque = deque(maxlen=buffer_size)
        self.trades_opened: deque = deque(maxlen=buffer_size)
        self.spreads: deque = deque(maxlen=buffer_size)
        self.data_source: str = "rest"
        self.ws_connected: bool = False
        self.ws_reconnect_count: int = 0
        self.trades_opened_total: int = 0
    
    def update_loop_metrics(
        self,
        loop_time_ms: float,
        trades_opened: int,
        spread_bps: float,
        data_source: str,
        ws_status: dict,  # {"connected": bool, "reconnects": int}
    ):
        """루프 메트릭 업데이트"""
        self.loop_times.append(loop_time_ms)
        self.trades_opened.append(trades_opened)
        self.spreads.append(spread_bps)
        self.data_source = data_source
        self.ws_connected = ws_status.get("connected", False)
        self.ws_reconnect_count = ws_status.get("reconnects", 0)
        self.trades_opened_total += trades_opened
    
    def get_metrics(self) -> dict:
        """현재 메트릭 반환"""
        loop_times = list(self.loop_times)
        spreads = list(self.spreads)
        
        return {
            "loop_time_ms": loop_times[-1] if loop_times else 0,
            "loop_time_avg_ms": sum(loop_times) / len(loop_times) if loop_times else 0,
            "loop_time_max_ms": max(loop_times) if loop_times else 0,
            "loop_time_min_ms": min(loop_times) if loop_times else 0,
            "trades_opened_total": self.trades_opened_total,
            "trades_opened_recent": sum(self.trades_opened),
            "spread_bps": spreads[-1] if spreads else 0,
            "spread_avg_bps": sum(spreads) / len(spreads) if spreads else 0,
            "data_source": self.data_source,
            "ws_connected": self.ws_connected,
            "ws_reconnect_count": self.ws_reconnect_count,
        }
```

---

## 🌐 HTTP 엔드포인트

### 옵션 A: Prometheus 형식 (선택)

**GET /health**
```json
{
  "status": "ok",
  "data_source": "rest",
  "uptime_seconds": 123.45
}
```

**GET /metrics**
```
# HELP arbitrage_loop_time_ms Recent loop execution time
# TYPE arbitrage_loop_time_ms gauge
arbitrage_loop_time_ms 1001.23

# HELP arbitrage_loop_time_avg_ms Average loop time
# TYPE arbitrage_loop_time_avg_ms gauge
arbitrage_loop_time_avg_ms 1000.50

# HELP arbitrage_trades_opened_total Total trades opened
# TYPE arbitrage_trades_opened_total counter
arbitrage_trades_opened_total 2

# HELP arbitrage_spread_bps Recent spread in basis points
# TYPE arbitrage_spread_bps gauge
arbitrage_spread_bps 14752.48

# HELP arbitrage_data_source Current data source
# TYPE arbitrage_data_source gauge
arbitrage_data_source{source="rest"} 1

# HELP arbitrage_ws_connected WebSocket connection status
# TYPE arbitrage_ws_connected gauge
arbitrage_ws_connected 0
```

### 옵션 B: JSON 형식 (선택)

**GET /health**
```json
{
  "status": "ok",
  "data_source": "rest",
  "uptime_seconds": 123.45
}
```

**GET /metrics**
```json
{
  "loop_time_ms": 1001.23,
  "loop_time_avg_ms": 1000.50,
  "loop_time_max_ms": 1050.00,
  "loop_time_min_ms": 950.00,
  "trades_opened_total": 2,
  "trades_opened_recent": 2,
  "spread_bps": 14752.48,
  "spread_avg_bps": 14500.00,
  "data_source": "rest",
  "ws_connected": false,
  "ws_reconnect_count": 0
}
```

**선택 이유:**
- JSON 형식이 더 간단하고 빠름
- 초기 단계에는 JSON으로 시작
- 나중에 필요하면 Prometheus 형식 추가 가능

---

## 📁 파일 구조

```
arbitrage/
├── live_runner.py (MODIFIED)
│   ├── MarketDataProvider DI 추가
│   ├── data_source 기반 provider 선택
│   └── 루프 끝에 metrics 업데이트
├── config.py (또는 live_runner.py)
│   └── create_market_data_provider() 함수
├── monitoring/
│   ├── __init__.py
│   ├── metrics_collector.py (NEW)
│   │   └── MetricsCollector 클래스
│   └── metrics_server.py (NEW)
│       └── HTTP 엔드포인트 (FastAPI 또는 Flask)
└── exchanges/
    └── market_data_provider.py (기존)

configs/live/
└── arbitrage_live_upbit_binance_trading.yaml (MODIFIED)
    └── data_source, ws, monitoring 섹션 추가

tests/
├── test_d50_live_runner_datasource.py (NEW)
├── test_d50_metrics_collector.py (NEW)
└── test_d50_metrics_server.py (NEW)

docs/
├── D50_MONITORING_DESIGN.md (본 문서)
└── D50_FINAL_REPORT.md (최종 보고서)
```

---

## 🔄 LiveRunner 수정 계획

### 현재 코드 (개념)

```python
class ArbitrageLiveRunner:
    def __init__(self, config, exchanges):
        self.config = config
        self.exchanges = exchanges
        self.engine = ArbitrageEngine(config)
    
    def run(self):
        while not self.should_stop:
            # 호가 조회 (REST 직접 호출)
            snapshot_a = self.exchanges["a"].get_orderbook(symbol_a)
            snapshot_b = self.exchanges["b"].get_orderbook(symbol_b)
            
            # 엔진 호출
            action = self.engine.analyze(snapshot_a, snapshot_b)
            
            # 주문 실행
            if action:
                self.execute_action(action)
            
            # 리스크 체크
            self.risk_guard.check()
```

### 수정 후 코드 (D50)

```python
class ArbitrageLiveRunner:
    def __init__(
        self,
        config,
        exchanges,
        market_data_provider: MarketDataProvider,  # DI
        metrics_collector: MetricsCollector = None,  # 선택사항
    ):
        self.config = config
        self.exchanges = exchanges
        self.market_data_provider = market_data_provider
        self.metrics_collector = metrics_collector
        self.engine = ArbitrageEngine(config)
    
    def run(self):
        while not self.should_stop:
            loop_start = time.time()
            
            # 호가 조회 (MarketDataProvider 경유)
            snapshot_a = self.market_data_provider.get_latest_snapshot(symbol_a)
            snapshot_b = self.market_data_provider.get_latest_snapshot(symbol_b)
            
            # 엔진 호출 (변경 없음)
            action = self.engine.analyze(snapshot_a, snapshot_b)
            
            # 주문 실행 (변경 없음)
            trades_opened = 0
            if action:
                trades_opened = self.execute_action(action)
            
            # 리스크 체크 (변경 없음)
            self.risk_guard.check()
            
            # 메트릭 업데이트 (경량, 선택사항)
            if self.metrics_collector:
                loop_time_ms = (time.time() - loop_start) * 1000
                spread_bps = self.engine.last_spread_bps or 0
                ws_status = {
                    "connected": getattr(self.market_data_provider, "ws_connected", False),
                    "reconnects": getattr(self.market_data_provider, "ws_reconnects", 0),
                }
                self.metrics_collector.update_loop_metrics(
                    loop_time_ms=loop_time_ms,
                    trades_opened=trades_opened,
                    spread_bps=spread_bps,
                    data_source=self.config.data_source,
                    ws_status=ws_status,
                )
```

**변경 사항:**
- ✅ MarketDataProvider DI 추가
- ✅ `get_orderbook()` → `market_data_provider.get_latest_snapshot()` 변경
- ✅ 루프 끝에 메트릭 업데이트 (경량)
- ✅ 엔진/주문/리스크 로직 변경 없음

---

## 🧪 테스트 전략

### 1. LiveRunner DataSource 테스트

```python
def test_live_runner_rest_datasource():
    """data_source='rest'일 때 기존 동작과 동일"""
    # Mock RestMarketDataProvider
    # LiveRunner 실행
    # 스냅샷이 REST에서 오는지 확인
    pass

def test_live_runner_ws_datasource():
    """data_source='ws'일 때 WebSocketMarketDataProvider 사용"""
    # Mock WebSocketMarketDataProvider
    # LiveRunner 실행
    # 스냅샷이 WS에서 오는지 확인
    pass
```

### 2. MetricsCollector 테스트

```python
def test_metrics_collector_update():
    """메트릭 업데이트"""
    collector = MetricsCollector()
    collector.update_loop_metrics(1000.0, 1, 5000.0, "rest", {"connected": False, "reconnects": 0})
    
    metrics = collector.get_metrics()
    assert metrics["loop_time_ms"] == 1000.0
    assert metrics["trades_opened_total"] == 1
    pass

def test_metrics_collector_averaging():
    """평균 계산"""
    collector = MetricsCollector(buffer_size=10)
    for i in range(5):
        collector.update_loop_metrics(1000.0 + i * 10, 0, 5000.0, "rest", {"connected": False, "reconnects": 0})
    
    metrics = collector.get_metrics()
    assert metrics["loop_time_avg_ms"] > 1000.0
    pass
```

### 3. MetricsServer 테스트

```python
def test_metrics_server_health():
    """GET /health 응답"""
    # FastAPI TestClient
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    pass

def test_metrics_server_metrics():
    """GET /metrics 응답"""
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "loop_time_ms" in data
    pass
```

---

## 🚀 구현 순서

1. **MetricsCollector** 구현
   - 메트릭 수집 로직
   - 버퍼 관리
   - 통계 계산

2. **MetricsServer** 구현
   - FastAPI 기반 HTTP 엔드포인트
   - /health, /metrics 라우트
   - JSON 응답

3. **LiveRunner 수정**
   - MarketDataProvider DI 추가
   - data_source 기반 provider 선택
   - 메트릭 업데이트 호출

4. **Config 확장**
   - data_source 필드 추가
   - ws 섹션 추가
   - monitoring 섹션 추가

5. **테스트 작성**
   - LiveRunner DataSource 테스트
   - MetricsCollector 테스트
   - MetricsServer 테스트

---

**설계 문서 완료. 구현 단계로 진행.**
