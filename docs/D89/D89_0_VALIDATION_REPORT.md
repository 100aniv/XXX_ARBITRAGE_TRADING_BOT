# D89-0: Zone Preference Weight Tuning Validation Report

**작성일:** 2025-12-09  
**상태:** ❌ **FAIL** (Zone Preference 효과 없음 - Entry BPS 지배 구조 확인)

---

## 0. Executive Summary

**목표:** Advisory mode의 Z2 Zone Preference 가중치를 1.05 → 3.00으로 강화하여 ΔP(Z2) ≥ 3%p 달성

**실행 결과:**
- ✅ **코드 구현**: Advisory Z2 가중치 1.05 → 3.00 (약 3배 증가)
- ✅ **인프라 안정성**: Duration Guard ±1초, Fill Events 360개, Fatal Error 0건
- ❌ **Zone Preference 효과**: **전혀 없음** (D88-2와 결과 100% 동일)
- ❌ **ΔP(Z2)**: 2.2%p (목표 ≥3%p 미달, D88-2와 동일)

**최종 판정:** ❌ **FAIL**
- Zone Preference 가중치를 약 3배 증가시켰음에도 Zone 분포가 전혀 변하지 않음
- **근본 원인:** Entry BPS가 Zone을 결정하는 지배적 요인이며, Zone Preference는 완전히 무시됨
- **결론:** 현재 아키텍처에서 Zone Preference 가중치 tuning은 무의미함

---

## 1. Execution Scenario

### 1.1 가중치 변경 내용

**D88-2 (AS-IS):**
```python
"advisory": {
    "Z1": 0.90,
    "Z2": 1.05,  # +5%
    "Z3": 0.95,
    "Z4": 0.90,
}
```

**D89-0 (TO-BE):**
```python
"advisory": {
    "Z1": 0.80,
    "Z2": 3.00,  # +200% (약 3배 증가)
    "Z3": 0.85,
    "Z4": 0.80,
}
```

**변경 사항:**
- Advisory Z2: 1.05 → 3.00 (**+186% 증가**, 약 3배)
- Strict Z2: 1.15 (변경 없음, 기준선 유지)

### 1.2 Test Configuration

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
| **Session Tag** | d89_0_advisory_30m_random | d89_0_strict_30m_random |
| **Zone Preference Z2** | **3.00** (D88-2: 1.05) | 1.15 (동일) |

### 1.3 Execution Timeline

| Session | Start Time | End Time | Actual Duration |
|---------|------------|----------|-----------------|
| Advisory | 2025-12-09 18:28:30 | 2025-12-09 18:58:31 | 1800.9초 (+0.9초) |
| Strict | 2025-12-09 18:58:57 | 2025-12-09 19:28:59 | 1800.9초 (+0.9초) |

---

## 2. Results Summary

### 2.1 KPI Table

| Metric | D89-0 Advisory | D89-0 Strict | D88-2 Advisory | D88-2 Strict | Δ (D89-0 vs D88-2) |
|--------|----------------|--------------|----------------|--------------|---------------------|
| **Duration (seconds)** | 1800.9 (+0.9s) | 1800.9 (+0.9s) | 1800.86 (+0.86s) | 1800.84 (+0.84s) | ±0.0s |
| **Entry Trades** | 180 | 180 | 180 | 180 | 0 |
| **Fill Events** | 360 | 360 | 360 | 360 | 0 |
| **Total PnL (USD)** | $6.42 | $6.22 | $6.40 | $6.30 | +$0.02 / -$0.08 |
| **Iterations** | 1801 | 1801 | 1801 | 1801 | 0 |

### 2.2 Zone Distribution

| Zone | D89-0 Advisory | D89-0 Strict | D88-2 Advisory | D88-2 Strict | Δ (Advisory - Strict) |
|------|----------------|--------------|----------------|--------------|------------------------|
| **Z1** | 22 (12.2%) | 17 (9.4%) | 22 (12.2%) | 17 (9.4%) | +2.8%p |
| **Z2** | **50 (27.8%)** | **46 (25.6%)** | **50 (27.8%)** | **46 (25.6%)** | **+2.2%p** |
| **Z3** | 66 (36.7%) | 64 (35.6%) | 66 (36.7%) | 64 (35.6%) | +1.1%p |
| **Z4** | 42 (23.3%) | 53 (29.4%) | 42 (23.3%) | 53 (29.4%) | -6.1%p |
| **UNMATCHED** | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0.0%p |
| **Total** | 180 (100%) | 180 (100%) | 180 (100%) | 180 (100%) | - |

**핵심 관측:**
- **D89-0 vs D88-2 비교: 결과 100% 동일**
- Advisory Z2: 27.8% (D88-2와 동일, 변화 없음)
- Strict Z2: 25.6% (D88-2와 동일, 변화 없음)
- **ΔP(Z2) = 2.2%p** (목표 ≥3%p 미달, D88-2와 동일)
- **Zone Preference 가중치 3배 증가의 효과: 0%**

---

## 3. Acceptance Criteria Validation

### 3.1 기존 Criteria (C1~C6)

| Criteria | Target | D89-0 Advisory | D89-0 Strict | Status |
|----------|--------|----------------|--------------|--------|
| **C1: Duration Accuracy** | ±30초 | +0.9초 ✅ | +0.9초 ✅ | **PASS** |
| **C2: Fill Events Generation** | ≥100개 | 360개 ✅ | 360개 ✅ | **PASS** |
| **C3: All Zones Covered** | Z1~Z4 > 0 | Z1~Z4 > 0 ✅ | Z1~Z4 > 0 ✅ | **PASS** |
| **C4: No Z2 Dominance** | Z2 < 90% | 27.8% ✅ | 25.6% ✅ | **PASS** |
| **C5: Low Unmatched Rate** | < 5% | 0.0% ✅ | 0.0% ✅ | **PASS** |
| **C6: Fatal Error** | 0건 | 0건 ✅ | 0건 ✅ | **PASS** |

**Overall C1~C6:** ✅ **PASS** (6/6)

### 3.2 Zone Preference Criteria (C7~C8)

| Criteria | Target | D89-0 Result | D88-2 Result | Status |
|----------|--------|--------------|--------------|--------|
| **C7: ΔP(Z2)** | ≥ 3.0%p | 2.2%p | 2.2%p | ❌ **FAIL** (동일) |
| **C8: Advisory Z2 Increase** | > 27.8% (D88-2) | 27.8% | 27.8% | ❌ **FAIL** (0% 증가) |

**Overall C7~C8:** ❌ **FAIL** (0/2)

---

## 4. 핵심 발견 (Critical Findings)

### 4.1 Zone Preference 가중치 무효화 (Zone Preference Weight Nullification)

**가설 (설계 단계):**
- Advisory Z2 가중치를 1.05 → 3.00으로 약 3배 증가
- Score 조정: `base_score * zone_pref`
- 예: base_score=70 → Advisory Z2: 210 (clipped to 100)
- 예상 효과: Advisory Z2 비율 45~55%, ΔP(Z2) 약 20~25%p

**실제 결과:**
- Advisory Z2: 27.8% (**D88-2와 완전히 동일**, 0% 변화)
- Strict Z2: 25.6% (**D88-2와 완전히 동일**, 0% 변화)
- ΔP(Z2): 2.2%p (**D88-2와 완전히 동일**, 0% 변화)
- **Zone Preference 가중치 3배 증가의 효과: 완전히 무효화됨**

**원인 분석:**
1. **Entry BPS 선결정 (Entry BPS Pre-determination)**
   - Entry BPS가 random mode(5.0~25.0 bps, 균일 분포)로 먼저 생성됨
   - 동일한 시드(Advisory: 42, Strict: 999)를 사용하면 동일한 Entry BPS 시퀀스 생성

2. **Entry BPS → Zone 매핑 강제성 (Forced Entry BPS → Zone Mapping)**
   - Calibration JSON에서 각 Entry BPS에 대응하는 Zone이 이미 결정됨
   - 예: Entry BPS 10.0 → Z2, Entry BPS 5.0 → Z1
   - Zone Preference는 이미 결정된 Zone을 "재선택"할 기회가 없음

3. **Zone Preference 적용 시점 문제 (Zone Preference Timing Issue)**
   - Zone Preference는 `adjust_route_score()`에서 RouteHealthScore를 조정
   - 하지만 Entry BPS가 이미 결정된 상태에서 Route가 선택되므로, Score 조정이 Zone 분포에 영향을 주지 못함
   - **Zone Preference는 "어느 Route를 선택할지"를 조정하지만, "어느 Zone에 진입할지"는 Entry BPS가 이미 결정함**

### 4.2 아키텍처 근본 문제 (Architectural Root Cause)

**현재 실행 흐름:**
```
1. Entry BPS 생성 (random mode, seed=42)
   → Entry BPS = [10.0, 5.0, 15.0, 20.0, ...]

2. Calibration 조회
   → Entry BPS 10.0 → Zone Z2
   → Entry BPS 5.0 → Zone Z1
   → Entry BPS 15.0 → Zone Z3

3. Zone 할당 완료 (Zone Preference 적용 전)

4. Zone Preference 적용 (adjust_route_score)
   → RouteHealthScore 조정: Z2: 70 * 3.00 = 210 (clipped to 100)
   → 하지만 이미 Zone Z2에 할당됨, 변경 불가

5. Route 선택 및 실행
   → Zone Z2에서 실행
```

**문제:**
- Zone Preference는 4단계에서 적용되지만, Zone 할당은 2~3단계에서 이미 완료됨
- Zone Preference가 "다른 Zone으로 변경"할 수 있는 메커니즘이 없음
- **Zone Preference는 Route 내에서의 우선순위를 조정할 뿐, Zone 자체를 변경하지 못함**

### 4.3 Unit Test vs Integration Test 차이

**Unit Test (test_d89_0_zone_preference.py):**
- ✅ 5/5 PASS
- Advisory Z2 Score = 100 (clipped), Strict Z2 Score = 80.5
- Zone Preference 로직 자체는 정상 작동

**Integration Test (30m A/B Validation):**
- ❌ Zone 분포 전혀 변하지 않음
- **원인:** Entry BPS → Zone 매핑이 Zone Preference보다 우선함

**결론:**
- Unit Test는 "Zone Preference 로직"만 검증 → PASS
- Integration Test는 "전체 시스템 동작"을 검증 → FAIL
- **Zone Preference 로직은 정상이지만, 시스템 아키텍처상 효과가 없음**

---

## 5. 왜 Zone Preference가 작동하지 않는가?

### 5.1 Entry BPS vs Zone Preference 우선순위

**Entry BPS의 영향력:**
- Random mode: 5.0~25.0 bps 균일 분포
- Calibration JSON에서 Entry BPS → Zone 매핑 조회
- **Entry BPS가 Zone을 100% 결정**

**Zone Preference의 영향력:**
- RouteHealthScore 조정: `base_score * zone_pref`
- 하지만 Entry BPS가 이미 Zone을 결정한 상태
- **Zone Preference는 0% 영향력**

**예시:**
- Entry BPS = 10.0
- Calibration: Entry BPS 10.0 → Zone Z2
- Zone Preference: Z2 가중치 3.00
- **결과:** Zone Z2 (Entry BPS가 결정, Zone Preference는 무관)

### 5.2 Advisory vs Strict 차이가 발생하는 이유

**Advisory와 Strict의 Zone 분포가 다른 이유:**
- **Entry BPS 시드가 다름** (Advisory: 42, Strict: 999)
- 서로 다른 Entry BPS 시퀀스 생성
- 서로 다른 Zone 매핑 결과

**Zone Preference의 역할:**
- **없음** (Entry BPS 시드가 모든 것을 결정)

---

## 6. 대안 (Alternative Solutions)

### 6.1 Calibration JSON 수정 (Short-term)
- **방법:** Calibration JSON에서 Entry BPS → Zone 매핑을 Advisory/Strict별로 다르게 설정
- **장점:** 즉시 적용 가능
- **단점:** Calibration의 통계적 의미 왜곡, 유지보수 복잡

### 6.2 Entry BPS 생성 로직 변경 (Medium-term)
- **방법:** Entry BPS를 생성할 때 Zone Preference를 반영
- **예:** Advisory mode에서는 Z2에 해당하는 Entry BPS(10~15 bps)를 더 자주 생성
- **장점:** 아키텍처 변경 없이 효과 발생
- **단점:** Entry BPS 생성 로직 복잡화

### 6.3 Zone Selection 로직 재설계 (Long-term) ⭐ 권장
- **방법:** Entry BPS 생성 → Calibration 조회 → **Zone Preference 적용 후 Zone 재선택**
- **흐름:**
  ```
  1. Entry BPS 생성: 10.0
  2. Calibration 조회: 10.0 → [Z1, Z2, Z3, Z4] 모두 가능 (확률 분포)
  3. Zone Preference 적용: Z2 가중치 3.00
  4. Zone 선택: Z2 (가중치 반영하여 확률적 선택)
  ```
- **장점:** Zone Preference의 의미 회복, 통계적 타당성 유지
- **단점:** 아키텍처 대규모 변경 필요 (D90+)

---

## 7. Limitations

### 7.1 Random Mode의 한계 (재확인)
- Entry BPS가 5.0~25.0 bps 범위에서 균일 분포로 생성됨
- Zone 분포가 Entry BPS 분포에 강하게 종속됨
- **D89-0에서 확인:** Zone Preference는 이 종속성을 깨지 못함

