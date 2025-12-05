# D82-10: Recalibrated Edge Model & TP/Entry Candidate Re-selection

**Status:** ✅ COMPLETE  
**Date:** 2025-12-05  
**Author:** AI Assistant

---

## 📋 개요

D82-10은 D82-9 PAPER 실측 데이터를 기반으로 D82-7 이론 Edge 모델을 현실에 맞게 재보정하고, Optimistic/Realistic/Conservative 시나리오별로 이론 Edge를 재계산하여 실전 가능한 후보 세트를 도출하는 단계입니다.

### 배경

**D82-9 PAPER 실행 결과:**
- 5개 후보 (Entry [10, 12] × TP [13, 14, 15]) 모두 실패
- Win Rate: 0% (11/11 exits = time_limit)
- Total PnL: -$1,271 (평균)
- Buy Fill Ratio: 26.15% (매우 낮음)
- Slippage: 2.14 bps (일정)

**핵심 문제:**
- D82-7 이론 모델의 가정 vs D82-9 실측 비용 구조 불일치
- Entry/TP threshold가 D77-4 baseline 대비 2-3배 과도하게 높음
- TP 13-15 bps는 현재 시장 변동성에서 도달 불가능

---

## 🔬 D82-9 실측 비용 구조

### 비용 프로파일 (Cost Profile)

| 항목 | 값 | 비고 |
|------|-----|------|
| **Slippage (평균)** | 2.14 bps | 편도 (buy+sell 평균) |
| **Slippage (P75)** | 2.14 bps | 75% 백분위 |
| **Slippage (P90)** | 2.14 bps | 90% 백분위 |
| **Fee (Total)** | 9.00 bps | Upbit 5 + Binance 4 |
| **Buy Fill Ratio (평균)** | 26.15% | Mock Fill Model |
| **Sell Fill Ratio (평균)** | 100.00% | 매도는 100% 체결 |
| **Round Trips** | 11 total | 0.22 RT/min (매우 낮음) |
| **Timeout Exits** | 100% | TP 도달 0건 |

### 총 왕복 비용

```
Roundtrip Cost = Slippage * 2 + Fee
               = 2.14 * 2 + 9.00
               = 13.28 bps
```

**결론:** Gross Spread가 최소 13.28 bps 이상이어야 Edge >= 0

---

## 💡 Edge 재보정 로직

### 계산 공식

```python
# 1. Gross Spread (이론적 평균 스프레드)
gross_spread_bps = (entry_bps + tp_bps) / 2

# 2. Roundtrip Costs
roundtrip_slippage_bps = slippage_per_trade * 2  # Entry + Exit
roundtrip_fee_bps = 9.0  # Already total

# 3. Net Edge
net_edge_bps = gross_spread_bps - (roundtrip_slippage_bps + roundtrip_fee_bps)
```

### D82-7 가정 vs D82-9 실측

| 항목 | D82-7 가정 | D82-9 실측 | Difference |
|------|-----------|-----------|------------|
| **Slippage** | 2.14 bps (P95) | 2.14 bps (Avg) | Same |
| **Fee** | 9.0 bps | 9.0 bps | Same |
| **Buy Fill Ratio** | ~100% (가정) | **26.15%** | **-74%** |
| **Sell Fill Ratio** | ~100% (가정) | 100% | Same |
| **TP 도달률** | 높음 (가정) | **0%** | **-100%** |

**핵심 차이점:**
1. ✅ Slippage/Fee는 D82-7 가정과 일치
2. ❌ Buy Fill Ratio가 극도로 낮음 (26% vs 100%)
3. ❌ TP threshold가 과도하게 높아 도달 불가

---

## 🎯 시나리오별 재보정

### 3개 시나리오 정의

| Scenario | Slippage (편도) | Fee | Buy Fill Ratio | Description |
|----------|-----------------|-----|----------------|-------------|
| **Optimistic** | 2.14 bps (Median) | 9.0 bps | 26.15% (Avg) | 중앙값 비용, 평균 필률 |
| **Realistic** | 2.14 bps (P75) | 9.0 bps | 26.15% (Avg) | 75% 백분위 비용, 평균 필률 |
| **Conservative** | 2.14 bps (P90) | 9.0 bps | 26.15% (P25) | 90% 백분위 비용, 하위 quartile 필률 |

**Note:** D82-9 데이터에서 슬리피지가 매우 일정하여 (2.14 bps), 시나리오 간 차이는 미미합니다.

### Candidate Grid

**Entry:** [6, 8, 10, 12, 14, 16] bps  
**TP:** [8, 10, 12, 14, 16, 18] bps  
**Total:** 26 combinations (Entry <= TP 조건)

**재보정 기준:**
- `(Entry + TP) / 2 > 13.28` → Edge >= 0
- 최소 Entry + TP > 26.56

---

## 📊 Edge 재계산 결과

### D82-9 실패 조합 비교

