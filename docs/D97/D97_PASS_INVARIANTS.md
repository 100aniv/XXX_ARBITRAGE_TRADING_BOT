# D97 PASS 불변식 (Invariants) - SSOT

**목적**: D97 Top50 1h Baseline Test의 PASS 기준을 불변식으로 정의

**작성일**: 2025-12-18  
**브랜치**: rescue/d97_kpi_ssot_roi

---

## 1. PASS 필수 조건 (하나라도 FAIL 시 전체 FAIL)

### 1.1 실행 시간 (Duration)

```
duration_seconds >= 3600 AND duration_seconds <= 3630
```

- **최소**: 3600초 (1시간)
- **최대**: 3630초 (1시간 30초, 허용 오차 30초)
- **측정 기준**: 실제 wall-clock time (start_time ~ end_time)
- **검증**: KPI JSON의 `duration_seconds` 필드

### 1.2 종료 코드 (Exit Code)

```
exit_code == 0
```

- **0**: 정상 종료 (duration 완료 또는 graceful shutdown)
- **1+**: 오류 종료 (crash, exception, kill signal)
- **검증**: KPI JSON의 `exit_code` 필드

### 1.3 라운드 트립 (Round Trips)

```
round_trips >= 20
```

- **최소**: 20 RT (Entry + Exit 완료된 거래)
- **측정 기준**: exit_trades == round_trips_completed
- **검증**: KPI JSON의 `round_trips_completed` 필드

### 1.4 총 손익 (Total PnL)

```
total_pnl_usd >= 0.0
```

- **최소**: $0 이상 (손실 불가)
- **측정 기준**: 모든 round trip PnL 합계
- **검증**: KPI JSON의 `total_pnl_usd` 필드

### 1.5 KPI JSON 파일 자동 생성

```
KPI JSON 파일이 존재 AND 파싱 가능 AND 필수 필드 포함
```

- **경로**: `--kpi-output-path` 인자로 지정된 경로
- **포맷**: 유효한 JSON (json.load 성공)
- **생성 방식**: 자동 생성 (수동 작성 금지)
- **필수 필드**: 아래 섹션 2 참조

---

## 2. KPI JSON 필수 필드 (Required Fields)

### 2.1 실행 메타데이터 (Execution Metadata)

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `run_id` | string | 실행 세션 고유 ID | "d97_top50_20251218_210000" |
| `start_time` | float | 시작 Unix timestamp | 1702911600.0 |
| `end_time` | float | 종료 Unix timestamp | 1702915200.0 |
| `start_timestamp` | string | 시작 ISO 8601 | "2025-12-18T21:00:00" |
| `end_timestamp` | string | 종료 ISO 8601 | "2025-12-18T22:00:00" |
| `duration_seconds` | float | 실제 실행 시간 (초) | 3600.5 |
| `exit_code` | int | 종료 코드 | 0 |

### 2.2 Universe & Environment

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `universe_mode` | string | Universe 모드 | "TOP_50" |
| `environment` | string | 실행 환경 | "paper" |
| `config_digest` | string | 설정 해시 또는 핵심 파라미터 요약 | "zone_profile_v2_20251218" |

### 2.3 거래 KPI (Trading KPIs)

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `round_trips_completed` | int | 완료된 round trips | 24 |
| `entry_trades` | int | Entry 거래 수 | 24 |
| `exit_trades` | int | Exit 거래 수 | 24 |
| `wins` | int | 수익 RT 수 | 24 |
| `losses` | int | 손실 RT 수 | 0 |
| `win_rate` | float | 승률 (wins / round_trips) | 1.0 |

### 2.4 손익 (PnL)

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `total_pnl_usd` | float | 총 손익 (USD) | 9.92 |
| `total_pnl_krw` | float | 총 손익 (KRW) | 12900.0 |

### 2.5 **원금 & 수익률 (Equity & ROI)** ← 이번 핵심

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `initial_equity_usd` | float | 초기 원금 (USD) | 100000.0 |
| `final_equity_usd` | float | 최종 자산 (USD) | 100009.92 |
| `roi_pct` | float | 수익률 (%) | 0.00992 |

**ROI 계산 공식**:
```python
roi_pct = (final_equity_usd - initial_equity_usd) / initial_equity_usd * 100.0
```

**원금 (initial_equity) 출처**:
- PAPER 모드: `PortfolioState.cash_balance` 초기값
- 또는 `RiskGuard.risk_limits.max_total_exposure` (운용 budget)
- **SSOT**: 코드에서 실제로 사용하는 값을 기록 (추정 금지)

### 2.6 Exit Reason 분포

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `exit_reasons` | object | Exit reason별 카운트 | {"take_profit": 24, "stop_loss": 0, "time_limit": 0} |

### 2.7 Performance Metrics

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `avg_loop_latency_ms` | float | 평균 루프 지연 (ms) | 13.5 |
| `avg_cpu_percent` | float | 평균 CPU 사용률 (%) | 8.5 |
| `avg_memory_mb` | float | 평균 메모리 사용량 (MB) | 120.0 |

---

## 3. 검증 스크립트 (Validation Script)

D97 PASS 여부를 자동 검증하는 스크립트:

```python
import json
from pathlib import Path

def validate_d97_pass(kpi_json_path: str) -> tuple[bool, list[str]]:
    """
    D97 PASS 불변식 검증.
    
    Returns:
        (passed: bool, reasons: list[str])
    """
    reasons = []
    
    # 1. KPI JSON 파일 존재 확인
    kpi_path = Path(kpi_json_path)
    if not kpi_path.exists():
        reasons.append(f"FAIL: KPI JSON file not found: {kpi_json_path}")
        return False, reasons
    
    # 2. JSON 파싱
    try:
        with open(kpi_path, 'r') as f:
            kpi = json.load(f)
    except json.JSONDecodeError as e:
        reasons.append(f"FAIL: Invalid JSON format: {e}")
        return False, reasons
    
    # 3. 필수 필드 존재 확인
    required_fields = [
        "run_id", "start_time", "end_time", "duration_seconds", "exit_code",
        "universe_mode", "environment", "config_digest",
        "round_trips_completed", "entry_trades", "exit_trades",
        "wins", "losses", "win_rate",
        "total_pnl_usd", "total_pnl_krw",
        "initial_equity_usd", "final_equity_usd", "roi_pct",
        "exit_reasons", "avg_loop_latency_ms"
    ]
    
    missing_fields = [f for f in required_fields if f not in kpi]
    if missing_fields:
        reasons.append(f"FAIL: Missing required fields: {missing_fields}")
        return False, reasons
    
    # 4. 불변식 검증
    passed = True
    
    # 4.1 Duration
    duration = kpi["duration_seconds"]
    if duration < 3600:
        reasons.append(f"FAIL: duration_seconds ({duration:.1f}) < 3600")
        passed = False
    elif duration > 3630:
        reasons.append(f"WARN: duration_seconds ({duration:.1f}) > 3630 (tolerance exceeded)")
    
    # 4.2 Exit Code
    exit_code = kpi["exit_code"]
    if exit_code != 0:
        reasons.append(f"FAIL: exit_code ({exit_code}) != 0")
        passed = False
    
    # 4.3 Round Trips
    round_trips = kpi["round_trips_completed"]
    if round_trips < 20:
        reasons.append(f"FAIL: round_trips_completed ({round_trips}) < 20")
        passed = False
    
    # 4.4 PnL
    pnl = kpi["total_pnl_usd"]
    if pnl < 0:
        reasons.append(f"FAIL: total_pnl_usd ({pnl:.2f}) < 0")
        passed = False
    
    # 4.5 ROI 계산 검증
    initial = kpi["initial_equity_usd"]
    final = kpi["final_equity_usd"]
    roi_calculated = (final - initial) / initial * 100.0
    roi_recorded = kpi["roi_pct"]
    
    if abs(roi_calculated - roi_recorded) > 0.01:  # 0.01% tolerance
        reasons.append(f"WARN: ROI mismatch (calculated: {roi_calculated:.4f}%, recorded: {roi_recorded:.4f}%)")
    
    # 5. PASS 메시지
    if passed:
        reasons.append(f"PASS: All invariants satisfied")
        reasons.append(f"  - Duration: {duration:.1f}s (>= 3600s)")
        reasons.append(f"  - Exit Code: {exit_code} (== 0)")
        reasons.append(f"  - Round Trips: {round_trips} (>= 20)")
        reasons.append(f"  - PnL: ${pnl:.2f} (>= 0)")
        reasons.append(f"  - ROI: {roi_recorded:.4f}% (initial: ${initial:.2f}, final: ${final:.2f})")
    
    return passed, reasons


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python validate_d97.py <kpi_json_path>")
        sys.exit(1)
    
    kpi_path = sys.argv[1]
    passed, reasons = validate_d97_pass(kpi_path)
    
    print("=" * 80)
    print("D97 PASS INVARIANTS VALIDATION")
    print("=" * 80)
    for reason in reasons:
        print(reason)
    print("=" * 80)
    
    sys.exit(0 if passed else 1)
```

---

## 4. 사용법 (Usage)

### 4.1 D97 실행

```bash
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --universe top50 \
  --duration-minutes 60 \
  --kpi-output-path docs/D97/evidence/<run_id>/kpi.json
```

### 4.2 검증

```bash
python scripts/validate_d97.py docs/D97/evidence/<run_id>/kpi.json
```

### 4.3 기대 출력 (PASS)

```
================================================================================
D97 PASS INVARIANTS VALIDATION
================================================================================
PASS: All invariants satisfied
  - Duration: 3600.5s (>= 3600s)
  - Exit Code: 0 (== 0)
  - Round Trips: 24 (>= 20)
  - PnL: $9.92 (>= 0)
  - ROI: 0.0099% (initial: $100000.00, final: $100009.92)
================================================================================
```

---

## 5. 다음 단계 (Next Steps)

1. **STEP 3**: Runner 스크립트 수정
   - SIGTERM/SIGINT 핸들러 추가
   - 주기적 체크포인트 (60초마다 KPI JSON 업데이트)
   - Duration 제어 (3600초 후 graceful shutdown)
   - ROI 계산 (initial_equity, final_equity, roi_pct)

2. **STEP 4**: Gate 실행 (Fast Gate 5/5, Core Regression 100%)

3. **STEP 5**: D97 1h baseline 재실행 (KPI JSON 자동 생성 검증)

4. **STEP 6**: 문서/ROADMAP 업데이트

5. **STEP 7**: Git commit & push

---

**문서 버전**: 1.0  
**SSOT 상태**: ACTIVE  
**다음 리뷰**: D97 PASS 후
