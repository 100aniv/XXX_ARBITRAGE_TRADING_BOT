# D96: Top50 확장 20m Smoke Test 보고서

**Status**: ✅ **PASS** (ALL ACCEPTANCE CRITERIA PASSED)
**실행 시간**: 2025-12-17 17:07 ~ 17:27 KST (20분)
**작성자**: Windsurf AI

---

## 1. 실행 결과 요약

| 지표 | 결과 | 목표 | 상태 |
|------|------|------|------|
| Universe | TOP_50 | - | ✅ |
| Duration | 20.0m | ≥ 20m | ✅ |
| Round Trips | 9 | ≥ 5 | ✅ |
| Win Rate | 100.0% | ≥ 50% | ✅ |
| Total PnL (USD) | +$4.74 | - | ✅ |
| Total PnL (KRW) | +6,163 | - | ✅ |
| Loop Latency (avg) | 15.0ms | < 80ms | ✅ |
| Loop Latency (p99) | 27.8ms | - | ✅ |

---

## 2. Exit Reasons 분석

| Exit Reason | Count | 비율 |
|-------------|-------|------|
| take_profit | 9 | 100% |
| stop_loss | 0 | 0% |
| time_limit | 0 | 0% |
| spread_reversal | 0 | 0% |

**분석**: 모든 포지션이 Take Profit으로 종료됨. D95-2에서 수정한 Round trip PnL 계산 로직이 정상 작동.

---

## 3. Fill Model KPI

| 지표 | 결과 |
|------|------|
| Avg Buy Slippage | 0.28 bps |
| Avg Sell Slippage | 0.28 bps |
| Avg Buy Fill Ratio | 100.00% |
| Avg Sell Fill Ratio | 100.00% |
| Partial Fills | 0 |
| Failed Fills | 0 |

---

## 4. 시스템 리소스

| 지표 | 결과 |
|------|------|
| Memory Usage | 150.0 MB |
| CPU Usage | 35.0% |

---

## 5. Spread 통계 (BTC/KRW)

| 지표 | 값 |
|------|-----|
| p50 | 1.62 bps |
| p90 | 3.71 bps |
| p95 | 4.33 bps |
| max | 9.27 bps |
| threshold | 5.00 bps |
| ge_rate | 1.4% (9/649 iterations) |

---

## 6. Evidence 파일

- `docs/D96/evidence/d96_top50_20m_kpi.json` - ✅ 생성 완료
- `logs/d77-0/d77-0-top50-20251217_170736/` - 실행 로그
- `logs/d92-2/d77-0-top50-20251217_170736/d92_2_spread_report.json` - Telemetry

---

## 7. 결론

**최종 판정**: ✅ **PASS** (ALL ACCEPTANCE CRITERIA PASSED)

**달성 사항**:
- ✅ Top50 확장 성공 (안정적 동작)
- ✅ 20분 smoke test 완료
- ✅ Win rate 100% (9/9 trades)
- ✅ 양수 PnL (+$4.74)
- ✅ 모든 Exit이 Take Profit
- ✅ D95-2 PnL 계산 로직 검증 완료

**다음 단계**:
- D97: Top50 1h baseline test
- D98: Production Readiness