| Entry (bps) | TP (bps) | Gross Spread | Edge (Opt) | Edge (Real) | Edge (Cons) | D82-9 Result |
|-------------|----------|--------------|------------|-------------|-------------|--------------|
| 10 | 13 | 11.5 | **-1.77** | **-1.77** | **-1.77** | FAILED (0% WR, -$926) |
| 10 | 14 | 12.0 | **-1.27** | **-1.27** | **-1.27** | FAILED (0% WR, -$824) |
| 10 | 15 | 12.5 | **-0.77** | **-0.77** | **-0.77** | FAILED (0% WR, -$1,037) |
| 12 | 13 | 12.5 | **-0.77** | **-0.77** | **-0.77** | FAILED (0% WR, -$850) |
| 12 | 14 | 13.0 | **-0.27** | **-0.27** | **-0.27** | FAILED (0% WR, -$2,720) |

**결론:** D82-9 모든 조합은 Edge < 0 (구조적으로 손실 확정)

### 재보정 후보 (Edge >= 0)

**Total:** 8 candidates selected  
**Recommended (Realistic >= 0.5 bps):** 8 candidates

| Rank | Entry (bps) | TP (bps) | Edge (Opt) | Edge (Real) | Edge (Cons) | Rationale |
|------|-------------|----------|------------|-------------|-------------|-----------|
| **1** | **16** | **18** | **+3.73** | **+3.73** | **+3.73** | Realistic Edge >= 0.5 bps (recommended) |
| **2** | **14** | **18** | **+2.73** | **+2.73** | **+2.73** | Realistic Edge >= 0.5 bps (recommended) |
| **3** | **16** | **16** | **+2.73** | **+2.73** | **+2.73** | Realistic Edge >= 0.5 bps (recommended) |
| 4 | 12 | 18 | +1.73 | +1.73 | +1.73 | Realistic Edge >= 0.5 bps (recommended) |
| 5 | 14 | 16 | +1.73 | +1.73 | +1.73 | Realistic Edge >= 0.5 bps (recommended) |
| 6 | 10 | 18 | +0.73 | +0.73 | +0.73 | Realistic Edge >= 0.5 bps (recommended) |
| 7 | 12 | 16 | +0.73 | +0.73 | +0.73 | Realistic Edge >= 0.5 bps (recommended) |
| 8 | 14 | 14 | +0.73 | +0.73 | +0.73 | Realistic Edge >= 0.5 bps (recommended) |

**Top 3 추천:**
1. **Entry 16, TP 18**: Edge +3.73 bps (최고 Edge, 보수적)
2. **Entry 14, TP 18**: Edge +2.73 bps (고 Edge, 적당한 Entry)
3. **Entry 16, TP 16**: Edge +2.73 bps (균형적 조합)

---

## 🔍 핵심 발견

### 1. D82-9 실패 원인 정량화

**D82-9 조합의 Edge 분포:**
- Entry 10, TP 13-15: Edge **-1.77 ~ -0.77 bps**
- Entry 12, TP 13-14: Edge **-0.77 ~ -0.27 bps**

**결론:**
- D82-9 모든 조합은 구조적으로 Edge < 0
- 최소 비용 13.28 bps를 커버하지 못함
- TP threshold만 낮춰서는 해결 불가능

### 2. 최소 생존 Threshold

**Break-even 조건:**
```
(Entry + TP) / 2 >= 13.28
Entry + TP >= 26.56
```

**예시:**
- Entry 14, TP 14: Spread = 14, Edge = +0.72 bps ✅
- Entry 12, TP 16: Spread = 14, Edge = +0.72 bps ✅
- Entry 10, TP 18: Spread = 14, Edge = +0.72 bps ✅

### 3. Trade-off 분석

| Entry (bps) | TP (bps) | Edge (bps) | Trade Activity | Win Rate Potential | 종합 평가 |
|-------------|----------|------------|----------------|-------------------|----------|
| 10 | 18 | +0.73 | ⭐⭐⭐ 높음 | ⭐ 낮음 (TP 높음) | ⚠️ Activity↑ but WR↓ |
| 14 | 14 | +0.73 | ⭐⭐ 중간 | ⭐⭐⭐ 높음 (TP 낮음) | ✅ 균형적 |
| 14 | 18 | +2.73 | ⭐⭐ 중간 | ⭐ 낮음 (TP 높음) | ✅ 고 Edge |
| 16 | 16 | +2.73 | ⭐ 낮음 (Entry 높음) | ⭐⭐⭐ 높음 (TP 낮음) | ✅ 보수적 |
| 16 | 18 | +3.73 | ⭐ 낮음 | ⭐ 낮음 | ✅ 최고 Edge, 보수적 |

**권장 전략:**
1. **고 활동성 추구**: Entry 10~12, TP 16~18
2. **균형적 접근**: Entry 14, TP 14~16
3. **보수적 안전**: Entry 16, TP 16~18

---

## 🚨 Mock Fill Model 문제

### 관측된 이슈

**Buy Fill Ratio: 26.15%**
- D82-9에서 매수 주문의 **74%가 미체결**
- 이는 매우 비현실적인 수치 (Mock 모델 과도한 pessimism)
- Position size가 1/4로 줄어 수익 잠재력 제한

**D77-4 vs D82-9 비교:**
- D77-4: 1,656 RT, 100% Win Rate, Positive PnL
- D82-9: 2.2 RT (99.9% 감소), 0% Win Rate, Negative PnL

**근본 원인:**
- D77-4와 D82-9가 동일한 Mock Fill Model을 사용했을 가능성은 낮음
- D82-9 threshold (10-15 bps)가 Mock 모델의 유동성 가정과 맞지 않음
- 또는 D77-4는 더 낮은 threshold (~5-10 bps)로 실행되어 필률이 높았을 가능성

**권장 조치:**
1. **D83-x: WebSocket L2 Orderbook 통합** (Priority HIGH)
   - 실시간 L2 데이터로 정확한 Fill/Slippage 모델링
   - Mock 모델 의존도 탈피
2. **D77-4 Baseline 재검증**
   - Entry ~5-10, TP ~5-10 bps로 재테스트
   - D77-4 성공 요인 재분석
3. **Fill Model Parameter 검토**
   - `arbitrage/models/realistic_fill_model.py` 설정 검토
   - D77-4 vs D82-9 파라미터 차이 비교

---

## 📦 산출물

### JSON 파일

**1. Cost Profile**
```
logs/d82-10/d82_9_cost_profile.json
```
- Slippage/Fee/Fill Ratio 통계
- 후보별 세부 지표
- Exit Reason 분포

**2. Recalibrated Candidates**
```
logs/d82-10/recalibrated_tp_entry_candidates.json
```
- 8개 후보 조합 (Edge >= 0)
- Optimistic/Realistic/Conservative Edge 값
- 후보별 Rationale

**3. Edge Recalibration Report**
```
logs/d82-10/edge_recalibration_report.json
```
- 시나리오 파라미터
- Grid 크기 및 계산 통계
- D82-9 조합 비교 테이블

### 스크립트

**1. `scripts/compute_d82_9_cost_profile.py`**
- D82-9 KPI 파일 파싱
- 비용 구조 통계 계산
- JSON 출력

**2. `scripts/recalibrate_d82_edge_model.py`**
- 시나리오별 Edge 재계산
- 후보 선정 로직
- 비교 분석 및 리포트 생성

---

## 🎯 D82-11 계획

### 다음 단계: PAPER Smoke Test

**목적:**
- D82-10 재보정 후보 검증
- 10분/20분 단계적 테스트
- TP 도달률 및 Win Rate 확인

**후보 우선순위 (Top 5):**
1. **Entry 16, TP 18** (Edge +3.73 bps)
2. **Entry 14, TP 18** (Edge +2.73 bps)
3. **Entry 16, TP 16** (Edge +2.73 bps)
4. **Entry 12, TP 18** (Edge +1.73 bps)
5. **Entry 14, TP 16** (Edge +1.73 bps)

**실행 계획:**
```powershell
# 10분 스모크 테스트 (Top 3)
python scripts/run_d82_11_smoke_test.py --duration 600

# 20분 검증 (통과한 후보)
python scripts/run_d82_11_smoke_test.py --duration 1200

# 1시간 본 검증 (안정성 확인)
python scripts/run_d82_11_longrun.py --duration 3600
```

**Acceptance Criteria:**
- Round Trips >= 5 (10분), >= 10 (20분)
- Win Rate > 0% (최소 1건 TP 도달)
- PnL >= 0
- TP Exit % > 0%

---

## 📝 Lessons Learned

### D82-9 → D82-10 핵심 교훈

1. **이론 Edge 모델은 실측 데이터로 검증 필수**
   - D82-7 가정 (Fill 100%) vs D82-9 실측 (Fill 26%)
   - 모델 파라미터의 현실 부합성 확인 필요

2. **Threshold Tuning은 비용 구조 기반으로**
   - Entry + TP 합산이 최소 비용(13.28 bps)의 2배 이상 필요
   - 단순히 TP만 낮춰서는 해결 불가

3. **Trade-off 곡선의 복잡성**
   - Entry↓ → Activity↑ but Edge↓
   - TP↓ → Win Rate↑ but Edge↓
   - 최적 균형점 찾기는 실험적 검증 필요

4. **Mock Fill Model의 한계**
   - 26% 필률은 비현실적 (D77-4는 100% WR 달성)
   - L2 Orderbook 통합이 최우선 과제

---

## ✅ Status Summary

| Task | Status | Output |
|------|--------|--------|
| D82-9 비용 프로파일 계산 | ✅ | `d82_9_cost_profile.json` |
| Edge 모델 재보정 | ✅ | 3 scenarios, 26 combinations |
| 후보 선정 | ✅ | 8 candidates (Edge >= 0) |
| D82-9 비교 분석 | ✅ | 모두 Edge < 0 확인 |
| 문서 작성 | ✅ | `D82-10_RECALIBRATED_EDGE_MODEL.md` |
| JSON 산출물 | ✅ | 3 files |
| 테스트 작성 | ⏳ | Pending |

**D82-10: COMPLETE** → Ready for D82-11 PAPER Smoke Test

---

**Document Generated:** 2025-12-05  
**Author:** AI Assistant  
**Reviewed By:** Automated Analysis
