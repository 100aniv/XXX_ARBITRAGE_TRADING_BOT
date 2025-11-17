# D21 Observability & StateManager Redis Integration Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [StateManager 새 인터페이스](#statemanager-새-인터페이스)
3. [Redis 통합 & In-Memory Fallback](#redis-통합--in-memory-fallback)
4. [Namespace 시스템](#namespace-시스템)
5. [Observability 메트릭](#observability-메트릭)
6. [CLI 메트릭 조회](#cli-메트릭-조회)
7. [운영 가이드](#운영-가이드)

---

## 개요

D21은 **StateManager의 Redis 통합**과 **Observability 베이스라인**을 구현합니다.

### 핵심 개선사항

- ✅ **Redis 통합**: 명시적인 Redis 연결 관리
- ✅ **In-Memory Fallback**: Redis 연결 실패 시 자동 in-memory 모드 전환
- ✅ **Namespace 시스템**: Live/Paper/Shadow 모드별 key 체계화
- ✅ **Observability 메트릭**: 실시간 거래 지표 저장/조회
- ✅ **CLI 스크립트**: 메트릭을 CLI에서 조회 가능

### 문제 해결

**D18에서 발생한 문제:**
```
StateManager.__init__() got an unexpected keyword argument 'db'. 
Using in-memory state.
```

**D21 해결책:**
- `redis_db` 파라미터 추가
- `namespace` 파라미터 추가
- `enabled` 파라미터로 Redis 사용 여부 제어
- 자동 Redis 연결 시도 + fallback 메커니즘

---

## StateManager 새 인터페이스

### 시그니처

```python
class StateManager:
    def __init__(
        self,
        redis_host: Optional[str] = None,
        redis_port: Optional[int] = None,
        redis_db: int = 0,
        namespace: str = "default",
        enabled: bool = True,
        key_prefix: str = "arbitrage"
    ):
        """
        Args:
            redis_host: Redis 호스트 (None이면 환경 변수 또는 localhost)
            redis_port: Redis 포트 (None이면 환경 변수 또는 6379)
            redis_db: Redis 데이터베이스 번호
            namespace: 네임스페이스 (예: live:docker, paper:local, shadow:docker)
            enabled: Redis 사용 여부 (False면 항상 in-memory)
            key_prefix: 키 프리픽스 (기본값: arbitrage)
        """
```

### 사용 예시

#### Live Mode (Docker)

```python
from arbitrage.state_manager import StateManager

state_manager = StateManager(
    redis_host="redis",  # Docker 내부 호스트명
    redis_port=6379,     # 컨테이너 내부 포트
    redis_db=0,
    namespace="live:docker",
    enabled=True,
    key_prefix="arbitrage"
)
```

#### Paper Mode (Local)

```python
state_manager = StateManager(
    redis_host="localhost",
    redis_port=6379,
    redis_db=0,
    namespace="paper:local",
    enabled=True,
    key_prefix="arbitrage"
)
```

#### In-Memory Mode (테스트)

```python
state_manager = StateManager(
    namespace="test:memory",
    enabled=False  # Redis 사용 안 함
)
```

---

## Redis 통합 & In-Memory Fallback

### 동작 규칙

#### 1. Redis 연결 시도

```python
if enabled == True:
    try:
        redis.Redis(host, port, db).ping()
        # 성공 → Redis 모드
        self._redis_connected = True
    except Exception:
        # 실패 → In-memory 모드로 fallback
        self._redis_connected = False
        logger.warning("Redis connection failed. Using in-memory state.")
```

#### 2. 데이터 저장 (Redis/In-Memory)

```python
def _set_redis_or_memory(self, key: str, value: Any, ttl: Optional[int] = None):
    if self._redis_connected and self._redis:
        try:
            self._redis.hset(key, mapping=value)  # Redis에 저장
            if ttl:
                self._redis.expire(key, ttl)
        except Exception:
            self._in_memory_store[key] = value  # Fallback
    else:
        self._in_memory_store[key] = value  # In-memory에 저장
```

#### 3. 데이터 조회 (Redis/In-Memory)

```python
def _get_redis_or_memory(self, key: str) -> Optional[Any]:
    if self._redis_connected and self._redis:
        try:
            data = self._redis.hgetall(key)
            if data:
                return data
            value = self._redis.get(key)
            return value
        except Exception:
            return self._in_memory_store.get(key)  # Fallback
    else:
        return self._in_memory_store.get(key)  # In-memory에서 조회
```

### 환경 변수

| 환경 변수 | 기본값 | 설명 |
|----------|--------|------|
| `REDIS_HOST` | `localhost` | Redis 호스트 |
| `REDIS_PORT` | `6379` | Redis 포트 |
| `REDIS_DB` | `0` | Redis 데이터베이스 |

---

## Namespace 시스템

### Namespace 구조

Namespace는 `{mode}:{env}` 형식입니다:

| Mode | Env | Namespace | 설명 |
|------|-----|-----------|------|
| live | docker | `live:docker` | 실거래 (Docker) |
| live | local | `live:local` | 실거래 (Local) |
| paper | docker | `paper:docker` | 종이 거래 (Docker) |
| paper | local | `paper:local` | 종이 거래 (Local) |
| shadow | docker | `shadow:docker` | 섀도우 거래 (Docker) |
| shadow | local | `shadow:local` | 섀도우 거래 (Local) |

### Key 생성 규칙

```
{namespace}:{key_prefix}:{parts}

예시:
- live:docker:arbitrage:position:upbit:BTC_KRW
- paper:local:arbitrage:metrics:live
- shadow:docker:arbitrage:stats:trades_total
```

### 코드 예시

```python
# Namespace 설정
state_manager = StateManager(namespace="live:docker")

# Key 생성 (자동으로 namespace 포함)
position_key = state_manager._get_key("position", "upbit", "BTC_KRW")
# → "live:docker:arbitrage:position:upbit:BTC_KRW"

metrics_key = state_manager._get_key("metrics", "live")
# → "live:docker:arbitrage:metrics:live"
```

---

## Observability 메트릭

### 핵심 메트릭

| 메트릭 | 타입 | 설명 |
|--------|------|------|
| `trades_total` | Counter | 누적 거래 수 |
| `trades_today` | Counter | 오늘 거래 수 |
| `safety_violations_total` | Counter | 누적 안전 위반 수 |
| `circuit_breaker_triggers_total` | Counter | 누적 회로차단기 발동 수 |
| `last_heartbeat` | Timestamp | 마지막 하트비트 |
| `total_balance` | Gauge | 총 잔액 |
| `available_balance` | Gauge | 사용 가능 잔액 |
| `total_position_value` | Gauge | 포지션 총액 |

### 메트릭 저장

```python
# 통계 증가
state_manager.increment_stat("trades_total", 1.0)
state_manager.increment_stat("safety_violations_total", 1.0)

# 메트릭 저장
metrics = {
    "trades_total": 42,
    "trades_today": 5,
    "safety_violations_total": 0,
    "circuit_breaker_triggers_total": 0,
    "avg_trade_pnl": 1500.50
}
state_manager.set_metrics(metrics)

# 하트비트 저장
state_manager.set_heartbeat("live_trader")
```

### 메트릭 조회

```python
# 통계 조회
trades = state_manager.get_stat("trades_total")

# 메트릭 조회
metrics = state_manager.get_metrics()

# 하트비트 조회
heartbeat = state_manager.get_heartbeat("live_trader")
```

---

## CLI 메트릭 조회

### 스크립트 위치

```
scripts/show_live_metrics.py
```

### 사용법

#### 기본 사용 (Live 모드, Docker 환경)

```bash
python scripts/show_live_metrics.py
```

#### 모드 지정

```bash
# Paper 모드
python scripts/show_live_metrics.py --mode paper

# Shadow 모드
python scripts/show_live_metrics.py --mode shadow
```

#### 환경 지정

```bash
# Local 환경
python scripts/show_live_metrics.py --env local

# Docker 환경 (기본값)
python scripts/show_live_metrics.py --env docker
```

#### 출력 형식 지정

```bash
# 테이블 형식 (기본값)
python scripts/show_live_metrics.py --format table

# JSON 형식
python scripts/show_live_metrics.py --format json

# 로그 형식
python scripts/show_live_metrics.py --format log
```

### 출력 형식 설명

**테이블 형식:**
- 메트릭을 그룹별로 구분하여 표 형태로 출력
- 각 행은 `key = value` 형식
- 조회 시간 포함

**JSON 형식:**
- 네임스페이스, 타임스탬프, 메트릭을 JSON 객체로 출력
- 프로그래밍 방식의 파싱에 적합

**로그 형식:**
- `[METRICS] key=value` 스타일의 로그 라인들
- 로그 파일에 추가하기에 적합

---

## ⚠️ Observability 정책

**For all runtime metrics / observability scripts (like show_live_metrics.py),
this project NEVER documents fake or "expected" outputs with concrete numbers.
Only real logs from actual executions may be shown in reports, otherwise we only describe the format and fields conceptually.**

이 정책은 다음을 의미합니다:

1. **운영/메트릭/관측 관련 스크립트**에 대해 "예상 출력", "샘플 출력", "예상 결과" 같은 표현을 사용하지 않습니다.
2. **실제 숫자가 포함된 출력 예시**는 절대 문서에 적지 않습니다.
3. **형식과 필드**만 개념적으로 설명합니다.
4. **유일한 예외**: pytest 테스트 결과 (예: `PASSED`, `FAILED`)는 실제 실행 로그를 보고할 수 있습니다.

---

## 운영 가이드

### StateManager 초기화 (각 모드별)

#### Live Trader

```python
# arbitrage/live_trader.py
from arbitrage.state_manager import StateManager

env_app_env = os.getenv("APP_ENV", "docker")
self.state_manager = StateManager(
    redis_host=redis_host,
    redis_port=redis_port,
    redis_db=0,
    namespace=f"live:{env_app_env}",
    enabled=True,
    key_prefix="arbitrage"
)
```

#### Paper Trader

```python
# arbitrage/paper_trader.py
from arbitrage.state_manager import StateManager

self.state_manager = StateManager(
    redis_host=redis_host,
    redis_port=redis_port,
    redis_db=0,
    namespace="paper:local",
    enabled=True,
    key_prefix="arbitrage"
)
```

### Redis 연결 확인

```bash
# Redis 연결 상태 확인
redis-cli -h localhost -p 6380 ping
# → PONG

# 저장된 key 확인
redis-cli -h localhost -p 6380 keys "live:docker:arbitrage:*"

# 특정 key 조회
redis-cli -h localhost -p 6380 hgetall "live:docker:arbitrage:metrics:live"
```

### 메트릭 모니터링

```bash
# 1분마다 메트릭 조회
watch -n 1 'python scripts/show_live_metrics.py --mode live --env docker'

# JSON으로 저장
python scripts/show_live_metrics.py --mode live --env docker --format json > metrics.json

# 로그 형식으로 파일에 저장
python scripts/show_live_metrics.py --mode live --env docker --format log >> metrics.log
```

---

## 호환성 및 마이그레이션

### D16 테스트 호환성

D16 테스트는 새로운 StateManager 시그니처에 맞게 업데이트되었습니다:

```python
# 이전 (D16)
manager = StateManager()

# 현재 (D21)
manager = StateManager(
    redis_host="localhost",
    redis_port=6379,
    redis_db=0,
    namespace="test:local",
    enabled=True,
    key_prefix="arbitrage"
)
```

### 기존 코드 마이그레이션

```python
# 이전
state_manager = StateManager(
    redis_host="localhost",
    redis_port=6379
)
state_manager.connect()

# 현재
state_manager = StateManager(
    redis_host="localhost",
    redis_port=6379,
    namespace="live:docker",
    enabled=True
)
# 자동으로 연결 시도 (성공 또는 in-memory fallback)
```

---

## 알려진 제한사항 & 향후 계획

### 현재 제한사항

1. **메트릭 만료 정책**: TTL 기반 자동 만료 (5분~24시간)
2. **메트릭 집계**: 실시간 메트릭만 제공 (히스토리 없음)
3. **대시보드**: CLI 스크립트만 제공 (UI 없음)
4. **Prometheus**: 메트릭 내보내기 미지원

### D22 이후 계획

- [ ] **Prometheus 통합**: 메트릭 내보내기
- [ ] **Grafana 대시보드**: 시각화
- [ ] **메트릭 히스토리**: 시계열 데이터 저장
- [ ] **알림 시스템**: 임계값 기반 알림
- [ ] **튜닝 프레임워크**: 자동 최적화

---

## 관련 문서

- [D20 LIVE ARM Guide](D20_LIVE_ARM_GUIDE.md)
- [D19 Live Mode Guide](D19_LIVE_MODE_GUIDE.md)

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready
