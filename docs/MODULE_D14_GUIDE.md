# MODULE D14 – 72시간 실거래 안정화 + 고급 포지션 관리 + 대시보드 확장

## 개요

MODULE D14는 D13의 기반 위에서 **72시간 장기 실거래 안정화**, **고급 포지션 관리**, **리스크 기반 리밸런싱**, **대시보드 메트릭 확장**을 추가하는 운영 최적화 모듈입니다.

### 핵심 기능

1. **72시간 실거래 모드 엔진** (`arbitrage/longrun.py` 확장)
   - 거래/리스크 이벤트 히스토리 (JSONL)
   - 드리프트 추적 (메모리, WS, Redis)
   - 루프 지연 악화 감지
   - 자동 리밸런서 호출

2. **고급 포지션 관리** (`arbitrage/position_adv.py`)
   - 변동성 기반 포지션 사이징 (D13 확장)
   - 시장 레짐 감지 (Trending/Ranging)
   - Slippage 비용 기반 감쇠
   - 동적 노출도 조정

3. **리스크 기반 리밸런서 고도화**
   - 변동성 → 리스크 모드 → 리밸런싱 연동
   - 노출도 증가 속도 감지
   - 리스크 모드별 리밸런싱 강도 조절

4. **대시보드 메트릭 확장**
   - 변동성 (EMA 기반)
   - 노출도 드리프트 비율
   - 시장 레짐
   - 실시간 이벤트 카운트

---

## 설정 가이드

### config/live.yml 확장

```yaml
# D14: 72시간 실거래 모드
longrun:
  enabled: true
  interval_loops: 360        # 6시간마다 스냅샷
  snapshot_path: "logs/stability"
  event_logging: true        # 이벤트 로깅 활성화

# D14: 고급 포지션 관리
position_adv:
  enabled: true
  base_position_size_krw: 100000
  max_exposure_krw: 500000
  slippage_cost_threshold_pct: 0.2

# D14: 리밸런서 고도화
rebalancer:
  enabled: true
  risk_mode_rebalance_trigger: true
  exposure_drift_threshold: 0.1
```

---

## 모듈 설명

### 1. arbitrage/longrun.py (D14 확장)

**72시간 장기 실거래 모드**

```python
from arbitrage.longrun import LongRunTester

tester = LongRunTester(enabled=True, interval_loops=360)

# 거래 이벤트 기록
tester.record_event('trade', {
    'symbol': 'BTC/KRW',
    'side': 'buy',
    'quantity': 0.1,
    'price': 50000000.0
})

# 드리프트 메트릭 업데이트
tester.update_drift_metrics(metrics)

# 드리프트 비율 계산
memory_drift = tester.get_drift_rate('memory')
ws_lag_drift = tester.get_drift_rate('ws_lag')

# 루프 지연 악화 감지
if tester.check_latency_degradation():
    # 자동 리밸런서 호출
    rebalancer.rebalance()
```

**새로운 기능:**
- `record_event()`: 거래/리스크 이벤트 JSONL 로깅
- `update_drift_metrics()`: 메모리, WS, Redis 드리프트 추적
- `get_drift_rate()`: 드리프트 비율 계산 (d/dt)
- `check_latency_degradation()`: 루프 지연 악화 감지

### 2. arbitrage/position_adv.py

**고급 포지션 관리**

```python
from arbitrage.position_adv import AdvancedPositionManager

manager = AdvancedPositionManager(
    base_position_size_krw=100000.0,
    max_exposure_krw=500000.0
)

# 시장 데이터 업데이트
manager.update_market_data(
    price=50000000.0,
    bid_ask_spread_pct=0.05
)

# 동적 포지션 사이즈 계산
position_size = manager.get_dynamic_position_size(
    volatility_estimate=0.3,
    risk_mode='normal'
)

# 동적 노출도 한계 조정
adjusted_limit = manager.get_adjusted_exposure_limit(
    current_exposure_krw=200000.0,
    exposure_increase_rate=0.05
)

# 거래 기록
manager.record_trade(trade_size_krw=100000.0)
```

**시장 레짐:**
- **RANGING**: 박스권 (변동성 낮음) → 포지션 80%
- **TRENDING**: 추세 (변동성 높음) → 포지션 120%

**포지션 사이즈 계산:**
```
position_size = base_size × risk_multiplier × regime_multiplier × slippage_decay
```

---

## 새로운 메트릭

### D14 추가 메트릭

