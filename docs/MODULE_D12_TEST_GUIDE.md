# MODULE D12 – Long-Run Stability & Performance Optimization

## 개요

MODULE D12는 D11의 기반 위에서 **24h~72h 장시간 운영 안정성**, **성능 프로파일링**, **워치독 튜닝**, **자동 복구 메커니즘**을 추가하는 운영 최적화 모듈입니다.

### 핵심 기능

1. **장시간 안정성 테스트 프레임워크** (`arbitrage/longrun.py`)
   - 주기적 스냅샷 저장 (JSON)
   - 체크포인트 기반 상태 추적
   - 메모리, CPU, 네트워크, 거래 상태 모니터링

2. **성능 프로파일링** (`arbitrage/perf.py`)
   - 루프 지연 분석 (평균, P95, 최대)
   - WebSocket 지연 이동 평균 & 스파이크 감지
   - Redis heartbeat 나이 추세 분석

3. **워치독 튜닝 & Auto-reset** (`arbitrage/watchdog.py` 확장)
   - WARN 상태 자동 리셋
   - ERROR 상태 자동 리셋
   - Soft reset (비파괴적 상태 초기화)

4. **통합 모니터링** (`scripts/run_live.py`)
   - 모든 D12 모듈 자동 통합
   - 메트릭 출력에 성능 지표 포함
   - 비블로킹 설계

---

## 설정 가이드

### config/live.yml 확장 (D12)

```yaml
# 워치독 (PHASE D11 + D12)
watchdog:
  enabled: true
  # ... D11 설정 ...
  # D12: 튜닝 & Auto-reset
  warn_reset_cycles: 5            # WARN 상태 자동 리셋 사이클 수
  error_reset_cycles: 20          # ERROR 상태 자동 리셋 사이클 수
  cooldown_after_critical: 60.0   # CRITICAL 후 쿨다운 (초)

# 장시간 안정성 테스트 (PHASE D12)
longrun:
  enabled: true                   # 장시간 테스트 활성화
  interval_loops: 50              # 스냅샷 저장 간격 (루프 수)
  snapshot_path: "logs/stability" # 스냅샷 저장 경로
```

---

## 모듈 설명

### 1. arbitrage/longrun.py

**장시간 운영 안정성 테스트 프레임워크**

```python
from arbitrage.longrun import LongRunTester

tester = LongRunTester(
    enabled=True,
    interval_loops=50,
    snapshot_path="logs/stability"
)

# 루프마다 기록
tester.record_loop(loop_latency_ms)

# 주기적으로 체크포인트 생성
checkpoint = tester.take_checkpoint(metrics)
if checkpoint:
    # JSON 파일로 자동 저장: logs/stability/snapshot_<timestamp>.json
    print(f"Checkpoint saved: {checkpoint.loop_count} loops")
```

**체크포인트 내용:**
- 타임스탬프, 루프 카운트
- CPU, 메모리, 스레드 수
- WebSocket 신선도, Redis 상태
- 루프 지연 (평균, P95)
- 거래 상태 (실거래, 모의거래, 포지션)
- 손절매, 워치독 상태
- 전체 안정 여부

### 2. arbitrage/perf.py

**성능 프로파일링**

```python
from arbitrage.perf import PerformanceProfiler

profiler = PerformanceProfiler()

# 각 루프마다 기록
profiler.record_loop(latency_ms)
profiler.record_ws_lag(lag_ms)
profiler.record_redis_heartbeat(age_ms)

# 메트릭 조회
metrics = profiler.get_all_metrics()
# {
#   'loop_avg_ms': 50.5,
#   'loop_p95_ms': 120.3,
#   'loop_max_ms': 450.0,
#   'ws_lag_ma': 150.2,
#   'ws_spike_count': 3,
#   'redis_heartbeat_avg_ms': 5000.0,
#   'redis_heartbeat_max_ms': 8000.0,
#   'redis_heartbeat_trend': 'stable'
# }

# 요약 문자열
print(profiler.get_summary())
```

**프로파일러 종류:**

1. **LoopProfiler**: 루프 지연
   - 평균, P95, 최대값 추적
   - 윈도우 크기: 100 루프

2. **WebsocketLagProfiler**: WS 지연
   - 이동 평균 계산
   - 스파이크 감지 (평균의 2배 이상)

3. **RedisLatencyProfiler**: Redis heartbeat
   - 평균, 최대 나이 추적
   - 추세 분석 (increasing/stable/decreasing)

### 3. arbitrage/watchdog.py 확장 (D12)

**Auto-reset 메커니즘**

```python
config = WatchdogConfig(
    warn_reset_cycles=5,           # WARN 5 사이클 후 자동 리셋
    error_reset_cycles=20,         # ERROR 20 사이클 후 자동 리셋
    cooldown_after_critical=60.0   # CRITICAL 후 60초 쿨다운
)
watchdog = Watchdog(config)

# 자동 리셋 (내부에서 자동 호출)
watchdog.soft_reset()  # 카운터 초기화, 비파괴적
```

**상태 전이:**
```
정상 → WARN (5 사이클) → 자동 리셋 → 정상
정상 → ERROR (20 사이클) → 자동 리셋 → 정상
ERROR × 3 → CRITICAL → graceful shutdown
```

---

## 실행 방법

### 기본 실행 (D12 통합)

```bash
python scripts/run_live.py --once --mock
```

**출력 예시:**
```
[LIVE] [METRICS] ... loop_ms=50.1 loop_p95=120.3 ... live=❌
[LONGRUN] Checkpoint saved (loop=50, stable=True)
```

### 장시간 테스트 (24h 시뮬레이션)

```bash
# 1440 루프 = 24시간 (1분 간격)
python scripts/run_live.py --mode mock --loops 1440 --interval 60
```

### 72시간 테스트

```bash
# 4320 루프 = 72시간 (1분 간격)
python scripts/run_live.py --mode mock --loops 4320 --interval 60
```

### 스트레스 테스트

```bash
python test_d12_stress.py
```

---

## 테스트 시나리오

### T1: 기본 D12 통합 테스트

```bash
python scripts/run_live.py --once --mock
```

**기대:**
- ✅ LongRunTester 초기화
- ✅ PerformanceProfiler 초기화
- ✅ 메트릭 출력에 loop_p95 포함
- ✅ 로그 파일 생성

### T2: 워치독 Auto-reset 테스트

```bash
python test_d12_stress.py
```

**기대:**
- ✅ WARN 상태 5 사이클 후 자동 리셋
- ✅ ERROR 상태 20 사이클 후 자동 리셋
- ✅ Soft reset 호출 확인

### T3: 성능 프로파일러 테스트

```bash
python -c "
from arbitrage.perf import PerformanceProfiler
p = PerformanceProfiler()
for i in range(100):
    p.record_loop(50 + i*0.5)
    p.record_ws_lag(100 + i*0.2)
print(p.get_summary())
"
```

**기대:**
- ✅ P95 계산 정확
- ✅ 이동 평균 계산 정확
- ✅ 추세 분석 정확

### T4: 장시간 테스터 스냅샷

```bash
python scripts/run_live.py --mode mock --loops 100 --interval 0
```

**기대:**
- ✅ logs/stability/ 디렉토리 생성
- ✅ snapshot_*.json 파일 생성 (interval_loops마다)
- ✅ JSON 포맷 정확

### T5: 스트레스 테스트 (모든 시나리오)

```bash
python test_d12_stress.py
```

**기대:**
- ✅ 높은 WS 지연 처리
- ✅ Redis 지연 처리
- ✅ 루프 블로킹 처리
- ✅ CPU 부하 처리
- ✅ 메모리 스파이크 처리
- ✅ 워치독 auto-reset 작동
- ✅ 스냅샷 생성
- ✅ 성능 메트릭 계산

---

## 스냅샷 로그 분석

### 스냅샷 파일 위치

```
logs/stability/
├── snapshot_2025-11-15T20-57-22-906000.json
├── snapshot_2025-11-15T20-57-24-906000.json
└── ...
```

### 스냅샷 포맷

```json
{
  "timestamp": "2025-11-15T20:57:22.906000+00:00",
  "loop_count": 50,
  "cpu_pct": 15.5,
  "rss_mb": 256.3,
  "open_files": 12,
  "num_threads": 8,
  "ws_lag_ms": 150.0,
  "ws_freshness_ok": true,
  "redis_heartbeat_age_ms": 5000.0,
  "redis_ok": true,
  "loop_latency_ms": 50.1,
  "loop_latency_p95_ms": 120.3,
  "num_live_trades": 5,
  "num_paper_trades": 10,
  "num_open_positions": 2,
  "total_exposure_krw": 500000.0,
  "stoploss_triggers": 1,
  "watchdog_healthy": true,
  "watchdog_alerts": 0,
  "watchdog_consecutive_errors": 0,
  "safety_rejections": 0,
  "is_stable": true
}
```

### 스냅샷 분석 스크립트

```python
import json
from pathlib import Path

snapshot_dir = Path("logs/stability")
snapshots = sorted(snapshot_dir.glob("snapshot_*.json"))

for snapshot_file in snapshots:
    with open(snapshot_file) as f:
        data = json.load(f)
    
    print(f"Loop {data['loop_count']}: "
          f"CPU={data['cpu_pct']:.1f}%, "
          f"Mem={data['rss_mb']:.0f}MB, "
          f"Stable={data['is_stable']}")
```

---

## 루프 지연 분석

### 메트릭 출력 해석

```
[METRICS] ... loop_ms=50.1 loop_p95=120.3 ...
```

- **loop_ms**: 현재 루프 지연 (ms)
- **loop_p95**: 최근 100 루프 중 P95 지연 (ms)

### 성능 기준

| 메트릭 | 정상 | 경고 | 에러 |
|--------|------|------|------|
| loop_ms | < 100 | 100-2000 | > 2000 |
| loop_p95 | < 200 | 200-5000 | > 5000 |
| ws_lag_ms | < 500 | 500-2000 | > 2000 |
| redis_age_ms | < 5000 | 5000-15000 | > 15000 |

---

## WebSocket 메트릭 분석

### WS 지연 추세

```python
from arbitrage.perf import WebsocketLagProfiler

profiler = WebsocketLagProfiler()
# ... 기록 ...

ma = profiler.get_moving_avg()
spikes = profiler.get_spike_count()

print(f"WS Moving Avg: {ma:.1f}ms")
print(f"Spike Count: {spikes}")
```

### 스파이크 감지 기준

- 평균의 2배 이상 = 스파이크
- 예: 평균 150ms → 300ms 이상 = 스파이크

---

## 워치독 튜닝 가이드

### 기본값

```yaml
watchdog:
  warn_reset_cycles: 5            # 5 루프 = ~2.5분 (30초 간격)
  error_reset_cycles: 20          # 20 루프 = ~10분
  cooldown_after_critical: 60.0   # 60초
```

### 튜닝 시나리오

**경우 1: 자주 WARN 경고 발생**
```yaml
warn_reset_cycles: 10  # 5 → 10 (리셋 시간 연장)
```

**경우 2: ERROR 상태 자주 발생**
```yaml
error_reset_cycles: 30  # 20 → 30 (리셋 시간 연장)
```

**경우 3: 과도한 자동 리셋**
```yaml
warn_reset_cycles: 3   # 5 → 3 (리셋 시간 단축)
```

---

## 권장 배포 설정

### 24h 운영

```yaml
longrun:
  enabled: true
  interval_loops: 120         # 2시간마다 스냅샷
  snapshot_path: "logs/stability"

watchdog:
  warn_reset_cycles: 5
  error_reset_cycles: 20
```

### 72h 운영

```yaml
longrun:
  enabled: true
  interval_loops: 360         # 6시간마다 스냅샷
  snapshot_path: "logs/stability"

watchdog:
  warn_reset_cycles: 10       # 더 관대한 기준
  error_reset_cycles: 30
```

### 프로덕션 (무한 운영)

```yaml
longrun:
  enabled: true
  interval_loops: 1440        # 24시간마다 스냅샷
  snapshot_path: "logs/stability"

watchdog:
  warn_reset_cycles: 10
  error_reset_cycles: 40      # 매우 관대
  cooldown_after_critical: 300.0  # 5분 쿨다운
```

---

## 문제 해결

### 스냅샷이 생성되지 않음

**원인:** interval_loops 설정이 너무 큼

**해결:**
```yaml
longrun:
  interval_loops: 50  # 기본값으로 리셋
```

### 자동 리셋이 너무 자주 발생

**원인:** warn_reset_cycles/error_reset_cycles가 너무 작음

**해결:**
```yaml
watchdog:
  warn_reset_cycles: 10    # 5 → 10
  error_reset_cycles: 40   # 20 → 40
```

### 메모리 누수 의심

**확인:**
```bash
# 스냅샷에서 메모리 추세 확인
python -c "
import json
from pathlib import Path
for f in sorted(Path('logs/stability').glob('*.json'))[-10:]:
    data = json.load(open(f))
    print(f\"Loop {data['loop_count']}: {data['rss_mb']:.0f}MB\")
"
```

---

## 다음 단계 (MODULE D13 예정)

1. **실거래 모드 72h 테스트**
   - 실제 환경에서 D12 검증
   - 워치독 임계치 최적화

2. **성능 최적화**
   - 루프 지연 감소
   - 메트릭 수집 최적화

3. **고급 리스크 모델링**
   - 동적 손절매
   - 포트폴리오 리밸런싱

---

## 요약

**MODULE D12는 D11 기반에서 장시간 운영 안정성, 성능 프로파일링, 자동 복구를 추가하여 24h~72h 무중단 운영을 가능하게 합니다.**

- ✅ 장시간 테스트 프레임워크 완성
- ✅ 성능 프로파일링 완성
- ✅ 워치독 튜닝 & Auto-reset 완성
- ✅ 모든 모듈 통합 완성
- ✅ 프로덕션 준비 완료
