# D207-5: Baseline Validity Guard + Evidence Hardening

**Date:** 2026-01-27  
**Status:** ✅ DONE  
**Evidence:** `logs/evidence/d207_5_docops_gate_20260127_123633/`

---

## 목표

- Baseline Validity Guard: symbols 비어있음 또는 real_ticks_ok_count=0 → Exit 1
- Evidence Hardening: run_meta (config_path, symbols, cli_args, git_sha, branch, run_id) 자동 기록
- Edge Analysis Summary: edge_distribution.json 기반 통계 자동 생성
- D_ROADMAP Rebase: D208-0 제거, D208~D210 번호 시프트

---

## 구현 요약

### 1. Baseline Validity Guard (orchestrator.py)
- symbols 비어있음 → INVALID_RUN_SYMBOLS_EMPTY, Exit 1
- REAL mode + real_ticks_ok_count=0 → INVALID_RUN_REAL_TICKS_ZERO, Exit 1
- 모든 경우 stop_reason + stop_message 기록

### 2. Evidence Hardening (engine_report.py, monitor.py, orchestrator.py)
- run_meta 필드: run_id, git_sha, branch, config_path, symbols, cli_args
- engine_report.json에 run_meta 포함
- manifest.json에 run_meta 포함
- edge_analysis_summary.json 자동 생성 (p50/max/min edge_bps 통계)

### 3. Real Tick Counting (opportunity_source.py)
- real_ticks_ok_count 증가 시점: 성공적인 tick 처리 후 (profitability 필터 전)
- 정확한 real tick 개수 추적

### 4. Break-even Fix (break_even.py)
- compute_execution_risk_round_trip: 2x per_leg 적용 (D205-9-2 정렬)
- test_d203_1_break_even 9/9 PASS

### 5. D_ROADMAP Rebase
- D208-0 제거 (계획 블록)
- D208 승격: Structural Normalization
- D209/D210 번호 시프트 (기존 D208/D209 → D209/D210)
- REBASELOG 기록

---

## 테스트 결과

### Unit Tests
- test_d207_3_edge_distribution_artifact.py: ✅ PASS
- test_d207_5_invalid_run_guards.py: ✅ PASS (2/2)
- test_d203_1_break_even.py: ✅ PASS (9/9)

### Gate Results
- **Doctor:** ✅ PASS (logs/evidence/20260127_123537_gate_doctor_197cb83/)
- **Fast:** ✅ PASS (logs/evidence/20260127_111915_gate_fast_197cb83/)
- **Regression:** ✅ PASS (logs/evidence/20260127_112308_gate_regression_197cb83/)

### DocOps Gate
- **Gate (A):** check_ssot_docs.py ExitCode=0 ✅ PASS
- **Gate (B):** ripgrep 위반 탐지 ✅ PASS (0건)
- **Gate (C):** Pre-commit sanity ✅ PASS
- **Evidence:** logs/evidence/d207_5_docops_gate_20260127_123633/

---

## REAL Baseline (20분)

**Run ID:** d205_18_2d_baseline_20260127_1047  
**Duration:** 20분 (1200.34초)  
**Evidence:** logs/evidence/d205_18_2d_baseline_20260127_1047/

### KPI 결과
- real_ticks_ok_count: 5260 ✅ (유효한 real tick)
- symbols: [["BTC/KRW", "BTC/USDT"]] ✅ (비어있지 않음)
- opportunities_generated: 0
- closed_trades: 0
- net_pnl: 0.0 KRW
- stop_reason: TIME_REACHED (정상 완료)
- status: PASS

### Edge Analysis Summary
- total_ticks: 5260
- total_candidates: 10520
- p50 net_edge_bps: -52.5746 (모두 음수)
- positive_net_edge_pct: 0.0%
- negative_net_edge_pct: 100.0%

**해석:** 현재 break-even threshold(43 bps)에 비해 실제 spread(0.4254 bps)가 너무 작아 수익 기회 없음. 전략 파라미터 조정 필요 (D207-1 후속).

---

## 파일 변경 목록

### Modified (9개)
1. `arbitrage/v2/harness/paper_runner.py` - run_meta 필드 추가 (config_path, symbols, cli_args)
2. `arbitrage/v2/core/orchestrator.py` - Validity Guard + run_meta 전달
3. `arbitrage/v2/core/engine_report.py` - run_meta 포함 + get_git_branch() 추가
4. `arbitrage/v2/core/opportunity_source.py` - real_ticks_ok_count 증가 시점 수정
5. `arbitrage/v2/core/monitor.py` - edge_analysis_summary.json 생성 + run_meta in manifest
6. `arbitrage/v2/domain/break_even.py` - compute_execution_risk_round_trip 2x 수정
7. `arbitrage/v2/core/runtime_factory.py` - config_path/symbols 기본값 설정
8. `tests/test_d207_3_edge_distribution_artifact.py` - run_meta 검증 추가
9. `D_ROADMAP.md` - D208-0 제거, D208~D210 시프트, REBASELOG 기록

