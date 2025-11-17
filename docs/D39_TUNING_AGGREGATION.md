# D39 Tuning Results Aggregation Guide

**Document Version:** 1.0  
**Date:** 2025-11-17  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [핵심 개념](#핵심-개념)
3. [결과 로드](#결과-로드)
4. [필터링 및 순위](#필터링-및-순위)
5. [사용 예시](#사용-예시)

---

## 개요

D39 Tuning Results Aggregator는 **여러 D38 결과 JSON 파일을 집계**하는 도구입니다.

### 특징

- ✅ 디렉토리에서 모든 D38 결과 로드
- ✅ 필터링 (최대 낙폭, 최소 거래 수)
- ✅ 성능 기준으로 순위 지정 (PnL)
- ✅ 인간 친화적 및 기계 친화적 출력
- ✅ 오프라인 전용 (외부 API 호출 없음)

### 목적

- 대규모 튜닝 실험의 결과 분석
- 최고 성능 설정 식별
- 메트릭 추세 분석
- 최적화 방향 결정

### 아키텍처 위치

```
D39 Session Planner
    ↓
Generate Job Plans (JSONL)
    ↓
D38 Tuning Job Runner (many jobs)
    ↓
D39 Results Aggregator
    ↓
Ranked Summary & Insights
```

---

## 핵심 개념

### AggregatedJobResult

```python
@dataclass
class AggregatedJobResult:
    job_id: str                      # 작업 ID (e.g., "sess001_0001")
    tag: Optional[str]               # 작업 태그
    config: Dict[str, Any]           # 설정 (TuningConfig 필드)
    metrics: Dict[str, Any]          # 메트릭 (TuningMetrics 필드)
    status: Literal["success", "error"]  # 성공 또는 오류
```

### AggregatedSummary

```python
@dataclass
class AggregatedSummary:
    total_jobs: int                  # 총 작업 수
    success_jobs: int                # 성공한 작업 수
    error_jobs: int                  # 오류 작업 수
    top_by_pnl: List[AggregatedJobResult]  # PnL 기준 상위 결과
    filters: Dict[str, Any]          # 적용된 필터
```

### TuningResultsAggregator

```python
class TuningResultsAggregator:
    def __init__(
        self,
        results_dir: str,
        max_results: int = 100,
        max_drawdown_pct: Optional[float] = None,
        min_trades: Optional[int] = None,
    ):
        """집계기 초기화"""

    def load_results(self) -> List[AggregatedJobResult]:
        """
        results_dir에서 모든 *.json 파일 스캔
        D38 출력을 AggregatedJobResult로 변환
        파싱 실패 시 status="error"로 표시
        """

    def summarize(self) -> AggregatedSummary:
        """
        - max_drawdown_pct로 필터링 (설정된 경우)
        - min_trades로 필터링 (설정된 경우)
        - realized_pnl_usd로 순위 지정 (내림차순)
        - 상위 max_results 선택
        - 필터 기준 포함하여 AggregatedSummary 반환
        """
```

---

## 결과 로드

### 디렉토리 구조

```
outputs/tuning/sess001/
├── sess001_0001.json
├── sess001_0002.json
├── sess001_0003.json
├── sess001_0004.json (오류 파일)
└── sess001_0005.json
```

### D38 결과 JSON 형식

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
    "tag": "sess001"
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
    "job_id": "sess001_0001"
  }
}
```

### Python API 사용

```python
from arbitrage.tuning_aggregate import TuningResultsAggregator

# 집계기 초기화
aggregator = TuningResultsAggregator(
    results_dir="outputs/tuning/sess001",
)

# 모든 결과 로드
results = aggregator.load_results()

# 결과 확인
for result in results:
    print(f"Job: {result.job_id}")
    print(f"Status: {result.status}")
    print(f"PnL: ${result.metrics.get('realized_pnl_usd', 0):,.2f}")
    print()
```

---

## 필터링 및 순위

### 필터 옵션

#### max_drawdown_pct

최대 낙폭(%) 제한:
```python
aggregator = TuningResultsAggregator(
    results_dir="outputs/tuning/sess001",
    max_drawdown_pct=15.0,  # 낙폭 15% 이하만
)
```

#### min_trades

최소 거래 수 제한:
```python
aggregator = TuningResultsAggregator(
    results_dir="outputs/tuning/sess001",
    min_trades=5,  # 5개 이상 거래만
)
```

#### max_results

상위 결과 수 제한:
```python
aggregator = TuningResultsAggregator(
    results_dir="outputs/tuning/sess001",
    max_results=10,  # 상위 10개만
)
```

### 순위 지정

결과는 **realized_pnl_usd 기준 내림차순**으로 순위 지정됩니다:

```
1. Job A: PnL = +1,250.00
2. Job B: PnL = +1,050.00
3. Job C: PnL = +950.00
4. Job D: PnL = +800.00
5. Job E: PnL = +750.00
```

---

## 사용 예시

### 예시 1: 기본 집계

```bash
python -m scripts.aggregate_tuning_results \
  --results-dir outputs/tuning/sess001
```

**출력:**
```
======================================================================
[D39_AGG] TUNING SESSION SUMMARY
======================================================================

Total Jobs:           50
Success Jobs:         47
Error Jobs:           3

Top 10 by Realized PnL (USD):
  1) job_id=sess001_0007  PnL=+1,250.00  DD=10.00%  trades=18  min_spread_bps=30  slippage_bps=3
  2) job_id=sess001_0012  PnL=+1,050.00  DD=12.00%  trades=20  min_spread_bps=25  slippage_bps=5
  3) job_id=sess001_0003  PnL=+950.00   DD=8.00%   trades=15  min_spread_bps=35  slippage_bps=3
  ...

