# D95: 1h PAPER 성능 Gate 실행 보고서

**상태**: ❌ **FAIL** (성능 기준 미달)  
**작성일**: 2025-12-16 19:41 KST (완료)  
**작성자**: Windsurf AI

---

## 1. 목표 (Objective)

D95는 성능 Gate로, 최소 성능 기준 (win_rate >= 20%, TP/SL 발생, round_trips >= 10)을 검증한다.

---

## 2. Execution Plan

### Step 1: Fast Gate 5종
```powershell
python scripts/check_docs_layout.py
python scripts/check_shadowing_packages.py
python scripts/check_required_secrets.py
python -m compileall .
python scripts/check_roadmap_sync.py
```

### Step 2: Core Regression (D92 SSOT)
```powershell
python -m pytest tests/test_d27_monitoring.py tests/test_d82_0_runner_executor_integration.py tests/test_d82_2_hybrid_mode.py tests/test_d92_1_fix_zone_profile_integration.py tests/test_d92_7_3_zone_profile_ssot.py --import-mode=importlib -v --tb=short
```

### Step 3: D95 1h Baseline
```powershell
python scripts/run_d95_performance_paper_gate.py --duration-sec 3600 --log-dir logs/d95 --evidence-dir docs/D95/evidence
```

### Step 4: Decision-only 판정
```powershell
python scripts/d95_decision_only.py --kpi docs/D95/evidence/d95_1h_kpi.json --out docs/D95/evidence/d95_decision.json
```

---

## 3. D95 Decision Policy (SSOT)

### Critical (FAIL 즉시)
- exit_code != 0
- ERROR count > 0
- kill_switch_triggered == true
- duration < target - 60s

### Semi-Critical (성능 최소선)
- round_trips >= 10
- win_rate >= 20%
- take_profit_count >= 1
- stop_loss_count >= 1

### Variable (PASS/FAIL 무관)
- total_pnl_usd
- slippage_bps_avg
- exit_reason 분포

---

## 4. 실행 결과 (Execution Results)

### Fast Gate 5종
```
✅ check_docs_layout.py - PASS
✅ check_shadowing_packages.py - PASS
✅ check_required_secrets.py - PASS
✅ compileall - PASS
✅ check_roadmap_sync.py - PASS

결과: 5/5 PASS
```

### Core Regression
```
pytest tests/test_d27_monitoring.py tests/test_d82_0_runner_executor_integration.py tests/test_d82_2_hybrid_mode.py tests/test_d92_1_fix_zone_profile_integration.py tests/test_d92_7_3_zone_profile_ssot.py --import-mode=importlib -v --tb=short

결과: 44/44 PASS (D92 SSOT 기준 100%)
```

### D95 1h Baseline
**실행 시간**: 2025-12-16 18:35:31 ~ 19:35:32 (60.01분)  
**판정**: ❌ **FAIL** (Semi-Critical 3개 미달)

**KPI 요약**:
```json
{
  "session_id": "d77-0-top20-20251216_183531",
  "duration_minutes": 60.01,
  "round_trips_completed": 16,
  "win_rate_pct": 0.0,
  "total_pnl_usd": -0.74,
  "exit_reasons": {
    "take_profit": 0,
    "stop_loss": 0,
    "time_limit": 16
  },
  "avg_buy_slippage_bps": 2.14,
  "avg_sell_slippage_bps": 2.14,
  "zone_profiles_loaded": {
    "BTC": {"threshold_bps": 1.5}
  }
}
```

**판정 결과**:
```json
{
  "decision": "FAIL",
  "reasons": [
    "✅ exit_code=0 (Critical: PASS)",
    "✅ duration=3600.8s >= 3540s (Critical: PASS)",
    "✅ ERROR count=0 (Critical: PASS)",
    "✅ round_trips=16 >= 10 (Semi-Critical: PASS)",
    "❌ win_rate=0.0% < 20% (Semi-Critical: FAIL)",
    "❌ take_profit=0 < 1 (Semi-Critical: FAIL)",
    "❌ stop_loss=0 < 1 (Semi-Critical: FAIL)"
  ],
  "tolerances": {
    "round_trips_min": 10,
    "win_rate_min": 20.0,
    "take_profit_min": 1,
    "stop_loss_min": 1
  }
}
```

**로그 tail (주요 부분)**:
```
2025-12-16 19:34:52 [D82-1] Exit: BTC/KRW @ spread=4.90 bps, reason=TIME_LIMIT
2025-12-16 19:35:32 [D92-3] ACTUAL DURATION: 60.01 minutes (3600.8 seconds)
2025-12-16 19:35:32 Round Trips: 16
2025-12-16 19:35:32 Total PnL (USD): $-0.74
2025-12-16 19:35:32 Exit Reasons: time_limit=16, take_profit=0, stop_loss=0
2025-12-16 19:35:32 [PASS] Round trips: 16 >= 5
```

---

## 5. Evidence 파일 (증거)

### 생성된 파일
- `docs/D95/evidence/d95_1h_kpi.json` - ✅ 생성 완료 (3.6KB)
- `docs/D95/evidence/d95_decision.json` - ✅ 생성 완료 (1.2KB)
- `docs/D95/evidence/d95_log_tail.txt` - ✅ 생성 완료 (300 lines)

### GitHub Raw URL
```
[Push 후 업데이트 예정]
```

---

## 6. 분석 (Analysis)

### 성능 평가 (FAIL)
**Critical 항목**: ✅ 전부 PASS (안정성 확보)
- exit_code=0
- duration=60.01분
- ERROR count=0
- kill_switch=false

**Semi-Critical 항목**: ❌ 3/4 FAIL (성능 기준 미달)
- ✅ round_trips=16 >= 10
- ❌ win_rate=0% < 20%
- ❌ take_profit=0 < 1
- ❌ stop_loss=0 < 1

### TP/SL 발생 분석
**문제**: Exit 로직이 시장에서 작동하지 않음
- **TP/SL 0건**: Exit reason이 100% time_limit (16/16)
- **원인 1**: Paper mode에서 Exit 조건 (spread < 0) 발생 안 함
- **원인 2**: TP/SL 파라미터가 실제 시장 변동성보다 너무 넓음
- **원인 3**: Paper mode의 가격 주입 로직이 Entry만 생성 (D64 패턴 재발)

### Win Rate 분석
**문제**: 모든 거래가 손실로 종료
- **Win rate 0%**: 16 round trips 전부 손실
- **PnL -$0.74**: 평균 -$0.046/trade
- **원인**: Slippage (2.14bps) > Spread (4.90bps) - Entry threshold (1.5bps)
  - Entry spread 4.90bps
  - Slippage 양방향 2.14bps * 2 = 4.28bps
  - 실제 edge = 4.90 - 4.28 = 0.62bps (매우 작음)
  - Time limit으로 종료 시 spread 변동으로 손실 발생

### BTC Threshold 조정 효과
**변경**: 4.5bps → 1.5bps
- **효과**: Round trips 8 → 16 (2배 증가) ✅
- **부작용**: Entry edge 감소로 win rate 저하 (0% 유지)

---

## 7. 결론 (Conclusion)

**최종 판정**: ❌ **FAIL** (Semi-Critical 3개 미달)

**달성 사항**:
- ✅ Fast Gate 5/5 PASS
- ✅ Core Regression 44/44 PASS
- ✅ BTC threshold 1.5bps 적용 → Round trips 2배 증가
- ✅ 안정성 (Critical) 전부 PASS
- ✅ Evidence 3종 생성 완료

**미달 사항**:
- ❌ Win rate 0% (목표 20%)
- ❌ TP/SL 0건 (목표 각 1건)
- ❌ Exit 로직 미작동 (time_limit 100%)

**근본 원인**:
1. **Paper mode 한계**: Exit 조건 (spread < 0) 발생 안 함 (D64 패턴 재발)
2. **TP/SL 파라미터**: 실제 시장 변동성보다 너무 넓음
3. **Entry edge 부족**: Slippage (4.28bps) vs Spread (4.90bps) = 0.62bps만 남음

**해결 방안 (D95 재실행)**:
1. **Paper mode 개선**: Exit 조건 발생 로직 추가 (D64 솔루션 재적용)
2. **TP/SL 파라미터 조정**: 더 좁은 범위로 설정 (예: TP=10bps, SL=5bps)
3. **Real selection 활성화**: 스프레드 상위 심볼 우선 선택
4. **Threshold 재조정**: BTC 1.5bps → 2.0bps (edge 확보)

**다음 단계**:
- **D95 재실행**: Paper mode Exit 로직 수정 + TP/SL 파라미터 조정
- **D96**: Multi-Symbol TopN 확장 (D95 PASS 후)
- **D97**: Production Readiness (D96 PASS 후)

---

## 참고 (References)

- D95 목표: `docs/D95/D95_0_OBJECTIVE.md`
- D94 안정성 Gate: `docs/D94/D94_1_LONGRUN_PAPER_REPORT.md`
- Core Regression: `docs/D92/D92_CORE_REGRESSION_DEFINITION.md`
- PAPER Runner: `scripts/run_d95_performance_paper_gate.py`
