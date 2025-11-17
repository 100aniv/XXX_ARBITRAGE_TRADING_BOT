# D24 Tuning Session Runner Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [설치 및 실행](#설치-및-실행)
4. [CLI 인터페이스](#cli-인터페이스)
5. [결과 저장](#결과-저장)
6. [Observability 정책](#observability-정책)

---

## 개요

D24는 **Tuning Session Runner**를 구현합니다. D23 Tuning Engine과 D18 Paper Engine을 통합하여 실제 Paper Mode 시나리오를 실행하는 end-to-end 튜닝 세션을 제공합니다.

### 핵심 특징

- ✅ **실제 Paper Mode 실행**: 시뮬레이션 기반 튜닝
- ✅ **D23 Optimizer 통합**: Grid/Random/Bayesian 지원
- ✅ **StateManager 연동**: Redis 기반 결과 저장
- ✅ **CSV 출력**: 결과 파일 저장
- ✅ **CLI 인터페이스**: 명령줄 기반 실행
- ✅ **Observability 정책 준수**: 가짜 메트릭 없음

---

## 아키텍처

### 계층 구조

```
CLI (run_d24_tuning_session.py)
    ↓
TuningSessionRunner
    ├─ TuningHarness (D23)
    │   ├─ Optimizer (Grid/Random/Bayesian)
    │   └─ StateManager (D21)
    │       └─ Redis
    └─ Paper Engine (D18)
        └─ Scenario Execution
```

### 데이터 흐름

```
1. CLI 인자 파싱
   ├─ config: 튜닝 설정 파일
   ├─ iterations: 반복 횟수
   ├─ mode: paper/shadow/live
   ├─ env: docker/local
   ├─ optimizer: grid/random/bayesian (선택)
   └─ output-csv: 결과 파일 (선택)
   ↓
2. TuningSessionRunner 초기화
   ├─ 설정 로드
   ├─ StateManager 생성
   └─ TuningHarness 생성
   ↓
3. 반복 실행
   ├─ optimizer.ask() → 파라미터
   ├─ Paper Engine 실행 → 결과
   ├─ optimizer.tell() → 결과 기록
   └─ StateManager 저장
   ↓
4. 결과 저장
   ├─ Redis (자동)
   └─ CSV (선택)
   ↓
5. 요약 출력
```

---

## 설치 및 실행

### 사전 요구사항

1. **Python 환경**
   ```bash
   cd arbitrage-lite
   abt_bot_env\Scripts\activate
   ```

2. **Docker 스택 시작** (Paper Mode)
   ```bash
   cd infra
   docker-compose up -d redis postgres arbitrage-paper-trader
   cd ..
   ```

### 기본 실행

```bash
python scripts/run_d24_tuning_session.py \
  --config configs/d23_tuning/advanced_baseline.yaml \
  --iterations 5 \
  --mode paper \
  --env docker
```

### 결과 저장

```bash
python scripts/run_d24_tuning_session.py \
  --config configs/d23_tuning/advanced_baseline.yaml \
  --iterations 5 \
  --mode paper \
  --env docker \
  --output-csv outputs/d24_tuning_session.csv
```

### Optimizer 오버라이드

```bash
# Grid Search 사용
python scripts/run_d24_tuning_session.py \
  --config configs/d23_tuning/advanced_baseline.yaml \
  --iterations 5 \
  --optimizer grid

# Random Search 사용
python scripts/run_d24_tuning_session.py \
  --config configs/d23_tuning/advanced_baseline.yaml \
  --iterations 5 \
  --optimizer random

# Bayesian 최적화 사용
python scripts/run_d24_tuning_session.py \
  --config configs/d23_tuning/advanced_baseline.yaml \
  --iterations 5 \
  --optimizer bayesian
```

---

## CLI 인터페이스

### 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--config` | `configs/d23_tuning/advanced_baseline.yaml` | 튜닝 설정 파일 경로 |
| `--iterations` | `5` | 실행할 반복 횟수 |
| `--mode` | `paper` | 모드 (paper, shadow, live) |
| `--env` | `docker` | 환경 (docker, local) |
| `--optimizer` | None | Optimizer 방법 (grid, random, bayesian) |
| `--output-csv` | None | CSV 출력 파일 경로 |

### 출력 형식

```
[D24_TUNING] Session initialized: session_id=...
[D24_TUNING] Config: method=bayesian, scenarios=2, iterations=5
[D24_TUNING] StateManager initialized: namespace=tuning:docker:paper
[D24_TUNING] Starting tuning session: 5 iterations
[D24_TUNING] Iteration 1/5
[D24_TUNING] Running objective with params: {...}
[D24_RESULT] Iteration 1: status=completed
[D24_TUNING] Result persisted: iteration=1
...
[D24_TUNING] Session completed: 5 iterations
[D24_TUNING] Results saved to CSV: outputs/d24_tuning_session.csv

======================================================================
[D24_TUNING] SESSION SUMMARY
======================================================================
Session ID:        <uuid>
Iterations:        5/5
Mode:              paper
Environment:       docker
Optimizer:         bayesian
Namespace:         tuning:docker:paper
Scenarios:         2
Search Space:      3 parameters
CSV Output:        outputs/d24_tuning_session.csv
Timestamp:         2025-11-16T...
======================================================================
```

---

## 결과 저장

### Redis 저장

결과는 자동으로 Redis에 저장됩니다:

```
Namespace: tuning:{env}:{mode}
Key: tuning:{env}:{mode}:arbitrage:tuning_session:{session_id}:{iteration}

Value:
{
    "session_id": "...",
    "iteration": "1",
    "status": "completed",
    "timestamp": "2025-11-16T12:00:00.000000"
}
```

### CSV 저장

`--output-csv` 옵션으로 결과를 CSV 파일로 저장:

```csv
session_id,iteration,status,timestamp
550e8400-e29b-41d4-a716-446655440000,1,completed,2025-11-16T12:00:00
550e8400-e29b-41d4-a716-446655440000,2,completed,2025-11-16T12:01:00
550e8400-e29b-41d4-a716-446655440000,3,completed,2025-11-16T12:02:00
```

### Redis 조회

```bash
# Redis CLI로 결과 확인
redis-cli -h localhost -p 6380

# 네임스페이스의 모든 키 조회
keys "tuning:docker:paper:*"

# 특정 결과 조회
hgetall "tuning:docker:paper:arbitrage:tuning_session:550e8400-e29b-41d4-a716-446655440000:1"
```

---

## Observability 정책

### 정책 명시

**For all tuning / runtime scripts,
this project NEVER documents fake or "expected" outputs with concrete numbers.
Only real logs from actual executions may be shown in reports.**

### 준수 사항

1. ❌ "예상 결과", "샘플 PnL", "기대 수익률" 금지
2. ❌ 구체적인 숫자가 포함된 출력 예시 금지
3. ✅ 실제 실행 로그만 문서에 포함
4. ✅ 형식과 필드만 개념적으로 설명

### 결과 스키마 (키만)

```python
{
    "session_id": str,              # 세션 UUID
    "iteration": int,               # 반복 번호
    "params": Dict[str, Any],       # 파라미터
    "metrics": {
        "trades": int,              # 거래 수
        "total_fees": float,        # 총 수수료
        "pnl": float,               # 손익
        "circuit_breaker_active": bool,  # 회로차단기 활성화
        "safety_violations": int    # 안전 위반 수
    },
    "scenario_files": List[str],    # 시나리오 파일 목록
    "timestamp": str,               # ISO8601 타임스탬프
    "status": str                   # 상태 (completed, failed)
}
```

---

## 관련 문서

- [D23 Advanced Tuning Engine](D23_ADVANCED_TUNING_ENGINE.md)
- [D21 Observability](D21_OBSERVABILITY_AND_STATE_MANAGER.md)
- [D18 Docker Paper Validation](D18_DOCKER_PAPER_VALIDATION.md)

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready
