# D90-0: Entry BPS Zone-Weighted Random - Validation Report

**작성일:** 2025-12-10  
**Status:** ✅ **COMPLETE - GO**  
**핵심 성과:** ΔP(Z2) = 22.8%p (목표 ≥5%p의 **4.6배 초과 달성**)

---

## 1. 개요

### 1.1 배경: D88-2 / D89-0 문제

**D88-2 결과 (Entry BPS random 모드):**
- Entry BPS: 5.0~25.0 bps 균일 분포 난수 샘플링
- Advisory Z2: 27.8%, Strict Z2: 25.6%
- **ΔP(Z2) = 2.2%p** (목표 ≥3%p 미달)

**D89-0 시도 및 실패:**
- Zone Preference 가중치를 **1.05 → 3.00으로 약 3배 증가**
- 예상: Advisory Z2 비율 45~55%, ΔP(Z2) 약 20~25%p
- **실제: Advisory Z2 27.8%, Strict Z2 25.6% (D88-2와 100% 동일, 0% 변화)**
- **근본 원인 발견:** Entry BPS가 Zone을 먼저 결정 → Zone Preference는 이후에 적용되어 무효화

### 1.2 구조적 문제 (D89-0 실증)

```
현재 실행 흐름:
1. Entry BPS 생성 (random mode) → Entry BPS = [10.0, 5.0, 15.0, ...]
2. Calibration 조회 → Entry BPS 10.0 → Zone Z2 (고정 매핑) ✅ Zone 할당 완료
3. Zone Preference 적용 → Score * 3.00, 하지만 Zone은 이미 결정됨 ❌ 변경 불가
4. Route 선택 및 실행

문제: Entry BPS가 Zone을 100% 결정, Zone Preference는 0% 영향
```

### 1.3 D90-0 솔루션: Zone-Weighted Random

**핵심 아이디어:**
- **Entry BPS 생성 단계에서 Zone 가중치를 직접 반영**
- Zone을 먼저 선택 → 해당 Zone의 Entry BPS 범위 내에서 샘플링

**2단계 샘플링:**
1. **Zone 선택 (가중치 기반 확률 분포)**
   - zone_weights = [0.5, 3.0, 1.5, 0.5] → P(Z2) = 54.5%
2. **Entry BPS 샘플링 (선택된 Zone 범위 내 균등 분포)**
   - Z2 선택됨 → Entry BPS ∈ [7.0, 12.0]

**예상 효과:**
- Advisory: Z2가 50%+ 선택됨
- Strict: 각 Zone 25% 균등 선택
- **ΔP(Z2) ≥ 5%p 달성 가능**

---

## 2. 구현 요약

### 2.1 EntryBPSProfile zone_random 모드

**구현 위치:** `arbitrage/domain/entry_bps_profile.py`

**핵심 메서드:**

```python
def _compute_cumulative_weights(self):
    """누적 가중치 계산"""
    self._zone_cumulative_weights = []
    cumsum = 0.0
    for weight in self.zone_weights:
        cumsum += weight
        self._zone_cumulative_weights.append(cumsum)
    # 예: [0.5, 3.0, 1.5, 0.5] → [0.5, 3.5, 5.0, 5.5]

def _sample_zone_index(self) -> int:
    """Zone 인덱스 확률적 샘플링"""
    total_weight = self._zone_cumulative_weights[-1]  # 5.5
    rand_val = self._rng.uniform(0, total_weight)  # 0~5.5
    
    for idx, cumsum in enumerate(self._zone_cumulative_weights):
        if rand_val < cumsum:
            return idx  # Zone 인덱스 반환
    return len(self._zone_cumulative_weights) - 1

def _next_zone_random(self) -> float:
    """Zone-weighted random Entry BPS 생성"""
    # 1. Zone 선택
    zone_idx = self._sample_zone_index()
    
    # 2. 선택된 Zone boundary 내에서 균등 샘플링
    zmin, zmax = self.zone_boundaries[zone_idx]
    bps = self._rng.uniform(zmin, zmax)
    
    return bps
```

**Validation 로직:**
- zone_boundaries 비어있으면 ValueError
- zone_weights 길이가 zone_boundaries와 다르면 ValueError
- zone_weights에 0 이하 값이 있으면 ValueError
- zone_weights=None이면 균등 가중치 [1.0, 1.0, 1.0, 1.0] 사용 (하위 호환성)

**Reproducibility:**
- seed 고정 시 동일한 Entry BPS 시퀀스 생성
- reset() 호출 시 _rng 재초기화 → 같은 시퀀스 재현

### 2.2 CLI 통합

**수정 위치:** `scripts/run_d84_2_calibrated_fill_paper.py`

**추가 옵션:**
```bash
--entry-bps-mode zone_random
--entry-bps-zone-weights 0.5,3.0,1.5,0.5
```

**파싱 로직:**
```python
zone_weights = None
if entry_bps_zone_weights:
    zone_weights = [float(w.strip()) for w in entry_bps_zone_weights.split(',')]
    logger.info(f"[D90-0] Zone weights parsed: {zone_weights}")
```

### 2.3 Unit Test

**테스트 파일:** `tests/test_d90_0_entry_bps_zone_random.py`

**커버리지:**
- T1: 잘못된 설정 검증 (empty boundaries, length mismatch, zero/negative weight)
- T2: seed 고정 시 재현성 검증
- T3: Zone 분포 rough 검증 (N=10,000, 허용 오차 ±7%p)
- T4: Advisory 프로필 검증 (zone_weights=[0.5,3.0,1.5,0.5])
- T5: Strict 프로필 검증 (zone_weights=[1.0,1.0,1.0,1.0])
- T6: reset() 기능 검증
- T7: zone_weights=None 하위 호환성 검증

**결과:** 10/10 PASS

---

## 3. 30m A/B PAPER 실험

### 3.1 실행 설정

**공통 설정:**
- Duration: 1800초 (30분)
- seed: 90 (재현성 보장)
- L2 Source: real (Upbit WebSocket)
- Calibration: logs/d86-1/calibration_20251207_123906.json
- Entry BPS mode: zone_random
- Zone boundaries: [(5.0,7.0), (7.0,12.0), (12.0,20.0), (20.0,30.0)]

**Advisory 프로필 (Z2 강화):**
```bash
--entry-bps-mode zone_random
--entry-bps-zone-weights 0.5,3.0,1.5,0.5
--fillmodel-mode advisory
--session-tag d90_0_advisory_30m_zone_random
```
- 예상 확률: Z1=9.1%, **Z2=54.5%**, Z3=27.3%, Z4=9.1%

**Strict 프로필 (균등 분포):**
```bash
--entry-bps-mode zone_random
--entry-bps-zone-weights 1.0,1.0,1.0,1.0
--fillmodel-mode strict
--session-tag d90_0_strict_30m_zone_random
```
- 예상 확률: 각 Zone 25%

### 3.2 실행 결과

#### Advisory 30m

**세션:** 20251209_141415  
**KPI:**
- Duration: 1800.93초 (목표 1800초, 오차 +0.93초)
- Entry Trades: 180
- Fill Events: 360 (BUY + SELL)
- Total PnL: **$8.06**

**Zone 분포:**
| Zone | Trades | 비율 | 예상 | 차이 |
|------|--------|------|------|------|
| Z1 | 13 | 7.2% | 9.1% | -1.9%p |
| **Z2** | **95** | **52.8%** | **54.5%** | **-1.7%p** |
| Z3 | 56 | 31.1% | 27.3% | +3.8%p |
| Z4 | 16 | 8.9% | 9.1% | -0.2%p |

**Acceptance Criteria:**
- ✅ C1 (All Zones Covered): Z1~Z4 모두 1개 이상
- ✅ C2 (No Z2 Dominance): Z2=52.8% < 90%
- ✅ C3 (Low Unmatched): 0%

#### Strict 30m

**세션:** 20251209_144433  
**KPI:**
- Duration: 1800.96초 (목표 1800초, 오차 +0.96초)
- Entry Trades: 180
- Fill Events: 360 (BUY + SELL)
- Total PnL: **$6.54**

**Zone 분포:**
| Zone | Trades | 비율 | 예상 | 차이 |
|------|--------|------|------|------|
| Z1 | 35 | 19.4% | 25% | -5.6%p |
| **Z2** | **54** | **30.0%** | **25%** | **+5.0%p** |
| Z3 | 45 | 25.0% | 25% | 0.0%p |
| Z4 | 46 | 25.6% | 25% | +0.6%p |

**Acceptance Criteria:**
- ✅ C1 (All Zones Covered): Z1~Z4 모두 1개 이상
- ✅ C2 (No Z2 Dominance): Z2=30.0% < 90%
- ✅ C3 (Low Unmatched): 0%

### 3.3 A/B 비교 분석

**Zone 분포 비교:**

| Zone | Advisory | Strict | ΔP |
|------|----------|--------|-----|
| Z1 | 7.2% | 19.4% | **-12.2%p** |
| **Z2** | **52.8%** | **30.0%** | **+22.8%p** ⭐ |
| Z3 | 31.1% | 25.0% | **+6.1%p** |
| Z4 | 8.9% | 25.6% | **-16.7%p** |

**핵심 지표:**
- **ΔP(Z2) = 22.8%p**
- 목표: ≥5%p
- 달성: **4.6배 초과 달성** 🎉

**설계 예상 vs 실제:**
- Advisory Z2 예상: 54.5% → 실제: 52.8% (차이 -1.7%p, **거의 일치**)
- Strict Z2 예상: 25% → 실제: 30.0% (차이 +5.0%p)
- ΔP(Z2) 예상: ~29.5%p → 실제: 22.8%p (차이 -6.7%p)

**분석:**
- Zone-weighted random 샘플링이 **설계 의도대로 정확히 작동**
- Advisory는 예상과 거의 일치 (오차 1.7%p)
- Strict는 Z2가 예상보다 약간 높음 (Z1이 낮고 Z2가 높음)
  - 30분 샘플(180 trades)의 통계적 변동으로 추정
  - 3h LONGRUN에서 재검증 필요

---

## 4. Acceptance Criteria 평가

### AC1: Unit Test 통과 ✅

**결과:** 10/10 PASS

**커버리지:**
- 잘못된 설정 검증 ✅
- seed 재현성 검증 ✅
- Zone 분포 rough 검증 ✅
- Advisory/Strict 프로필 검증 ✅
- reset() 기능 검증 ✅
- 하위 호환성 검증 ✅

### AC2: 인프라 기준 (C1~C6) ✅

**C1: Duration 정확도**
- Advisory: 1800.93초 (오차 +0.93초, ±30초 이내 ✅)
- Strict: 1800.96초 (오차 +0.96초, ±30초 이내 ✅)

**C2: Fatal Error**
- Advisory: 0건 ✅
- Strict: 0건 ✅

**C3: Fill Events**
- Advisory: 360개 (목표 ≥300 ✅)
- Strict: 360개 (목표 ≥300 ✅)

**C4: Entry Trades**
- Advisory: 180개 (예상 180개 ✅)
- Strict: 180개 (예상 180개 ✅)

**C5: Zone Coverage**
- Advisory: Z1~Z4 모두 1개 이상 ✅
- Strict: Z1~Z4 모두 1개 이상 ✅

**C6: Unmatched Rate**
- Advisory: 0% (목표 <5% ✅)
- Strict: 0% (목표 <5% ✅)

### AC3: ΔP(Z2) ≥ 5%p ✅

**목표:** ΔP(Z2) ≥ 5%p  
**실제:** ΔP(Z2) = 22.8%p  
**평가:** **4.6배 초과 달성** 🎉

**상세:**
- Advisory Z2: 52.8%
- Strict Z2: 30.0%
- 차이: +22.8%p

**D88-2 / D89-0 대비:**
| 단계 | Advisory Z2 | Strict Z2 | ΔP(Z2) | 개선 |
|------|-------------|-----------|--------|------|
| D88-2 | 27.8% | 25.6% | 2.2%p | - |
| D89-0 | 27.8% | 25.6% | 2.2%p | 0%p |
| **D90-0** | **52.8%** | **30.0%** | **22.8%p** | **+20.6%p** |

**결론:**
- D89-0에서 Zone Preference 가중치를 3배 증가시켜도 0% 변화
- D90-0에서 zone_random 모드 도입으로 **+20.6%p 개선** (무한대 개선률)

---

## 5. 결론

### 5.1 최종 평가: ✅ GO

**D90-0는 다음을 달성했습니다:**
1. **구조적 문제 해결:** Entry BPS 생성 단계에서 Zone 가중치를 직접 반영하여 "Zone Preference 무력화" 문제 근본 해결
2. **목표 초과 달성:** ΔP(Z2) = 22.8%p (목표 ≥5%p의 4.6배)
3. **설계 정확성:** Advisory Z2 예상 54.5% → 실제 52.8% (오차 1.7%p)
4. **인프라 안정성:** Duration, Fatal Error, Fill Events 등 모든 기준 PASS
5. **코드 품질:** Unit Test 10/10 PASS, 재현성/하위 호환성 보장

**D90-0는 "Zone Exposure 조정 레이어"를 구조적으로 확보한 단계로서 GO 수준입니다.**

### 5.2 D89-0 vs D90-0 비교

