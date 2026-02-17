# DALPHA-2 AC-6 Model Anomaly Decomposition Report

Date: 2026-02-17  
Step: D_ALPHA-2 AC-6

## Objective

AC-6 요구사항인 MODEL_ANOMALY 원인 분해를 기존 실행 증거와 코드 경로로 연결해 정리한다.

## Canonical Evidence

- Failing run: `logs/evidence/d_alpha_2_obi_off_smoke_20m_20260205_005828/`
- Key fields:
  - `watch_summary.stop_reason = MODEL_ANOMALY`
  - `kpi.duration_seconds = 123.79`, `kpi.expected_duration_sec = 1200`
  - `kpi.wallclock_drift_pct = 89.7`
  - `kpi.winrate_pct = 100.0`

## Root-Cause Decomposition

1. Time Truth Axis
   - Symptom: planned 20m 대비 조기 종료(약 124s)
   - Indicator: `wallclock_drift_pct=89.7`
   - Interpretation: watcher fail-fast guard가 early-stop을 트리거

2. Market Structure Axis
   - Symptom: OBI OFF run에서 안정적 trade continuation 실패
   - Indicator: stop reason이 MODEL_ANOMALY로 전환
   - Interpretation: 순수 spread 기반 후보군에서 guard tolerance와 충돌

3. Friction/Cost Axis
   - Guard path exists for friction=0 anomaly
   - If `fees_total==0` after enough trades, watcher marks MODEL_ANOMALY

4. Execution Probability Axis
   - Winrate cap and machinegun protections can trigger anomaly stop
   - 100% winrate sustained path is explicitly guarded

## Code Path Mapping

- `arbitrage/v2/core/run_watcher.py`
  - Winrate cap anomaly: stop_reason MODEL_ANOMALY (`FAIL (F)`) at `@arbitrage/v2/core/run_watcher.py#230-250`
  - Friction zero anomaly: stop_reason MODEL_ANOMALY (`FAIL (G)`) at `@arbitrage/v2/core/run_watcher.py#252-264`
  - Machinegun anomaly: stop_reason MODEL_ANOMALY (`FAIL (H)`) at `@arbitrage/v2/core/run_watcher.py#266-283`

## Conclusion

AC-6 요구사항(원인 분해 + 코드 경로 연결)은 충족됨.

- Evidence-linked decomposition: 완료
- Code-path linked diagnosis: 완료
- Canonical link retained in roadmap: 완료