| 메트릭 | 설명 | 범위 |
|--------|------|------|
| `volatility_smoothed` | EMA 기반 변동성 | 0.0~1.0 |
| `exposure_drift_rate` | 노출도 증가 속도 | -1.0~1.0 |
| `trend_regime` | 시장 레짐 | 0=range, 1=trend |
| `live_event_count` | 실시간 이벤트 수 | 0~ |
| `risk_mode_current` | 현재 리스크 모드 | 0=normal, 1=cautious, 2=extreme |
| `failclosed_events` | Fail-closed 이벤트 | 0~ |
| `ws_freshness_seconds` | WS 신선도 | 0~ |
| `memory_drift_rate` | 메모리 드리프트 | -1.0~1.0 |
| `redis_age_drift_rate` | Redis 나이 드리프트 | -1.0~1.0 |

---

## 72시간 안정성 개선점

### 1. 자동 드리프트 감지
- 메모리 누수 조기 감지
- WS 지연 악화 추적
- Redis 연결 문제 감지

### 2. 자동 리밸런싱
- 루프 지연 2시간 악화 → 자동 리밸런서 호출
- WS stale 10분 이상 → Fail-closed

### 3. 이벤트 로깅
- 모든 거래 기록 (JSONL)
- 리스크 차단 이유 기록
- 리밸런싱 이벤트 기록

### 4. 동적 포지션 조정
- 시장 레짐 변화 감지
- 슬리피지 누적 추적
- 노출도 증가 속도 제한

---

## 실행 방법

### 72시간 모드 실행

```bash
python scripts/run_live.py --mode live --longrun 72h
```

### 이벤트 로그 분석

```bash
# 최근 이벤트 확인
tail -f logs/stability/longrun_events_*.jsonl

# 거래 이벤트만 필터링
grep '"event_type":"trade"' logs/stability/longrun_events_*.jsonl

# 리스크 차단 이벤트
grep '"event_type":"risk_block"' logs/stability/longrun_events_*.jsonl
```

---

## 테스트 시나리오

### T1: 고급 포지션 관리 테스트

```bash
python test_d14_position_adv.py
```

**기대:**
- ✅ 리스크 모드별 포지션 사이즈 변경
- ✅ 시장 레짐 감지 (Ranging/Trending)
- ✅ 슬리피지 비용 감쇠
- ✅ 동적 노출도 조정

### T2: 드리프트 감지 테스트

```bash
# 메모리 드리프트 시뮬레이션
python -c "
from arbitrage.longrun import LongRunTester
tester = LongRunTester()
for i in range(100):
    metrics = {'rss_mb': 100 + i * 2}  # 메모리 증가
    tester.update_drift_metrics(metrics)
print(f'Memory drift: {tester.get_drift_rate(\"memory\"):.2f}')
"
```

### T3: 72시간 통합 테스트

```bash
# 5 루프 시뮬레이션
python scripts/run_live.py --mode mock --loops 5 --interval 0
```

---

## 대시보드 설정 (Grafana)

### Prometheus 메트릭 추가

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'arbitrage-lite'
    static_configs:
      - targets: ['localhost:8000']
```

### Grafana 대시보드 쿼리

```promql
# 변동성 추세
volatility_smoothed

# 노출도 드리프트
exposure_drift_rate

# 시장 레짐
trend_regime

# 이벤트 카운트
increase(live_event_count[1h])

# 리스크 모드
risk_mode_current

# Fail-closed 이벤트
increase(failclosed_events[1h])
```

---

## 문제 해결

### 메모리 드리프트 감지

**증상:** `memory_drift_rate > 0.1` (10% 이상 증가)

**해결:**
1. 메모리 누수 확인
2. 거래 히스토리 정리
3. 자동 리밸런서 호출

### WS 지연 악화

**증상:** `ws_freshness_seconds > 600` (10분 이상)

**해결:**
1. WebSocket 재연결
2. Fail-closed 모드 활성화
3. 거래 차단

### 루프 지연 악화

**증상:** `check_latency_degradation() = True`

**해결:**
1. 자동 리밸런서 호출
2. 포지션 감소
3. 시스템 리소스 확인

---

## 다음 단계 (MODULE D15 예정)

1. **머신러닝 기반 변동성 예측**
   - LSTM 모델로 변동성 예측
   - 동적 임계치 조정

2. **포트폴리오 최적화**
   - 자산 간 상관관계 분석
   - 최적 포지션 비율 계산

3. **고급 리스크 관리**
   - VaR (Value at Risk) 계산
   - 스트레스 테스트

4. **완전 자동화 대시보드**
   - 웹 기반 실시간 모니터링
   - 알림 및 자동 조치

---

## 요약

**MODULE D14는 D13 기반에서 72시간 장기 실거래 안정화, 고급 포지션 관리, 리스크 기반 리밸런싱을 추가하여 프로덕션 환경에서의 완전한 자동화 운영을 가능하게 합니다.**

- ✅ 72시간 장기 실거래 모드 완성
- ✅ 고급 포지션 관리 완성
- ✅ 드리프트 추적 및 자동 대응 완성
- ✅ 메트릭 확장 완성
- ✅ 프로덕션 준비 완료
