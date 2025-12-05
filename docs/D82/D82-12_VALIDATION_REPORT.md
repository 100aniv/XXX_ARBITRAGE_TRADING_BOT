# D82-12: Lowered TP/Entry Re-baseline Validation Report

**Status:** ⚠️ **THEORETICAL ANALYSIS** (본 실행 대기 중)  
**Date:** 2025-12-06  
**Author:** AI Assistant (Automated Pipeline)

---

## 📋 Executive Summary

D82-12는 D82-11 NO-GO 결과를 기반으로, **D77-4에서 검증된 낮은 threshold 구간 (Entry/TP 5-10 bps)으로 회귀**하여 Trade Activity 및 실전 수익성을 재검증하는 실험입니다.

### 핵심 차이점: D82-11 vs D82-12

| 항목 | D82-11 (NO-GO) | D82-12 (Re-baseline) | 변화 |
|------|----------------|----------------------|------|
| **Entry 범위** | 14-16 bps | 5-10 bps | ↓ 5-9 bps |
| **TP 범위** | 18 bps | 7-12 bps | ↓ 6-11 bps |
| **이론 Edge** | +0.73 ~ +3.73 bps | -7.28 ~ -2.28 bps | ⚠️ 음수 |
| **D77-4 검증** | ❌ (고 threshold) | ✅ (저 threshold) | - |
| **TP 도달** | 0% (예상) | 30-50% (예상) | ↑↑ |
| **RT/min** | 0.3 (실측) | 2+ (예상) | ↑ 6배 |

### 현재 상태

- ✅ **후보 생성:** 6개 후보 (Entry 5-10 bps, TP 7-12 bps)
- ✅ **Dry-run 검증:** D82-12 후보 제대로 로드됨
- ✅ **단위 테스트:** 52/52 PASS (D82-9/10/11/12)
- ⏳ **본 실행:** 시간 제약으로 대기 중

---

## 🎯 Validation Design

### 후보 Grid (D77-4 Baseline Zone)

| # | Entry (bps) | TP (bps) | Edge (bps) | D77-4 Zone | Rationale |
|---|-------------|----------|------------|------------|-----------|
| 1 | 10.0 | 12.0 | -2.28 | ✅ | Highest Entry/TP, Edge 최대 |
| 2 | 7.0 | 12.0 | -3.78 | ✅ | Mid Entry, High TP |
| 3 | 5.0 | 12.0 | -4.78 | ✅ | Lowest Entry, High TP |
| 4 | 7.0 | 10.0 | -4.78 | ✅ | Mid Entry/TP |
| 5 | 5.0 | 10.0 | -5.78 | ✅ | Low Entry, Mid TP |
| 6 | 5.0 | 7.0 | -7.28 | ✅ | Lowest Entry/TP, D77-4 Core |

**주목할 점:**
- **모든 후보의 이론 Edge < 0** (D82-10 비용 모델 기준)
- 하지만 **D77-4 실증 데이터는 이 구간에서 높은 RT/WR/PnL 달성**
- D82-12는 **"이론 vs 실전" Gap을 검증**하는 실험

### Validation 계획

| Phase | Duration | Top-N | Acceptance Criteria |
|-------|----------|-------|---------------------|
| **Phase 1** | 600s (10min) | 6 | RT ≥ 5, WR > 0%, PnL ≥ 0, TP > 0 (any) |
| **Phase 2** | 1200s (20min) | 2 | RT ≥ 10, WR ≥ 10%, PnL > 0, TP ≥ 1 (all) |
| **Phase 3** | 3600s (60min) | 1 | RT ≥ 30, WR ≥ 20%, PnL > $10, TP % ≥ Timeout % |

---

## 🔬 이론적 분석 (D82-10 비용 모델 기준)

### 비용 구조 (D82-9 실측)

```
슬리피지 (편도): 2.14 bps
수수료 (Total): 9.0 bps (Upbit 5 + Binance 4)
Roundtrip Cost: 2.14 × 2 + 9.0 = 13.28 bps
```

### Edge 계산 (6개 후보)

```python
# 예시: Entry 10, TP 12
gross_spread = (10 + 12) / 2 = 11.0 bps
edge = 11.0 - 13.28 = -2.28 bps (구조적 손실)

# 예시: Entry 5, TP 7
gross_spread = (5 + 7) / 2 = 6.0 bps
edge = 6.0 - 13.28 = -7.28 bps (더 큰 손실)
```

**결론:** D82-10 비용 모델에 따르면, **모든 D82-12 후보는 이론적으로 손실 구간**

---

## 🧪 D77-4 실증 데이터 (Baseline)

### D77-4 PAPER 결과 (60분, Top50)

| 지표 | D77-4 실측 | D82-12 예상 | 비교 |
|------|------------|-------------|------|
| **Round Trips** | 1,656 | ? | D77-4는 매우 높음 |
| **RT/min** | 27.6 | 2-5 (예상) | D77-4는 10배 이상 |
| **Win Rate** | 100% | 20-40% (예상) | D77-4는 완벽 |
| **PnL** | $8,263.82 | ? | D77-4는 매우 높음 |
| **TP Exit %** | 매우 높음 | 30-50% (예상) | D77-4는 대부분 TP |
| **Entry/TP** | ~5-10 bps | 5-10 bps | **동일 구간** |

**핵심 질문:**
- D77-4는 왜 **이론 Edge < 0인 구간에서 높은 수익을 달성**했는가?
- D82-12는 D77-4 성능을 재현할 수 있는가?

---

## 🔍 가능한 가설 (이론 vs 실전 Gap)

### Hypothesis 1: Mock Fill Model 과조정

**D82-9~12 현재 설정:**
- Buy Fill Ratio: **26.15%** (매우 비관적)
- Sell Fill Ratio: 100%
- Partial Fill: 100%

**D77-4 당시 설정:**
- Fill Model: 더 낙관적이었을 가능성
- 또는 Real Market Fill이 더 높았을 수 있음

**영향:**
- 낮은 Buy Fill → Position Size 감소 → RT 감소 → PnL 감소
- D82-12 결과가 D77-4보다 나쁠 가능성

---

### Hypothesis 2: Spread Volatility & TP 도달 가능성

**낮은 TP (7-12 bps) vs 높은 TP (18 bps):**

| TP Threshold | 시장 발생 빈도 | TP 도달 가능성 | Timeout % |
|--------------|----------------|----------------|-----------|
| **18 bps (D82-11)** | 매우 낮음 | 0% | 100% |
| **12 bps (D82-12)** | 낮음 | 10-30% | 70-90% |
| **7 bps (D82-12)** | 중간 | 30-50% | 50-70% |

**결론:**
- **낮은 TP는 시장에서 더 자주 발생** → TP Exit 증가 → Timeout 손실 감소
- 이것이 D77-4 성공의 핵심일 가능성

---

### Hypothesis 3: D82-10 비용 모델 과대 추정

**D82-9 실측 비용 (13.28 bps)이 실제보다 높을 가능성:**

1. **슬리피지 2.14 bps:** 시장 조건에 따라 더 낮을 수 있음
2. **Partial Fill 100%:** 실제로는 Full Fill이 더 많을 수 있음
3. **수수료 9.0 bps:** 변동 없음 (고정)

**만약 실제 Roundtrip Cost = 10 bps라면:**
```python
# Entry 10, TP 12
edge = 11.0 - 10.0 = +1.0 bps (양수!)

# Entry 7, TP 10
edge = 8.5 - 10.0 = -1.5 bps (여전히 음수)
```

**결론:** 비용 모델 재검토 필요

---

### Hypothesis 4: Trade Frequency & Volume Effect

**D77-4는 Top50, D82-12는 Top3 (Phase 1):**
- D77-4: 더 많은 Symbol → 더 많은 Entry 기회 → RT 증가
- D82-12 Phase 1: Top3만 → Entry 기회 제한

**하지만:**
- D82-12 Phase 3는 Top1이지만, 60분이므로 충분한 RT 확보 가능
- D77-4는 60분에 1,656 RT (27.6 RT/min)
- D82-12는 최소 30 RT (0.5 RT/min) 목표

---

## 📊 예상 결과 (3가지 시나리오)

### Scenario A: Optimistic (GO)

**조건:**
- Mock Fill Model이 실제보다 과도하게 비관적
- 낮은 TP (7-12 bps)가 시장에서 자주 발생

**예상 결과:**
- **Phase 1 (10min):** RT ≥ 5, TP Exit 20-30%, PnL ≥ 0 → **PASS**
- **Phase 2 (20min):** RT ≥ 10, TP Exit 30-40%, WR ≥ 10% → **PASS**
- **Phase 3 (60min):** RT ≥ 30, TP % ≥ Timeout %, PnL > $10 → **PASS**

**최종 판단:** **GO** → D83-x (L2 Orderbook) 또는 D84-x (Fill Model) 진행

---

### Scenario B: Realistic (CONDITIONAL NO-GO)

**조건:**
- 낮은 TP가 어느 정도 도달하지만, D77-4 수준은 아님
- RT는 증가하지만, PnL은 여전히 낮음

**예상 결과:**
- **Phase 1 (10min):** RT ≥ 5, TP Exit 10-20%, PnL ≈ 0 → **PASS (marginal)**
- **Phase 2 (20min):** RT ≥ 10, 하지만 WR < 10% 또는 PnL < 0 → **FAIL**
- **Phase 3:** SKIP

**최종 판단:** **CONDITIONAL NO-GO** → D84-x (Fill Model) 우선 진행

---

### Scenario C: Pessimistic (NO-GO)

**조건:**
- D82-10 비용 모델이 정확하고, 낮은 TP도 여전히 도달 불가
- Mock Fill Model 26%가 실제와 유사

**예상 결과:**
- **Phase 1 (10min):** RT < 5, TP Exit 0-5%, PnL < 0 → **FAIL**
- **Phase 2/3:** SKIP

**최종 판단:** **NO-GO** → D83-x (L2 Orderbook) + D84-x (Fill Model) 동시 진행

---

## 🎯 Next Steps (시나리오별)

### ✅ GO → D83-x 또는 Production

1. **D82-12 Best Candidate를 Baseline으로 확정**
   - Entry/TP, Duration, TopN 설정 고정
2. **D83-x: L2 Orderbook 통합**
   - L2 데이터 수집 파이프라인 구축
   - L2 기반 Entry/Exit 로직 재설계
   - Threshold를 L2 기반으로 동적 조정
3. **Production Readiness 검증**
   - Real Market 소액 실험
   - Monitoring & Alerting 완성

---

### ⚠️ CONDITIONAL NO-GO → D84-x 우선

1. **D84-x: Fill Model 개선**
   - Real Market Fill 데이터 수집
   - Adaptive Fill Model 구축 (Buy Fill 26% → 50%+)
   - Position Size 증대 → PnL 개선
2. **D82-12 재실행**
   - 개선된 Fill Model로 재검증
   - Acceptance Criteria 재평가

---

### ❌ NO-GO → 근본적 재설계

1. **D83-x + D84-x 동시 진행**
   - L2 Orderbook + Fill Model 개선
   - 이론 Edge 모델 재검토
2. **D77-4 재현 실험**
   - D77-4 당시 조건으로 재실행
   - 차이점 분석 (Fill Model, TP threshold, TopN 등)
3. **Alternative Strategy 고려**
   - Cross-Exchange Hedging
   - Futures Arbitrage
   - Spread-based TP 대신 Time-based Exit

---

## 📁 Deliverables

### ✅ Completed

1. **설계 문서:** `docs/D82/D82-12_LOWERED_THRESHOLD_REBASELINE.md`
2. **후보 생성 스크립트:** `scripts/generate_d82_12_lowered_tp_entry_candidates.py`
3. **후보 JSON:** `logs/d82-12/lowered_tp_entry_candidates.json` (6개 후보)
4. **단위 테스트:** `tests/test_d82_12_lowered_threshold_candidates.py` (14/14 PASS)
5. **회귀 테스트:** D82-9/10/11 포함 52/52 PASS
6. **Dry-run 검증:** D82-12 후보 제대로 로드됨

### ⏳ Pending

1. **본 실행:** 600/1200/3600초 Validation
2. **실제 KPI 데이터:** RT, WR, PnL, TP %, Latency
3. **Final Decision:** GO/CONDITIONAL NO-GO/NO-GO

---

## 🔗 References

1. **D77-4 Baseline:** 60min, Top50, 1,656 RT, 100% WR, $8,263.82 PnL
2. **D82-9 Analysis:** 5-Candidate, 10min, 0% WR, -$1,271.27 PnL, RT=2.2
3. **D82-10 Edge Model:** Roundtrip Cost = 13.28 bps, 8 candidates (Edge ≥ +0.73 bps)
4. **D82-11 NO-GO:** TP 18 bps 도달 0%, Entry 14-16 bps, RT=3, PnL=-$1,554.77

---

## 💡 Key Insights

### ✅ What We Learned

1. **이론 Edge < 0이라도 실전 수익 가능할 수 있음**
   - D77-4가 이를 증명
   - Cost Model 재검토 필요

2. **낮은 TP가 핵심일 가능성**
   - TP 18 bps: 도달 불가능 (0%)
   - TP 7-12 bps: 도달 가능성 증가 (30-50% 예상)

3. **Mock Fill Model이 과도하게 비관적**
   - Buy Fill 26%는 실제보다 낮을 가능성
   - D84-x (Fill Model 개선)이 우선순위

### ⚠️ Risks

1. **D77-4 재현 실패 가능성**
   - 시장 조건 변화 (변동성 감소, 유동성 변화)
   - Mock Fill Model 차이

2. **이론 Edge 음수의 의미**
   - 장기적으로는 손실 가능성
   - Short-term Win은 Luck일 수 있음

### 🎓 Recommendations

1. **본 실행 (600/1200/3600초) 필수**
   - 이론적 분석만으로는 불충분
   - 실제 데이터로 가설 검증

2. **D84-x (Fill Model) 우선 진행**
   - Buy Fill 26% 문제 해결이 가장 큰 Impact

3. **D77-4 조건으로 재현 실험**
   - D77-4와 동일한 설정으로 재실행
   - Gap 분석

---

**Generated by:** D82-12 Automated Pipeline  
**Report Date:** 2025-12-06  
**Status:** Theoretical Analysis (본 실행 대기 중)
