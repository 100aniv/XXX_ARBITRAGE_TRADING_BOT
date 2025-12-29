# ⚠️ DEPRECATED - 이 파일은 더 이상 사용되지 않습니다

**Status:** DEPRECATED (2025-12-29)  
**Reason:** ROADMAP SSOT 단일화 - D95 내용은 D_ROADMAP.md에 통합됨  
**SSOT:** `/D_ROADMAP.md`

---

## D95: 1h PAPER 성능 Gate

**Status**: ❌ **FAIL** (2025-12-16 19:41 KST - 성능 기준 미달, 재실행 필요)

**Objective**: 1시간 PAPER 모드 성능 검증 (win_rate, TP/SL, 최소 기대값)

**AS-IS (Before D95)**:
- D94에서 안정성만 검증 (win_rate/PnL은 INFO)
- TP/SL 발생 검증 없음
- 성능 자동 판정 로직 없음

**TOBE (After D95)**:
- ✅ Fast Gate 5/5 PASS
- ✅ Core Regression 44/44 PASS
- ✅ BTC threshold 1.5bps 적용 → Round trips 2배 증가
- ✅ Evidence 3종 생성 (KPI, decision, log tail)
- ❌ Win rate 0% (목표 20%)
- ❌ TP/SL 0건 (목표 각 1건)
- ❌ Exit 로직 미작동 (time_limit 100%)

**Deliverables**:
1. ✅ Runner Script: `scripts/run_d95_performance_paper_gate.py`
2. ✅ Decision Script: `scripts/d95_decision_only.py`
3. ✅ Evidence: `docs/D95/evidence/` (3 files)
4. ✅ Report: `docs/D95/D95_1_PERFORMANCE_PAPER_REPORT.md` (FAIL 원인 분석 포함)
5. ✅ Objective: `docs/D95/D95_0_OBJECTIVE.md`
6. ✅ Zone Profile: `config/arbitrage/zone_profiles_v2.yaml` (BTC 1.5bps)

**Acceptance Criteria**:
- ✅ Fast Gate 5/5 PASS
- ✅ Core Regression 44/44 PASS
- ✅ round_trips >= 10 (16건)
- ❌ win_rate >= 20% (0%)
- ❌ take_profit >= 1 (0건)
- ❌ stop_loss >= 1 (0건)

**Dependencies**:
- D94 (안정성 Gate PASS)
- D92 (Fast Gate + Core Regression SSOT)

**Risks (Identified)**:
- ❌ Paper mode Exit 조건 미발생 (D64 패턴 재발)
- ❌ TP/SL 파라미터가 시장 변동성보다 너무 넓음
- ❌ Entry edge 부족 (Slippage 4.28bps vs Spread 4.90bps)

**Execution Log**:
- 2025-12-16 18:00-18:30: D95 준비 (Fast Gate 5/5, Core Regression 44/44)
- 2025-12-16 18:30-18:35: Zone profile 조정 (BTC 4.5→1.5bps)
- 2025-12-16 18:35-19:35: 1h Baseline 실행 (RT=16, win_rate=0%, TP/SL=0)
- 2025-12-16 19:35-19:41: Decision 판정 (FAIL) + 문서화

**Result**: ❌ **FAIL** (Semi-Critical 3/4 미달)
- **Critical (안정성)**: exit_code=0 ✅, ERROR=0 ✅, duration OK ✅, kill_switch=false ✅
- **Semi-Critical (성능)**: round_trips=16 ✅, win_rate=0% ❌, TP=0 ❌, SL=0 ❌
- **Variable (INFO)**: PnL=-$0.74, slippage=2.14bps, time_limit=100%

**Root Cause Analysis**:
1. **Paper mode 한계**: Exit 조건 (spread < 0) 발생 안 함 (D64 패턴 재발)
2. **TP/SL 파라미터**: 실제 시장 변동성보다 너무 넓음
3. **Entry edge 부족**: Slippage (4.28bps) vs Spread (4.90bps) = 0.62bps만 남음

**해결 방안 (D95 재실행 계획)**:
1. **Paper mode 개선**: Exit 조건 발생 로직 추가 (D64 솔루션 재적용)
   - `arbitrage/live_runner.py` 수정: `_inject_paper_prices()` 함수에 Exit spread 주입
   - Position open time 추적 → 10초 후 negative spread 생성
2. **TP/SL 파라미터 조정**: 더 좁은 범위로 설정
   - TP: 50bps → 10bps
   - SL: 30bps → 5bps
3. **Threshold 재조정**: BTC 1.5bps → 2.0bps (edge 확보)
4. **Real selection 활성화** (선택): 스프레드 상위 심볼 우선 선택

**다음 단계**:
- **D95-2**: Paper mode Exit 로직 수정 + TP/SL 파라미터 조정 + 재실행
- **D96**: Multi-Symbol TopN 확장 (D95 PASS 후)
- **D97**: Production Readiness (D96 PASS 후)

**Evidence Files**:
- `docs/D95/evidence/d95_1h_kpi.json` (3.6KB)
- `docs/D95/evidence/d95_decision.json` (1.2KB, decision=FAIL)
- `docs/D95/evidence/d95_log_tail.txt` (300 lines)

**Git Branch**: `rescue/d95_performance_gate_ssot`
