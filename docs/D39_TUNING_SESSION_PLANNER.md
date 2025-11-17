# D39 Tuning Session Planner Guide

**Document Version:** 1.0  
**Date:** 2025-11-17  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [핵심 개념](#핵심-개념)
3. [세션 설정](#세션-설정)
4. [작업 계획 생성](#작업-계획-생성)
5. [사용 예시](#사용-예시)

---

## 개요

D39 Tuning Session Planner는 **대규모 매개변수 그리드 스윕**을 계획하는 도구입니다.

### 특징

- ✅ 매개변수 그리드 정의 (이산 값 목록)
- ✅ 카르테시안 곱 생성 (모든 조합)
- ✅ 결정론적 작업 계획 생성
- ✅ JSONL 형식 출력 (D38 CLI 호환)
- ✅ 오프라인 전용 (외부 API 호출 없음)

### 목적

- 하나의 데이터셋에 대해 여러 설정으로 백테스트 실행
- 각 설정을 독립적인 D38 작업으로 변환
- 대규모 파라미터 탐색 자동화

### 아키텍처 위치

```
D39 Session Planner
    ↓
Generate Job Plans (JSONL)
    ↓
D38 Tuning Job Runner (many jobs)
    ↓
D39 Results Aggregator
```

---

## 핵심 개념

### ParamGrid

```python
@dataclass
class ParamGrid:
    name: str              # 매개변수 이름 (e.g., "min_spread_bps")
    values: List[float]    # 이산 값 목록 (e.g., [20, 30, 40])
```

**예시:**
```python
ParamGrid(name="min_spread_bps", values=[20, 30, 40])
ParamGrid(name="slippage_bps", values=[3, 5, 7])
```

### TuningSessionConfig

```python
@dataclass
class TuningSessionConfig:
    # 데이터 입력
    data_file: str

    # 고정 매개변수 (모든 작업에 적용)
    min_spread_bps: Optional[float] = None
    taker_fee_a_bps: Optional[float] = None
    taker_fee_b_bps: Optional[float] = None
    slippage_bps: Optional[float] = None
    max_position_usd: Optional[float] = None
    max_open_trades: Optional[int] = 1
    initial_balance_usd: float = 10_000.0
    stop_on_drawdown_pct: Optional[float] = None

    # 매개변수 그리드 (스윕)
    grids: List[ParamGrid] = field(default_factory=list)

    # 선택적 제어
    max_jobs: Optional[int] = None      # 조합 수 제한
    tag_prefix: Optional[str] = None    # 작업 ID 접두사
```

### TuningJobPlan

```python
@dataclass
class TuningJobPlan:
    job_id: str              # 고유 ID (e.g., "sess001_0001")
    config: Dict[str, Any]   # TuningConfig 필드와 일치하는 딕셔너리
    output_json: str         # 이 작업의 제안 출력 경로
```

### TuningSessionPlanner

```python
class TuningSessionPlanner:
    def __init__(self, session_config: TuningSessionConfig):
        """세션 설정으로 플래너 초기화"""

    def generate_jobs(self) -> List[TuningJobPlan]:
        """
        작업 계획 목록 생성 (그리드에 대한 카르테시안 곱)
        
        단계:
        1. 모든 ParamGrid 값 결합 (카르테시안 곱)
        2. TuningSessionConfig의 고정 매개변수 적용
        3. 각 계획에 data_file 추가
        4. max_jobs 설정 시 결정론적 잘라내기
        5. 각 계획에 job_id 및 output_json 생성
        """
```

---

## 세션 설정

### YAML 형식

```yaml
# 필수
data_file: data/sample_arbitrage_prices.csv

# 고정 매개변수
min_spread_bps: 30
taker_fee_a_bps: 5
taker_fee_b_bps: 5
slippage_bps: 5
max_position_usd: 1000
initial_balance_usd: 10000

# 매개변수 그리드 (스윕)
grids:
  - name: min_spread_bps
    values: [20, 30, 40]
  - name: slippage_bps
    values: [3, 5, 7]

# 선택적 제어
max_jobs: 50
tag_prefix: "sess001"
```

### JSON 형식

```json
{
  "data_file": "data/sample_arbitrage_prices.csv",
  "min_spread_bps": 30,
  "taker_fee_a_bps": 5,
  "taker_fee_b_bps": 5,
  "slippage_bps": 5,
  "max_position_usd": 1000,
  "initial_balance_usd": 10000,
  "grids": [
    {
      "name": "min_spread_bps",
      "values": [20, 30, 40]
    },
    {
      "name": "slippage_bps",
      "values": [3, 5, 7]
    }
  ],
  "max_jobs": 50,
  "tag_prefix": "sess001"
}
```

---

## 작업 계획 생성

### CLI 사용

```bash
# 기본 사용
python -m scripts.plan_tuning_session \
  --session-file configs/tuning/session001.yaml \
  --output-jobs-file outputs/tuning/session001_jobs.jsonl

# JSON 설정 파일 사용
python -m scripts.plan_tuning_session \
  --session-file configs/tuning/session001.json \
  --output-jobs-file outputs/tuning/session001_jobs.jsonl
```

### Python API 사용

```python
from arbitrage.tuning_session import (
    ParamGrid,
    TuningSessionConfig,
    TuningSessionPlanner,
)

# 세션 설정 생성
grids = [
    ParamGrid(name="min_spread_bps", values=[20, 30, 40]),
    ParamGrid(name="slippage_bps", values=[3, 5, 7]),
]

config = TuningSessionConfig(
    data_file="data/sample_arbitrage_prices.csv",
    min_spread_bps=30.0,
    taker_fee_a_bps=5.0,
    taker_fee_b_bps=5.0,
    slippage_bps=5.0,
    max_position_usd=1000.0,
    grids=grids,
    tag_prefix="sess001",
)

# 작업 계획 생성
planner = TuningSessionPlanner(config)
jobs = planner.generate_jobs()

# 결과 확인
for job in jobs:
    print(f"Job ID: {job.job_id}")
    print(f"Config: {job.config}")
    print(f"Output: {job.output_json}")
    print()
```

### 출력 형식 (JSONL)

```jsonl
{"job_id": "sess001_0001", "config": {"data_file": "data/sample_arbitrage_prices.csv", "min_spread_bps": 20, "slippage_bps": 3, ...}, "output_json": "outputs/tuning/sess001/sess001_0001.json"}
{"job_id": "sess001_0002", "config": {"data_file": "data/sample_arbitrage_prices.csv", "min_spread_bps": 20, "slippage_bps": 5, ...}, "output_json": "outputs/tuning/sess001/sess001_0002.json"}
{"job_id": "sess001_0003", "config": {"data_file": "data/sample_arbitrage_prices.csv", "min_spread_bps": 20, "slippage_bps": 7, ...}, "output_json": "outputs/tuning/sess001/sess001_0003.json"}
...
```

---

## 사용 예시

### 예시 1: 기본 그리드 스윕

**세션 설정 (session001.yaml):**
```yaml
data_file: data/sample_arbitrage_prices.csv
min_spread_bps: 30
taker_fee_a_bps: 5
taker_fee_b_bps: 5
slippage_bps: 5
max_position_usd: 1000
initial_balance_usd: 10000

grids:
  - name: min_spread_bps
    values: [20, 30, 40]

tag_prefix: "sess001"
```

**작업 계획 생성:**
```bash
python -m scripts.plan_tuning_session \
  --session-file configs/tuning/session001.yaml \
  --output-jobs-file outputs/tuning/session001_jobs.jsonl
```

**결과:** 3개 작업 생성 (min_spread_bps: 20, 30, 40)

### 예시 2: 2D 그리드 스윕

**세션 설정 (session002.yaml):**
```yaml
data_file: data/sample_arbitrage_prices.csv
min_spread_bps: 30
taker_fee_a_bps: 5
taker_fee_b_bps: 5
slippage_bps: 5
max_position_usd: 1000

grids:
  - name: min_spread_bps
    values: [20, 30, 40]
  - name: slippage_bps
    values: [3, 5, 7]

max_jobs: 6
tag_prefix: "sess002"
```

**결과:** 6개 작업 생성 (3 × 2 = 6 조합)

### 예시 3: 3D 그리드 스윕 (제한)

**세션 설정 (session003.yaml):**
```yaml
data_file: data/sample_arbitrage_prices.csv
min_spread_bps: 30
taker_fee_a_bps: 5
taker_fee_b_bps: 5
slippage_bps: 5
max_position_usd: 1000

grids:
  - name: min_spread_bps
    values: [20, 30, 40]
  - name: slippage_bps
    values: [3, 5, 7]
  - name: max_position_usd
    values: [500, 1000, 1500]

max_jobs: 10  # 27개 중 10개만 생성
tag_prefix: "sess003"
```

**결과:** 10개 작업 생성 (결정론적 순서로 처음 10개)

---

## 워크플로우

### 전체 파이프라인

```
1. 세션 설정 파일 작성 (YAML/JSON)
   ↓
2. plan_tuning_session CLI 실행
   ↓
3. JSONL 작업 계획 생성
   ↓
4. 각 작업에 대해 run_arbitrage_tuning 실행
   ↓
5. JSON 결과 파일 생성
   ↓
6. aggregate_tuning_results로 결과 분석
```

### 자동화 예시 (Bash)

```bash
#!/bin/bash

# 1. 작업 계획 생성
python -m scripts.plan_tuning_session \
  --session-file configs/tuning/session001.yaml \
  --output-jobs-file outputs/tuning/session001_jobs.jsonl

# 2. 각 작업 실행
while IFS= read -r line; do
    job_id=$(echo "$line" | jq -r '.job_id')
    config=$(echo "$line" | jq -r '.config')
    output_json=$(echo "$line" | jq -r '.output_json')
    
    # config를 CLI 인자로 변환하여 run_arbitrage_tuning 실행
    # (이 부분은 추가 스크립트 필요)
    
    echo "Running job: $job_id"
done < outputs/tuning/session001_jobs.jsonl

# 3. 결과 집계
python -m scripts.aggregate_tuning_results \
  --results-dir outputs/tuning/sess001 \
  --max-results 10 \
  --max-drawdown-pct 15 \
  --output-json outputs/tuning/session001_summary.json
```

---

## 주요 특징

### 결정론적 생성

- 같은 설정 → 같은 작업 계획
- 작업 ID 순서 일관성
- 재현 가능한 실험

### 확장성

- 무제한 그리드 조합 지원
- max_jobs로 계산량 제어
- 메모리 효율적 (스트리밍 JSONL)

### 호환성

- D38 CLI와 완벽 호환
- 표준 JSON/YAML 형식
- 외부 도구와 통합 가능

---

## 안전 정책

### Read-Only 정책

✅ 모든 작업이 읽기 전용:
- 설정 파일 로드 (읽기만)
- 작업 계획 생성 (메모리)
- JSONL 파일 쓰기

### Observability 정책

✅ 투명한 계획:
- 모든 작업 ID 결정론적
- 모든 설정 명시적
- 재현 가능한 결과

### 네트워크 정책

✅ 네트워크 호출 없음:
- 순수 Python 계산
- 외부 API 의존성 없음
- K8s 통합 없음

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-17  
**상태:** ✅ Production Ready
