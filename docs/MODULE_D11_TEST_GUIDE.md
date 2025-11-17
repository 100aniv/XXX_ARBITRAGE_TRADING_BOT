# MODULE D11 – Stability & Ops Hardening

## 개요

MODULE D11은 D1~D10의 비즈니스 로직을 건드리지 않으면서, **중앙 로깅 시스템**, **워치독 모니터링**, **리소스 추적**을 추가하여 **24/7 안정 운용**을 가능하게 하는 운영 인프라 강화 모듈입니다.

### 핵심 기능

1. **중앙 로깅 시스템**: 공통 로거, 파일 로테이션, 구조화된 포맷
2. **워치독 모니터링**: 메트릭 기반 상태 판단, 단계적 경고, graceful shutdown
3. **리소스 모니터링**: CPU/메모리 추적 (선택적 psutil)
4. **운영 친화성**: 로그 파일, 메트릭, 경고를 통한 장시간 운용 지원

---

## 설정 가이드

### 1. config/live.yml 확장 (D11)

```yaml
# 로깅 (PHASE D11)
logging:
  level: "INFO"  # DEBUG | INFO | WARNING | ERROR
  file: "logs/live.log"

# 시스템 모니터 (PHASE D11)
sys_monitor:
  enabled: true                   # psutil 기반 리소스 모니터링
  max_cpu_pct: 90.0              # CPU 임계치 (%)
  max_rss_mb: 2048.0             # 메모리 임계치 (MB)
  warn_cpu_pct: 75.0             # CPU 경고 임계치 (%)
  warn_rss_mb: 1536.0            # 메모리 경고 임계치 (MB)
  sample_interval_sec: 30.0      # 샘플 간격 (초)

# 워치독 (PHASE D11)
watchdog:
  enabled: true                   # 워치독 활성화
  max_ws_lag_ms: 5000.0          # 최대 WS 지연 (ms)
  ws_lag_warn_threshold_ms: 2000.0
  max_redis_heartbeat_age_ms: 30000.0
  redis_heartbeat_warn_threshold_ms: 15000.0
  max_loop_latency_ms: 5000.0
  loop_latency_warn_threshold_ms: 2000.0
  max_safety_rejections_per_minute: 10
  max_live_errors_per_minute: 5
```

---

## 모듈 설명

### 1. arbitrage/logging_utils.py

**공통 로거 제공**

```python
from arbitrage.logging_utils import get_live_loop_logger

logger = get_live_loop_logger()
logger.info("메시지")  # logs/live_loop.log에 기록
```

**특징:**
- 콘솔 + 파일 로그 동시 지원
- 일 단위 로테이션 (자정마다 새 파일)
- 구조화된 포맷: `timestamp [level] [logger_name] message`

**로그 파일:**
- `logs/live_loop.log`: 메인 루프 로그
- `logs/health.log`: 헬스 체크 로그
- `logs/safety.log`: 안전 검증 로그
- `logs/watchdog.log`: 워치독 로그
- `logs/sys_monitor.log`: 시스템 모니터 로그

### 2. arbitrage/watchdog.py

**메트릭 기반 상태 모니터링**

```python
from arbitrage.watchdog import Watchdog, WatchdogConfig

config = WatchdogConfig(
    max_ws_lag_ms=5000.0,
    max_loop_latency_ms=5000.0
)
watchdog = Watchdog(config)

# 메인 루프에서
status = watchdog.evaluate(metrics)
if status.should_shutdown:
    # graceful shutdown
    break
```

**감시 대상:**
- WebSocket 지연 (ws_lag_ms)
- Redis heartbeat 나이
- 메인 루프 지연 (loop_latency_ms)
- 안전 검증 거부 수

**경고 단계:**
- 🟢 OK: 모든 메트릭 정상
- 🟡 WARN: 경고 임계치 초과
- 🟠 ERROR: 에러 임계치 초과
- 🔴 CRITICAL: 연속 ERROR 3회 이상 → graceful shutdown

### 3. arbitrage/sys_monitor.py

**리소스 모니터링 (선택적)**

```python
from arbitrage.sys_monitor import SystemMonitor, SysMonitorConfig

config = SysMonitorConfig(
    enabled=True,
    max_cpu_pct=90.0,
    max_rss_mb=2048.0
)
monitor = SystemMonitor(config)

sample = monitor.sample()
print(f"CPU: {sample.cpu_pct}%, Memory: {sample.rss_mb}MB")
```

**특징:**
- psutil 없는 환경에서 graceful fallback
- CPU, 메모리, 파일 디스크립터, 스레드 수 추적
- 임계치 기반 경고

---

## 실행 방법

### 기본 실행

```bash
python scripts/run_live.py --once --mock
```

**출력:**
```
[LIVE] [METRICS] pnl=0₩ trades=0 open_pos=0 exposure=0₩ realized_pnl=0₩ signals=0 exec_rate=0.0% safety_rejections=0 sl_triggers=0 loop_ms=0.0 cpu=0.0% mem=0MB live=❌
```

### 다중 루프 스트레스 테스트

```bash
python scripts/run_live.py --mode mock --loops 50 --interval 1
```

**옵션:**
- `--loops N`: N번 루프 실행 후 종료
- `--interval S`: 루프 간격 (초)
- `--mode mock|paper|live`: 실행 모드 지정

### 모드별 실행

```bash
# Mock 모드 (완전 시뮬레이션)
python scripts/run_live.py --mode mock --once

# Paper 모드 (실제 시세, 모의 주문)
python scripts/run_live.py --mode paper --once

# Live 모드 (실제 시세 + 실제 주문, 보호 필수)
export LIVE_TRADING=1
touch .live_trading_ok
python scripts/run_live.py --mode live
```

---

## 테스트 시나리오

### T1: 기본 헬스 체크

```bash
python scripts/run_live.py --once --mock
```

**기대:**
- ✅ 모든 엔진 정상 초기화
- ✅ 로그 파일 생성 (logs/live_loop.log)
- ✅ 메트릭 출력 (cpu, mem 포함)
- ✅ 워치독 상태 OK

### T2: 워치독 유닛 테스트

```bash
python test_d11_watchdog.py
```

**기대:**
- ✅ 정상 상태: 🟢 OK
- ✅ 경고 상태: 🟡 WARN
- ✅ 에러 상태: 🟠 ERROR
- ✅ 연속 에러: 🔴 CRITICAL → shutdown

### T3: 시스템 모니터 테스트

```bash
python test_d11_sys_monitor.py
```

**기대:**
- ✅ psutil 없을 때 graceful fallback
- ✅ CPU/메모리 샘플링
- ✅ 임계치 확인

### T4: 로깅 시스템 테스트

```bash
python test_d11_logging.py
```

**기대:**
- ✅ 로그 디렉토리 생성
- ✅ 컴포넌트별 로거 생성
- ✅ 로그 파일 기록

### T5: 다중 루프 스트레스 테스트

```bash
python scripts/run_live.py --mode mock --loops 50 --interval 0.5
```

**기대:**
- ✅ 50 루프 정상 완료
- ✅ 메모리 누수 없음
- ✅ 워치독 경고 없음 (기본값)

### T6: Docker 통합 (선택)

```bash
docker-compose -f infra/docker-compose.yml up -d
docker-compose -f infra/docker-compose.yml logs arbitrage-app
docker-compose -f infra/docker-compose.yml down
```

**기대:**
- ✅ 컨테이너 정상 기동
- ✅ 로그에 D11 메시지 포함
- ✅ 정상 종료

---

## 로그 분석

### 로그 파일 위치

```
logs/
├── live_loop.log        # 메인 루프 로그
├── health.log           # 헬스 체크 로그
├── safety.log           # 안전 검증 로그
├── watchdog.log         # 워치독 로그
└── sys_monitor.log      # 시스템 모니터 로그
```

### 로그 포맷

```
2025-11-15 20:56:14,510 [INFO    ] [arbitrage.live_loop] [LIVE] Starting Live Trading Service (PHASE D4)
```

**구성:**
- `timestamp`: 시간
- `[level]`: 로그 레벨 (INFO, WARNING, ERROR)
- `[logger_name]`: 로거 이름
- `message`: 메시지

### 실시간 모니터링

```bash
# 메인 루프 로그 모니터링
tail -f logs/live_loop.log

# 워치독 경고만 필터링
tail -f logs/watchdog.log | grep -i "warn\|error\|critical"

# 모든 로그 모니터링
tail -f logs/*.log
```

---

## 운영 체크리스트

### 시작 전

- [ ] config/live.yml 확인 (watchdog, sys_monitor 설정)
- [ ] logs/ 디렉토리 권한 확인
- [ ] 로그 로테이션 설정 확인 (7일 보관)

### 운영 중

- [ ] 메트릭 로그 정기 확인
- [ ] 워치독 경고 모니터링
- [ ] 리소스 사용량 추적
- [ ] 로그 파일 크기 확인

### 문제 발생 시

**메모리 누수 의심:**
```bash
# 메모리 사용량 추적
tail -f logs/live_loop.log | grep "mem="
```

**워치독 경고 발생:**
```bash
# 경고 상세 확인
tail -f logs/watchdog.log
```

**로그 파일 과다:**
```bash
# 로그 파일 크기 확인
du -sh logs/
# 오래된 파일 삭제
find logs/ -name "*.log.*" -mtime +7 -delete
```

---

## 하위 호환성

- ✅ D1-D10 완벽 호환
- ✅ 기존 설정 유지 (watchdog, sys_monitor 기본값 보수적)
- ✅ 모든 기존 테스트 통과
- ✅ D11 기능 선택적 (enabled: true/false)

---

## 알려진 제한사항

### psutil 미설치

- **증상**: `[SysMonitor] psutil not installed, system monitoring disabled`
- **해결**: `pip install psutil` (선택사항)
- **영향**: CPU/메모리 모니터링 비활성화, 나머지 기능 정상

### 로그 파일 권한

- **증상**: `Permission denied` when writing logs
- **해결**: `chmod 755 logs/` 또는 디렉토리 소유권 확인

### 워치독 과도한 경고

- **증상**: 정상 운영 중 WARN/ERROR 경고 과다
- **해결**: config/live.yml의 임계치 조정 (예: max_loop_latency_ms 증가)

---

## 다음 단계 (MODULE D12 예정)

- 실거래 모드 장기 운영 테스트 (72시간+)
- 성능 최적화 및 튜닝
- 고급 리스크 모델링
- 자동 손절매 최적화
- 포트폴리오 리밸런싱 고도화
- 시크릿/설정 구조 리팩토링 (환경 변수 중앙화)

---

## 참고

- **D1-D10**: 비즈니스 로직 (변경 없음)
- **D11**: 운영 인프라 (로깅, 모니터링, 워치독)
- **D12+**: 성능 최적화 및 고도화
