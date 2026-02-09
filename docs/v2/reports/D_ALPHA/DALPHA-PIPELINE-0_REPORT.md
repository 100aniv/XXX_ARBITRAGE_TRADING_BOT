# D_ALPHA-PIPELINE-0 REPORT — One-Command Product Pipeline + Auto-Rail

**Date:** 2026-02-09 11:30 UTC+09:00  
**Branch:** rescue/d207_6_multi_symbol_alpha_survey  
**Status:** IN PROGRESS (entrypoint 경로 확인 필요)

---

## 1. 목표
- Gate/DocOps/Boundary/Survey를 단일 파이프라인으로 실행 가능하게 하고 증거를 단일 경로로 저장.
- Auto-Rail(bootstrap + git clean + gate + docops + boundary + survey) 완주 확인.

---

## 2. 실행 요약

### 2.1 Gate (Doctor/Fast/Regression)
- Doctor: `logs/evidence/20260209_105148_gate_doctor_66a6d64/`
- Fast: `logs/evidence/20260209_105214_gate_fast_66a6d64/`
- Regression: `logs/evidence/20260209_105512_gate_regression_66a6d64/`

### 2.2 DocOps Gate
- Evidence: `logs/evidence/dalpha_pipeline_0_docops_20260209_113000/`
- `ssot_docs_check_exitcode.txt`: 0
- `ssot_docs_check_raw.txt`: PASS 출력
- `rg_cci.txt`, `rg_migrate.txt`, `rg_marker.txt`: 결과 저장 (SSOT 문서 내 규칙/가이드 포함)

### 2.3 V2 Boundary
- Evidence: `logs/evidence/dalpha_pipeline_0_boundary_20260209_105950/`
- `v2_boundary_exitcode.txt`: 0

---

## 3. Survey (20m, REAL, Maker)

**Run ID:** dalpha_pipeline_0_survey_20260209_110022  
**Evidence:** `logs/evidence/dalpha_pipeline_0_survey_20260209_110022/`

### 3.1 KPI 요약
- duration_minutes: 20.16 (expected=20)
- stop_reason: TIME_REACHED
- opportunities_generated: 63
- closed_trades: 14 (wins=10, losses=4, winrate=71.43%)
- gross_pnl: 1.69
- net_pnl_full: -7.82
- exec_cost_total: 9.517

### 3.2 Edge Survey 요약
- total_ticks: 69
- unique_symbols_evaluated: 47
- coverage_ratio: 0.47
- positive_net_edge_pct: 18.52

### 3.3 Wallclock
- started_at_utc: 2026-02-09T02:02:02.931128+00:00
- ended_at_utc: 2026-02-09T02:22:13.502392+00:00
- completeness_ratio: 1.0

---

## 4. 실행 명령

### Gate
```powershell
powershell -ExecutionPolicy Bypass -Command "& { . .\scripts\bootstrap_runtime_env.ps1; python scripts\run_gate_with_evidence.py doctor }"
powershell -ExecutionPolicy Bypass -Command "& { . .\scripts\bootstrap_runtime_env.ps1; python scripts\run_gate_with_evidence.py fast }"
powershell -ExecutionPolicy Bypass -Command "& { . .\scripts\bootstrap_runtime_env.ps1; python scripts\run_gate_with_evidence.py regression }"
```

### DocOps
```powershell
$docops = "logs/evidence/dalpha_pipeline_0_docops_20260209_113000"; New-Item -ItemType Directory -Path $docops -Force | Out-Null
$raw = & python scripts/check_ssot_docs.py 2>&1; $exit = $LASTEXITCODE
$raw | Out-File -FilePath (Join-Path $docops "ssot_docs_check_raw.txt") -Encoding utf8
$exit | Out-File -FilePath (Join-Path $docops "ssot_docs_check_exitcode.txt") -Encoding ascii
$paths = @(Get-ChildItem -Path "docs/v2" -Recurse -File | Select-Object -ExpandProperty FullName); $paths += (Resolve-Path "D_ROADMAP.md").Path
(Select-String -Pattern "cci:" -Path $paths) | Out-File -FilePath (Join-Path $docops "rg_cci.txt") -Encoding utf8
(Select-String -Pattern "이관|migrate|migration" -Path $paths) | Out-File -FilePath (Join-Path $docops "rg_migrate.txt") -Encoding utf8
(Select-String -Pattern "TODO|TBD|PLACEHOLDER" -Path $paths) | Out-File -FilePath (Join-Path $docops "rg_marker.txt") -Encoding utf8
git status --short | Out-File -FilePath (Join-Path $docops "git_status.txt") -Encoding utf8
git diff --stat | Out-File -FilePath (Join-Path $docops "git_diff_stat.txt") -Encoding utf8
git diff | Out-File -FilePath (Join-Path $docops "git_diff.txt") -Encoding utf8
```

### Survey
```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmmss"; $out = "logs/evidence/dalpha_pipeline_0_survey_$ts"
& { . .\scripts\bootstrap_runtime_env.ps1; python -m arbitrage.v2.harness.paper_runner --duration 20 --phase edge_survey --survey-mode --use-real-data --maker-mode --output-dir $out --db-mode strict --ensure-schema }
```

---

## 5. 경로 불일치 이슈
- 실패 경로: `c:/work/XXX_ARBITRAGE_TRADING_BOT/scripts/run_alpha_pipeline.py`
- 실제 경로: 검색 결과 없음 (repo 전체 탐색 결과 미발견)
- 원인: 파일명/경로 불일치 또는 파일 미존재

---

## 6. Evidence 경로
- Gate Doctor: `logs/evidence/20260209_105148_gate_doctor_66a6d64/`
- Gate Fast: `logs/evidence/20260209_105214_gate_fast_66a6d64/`
- Gate Regression: `logs/evidence/20260209_105512_gate_regression_66a6d64/`
- DocOps: `logs/evidence/dalpha_pipeline_0_docops_20260209_113000/`
- Boundary: `logs/evidence/dalpha_pipeline_0_boundary_20260209_105950/`
- Survey: `logs/evidence/dalpha_pipeline_0_survey_20260209_110022/`

---

## 7. 결론
- Gate/DocOps/Boundary/Survey는 완료했으며, entrypoint 경로 확인이 잔여.
- 파이프라인 자동 실행 기록은 entrypoint 경로 확인 후 AC-1/AC-6 확정 필요.
