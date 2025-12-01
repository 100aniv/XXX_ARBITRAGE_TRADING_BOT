# D79-6: Cross-Exchange Monitoring & Metrics

**Status:** 🚧 **IN PROGRESS**  
**Date:** 2025-12-01  
**Owner:** Arbitrage Bot Team

---

## 📋 Summary

Cross-Exchange 아비트라지 전용 모니터링/메트릭/알림 인프라 구축.

**목표:**
1. ✅ Cross-Exchange 전용 메트릭 수집 시스템
2. ✅ D76 AlertManager 연계
3. ✅ D77 Prometheus Exporter 연계
4. ✅ RiskGuard/Executor/PnLTracker와 Hook 통합
5. ✅ 1조짜리 시스템 수준의 관측성(Observability) 확보

---

## 🎯 설계 목표

### 1. 관측성 (Observability) 3대 축
- **Metrics**: 정량적 성능/상태 지표 (Prometheus)
- **Logs**: 구조화된 이벤트 로그 (기존 logger + 추가)
- **Alerts**: 임계값 기반 자동 알림 (D76 AlertManager)

### 2. 상용 시스템 기준 요구사항
- **실시간성**: 메트릭 수집/업데이트 < 100ms
- **정확성**: 주문/PnL/리스크 데이터 100% 정확
- **가용성**: Metrics 시스템 장애가 Trading 로직을 중단시키지 않음
- **확장성**: 멀티심볼/멀티라우트 확장 시에도 성능 유지

### 3. Cross-Exchange 특화 요구사항
- Upbit ↔ Binance 양방향 메트릭 분리
- 심볼별/라우트별 집계
- First trigger vs Final block 구분
- Exposure/Imbalance 실시간 추적

---

## 📊 수집할 메트릭 정의

### 1. Risk 관점 (RiskGuard)

#### 1.1 Cross-Exposure Ratio
```python
# Gauge: 현재 cross-exposure 비율 (0.0 ~ 1.0)
cross_exposure_ratio{symbol="KRW-BTC", route="upbit_binance"} = 0.82
```
- **의미**: 한쪽 거래소에 자산이 집중된 정도
- **임계값**: 0.6 (60%)
- **수집 시점**: InventoryTracker 업데이트 시

#### 1.2 Inventory Imbalance Ratio
```python
# Gauge: Upbit vs Binance 잔고 불균형 비율 (-1.0 ~ +1.0)
inventory_imbalance_ratio{symbol="KRW-BTC"} = +0.75
```
- **의미**: +는 Upbit 많음, -는 Binance 많음
- **임계값**: ±0.5 (±50%)
- **수집 시점**: RebalanceSignal 생성 시

#### 1.3 RiskGuard Block Count
```python
# Counter: Tier별 BLOCK 횟수
risk_guard_blocks_total{tier="cross_exchange", reason="cross_exposure_limit"} = 12
risk_guard_blocks_total{tier="cross_exchange", reason="cross_inventory_imbalance"} = 8
risk_guard_blocks_total{tier="cross_exchange", reason="cross_daily_loss_limit"} = 3
```
- **의미**: 각 리스크 룰이 BLOCK한 누적 횟수
- **중요도**: P1 (높음)

#### 1.4 Circuit Breaker Status
```python
# Gauge: Circuit breaker 활성 여부 (0=off, 1=on)
circuit_breaker_active{type="daily_loss"} = 1
circuit_breaker_active{type="consecutive_loss"} = 0

# Gauge: Cooldown 남은 시간 (초)
circuit_breaker_cooldown_remaining{type="daily_loss"} = 1847.3
```

#### 1.5 First Trigger vs Final Block
```python
# Counter: 첫 번째로 감지된 룰 (노이즈 감지용)
risk_first_trigger_total{reason="cross_exposure_limit"} = 45
risk_first_trigger_total{reason="cross_inventory_imbalance"} = 23

# Counter: 최종 BLOCK 이유 (실제 적용된 룰)
risk_final_block_total{reason="cross_daily_loss_limit"} = 3
```
- **목적**: D79-5에서 발견한 "exposure_limit이 먼저 걸려서 다른 룰 테스트 불가" 문제 해결

---

### 2. 실행 관점 (Executor)

#### 2.1 주문 실행 카운트
```python
# Counter: 주문 상태별 누적 횟수
cross_orders_total{exchange="upbit", status="success"} = 128
cross_orders_total{exchange="upbit", status="failed"} = 3
cross_orders_total{exchange="upbit", status="partial_fill"} = 5
cross_orders_total{exchange="binance", status="success"} = 125
```

#### 2.2 주문 Latency Histogram
```python
# Histogram: 주문 제출 → 완전 체결까지 latency
cross_order_fill_duration_seconds{exchange="upbit", percentile="p50"} = 0.234
cross_order_fill_duration_seconds{exchange="upbit", percentile="p95"} = 1.456
cross_order_fill_duration_seconds{exchange="upbit", percentile="p99"} = 3.821
```
- **버킷**: [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]

#### 2.3 Partial Fill 비율
```python
# Gauge: Partial fill 발생 비율 (0.0 ~ 1.0)
cross_partial_fill_ratio{exchange="upbit"} = 0.039  # 3.9%
cross_partial_fill_ratio{exchange="binance"} = 0.012  # 1.2%
```

#### 2.4 Rollback 횟수
```python
# Counter: Partial fill/One-side fill로 인한 rollback
cross_rollbacks_total{reason="partial_fill"} = 5
cross_rollbacks_total{reason="one_side_fill"} = 2
```

---

### 3. 성과 관점 (PnLTracker)

#### 3.1 Daily PnL
```python
# Gauge: 일별 실현 PnL (KRW)
cross_daily_pnl_krw{symbol="KRW-BTC"} = +1_234_567.89
cross_daily_pnl_krw{symbol="KRW-ETH"} = -123_456.78

# Gauge: 전체 Cross-Exchange PnL
cross_total_pnl_krw = +1_111_111.11
```

#### 3.2 Unrealized PnL
```python
# Gauge: 미실현 PnL (현재 Open positions)
cross_unrealized_pnl_krw{symbol="KRW-BTC"} = +567_890.12
```

#### 3.3 Consecutive Loss Count
```python
# Gauge: 현재 연속 손실 횟수
cross_consecutive_loss_count = 2
```

#### 3.4 Win/Loss Stats
```python
# Counter: 승/패 누적
cross_trades_total{result="win"} = 48
cross_trades_total{result="loss"} = 32

# Gauge: Winrate
cross_winrate = 0.60  # 60%
```

---

## 🏗️ 기술 구조

### 1. 기존 D76/D77 인프라 요약

#### D76 AlertManager (기존)
```python
# arbitrage/infrastructure/alert_manager.py (placeholder)
class AlertManager:
    def send_alert(self, level: AlertLevel, title: str, message: str, context: dict) -> None:
        """Alert 전송 (Telegram, Email, Slack 등)"""
        pass
```

#### D77 Prometheus Exporter (기존)
```python
# arbitrage/infrastructure/prometheus_exporter.py (placeholder)
class PrometheusExporter:
    def register_metric(self, name: str, type: str, help: str) -> None:
        pass
    
    def update_counter(self, name: str, value: float, labels: dict) -> None:
        pass
    
    def update_gauge(self, name: str, value: float, labels: dict) -> None:
        pass
    
    def observe_histogram(self, name: str, value: float, labels: dict) -> None:
        pass
```

---

### 2. Cross-Exchange Metrics Collector (신규)

#### 파일 구조
```
arbitrage/
  monitoring/
    __init__.py
    cross_exchange_metrics.py  # 신규: Cross-Exchange 전용 Metrics Collector
```

#### CrossExchangeMetrics 클래스 설계
```python
class CrossExchangeMetrics:
    """
    Cross-Exchange 아비트라지 전용 메트릭 수집기.
    
    Features:
    - RiskGuard decision 기록
    - Executor result 기록
    - PnL snapshot 기록
    - Prometheus export용 인터페이스 제공
    - AlertManager 연계
    """
    
    def __init__(
        self,
        prometheus_backend: Optional[PrometheusBackend] = None,
        alert_manager: Optional[AlertManager] = None,
    ):
        self.backend = prometheus_backend or InMemoryMetricsBackend()
        self.alert_manager = alert_manager
        
        # Metrics 초기화
        self._init_metrics()
    
    def record_risk_decision(
        self,
        decision: CrossRiskDecision,
        decision_context: dict,
    ) -> None:
        """
        RiskGuard 결정 기록.
        
        Args:
            decision: CrossRiskDecision
            decision_context: {
                "symbol_upbit": str,
                "symbol_binance": str,
                "action": str,
                "first_trigger_reason": Optional[str],  # 첫 번째 감지된 룰
            }
        """
        # Counter: Block count
        if not decision.allowed:
            self.backend.inc_counter(
                "risk_guard_blocks_total",
                labels={
                    "tier": decision.tier,
                    "reason": decision.reason_code,
                }
            )
            
            # First trigger 기록 (있으면)
            if first_trigger := decision_context.get("first_trigger_reason"):
                self.backend.inc_counter(
                    "risk_first_trigger_total",
                    labels={"reason": first_trigger}
                )
            
            # Final block 기록
            self.backend.inc_counter(
                "risk_final_block_total",
                labels={"reason": decision.reason_code}
            )
            
            # Alert 전송 (Circuit breaker 등 중요 이벤트)
            if decision.reason_code in [
                CrossRiskReasonCode.CROSS_DAILY_LOSS_LIMIT.value,
                CrossRiskReasonCode.CROSS_CONSECUTIVE_LOSS_LIMIT.value,
            ]:
                self._send_alert_if_enabled(
                    level="P1",
                    title=f"Circuit Breaker: {decision.reason_code}",
                    message=f"Cross-Exchange trading blocked: {decision.details}",
                    context=decision_context,
                )
        
        # Gauge: Exposure/Imbalance 업데이트
        if "exposure_risk" in decision.details:
            self.backend.set_gauge(
                "cross_exposure_ratio",
                value=decision.details["exposure_risk"],
                labels={
                    "symbol": decision_context.get("symbol_upbit", "unknown"),
                }
            )
        
        if "imbalance_ratio" in decision.details:
            self.backend.set_gauge(
                "inventory_imbalance_ratio",
                value=decision.details["imbalance_ratio"],
                labels={
                    "symbol": decision_context.get("symbol_upbit", "unknown"),
                }
            )
    
    def record_execution_result(
        self,
        result: CrossExecutionResult,
    ) -> None:
        """
        Executor 실행 결과 기록.
        
        Args:
            result: CrossExecutionResult (status, upbit_result, binance_result, latency, etc.)
        """
        # Counter: 주문 성공/실패
        for exchange, order_result in [
            ("upbit", result.upbit_result),
            ("binance", result.binance_result),
        ]:
            if order_result:
                self.backend.inc_counter(
                    "cross_orders_total",
                    labels={
                        "exchange": exchange,
                        "status": order_result.status,  # success/failed/partial_fill
                    }
                )
        
        # Histogram: Order fill latency
        if result.total_latency:
            self.backend.observe_histogram(
                "cross_order_fill_duration_seconds",
                value=result.total_latency,
                labels={"exchange": "combined"}
            )
        
        # Counter: Rollback
        if result.status == "rollback":
            self.backend.inc_counter(
                "cross_rollbacks_total",
                labels={"reason": result.rollback_reason or "unknown"}
            )
    
    def record_pnl_snapshot(
        self,
        snapshot: CrossExchangePnLSnapshot,
    ) -> None:
        """
        PnL 스냅샷 기록.
        
        Args:
            snapshot: {
                "daily_pnl_krw": float,
                "unrealized_pnl_krw": float,
                "consecutive_loss_count": int,
                "win_count": int,
                "loss_count": int,
                "symbol": Optional[str],
            }
        """
        # Gauge: Daily PnL
        self.backend.set_gauge(
            "cross_daily_pnl_krw",
            value=snapshot["daily_pnl_krw"],
            labels={"symbol": snapshot.get("symbol", "total")}
        )
        
        # Gauge: Unrealized PnL
        if "unrealized_pnl_krw" in snapshot:
            self.backend.set_gauge(
                "cross_unrealized_pnl_krw",
                value=snapshot["unrealized_pnl_krw"],
                labels={"symbol": snapshot.get("symbol", "total")}
            )
        
        # Gauge: Consecutive loss
        self.backend.set_gauge(
            "cross_consecutive_loss_count",
            value=snapshot["consecutive_loss_count"],
            labels={}
        )
        
        # Counter: Win/Loss (증분만)
        # (주의: 이미 Counter가 있으면 증분만 추가)
        
        # Gauge: Winrate
        total_trades = snapshot["win_count"] + snapshot["loss_count"]
        if total_trades > 0:
            winrate = snapshot["win_count"] / total_trades
            self.backend.set_gauge("cross_winrate", value=winrate, labels={})
    
    def export_prometheus(self) -> str:
        """
        Prometheus 형식으로 export.
        
        D77 PrometheusExporter가 호출할 수 있는 형태.
        """
        return self.backend.export_prometheus_text()
    
    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """테스트/디버깅용 스냅샷"""
        return self.backend.get_all_metrics()
    
    def _send_alert_if_enabled(
        self,
        level: str,
        title: str,
        message: str,
        context: dict,
    ) -> None:
        """AlertManager가 있으면 Alert 전송"""
        if self.alert_manager:
            self.alert_manager.send_alert(
                level=level,
                title=title,
                message=message,
                context=context,
            )
```

