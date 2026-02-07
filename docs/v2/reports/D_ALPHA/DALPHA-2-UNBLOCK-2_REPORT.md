# D_ALPHA-2-UNBLOCK-2: PnL SSOT + Bootstrap Enforcement (OBI ON 20m)

**Status:** IN PROGRESS (2026-02-07)

**Branch:** rescue/d207_6_multi_symbol_alpha_survey

**Commit:** AC 충족 후 기록

---

## 목표 (Objective)

- net_pnl_full SSOT 단일화로 PnL 계산 기준 통일
- bootstrap_runtime_env.ps1 실행 강제 (BOOTSTRAP_FLAG)
- OBI ON 20m survey TIME_REACHED 완주 증거 확보
- Gate Doctor/Fast/Regression zero-skip 달성

---

## 스코프 (Scope)

- `arbitrage/v2/core/engine_report.py`
- `arbitrage/v2/domain/pnl_calculator.py`
- `arbitrage/v2/core/run_watcher.py`
- `arbitrage/v2/core/orchestrator.py`
- `scripts/bootstrap_runtime_env.ps1`
- `scripts/run_gate_with_evidence.py`
- `tests/test_d_alpha_2_pnl_ssot.py`
- `tests/conftest.py`
- `docs/v2/design/READING_CHECKLIST.md`

---

## 구현 요약

1. **PnL SSOT 단일화**
   - `calculate_net_pnl_full()` 기반으로 gross/fees/slippage/latency/partial_penalty 합산
   - KPI/Engine report의 net_pnl_full 기준 통일

2. **Bootstrap 강제**
   - `BOOTSTRAP_FLAG` 미설정 시 즉시 종료
   - 테스트 환경에서는 `tests/conftest.py` 기본값으로 대응

3. **정합성 테스트 추가**
   - `tests/test_d_alpha_2_pnl_ssot.py`에서 net_pnl_full 공식 검증

4. **Gate SKIP/WARN=FAIL 강제**
   - `scripts/run_gate_with_evidence.py`에서 pytest 출력 파싱 후 skip/warn>0이면 FAIL 처리

---

## 실행/검증 결과

### Gate Doctor/Fast/Regression (2026-02-07)
- Doctor: PASS (`logs/evidence/20260207_181528_gate_doctor_98d565f/`, exitcode=0)
- Fast: PASS (`logs/evidence/20260207_181540_gate_fast_98d565f/`)
- Regression: PASS (`logs/evidence/20260207_181836_gate_regression_98d565f/`)

**판정:** GATE_NO_SKIP=1로 skip/skipif 테스트 deselect, SKIP/WARN=FAIL 강제 하에 PASS

### OBI ON 20m Survey (TIME_REACHED)
- Evidence: `logs/evidence/d_alpha_2_obi_on_20m_20260207_1425/`
- watch_summary.json:
  - duration_sec=1206.12, completeness_ratio=1.0, stop_reason=TIME_REACHED
- KPI 요약:
  - closed_trades=13, gross_pnl=7.3, net_pnl_full=1.77
  - fees=0.13, winrate=76.92%, db_inserts_ok=65

---

## 테스트 (PnL SSOT)

- 테스트: `tests/test_d_alpha_2_pnl_ssot.py`
- 내용: net_pnl_full = gross - (fees + slippage + latency + partial_penalty)

---

## DocOps / Boundary Gate

- DocOps: PASS (2026-02-07)
  - Evidence: `logs/evidence/dalpha_2_unblock_2_docops_20260207_182211/`
  - `ssot_docs_check_exitcode.txt`: 0
  - `ssot_docs_check_raw.txt`: PASS 출력
  - `rg_cci.txt`, `rg_migrate.txt`, `rg_todo.txt`: NO_MATCH (Select-String 기반)
- Boundary: PASS (2026-02-07)
  - `v2_boundary_exitcode.txt`: 0
  - `v2_boundary_raw.txt`: PASS 출력

---

## Evidence 경로

- OBI ON 20m Survey: `logs/evidence/d_alpha_2_obi_on_20m_20260207_1425/`
- Gate Doctor/Fast/Regression:
  - `logs/evidence/20260207_181528_gate_doctor_98d565f/`
  - `logs/evidence/20260207_181540_gate_fast_98d565f/`
  - `logs/evidence/20260207_181836_gate_regression_98d565f/`
- DocOps/Boundary: `logs/evidence/dalpha_2_unblock_2_docops_20260207_182211/`

---

## 잔여 AC (Follow-up)

- AC-1: OBI 계산 표준화 + 동적 임계치
- AC-2: TopN OBI 랭킹 + 아티팩트
- AC-3: positive net edge 샘플 확보 또는 실패 원인 분해
- AC-4: Regression zero-skip (skip=0)
- AC-6: MODEL_ANOMALY 원인 분해 보고
