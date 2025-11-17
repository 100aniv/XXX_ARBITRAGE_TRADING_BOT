# D31 Safe Kubernetes Apply Layer Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [데이터 구조](#데이터-구조)
4. [사용 방법](#사용-방법)
5. [안전 모드](#안전-모드)
6. [제한사항](#제한사항)

---

## 개요

D31은 **생성되고 검증된 K8s Job YAML 파일을 안전하게 K8s 클러스터에 적용**하는 모듈입니다.

### 핵심 특징

- ✅ **기본 안전 모드**: Dry-run이 기본값 (실제 kubectl 실행 안 함)
- ✅ **명시적 실행**: `--apply` 플래그로만 실제 kubectl 실행
- ✅ **Apply 계획 생성**: 실행할 kubectl 명령 미리 확인
- ✅ **kubeconfig 지원**: 여러 K8s 클러스터 지원
- ✅ **상세 결과 보고**: 성공/실패 상태 추적
- ✅ **Observability 정책 준수**: 가짜 메트릭 없음
- ✅ **인프라 안전**: 기본값은 안전, 명시적 플래그 필요

### 중요: 이것은 "안전한 Apply 도구"입니다

```
D29: K8s Job YAML 생성
  ↓
D30: YAML 검증 및 실행 계획 생성
  ↓
D31: 안전한 Apply 실행 (이 단계)
  ├─ 기본값: Dry-run (실제 실행 안 함)
  └─ --apply 플래그: 실제 kubectl 실행
  ↓
K8s 클러스터에서 Job 실행
```

---

## 아키텍처

### 데이터 흐름

```
K8s Job YAML 파일들 (D29 생성, D30 검증)
    ↓
K8sApplyExecutor
    ├─ build_plan()
    │  ├─ 디렉토리 스캔
    │  ├─ 각 YAML에서 Job 정보 추출
    │  └─ kubectl 명령 생성
    │
    └─ execute_plan()
       ├─ Dry-run 모드 (기본)
       │  └─ kubectl 실행 안 함
       │
       └─ Apply 모드 (--apply)
          ├─ subprocess로 kubectl 실행
          └─ 결과 수집
    ↓
generate_apply_report_text()
    └─ 포맷된 결과 보고서 생성
    ↓
사용자 (또는 CI/CD)
    └─ 결과 확인 및 필요시 재시도
```

### 안전 메커니즘

```
1. 기본값: dry_run=True
   ├─ 실제 kubectl 실행 안 함
   └─ 상태: SKIPPED

2. 명시적 플래그: --apply
   ├─ subprocess.run() 호출
   └─ 상태: SUCCESS 또는 FAILED

3. 결과 추적
   ├─ 각 Job별 상태 기록
   ├─ stdout/stderr 수집
   └─ 상세 보고서 생성
```

---

## 데이터 구조

### K8sApplyPlanItem

```python
@dataclass
class K8sApplyPlanItem:
    job_name: str                       # Job 이름
    namespace: str                      # K8s 네임스페이스
    yaml_path: str                      # YAML 파일 경로
    kubectl_command: List[str]          # kubectl 명령
```

### K8sApplyPlan

```python
@dataclass
class K8sApplyPlan:
    jobs: List[K8sApplyPlanItem]        # Apply 계획 항목
    total_jobs: int                     # 총 Job 수
```

### K8sApplyJobResult

```python
@dataclass
class K8sApplyJobResult:
    job_name: str                       # Job 이름
    namespace: str                      # K8s 네임스페이스
    yaml_path: str                      # YAML 파일 경로
    command: List[str]                  # 실행된 kubectl 명령
    return_code: int                    # 반환 코드
    stdout: str                         # 표준 출력
    stderr: str                         # 표준 에러
    status: Literal["SKIPPED", "SUCCESS", "FAILED"]  # 상태
    timestamp: str                      # 타임스탬프
```

### K8sApplyResult

```python
@dataclass
class K8sApplyResult:
    total_jobs: int                     # 총 Job 수
    successful_jobs: int                # 성공한 Job 수
    failed_jobs: int                    # 실패한 Job 수
    skipped_jobs: int                   # 스킵된 Job 수 (dry-run)
    job_results: List[K8sApplyJobResult]  # 각 Job 결과
```

### K8sApplyExecutor

```python
class K8sApplyExecutor:
    def __init__(
        self,
        dry_run: bool = True,           # 기본값: True (안전)
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None
    ):
        pass
    
    def build_plan(self, jobs_dir: str) -> K8sApplyPlan:
        """Apply 계획 생성"""
    
    def execute_plan(self, plan: K8sApplyPlan) -> K8sApplyResult:
        """Apply 계획 실행"""
```

---

## 사용 방법

### 1. Dry-run 모드 (기본값, 안전)

```bash
python scripts/apply_k8s_jobs.py --jobs-dir outputs/d29_k8s_jobs
```

**출력:**
```
[D31_K8S_APPLY] Mode: DRY-RUN
[D31_K8S_APPLY] Found 2 YAML files
[D31_K8S_APPLY] Executing apply plan: 2 jobs, dry_run=True
[D31_K8S_APPLY] Dry-run (skipped): arb-tuning-d29-k8s--worker-1-0
[D31_K8S_APPLY] Dry-run (skipped): arb-tuning-d29-k8s--worker-2-1

[SUMMARY]
Total Jobs:              2
Successful:              0
Failed:                  0
Skipped (dry-run):       2

[SKIPPED JOBS (DRY-RUN)]
  ⊘ arb-tuning-d29-k8s--worker-1-0
  ⊘ arb-tuning-d29-k8s--worker-2-1
```

### 2. Apply 모드 (--apply 플래그 필수)

```bash
python scripts/apply_k8s_jobs.py \
  --jobs-dir outputs/d29_k8s_jobs \
  --apply
```

**출력:**
```
[D31_K8S_APPLY] Mode: APPLY
[D31_K8S_APPLY] ⚠️  APPLY MODE ENABLED - kubectl will be executed
[D31_K8S_APPLY] Found 2 YAML files
[D31_K8S_APPLY] Executing apply plan: 2 jobs, dry_run=False
[D31_K8S_APPLY] Executing kubectl: kubectl apply -f ...
[D31_K8S_APPLY] Applied successfully: arb-tuning-d29-k8s--worker-1-0
[D31_K8S_APPLY] Applied successfully: arb-tuning-d29-k8s--worker-2-1

[SUMMARY]
Total Jobs:              2
Successful:              2
Failed:                  0
Skipped (dry-run):       0

[SUCCESSFUL JOBS]
  ✓ arb-tuning-d29-k8s--worker-1-0
  ✓ arb-tuning-d29-k8s--worker-2-1
```

### 3. kubeconfig 지정

```bash
python scripts/apply_k8s_jobs.py \
  --jobs-dir outputs/d29_k8s_jobs \
  --kubeconfig ~/.kube/config \
  --context my-cluster \
  --apply
```

### 4. 결과 파일로 저장

```bash
python scripts/apply_k8s_jobs.py \
  --jobs-dir outputs/d29_k8s_jobs \
  --apply \
  --output-report outputs/d31_apply_report.txt
```

---

## 안전 모드

### 기본값: Dry-run

```python
# 기본값은 dry_run=True
executor = K8sApplyExecutor()
assert executor.dry_run is True
```

### 명시적 Apply

```bash
# --apply 플래그 없으면 dry-run
python scripts/apply_k8s_jobs.py --jobs-dir outputs/d29_k8s_jobs
# 결과: 모든 Job이 SKIPPED

# --apply 플래그로 실제 실행
python scripts/apply_k8s_jobs.py --jobs-dir outputs/d29_k8s_jobs --apply
# 결과: 실제 kubectl 실행
```

### 권장 워크플로우

```bash
# Step 1: YAML 생성 (D29)
python scripts/gen_d29_k8s_jobs.py \
  --orchestrator-config configs/d28_orchestrator/demo_baseline.yaml \
  --k8s-config configs/d29_k8s/orchestrator_k8s_baseline.yaml \
  --output-dir outputs/d29_k8s_jobs

# Step 2: YAML 검증 (D30)
python scripts/validate_k8s_jobs.py --jobs-dir outputs/d29_k8s_jobs

# Step 3: Dry-run 확인 (D31)
python scripts/apply_k8s_jobs.py --jobs-dir outputs/d29_k8s_jobs

# Step 4: 실제 적용 (D31)
python scripts/apply_k8s_jobs.py \
  --jobs-dir outputs/d29_k8s_jobs \
  --apply \
  --output-report outputs/d31_apply_report.txt
```

---

## 제한사항 및 주의

### D31에서 하지 않는 것

❌ **기본값에서 실제 kubectl 실행:**
- `--apply` 플래그 없으면 dry-run
- 실제 실행은 명시적 플래그 필수

❌ **기존 인프라 변경:**
- Docker Compose 설정 수정 금지
- Redis 컨테이너 제어 금지
- 외부 컨테이너 조작 금지

### D31에서 하는 것

✅ **Apply 계획 생성:**
- 실행할 kubectl 명령 미리 확인
- Job 정보 추출

✅ **선택적 실행:**
- Dry-run 모드 (기본)
- Apply 모드 (--apply)

✅ **결과 추적:**
- 각 Job별 상태 기록
- 성공/실패 구분
- 상세 보고서 생성

---

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 (모든 Job 성공 또는 dry-run) |
| 1 | 실패 (1개 이상의 Job 실패) |

---

## 관련 문서

- [D30 Kubernetes Executor](D30_K8S_EXECUTOR.md)
- [D29 Kubernetes Orchestrator](D29_K8S_ORCHESTRATOR.md)
- [D28 Tuning Orchestrator](D28_TUNING_ORCHESTRATOR.md)

---

## 향후 단계

### D32+ (미래 계획)

- **Pod 모니터링**: 실행 중인 Job 모니터링
- **로그 수집**: K8s 로그 수집 및 분석
- **자동 재시도**: 실패한 Job 자동 재시도
- **상태 추적**: Job 완료 상태 추적

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready
