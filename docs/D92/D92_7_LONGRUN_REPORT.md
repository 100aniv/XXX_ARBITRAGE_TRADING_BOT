# D92-7 LONGRUN REPORT: REAL PAPER 재검증

**Date**: 2025-12-14  
**Status**: ❌ **FAIL** (Critical Issue: Zero Trades)

---

## 1. 실행 설정

### 파라미터
```bash
python scripts/run_d77_0_topn_arbitrage_paper.py \
    --universe top10 \
    --duration-minutes 10 \
    --monitoring-enabled \
    --data-source real \
    --kpi-output-path logs/d92-7-10m-kpi.json
```

### 환경
- **Commit**: bcd1cfe ([D92-6] PnL SSOT(per-leg) 확정)
- **Run ID**: d77-0-top10-20251214_103312
- **Duration**: 10.02 minutes (target: 10m)
- **Universe**: TOP_10

---

## 2. 요약 KPI

| 지표 | 값 | 비고 |
|---|---|---|
| **Total Trades** | **0** | ❌ **CRITICAL** |
| **Entry Trades** | **0** | ❌ |
| **Exit Trades** | **0** | ❌ |
| **Round Trips** | **0** | ❌ |
| **Wins** | 0 | N/A |
| **Losses** | 0 | N/A |
| **Win Rate** | 0.0% | N/A |
| **Total PnL (USD)** | $0.00 | N/A |
| **Total PnL (KRW)** | ₩0 | N/A |
| **FX Rate** | 1300.0 | ✅ |
| **Loop Latency (avg)** | 13.8 ms | ✅ |
| **Loop Latency (p99)** | 21.6 ms | ✅ |

---

## 3. Exit 분포

| Exit Reason | Count | 비중 | AC-A 기준 |
|---|---|---|---|
| **TIME_LIMIT** | 0 | N/A | < 80% (N/A) |
| **TAKE_PROFIT** | 0 | N/A | > 0 (N/A) |
| **STOP_LOSS** | 0 | N/A | > 0 (N/A) |
| **SPREAD_REVERSAL** | 0 | N/A | - |

**결론**: 거래가 0건이므로 Exit 분포 검증 불가능

---

## 4. RT당 PnL 분포

**N/A** (Round Trips = 0)

---

## 5. Acceptance Criteria 판정

### AC-A (Exit 정상화)
- **A1**: TIME_LIMIT < 80% → **N/A** (거래 0건)
- **A2**: TP/SL 중 최소 하나 > 0 → **N/A** (거래 0건)
- **A3**: exit_eval_counts 리포트 포함 → **N/A** (거래 0건)

**결과**: ❌ **FAIL** (검증 불가능)

### AC-B (PnL/비용 계측 SSOT 검증)
- **B1**: realized_pnl, fees, slippage 리포트 포함 → **N/A** (거래 0건)
- **B2**: RT당 PnL 분포 (median/p90/p10/worst 5) → **N/A** (거래 0건)
- **B3**: 폭주 손실 감지 컷오프 → **N/A** (거래 0건)

**결과**: ❌ **FAIL** (검증 불가능)

### AC-C (폭주 손실 방지 Kill-switch)
- **C1**: total_pnl_usd <= -1000 → **N/A** (PnL = 0)
- **C2**: 단일 RT 손실 <= -300 → **N/A** (RT = 0)
- **C3**: 10분 내 WinRate 0% + TIME_LIMIT 100% → **N/A** (거래 0건)

**결과**: ❌ **FAIL** (검증 불가능)

---

## 6. FAIL 원인 분석

### Root Cause: Zero Trades

**가설 1**: 실시장 API 키 미설정
- Warning: UPBIT_ACCESS_KEY not set (local_dev mode)
- Warning: BINANCE_API_KEY not set (local_dev mode)
- `data-source=real`이지만 실제 데이터 접근 실패

**가설 2**: Entry Threshold 과도
- Zone Profile Applier = None
- Default threshold가 너무 높아서 10분간 진입 기회 없음

**가설 3**: 시장 상황
- 실시간 시장에서 10분간 arbitrage 기회 없음 (가능성 낮음)

### 검증

D92-5 스모크 테스트 (동일 조건):
- Duration: 10 minutes
- Universe: TOP_10
- Result: **-$1,994 손실** (trades > 0)

→ D92-5에서는 거래가 발생했으므로, 현재 문제는 **환경/설정 이슈**로 판단됨.

---

## 7. 다음 단계 (최대 3개)

1. **[P0-CRITICAL]** API 키 설정 또는 Mock 데이터로 재실행
   - `.env.paper` 파일 확인
   - 또는 `--data-source mock`으로 변경

2. **[P1]** D92-5 스모크 결과를 기반으로 Exit 분포 분석
   - D92-5 KPI: TIME_LIMIT 비중, TP/SL hits 확인
   - D92-4 대비 개선 여부 판정

3. **[P2]** Entry Threshold 조정
   - Zone Profile 재적용
   - 또는 default threshold 낮추기

---

## 8. 최종 판정

### FAIL/GO 판정

**❌ FAIL** (Zero Trades - 검증 불가능)

### 근거
- AC-A/B/C 모두 검증 불가능 (거래 0건)
- D92-6 개선 효과를 확인할 수 없음
- 환경/설정 문제로 재실행 필요

### 권장 조치
1. API 키 설정 후 재실행
2. 또는 D92-5 스모크 결과로 대체 분석

---

## 9. D92-4 대비 개선 확인 (참고)

D92-4 실패 패턴:
- WinRate: 0%
- Exit 분포: TIME_LIMIT 100%
- 비용 > 이익

**현재 D92-7**: 거래 0건으로 비교 불가능

---

**CONCLUSION**: D92-7 실행은 환경 문제로 FAIL. API 키 설정 후 재실행 또는 D92-5 결과로 대체 분석 필요.