### Created (2개)
1. `tests/test_d207_5_invalid_run_guards.py` - Validity Guard 테스트
2. `docs/v2/reports/D207/D207-5_REPORT.md` - 이 보고서

### Renamed (1개)
1. `docs/v2/reports/D207/D207-4_CTO_AUDIT_REPORT.md` → `D207-4_REPORT.md` (파일명 규칙 준수)

---

## AC 달성 현황

| AC | 목표 | 상태 | 세부사항 |
|----|------|------|---------|
| AC-1 | symbols 비어있음 → Exit 1 | ✅ PASS | orchestrator.py:214-228, test 2/2 PASS |
| AC-2 | real_ticks_ok_count=0 (REAL) → Exit 1 | ✅ PASS | orchestrator.py:474-487, test 2/2 PASS |
| AC-3 | run_meta 자동 기록 (config_path, symbols, cli_args, git_sha, branch, run_id) | ✅ PASS | engine_report.json + manifest.json 검증 |
| AC-4 | edge_analysis_summary.json 자동 생성 | ✅ PASS | monitor.py:148-186, manifest 포함 |
| AC-5 | REAL baseline 20분 실행 + 증거 확보 | ✅ PASS | d205_18_2d_baseline_20260127_1047/ |
| AC-6 | Gate 3단 PASS (Doctor/Fast/Regression) | ✅ PASS | 모두 PASS |
| AC-7 | DocOps Gate PASS (check_ssot_docs.py ExitCode=0) | ✅ PASS | logs/evidence/d207_5_docops_gate_20260127_123633/ |
| AC-8 | D_ROADMAP Rebase (D208-0 제거, D208~D210 시프트) | ✅ PASS | REBASELOG 기록 + 모든 참조 업데이트 |

---

## 정직한 손실 & 기술적 사기 제거

- **정직한 손실:** 현재 spread가 break-even 미만이므로 거래 미체결 (과장 없는 기록)
- **기술적 사기 제거:** Validity Guard로 symbols 비어있음/real_ticks=0 경로 차단

---

## 남은 과제

- **D207-1 (BASELINE 수익성):** net_pnl > 0 증명 또는 실패 원인 분석 필요
  - 현재: spread 부족 (0.4254 bps vs 43 bps break-even)
  - 다음: 전략 파라미터 조정 또는 거래소 선택 확대 검토

---

## 커밋 정보

**커밋 메시지:**
```
D207-5: Baseline Validity Guard + Evidence Hardening + D_ROADMAP Rebase

- Add invalid-run guards: symbols empty / real_ticks_ok_count=0 → Exit 1
- Harden evidence: run_meta (config_path/symbols/cli_args/git_sha/branch/run_id)
- Auto-generate edge_analysis_summary.json (p50/max/min edge_bps stats)
- Fix compute_execution_risk_round_trip: 2x per_leg (D205-9-2 alignment)
- Rebase D_ROADMAP: Remove D208-0, promote D208, shift D209/D210
- All gates PASS: Doctor/Fast/Regression + DocOps
- REAL baseline 20m: 5260 real_ticks, 0 trades (spread < break-even)
```

**Branch:** rescue/d207_2_longrun_60m  
**Git SHA:** (진행 중)

---

## 증거 경로

### Bootstrap
- logs/evidence/d207_5_docops_gate_20260127_123633/ (DocOps Gate)

### Main Run
- logs/evidence/d205_18_2d_baseline_20260127_1047/ (REAL baseline 20m)
  - kpi.json: real_ticks_ok_count=5260, stop_reason=TIME_REACHED
  - engine_report.json: run_meta 포함, status=PASS
  - manifest.json: run_meta 포함, edge_analysis_summary.json 기록
  - edge_analysis_summary.json: p50/max/min edge_bps 통계

### Gate Results
- logs/evidence/20260127_123537_gate_doctor_197cb83/ (Doctor PASS)
- logs/evidence/20260127_111915_gate_fast_197cb83/ (Fast PASS)
- logs/evidence/20260127_112308_gate_regression_197cb83/ (Regression PASS)

---

## 최종 상태

✅ **D207-5 DONE**
- 모든 AC 충족 (8/8)
- Gate 3단 PASS
- DocOps PASS
- REAL baseline 증거 확보
- D_ROADMAP Rebase 완료
- 커밋/푸시 준비 완료
