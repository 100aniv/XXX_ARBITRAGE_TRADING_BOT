# D38 Arbitrage Tuning Job Runner Guide

**Document Version:** 1.0  
**Date:** 2025-11-16  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [핵심 개념](#핵심-개념)
4. [사용 방법](#사용-방법)
5. [K8s 통합](#k8s-통합)

---

## 개요

D38은 **단일 차익거래 튜닝 작업 실행기**를 구현합니다.

### 특징

- ✅ 하나의 설정 + 하나의 데이터셋으로 백테스트 실행
- ✅ 안정적인 메트릭 JSON 생성
- ✅ K8s Job 친화적 (간단한 CLI, 결정론적 종료 코드)
- ✅ 오프라인 전용 (외부 API 호출 없음)
- ✅ 완전히 테스트 가능

### 목적

- D37 (백테스트 엔진)과 D29-D36 (K8s 튜닝 파이프라인) 연결
- 각 K8s Job이 다양한 파라미터로 튜닝 작업 실행
- 메트릭 JSON으로 결과 저장 및 집계

### 아키텍처 위치

```
D29-D36 (K8s Tuning Pipeline)
    ↓
D38 (Tuning Job Runner)
    ↓
D37 (Arbitrage Engine + Backtest)
```

---

## 아키텍처

### 모듈 구조

```
arbitrage/
├── arbitrage_core.py      # D37: 핵심 엔진
├── arbitrage_backtest.py  # D37: 백테스트 프레임워크
└── arbitrage_tuning.py    # D38: 튜닝 작업 실행기

scripts/
└── run_arbitrage_tuning.py  # D38: CLI 도구
```

### 데이터 흐름

```
TuningConfig (설정)
    ↓
ArbitrageTuningRunner.run()
    ├─ load_snapshots() → CSV 로드
    ├─ ArbitrageEngine 생성
    ├─ ArbitrageBacktester 실행
    └─ BacktestResult → TuningMetrics 변환
    ↓
TuningMetrics (결과)
    ↓
JSON 출력 (파일 또는 stdout)
```

---

## 핵심 개념

### TuningConfig

```python
@dataclass
class TuningConfig:
    # 데이터 입력
    data_file: str

    # 전략 파라미터 (ArbitrageConfig 미러)
    min_spread_bps: float
    taker_fee_a_bps: float
    taker_fee_b_bps: float
    slippage_bps: float
    max_position_usd: float
    max_open_trades: int = 1

    # 백테스트 파라미터 (BacktestConfig 미러)
    initial_balance_usd: float = 10_000.0
    stop_on_drawdown_pct: Optional[float] = None

    # 선택적 메타데이터
    tag: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
```

### TuningMetrics

```python
@dataclass
class TuningMetrics:
    # 핵심 메트릭
    total_trades: int
    closed_trades: int
    open_trades: int
    final_balance_usd: float
    realized_pnl_usd: float
    max_drawdown_pct: float
    win_rate: float
    avg_pnl_per_trade_usd: float

    # 선택적 확장
    runtime_seconds: Optional[float] = None
    config_summary: Optional[Dict[str, Any]] = None
```

### ArbitrageTuningRunner

```python
class ArbitrageTuningRunner:
    def __init__(self, tuning_config: TuningConfig):
        """튜닝 실행기 초기화"""

    def load_snapshots(self) -> List[OrderBookSnapshot]:
        """CSV 파일에서 스냅샷 로드"""

    def run(self) -> TuningMetrics:
        """튜닝 작업 실행"""
```

---

## 사용 방법

### 1. Python API 사용

```python
from arbitrage.arbitrage_tuning import TuningConfig, ArbitrageTuningRunner

# 설정 생성
config = TuningConfig(
    data_file="data/sample_arbitrage_prices.csv",
    min_spread_bps=30.0,
    taker_fee_a_bps=5.0,
    taker_fee_b_bps=5.0,
    slippage_bps=5.0,
    max_position_usd=1000.0,
    initial_balance_usd=10_000.0,
    tag="experiment_001",
)

# 튜닝 작업 실행
runner = ArbitrageTuningRunner(config)
metrics = runner.run()

# 결과 확인
print(f"Total Trades: {metrics.total_trades}")
print(f"Final Balance: ${metrics.final_balance_usd:,.2f}")
print(f"Realized PnL: ${metrics.realized_pnl_usd:,.2f}")
print(f"Win Rate: {metrics.win_rate*100:.2f}%")
print(f"Runtime: {metrics.runtime_seconds:.3f}s")
```

### 2. CLI 사용

```bash
# 기본 튜닝 작업
python -m scripts.run_arbitrage_tuning \
  --data-file data/sample_arbitrage_prices.csv \
  --min-spread-bps 30 \
  --taker-fee-a-bps 5 \
  --taker-fee-b-bps 5 \
  --slippage-bps 5 \
  --max-position-usd 1000 \
  --output-json outputs/tuning_result.json

# 선택적 파라미터 포함
python -m scripts.run_arbitrage_tuning \
  --data-file data/sample_arbitrage_prices.csv \
  --min-spread-bps 40 \
  --taker-fee-a-bps 7 \
  --taker-fee-b-bps 7 \
  --slippage-bps 5 \
  --max-position-usd 1500 \
  --max-open-trades 2 \
  --initial-balance-usd 20000 \
  --stop-on-drawdown-pct 25 \
  --tag "experiment_001" \
  --output-json outputs/tuning_result_001.json

# stdout으로 JSON 출력
python -m scripts.run_arbitrage_tuning \
  --data-file data/sample_arbitrage_prices.csv \
  --min-spread-bps 30 \
  --taker-fee-a-bps 5 \
  --taker-fee-b-bps 5 \
  --slippage-bps 5 \
  --max-position-usd 1000
```

### 3. CLI 인자

**필수:**
- `--data-file` (str): CSV 파일 경로
- `--min-spread-bps` (float): 최소 스프레드 (bps)
- `--taker-fee-a-bps` (float): Exchange A 수수료 (bps)
- `--taker-fee-b-bps` (float): Exchange B 수수료 (bps)
- `--slippage-bps` (float): 슬리피지 (bps)
- `--max-position-usd` (float): 최대 포지션 (USD)

**선택적:**
- `--max-open-trades` (int, 기본값: 1): 최대 동시 거래 수
- `--initial-balance-usd` (float, 기본값: 10000): 초기 잔액 (USD)
- `--stop-on-drawdown-pct` (float): 낙폭 한계 (%)
- `--tag` (str): 실험 태그
- `--output-json` (str): 출력 JSON 파일 경로 (생략 시 stdout)

### 4. 종료 코드

```
0: 성공
1: 설정 또는 데이터 오류 (파일 없음, 잘못된 인자)
2: 예상치 못한 런타임 오류
```

---

## JSON 출력 형식

### 구조

```json
{
  "status": "success",
  "config": {
    "data_file": "data/sample_arbitrage_prices.csv",
    "min_spread_bps": 30.0,
    "taker_fee_a_bps": 5.0,
    "taker_fee_b_bps": 5.0,
    "slippage_bps": 5.0,
    "max_position_usd": 1000.0,
    "max_open_trades": 1,
    "initial_balance_usd": 10000.0,
    "stop_on_drawdown_pct": null,
    "tag": "experiment_001"
  },
  "metrics": {
    "total_trades": 10,
    "closed_trades": 8,
    "open_trades": 2,
    "final_balance_usd": 11000.0,
    "realized_pnl_usd": 1000.0,
    "max_drawdown_pct": 5.0,
    "win_rate": 0.75,
    "avg_pnl_per_trade_usd": 125.0,
    "runtime_seconds": 0.123
  },
  "config_summary": {
    "data_file": "data/sample_arbitrage_prices.csv",
    "min_spread_bps": 30.0,
    "max_position_usd": 1000.0,
    "tag": "experiment_001",
    "snapshots_count": 100
  }
}
```

---

## K8s 통합

### D29-D36과의 연결

D38은 D29-D36 K8s 튜닝 파이프라인에서 **개별 Job**으로 실행됩니다.

```yaml
# K8s Job 예시 (D29-D36에서 생성)
apiVersion: batch/v1
kind: Job
metadata:
  name: arbitrage-tuning-job-001
spec:
  template:
    spec:
      containers:
      - name: tuning-runner
        image: arbitrage:latest
        command:
        - python
        - -m
        - scripts.run_arbitrage_tuning
        args:
        - --data-file
        - /data/sample_arbitrage_prices.csv
        - --min-spread-bps
        - "30"
        - --taker-fee-a-bps
        - "5"
        - --taker-fee-b-bps
        - "5"
        - --slippage-bps
        - "5"
        - --max-position-usd
        - "1000"
        - --output-json
        - /output/tuning_result.json
```

### 메트릭 집계

D29-D36은 여러 Job의 JSON 결과를 수집하여:
- 최고 성능 설정 식별
- 메트릭 추세 분석
- 알림 발송

---

## 안전 정책

### Read-Only 정책

✅ 모든 작업이 읽기 전용:
- CSV 파일 로드 (읽기만)
- 백테스트 시뮬레이션
- 메트릭 계산

### Observability 정책

✅ 가짜 메트릭 없음:
- 모든 계산이 입력 데이터 기반
- 실제 백테스트 결과만 보고

### 네트워크 정책

✅ 네트워크 호출 없음:
- 순수 Python 계산
- 외부 API 의존성 없음
- K8s API 호출 없음

---

## 설정 예시

### 보수적 설정

```python
config = TuningConfig(
    data_file="data/sample.csv",
    min_spread_bps=50.0,           # 높은 임계값
    taker_fee_a_bps=5.0,
    taker_fee_b_bps=5.0,
    slippage_bps=10.0,             # 높은 슬리피지
    max_position_usd=500.0,        # 작은 포지션
    tag="conservative",
)
```

### 공격적 설정

```python
config = TuningConfig(
    data_file="data/sample.csv",
    min_spread_bps=20.0,           # 낮은 임계값
    taker_fee_a_bps=3.0,
    taker_fee_b_bps=3.0,
    slippage_bps=2.0,              # 낮은 슬리피지
    max_position_usd=5000.0,       # 큰 포지션
    tag="aggressive",
)
```

---

## 다음 단계 (D39+)

- D29-D36과 완전 통합
- 대규모 파라미터 그리드 서치
- 메트릭 집계 및 분석
- 최적 설정 자동 선택

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-16  
**상태:** ✅ Production Ready
