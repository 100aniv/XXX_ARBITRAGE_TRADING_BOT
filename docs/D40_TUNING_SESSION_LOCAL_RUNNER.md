# D40 Tuning Session Local Runner Guide

**Document Version:** 1.0  
**Date:** 2025-11-17  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [핵심 개념](#핵심-개념)
3. [세션 실행](#세션-실행)
4. [사용 예시](#사용-예시)
5. [워크플로우](#워크플로우)

---

## 개요

D40 Tuning Session Local Runner는 **로컬 환경에서 D39 작업 계획을 순차적으로 실행**하는 도구입니다.

### 특징

- ✅ D39 JSONL 작업 계획 읽기
- ✅ D38 튜닝 작업 순차 실행
- ✅ 결과 JSON 파일 자동 생성
- ✅ 세션 수준 요약 및 통계
- ✅ 오프라인 전용 (외부 API 호출 없음)

### 목적

- 로컬 배치 실행 (K8s 없음)
- 대규모 매개변수 탐색 자동화
- 세션 수준 실행 추적

### 아키텍처 위치

```
D39 Session Planner
    ↓
Generate Job Plans (JSONL)
    ↓
D40 Local Session Runner ← 여기
    ├─ 각 작업에 대해 D38 실행
    └─ 결과 JSON 생성
    ↓
D39 Results Aggregator
    ↓
Ranked Summary & Insights
```

---

## 핵심 개념

### TuningSessionRunResult

```python
@dataclass
class TuningSessionRunResult:
    total_jobs: int              # 총 작업 수
    attempted_jobs: int          # 시도한 작업 수
    success_jobs: int            # 성공한 작업 수
    error_jobs: int              # 오류 작업 수
    skipped_jobs: int            # 건너뛴 작업 수
    exit_code: int               # 종료 코드
    errors: List[str]            # 오류 메시지 목록
```

### TuningSessionRunner

```python
class TuningSessionRunner:
    def __init__(
        self,
        jobs_file: str,
        python_executable: str = "python",
        max_jobs: Optional[int] = None,
        stop_on_error: bool = False,
    ):
        """로컬 튜닝 세션 실행기 초기화"""

    def load_jobs(self) -> List[Dict[str, Any]]:
        """JSONL 파일에서 작업 계획 로드"""

    def run(self) -> TuningSessionRunResult:
        """세션 실행 및 결과 반환"""
```

---

## 세션 실행

### 기본 사용

```bash
# 모든 작업 실행
python -m scripts.run_tuning_session_local \
  --jobs-file outputs/tuning/session001_jobs.jsonl
```

### 고급 옵션

```bash
# 최대 10개 작업만 실행
python -m scripts.run_tuning_session_local \
  --jobs-file outputs/tuning/session001_jobs.jsonl \
  --max-jobs 10

# 첫 오류에서 중단
python -m scripts.run_tuning_session_local \
  --jobs-file outputs/tuning/session001_jobs.jsonl \
  --stop-on-error

# 커스텀 Python 실행 파일
python -m scripts.run_tuning_session_local \
  --jobs-file outputs/tuning/session001_jobs.jsonl \
  --python-executable python3
```

### 출력 형식

```
======================================================================
[D40_SESSION] LOCAL TUNING SESSION SUMMARY
======================================================================

Total Jobs:     50
Attempted:      50
Success:        47
Errors:         3
Skipped:        0

Exit Code:      1  (⚠️  SOME JOBS FAILED)

Errors:
  - Job sess001_0005 failed with exit code 1
  - Job sess001_0012 failed with exit code 1
  - Job sess001_0023 failed with exit code 1

======================================================================
```

### 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 모든 작업 성공 |
| 1 | 일부 작업 실패 |
| 2 | 파일 오류 또는 런타임 오류 |

---

## 사용 예시

### 예시 1: 기본 세션 실행

**세션 계획 생성 (D39):**
```bash
python -m scripts.plan_tuning_session \
  --session-file configs/tuning/session001.yaml \
  --output-jobs-file outputs/tuning/session001_jobs.jsonl
```

**세션 실행 (D40):**
```bash
python -m scripts.run_tuning_session_local \
  --jobs-file outputs/tuning/session001_jobs.jsonl
```

**결과 집계 (D39):**
```bash
python -m scripts.aggregate_tuning_results \
  --results-dir outputs/tuning/sess001 \
  --max-results 10
```

### 예시 2: 제한된 실행

```bash
# 처음 20개 작업만 실행
python -m scripts.run_tuning_session_local \
  --jobs-file outputs/tuning/session001_jobs.jsonl \
  --max-jobs 20
```

### 예시 3: 안전한 실행 (오류 시 중단)

```bash
# 첫 오류에서 중단
python -m scripts.run_tuning_session_local \
  --jobs-file outputs/tuning/session001_jobs.jsonl \
  --stop-on-error
```

### 예시 4: Python API 사용

```python
from arbitrage.tuning_session_runner import TuningSessionRunner

# 실행기 생성
runner = TuningSessionRunner(
    jobs_file="outputs/tuning/session001_jobs.jsonl",
    max_jobs=10,
    stop_on_error=False,
)

# 세션 실행
result = runner.run()

# 결과 확인
print(f"Total Jobs: {result.total_jobs}")
print(f"Success: {result.success_jobs}")
print(f"Errors: {result.error_jobs}")
print(f"Exit Code: {result.exit_code}")

# 오류 확인
if result.errors:
    for error in result.errors:
        print(f"  - {error}")
```

---

## 워크플로우

### 전체 파이프라인

```
1. 세션 설정 파일 작성 (YAML/JSON)
   ↓
2. plan_tuning_session 실행 (D39)
   ├─ JSONL 작업 계획 생성
   └─ 각 작업: job_id, config, output_json
   ↓
3. run_tuning_session_local 실행 (D40)
   ├─ JSONL 파일 로드
   ├─ 각 작업에 대해:
   │  ├─ D38 CLI 실행
   │  ├─ 결과 JSON 생성
   │  └─ 성공/오류 기록
   └─ 세션 요약 출력
   ↓
4. aggregate_tuning_results 실행 (D39)
   ├─ 모든 결과 JSON 로드
   ├─ 필터링 및 순위
   └─ 최고 성능 설정 식별
```

### 자동화 예시 (Bash)

```bash
#!/bin/bash

SESSION_NAME="session001"
SESSION_FILE="configs/tuning/${SESSION_NAME}.yaml"
JOBS_FILE="outputs/tuning/${SESSION_NAME}_jobs.jsonl"
RESULTS_DIR="outputs/tuning/sess001"

# 1. 작업 계획 생성
echo "Generating job plans..."
python -m scripts.plan_tuning_session \
  --session-file "$SESSION_FILE" \
  --output-jobs-file "$JOBS_FILE"

if [ $? -ne 0 ]; then
    echo "Failed to generate job plans"
    exit 1
fi

# 2. 세션 실행
echo "Running tuning session..."
python -m scripts.run_tuning_session_local \
  --jobs-file "$JOBS_FILE" \
  --max-jobs 50

if [ $? -ne 0 ]; then
    echo "Some jobs failed"
fi

# 3. 결과 집계
echo "Aggregating results..."
python -m scripts.aggregate_tuning_results \
  --results-dir "$RESULTS_DIR" \
  --max-results 10 \
  --max-drawdown-pct 15 \
  --output-json "outputs/tuning/${SESSION_NAME}_summary.json"

echo "Done!"
```

---

## 주요 특징

### 순차 실행

- 작업을 순서대로 실행
- 각 작업 완료 후 다음 작업 시작
- 병렬 실행 없음 (로컬 단일 스레드)

### 오류 처리

- 유효하지 않은 작업 자동 감지
- 작업 실패 시 계속 진행 (기본값)
- `--stop-on-error` 플래그로 중단 가능

### 디렉토리 관리

- 출력 디렉토리 자동 생성
- 중첩된 디렉토리 지원
- 기존 파일 덮어쓰기

### 타임아웃

- 각 작업 최대 5분 (300초)
- 타임아웃 시 오류로 처리
- 다음 작업 계속 진행

---

## 제한사항

### 로컬 전용

- K8s 통합 없음
- 네트워크 호출 없음
- 단일 머신에서만 실행

### 순차 실행

- 병렬 처리 없음
- 대규모 세션은 시간 소요
- 병렬 실행은 D29-D36 K8s 파이프라인 사용

### 리소스

- 메모리: 작음 (JSONL 스트리밍)
- CPU: 단일 코어 (순차 실행)
- 디스크: 결과 JSON 파일 저장 필요

---

## 안전 정책

### Read-Only 정책

✅ 허용:
- JSONL 파일 읽기
- D38 CLI 호출
- 결과 JSON 쓰기

❌ 금지:
- 기존 파일 수정
- 실제 거래 실행
- 데이터 변경

### Observability 정책

✅ 준수:
- 모든 작업 추적
- 성공/오류 기록
- 세션 수준 요약

### 네트워크 정책

✅ 준수:
- 네트워크 호출 없음
- 순수 로컬 실행
- K8s API 호출 없음

---

## 다음 단계

### D40 이후

1. **D41**: K8s 통합 (D29-D36과 완전 통합)
2. **D42**: 실시간 모니터링 및 대시보드
3. **D43**: 자동화된 매개변수 탐색
4. **D44**: 결과 분석 및 리포팅

### 관련 모듈

- **D37**: Arbitrage Strategy MVP (Core Engine)
- **D38**: Arbitrage Tuning Job Runner (Single Job)
- **D39**: Arbitrage Tuning Session Planner & Aggregator
- **D40**: Arbitrage Tuning Session Local Runner (이 모듈)

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-17  
**상태:** ✅ Production Ready