---

### 3. Metrics Backend 인터페이스

```python
class PrometheusBackend(Protocol):
    """
    Prometheus-like metrics backend 인터페이스.
    
    실제 Prometheus client는 D77에서 주입.
    테스트/개발 시에는 InMemoryMetricsBackend 사용.
    """
    
    def inc_counter(self, name: str, labels: dict, value: float = 1.0) -> None:
        """Counter 증가"""
        ...
    
    def set_gauge(self, name: str, labels: dict, value: float) -> None:
        """Gauge 설정"""
        ...
    
    def observe_histogram(self, name: str, labels: dict, value: float) -> None:
        """Histogram 관측값 추가"""
        ...
    
    def export_prometheus_text(self) -> str:
        """Prometheus text format으로 export"""
        ...
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """전체 metrics 스냅샷 (테스트용)"""
        ...


class InMemoryMetricsBackend:
    """
    테스트/개발용 in-memory metrics backend.
    
    실제 Prometheus 없이도 metrics 수집/조회 가능.
    """
    
    def __init__(self):
        self.counters: Dict[str, float] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = {}
    
    def inc_counter(self, name: str, labels: dict, value: float = 1.0) -> None:
        key = self._make_key(name, labels)
        self.counters[key] = self.counters.get(key, 0.0) + value
    
    def set_gauge(self, name: str, labels: dict, value: float) -> None:
        key = self._make_key(name, labels)
        self.gauges[key] = value
    
    def observe_histogram(self, name: str, labels: dict, value: float) -> None:
        key = self._make_key(name, labels)
        if key not in self.histograms:
            self.histograms[key] = []
        self.histograms[key].append(value)
    
    def export_prometheus_text(self) -> str:
        """간단한 text format (실제 Prometheus 형식은 아님)"""
        lines = []
        for key, value in self.counters.items():
            lines.append(f"{key} {value}")
        for key, value in self.gauges.items():
            lines.append(f"{key} {value}")
        return "\n".join(lines)
    
    def get_all_metrics(self) -> Dict[str, Any]:
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {k: {"count": len(v), "values": v} for k, v in self.histograms.items()},
        }
    
    def _make_key(self, name: str, labels: dict) -> str:
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}" if label_str else name
```

---

## 🔗 데이터 흐름

### 1. RiskGuard → Metrics
```
CrossExchangeRiskGuard.check_cross_exchange_trade()
    ↓
각 체크 결과 (exposure, imbalance, daily_loss 등)
    ↓
CrossExchangeMetrics.record_risk_decision(decision, context)
    ↓
- Counter: risk_guard_blocks_total{tier, reason}
- Counter: risk_first_trigger_total{reason}
- Counter: risk_final_block_total{reason}
- Gauge: cross_exposure_ratio{symbol}
- Gauge: inventory_imbalance_ratio{symbol}
- Alert: Circuit breaker 발동 시
```

### 2. Executor → Metrics
```
CrossExchangeExecutor.execute_decision()
    ↓
CrossExecutionResult (status, upbit_result, binance_result, latency)
    ↓
CrossExchangeMetrics.record_execution_result(result)
    ↓
- Counter: cross_orders_total{exchange, status}
- Histogram: cross_order_fill_duration_seconds{exchange}
- Counter: cross_rollbacks_total{reason}
```

