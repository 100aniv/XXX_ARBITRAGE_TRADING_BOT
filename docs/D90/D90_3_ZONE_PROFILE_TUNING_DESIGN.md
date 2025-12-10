# D90-3: Zone Profile Tuning v1 - Design Document

**작성일:** 2025-12-10  
**Status:** 🚧 **IN PROGRESS**  
**목표:** PnL 최적화를 위한 Zone Profile 후보 설계 및 20m SHORT PAPER 검증

---

## 1. 배경: D88~D90-2 흐름 요약

### 1.1 D88-0/D89-0: Entry BPS 지배 구조 문제
- **문제:** Entry BPS가 Zone Preference보다 우선순위가 높아, Zone 선택이 무력화됨
- **증상:** Advisory 모드에서도 Z2 비중이 Strict와 차이 없음 (ΔP(Z2) ≈ 0%p)

### 1.2 D90-0: zone_random 모드 도입
- **해결책:** Entry BPS 생성 단계에서 Zone 가중치 반영
  - 2단계 샘플링: Zone 선택 → Zone 내 BPS 샘플링
  - zone_weights로 Zone 선택 확률 조정
- **30m A/B 결과:**
  - ΔP(Z2) = 22.8%p (목표 ≥5%p의 4.6배 달성)
  - Advisory Z2: 52.8%, Strict Z2: 30.0%
  - PnL: Advisory $8.06 > Strict $6.54 (+23%)

### 1.3 D90-1: 3h LONGRUN 검증
- **목표:** 장기 안정성 및 샘플 사이즈 확대
- **3h A/B 결과:**
  - ΔP(Z2) = 27.2%p (목표 ≥15%p의 1.8배 달성)
  - Advisory Z2: 51.5%, Strict Z2: 24.3%
  - 샘플 사이즈: 1,079 trades (30m 대비 6배)
  - **핵심 발견:** Z2-heavy 전략이 장기적으로도 안정적

### 1.4 D90-2: Zone Profile 구조화
- **목표:** zone_weights를 명명된 프로파일로 관리
- **구현:**
  - `ZoneProfile` dataclass + `ZONE_PROFILES` dict
  - 기본 프로파일 2개:
    - `strict_uniform`: (1.0, 1.0, 1.0, 1.0) → Z1~Z4 균등 (≈25%)
    - `advisory_z2_focus`: (0.5, 3.0, 1.5, 0.5) → Z2 집중 (≈50%)
  - CLI 연동: `--entry-bps-zone-profile`
- **20m A/B 결과:**
  - ΔP(Z2) = 23.3%p (목표 ≥15%p의 1.6배 달성)
  - Advisory Z2: 50.0%, Strict Z2: 26.7%
  - **PnL: Advisory $5.30 > Strict $4.27 (+24%)**

### 1.5 D90-0/1/2 공통 패턴
| Milestone | Duration | ΔP(Z2) | Advisory Z2 | Strict Z2 | PnL Uplift |
|-----------|----------|--------|-------------|-----------|------------|
| D90-0 | 30m | 22.8%p | 52.8% | 30.0% | +23% |
| D90-1 | 3h | 27.2%p | 51.5% | 24.3% | N/A |
| D90-2 | 20m | 23.3%p | 50.0% | 26.7% | **+24%** |

**일관성:**
- ΔP(Z2) 항상 ≥15%p 달성
- Advisory Z2 비중 50~53% 범위 (안정적)
- **PnL Uplift 20~25% 범위 (재현 가능)**

---

## 2. AS-IS: 현재 Zone Profile 현황

### 2.1 strict_uniform (Baseline)
```python
zone_weights=(1.0, 1.0, 1.0, 1.0)
```
- **목적:** Strict 모드 기준선, Zone 균등 분포
- **실제 분포 (D90-2 20m):**
  - Z1: 17.5%, Z2: 26.7%, Z3: 26.7%, Z4: 29.2%
  - 균등 분포 (25% ± 5%p) 달성 ✅
- **PnL:** $4.27 (20m, 120 trades)
- **역할:** Strict 모드 기준선, 변경 금지

### 2.2 advisory_z2_focus (Current Best)
```python
zone_weights=(0.5, 3.0, 1.5, 0.5)
```
- **목적:** Advisory 모드 기본 프로파일, Z2 집중
- **실제 분포 (D90-2 20m):**
  - Z1: 7.5%, Z2: 50.0%, Z3: 31.7%, Z4: 10.8%
  - Z2 집중 (50%) 달성 ✅
- **PnL:** $5.30 (20m, 120 trades, **+24% vs Strict**)
- **역할:** Advisory 모드 기준선, 변경 금지

### 2.3 AS-IS 한계
1. **Z2 집중도 고정:** advisory_z2_focus는 Z2에 50% 집중
   - Z3 비중이 31.7%로 높은데, 이게 최적인지 불명확
   - Z1/Z4 비중이 7~11%로 낮음 (Tail 이벤트 커버 부족 가능성)

2. **PnL 최적화 미검증:**
   - D90-0/1/2는 ΔP(Z2) ≥ 15%p 달성에 집중
   - PnL 최적화는 부수적 효과로만 관찰됨
   - "Z2 집중 = PnL 최대화"인지 검증 필요

3. **Zone 간 균형 미탐색:**
   - Z2+Z3 조합 최적화 가능성
   - Z1/Z4 Tail 이벤트 활용 가능성

---

## 3. TO-BE: D90-3 Zone Profile 후보 설계

### 3.1 설계 철학
1. **ΔP(Z2) ≥ 15%p 유지:** D90-0/1/2에서 검증된 기준선
2. **PnL 최적화 탐색:** Zone 분포 조정으로 PnL 개선 가능성 탐색
3. **Zone 균형 고려:** Z1/Z4 Tail 이벤트 커버, Z2/Z3 조합 최적화
4. **점진적 튜닝:** 극단적 변경 회피, 기존 프로파일 대비 ±20% 범위 내 조정

### 3.2 후보 프로파일 정의

#### Profile 1: advisory_z2_balanced
```python
zone_weights=(0.7, 2.5, 2.0, 0.8)
```

**설계 의도:**
- Z2 집중도를 약간 낮추고 (3.0 → 2.5), Z3 비중을 높임 (1.5 → 2.0)
- Z1/Z4 비중을 소폭 증가 (0.5 → 0.7/0.8)
- **가설:** Z2 과도 집중을 완화하고 Z3 기회 활용 → PnL 개선

**예상 분포:**
- 정규화 가중치: [0.7, 2.5, 2.0, 0.8] / 6.0 = [11.7%, 41.7%, 33.3%, 13.3%]
- Z2: 41.7% (advisory_z2_focus 50.0% 대비 -8.3%p)
- Z3: 33.3% (advisory_z2_focus 31.7% 대비 +1.6%p)
- Z1/Z4: 11.7% / 13.3% (advisory_z2_focus 7.5% / 10.8% 대비 증가)

**기대 효과:**
- ΔP(Z2) ≥ 15%p 유지 (41.7% vs Strict 26.7% = 15.0%p)
- Z3 비중 증가로 중위험/중수익 기회 활용
- Z1/Z4 Tail 이벤트 커버 개선 (7~11% → 11~13%)
- **PnL 목표:** Advisory_z2_focus 대비 +5~10% (Strict 대비 +30~35%)

#### Profile 2: advisory_z23_focus
```python
zone_weights=(0.3, 2.8, 2.2, 0.3)
```

**설계 의도:**
- Z2+Z3에 집중 (Z2: 2.8, Z3: 2.2)
- Z1/Z4를 최소화 (0.3)
- **가설:** 중위험/중수익 Zone(Z2+Z3)에 집중 → PnL 최대화

**예상 분포:**
- 정규화 가중치: [0.3, 2.8, 2.2, 0.3] / 5.6 = [5.4%, 50.0%, 39.3%, 5.4%]
- Z2: 50.0% (advisory_z2_focus와 동일)
- Z3: 39.3% (advisory_z2_focus 31.7% 대비 +7.6%p)
- Z1/Z4: 5.4% (advisory_z2_focus 7.5% / 10.8% 대비 감소)

**기대 효과:**
- ΔP(Z2) ≥ 15%p 유지 (50.0% vs Strict 26.7% = 23.3%p)
- Z3 비중 대폭 증가로 중위험/중수익 기회 최대 활용
- Z1/Z4 Tail 이벤트 최소화 (리스크 회피)
- **PnL 목표:** Advisory_z2_focus 대비 +10~15% (Strict 대비 +35~40%)

#### Profile 3: advisory_z2_conservative
```python
zone_weights=(1.0, 2.0, 1.8, 1.0)
```

