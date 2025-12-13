# D92-6 Context Scan: PnL/Exit/Threshold 근본 수리

**Date**: 2025-12-14  
**Objective**: 구조적 PnL 오류, Exit 로직 부재, Threshold 스윕 미적용 문제 파악

---

## 1. 발견된 핵심 파일 (10개 내외)

### PnL / Accounting / Realized / Fees / FX_Rate

| 파일 | 위치 | 역할 | 현황 |
|---|---|---|---|
| **currency.py** | `arbitrage/common/currency.py` | Money 클래스, FX 환산 로직 | 통화 변환 기본 구조 있음 |
| **fx_converter.py** | `arbitrage/cross_exchange/fx_converter.py` | KRW↔USDT 환율 변환 | 캐싱 + fallback 구현 |
| **executor.py** | `arbitrage/cross_exchange/executor.py` | Entry/Exit 주문 실행 + PnL 계산 | PnL 필드 있으나 spread-diff 기반 (문제) |
| **arbitrage_backtest.py** | `arbitrage/arbitrage_backtest.py` | 백테스트 PnL 누적 | realized_pnl 변수 사용 |
| **live_runner.py** | `arbitrage/live_runner.py` | 라이브 거래 실행 + PnL 누적 | pnl_usd 필드 있음 (부호 불명확) |

### Exit / Take_Profit / Stop_Loss / Hysteresis / Time_Limit

| 파일 | 위치 | 역할 | 현황 |
|---|---|---|---|
| **exit_strategy.py** | `arbitrage/domain/exit_strategy.py` | TP/SL/Time/Spread 조건 | 기본 구조 있음 (hysteresis 없음) |
| **settings.py** | `arbitrage/config/settings.py` | TopNEntryExitConfig | tp_spread_bps, sl_spread_bps 정의 (기본값 5/50 bps) |
| **run_d77_0_topn_arbitrage_paper.py** | `scripts/run_d77_0_topn_arbitrage_paper.py` | Exit 평가 + 이유 기록 | exit_reason 집계 있음 (time_limit 도배 문제) |

### KPI / Telemetry / Trades / Run_ID / Stage_ID / Logs

| 파일 | 위치 | 역할 | 현황 |
|---|---|---|---|
| **run_paths.py** | `arbitrage/common/run_paths.py` | SSOT 경로 해석 | logs/{stage_id}/{run_id}/ 구조 확정 |
| **trade_logger.py** | `arbitrage/logging/trade_logger.py` | Trade-level JSONL 로깅 | TradeLogEntry 스키마 정의 (PnL 필드 있음) |

---

## 2. 문제 정의

### 문제 A: PnL 계산 (spread-diff 기반 → per-leg 기반으로 변경 필요)

**현재 상태**:
- `executor.py`: `pnl_krw = decision.exit_pnl_krw` (spread-diff 기반으로 추정)
- `live_runner.py`: `trade.pnl_usd` 누적 (부호 정의 불명확)
- `arbitrage_backtest.py`: `realized_pnl += trade.pnl_usd` (누적만 함)

**문제**:
- Spread 수렴 시나리오에서 PnL 부호가 뒤집힐 수 있음
- Per-leg fill price 기반 정산 없음
- Fees/Slippage 분리 불명확

**해결책**:
- Per-leg realized PnL 함수 신규 작성
- Long leg: (sell_exit - buy_entry) * qty - fees - slippage
- Short leg: (sell_entry - buy_exit) * qty - fees - slippage
- KPI에 `realized_pnl_krw`, `realized_pnl_usd`, `fees_total_*` 필드 추가

---

### 문제 B: Exit 로직 (time_limit 중심 → TP/SL 우선으로 정상화)

**현재 상태**:
- `exit_strategy.py`: TP/SL/Time/Spread 조건 정의 있음
- `settings.py`: `exit_tp_spread_bps=5.0`, `exit_sl_spread_bps=50.0` (기본값)
- `run_d77_0_topn_arbitrage_paper.py`: Exit 평가 + exit_reason 기록

**문제**:
- TP/SL 기본값이 0이면 "꺼짐" 상태 (의도치 않은 동작)
- time_limit이 최후 수단이 아니라 도배됨 (D92-4 결과: 50% time_limit)
- Hysteresis 없음 (spread 진동 시 반복 exit)

**해결책**:
- Config에서 TP/SL이 0이면 에러 발생 (검증)
- Exit 평가 카운트 추가: `exit_eval_counts: {tp_hit, sl_hit, time_limit_hit, none}`
- Hysteresis 로직 추가 (선택사항)

---

### 문제 C: Threshold Sweep (라벨만 바꿈 → 실제 파라미터 적용)

**현재 상태**:
- `run_d92_4_threshold_sweep.py`: stage_id만 바꿈 (threshold 미적용)
- `run_d92_1_topn_longrun.py`: CLI에 `--threshold-bps` 파라미터 없음
- `settings.py`: TopNEntryExitConfig에 threshold 필드 없음

**문제**:
- 스윕이 placebo (같은 설정으로 반복 실행)
- 리포트의 "best threshold" 선택 로직이 표와 불일치

**해결책**:
- Option-1 (권장): `run_d92_1_topn_longrun.py`에 `--threshold-bps` CLI 추가
- 스윕 리포트 "best threshold" 로직 수정 (PnL 기준 정렬)

---

## 3. 구현 순서 (STEP C → D → E)

1. **STEP C**: per-leg PnL SSOT 확정 + 단위테스트
2. **STEP D**: Exit 로직 정상화 (TP/SL/hysteresis)
3. **STEP E**: Threshold Sweep 실제 적용

---

## 4. 관련 테스트 파일

- `tests/test_d77_0_topn_arbitrage_paper.py`: Exit Strategy 테스트 (TP/SL/Time/Spread)
- `tests/test_d92_5_pnl_currency.py`: PnL 통화 변환 테스트
- `tests/test_d92_1_topn_longrun.py`: TopN 장시간 실행 테스트

---

## 5. SSOT 경로 구조 (확정)

```
logs/{stage_id}/{run_id}/
├── {run_id}_kpi_summary.json       (KPI + 메타)
├── {run_id}_trades.jsonl           (Trade-level 로그)
├── {run_id}_config_snapshot.yaml   (Config)
├── {run_id}_runtime_meta.json      (Runtime 메타)
└── trades/                         (TradeLogger 출력)
```

---

## 6. 다음 단계

- STEP B: 환경 Preflight (프로세스/Docker/Redis/DB 클린업)
- STEP C: per-leg PnL SSOT 확정