### 3. PnLTracker → Metrics
```
CrossExchangePnLTracker.add_trade(pnl_krw)
    ↓
PnL 업데이트 (daily, consecutive_loss_count 등)
    ↓
CrossExchangeMetrics.record_pnl_snapshot(snapshot)
    ↓
- Gauge: cross_daily_pnl_krw{symbol}
- Gauge: cross_consecutive_loss_count
- Counter: cross_trades_total{result}
- Gauge: cross_winrate
```

---

## 🧪 테스트 전략

### 1. Unit Test (tests/test_d79_6_monitoring.py)

#### 1.1 CrossExchangeMetrics 단위 테스트
```python
def test_metrics_record_risk_decision():
    """RiskGuard decision 기록 → metrics 업데이트 검증"""
    metrics = CrossExchangeMetrics()
    
    decision = CrossRiskDecision(
        allowed=False,
        tier="cross_exchange",
        reason_code="cross_exposure_limit",
        details={"exposure_risk": 0.82, "limit": 0.6},
    )
    
    context = {
        "symbol_upbit": "KRW-BTC",
        "symbol_binance": "BTCUSDT",
        "action": "entry_positive",
        "first_trigger_reason": "cross_exposure_limit",
    }
    
    metrics.record_risk_decision(decision, context)
    
    snapshot = metrics.get_metrics_snapshot()
    
    # Counter 확인
    assert snapshot["counters"]["risk_guard_blocks_total{tier=cross_exchange,reason=cross_exposure_limit}"] == 1
    assert snapshot["counters"]["risk_first_trigger_total{reason=cross_exposure_limit}"] == 1
    assert snapshot["counters"]["risk_final_block_total{reason=cross_exposure_limit}"] == 1
    
    # Gauge 확인
    assert snapshot["gauges"]["cross_exposure_ratio{symbol=KRW-BTC}"] == 0.82
```

#### 1.2 First Trigger vs Final Block
```python
def test_metrics_first_trigger_vs_final_block():
    """여러 룰이 동시 감지될 때 first_trigger와 final_block 구분"""
    metrics = CrossExchangeMetrics()
    
    # exposure_limit이 먼저 감지되었지만, daily_loss_limit이 최종 block
    decision = CrossRiskDecision(
        allowed=False,
        tier="cross_exchange",
        reason_code="cross_daily_loss_limit",
        details={},
    )
    
    context = {
        "first_trigger_reason": "cross_exposure_limit",  # 첫 감지
    }
    
    metrics.record_risk_decision(decision, context)
    
    snapshot = metrics.get_metrics_snapshot()
    
    # First trigger는 exposure_limit
    assert snapshot["counters"]["risk_first_trigger_total{reason=cross_exposure_limit}"] == 1
    
    # Final block은 daily_loss_limit
    assert snapshot["counters"]["risk_final_block_total{reason=cross_daily_loss_limit}"] == 1
    assert "risk_final_block_total{reason=cross_exposure_limit}" not in snapshot["counters"]
```

#### 1.3 Execution Result 기록
```python
def test_metrics_record_execution_result():
    """Executor 결과 기록 → metrics 업데이트"""
    metrics = CrossExchangeMetrics()
    
    result = CrossExecutionResult(
        status="success",
        upbit_result=OrderResult(status="filled", ...),
        binance_result=OrderResult(status="filled", ...),
        total_latency=1.234,
    )
    
    metrics.record_execution_result(result)
    
    snapshot = metrics.get_metrics_snapshot()
    
    assert snapshot["counters"]["cross_orders_total{exchange=upbit,status=filled}"] == 1
    assert snapshot["counters"]["cross_orders_total{exchange=binance,status=filled}"] == 1
    assert len(snapshot["histograms"]["cross_order_fill_duration_seconds{exchange=combined}"]["values"]) == 1
```

---

### 2. Integration Test

#### 2.1 RiskGuard + Metrics 통합
```python
def test_risk_guard_with_metrics_integration():
    """RiskGuard 체크 → Metrics 자동 기록 확인"""
    metrics = CrossExchangeMetrics()
    
    # RiskGuard에 metrics 주입
    risk_guard = CrossExchangeRiskGuard(
        ...,
        metrics_collector=metrics,
    )
    
    # daily_loss_limit 초과 시나리오
    decision = CrossExchangeDecision(...)
    result = risk_guard.check_cross_exchange_trade(decision)
    
    # Metrics 자동 업데이트 확인
    snapshot = metrics.get_metrics_snapshot()
    assert snapshot["counters"]["risk_final_block_total{reason=cross_daily_loss_limit}"] == 1
```

