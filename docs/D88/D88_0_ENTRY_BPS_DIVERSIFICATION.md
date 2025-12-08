# D88-0: PAPER Entry BPS Diversification v1

**Status:** ✅ **COMPLETE**  
**Date:** 2025-12-09  
**Related:** D87-6 (Zone Selection A/B Validation)

---

## 목표 (Objective)

D87-6에서 발견된 "모든 트레이드가 Z2에만 집중되는 문제"를 해결하기 위해, PAPER 실행 시 Entry BPS를 다양하게 생성하여 Z1~Z4 Zone에 트레이드가 분산되도록 한다.

**핵심 가치:**
- Zone Preference 로직 (D87-4)의 실전 효과 검증 가능
- 재현 가능한 시나리오 생성 (seed 기반)
- 기존 도메인/엔진 로직 변경 없이 PAPER 입력만 조정

---

## 설계 (Design)

### 1. Entry BPS Profile 클래스

**파일:** `arbitrage/domain/entry_bps_profile.py`

```python
class EntryBPSProfile:
    """
    Entry BPS 생성 프로파일.
    
    Modes:
    - fixed: 고정값 (기존 동작)
    - cycle: Zone별 대표 BPS를 순환 (Z1 → Z2 → Z3 → Z4 → Z1 ...)
    - random: [min_bps, max_bps] 범위 내 균일 분포 난수 생성
    """
```

**주요 메서드:**
- `next()`: 다음 Entry BPS 값 생성
- `reset()`: 프로파일 상태 초기화

**특징:**
- Zone 경계값은 Calibration JSON에서 자동 추출 (하드코딩 방지)
- 독립적인 난수 생성기 (`random.Random(seed)`) 사용 (재현성 보장)
- 입력 검증 로직 포함

### 2. run_d84_2_calibrated_fill_paper.py 수정

**추가된 CLI 인자:**
```bash
--entry-bps-mode {fixed,cycle,random}  # 생성 모드 (기본값: fixed)
--entry-bps-min 5.0                    # 최소 BPS (기본값: 10.0)
--entry-bps-max 25.0                   # 최대 BPS (기본값: 10.0)
--entry-bps-seed 42                    # 난수 생성 seed (기본값: 42)
```

**변경 사항:**
1. Entry BPS Profile 생성 (Calibration에서 zone_boundaries 추출)
2. 루프 내에서 매 트레이드마다 `entry_bps = entry_bps_profile.next()` 호출
3. `fill_model.entry_bps`와 `fill_model.zone` 동적 업데이트

**하위 호환성:**
- 인자를 생략하면 기존과 동일하게 "fixed 10.0bps" 동작

---

## 구현 결과 (Implementation Results)

### 1. Unit Test (11/11 PASS)

**파일:** `tests/test_d88_0_entry_bps_profile.py`

**테스트 항목:**
- ✅ Fixed 모드: 항상 같은 값 반환
- ✅ Cycle 모드: Zone별 대표 BPS 순환
- ✅ Random 모드: 범위 내 난수 생성
- ✅ Random 모드 재현성: 같은 seed로 동일한 시퀀스
- ✅ Reset: 초기 상태 복원
- ✅ Zone Boundary 검증
- ✅ Invalid Mode/Min/Max 검증
- ✅ Zone Coverage: 모든 Zone을 커버
- ✅ Zone Distribution: 1000개 샘플 균일 분포

**결과:**
```
11 passed in 0.15s
```

### 2. Short PAPER Smoke Test (120초, cycle 모드)

**실행 명령어:**
```bash
python scripts/run_d84_2_calibrated_fill_paper.py \
  --duration-seconds 120 \
  --l2-source mock \
  --fillmodel-mode none \
  --calibration-path logs/d86-1/calibration_20251207_123906.json \
  --entry-bps-mode cycle \
  --entry-bps-min 5.0 \
  --entry-bps-max 25.0 \
  --session-tag d88_0_smoke_120s
```