======================================================================
```

### 예시 2: 필터링 적용

```bash
python -m scripts.aggregate_tuning_results \
  --results-dir outputs/tuning/sess001 \
  --max-drawdown-pct 15 \
  --min-trades 5 \
  --max-results 10
```

**필터:**
- 낙폭 15% 이하
- 최소 5개 거래
- 상위 10개만 표시

### 예시 3: JSON 출력

```bash
python -m scripts.aggregate_tuning_results \
  --results-dir outputs/tuning/sess001 \
  --max-drawdown-pct 15 \
  --min-trades 5 \
  --output-json outputs/tuning/sess001_summary.json
```

**출력 JSON:**
```json
{
  "total_jobs": 50,
  "success_jobs": 47,
  "error_jobs": 3,
  "filters": {
    "max_drawdown_pct": 15.0,
    "min_trades": 5
  },
  "top_by_pnl": [
    {
      "job_id": "sess001_0007",
      "tag": "sess001",
      "config": {
        "data_file": "data/sample_arbitrage_prices.csv",
        "min_spread_bps": 30.0,
        ...
      },
      "metrics": {
        "total_trades": 18,
        "realized_pnl_usd": 1250.0,
        "max_drawdown_pct": 10.0,
        ...
      },
      "status": "success"
    },
    ...
  ]
}
```

### 예시 4: Python API 사용

```python
from arbitrage.tuning_aggregate import TuningResultsAggregator

# 집계기 초기화 (필터 적용)
aggregator = TuningResultsAggregator(
    results_dir="outputs/tuning/sess001",
    max_results=10,
    max_drawdown_pct=15.0,
    min_trades=5,
)

# 요약 생성
summary = aggregator.summarize()

# 결과 확인
print(f"Total Jobs: {summary.total_jobs}")
print(f"Success Jobs: {summary.success_jobs}")
print(f"Error Jobs: {summary.error_jobs}")
print()

# 상위 결과 출력
for idx, result in enumerate(summary.top_by_pnl, 1):
    metrics = result.metrics
    config = result.config
    
    print(f"{idx}. {result.job_id}")
    print(f"   PnL: ${metrics['realized_pnl_usd']:,.2f}")
    print(f"   Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"   Trades: {metrics['total_trades']}")
    print(f"   Min Spread: {config['min_spread_bps']} bps")
    print()
```

---

## 결과 해석

### 메트릭 설명

| 메트릭 | 설명 | 해석 |
|--------|------|------|
| `realized_pnl_usd` | 실현된 손익 | 높을수록 좋음 |
| `max_drawdown_pct` | 최대 낙폭 | 낮을수록 좋음 |
| `total_trades` | 총 거래 수 | 충분한 샘플 필요 |
| `win_rate` | 승률 | 높을수록 좋음 |
| `avg_pnl_per_trade_usd` | 거래당 평균 PnL | 높을수록 좋음 |

### 필터 선택 가이드

**보수적 필터:**
```bash
--max-drawdown-pct 10 \
--min-trades 10
```
→ 안정적이고 검증된 설정

**공격적 필터:**
```bash
--max-drawdown-pct 20 \
--min-trades 5
```
→ 높은 수익 가능성

**균형잡힌 필터:**
```bash
--max-drawdown-pct 15 \
--min-trades 8
```
→ 위험-수익 균형

---

## 워크플로우

### 전체 분석 파이프라인

```
1. 세션 계획 생성
   ↓
2. 모든 작업 실행 (D38)
   ↓
3. 결과 집계
   ↓
4. 필터링 및 순위 지정
   ↓
5. 최고 성능 설정 식별
   ↓
6. 최적화 방향 결정
```

### 자동화 예시 (Python)

```python
from arbitrage.tuning_aggregate import TuningResultsAggregator
import json

# 여러 필터 조합으로 분석
filters = [
    {"max_drawdown_pct": 10, "min_trades": 10},
    {"max_drawdown_pct": 15, "min_trades": 8},
    {"max_drawdown_pct": 20, "min_trades": 5},
]

for filter_set in filters:
    aggregator = TuningResultsAggregator(
        results_dir="outputs/tuning/sess001",
        **filter_set,
    )
    summary = aggregator.summarize()
    
    print(f"Filter: {filter_set}")
    print(f"Results: {len(summary.top_by_pnl)}")
    if summary.top_by_pnl:
        best = summary.top_by_pnl[0]
        print(f"Best PnL: ${best.metrics['realized_pnl_usd']:,.2f}")
    print()
```

---

## 주요 특징

### 오류 처리

- 잘못된 JSON 파일 자동 감지
- 오류 작업을 별도로 계산
- 전체 집계 계속 진행

### 확장성

- 무제한 결과 파일 지원
- 메모리 효율적 (순차 로드)
- 빠른 필터링 및 순위 지정

### 호환성

- D38 JSON 출력과 완벽 호환
- 표준 JSON 형식
- 외부 분석 도구와 통합 가능

---

## 안전 정책

### Read-Only 정책

✅ 모든 작업이 읽기 전용:
- 결과 파일 로드 (읽기만)
- 메트릭 계산 (메모리)
- 요약 파일 쓰기 (선택적)

### Observability 정책

✅ 투명한 집계:
- 모든 필터 명시적
- 모든 계산 추적 가능
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