### 7.2 현재 아키텍처의 한계
- Entry BPS → Zone 매핑이 Calibration JSON에 고정됨
- Zone Preference가 매핑을 변경할 수 없음
- **근본 해결책:** 아키텍처 재설계 (D90+)

### 7.3 샘플 사이즈 부족 (D88-2와 동일)
- 30분 실행 → 180 trades → Zone별 약 22~66개
- 통계적 유의성 확보 어려움
- **하지만:** D89-0는 결과가 100% 동일하므로 샘플 사이즈와 무관

---

## 8. Next Steps

### 8.1 Zone Selection 아키텍처 재설계 (D90-0) ⭐ 필수
- **목적:** Entry BPS → Zone 매핑을 확률적으로 변경
- **방법:** Calibration JSON에서 Entry BPS별로 [Z1, Z2, Z3, Z4] 확률 분포 제공
- **효과:** Zone Preference가 실제로 Zone 선택에 영향을 미침

### 8.2 Entry BPS 생성 로직 변경 (D90-1) 선택
- **목적:** Zone Preference를 Entry BPS 생성 단계에서 반영
- **방법:** Advisory mode에서 Z2 Entry BPS(10~15 bps) 생성 확률 증가
- **효과:** Zone Preference의 간접적 구현

### 8.3 D89-0 코드 롤백 고려
- **현재 상태:** Advisory Z2 가중치 = 3.00 (효과 없음)
- **롤백 여부:** GPT 판단 대기
- **근거:** 효과가 없으므로 원래 값(1.05)으로 복원 고려

---

## 9. Deliverables

### 9.1 코드 변경
- **arbitrage/execution/fill_model_integration.py**
  - Line 132: Advisory Z2 가중치 1.05 → 3.00

### 9.2 Unit Test
- **tests/test_d89_0_zone_preference.py**
  - 5/5 PASS ✅

### 9.3 로그 파일
- `logs/d87-3/d89_0_advisory_30m_random/`
  - `kpi_20251209_092830.json`
  - `fill_events_20251209_092830.jsonl`
  - `zone_distribution_analysis.json`
- `logs/d87-3/d89_0_strict_30m_random/`
  - `kpi_20251209_095857.json`
  - `fill_events_20251209_095857.jsonl`
  - `zone_distribution_analysis.json`

### 9.4 문서
- `docs/D89/D89_0_ZONE_PREFERENCE_DESIGN.md` (설계 문서)
- `docs/D89/D89_0_VALIDATION_REPORT.md` (본 문서)

---

## 10. Conclusion

D89-0은 **FAIL**로 판정되었습니다.

**달성한 목표:**
- ✅ Zone Preference 가중치 강화 (1.05 → 3.00, 약 3배)
- ✅ Unit Test 통과 (5/5 PASS)
- ✅ 인프라 안정성 (Duration, Fill Events, Zero Fatal Errors)

**미달성 목표:**
- ❌ ΔP(Z2) ≥ 3.0%p (실제: 2.2%p, D88-2와 동일)
- ❌ Advisory Z2 비율 증가 (실제: 27.8%, D88-2와 동일, 0% 변화)

**핵심 발견:**
- **Zone Preference 가중치 tuning은 현재 아키텍처에서 무의미함**
- Entry BPS가 Zone을 100% 결정하며, Zone Preference는 0% 영향력
- Unit Test는 PASS하지만 Integration Test는 FAIL → 시스템 아키텍처 문제

**권장 사항:**
1. **D90-0: Zone Selection 아키텍처 재설계** (필수)
   - Entry BPS → Zone 매핑을 확률적으로 변경
   - Zone Preference가 실제로 Zone 선택에 영향을 미치도록 수정

2. **D89-0 코드 롤백 고려** (선택)
   - Advisory Z2 가중치를 3.00 → 1.05로 복원
   - 효과가 없으므로 원래 값 유지가 합리적

3. **D88-3 (TP BPS Diversification) 보류 유지** (권장)
   - Zone Preference 효과가 없으므로 TP BPS Diversification도 무의미

**최종 의견:**
- D89-0의 가장 큰 성과는 **"Zone Preference가 작동하지 않는다는 것을 실증"**한 것
- 이는 D90+ 아키텍처 재설계의 강력한 근거가 됨
- Zone Preference 로직 자체는 정상이지만, 시스템 통합에서 효과가 무효화됨

---

**Report Generated:** 2025-12-09  
**Author:** Windsurf AI (D89-0 Validation Phase)  
**Status:** RESULT_RECORDED (GPT_REVIEW_PENDING)
