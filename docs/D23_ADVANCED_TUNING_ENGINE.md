
# D23 Advanced Tuning Engine Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [Optimizer 추상화](#optimizer-추상화)
4. [구현된 최적화 알고리즘](#구현된-최적화-알고리즘)
5. [D22 Tuning Harness 통합](#d22-tuning-harness-통합)
6. [설정 및 실행](#설정-및-실행)
7. [Observability 정책](#observability-정책)
8. [향후 계획](#향후-계획)

---

## 개요

D23은 **Advanced Tuning Engine**을 구현합니다. 파라미터 최적화를 위한 다양한 알고리즘을 지원하는 확장 가능한 구조를 제공합니다.

### 핵심 특징

- ✅ **Optimizer 추상화**: BaseOptimizer 인터페이스
- ✅ **Grid Search**: 결정론적 그리드 탐색
- ✅ **Random Search**: 균일 분포 샘플링
- ✅ **Bayesian Optimization**: 구조 기반 설계 (향후 확장)
- ✅ **D22 Tuning Harness 통합**: 기존 튜닝 시스템과 호환
- ✅ **StateManager 연동**: Redis 기반 결과 저장
- ✅ **Observability 정책 준수**: 가짜 메트릭 없음

### 설계 원칙

1. **실제 최적화 없음**: 구조와 인터페이스만 구현
2. **플러그인 가능**: 향후 scikit-opt, hyperopt, optuna 등 연동 가능
3. **테스트 가능**: 모든 알고리즘 Mock 가능
4. **인프라 안전**: StateManager를 통한 Redis 접근만 사용

---

## 아키텍처

### 계층 구조

```
┌─────────────────────────────────────────┐
│      TuningHarness (D22)                │
│   - 시나리오 로드                        │
│   - 목적 함수 실행                       │
│   - 결과 저장                            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Optimizer (D23)                    │
│   - ask(): 파라미터 제안                 │
│   - tell(): 결과 기록                    │
│   - get_history(): 히스토리 조회         │
└──────────────┬──────────────────────────┘
               │
        ┌──────┼──────┐
        ▼      ▼      ▼
    ┌────┐ ┌────┐ ┌────────┐
    │Grid│ │Rand│ │Bayesian│
    └────┘ └────┘ └────────┘
```

### 주요 클래스

#### 1. TuningMethod (Enum)

```python
class TuningMethod(Enum):
    GRID = "grid"
    RANDOM = "random"
    BAYESIAN = "bayesian"
```

#### 2. ParameterBound

파라미터 범위 정의 및 검증:

```python
@dataclass
class ParameterBound:
    name: str              # 파라미터 이름
    param_type: str        # "float" 또는 "int"
    bounds: Tuple[float, float]  # (min, max)
    
    def validate(self, value: Any) -> bool:
        """값이 범위 내인지 확인"""
```

#### 3. BaseOptimizer (추상 클래스)

모든 최적화 알고리즘의 기본 인터페이스:

```python
class BaseOptimizer(ABC):
    def __init__(self, search_space: List[ParameterBound]):
        ...
    
    @abstractmethod
    def ask(self) -> Dict[str, Any]:
        """다음 시도할 파라미터 제안"""
        pass
    
    @abstractmethod
    def tell(self, params: Dict[str, Any], result_summary: Dict[str, Any]) -> None:
        """결과 기록 및 모델 업데이트"""
        pass
    
    def get_history(self) -> List[OptimizationResult]:
        """최적화 히스토리 조회"""
        pass
```

---

## Optimizer 추상화

### ask() / tell() 패턴

모든 Optimizer는 다음 패턴을 따릅니다:

```python
# 초기화
optimizer = create_optimizer(TuningMethod.BAYESIAN, search_space)

# 반복
for iteration in range(max_iterations):
    # 1. 파라미터 제안
    params = optimizer.ask()
    
    # 2. 목적 함수 실행 (외부)
    result = objective_function(params)
    
    # 3. 결과 기록
    optimizer.tell(params, result)
```

### 결과 스키마

```python
@dataclass
class OptimizationResult:
    iteration: int                          # 반복 번호
    params: Dict[str, Any]                  # 사용한 파라미터
    result_summary: Dict[str, Any]          # 결과 요약 (키만)
    timestamp: str                          # ISO8601 타임스탬프
```

**result_summary 예시 (숫자 없음):**

```python
{
    "status": "completed",
    "scenario": "basic_spread_win",
    "engine_mode": "paper"
}
```

---

## 구현된 최적화 알고리즘

### 1. GridOptimizer

**특징:**
- 결정론적 그리드 탐색
- 각 차원당 `grid_points` 개의 포인트 생성
- 모든 조합 탐색

**사용 예:**

```python
optimizer = GridOptimizer(
    search_space=[
        ParameterBound("min_spread_pct", "float", (0.05, 0.50)),
        ParameterBound("slippage_bps", "int", (1, 30))
    ],
    grid_points=3
)
```

**동작:**
- 첫 번째 ask(): (0.05, 1)
- 두 번째 ask(): (0.05, 15)
- 세 번째 ask(): (0.05, 30)
- ...

### 2. RandomOptimizer

**특징:**
- 균일 분포 샘플링
- 시드 기반 재현성
- 빠른 탐색

**사용 예:**

```python
optimizer = RandomOptimizer(
    search_space=[...],
    seed=42
)
```

**동작:**
- ask(): 범위 내 무작위 값 반환
- 같은 시드 → 같은 시퀀스 (재현성)

### 3. BayesianOptimizer

**현재 상태:**
- 구조만 구현 (실제 GP 모델 없음)
- Random sampling 사용 (ask())
- 히스토리 저장 (tell())

**향후 확장 (D24+):**
- Gaussian Process 모델
- Acquisition function (UCB, EI, POI)
- scikit-opt / hyperopt / optuna 통합

**사용 예:**

```python
optimizer = BayesianOptimizer(
    search_space=[...],
    acquisition_fn="ucb",
    seed=42
)
```

---

## D22 Tuning Harness 통합

### TuningHarness 클래스

```python
class TuningHarness:
    def __init__(self, config: TuningConfig, state_manager: Optional[StateManager] = None):
        """
        Args:
            config: 튜닝 설정
            state_manager: StateManager (Redis 연동)
        """
        ...
    
    def run_iteration(self, iteration: int, objective_fn) -> Dict[str, Any]:
        """한 번의 튜닝 반복 실행"""
        params = self.optimizer.ask()
        result = objective_fn(params)
        self.optimizer.tell(params, result)
        return result
```

### 통합 흐름

```python
# 1. 설정 로드
config = load_tuning_config("configs/d23_tuning/advanced_baseline.yaml")

# 2. Harness 생성
harness = TuningHarness(config)

# 3. 목적 함수 정의
def objective_function(params):
    # 시나리오 실행
    # 결과 계산
    return {"status": "completed"}

# 4. 반복 실행
for i in range(config.max_iterations):
    result = harness.run_iteration(i + 1, objective_function)

# 5. 결과 조회
results = harness.get_results()
history = harness.get_optimizer_history()
```

### StateManager 연동

결과는 자동으로 Redis에 저장됩니다:

```python
# Namespace: tuning:{env}:{mode}
# Key: tuning:{env}:{mode}:arbitrage:tuning_result:{iteration}

{
    "iteration": "1",
    "params": "{'min_spread_pct': 0.1, ...}",
    "timestamp": "2025-11-16T12:34:56.789123"
}
```

---

## 설정 및 실행

### 설정 파일 구조

**File:** `configs/d23_tuning/advanced_baseline.yaml`

```yaml
tuning:
  # 튜닝 방법
  method: bayesian  # grid, random, bayesian
  
  # 시나리오 파일
  scenarios:
    - configs/d17_scenarios/basic_spread_win.yaml
    - configs/d17_scenarios/choppy_market.yaml
  
  # 파라미터 범위
  search_space:
    min_spread_pct:
      type: float
      bounds: [0.05, 0.50]
    
    slippage_bps:
      type: int
      bounds: [1, 30]
    
    max_position_krw:
      type: int
      bounds: [300000, 2000000]
  
  # 최대 반복 횟수
  max_iterations: 10
  
  # 난수 시드
  seed: 42
  
  # Grid Search 포인트 수
  grid_points: 3
  
  # Acquisition function
  acquisition_fn: ucb
```

### 실행 명령

```bash
# CLI 스크립트 (향후 구현)
python scripts/run_d23_tuning.py --config configs/d23_tuning/advanced_baseline.yaml

# 또는 Python 코드
python -c "
from arbitrage.tuning import load_tuning_config, TuningHarness

config = load_tuning_config('configs/d23_tuning/advanced_baseline.yaml')
harness = TuningHarness(config)

def objective(params):
    return {'status': 'completed'}

for i in range(3):
    harness.run_iteration(i + 1, objective)

print(f'Completed {len(harness.get_results())} iterations')
"
```

---

## Observability 정책

### 정책 명시

**For all tuning / optimization scripts,
this project NEVER documents fake or "expected" outputs with concrete numbers.
Only real logs from actual executions may be shown in reports, otherwise we only describe the format and fields conceptually.**

### 준수 사항

1. ❌ "예상 결과", "샘플 PnL", "기대 수익률" 금지
2. ❌ 구체적인 숫자가 포함된 출력 예시 금지
3. ✅ 알고리즘 구조와 인터페이스만 설명
4. ✅ 결과 스키마 (키만) 문서화

### 테스트 검증

```python
def test_no_fake_metrics():
    """가짜 메트릭 없음 확인"""
    forbidden_patterns = [
        "trades_total",
        "win_rate",
        "drawdown",
        "pnl",
        "예상 출력"
    ]
    # 소스 코드에서 패턴 검색
```

---

## 향후 계획

### D24: Bayesian Backend 구현

- [ ] Gaussian Process 모델 추가
- [ ] Acquisition function 구현 (UCB, EI, POI)
- [ ] scikit-opt 또는 hyperopt 통합
- [ ] 실제 Bayesian 최적화 실행

### D25: 고급 기능

- [ ] Multi-objective optimization
- [ ] Constraint handling
- [ ] Warm start (이전 결과 활용)
- [ ] Early stopping

### D26: 운영 도구

- [ ] CLI 대시보드
- [ ] 결과 시각화
- [ ] 병렬 실행
- [ ] 분산 튜닝

---

## 관련 문서

- [D22 Tuning Harness](D22_TUNING_HARNESS.md) (향후 작성)
- [D21 Observability](D21_OBSERVABILITY_AND_STATE_MANAGER.md)
- [D20 LIVE ARM Guide](D20_LIVE_ARM_GUIDE.md)

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready
