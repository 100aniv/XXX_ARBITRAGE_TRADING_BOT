# D92-4 Threshold 스윕 리포트

**Date**: 2025-12-13 14:04:11

## 1. 10분 게이트 스윕 결과

| Threshold (bps) | Trades | PnL (KRW) | Win Rate | Time Limit % |
|---|---|---|---|---|
| 5.0 | 2 | -795,776 | 0.0% | 50.0% |
| 4.8 | 0 | 0 | 0.0% | 0.0% |
| 4.5 | 1 | 0 | 0.0% | 0.0% |

## 2. 60분 베이스라인 결과

| Threshold (bps) | Trades | PnL (KRW) | Win Rate | Time Limit % |
|---|---|---|---|---|
| 4.5 | 14 | -6,448,760 | 0.0% | 50.0% |
| 5.0 | 6 | -1,874,378 | 0.0% | 50.0% |

## 3. 결론

**최적 Threshold**: 4.5 bps
**근거**: 60분 베이스라인에서 최고 PnL 달성 (-6,448,760 KRW)

### Exit Reason 분포 분석

**Threshold 4.5 bps**:
- take_profit: 0
- stop_loss: 0
- time_limit: 7
- spread_reversal: 0

**Threshold 5.0 bps**:
- take_profit: 0
- stop_loss: 0
- time_limit: 3
- spread_reversal: 0
