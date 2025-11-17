# D29 Kubernetes Orchestrator Integration Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [데이터 구조](#데이터-구조)
4. [사용 방법](#사용-방법)
5. [제한사항 및 주의](#제한사항-및-주의)
6. [정책 준수](#정책-준수)

---

## 개요

D29는 **Tuning Orchestrator(D28)를 Kubernetes Job 기반으로 확장**하는 스펙과 도구를 제공합니다.

### 핵심 특징

- ✅ **K8s Job 매니페스트 생성**: YAML 파일 생성 (실제 K8s 조작 없음)
- ✅ **Job 이름 규칙**: `arb-tuning-{session_short}-{worker_id}-{index}`
- ✅ **Label/Annotation**: K8s 표준 메타데이터 포함
- ✅ **환경 변수**: 튜닝 파라미터를 K8s env로 전달
- ✅ **리소스 요청/제한**: CPU/Memory 설정 가능
- ✅ **Observability 정책 준수**: 가짜 메트릭 없음
- ✅ **인프라 안전**: 실제 K8s 조작 금지

### 중요: 이것은 "매니페스트 생성 도구"입니다

```
D29: K8s Job YAML 생성 (이 단계)
  ↓
(별도 파이프라인/사람이 kubectl apply 실행)
  ↓
K8s 클러스터에서 Job 실행
```

---

## 아키텍처

### 데이터 흐름

```
OrchestratorConfig (D28)
    ├─ session_id, total_iterations, workers
    └─ mode, env, optimizer, config_path
    ↓
K8sOrchestratorConfig (D29)
    ├─ k8s_namespace, image, resources
    └─ extra_env
    ↓
build_k8s_jobs_from_orchestrator()
    ├─ Job 분배 (D28 plan_jobs 로직)
    └─ K8sJobSpec 리스트 생성
    ↓
K8sTuningJobFactory.to_yaml_dict()
    └─ K8s Job 리소스 (batch/v1)
    ↓
gen_d29_k8s_jobs.py
    └─ YAML 파일 저장
    ↓
사용자 (또는 CI/CD)
    └─ kubectl apply -f job-*.yaml
```

### Orchestrator와의 관계

**D28 (로컬 Orchestrator):**
- subprocess로 run_d24_tuning_session.py 실행
- Job 상태를 StateManager에 저장

**D29 (K8s Orchestrator):**
- D28의 Job 계획 로직 재사용
- K8s Job 매니페스트로 변환
- 실제 실행은 K8s 클러스터에서 담당

---

## 데이터 구조

### K8sJobSpec

```python
@dataclass
class K8sJobSpec:
    name: str                           # Job 이름
    namespace: str                      # K8s 네임스페이스
    image: str                          # 컨테이너 이미지
    command: List[str]                  # 실행 명령 (예: ["python"])
    args: List[str]                     # 명령 인자
    env: Dict[str, str]                 # 환경 변수
    labels: Dict[str, str]              # K8s 레이블
    annotations: Dict[str, str]         # K8s 어노테이션
    restart_policy: str = "Never"       # 재시작 정책
    backoff_limit: int = 0              # 재시도 횟수
    resources: Optional[Dict] = None    # CPU/Memory 요청/제한
```

### K8sOrchestratorConfig

```python
@dataclass
class K8sOrchestratorConfig:
    session_id: str                     # 세션 ID
    k8s_namespace: str                  # K8s 네임스페이스
    image: str                          # 컨테이너 이미지
    mode: str                           # paper, shadow, live
    env: str                            # docker, local, stage, prod
    total_iterations: int               # 총 반복 수
    workers: int                        # 워커 수
    optimizer: str                      # grid, random, bayesian
    config_path: str                    # 튜닝 설정 파일
    extra_env: Dict[str, str]           # 추가 환경 변수
    resources: Optional[Dict]           # 리소스 요청/제한
```

### K8sTuningJobFactory

```python
class K8sTuningJobFactory:
    def create_job_for_worker(
        self,
        worker_id: str,
        iterations: int,
        index: int
    ) -> K8sJobSpec:
        """워커별 K8s Job 스펙 생성"""
    
    def to_yaml_dict(self, job: K8sJobSpec) -> Dict[str, Any]:
        """K8s Job 리소스 딕셔너리로 변환"""
```

---

## 사용 방법

### 1. 설정 파일 준비

#### Orchestrator 설정 (D28)

```yaml
# configs/d28_orchestrator/demo_baseline.yaml
session_id: "d28-demo-session"
total_iterations: 6
workers: 2
mode: "paper"
env: "docker"
optimizer: "bayesian"
config_path: "configs/d23_tuning/advanced_baseline.yaml"
base_output_csv: "outputs/d28_tuning_session"
```

#### K8s Orchestrator 설정 (D29)

```yaml
# configs/d29_k8s/orchestrator_k8s_baseline.yaml
session_id: "d29-k8s-demo-session"
k8s_namespace: "trading-bots"
image: "your-registry/arbitrage-lite:latest"
mode: "paper"
env: "docker"
total_iterations: 6
workers: 2
optimizer: "bayesian"
config_path: "configs/d23_tuning/advanced_baseline.yaml"

resources:
  requests:
    cpu: "500m"
    memory: "512Mi"
  limits:
    cpu: "1"
    memory: "1Gi"

extra_env:
  APP_ENV: "docker"
  REDIS_HOST: "arbitrage-redis"
  REDIS_PORT: "6379"
```

### 2. K8s Job YAML 생성

```bash
python scripts/gen_d29_k8s_jobs.py \
  --orchestrator-config configs/d28_orchestrator/demo_baseline.yaml \
  --k8s-config configs/d29_k8s/orchestrator_k8s_baseline.yaml \
  --output-dir outputs/d29_k8s_jobs
```

### 3. 생성된 파일 확인

```bash
ls outputs/d29_k8s_jobs/
# job-00-arb-tuning-d29-k8s--worker-1-0.yaml
# job-01-arb-tuning-d29-k8s--worker-2-1.yaml
```

### 4. (선택) K8s 클러스터에 제출

```bash
# 주의: 이 단계는 D29 범위 밖입니다
# 사용자 또는 CI/CD 파이프라인에서 수행

kubectl apply -f outputs/d29_k8s_jobs/job-*.yaml
```

---

## 생성된 K8s Job 구조

### 예시 YAML

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: arb-tuning-d29-k8s--worker-1-0
  namespace: trading-bots
  labels:
    app: arbitrage-tuning
    session_id: d29-k8s-demo-session
    worker_id: worker-1
    component: tuning
    mode: paper
    env: docker
  annotations:
    description: Arbitrage tuning job for worker-1
    created_at: "2025-11-16T18:21:45.906585"
spec:
  backoffLimit: 0
  template:
    metadata:
      labels:
        app: arbitrage-tuning
        session_id: d29-k8s-demo-session
        worker_id: worker-1
        component: tuning
        mode: paper
        env: docker
    spec:
      containers:
      - name: arb-tuning-d29-k8s--worker-1-0
        image: your-registry/arbitrage-lite:latest
        command:
        - python
        args:
        - scripts/run_d24_tuning_session.py
        - --config
        - configs/d23_tuning/advanced_baseline.yaml
        - --iterations
        - "3"
        - --mode
        - paper
        - --env
        - docker
        - --optimizer
        - bayesian
        - --session-id
        - d29-k8s-demo-session
        - --worker-id
        - worker-1
        - --output-csv
        - outputs/d29_k8s_session_worker-1.csv
        env:
        - name: APP_ENV
          value: docker
        - name: REDIS_HOST
          value: arbitrage-redis
        - name: REDIS_PORT
          value: "6379"
        - name: SESSION_ID
          value: d29-k8s-demo-session
        - name: WORKER_ID
          value: worker-1
        - name: MODE
          value: paper
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: "1"
            memory: 1Gi
      restartPolicy: Never
```

---

## 제한사항 및 주의

### D29에서 하지 않는 것

❌ **실제 K8s 조작 금지:**
- `kubectl apply` 실행 금지
- `kubectl delete` 실행 금지
- `kubectl scale` 실행 금지
- Helm 설치 금지
- Namespace 삭제 금지

❌ **기존 인프라 변경 금지:**
- Docker Compose 설정 수정 금지
- Redis 컨테이너 제어 금지
- 외부 컨테이너 조작 금지

### D29에서 하는 것

✅ **YAML 파일 생성:**
- K8s Job 매니페스트 생성
- 파일 시스템에 저장
- 콘솔에 요약 출력

✅ **구조 검증:**
- Job 이름 규칙 검증
- Label/Annotation 포함
- 환경 변수 설정

---

## 정책 준수

### Observability 정책

**금지:**
- "예상 출력", "샘플 출력", "예상 결과" 등 가짜 메트릭
- 구체적인 숫자 예시 (예: `trades_total=42`)

**허용:**
- 필드/형식 설명 (개념적)
- 실제 실행 로그 (실제 값)

### 인프라 안전 정책

**금지:**
- 실제 K8s 클러스터 조작
- 외부 컨테이너 제어
- 기존 Docker 설정 변경

**허용:**
- 매니페스트 파일 생성
- 로컬 파일 시스템 사용
- StateManager를 통한 Redis 접근 (필요시)

---

## 관련 문서

- [D28 Tuning Orchestrator](D28_TUNING_ORCHESTRATOR.md)
- [D27 Real-time Monitoring](D27_REALTIME_MONITORING.md)
- [D26 Tuning Parallel & Analysis](D26_TUNING_PARALLEL_AND_ANALYSIS.md)

---

## 향후 단계

### D30+ (미래 계획)

- **실제 K8s 통합**: 별도 모듈에서 kubectl 호출
- **CI/CD 파이프라인**: GitHub Actions / GitLab CI 통합
- **모니터링**: K8s Pod 상태 모니터링
- **로깅**: K8s 로그 수집 및 분석

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready
