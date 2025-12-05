# D82-12: Lowered TP/Entry Re-baseline (D77-4 Quick Win)

**Status:** 🚧 **IN PROGRESS**  
**Date:** 2025-12-05  
**Author:** AI Assistant (Automated Pipeline)

---

## 📋 Executive Summary

D82-12는 D82-11 NO-GO 결과를 바탕으로, **D77-4에서 검증된 낮은 threshold 구간 (Entry/TP ≈ 5–10 bps)으로 회귀**하여 Trade Activity 및 실전 수익성을 재검증하는 단계입니다.

### 배경

**D82-11 실패 원인:**
- TP 18 bps: 시장 변동성에서 도달 불가능 (TP Exit = 0%, Timeout = 100%)
- Entry 14-16 bps: D77-4 대비 2-3배 높아 진입 기회 감소 (RT = 3 vs 목표 5)
- D82-10 Edge 이론 (+2.73~+3.73 bps)은 양수지만, 실전 재현 불가

**D77-4 Baseline (검증된 성능):**
- Entry/TP: ~5-10 bps 구간
- 60분 PAPER: 1,656 RT, 100% WR, $8,263.82 PnL
- RT/min: 27.6 (10분 기준)

### D82-12 목표

1. **Trade Activity 회복:** RT/min을 D77-4 수준 (2+ RT/min)으로 복원
2. **TP 도달 가능성 검증:** TP Exit % > Timeout %
3. **실전 PnL 검증:** PnL > 0, WR > 0%
4. **이론 vs 실전 Gap 분석:** D82-10 비용 모델 (13.28 bps roundtrip cost) 관점에서 이 구간은 Edge < 0일 수 있으나, D77-4 실적이 이를 반증

---

## 🎯 Parameter Grid

### Threshold 설정

| Entry (bps) | TP (bps) | Valid? | Note |
|-------------|----------|--------|------|
| 5.0 | 7.0 | ✅ | TP > Entry |
| 5.0 | 10.0 | ✅ | TP > Entry |
| 5.0 | 12.0 | ✅ | TP > Entry |
| 7.0 | 7.0 | ❌ | TP = Entry (invalid) |
| 7.0 | 10.0 | ✅ | TP > Entry |
| 7.0 | 12.0 | ✅ | TP > Entry |
| 10.0 | 7.0 | ❌ | TP < Entry (invalid) |
| 10.0 | 10.0 | ❌ | TP = Entry (invalid) |
| 10.0 | 12.0 | ✅ | TP > Entry |

**유효 조합:** 6개 (TP > Entry 조건 만족)

### D82-10 vs D82-12 비교

| 항목 | D82-10 (NO-GO) | D82-12 (Re-baseline) | 변화 |
|------|----------------|----------------------|------|
| **Entry 범위** | 10-18 bps | 5-10 bps | -5 ~ -8 bps |
| **TP 범위** | 14-18 bps | 7-12 bps | -7 ~ -6 bps |
| **이론 Edge** | +0.73 ~ +3.73 bps | ? (재계산 필요) | - |
| **D77-4 검증** | ❌ (고 threshold) | ✅ (저 threshold) | - |

---

## 🔬 이론 vs 실전 관점 분리

### D82-10 비용 모델 (이론)

**D82-9 실측 비용:**
- Slippage (편도): 2.14 bps
- Fee (Total): 9.0 bps (Upbit 5 + Binance 4)
- **Roundtrip Cost:** 2.14 × 2 + 9.0 = **13.28 bps**

**D82-12 Threshold에 대한 이론 Edge:**

```python
# Example: Entry 5, TP 7
gross_spread = (5 + 7) / 2 = 6.0 bps
edge = gross_spread - roundtrip_cost
     = 6.0 - 13.28
     = -7.28 bps (구조적 손실)
```

**대부분의 D82-12 조합이 이론 Edge < 0.**

---

### D77-4 실전 성능 (실증)

**D77-4 PAPER 결과 (Top50, 60분):**
- Round Trips: 1,656
- Win Rate: 100%
- PnL: $8,263.82
- TP Exit %: 매우 높음 (시간 제한 청산 거의 없음)
- Loop Latency: < 25ms

**D77-4는 Entry/TP ~5-10 bps 구간에서 실행되었고, 매우 높은 RT/WR/PnL을 달성.**

---

### D82-12의 실험적 의의

**질문:**
- D82-10 이론 모델에 따르면 D82-12 조합은 Edge < 0이므로 "구조적 손실"이어야 한다.
- 그런데 D77-4는 왜 성공했는가?

**가능한 가설:**
1. **Mock Fill Model 과조정:** D82-9~11의 Buy Fill 26.15%는 과도하게 비관적. 실제 시장에서는 더 높을 수 있음.
2. **Spread Volatility:** 낮은 threshold는 더 자주 트리거되고, 순간적인 spread 확대 시 수익 실현 가능성 증가.
3. **TP 도달 가능성:** 낮은 TP (7-12 bps)는 높은 TP (18 bps)보다 시장에서 훨씬 자주 발생 → TP Exit % 증가 → 강제 timeout 손실 감소.
4. **Cost Model 재검토 필요:** D82-9 실측 비용 (13.28 bps)이 실제보다 과대 추정되었을 가능성.

**D82-12의 목적:**
- **이론 Edge 최적화가 아니라, 실전 Trade Activity + PnL 재현성 검증.**
- D82-10 이론 모델의 한계를 인정하고, D77-4 실증 데이터를 우선시.

---

## 📊 Validation Plan

### Phase 구성 (D82-11 파이프라인 재사용)

| Phase | Duration | Top-N | Acceptance Criteria |
|-------|----------|-------|---------------------|
| **Phase 1: 10min Smoke** | 600s | 전체 (6개) | RT ≥ 5, WR > 0%, PnL ≥ 0, TP Exits > 0 (any) |
| **Phase 2: 20min Validation** | 1200s | Top 2 | RT ≥ 10, WR ≥ 10%, PnL > 0, TP Exits ≥ 1 (all) |
| **Phase 3: 60min Confirmation** | 3600s | Top 1 | RT ≥ 30, WR ≥ 20%, PnL > $10, TP % ≥ Timeout %, Latency P99 < 25ms |

### Acceptance Criteria (D82-11과 동일)

**Phase 1:**
- Per candidate: `RT >= 5`, `PnL >= 0`, `WR > 0%`, `TP Exits > 0`
- Overall: 최소 1개 후보 만족
- Failure: `NO-GO` → Phase 2/3 스킵

**Phase 2:**
- Per candidate: `RT >= 10`, `PnL > 0`, `WR >= 10%`, `TP Exits >= 1`
- Overall: 최소 1개 후보 만족
- Failure: `CONDITIONAL_NO-GO` → Phase 3 스킵

**Phase 3:**
- Single candidate: `RT >= 30`, `PnL > $10`, `WR >= 20%`, `TP % >= Timeout %`, `Latency P99 < 25ms`
- Success: `GO` → D83-x (L2 Orderbook) 또는 D84-x (Fill Model) 진행

---

## 🎯 Expected Outcomes

### Optimistic Scenario (GO)

**기대 결과:**
- **RT/min:** 2-3 (D77-4 수준 회복, D82-11 대비 10배 증가)
- **TP Exit %:** 30-50% (D82-11의 0% 대비 대폭 개선)
- **Timeout Exit %:** 50-70% (D82-11의 100% 대비 감소)
- **Win Rate:** 20-40% (D82-11의 0% 대비 회복)
- **PnL:** 양수 (D82-11의 -$1,555 대비 반전)

**다음 단계:**
- D82-12 Best Candidate를 Baseline으로 확정
- D83-x: L2 Orderbook 통합 (정밀한 Entry/Exit 판단)
- D84-x: Fill Model 개선 (Mock → Real)

---

### Pessimistic Scenario (NO-GO)

**가능한 결과:**
- **RT/min:** 여전히 낮음 (< 1)
- **TP Exit %:** 여전히 0% 또는 매우 낮음
- **PnL:** 음수 지속

**원인 가능성:**
- D77-4와 현재 시장 환경의 근본적 차이 (변동성 감소, 유동성 변화 등)
- Mock Fill Model이 D77-4보다 훨씬 비관적 (26% vs 100%)
- D82-10 비용 모델이 정확하고, 저 threshold 구간도 실제로는 손실 구간

**다음 단계:**
- D83-x (L2 Orderbook)를 우선 진행하여 정밀한 스프레드 예측
- D84-x (Fill Model 개선)로 Buy Fill 26% 문제 해결
- 또는 D77-4 PAPER 재현 실험 (동일 조건으로 재실행하여 차이점 분석)

---

## 📁 Key Deliverables

### 1. 후보 생성
- **Script:** `scripts/generate_d82_12_lowered_tp_entry_candidates.py`
- **Output:** `logs/d82-12/lowered_tp_entry_candidates.json`
- **Format:** D82-10과 동일한 스키마 (metadata + candidates 배열)

### 2. Validation 실행
- **Runner:** `scripts/run_d82_11_validation_pipeline.py` (재사용)
- **Command:** `--candidates-json logs/d82-12/lowered_tp_entry_candidates.json`
- **Output:** `logs/d82-11/d82_11_validation_report.json` (D82-12 후보로 실행)

### 3. 문서 및 리포트
- **Design:** `docs/D82/D82-12_LOWERED_THRESHOLD_REBASELINE.md` (이 문서)
- **Validation Report:** `docs/D82/D82-12_VALIDATION_REPORT.md` (실행 후 생성)
- **D_ROADMAP:** D82-12 섹션 추가

### 4. 테스트
- **Unit Test:** `tests/test_d82_12_lowered_threshold_candidates.py`
- **Regression:** D82-9/10/11 테스트 통과 (38/38 PASS 유지)

---

## 🔗 References

1. **D77-4 Baseline:** 60min, Top50, 1,656 RT, 100% WR, $8,263.82 PnL
2. **D82-9 Analysis:** 5-Candidate, 10min, 0% WR, -$1,271.27 PnL, RT=2.2
3. **D82-10 Edge Model:** Roundtrip Cost = 13.28 bps, 8 candidates (Edge ≥ +0.73 bps)
4. **D82-11 NO-GO:** TP 18 bps 도달 0%, Entry 14-16 bps, RT=3, PnL=-$1,554.77

---

## ✅ Success Criteria

D82-12는 다음 조건 중 하나를 만족하면 **GO**로 판정:

1. **Phase 3 PASS:** Best candidate가 Phase 3 Acceptance Criteria 모두 만족
2. **Phase 2 PASS + High RT:** Phase 2 통과 + RT ≥ 20 (통계적 유의성)
3. **Phase 1 Strong PASS:** Phase 1에서 3개 이상 후보가 모든 조건 만족 + RT ≥ 10

Otherwise: **NO-GO** or **CONDITIONAL_NO-GO**

---

**Generated by:** D82-12 Automated Pipeline  
**Design Date:** 2025-12-05
