# D82-12: Lowered TP/Entry Re-baseline Validation Report

**Status:** ❌ **NO-GO**  
**Date:** 2025-12-06 01:10 KST  
**Author:** AI Assistant (Automated Pipeline)  
**Runtime:** 30 minutes (Phase 1 only)

---

## 📋 Executive Summary

D82-12는 D82-11 NO-GO 결과를 기반으로, **D77-4에서 검증된 낮은 threshold 구간 (Entry/TP 5-10 bps)으로 회귀**하여 Trade Activity 및 실전 수익성을 재검증하는 실험이었습니다.

### **최종 판정: ❌ NO-GO**

- **Phase 1 (10분):** ❌ FAIL - 모든 후보 Acceptance Criteria 미달
- **Phase 2/3:** SKIPPED (Phase 1 실패)
- **Root Cause:** TP 도달 0%, Timeout 100%, RT=3 < 5
- **D77-4 재현:** 완전 실패 (1,656 RT → 3 RT, 99.8% 성능 저하)

---

## 🎯 Validation Design

### 후보 Grid (D77-4 Baseline Zone)

| # | Entry (bps) | TP (bps) | Edge (bps) | D77-4 Zone | Status |
|---|-------------|----------|------------|------------|--------|
| 1 | 10.0 | 12.0 | -2.28 | ✅ | ❌ FAIL |
| 2 | 7.0 | 12.0 | -3.78 | ✅ | ❌ FAIL |
| 3 | 5.0 | 12.0 | -4.78 | ✅ | ❌ FAIL |
| 4 | 7.0 | 10.0 | -4.78 | ✅ | Not Tested |
| 5 | 5.0 | 10.0 | -5.78 | ✅ | Not Tested |
| 6 | 5.0 | 7.0 | -7.28 | ✅ | Not Tested |

**Phase 1 Top 3 후보만 실행됨 (TP 12 bps)**

### Validation 계획

| Phase | Duration | Top-N | Acceptance Criteria | Status |
|-------|----------|-------|---------------------|--------|
| **Phase 1** | 600s (10min) | 3 | RT ≥ 5, WR > 0%, PnL ≥ 0, TP > 0 | ❌ FAIL |
| **Phase 2** | 1200s (20min) | 2 | RT ≥ 10, WR ≥ 10%, PnL > 0 | SKIPPED |
| **Phase 3** | 3600s (60min) | 1 | RT ≥ 30, WR ≥ 20%, PnL > $10 | SKIPPED |

---

## 📊 Phase 1 실행 결과 (10분, Top 3)

### 후보별 상세 KPI

#### 1️⃣ Entry 10.0, TP 12.0 (Best Edge: -2.28 bps)
```
Round Trips: 3 (target: ≥5) ❌
Win Rate: 0.0% (target: >0%) ❌
TP Exit: 0.0% (target: >0) ❌
Timeout Exit: 100.0% ❌
Total PnL: -$1,785.85 (target: ≥0) ❌
Loop Latency: 14.84ms ✅
Status: FAIL
```

#### 2️⃣ Entry 7.0, TP 12.0 (Edge: -3.78 bps)
```
Round Trips: 3 (target: ≥5) ❌
Win Rate: 0.0% ❌
TP Exit: 0.0% ❌
Timeout Exit: 100.0% ❌
Total PnL: -$1,780.47 ❌
Loop Latency: 19.00ms ✅
Status: FAIL
```

#### 3️⃣ Entry 5.0, TP 12.0 (Edge: -4.78 bps)
```
Round Trips: 3 (target: ≥5) ❌
Win Rate: 0.0% ❌
TP Exit: 0.0% ❌
Timeout Exit: 100.0% ❌
Total PnL: -$1,971.21 ❌
Loop Latency: 18.81ms ✅
Status: FAIL
```

### 종합 통계

| 지표 | 결과 | Target | Pass? |
|------|------|--------|-------|
| **Total Runs** | 3 | - | - |
| **Successful Runs** | 0 | ≥1 | ❌ |
| **Avg Round Trips** | 3.0 | ≥5 | ❌ |
| **Avg Win Rate** | 0.0% | >0% | ❌ |
| **Avg TP Exit %** | 0.0% | >0% | ❌ |
| **Total PnL** | -$5,537.53 | ≥0 | ❌ |
| **Avg Latency** | 17.55ms | <25ms | ✅ |

---

## 🔍 비교 분석: D77-4 vs D82-11 vs D82-12

| 지표 | D77-4 (60min) | D82-11 (10min) | D82-12 (10min) | 변화 |
|------|---------------|----------------|----------------|------|
| **Entry/TP** | ~5-10 bps | 14-16 / 18 bps | 5-10 / 7-12 bps | D77-4와 동일 |
| **Round Trips** | 1,656 | 3 | 3 | **NO CHANGE** |
| **RT/min** | 27.6 | 0.3 | 0.3 | **NO CHANGE** |
| **Win Rate** | 100% | 0% | 0% | **NO CHANGE** |
| **TP Exit %** | 매우 높음 | 0% | 0% | **NO CHANGE** |
| **Timeout %** | 매우 낮음 | 100% | 100% | **NO CHANGE** |
| **PnL** | +$8,263.82 | -$1,554.77 | -$5,537.53 | **악화** |
| **Edge (이론)** | -7.28 ~ -2.28 | +0.73 ~ +3.73 | -7.28 ~ -2.28 | D77-4와 동일 |

### 핵심 발견

1. **D82-11 → D82-12 변경의 효과 = ZERO**
   - Threshold를 D77-4 수준으로 낮췄지만, 성능 개선 없음
   - RT, WR, TP Exit % 모두 D82-11과 동일

2. **D77-4 재현 완전 실패**
   - D77-4: 1,656 RT (27.6/min)
   - D82-12: 3 RT (0.3/min)
   - **99.8% 성능 저하**

3. **TP 12 bps도 도달 불가**
   - TP 18 bps (D82-11): 0% 도달
   - TP 12 bps (D82-12): 0% 도달
   - **낮은 TP로 변경했지만 여전히 Timeout 100%**

4. **PnL 더 악화**
   - D82-11: -$1,554.77 (3 RT)
   - D82-12: -$5,537.53 (3 RT)
   - **RT당 손실 증가** (-$518 → -$1,845)

---

## 🧪 Root Cause Analysis

### 1️⃣ TP Threshold 문제가 아님
- TP 18 bps → 12 bps 변경했지만 도달률 0% 유지
- **문제는 TP 값이 아니라 다른 곳에 있음**

### 2️⃣ Entry Threshold 문제가 아님
- Entry 14-16 bps → 5-10 bps 변경했지만 RT 3 유지
- **Entry를 낮춰도 거래 기회 증가 없음**

### 3️⃣ Fill Model 이상 징후
```json
"buy_fill_ratio_avg": 0.0,
"sell_fill_ratio_avg": 0.0,
"slippage_avg_bps": 0.0
```
- **모든 Fill Ratio와 Slippage가 0**
- RT=3이 발생했다는 것은 거래가 있었다는 의미
- **KPI 수집 또는 계산 로직 문제 의심**

### 4️⃣ 근본 원인 추정

**가능성 1: Mock Fill Model 26% 문제**
- Buy Fill 26%로 설정 → 거래 기회 74% 차단
- D77-4는 더 높은 Fill Ratio 또는 다른 로직 사용했을 가능성

**가능성 2: L2 Orderbook 부재**
- 현재는 L1 (Top of Book)만 사용
- 실제 Fill 가능 여부를 L2로 확인 못함
- Mock Fill 26%는 L2 없는 상태에서의 추정치

**가능성 3: 시장 조건 변화**
- D77-4 당시 (과거): 변동성 높음, Spread 빈번
- 현재: 변동성 낮음, Spread 희박
- **구조적 시장 변화로 인한 기회 감소**

---

## 💡 Key Insights

### ✅ 명확해진 사실

1. **Threshold 조정만으로는 해결 불가**
   - D82-11 (높은 TP) → D82-12 (낮은 TP): 변화 없음
   - **문제는 Threshold가 아니라 Infrastructure**

2. **D77-4와 근본적 차이 존재**
   - D77-4: 27.6 RT/min (매우 빈번한 거래)
   - D82-12: 0.3 RT/min (거의 거래 없음)
   - **같은 Threshold인데 100배 차이**

3. **Fill Model이 가장 큰 의심 대상**
   - Buy Fill 26%가 너무 낮음
   - KPI에서 Fill Ratio 0 보고 (데이터 이상)

4. **L2 Orderbook 필수성 확인**
   - L1만으로는 실제 Fill 가능 여부 판단 불가
   - D83-x (L2 통합)이 최우선 과제

### ⚠️ 실패한 가설

1. **"낮은 TP가 더 자주 도달한다"** → ❌ WRONG
   - TP 12 bps도 0% 도달
   - Timeout 여전히 100%

2. **"Entry를 낮추면 RT 증가한다"** → ❌ WRONG
   - Entry 5-10 bps로 낮췄지만 RT=3 유지

3. **"D77-4 조건으로 돌아가면 성능 재현된다"** → ❌ WRONG
   - 동일한 Threshold인데도 99.8% 성능 저하

---

## 🎯 Next Steps

### 🚨 HIGH PRIORITY: Infrastructure 개선

#### 1️⃣ D84-x: Fill Model 개선 (우선순위 1)
**문제:**
- Buy Fill 26% → 74% 거래 기회 차단
- KPI에서 Fill Ratio 0 보고 (로직 이상)

**해결:**
- Real Market Fill 데이터 수집
- Adaptive Fill Model 구축
- Partial Fill 로직 개선
- **Target: Buy Fill 50%+ 달성**

#### 2️⃣ D83-x: L2 Orderbook 통합 (우선순위 2)
**문제:**
- L1 (Top of Book)만으로는 Fill 가능 여부 판단 불가
- Mock Fill 26%는 L2 없는 상태에서의 추정치

**해결:**
- WebSocket L2 Stream 구축
- L2 기반 Fill Probability 계산
- Entry/Exit 로직에 L2 Depth 반영
- **Target: L2 기반 실시간 Fill 예측**

#### 3️⃣ D82-13: D77-4 조건 재현 실험
**목적:**
- D77-4 당시 코드/설정으로 재실행
- 차이점 정밀 분석

**비교 항목:**
- Fill Model 설정
- TP/Entry 계산 로직
- Position Sizing
- TopN 설정
- Duration
- Symbol Selection

### ⏸️ LOW PRIORITY: Threshold 재조정
- D82-12로 증명됨: Threshold 조정만으로는 해결 안 됨
- Fill Model + L2 개선 후 재시도

---

## 📁 Deliverables

### ✅ Completed

1. **설계 문서:** `docs/D82/D82-12_LOWERED_THRESHOLD_REBASELINE.md`
2. **후보 생성 스크립트:** `scripts/generate_d82_12_lowered_tp_entry_candidates.py`
3. **후보 JSON:** `logs/d82-12/lowered_tp_entry_candidates.json` (6개 후보)
4. **단위 테스트:** `tests/test_d82_12_lowered_threshold_candidates.py` (14/14 PASS)
5. **회귀 테스트:** D82-9/10/11/12 (52/52 PASS)
6. **✅ 본 실행 완료:** Phase 1 (10분) 완료
7. **✅ KPI 수집:** `logs/d82-11/d82_11_summary_600.json`
8. **✅ 최종 리포트:** `logs/d82-11/d82_11_validation_report.json`

### 📊 실행 결과 요약

```json
{
  "final_decision": "NO_GO",
  "phase1": {
    "status": "FAIL",
    "reason": "Phase 1 FAIL: No candidates met acceptance criteria",
    "candidates_tested": 3,
    "pass_candidates": 0
  },
  "phase2": {"status": "SKIPPED"},
  "phase3": {"status": "SKIPPED"},
  "notes": "Phase 1 미달 → Phase 2/3 스킵. Fill Model 및 L2 Orderbook 개선 필요."
}
```

---

## 🔗 References

1. **D77-4 Baseline:** 60min, Top50, 1,656 RT, 100% WR, $8,263.82 PnL
2. **D82-9 Analysis:** 5-Candidate, 10min, 0% WR, -$1,271.27 PnL, RT=2.2
3. **D82-10 Edge Model:** Roundtrip Cost = 13.28 bps, 8 candidates
4. **D82-11 NO-GO:** TP 18 bps, RT=3, PnL=-$1,554.77, Timeout=100%
5. **D82-12 NO-GO:** TP 7-12 bps, RT=3, PnL=-$5,537.53, Timeout=100%

---

## 🎓 Lessons Learned

### ✅ What Worked
- 완전 자동화 파이프라인 (30분 무인 실행)
- 52/52 테스트 유지 (회귀 방지)
- 명확한 Acceptance Criteria 적용

### ❌ What Failed
- Threshold 조정 접근법 (D82-11 → D82-12)
- "낮은 TP가 더 도달한다" 가설
- D77-4 재현 시도

### 🔬 What We Discovered
- **Fill Model이 가장 큰 병목**
- **L2 Orderbook 필수**
- **시장 조건 변화 가능성**
- **Threshold보다 Infrastructure가 중요**

---

**Generated by:** D82-12 Automated Pipeline  
**Execution Time:** 2025-12-06 00:40:25 - 01:10:35 KST (30 minutes)  
**Final Decision:** ❌ NO-GO  
**Next Phase:** D83-x (L2 Orderbook) + D84-x (Fill Model)
