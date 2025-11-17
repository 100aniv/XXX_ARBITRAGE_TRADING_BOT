# D30 Kubernetes Executor Guide (Read-Only Mode)

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [데이터 구조](#데이터-구조)
4. [사용 방법](#사용-방법)
5. [검증 규칙](#검증-규칙)
6. [제한사항](#제한사항)

---

## 개요

D30은 **생성된 K8s Job YAML 파일을 검증하고 실행 계획을 생성**하는 모듈입니다.

### 핵심 특징

- ✅ **YAML 검증**: 구조, 필드, 파라미터 검증
- ✅ **Dry-run 검증**: 실제 K8s 클러스터 상호작용 없음
- ✅ **실행 계획 생성**: 검증된 Job의 실행 계획 텍스트 생성
- ✅ **상세 분석**: Job 이름, 네임스페이스, 이미지, 리소스 등 분석
- ✅ **엄격한 모드**: 경고도 에러로 취급하는 옵션
- ✅ **Observability 정책 준수**: 가짜 메트릭 없음
- ✅ **인프라 안전**: 실제 K8s 조작 금지

### 중요: 이것은 "검증 및 분석 도구"입니다

```
D29: K8s Job YAML 생성
  ↓
D30: YAML 검증 및 실행 계획 생성 (이 단계)
  ↓
(별도 파이프라인/사람이 kubectl apply 실행)
  ↓
K8s 클러스터에서 Job 실행
```

---

## 아키텍처

### 데이터 흐름

```
K8s Job YAML 파일들 (D29 생성)
    ↓
K8sJobValidator
    ├─ YAML 파싱
    ├─ 기본 구조 검증 (apiVersion, kind, metadata, spec)
    ├─ 메타데이터 검증 (name, namespace, labels)
    ├─ Spec 검증 (template, containers)
    ├─ 컨테이너 검증 (image, command, args, env)
    └─ 리소스 검증 (requests, limits)
    ↓
K8sExecutionPlanner
    ├─ 디렉토리의 모든 YAML 파일 수집
    ├─ 각 파일 검증
    └─ 실행 계획 생성
    ↓
generate_execution_plan_text()
    └─ 포맷된 실행 계획 텍스트 생성
    ↓
사용자 (또는 CI/CD)
    └─ 검증 결과 확인 후 kubectl apply (D30 범위 밖)
```

### 검증 레벨

```
Level 1: YAML 파싱
  ├─ YAML 형식 검증
  └─ 기본 필드 존재 여부

Level 2: 구조 검증
  ├─ apiVersion, kind, metadata, spec 필드
  ├─ template, containers 필드
  └─ 필수 필드 존재 여부

Level 3: 상세 검증
  ├─ Job 이름 규칙
  ├─ 레이블/어노테이션
  ├─ 환경 변수 형식
  ├─ 리소스 요청/제한
  └─ 컨테이너 이미지 형식
```

---

## 데이터 구조

### K8sJobValidation

```python
@dataclass
class K8sJobValidation:
    valid: bool                         # 검증 성공 여부
    job_name: str                       # Job 이름
    namespace: str                      # K8s 네임스페이스
    errors: List[str]                   # 에러 메시지
    warnings: List[str]                 # 경고 메시지
    job_data: Optional[Dict]            # 파싱된 YAML 데이터
```

### K8sExecutionPlan

```python
@dataclass
class K8sExecutionPlan:
    total_jobs: int                     # 총 Job 수
    valid_jobs: int                     # 유효한 Job 수
    invalid_jobs: int                   # 무효한 Job 수
    jobs: List[Dict]                    # 유효한 Job 데이터
    errors: List[str]                   # 에러 메시지
    warnings: List[str]                 # 경고 메시지
    summary: Dict[str, Any]             # 요약 정보
```

### K8sJobValidator

```python
class K8sJobValidator:
    def __init__(self, strict_mode: bool = False):
        # strict_mode: True면 경고도 에러로 취급
    
    def validate_job_yaml(
        self,
        yaml_content: str,
        filename: str = ""
    ) -> K8sJobValidation:
        """K8s Job YAML 검증"""
```

### K8sExecutionPlanner

```python
class K8sExecutionPlanner:
    def __init__(self, validator: K8sJobValidator):
        pass
    
    def plan_from_directory(self, jobs_dir: str) -> K8sExecutionPlan:
        """디렉토리의 모든 YAML 파일 검증 및 실행 계획 생성"""
```

---

## 사용 방법

### 1. 기본 검증

```bash
python scripts/validate_k8s_jobs.py --jobs-dir outputs/d29_k8s_jobs
```

### 2. 엄격한 검증 모드

```bash
python scripts/validate_k8s_jobs.py --jobs-dir outputs/d29_k8s_jobs --strict
```

### 3. 실행 계획 파일로 저장

```bash
python scripts/validate_k8s_jobs.py \
  --jobs-dir outputs/d29_k8s_jobs \
  --output-plan outputs/d30_execution_plan.txt
```

---

## 검증 규칙

### 필수 필드 (에러)

| 필드 | 검증 내용 |
|------|---------|
| apiVersion | batch/v1이어야 함 |
| kind | Job이어야 함 |
| metadata.name | 필수 (공백 불가) |
| metadata.namespace | 권장 (없으면 default) |
| spec.template.spec.containers | 최소 1개 필수 |
| containers[].image | 필수 |
| containers[].args | 권장 |

### 권장 필드 (경고)

| 필드 | 검증 내용 |
|------|---------|
| metadata.labels | app, session_id, worker_id, component 권장 |
| containers[].resources | requests/limits 권장 |
| containers[].env | 환경 변수 설정 권장 |

### 이름 규칙 (경고)

```
Job 이름: arb-tuning-{session_short}-{worker_id}-{index}
예: arb-tuning-d29-k8s--worker-1-0
```

---

## 실행 계획 예시

```
======================================================================
[D30_K8S_EXEC] KUBERNETES EXECUTION PLAN
======================================================================

[SUMMARY]
Total Jobs:              2
Valid Jobs:              2
Invalid Jobs:            0
Namespaces:              trading-bots

[VALID JOBS]
  ✓ arb-tuning-d29-k8s--worker-1-0
  ✓ arb-tuning-d29-k8s--worker-2-1

[JOB DETAILS]

[Job 1]
  Name:                  arb-tuning-d29-k8s--worker-1-0
  Namespace:             trading-bots
  Labels:
    app: arbitrage-tuning
    session_id: d29-k8s-demo-session
    worker_id: worker-1
    component: tuning
    mode: paper
    env: docker
  Image:                 your-registry/arbitrage-lite:latest
  Command:               python
  Args:                  scripts/run_d24_tuning_session.py --config ...
  Environment Variables: (6 total)
    APP_ENV: docker
    REDIS_HOST: arbitrage-redis
    REDIS_PORT: 6379
    SESSION_ID: d29-k8s-demo-session
    WORKER_ID: worker-1
    ... and 1 more
  Resources (requests):  CPU=500m, Memory=512Mi
  Resources (limits):    CPU=1, Memory=1Gi

[Job 2]
  Name:                  arb-tuning-d29-k8s--worker-2-1
  Namespace:             trading-bots
  ...

======================================================================
[D30_K8S_EXEC] END OF EXECUTION PLAN
======================================================================
```

---

## 제한사항 및 주의

### D30에서 하지 않는 것

❌ **실제 K8s 조작 금지:**
- kubectl 명령 실행 금지
- K8s API 호출 금지
- 클러스터 상호작용 금지

❌ **기존 인프라 변경 금지:**
- Docker Compose 설정 수정 금지
- Redis 컨테이너 제어 금지
- 외부 컨테이너 조작 금지

### D30에서 하는 것

✅ **정적 분석:**
- YAML 파일 파싱
- 구조 검증
- 필드 검증
- 파라미터 검증

✅ **실행 계획 생성:**
- 검증 결과 요약
- Job 상세 정보
- 에러/경고 목록
- 텍스트 형식 출력

---

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 (모든 Job 유효) |
| 1 | 실패 (무효한 Job 또는 에러 존재) |

---

## 관련 문서

- [D29 Kubernetes Orchestrator](D29_K8S_ORCHESTRATOR.md)
- [D28 Tuning Orchestrator](D28_TUNING_ORCHESTRATOR.md)
- [D27 Real-time Monitoring](D27_REALTIME_MONITORING.md)

---

## 향후 단계

### D31+ (미래 계획)

- **실제 K8s 실행**: 별도 모듈에서 kubectl 호출
- **클러스터 상호작용**: K8s API 통합
- **Pod 모니터링**: 실행 중인 Job 모니터링
- **로그 수집**: K8s 로그 수집 및 분석

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready
