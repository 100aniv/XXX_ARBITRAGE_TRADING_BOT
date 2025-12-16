# D95: 1h PAPER 성능 Gate 목표 정의

**상태**: ❌ **FAIL** (성능 기준 미달, 재실행 필요)  
**작성일**: 2025-12-16 19:41 KST  
**작성자**: Windsurf AI

---

## 1. 목표 (Objective)

D95는 **성능 Gate**로, D94(안정성 Gate) PASS를 전제로 **최소 성능 기준**을 검증한다.

### D94 vs D95 분리 (SSOT)
- **D94 (안정성)**: Crash-free, Error-free, Duration 충족 → **PASS** ✅
- **D95 (성능)**: Win rate, TP/SL 발생, 최소 기대값 → 본 Gate에서 검증

### 핵심 목표
1. **TP/SL 발생 증명**: time_limit only 탈출
2. **Win rate 최소선 통과**: 0% 탈출 (>= 20%)
3. **성능 판정 자동화**: KPI → decision JSON (PASS/FAIL)

---

## 2. 범위 (Scope)

### In Scope
- 1시간 PAPER 모드 성능 검증
- 성능 지표 측정 (win_rate, TP/SL, PnL, slippage)
- 자동 판정 로직 (d95_decision_only.py)
- Evidence 3종 생성 (KPI, decision, log tail)
- Fail-fast: 10분 내 round_trips==0 → 중단/분석/재실행

### Out of Scope
- 안정성 검증 (D94에서 완료)
- Multi-symbol 확장 (D96+)
- Production 배포 (D97+)
- 최적화/튜닝 (D98+)

---

## 3. Decision Policy (SSOT)

### Critical (FAIL 즉시)
- ❌ exit_code != 0
- ❌ ERROR count > 0
- ❌ kill_switch_triggered == true
- ❌ duration < target - 60s

### Semi-Critical (성능 최소선 - PASS 조건)
- ⚠️ **round_trips >= 10** (표본 부족 방지)
- ⚠️ **win_rate >= 20%** (0% 탈출)
- ⚠️ **take_profit_count >= 1** (TP 발생 증명)
- ⚠️ **stop_loss_count >= 1** (SL 발생 증명)
  - 단, SL 설계상 비활성이면 대체 지표 `adverse_move_bps` 필수

### Variable (PASS/FAIL 무관, 보고서 필수)
- ℹ️  total_pnl_usd, pnl_per_trade_usd
- ℹ️  slippage_bps_avg, partial_fills_count
- ℹ️  exit_reason 분포 (time_limit 비중)
- ℹ️  entry_edge_bps_est vs realized_edge_bps (가능 시)

### 판정 로직
```python
if Critical FAIL:
    return FAIL
if Semi-Critical ANY FAIL:
    return FAIL
return PASS
```

---

## 4. Acceptance Criteria

### AC-1: Evidence 생성 ✅
- [x] `docs/D95/evidence/d95_1h_kpi.json` (생성 완료)
- [x] `docs/D95/evidence/d95_decision.json` (decision=FAIL)
- [x] `docs/D95/evidence/d95_log_tail.txt` (300 lines)

### AC-2: Fast Gate 5/5 PASS ✅
- [x] check_docs_layout.py
- [x] check_shadowing_packages.py
- [x] check_required_secrets.py
- [x] compileall
- [x] check_roadmap_sync.py

### AC-3: Core Regression 100% PASS ✅
- [x] D92 SSOT 정의 기준 (44/44 PASS, async 포함)

### AC-4: D95 Gate PASS ❌ (3/4 FAIL)
- [x] round_trips >= 10 (16건)
- [ ] win_rate >= 20% (0%)
- [ ] take_profit_count >= 1 (0건)
- [ ] stop_loss_count >= 1 (0건)

### AC-5: Documentation 완성 ✅
- [x] OBJECTIVE.md (placeholder 0)
- [x] REPORT.md (placeholder 0, FAIL 원인 분석 포함)
- [ ] D_ROADMAP.md (D95 섹션 동기화 대기)

---

## 5. 산출물 (Deliverables)

### Scripts
1. **`scripts/run_d95_performance_paper_gate.py`** (SSOT Runner)
2. **`scripts/d95_decision_only.py`** (KPI → decision 자동 판정)

### Documents
3. **`docs/D95/D95_0_OBJECTIVE.md`** (본 문서)
4. **`docs/D95/D95_1_PERFORMANCE_PAPER_REPORT.md`** (실행 결과)

### Evidence
5. **`docs/D95/evidence/d95_1h_kpi.json`** (KPI 전체)
6. **`docs/D95/evidence/d95_decision.json`** (판정 결과)
7. **`docs/D95/evidence/d95_log_tail.txt`** (로그 tail)

### Roadmap
8. **`D_ROADMAP.md`** (D95 섹션 업데이트)

---

## 6. D94 실패 패턴 분석 및 D95 개선 전략

### D94 결과 (안정성 PASS, 성능 과제)
```json
{
  "round_trips": 8,
  "win_rate": 0.0,
  "exit_reasons": {"TP": 0, "SL": 0, "time_limit": 8},
  "entry_threshold_bps": {"BTC": 4.5}
}
```

### 문제 진단
1. **TP/SL 0건**: Exit 로직이 시장에서 작동하지 않음
2. **Win rate 0%**: 모든 거래가 손실로 종료 (slippage 2.14bps > spread)
3. **BTC threshold 4.5bps**: 실제 시장 spread가 이를 넘지 못함

### D95 개선 전략 (우선순위)
1. **Zone profile 조정**: BTC threshold 4.5bps → 1.5bps (수수료+slippage 기반)
2. **Real selection 활성화**: 스프레드 상위 심볼 선택 (가능 시)
3. **TP/SL 파라미터 조정**: 발생 가능한 범위로 설정

### 최소 Threshold 공식 (SSOT)
```
min_threshold_bps = 1.5 * (fee_a_bps + fee_b_bps + slippage_bps)
                  = 1.5 * (10 + 10 + 10)
                  = 45 bps

현재 BTC 4.5bps는 이 공식보다 10배 낮음 → 오버라이드 허용 (시장 기반)
단, win_rate >= 20% 달성 불가 시 threshold 재검토 필수
```

---

## 7. 리스크 및 한계

### 리스크
- **시장 조건 의존**: 스프레드 부족 시 TP/SL 발생 어려움
- **Threshold 조정 실패**: 너무 낮추면 손실 확대, 너무 높으면 거래 없음
- **Real selection 미구현**: 현재 모의 데이터 사용 시 성능 제약

### 완화 방안
- Fail-fast (10분): 조기 중단 → 원인 분석 → 수정 → 재실행
- Zone profile 재산정: 비용모델 기반 최소선 준수
- Real selection 구현: 스프레드 상위 심볼 우선 선택

---

## 8. Dependencies

- D94: 1h PAPER 안정성 Gate (PASS 완료)
- D92: Fast Gate + Core Regression SSOT
- D93: 재현성 검증 패턴

---

## 9. 다음 단계 (D96+)

1. **D96: Multi-Symbol TopN 확장** (Top50 동시 실행)
2. **D97: Production Readiness** (모니터링/알림/Failover)
3. **D98: 최적화/튜닝** (Bayesian Optimization, Walk-forward)

---

## 10. 업데이트 이력

- 2025-12-16 18:30 KST: D95 목표 정의 초안 작성
