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
| partial_fill_penalty > 0 | 거래 로그에서 0 초과 값 확인 | 미기록 | 미검증 |
| friction breakdown | breakdown artifact 존재 | 미기록 | 미검증 |
| 복수 시드/유니버스 | 2회 이상 net_pnl_full 기록 | 미기록 | 미검증 |

## 판정 규칙
- 위 3개 항목이 모두 **검증** 상태일 때만 "Profit Logic = PASS"로 표기한다.
- 하나라도 미검증이면 "Profit Logic = FAIL"로 유지한다.

## 참고 데이터 소스
- `logs/evidence/**/kpi.json`
- `logs/evidence/**/pnl_breakdown.json`
- `logs/evidence/**/edge_decomposition.json`
- `logs/evidence/**/trades_ledger.jsonl`
- `logs/evidence/**/profitability_matrix.json`
