# D92-7 Context Scan: REAL PAPER 1h 재검증

**Date**: 2025-12-14  
**Objective**: D92-6 이후 1h PAPER 실행으로 Exit 분포/PnL/비용 개선 여부를 수치로 확정

---

## 1. 기존 스크립트 스캔 결과

### A. 실행 스크립트 (재사용 가능)

| 스크립트 | 역할 | 재사용 여부 |
|---|---|---|
| `run_d92_1_topn_longrun.py` | TopN PAPER 1h 실행 (Zone Profile 기반) | ✅ 재사용 (파라미터 조정) |
| `run_d77_0_topn_arbitrage_paper.py` | TopN PAPER Baseline (Exit Strategy 포함) | ✅ 참조 (Exit 분포 집계) |
| `run_d92_5_smoke_test.py` | 10분 스모크 테스트 | ❌ 불필요 (1h 실행이 목표) |

### B. 핵심 모듈

| 모듈 | 역할 | 현황 |
|---|---|---|
| `arbitrage/accounting/pnl_calculator.py` | Per-leg PnL SSOT | ✅ D92-6 완료 |
| `arbitrage/domain/exit_strategy.py` | TP/SL/Time Exit 로직 | ✅ D92-6에서 exit_eval_counts 추가 |
| `arbitrage/common/run_paths.py` | SSOT 경로 해석 | ✅ 기존 사용 |

---

## 2. D92-4 실패 패턴 (기준선)

D92-4 Threshold Sweep 결과에서 관측된 실패 패턴:
- **WinRate**: 0% (전체 손실)
- **Exit 분포**: TIME_LIMIT 100% (TP/SL 0회)
- **비용 > 이익**: 수수료/슬리피지가 spread 이득보다 큼
- **총 PnL**: 대규모 손실 (정확한 수치는 D92-4 리포트 확인 필요)

---

## 3. D92-7 실행 계획

### 실행 파라미터
```bash
python scripts/run_d77_0_topn_arbitrage_paper.py \
    --universe top10 \
    --duration-minutes 60 \
    --monitoring-enabled \
    --stage-id d92-7
```

**또는** (Zone Profile 기반)
```bash
python scripts/run_d92_1_topn_longrun.py \
    --top-n 10 \
    --duration-minutes 60 \
    --stage-id d92-7
```

### 필요한 최소 수정

#### A. Kill-switch 로직 추가
- `run_d77_0_topn_arbitrage_paper.py`에 런타임 Kill-switch 추가
- 조건:
  - `total_pnl_usd <= -1000`
  - 단일 RT 손실 `<= -300`
  - 10분 내 WinRate 0% + TIME_LIMIT 100%

#### B. Exit 분포 집계
- `exit_reasons` 카운트 (기존 코드 재사용)
- `exit_eval_counts` (D92-6에서 추가된 것 활용)

#### C. RT당 PnL 분포 계산
- Median, p90, p10, worst 5 RT
- Per-leg PnL 분리 (long/short)

---

## 4. 재사용할 기존 코드

### A. Exit 분포 집계 (run_d77_0_topn_arbitrage_paper.py:820-823)
```python
# Update exit reason count
reason_key = exit_signal.reason.name.lower()
self.metrics["exit_reasons"][reason_key] += 1
```

### B. PnL 누적 (run_d77_0_topn_arbitrage_paper.py:826-828)
```python
pnl = exit_result.pnl
self.metrics["total_pnl_usd"] += pnl
self.metrics["total_pnl_krw"] += pnl * self.metrics["fx_rate"]
```

### C. Exit Strategy exit_eval_counts (arbitrage/domain/exit_strategy.py:98-103)
```python
self.exit_eval_counts = {
    "tp_hit": 0,
    "sl_hit": 0,
    "time_limit_hit": 0,
    "none": 0,
}
```

---

## 5. 이번 작업에서 추가할 것

### A. Kill-switch 로직
- `_check_killswitch()` 메서드 추가
- 런타임 중 1분마다 체크
- 조건 만족 시 즉시 종료 + FAIL 기록

### B. RT 분포 계산
- `_calculate_rt_distribution()` 메서드 추가
- Per-RT PnL 리스트 유지
- Median/p90/p10/worst 5 계산

### C. 최종 리포트 생성
- `docs/D92/D92_7_LONGRUN_REPORT.md` 자동 생성
- AC-A/B/C 기반 PASS/FAIL 판정

---

## 6. 실행 흐름

```
1. Preflight (프로세스 정리 + Redis/DB 초기화)
2. 새 CMD 창에서 1h PAPER 실행
3. 1분마다 Kill-switch 체크 + KPI 출력
4. 완료 후 결과 분석 리포트 생성
5. AC 기반 PASS/FAIL 판정
6. ROADMAP 업데이트 + Git Commit
```

---

## 7. 다음 단계

✅ STEP B: Preflight (프로세스 정리 + Redis/DB 초기화)

