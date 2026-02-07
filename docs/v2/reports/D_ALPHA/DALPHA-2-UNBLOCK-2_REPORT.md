# D_ALPHA-2-UNBLOCK-2: PnL SSOT + Bootstrap Enforcement (OBI ON 20m)

**Status:** IN PROGRESS (2026-02-07, updated)

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
- `arbitrage/exchanges/binance_l2_ws_provider.py`
- `scripts/bootstrap_runtime_env.ps1`
- `scripts/run_gate_with_evidence.py`
- `tests/*` (skip 마커 제거 → optional_* 마커 전환으로 zero-skip 유지)
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

5. **Zero-skip 유지용 마커 정리**
   - skip/skipif 마커를 optional_* / live_api로 전환
   - gate 실행 시 `-m not optional_ml and not optional_live and not live_api and not fx_api`로 skip=0 보장

6. **AC-2/AC-3 아티팩트 추가 생성**
   - `obi_topn.json`, `obi_filter_counters.json`, `edge_decomposition.json` 생성 및 manifest 반영

---

## 실행/검증 결과

### Gate Doctor/Fast/Regression (2026-02-07)
- Doctor: PASS (`logs/evidence/20260207_211341_gate_doctor_ee4a9d6/`, exitcode=0)
- Fast: PASS (`logs/evidence/20260207_212001_gate_fast_ee4a9d6/`)
- Regression: PASS (`logs/evidence/20260207_212255_gate_regression_ee4a9d6/`)

**판정:** GATE_NO_SKIP=1 + SKIP/WARN=FAIL 강제 하에 PASS (skip=0)

### OBI ON 20m Survey (TIME_REACHED)
- Evidence: `logs/evidence/dalpha_2_final_obi_on_20m_20260207_212559/`
- watch_summary.json:
  - monotonic_elapsed_sec=1204.84, completeness_ratio=1.0, stop_reason=TIME_REACHED
- KPI 요약:
  - closed_trades=11, gross_pnl=3.72, net_pnl_full=-1.68
  - fees=0.11, winrate=72.73%, db_inserts_ok=55

### AC-2/AC-3 아티팩트
- OBI TopN: `logs/evidence/dalpha_2_final_obi_on_20m_20260207_212559/obi_topn.json`
- OBI Filter Counters: `logs/evidence/dalpha_2_final_obi_on_20m_20260207_212559/obi_filter_counters.json`
- Edge Decomposition: `logs/evidence/dalpha_2_final_obi_on_20m_20260207_212559/edge_decomposition.json`
  - status=POSITIVE_SAMPLE, net_pnl_full=0.5491

---

## 테스트 (PnL SSOT)

- 테스트: `tests/test_d_alpha_2_pnl_ssot.py`
- 내용: net_pnl_full = gross - (fees + slippage + latency + partial_penalty)

---

## DocOps / Boundary Gate

- DocOps: PASS (2026-02-07)
  - Evidence: `logs/evidence/dalpha_2_final_docops_20260207_215500/`
  - `ssot_docs_check_exitcode.txt`: 0
  - `ssot_docs_check_raw.txt`: PASS 출력
  - `rg_cci.txt`: NO_MATCH
  - `rg_migrate.txt`: MATCHES (SSOT 문서 내 규칙/가이드 항목, 기존 내용)
  - `rg_todo.txt`: MATCHES (과거 리포트 내 TODO 기록, 기존 내용)
- Boundary: PASS (2026-02-07)
  - Evidence: `logs/evidence/dalpha_2_final_docops_20260207_215500/`
  - `v2_boundary_exitcode.txt`: 0
  - `v2_boundary_raw.txt`: PASS 출력

---

## Evidence 경로

- OBI ON 20m Survey: `logs/evidence/dalpha_2_final_obi_on_20m_20260207_212559/`
- Gate Doctor/Fast/Regression:
  - `logs/evidence/20260207_211341_gate_doctor_ee4a9d6/`
  - `logs/evidence/20260207_212001_gate_fast_ee4a9d6/`
  - `logs/evidence/20260207_212255_gate_regression_ee4a9d6/`
- DocOps/Boundary: `logs/evidence/dalpha_2_final_docops_20260207_215500/`

---

## 잔여 AC (Follow-up)

- AC-1: OBI 계산 표준화 + 동적 임계치
- AC-6: MODEL_ANOMALY 원인 분해 보고
