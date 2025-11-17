# D27 Real-time Monitoring & Health Status Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [Live/Paper 모니터](#livepaper-모니터)
3. [Tuning 모니터](#tuning-모니터)
4. [watch_status.py 사용법](#watch_statuspy-사용법)
5. [아키텍처](#아키텍처)

---

## 개요

D27은 **Live/Paper/Tuning 상태를 실시간으로 모니터링**하는 기능을 제공합니다.

### 핵심 특징

- ✅ **Live/Paper 상태 스냅샷**: 현재 거래 상태 조회
- ✅ **Tuning 세션 모니터**: 진행 상황 실시간 추적
- ✅ **CLI 도구**: watch_status.py로 터미널에서 모니터링
- ✅ **StateManager 통합**: 모든 데이터는 StateManager를 통해 접근
- ✅ **Observability 정책 준수**: 가짜 메트릭 없음

---

## Live/Paper 모니터

### LiveStatusSnapshot

현재 Live/Paper 상태를 스냅샷으로 캡처합니다.

```python
@dataclass
class LiveStatusSnapshot:
    mode: str                           # "live" | "paper" | "shadow"
    env: str                            # "docker" | "local"
    live_enabled: bool
    live_armed: bool
    last_heartbeat: Optional[datetime]
    trades_total: Optional[int]
    trades_today: Optional[int]
    safety_violations_total: Optional[int]
    circuit_breaker_triggers_total: Optional[int]
    total_balance: Optional[float]
    available_balance: Optional[float]
    total_position_value: Optional[float]
    timestamp: datetime
```

### LiveStatusMonitor

StateManager를 통해 현재 상태를 로드합니다.

```python
class LiveStatusMonitor:
    def __init__(
        self,
        mode: str = "paper",
        env: str = "docker",
        state_manager: Optional[StateManager] = None
    ):
        ...
    
    def load_snapshot(self) -> LiveStatusSnapshot:
        """현재 Live/Paper 상태 스냅샷 로드"""
        # StateManager에서 데이터 읽기
        # portfolio_state, stats, heartbeat 등 수집
        # LiveStatusSnapshot 반환
```

### 데이터 소스

| 필드 | 소스 | Key |
|------|------|-----|
| trades_total | StateManager.get_stat() | "trades_total" |
| trades_today | StateManager.get_stat() | "trades_today" |
| safety_violations_total | StateManager.get_stat() | "safety_violations_total" |
| circuit_breaker_triggers_total | StateManager.get_stat() | "circuit_breaker_triggers_total" |
| total_balance | StateManager.get_portfolio_state() | "total_balance" |
| available_balance | StateManager.get_portfolio_state() | "available_balance" |
| total_position_value | StateManager.get_portfolio_state() | "total_position_value" |
| last_heartbeat | StateManager.get_heartbeat() | "heartbeat:trader" |

---

## Tuning 모니터

### TuningStatusSnapshot

현재 튜닝 세션 상태를 스냅샷으로 캡처합니다.

```python
@dataclass
class TuningStatusSnapshot:
    session_id: str
    total_iterations: int
    completed_iterations: int
    workers: List[str]
    metrics_keys: List[str]
    last_update: Optional[datetime]
    timestamp: datetime
    
    @property
    def progress_pct(self) -> float:
        """진행률 (%)"""
        if self.total_iterations == 0:
            return 0.0
        return (self.completed_iterations / self.total_iterations) * 100
```

### TuningStatusMonitor

Redis에서 튜닝 결과를 스캔하여 현재 진행 상황을 파악합니다.

```python
class TuningStatusMonitor:
    def __init__(
        self,
        session_id: str,
        total_iterations: int,
        env: str = "docker",
        mode: str = "paper",
        state_manager: Optional[StateManager] = None
    ):
        ...
    
    def load_snapshot(self) -> TuningStatusSnapshot:
        """현재 튜닝 세션 상태 스냅샷 로드"""
        # Redis에서 tuning_session:{session_id}:worker:*:iteration:* 패턴 스캔
        # completed_iterations, workers, metrics_keys 수집
        # TuningStatusSnapshot 반환
```

### 데이터 수집 방식

1. **Redis 스캔**: `tuning_session:{session_id}:worker:*:iteration:*` 패턴
2. **Key 파싱**: worker_id와 iteration 추출
3. **진행률 계산**: completed_iterations / total_iterations
4. **워커 목록**: 고유 worker_id 수집

---

## watch_status.py 사용법

### 기본 명령어

#### Live/Paper 상태 조회 (한 번)

```bash
python scripts/watch_status.py --target live --env docker
python scripts/watch_status.py --target paper --env docker
python scripts/watch_status.py --target shadow --env docker
```

#### Live/Paper 상태 모니터링 (5초마다)

```bash
python scripts/watch_status.py --target paper --env docker --interval 5
```

#### Tuning 세션 상태 조회 (한 번)

```bash
python scripts/watch_status.py \
  --target tuning \
  --session-id <session-id> \
  --total-iterations 5
```

#### Tuning 세션 상태 모니터링 (3초마다)

```bash
python scripts/watch_status.py \
  --target tuning \
  --session-id <session-id> \
  --total-iterations 5 \
  --interval 3
```

### 옵션

```
--target {live, paper, shadow, tuning}
  모니터링 대상 (필수)

--env {docker, local}
  환경 (기본값: docker)

--mode {paper, shadow, live}
  튜닝 모드 (기본값: paper)

--session-id <ID>
  튜닝 세션 ID (tuning 대상 필수)

--total-iterations <N>
  총 반복 수 (튜닝용, 기본값: 0)

--interval <N>
  갱신 주기 (초). 지정하면 무한 모니터링, 미지정하면 한 번만 조회
```

---

## 아키텍처

### 데이터 흐름

```
StateManager (Redis)
    ↓
LiveStatusMonitor / TuningStatusMonitor
    ↓
LiveStatusSnapshot / TuningStatusSnapshot
    ↓
watch_status.py
    ↓
터미널 출력
```

### Namespace 구조

#### Live/Paper

```
Namespace: live:{env} 또는 paper:{env}
예: live:docker, paper:docker
```

#### Tuning

```
Namespace: tuning:{env}:{mode}
Key Pattern: tuning_session:{session_id}:worker:{worker_id}:iteration:{iteration}
예: tuning:docker:paper
```

### StateManager 통합

모든 모니터링 데이터는 **StateManager를 통해서만** 접근합니다.

- ✅ Redis 연결 실패 시 in-memory fallback
- ✅ 직접 Redis 접근 없음 (StateManager wrapper 사용)
- ✅ 네임스페이스 기반 격리

---

## 관련 문서

- [D26 Tuning Parallel & Analysis](D26_TUNING_PARALLEL_AND_ANALYSIS.md)
- [D25 Real Paper Validation](D25_REAL_PAPER_VALIDATION.md)
- [D21 Observability & State Manager](D21_OBSERVABILITY_AND_STATE_MANAGER.md)

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready
