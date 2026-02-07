# D205-19: PnL Accounting Fix + Winrate Reality + No-Cheat Gate

## 목표 (Objective)

- net_pnl 회계를 마찰 포함(슬리피지/레이턴시/부분체결/거절)으로 정규화
- 승률 100%/비현실적 승률을 가드로 감지(Reality Guard)
- Gate 치팅 방지(Zero-skip Regression 방향 유지)
- infra SSOT(Compose) 기반 Step0 부트스트랩을 실행에 강제 연결

## Acceptance Criteria (AC) + 검증 결과

- AC-1: net_pnl_full = gross - (fees + slippage + latency + partial) 수식 강제
  - Evidence: `logs/evidence/d_alpha_2_obi_on_20m_20260207_1050/kpi.json` (`net_pnl_full`, `exec_cost_total`)
- AC-2: winrate는 net_pnl_full 기준으로 산출 (100% 즉시 가드)
  - Evidence: `logs/evidence/d_alpha_2_obi_on_20m_20260207_1050/kpi.json` (`winrate_pct=71.43`, `net_pnl_full<0`)
- AC-3: trades_ledger.jsonl (per-trade 비용 breakdown) 증거 생성
  - Evidence: `logs/evidence/d_alpha_2_obi_on_20m_20260207_1050/trades_ledger.jsonl`
- AC-4: engine_report.json의 net_pnl/exec_cost_total이 net_pnl_full 기준으로 동기화
  - Evidence: `logs/evidence/d_alpha_2_obi_on_20m_20260207_1050/engine_report.json`
- AC-5: tests/conftest.py 치팅(deselect) 제거 + 허용 스킵은 allowlist+증거로만 처리
  - Evidence: Gate 결과에서 deselect 기반 회피 제거 후 재실행
- AC-6: test_d87_3_duration_guard.py subprocess 기반 hang 제거 (unit test 전환)
  - Evidence: Gate 3단 PASS
- AC-7: OBI ON 20m survey 재실행 (TIME_REACHED + winrate 50~80% 목표)
  - Evidence: `logs/evidence/d_alpha_2_obi_on_20m_20260207_1050/`
  - Result: `watch_summary.json` stop_reason=TIME_REACHED, `kpi.json` winrate_pct=71.43
- AC-8: Gate 3단 PASS (Doctor/Fast/Regression) + DocOps PASS
  - Evidence:
    - DocOps: `python scripts/check_ssot_docs.py` (ExitCode=0)
    - Doctor: `logs/evidence/20260207_104629_gate_doctor_503f5c1/`
    - Fast: `logs/evidence/20260207_104630_gate_fast_503f5c1/`
    - Regression: `logs/evidence/20260207_104633_gate_regression_503f5c1/`

## 구현 내용 (Implementation)

- RunWatcher
  - survey_mode에서도 always-on 가드(승률 상한/마찰 0/기관총 매매/승률100 kill-switch)가 동작하도록 순서 정리
  - 승률 100% kill-switch는 1분 지속 조건 추가
- Step0 Bootstrap 중앙화
  - `infra/docker-compose.yml`을 기준으로 Redis/Postgres 부팅 및 healthcheck
  - 스키마(v2_orders/v2_fills/v2_trades) 확인 및 필요 시 적용
  - env (`POSTGRES_CONNECTION_STRING`, `REDIS_URL`)를 세션에 주입
- engine_report db_integrity
  - `ledger_writer.get_counts()`가 반환하는 `v2_orders/v2_fills/v2_trades` 형태를 합산하여 inserts_ok를 계산

## Gate 결과 (Doctor/Fast/Regression)

- Doctor PASS: `logs/evidence/20260207_104629_gate_doctor_503f5c1/`
- Fast PASS: `logs/evidence/20260207_104630_gate_fast_503f5c1/`
- Regression PASS: `logs/evidence/20260207_104633_gate_regression_503f5c1/`

## Reality Check (20m OBI ON Survey)

- Evidence: `logs/evidence/d_alpha_2_obi_on_20m_20260207_1050/`
- stop_reason: TIME_REACHED
- winrate_pct: 71.43
- net_pnl_full: -7.77
- exec_cost_total: 9.52 (fees+slippage+latency_cost+partial)

## Step0 Bootstrap Evidence

- `logs/evidence/STEP0_BOOTSTRAP_RUNTIME_ENV_20260207_105039/`

## 다음 단계 (Next Steps)

- D_ALPHA-2: OBI Filter & Ranking의 AC-1~3(동적 임계치/랭킹 아티팩트/시장구조 분해) 진행
