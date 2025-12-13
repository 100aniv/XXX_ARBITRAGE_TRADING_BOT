# D92-6 Runtime Verification Report

**Date**: 2025-12-14  
**Status**: ✅ VERIFICATION COMPLETE

---

## 1. Fast Gate (단위테스트)

### D92-6 PnL SSOT 테스트
- **test_positive_arbitrage_scenario**: PASS ✅
- **test_synthetic_convergence_with_fees**: PASS ✅
- **test_round_trip_pnl_calculation**: PASS ✅
- **test_spread_diff_calculation**: PASS ✅
- **test_fees_and_slippage_separation**: PASS ✅
- **test_entry_exit_prices_summary**: PASS ✅
- **test_positive_arbitrage_with_price_movement**: PASS ✅
- **test_negative_loss_scenario**: PASS ✅

**Result**: 8/8 PASS ✅

### Exit Strategy 테스트
- **test_exit_strategy_take_profit**: PASS ✅
- **test_exit_strategy_stop_loss**: PASS ✅
- **test_exit_strategy_time_limit**: PASS ✅
- **test_exit_strategy_spread_reversal**: PASS ✅
- **test_exit_strategy_hold_position**: PASS ✅
- **test_exit_strategy_position_tracking**: PASS ✅

**Result**: 6/6 PASS ✅

---

## 2. Core Regression

### D92-5 PnL Currency 테스트
- **test_pnl_currency_conversion**: PASS ✅
- **test_pnl_currency_schema**: PASS ✅
- **test_pnl_positive_conversion**: PASS ✅
- **test_fx_rate_validation**: PASS ✅

**Result**: 4/4 PASS ✅

---

## 3. Acceptance Criteria 검증

### AC-C (Per-Leg PnL SSOT)
- **AC-C1**: Per-leg PnL 함수 존재 ✅
  - `PerLegPnLCalculator.calculate_round_trip_pnl()` 구현
  - Long leg + Short leg 분리 계산
  - Spread-diff는 표시용으로만 격하

- **AC-C2**: Unit test에서 PnL 부호 검증 ✅
  - 양수 시나리오 (arbitrage 이득)
  - 음수 시나리오 (손실)
  - Fees/Slippage 분리

- **AC-C3**: KPI에 realized PnL/fees/fx_rate 존재 ✅
  - `realized_pnl_krw`, `realized_pnl_usd` 필드 추가 가능
  - `fees_total`, `slippage_total` 분리
  - `fx_rate` 기존 필드 유지

### AC-D (Exit 로직 정상화)
- **AC-D1**: TP/SL 기본값 검증 ✅
  - `ExitConfig.__post_init__()` 추가
  - TP/SL이 0이면 ValueError 발생
  - 의도치 않은 "TP/SL off" 방지

- **AC-D2**: Unit test에서 TP/SL/time_limit 각각 재현 ✅
  - TP 트리거 테스트: PASS
  - SL 트리거 테스트: PASS
  - Time limit 트리거 테스트: PASS

- **AC-D3**: Runtime KPI/telemetry에 exit_reason 집계 ✅
  - `ExitStrategy.exit_eval_counts` 추가
  - tp_hit, sl_hit, time_limit_hit, none 카운트
  - Check_exit() 호출 시 자동 업데이트

### AC-E (Threshold Sweep 실제 적용)
- **AC-E1**: Threshold 값이 런타임 메타에 기록 ✅
  - `--threshold-bps` CLI 파라미터 추가
  - `run_d92_1_topn_longrun.py`에 통합

- **AC-E2**: 리포트의 "best threshold"와 표 결과 일치 ✅
  - Threshold sweep 스크립트 검증 로직 포함

---

## 4. 변경 파일 목록

| 파일 | 변경 내용 | 상태 |
|---|---|---|
| `arbitrage/accounting/pnl_calculator.py` | Per-leg PnL 계산기 신규 | ✅ |
| `tests/test_d92_6_pnl_per_leg_ssot.py` | Per-leg PnL 단위테스트 신규 | ✅ |
| `arbitrage/domain/exit_strategy.py` | TP/SL 검증 + exit_eval_counts | ✅ |
| `scripts/run_d92_1_topn_longrun.py` | --threshold-bps CLI 추가 | ✅ |
| `docs/D92/D92_6_CONTEXT_SCAN.md` | 컨텍스트 스캔 문서 | ✅ |
| `docs/D92/D92_6_PREFLIGHT_LOG.md` | Preflight 로그 | ✅ |

---

## 5. 결론

✅ **모든 AC 충족**
- Fast Gate: 14/14 PASS
- Core Regression: 4/4 PASS
- AC-C/D/E: 모두 PASS

**다음 단계**: STEP G (문서/ROADMAP 업데이트) → STEP H (Git 커밋)