| 항목 | D89-0 | D90-0 |
|------|-------|-------|
| **접근 방식** | Zone Preference 가중치 강화 (1.05 → 3.00) | Entry BPS 생성에 Zone 가중치 직접 반영 |
| **구조** | Entry BPS → Zone 결정 → Zone Preference 적용 | Zone 선택 → Entry BPS 샘플링 |
| **Advisory Z2** | 27.8% (변화 없음) | 52.8% (**+25%p**) |
| **ΔP(Z2)** | 2.2%p (변화 없음) | 22.8%p (**+20.6%p**) |
| **근본 원인** | Entry BPS가 Zone을 100% 결정 → Zone Preference 무력화 | Zone-weighted random으로 Zone 선택 권한 회복 |
| **평가** | ❌ FAIL (구조적 한계 실증) | ✅ GO (구조적 해결 달성) |

**핵심 교훈:**
- "Zone Preference는 Score 조정만 가능, Zone 분포는 변경 불가"
- "Entry BPS 생성 단계에서 Zone을 직접 제어해야 함"
- **D90-0는 이 교훈을 코드 레벨에서 구조적으로 해결한 첫 번째 성공 사례**

### 5.3 한계 및 다음 단계

**한계:**
1. **샘플 사이즈:** 30분 실행 → 180 trades → Zone별 약 16~95개
   - 통계적 변동성 존재 (특히 Strict Z1=35, Z2=54)
   - 3h LONGRUN(D90-1)에서 재검증 필요
2. **PnL 영향:** Advisory $8.06 vs Strict $6.54 ($1.52 차이)
   - Z2 비중 증가가 PnL에 긍정적인지는 장기 검증 필요
3. **Zone Preference와의 조합:** zone_random만 사용, Zone Preference는 비활성화
   - 향후 두 레이어를 조합하여 더 정교한 Zone Selection 가능

**다음 단계 (D90-1):**
1. **3h LONGRUN A/B 실행:** Advisory/Strict 각 3h (1000+ trades)
   - 통계적 유의성 확보
   - ΔP(Z2) 안정성 검증
2. **Zone 가중치 튜닝:** 필요 시 [0.5, 3.0, 1.5, 0.5] 조정
3. **TopN Arbitrage 통합:** zone_random을 Multi-Symbol PAPER에 적용
4. **YAML 설정 분리:** 가중치를 config 파일로 외부화

---

## 6. 산출물 요약

### 6.1 코드

**구현:**
- `arbitrage/domain/entry_bps_profile.py` (zone_random 모드 추가)
- `scripts/run_d84_2_calibrated_fill_paper.py` (CLI 옵션 추가)

**테스트:**
- `tests/test_d90_0_entry_bps_zone_random.py` (10/10 PASS)

### 6.2 문서

**설계:**
- `docs/D90/D90_0_ENTRY_BPS_ZONE_RANDOM_DESIGN.md` (설계 문서)

**검증:**
- `docs/D90/D90_0_VALIDATION_REPORT.md` (본 문서)

### 6.3 데이터

**로그 디렉터리:**
- `logs/d87-3/d90_0_advisory_30m_zone_random/`
  - kpi_20251209_141415.json
  - fill_events_20251209_141415.jsonl
  - zone_distribution_analysis.json
- `logs/d87-3/d90_0_strict_30m_zone_random/`
  - kpi_20251209_144433.json
  - fill_events_20251209_144433.jsonl
  - zone_distribution_analysis.json

---

## 7. 요약 (Executive Summary)

**D90-0 Mission:** Entry BPS 생성 단계에서 Zone 가중치를 직접 반영하여 Advisory vs Strict 간 Zone 분포 차이를 명확하게 달성

**AS-IS (D88-2 / D89-0):**
- Entry BPS random 모드 → Zone 분포 고정
- Zone Preference 가중치 3배 증가 → 0% 변화 (구조적 무력화)
- ΔP(Z2) = 2.2%p (목표 미달)

**TO-BE (D90-0):**
- zone_random 모드 도입: Zone 선택 → Entry BPS 샘플링
- Advisory zone_weights = [0.5, 3.0, 1.5, 0.5] → Z2 54.5% 예상
- Strict zone_weights = [1.0, 1.0, 1.0, 1.0] → 각 Zone 25% 예상

**결과:**
- Advisory Z2: 52.8% (예상과 거의 일치)
- Strict Z2: 30.0%
- **ΔP(Z2) = 22.8%p** (목표 ≥5%p의 **4.6배 초과 달성**)
- 모든 Acceptance Criteria PASS

**평가:** ✅ **GO** - Zone Exposure 조정 레이어 구조적 확보 완료

**Next:** D90-1 3h LONGRUN으로 통계적 유의성 및 안정성 검증

---

**작성:** Windsurf AI (D90-0 Validation Phase)  
**최종 업데이트:** 2025-12-10  
**상태:** ✅ COMPLETE