#### 2.2 Executor + Metrics 통합
```python
def test_executor_with_metrics_integration():
    """Executor 실행 → Metrics 자동 기록 확인"""
    metrics = CrossExchangeMetrics()
    
    executor = CrossExchangeExecutor(
        ...,
        metrics_collector=metrics,
    )
    
    result = executor.execute_decision(decision)
    
    # 주문 성공/실패 metrics 확인
    snapshot = metrics.get_metrics_snapshot()
    assert "cross_orders_total" in str(snapshot["counters"])
```

---

### 3. Alert Hook Test

```python
def test_alert_sent_on_circuit_breaker():
    """Circuit breaker 발동 → Alert 전송 확인"""
    alert_manager = Mock()
    metrics = CrossExchangeMetrics(alert_manager=alert_manager)
    
    decision = CrossRiskDecision(
        allowed=False,
        tier="cross_exchange",
        reason_code="cross_daily_loss_limit",
        details={"daily_pnl": -5_500_000, "limit": -5_000_000},
    )
    
    context = {"symbol_upbit": "KRW-BTC"}
    metrics.record_risk_decision(decision, context)
    
    # Alert 호출 확인
    alert_manager.send_alert.assert_called_once()
    call_args = alert_manager.send_alert.call_args
    assert call_args[1]["level"] == "P1"
    assert "Circuit Breaker" in call_args[1]["title"]
```

---

## 📋 Done Criteria

### 1. 구현 완료
- ✅ `arbitrage/monitoring/cross_exchange_metrics.py` 구현
- ✅ `InMemoryMetricsBackend` 구현 (테스트용)
- ✅ `PrometheusBackend` 인터페이스 정의 (D77 연계용)

### 2. 통합 완료
- ✅ `CrossExchangeRiskGuard`에 `metrics_collector` 주입
- ✅ `CrossExchangeExecutor`에 `metrics_collector` 주입
- ✅ `CrossExchangePnLTracker`에서 `record_pnl_snapshot()` 호출

### 3. 테스트 PASS
- ✅ Unit tests (10개 이상)
- ✅ Integration tests (5개 이상)
- ✅ Alert hook tests (2개 이상)
- ✅ 전체 D79-2~6 테스트 100% PASS

### 4. 문서 완료
- ✅ 이 설계 문서 (D79_6_CROSS_EXCHANGE_MONITORING.md)
- ✅ D_ROADMAP.md 업데이트 (D79-6 완료 상태)

### 5. Git 커밋
- ✅ Commit message: `[D79-6] Cross-Exchange Monitoring & Metrics Integration`
- ✅ 변경 파일:
  - `arbitrage/monitoring/cross_exchange_metrics.py` (신규)
  - `arbitrage/cross_exchange/risk_guard.py` (metrics hook 추가)
  - `arbitrage/cross_exchange/executor.py` (metrics hook 추가)
  - `tests/test_d79_6_monitoring.py` (신규)
  - `docs/D79_6_CROSS_EXCHANGE_MONITORING.md` (신규)
  - `D_ROADMAP.md` (D79-6 완료 표시)

---

## 🚀 향후 확장 (D80+)

### 1. Grafana Dashboard
- Cross-Exchange 전용 대시보드
- Real-time exposure/imbalance visualization
- PnL timeline
- Latency heatmap

### 2. Advanced Alerts
- 복합 조건 alert (exposure + imbalance 동시 발생)
- Alert throttling (같은 alert 반복 방지)
- On-call rotation 지원

### 3. Multi-Currency Support
- KRW/USD/USDT/BTC base pairs별 metrics 분리
- Cross-currency PnL 집계

---

## 📚 참고 자료

- D75-5: 4-Tier RiskGuard
- D76: AlertManager
- D77: Prometheus Exporter
- D79-5: CrossExchangeRiskGuard
- Prometheus Best Practices: https://prometheus.io/docs/practices/naming/
