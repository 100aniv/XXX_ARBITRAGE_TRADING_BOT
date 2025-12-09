# D88-2: RANDOM Mode A/B Longrun Validation Report

**작성일:** 2025-12-09  
**상태:** ⚠️ **CONDITIONAL PASS** (Zone Preference 효과 미미)

---

## 0. Executive Summary

**목표:** Entry BPS random 모드를 사용하여 Advisory vs Strict A/B 테스트를 수행하고, Zone Preference (D87-4) 효과를 정량적으로 검증한다.

**실행 결과:**
- ✅ **인프라 안정성**: Duration Guard ±1초, Fill Events 360개, Fatal Error 0건
- ✅ **Zone 분산**: Z1~Z4 모두 커버, Z2 편중 해소 (< 30%)
- ⚠️ **Zone Preference 효과**: ΔP(Z2) = 2.2%p (목표: ≥3%p) → **효과 미미**

**최종 판정:** ⚠️ **CONDITIONAL PASS**
- Advisory와 Strict의 Zone 분포 차이가 목표(3%p)보다 작음 (2.2%p)
- Zone Selection (D87-4) 로직의 효과가 통계적으로 유의미하지 않음
- 1%p ≤ Δ < 3%p 구간: 효과는 관측되었으나 실전 적용에는 불충분

---

## 1. Execution Scenario

### 1.1 Test Configuration

| Parameter | Advisory 30m | Strict 30m |
|-----------|-------------|-----------|
| **Duration** | 1800초 (30분) | 1800초 (30분) |
| **L2 Source** | real (Upbit WebSocket) | real (Upbit WebSocket) |
| **FillModel Mode** | advisory | strict |
| **Calibration** | logs/d86-1/calibration_20251207_123906.json | logs/d86-1/calibration_20251207_123906.json |
| **Entry BPS Mode** | **random** | **random** |
| **Entry BPS Min** | 5.0 | 5.0 |
| **Entry BPS Max** | 25.0 | 25.0 |
| **Entry BPS Seed** | **42** | **999** (다른 시드) |
| **Session Tag** | d88_2_advisory_30m_random | d88_2_strict_30m_random |

**핵심 차이점:**
- **Random Seed**: Advisory(42) vs Strict(999) → 서로 다른 Entry BPS 시퀀스 생성
- **Zone Preference**: Advisory는 Z2/Z3 선호 (multiplicative), Strict는 균등 (additive bonus)

### 1.2 Execution Timeline

| Session | Start Time | End Time | Actual Duration |
|---------|------------|----------|-----------------|
| Advisory | 2025-12-09 10:18:36 | 2025-12-09 10:48:38 | 1800.86초 (+0.86초) |
| Strict | 2025-12-09 10:49:15 | 2025-12-09 11:19:22 | 1800.84초 (+0.84초) |

---

## 2. Results Summary

### 2.1 KPI Table

| Metric | Advisory 30m | Strict 30m | Δ (Advisory - Strict) |
|--------|--------------|------------|------------------------|
| **Duration (seconds)** | 1800.86 (+0.86s) | 1800.84 (+0.84s) | +0.02s |
| **Entry Trades** | 180 | 180 | 0 |
| **Fill Events** | 360 | 360 | 0 |
| **Total PnL (USD)** | $6.40 | $6.30 | +$0.10 (+1.6%) |
| **Iterations** | 1801 | 1801 | 0 |

### 2.2 Zone Distribution

| Zone | Advisory Count | Advisory % | Strict Count | Strict % | ΔP (Advisory - Strict) |
|------|----------------|------------|--------------|----------|------------------------|
| **Z1** | 22 | 12.2% | 17 | 9.4% | +2.8%p |
| **Z2** | 50 | **27.8%** | 46 | **25.6%** | **+2.2%p** |
| **Z3** | 66 | 36.7% | 64 | 35.6% | +1.1%p |
| **Z4** | 42 | 23.3% | 53 | 29.4% | -6.1%p |
| **UNMATCHED** | 0 | 0.0% | 0 | 0.0% | 0.0%p |
| **Total** | 180 | 100% | 180 | 100% | - |

**핵심 관측:**
- Advisory Z2: 27.8% (예상: Z2 선호 → 더 높은 비율)
- Strict Z2: 25.6% (예상: 균등 분포 → 25% 근처)
- **ΔP(Z2) = 2.2%p** (목표: ≥3%p) ⚠️ **미달**

---

## 3. Acceptance Criteria Validation

### 3.1 기존 Criteria (C1~C6)

| Criteria | Target | Advisory | Strict | Status |
|----------|--------|----------|--------|--------|
| **C1: Duration Accuracy** | ±30초 | +0.86초 ✅ | +0.84초 ✅ | **PASS** |
| **C2: Fill Events Generation** | ≥100개 | 360개 ✅ | 360개 ✅ | **PASS** |
| **C3: All Zones Covered** | Z1~Z4 > 0 | Z1~Z4 > 0 ✅ | Z1~Z4 > 0 ✅ | **PASS** |
| **C4: No Z2 Dominance** | Z2 < 90% | 27.8% ✅ | 25.6% ✅ | **PASS** |
| **C5: Low Unmatched Rate** | < 5% | 0.0% ✅ | 0.0% ✅ | **PASS** |
| **C6: Fatal Error** | 0건 | 0건 ✅ | 0건 ✅ | **PASS** |

**Overall C1~C6:** ✅ **PASS** (6/6)

### 3.2 새로운 Criteria (C7~C8)

| Criteria | Target | Result | Status |
|----------|--------|--------|--------|
| **C7: Z2 분포 차이** | \|ΔP(Z2)\| ≥ 3%p | 2.2%p | ⚠️ **CONDITIONAL PASS** |
| **C8: Z2 평균 Fill Size 차이** | ≥ 3%p | N/A (데이터 미수집) | ⏸️ **SKIP** |

**Overall C7~C8:** ⚠️ **CONDITIONAL PASS**

---

## 4. Interpretation & Findings

### 4.1 Zone Preference 효과 분석

**예상:**
- Advisory: Z2 선호(2.0x multiplicative) → Z2 비율 **>30%** 예상
- Strict: 균등 분포 → Z2 비율 **≈25%** 예상
- ΔP(Z2) ≥ 5%p 예상

**실제:**
- Advisory Z2: 27.8% (예상보다 낮음)
- Strict Z2: 25.6% (예상과 비슷함)
- ΔP(Z2) = 2.2%p (예상보다 훨씬 낮음)

**Why Zone Preference 효과가 미미한가?**

#### 4.1.1 가설 1: Entry BPS 분포가 Zone 분포를 지배
- Random 모드(5.0~25.0 bps 균일 분포)로 인해 Entry BPS가 먼저 결정됨
- Entry BPS가 Zone을 강하게 결정하므로, Fill Model의 Zone Preference가 작동할 여지가 제한됨
- **결론**: Entry BPS 분포가 Zone Selection 로직보다 우선순위가 높음

#### 4.1.2 가설 2: Multiplicative Preference(2.0x)가 충분히 강하지 않음
- Advisory Mode의 Z2 선호도(2.0x)가 실전에서는 약하게 작동
- Route Health Score 계산 시 다른 요인(spread, volume, latency 등)이 zone preference보다 우선될 가능성
- **결론**: Zone Preference 가중치를 3.0x~5.0x로 강화 필요

#### 4.1.3 가설 3: 30분 실행이 통계적으로 불충분
- 180 trades는 Zone별로 약 45개씩 분포 (22~66개 범위)
- 샘플 사이즈가 작아 통계적 유의성 확보 어려움
- **결론**: 3h 이상 LONGRUN 필요 (1000+ trades)

### 4.2 Zone Distribution 패턴 분석

**Advisory vs Strict 비교:**
- Z1: Advisory(12.2%) > Strict(9.4%) → +2.8%p
- Z2: Advisory(27.8%) > Strict(25.6%) → +2.2%p ⚠️
- Z3: Advisory(36.7%) > Strict(35.6%) → +1.1%p
- Z4: Advisory(23.3%) < Strict(29.4%) → -6.1%p

**패턴:**
- Advisory가 Z1~Z3에서 약간 높고, Z4에서 낮음
- Z2 선호 효과는 있으나, 목표(3%p)에 미달
- Z3가 두 모드 모두에서 가장 높음 (35.6~36.7%)

**의미:**
- Zone Preference 로직이 **작동은 하지만**, 효과가 약함
- Z2 대신 Z3가 가장 많이 선택됨 (Entry BPS 분포 영향으로 추정)

### 4.3 PnL 비교

- Advisory: $6.40
- Strict: $6.30
- Δ = $0.10 (+1.6%)

**의미:**
- PnL 차이는 거의 없음 (±10센트)
- Zone Preference가 PnL에 유의미한 영향을 주지 못함
- 실전 수익성 관점에서 Advisory의 이점 없음

---

## 5. Limitations

### 5.1 Random Mode의 한계
- Entry BPS가 5.0~25.0 bps 범위에서 균일 분포로 생성됨
- Zone 분포가 Entry BPS 분포에 강하게 종속됨
- Zone Preference 효과를 검증하기에는 부적합한 환경

### 5.2 샘플 사이즈 부족
- 30분 실행 → 180 trades → Zone별 약 22~66개
- 통계적 유의성 확보 어려움
- 3h 이상 LONGRUN 필요

### 5.3 Fill Size 데이터 미수집
- d88_0_analyze_zone_distribution.py 스크립트가 Fill Size 정보를 제공하지 않음
- C8 (ΔFillSize(Z2) ≥ 3%p) 검증 불가
- 추가 분석 스크립트 필요

### 5.4 Zone Preference 가중치 조정 필요
- 현재 Advisory Mode: Z2(2.0x), Z3(1.5x)
- 효과가 약함 → 3.0x~5.0x로 강화 필요

---

## 6. Next Steps

### 6.1 PASS 시나리오 (현재: CONDITIONAL PASS)
- ❌ **D88-3 (TP BPS Diversification)**: SKIP (Zone Preference 효과 미미로 인해 보류)
- ✅ **D89-0 (Zone Preference 로직 강화)**: 우선 진행
  - Advisory Mode Z2 가중치: 2.0x → 3.0x~5.0x
  - D88-2-2 (3h LONGRUN) 재실행하여 효과 재검증

### 6.2 FAIL 시나리오
- **D87-4 Zone Selection 로직 재설계**
  - Entry BPS 분포에 덜 종속되도록 로직 변경
  - Route Health Score 계산 시 Zone Preference 우선순위 상향

### 6.3 추가 분석 필요
- Fill Size 분석 스크립트 개발
- Zone별 평균 Fill Ratio 비교
- Zone별 PnL 기여도 분석

---

## 7. Deliverables

### 7.1 로그 파일
- `logs/d87-3/d88_2_advisory_30m_random/`
  - `kpi_20251209_011836.json`
  - `fill_events_20251209_011836.jsonl`
  - `zone_distribution_analysis.json`
- `logs/d87-3/d88_2_strict_30m_random/`
  - `kpi_20251209_014915.json`
  - `fill_events_20251209_014915.jsonl`
  - `zone_distribution_analysis.json`

### 7.2 문서
- `docs/D88/D88_2_RANDOM_VALIDATION_REPORT.md` (본 문서)

---

## 8. Conclusion

D88-2 RANDOM Mode A/B Validation은 **CONDITIONAL PASS**로 판정되었습니다.

**달성한 목표:**
- ✅ 인프라 안정성 (Duration Guard, Fill Events, Zero Fatal Errors)
- ✅ Zone 분산 (Z2 편중 해소, 모든 Zone 커버)
- ✅ Random Mode 정상 작동

**미달성 목표:**
- ⚠️ Zone Preference 효과 (ΔP(Z2) = 2.2%p < 3%p 목표)
- ⚠️ Advisory vs Strict 유의미한 차이 부재

**권장 사항:**
1. **D89-0**: Zone Preference 가중치 강화 (2.0x → 3.0x~5.0x)
2. **D88-2-2**: 3h LONGRUN 재실행 (샘플 사이즈 증가)
3. **Fill Size 분석**: 추가 스크립트 개발하여 C8 검증

**최종 의견:**
- Zone Selection (D87-4) 로직은 작동하지만, 효과가 미미함
- Entry BPS 분포가 Zone 분포를 지배하므로, Zone Preference의 영향력이 제한됨
- 실전 적용을 위해서는 Zone Preference 가중치 강화 또는 로직 재설계 필요

---

**Report Generated:** 2025-12-09  
**Author:** Windsurf AI (Automated D88-2 Validation)