**설계 의도:**
- Z2 집중도를 크게 낮춤 (3.0 → 2.0)
- 모든 Zone에 최소 1.0 이상 배정 (균형 중시)
- **가설:** Zone 분산으로 리스크 완화 → 안정적 PnL

**예상 분포:**
- 정규화 가중치: [1.0, 2.0, 1.8, 1.0] / 5.8 = [17.2%, 34.5%, 31.0%, 17.2%]
- Z2: 34.5% (advisory_z2_focus 50.0% 대비 -15.5%p)
- Z3: 31.0% (advisory_z2_focus 31.7% 대비 -0.7%p)
- Z1/Z4: 17.2% (advisory_z2_focus 7.5% / 10.8% 대비 대폭 증가)

**기대 효과:**
- ΔP(Z2) ≥ 15%p 유지 가능성 낮음 (34.5% vs Strict 26.7% = 7.8%p ❌)
- **리스크:** ΔP(Z2) < 15%p 시 D90-3 FAIL 가능성
- Zone 분산으로 안정성 증가 (변동성 감소)
- **PnL 목표:** Advisory_z2_focus 대비 -5~0% (안정성 우선)

### 3.3 후보 프로파일 요약

| Profile | Z1 | Z2 | Z3 | Z4 | 예상 Z2 | 예상 ΔP(Z2) | PnL 목표 | 리스크 |
|---------|----|----|----|----|---------|-------------|----------|--------|
| **advisory_z2_focus** (Baseline) | 0.5 | 3.0 | 1.5 | 0.5 | 50.0% | 23.3%p | $5.30 | 낮음 |
| **advisory_z2_balanced** | 0.7 | 2.5 | 2.0 | 0.8 | 41.7% | 15.0%p | +5~10% | 중간 |
| **advisory_z23_focus** | 0.3 | 2.8 | 2.2 | 0.3 | 50.0% | 23.3%p | +10~15% | 중간 |
| **advisory_z2_conservative** | 1.0 | 2.0 | 1.8 | 1.0 | 34.5% | 7.8%p ❌ | -5~0% | 높음 |

**권장 우선순위:**
1. **advisory_z2_balanced** (중위험/중수익, ΔP(Z2) 경계선)
2. **advisory_z23_focus** (Z2+Z3 집중, PnL 최대화 시도)
3. **advisory_z2_conservative** (보수적, ΔP(Z2) 리스크 높음)

---

## 4. 평가 기준 (D90-3 Acceptance Criteria)

### AC1: Unit Test 전부 PASS ✅
- 기존 D90-0/2 테스트: 25/25 PASS 유지
- D90-3 신규 테스트: 신규 프로파일 검증 PASS

### AC2: ΔP(Z2) ≥ 15%p 유지 ✅
- **Critical:** 최소 1개 이상의 신규 프로파일이 ΔP(Z2) ≥ 15%p 달성
- 측정: Advisory Z2% - Strict Z2% (Strict 기준선: 26.7%)

### AC3: PnL Uplift ≥ +5% ✅
- **High Priority:** 최소 1개 이상의 신규 프로파일이 Strict 대비 PnL ≥ +5% 달성
- 측정: (Advisory PnL - Strict PnL) / Strict PnL × 100%
- Strict 기준선: $4.27 (20m, 120 trades)

### AC4: Zone 분포 균형 ✅
- Z2 비중: 40~55% 범위 (너무 극단적이지 않게)
- Z1/Z4 비중: 각각 5% 이상 (Tail 이벤트 커버)
- Z3 비중: 25% 이상 (중위험/중수익 기회 활용)

### AC5: 실행 로그 정리 ✅
- 로그 디렉터리: `logs/d87-3/d90_3_<profile>_<mode>_run<idx>/`
- 요약 파일: `logs/d87-3/d90_3_profile_sweep/summary.json` + `summary.md`
- 프로파일별 KPI, Zone 분포, ΔP(Z2), PnL 정리

### AC6: Duration 정확도 ✅
- 각 실행: 1200초 ± 5초 이내

### AC7: Fatal Error 0건 ✅
- 모든 실행에서 치명적 예외 없음

---

## 5. 실행 계획 (D90-3 Validation Phase)

### 5.1 Phase 1: Strict 기준선 확인 (Optional)
- **목적:** Strict 기준선 재확인 (D90-2와 일관성 유지)
- **실행:**
  - Profile: `strict_uniform`
  - Duration: 1200초 (20m)
  - Repeat: 1회