**Zone 분포 결과:**
| Zone | Trades | Percentage |
|------|--------|------------|
| **Z1** | 3 | 25.0% |
| **Z2** | 3 | 25.0% |
| **Z3** | 3 | 25.0% |
| **Z4** | 3 | 25.0% |
| **Unmatched** | 0 | 0.0% |

**Acceptance Criteria:**
- ✅ **C1 (All Zones Covered)**: Z1~Z4 모두 최소 1개 이상의 트레이드
- ✅ **C2 (No Z2 Dominance)**: Z2 비율 < 90% (실제: 25%)
- ✅ **C3 (Low Unmatched Rate)**: Unmatched < 5% (실제: 0%)

**최종 판정:** ✅ **PASS**

### 3. 전체 회귀 테스트 (103/103 PASS)

**실행 결과:**
```
103 passed in 101.93s (0:01:41)
```

- D87 테스트 92개 (기존)
- D88 테스트 11개 (신규)

---

## 산출물 (Deliverables)

### 신규 파일
1. **`arbitrage/domain/entry_bps_profile.py`** (190 lines)
   - Entry BPS Profile 클래스 구현
   
2. **`tests/test_d88_0_entry_bps_profile.py`** (200 lines)
   - Unit Test 11개
   
3. **`scripts/d88_0_analyze_zone_distribution.py`** (130 lines)
   - Zone 분포 분석 도구
   
4. **`docs/D88/D88_0_ENTRY_BPS_DIVERSIFICATION.md`** (이 문서)
   - 설계/구현/검증 리포트

### 수정된 파일
1. **`scripts/run_d84_2_calibrated_fill_paper.py`**
   - CLI 인자 4개 추가 (`--entry-bps-mode/min/max/seed`)
   - `run_calibrated_fill_paper()` 함수 시그니처 확장
   - Entry BPS Profile 통합
   - 루프 내에서 동적 Entry BPS 생성

---

## 사용 예시 (Usage Examples)

### 1. Fixed 모드 (기존 동작)
```bash
python scripts/run_d84_2_calibrated_fill_paper.py \
  --duration-seconds 1800 \
  --l2-source real \
  --fillmodel-mode advisory \
  --calibration-path logs/d86-1/calibration_20251207_123906.json
```
→ Entry BPS 10.0bps 고정 (기본값)

### 2. Cycle 모드 (Zone별 순환)
```bash
python scripts/run_d84_2_calibrated_fill_paper.py \
  --duration-seconds 1800 \
  --l2-source real \
  --fillmodel-mode advisory \
  --calibration-path logs/d86-1/calibration_20251207_123906.json \
  --entry-bps-mode cycle \
  --entry-bps-min 5.0 \
  --entry-bps-max 25.0
```
→ Z1(6.0) → Z2(9.5) → Z3(16.0) → Z4(25.0) 순환

### 3. Random 모드 (균일 분포)
```bash
python scripts/run_d84_2_calibrated_fill_paper.py \
  --duration-seconds 1800 \
  --l2-source real \
  --fillmodel-mode strict \
  --calibration-path logs/d86-1/calibration_20251207_123906.json \
  --entry-bps-mode random \
  --entry-bps-min 5.0 \
  --entry-bps-max 25.0 \
  --entry-bps-seed 42
```
→ 5.0~25.0 범위 균일 분포 난수 (seed=42로 재현 가능)

### 4. Zone 분포 분석
```bash
python scripts/d88_0_analyze_zone_distribution.py \
  logs/d87-5/d87_5_advisory_30m/fill_events_*.jsonl
```
→ Zone 분포 및 Acceptance Criteria 자동 검증

---

## 검증 결과 요약 (Validation Summary)

