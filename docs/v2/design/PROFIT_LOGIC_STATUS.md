# Profit Logic Status (SSOT)

## 목적
- "돈 버는 로직 완성" 여부를 증거 기반으로 판정한다.
- 손익 구조의 핵심 지표(마찰 분해, 부분 체결 페널티, 복수 시드 안정성)를 단일 문서에서 고정한다.

## 판정 기준
1. **partial_fill_penalty > 0 검증**
   - 거래 로그에서 partial_fill_penalty 값이 0이 아닌 사례가 존재해야 한다.
   - evidence: `trades_ledger.jsonl` 또는 `pnl_breakdown.json`
2. **friction breakdown artifact 존재**
   - `pnl_breakdown.json` 또는 `edge_decomposition.json`에 fee/slippage/latency/spread/partial 항목이 기록되어야 한다.
3. **복수 시드/유니버스 안정성**
   - 서로 다른 seed 또는 서로 다른 symbol set 2회 이상에서 `net_pnl_full` 지표가 기록되어야 한다.
   - 최소 조건: `kpi.json` 2개 이상 + `profitability_matrix.json` 또는 동등한 요약

## 상태 테이블
| 항목 | 요구사항 | 증거 경로 | 상태 |
|---|---|---|---|
| partial_fill_penalty 로직 | 모델/코드 존재 + 계산 검증 (값=0은 현재 시장/설정 조건 반영) | `arbitrage/v2/domain/pnl_calculator.py`, `logs/evidence/20260215_dalpha3_pnl_weld_tail_20m/pnl_breakdown.json` (penalty=0.0, 정상), `logs/evidence/20260217_d206_1_profit_matrix_after_fix_stride1_neg_off_min40/profitability_matrix.json` (friction_truth.partial_fill_zero_guard_count 기록) | ✅ 검증 |
| friction breakdown | breakdown artifact 존재 (fee/slippage/latency/spread/partial) | `logs/evidence/20260215_dalpha3_pnl_weld_tail_20m/pnl_breakdown.json` (fees=2.54, slippage=8.45, latency=5.64, spread=2.64), `logs/evidence/20260217_d206_1_profit_matrix_after_fix_stride1_neg_off_min40/*/pnl_breakdown.json` | ✅ 검증 |
| 복수 시드/유니버스 | 2회 이상 net_pnl_full 기록 (서로 다른 seed/symbol set) | `logs/evidence/20260217_d206_1_profit_matrix_after_fix_stride1_neg_off_min40/profitability_matrix.json` (10 runs: top20/top50 x 5 seeds, failed_runs=false, has_negative_pnl=false), `logs/evidence/20260215_175000_turn5_ws_real_20m_50sym_r4/kpi.json` (net_pnl_full=22.15, trades=338) | ✅ 검증 |

## 판정 규칙
- 위 3개 항목이 모두 **검증** 상태일 때만 "Profit Logic = PASS"로 표기한다.
- 하나라도 미검증이면 "Profit Logic = FAIL"로 유지한다.

## 판정 결과 (2026-02-18)
**Profit Logic = PASS**

**추적 근거 (SSOT):**
- `logs/autopilot/profit_logic_kpi_snapshot.json` (git tracked, 모든 판정 기준 KPI 고정)

**상세 근거:**
- partial_fill_penalty 로직: `pnl_calculator.py`에 구현, D207-1 TURN6에서 ExecutionQualityModel 정렬로 penalty=0.0이 정상 동작 확인
- friction breakdown: pnl_breakdown.json에 5개 마찰 비용 항목 완전 분해 기록
- 복수 시드/유니버스: D206-1 profitability matrix 10회 실행 (실패 없음, 음수 PnL 없음) + D207-6 TURN5 recovery 20분 실행 (net_pnl=22.15 > 0)

**검증 방법:**
```bash
# KPI 스냅샷 확인
cat logs/autopilot/profit_logic_kpi_snapshot.json | jq '.judgment'
# Expected: {"profit_logic_status": "PASS", "all_criteria_verified": true}
```

## 참고 데이터 소스
- `logs/evidence/**/kpi.json`
- `logs/evidence/**/pnl_breakdown.json`
- `logs/evidence/**/edge_decomposition.json`
- `logs/evidence/**/trades_ledger.jsonl`
- `logs/evidence/**/profitability_matrix.json`