- **기대 결과:**
  - Z2: 25% ± 5%p
  - PnL: $4~5 범위

### 5.2 Phase 2: Advisory 프로파일 실험
- **목적:** 신규 프로파일 3개 + 기준선 1개 비교
- **실행:**
  - Profiles:
    1. `advisory_z2_focus` (Baseline, 재확인)
    2. `advisory_z2_balanced` (신규)
    3. `advisory_z23_focus` (신규)
    4. `advisory_z2_conservative` (신규, 리스크 높음)
  - Duration: 1200초 (20m)
  - Repeat: 각 2회 (seed/time offset 변경)
  - Total: 4 profiles × 2 runs = 8 runs
- **기대 결과:**
  - 최소 1개 프로파일이 AC2~AC4 동시 만족
  - Best Profile 선정

### 5.3 Phase 3: 결과 분석 및 리포트
- **산출물:**
  - `logs/d87-3/d90_3_profile_sweep/summary.json`
  - `logs/d87-3/d90_3_profile_sweep/summary.md`
  - `docs/D90/D90_3_VALIDATION_REPORT.md`
- **내용:**
  - 프로파일별 Zone 분포 / ΔP(Z2) / PnL 표
  - Best Profile 선정 및 이유
  - 리스크/한계 (20m만 테스트, 1h/3h 필요 등)

---

## 6. 구현 범위

### 6.1 수정 파일
- `arbitrage/domain/entry_bps_profile.py`
  - `ZONE_PROFILES` dict에 신규 프로파일 3개 추가
  - 기존 프로파일 (`strict_uniform`, `advisory_z2_focus`) 변경 금지

### 6.2 신규 파일
- `scripts/run_d90_3_zone_profile_sweep.py`
  - Zone Profile 일괄 실행 스크립트
  - 입력: `--profiles`, `--duration`, `--mode`, `--repeat`
  - 출력: 프로파일별 KPI/Zone 분포 요약
- `tests/test_d90_3_zone_profile_tuning.py`
  - 신규 프로파일 검증 (zone_weights 양수, 합 > 0)
  - Sweep 스크립트 핵심 함수 검증

### 6.3 문서
- `docs/D90/D90_3_ZONE_PROFILE_TUNING_DESIGN.md` (본 문서)
- `docs/D90/D90_3_VALIDATION_REPORT.md` (실행 후 작성)

---

## 7. 리스크 및 한계

### 7.1 리스크
1. **ΔP(Z2) < 15%p 가능성:**
   - `advisory_z2_conservative`는 ΔP(Z2) = 7.8%p 예상 (FAIL 가능성)
   - 완화: 우선순위를 낮추고, PASS 조건에서 제외 가능

2. **PnL 변동성:**
   - 20m 샘플 사이즈 (120 trades)는 PnL 변동성이 클 수 있음
   - 완화: 각 프로파일당 2회 실행으로 평균/표준편차 확인

3. **Zone 분포 편차:**
   - 예상 분포와 실제 분포 차이 (±5~10%p 가능)
   - 완화: 범위 기준 (예: Z2 40~55%) 적용

### 7.2 한계
1. **SHORT PAPER 한계:**
   - 20m × 2회는 통계적 유의성이 낮음
   - D90-4/5에서 1h/3h LONGRUN 필요

2. **Calibration 고정:**
   - D86-1 Calibration 사용 (2025-12-07 생성)
   - 시장 변동성 변화 시 재검증 필요

3. **단일 심볼:**
   - BTC/KRW 단일 심볼만 테스트
   - Multi-Symbol 환경에서 재검증 필요

---

## 8. Next Steps (D90-3 이후)

### D90-4: YAML 외부화 (Optional)
- 프로파일 정의를 `config/zone_profiles.yaml`로 외부화
- 코드 수정 없이 프로파일 추가/변경 가능

### D90-5: TopN Arbitrage 통합
- Multi-Symbol 환경에서 Zone Profile 적용
- 심볼별 독립적인 프로파일 선택

### D91+: Production PAPER
- 6~12h LONGRUN 검증
- Best Profile 선정 후 장기 안정성 확인
- LIVE 연동 준비

---

**작성:** Windsurf AI (D90-3 Design Phase)  
**최종 업데이트:** 2025-12-10 11:30 KST
