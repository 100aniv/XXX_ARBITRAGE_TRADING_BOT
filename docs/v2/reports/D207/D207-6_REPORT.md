# D207-6: Multi-Symbol Alpha Survey

**Date:** 2026-02-09  
**Status:** ✅ COMPLETED  
**Evidence:** `logs/evidence/d207_6_alpha_survey_20m/`

---

## 재사용 모듈

- `arbitrage/v2/core/opportunity_source.py`: 멀티 심볼 샘플링/가드 기반
- `arbitrage/v2/core/orchestrator.py`: stop_reason Truth Chain
- `arbitrage/v2/core/monitor.py`: evidence/manifest 기록
- `arbitrage/v2/domain/topn_provider.py`: Top-N 유니버스 공급

---

## 의존성

- Depends on: D207-5 (Baseline Validity Guard)
- Depends on: D207-1-5 (Truth Chain)

---

## 목표

- REAL MarketData 기반 멀티 심볼 알파 서베이 실행
- INVALID_UNIVERSE 가드로 비정상 유니버스 차단
- edge_survey_report.json 스키마 및 sampling_policy 기록
- stop_reason Truth Chain (kpi.json, engine_report.json, watch_summary.json)

---

## 구현 요약

1. **멀티 심볼 샘플링 정책**
   - round_robin + max_symbols_per_tick 적용
   - sampling_policy 메타데이터 기록
2. **INVALID_UNIVERSE 가드**
   - symbols 비어있음 또는 REAL tick 0 → Exit 1
3. **edge_survey_report.json 생성**
   - per-symbol 통계 + sampling_policy + run_meta 기록
4. **stop_reason 전파**
   - TIME_REACHED 및 WARN_FAIL 경로에서 kpi/engine_report/watch_summary 일치
5. **실측 안정화**
   - BTC 페어만 가격 sanity 체크 적용 (알트코인 오탐 방지)
   - Upbit invalid market 회피용 denylist 보강

---

## 테스트 결과

### Unit Tests
- `tests/test_d207_6_edge_survey_report.py`: ✅ PASS
- `tests/test_d207_5_invalid_run_guards.py`: ✅ PASS
- `tests/test_d207_1_5_truth_chain.py`: ✅ PASS

### Gate Results
- **Doctor:** ✅ PASS (`logs/evidence/20260128_211248_gate_doctor_a2269a9/`)
- **Fast:** ✅ PASS (`logs/evidence/20260128_211800_gate_fast_a2269a9/`)
- **Regression:** ✅ PASS (`logs/evidence/20260128_213534_gate_regression_a2269a9/`)

### DocOps Gate
- **Gate (A):** check_ssot_docs.py ExitCode=0 ✅ PASS (`logs/evidence/d207_6_docops_gate_20260128_222059/ssot_docs_check_exitcode.txt`)
- **Gate (B):** DocOps 검색 결과 저장
  - 로컬/IDE 링크 잔재: 0건 (`rg_cci.txt`)
  - 이관 키워드 검색 결과 기록 (`rg_migrate.txt`)
  - 임시 작업 마커 검색 결과 기록 (`rg_todo.txt`)
- **Gate (C):** Pre-commit sanity (`git_status.txt`, `git_diff_stat.txt`, `git_diff.txt`)

**실행 명령:**
```
python scripts/check_ssot_docs.py
PowerShell Select-String (rg 미설치 대체, 로컬 링크/이관/임시 마커 패턴 적용)
git status --short > git_status.txt
git diff --stat > git_diff_stat.txt
git diff > git_diff.txt
```

---

## REAL Survey (20분)

**Run ID:** d207_6_alpha_survey_20m  
**Duration:** 1204.5s (20.08분)  
**Symbols:** 50 (Top 100 요청, 50개 로드)

### KPI 요약
- real_ticks_ok_count: 68
- real_ticks_fail_count: 0
- opportunities_generated: 35
- closed_trades: 8
- winrate: 50.0% (4 wins / 4 losses)
- net_pnl: -2.44
- reject_total: 86
- reject_reasons: units_mismatch=0, candidate_none=33, cooldown=26
- stop_reason: TIME_REACHED
- fx_rate: 1485.13 KRW/USDT (crypto_implied)

### Edge Survey 요약
- total_ticks: 68
- total_candidates: 3400
- unique_symbols_evaluated: 49
- coverage_ratio: 0.49 (49/100)
- p95_net_edge_bps: 35.37
- p99_net_edge_bps: 91.40
- max_net_edge_bps: 110.46
- positive_net_edge_pct: 9.56%

**해석:** 멀티심볼 survey 정상 동작, units_mismatch=0 확인, edge_survey_report.json 생성 완료.

---

## AC 달성 현황

| AC | 목표 | 상태 | 세부사항 |
|----|------|------|---------|
| AC-1 | 멀티 심볼 샘플링 정책 적용 | ✅ PASS | round_robin + max_symbols_per_tick=6 기록 |
| AC-2 | INVALID_UNIVERSE 가드 | ✅ PASS | 빈 symbols/REAL tick 0 경로 Exit 1 |
| AC-3 | edge_survey_report.json 스키마 | ✅ PASS | sampling_policy + per-symbol 통계 포함 |
| AC-4 | stop_reason Truth Chain | ✅ PASS | kpi/engine_report/watch_summary TIME_REACHED 일치 |
| AC-5 | REAL 20분 Survey + 증거 | ✅ PASS | d207_6_edge_survey_20260128_2030 |
| AC-6 | Gate 3단 PASS | ✅ PASS | Doctor/Fast/Regression PASS |

---

## Evidence 경로

### Main Run
- `logs/evidence/d207_6_alpha_survey_20m/`
  - kpi.json, engine_report.json, watch_summary.json, edge_survey_report.json, manifest.json
  - edge_distribution.json, edge_analysis_summary.json
  - decision_trace.json, trades_ledger.jsonl

### Gate Results (Pre-flight)
- Doctor: 21/21 PASS (2.6s)
- Fast: 2316/2316 PASS (77s)
- Regression (D207-6): 22/22 PASS (3s)

---

## 다음 단계

- D207-4 Strategy Parameter AutoTuner는 D207-1 BASELINE PASS 이후 진행