| Item | Target | Result | Status |
|------|--------|--------|--------|
| **Unit Test** | 11개 | 11 passed | ✅ PASS |
| **Short PAPER** | Zone 분산 | Z1~Z4 각 25% | ✅ PASS |
| **C1: All Zones Covered** | Z1~Z4 ≥ 1개 | Z1~Z4 각 3개 | ✅ PASS |
| **C2: No Z2 Dominance** | Z2 < 90% | Z2 = 25% | ✅ PASS |
| **C3: Low Unmatched Rate** | Unmatched < 5% | 0% | ✅ PASS |
| **회귀 테스트** | 103개 | 103 passed | ✅ PASS |

---

## 알려진 한계 (Known Limitations)

1. **TP BPS 고정**
   - 현재 TP는 12.0bps로 고정
   - 필요 시 D88-1에서 TP Profile 추가 가능

2. **Zone 경계 하드코딩 없음**
   - Calibration JSON에서 자동 추출하므로, Zone 정의 변경 시 자동 반영
   - 다만, Calibration이 없으면 동작 불가

3. **D87-6 재실행 필요**
   - 이번 단계는 인프라 구현만 완료
   - Advisory vs Strict 30m A/B 재검증은 별도 실행 필요 (D88-1 권장)

---

## Next Steps

### D88-1: Advisory vs Strict 30m A/B 재검증 (HIGH Priority)
- **목표:** Entry BPS Diversification 적용 후 Zone Selection 효과 재검증
- **실행:** 
  ```bash
  # Advisory 30m
  python scripts/run_d84_2_calibrated_fill_paper.py \
    --duration-seconds 1800 \
    --l2-source real \
    --fillmodel-mode advisory \
    --calibration-path logs/d86-1/calibration_20251207_123906.json \
    --entry-bps-mode cycle \
    --entry-bps-min 5.0 \
    --entry-bps-max 25.0 \
    --session-tag d88_1_advisory_30m
  
  # Strict 30m
  python scripts/run_d84_2_calibrated_fill_paper.py \
    --duration-seconds 1800 \
    --l2-source real \
    --fillmodel-mode strict \
    --calibration-path logs/d86-1/calibration_20251207_123906.json \
    --entry-bps-mode cycle \
    --entry-bps-min 5.0 \
    --entry-bps-max 25.0 \
    --session-tag d88_1_strict_30m
  
  # 분석
  python scripts/d87_5_zone_selection_short_validation.py --duration-minutes 30
  ```
- **예상:** ΔP(Z2) ≥ 5%p (D87-6에서 0%p → 5%p 이상 개선)

### D88-2: TP BPS Diversification (OPTIONAL)
- **목표:** TP도 다양화하여 Zone 매칭 정확도 향상
- **구현:** `TPBPSProfile` 클래스 추가 (Entry BPS Profile 패턴 재사용)

### D87-3_LONGRUN_VALIDATION: 3h+3h 실행 (MEDIUM Priority)
- **조건:** D88-1 완료 후 (Zone Selection 효과 확인 후)
- **환경:** 서버 환경 (로컬 환경에서 3시간 실행 부담)

---

## 결론 (Conclusion)

D88-0에서 Entry BPS Diversification 인프라를 성공적으로 구현하고 검증했다. Zone별 트레이드 분산이 정확히 작동하며 (Z1~Z4 각 25%), 기존 테스트에 대한 회귀 없이 11개 신규 테스트가 추가되었다.

**핵심 성과:**
- ✅ Entry BPS Profile 클래스 구현 (fixed/cycle/random 모드)
- ✅ PAPER Runner 통합 (CLI 인자 4개 추가)
- ✅ Zone 분포 검증 도구 구현
- ✅ Unit Test 11/11 PASS
- ✅ Short PAPER Zone 분산 검증 (Z1~Z4 각 25%)
- ✅ 전체 회귀 테스트 103/103 PASS

**다음 단계:**
- D88-1: Advisory vs Strict 30m A/B 재검증으로 Zone Preference 효과 실증

---

**Status:** ✅ **D88-0 COMPLETE** - Entry BPS Diversification 인프라 구축 완료
