# D90-3: Zone Profile Tuning v1 - Validation Report

**작성일:** 2025-12-10  
**Status:** ✅ **PASS (CONDITIONAL)**  
**실행 시간:** 약 2.7시간 (8 runs × 20m)

---

## 1. 목적

D90-0/1/2에서 완성한 `zone_random` + `ZoneProfile` 레이어 위에, **PnL 최적화**를 위한 Zone Profile 후보들을 설계하고 20m SHORT PAPER로 검증.

**핵심 질문:**
- Q1. 기존 `advisory_z2_focus` (Z2 50%) 대비 PnL을 개선할 수 있는 프로파일이 존재하는가?
- Q2. ΔP(Z2) ≥ 15%p 기준을 유지하면서 PnL을 최적화할 수 있는가?
- Q3. Zone 분산(Z1/Z4 Tail 커버)과 PnL의 트레이드오프는 어떤가?

---

## 2. 실행 조건

### 2.1 공통 설정
- **Duration:** 1200초 (20분)
- **Mode:** Advisory
- **Calibration:** `logs/d86-1/calibration_20251207_123906.json` (D86-1)
- **Entry BPS Mode:** `zone_random`
- **Entry BPS Range:** 5.0~25.0 BPS
- **L2 Source:** Real (Upbit WebSocket)
- **Repeat:** 각 프로파일당 2회 (seed offset: 91, 92)

### 2.2 테스트 프로파일 (4개)

| Profile | Zone Weights | 예상 Z2% | 예상 PnL 목표 | 리스크 |
|---------|--------------|----------|---------------|--------|
| **advisory_z2_focus** (Baseline) | (0.5, 3.0, 1.5, 0.5) | 50% | $5.30 | 낮음 |
| **advisory_z2_balanced** | (0.7, 2.5, 2.0, 0.8) | 42% | +5~10% | 중간 |
| **advisory_z23_focus** | (0.3, 2.8, 2.2, 0.3) | 50% | +10~15% | 중간 |
| **advisory_z2_conservative** | (1.0, 2.0, 1.8, 1.0) | 35% | -5~0% | 높음 |

### 2.3 Strict 기준선 (D90-2)
- **Profile:** `strict_uniform` (1.0, 1.0, 1.0, 1.0)
- **Z2:** 26.7%
- **PnL:** $4.27 (20m, 120 trades)

---

## 3. 실행 결과

### 3.1 KPI 요약

| Profile | Runs | PnL (mean ± std) | vs Strict | vs Baseline | Trades | Duration |
|---------|------|------------------|-----------|-------------|--------|----------|
| **Strict (D90-2)** | 1 | **$4.27** | - | -19.3% | 120 | 1200.6s |
| **advisory_z2_focus** (Baseline) | 2 | **$5.29 ± $0.11** | **+23.9%** | - | 120 | 1200.6s |
| **advisory_z23_focus** | 2 | **$5.12 ± $0.02** | **+19.9%** | **-3.2%** | 120 | 1200.6s |
| **advisory_z2_balanced** | 2 | **$4.76 ± $0.05** | **+11.5%** | **-10.0%** | 120 | 1200.5s |
| **advisory_z2_conservative** | 2 | **$4.62 ± $0.02** | **+8.2%** | **-12.7%** | 120 | 1200.5s |

**관찰:**
- ✅ **모든 Advisory 프로파일이 Strict 대비 PnL 개선** (+8.2% ~ +23.9%)
- ⚠️ **신규 프로파일 중 Baseline 대비 PnL 개선한 것은 없음**
- ✅ **advisory_z23_focus가 Baseline 대비 -3.2%로 가장 근접** (통계적 유의성 낮음)
- ❌ **advisory_z2_balanced, advisory_z2_conservative는 Baseline 대비 -10% 이상 하락**

### 3.2 Zone 분포 결과

| Profile | Z1% | Z2% | Z3% | Z4% | ΔP(Z2) vs Strict |
|---------|-----|-----|-----|-----|------------------|
| **Strict (D90-2)** | 17.5% | **26.7%** | 26.7% | 29.2% | - |
| **advisory_z2_focus** (Baseline) | 5.0% | **50.8%** | 35.4% | 8.8% | **+24.1%p** ✅ |
| **advisory_z23_focus** | 1.2% | **46.2%** | 46.7% | 5.8% | **+19.5%p** ✅ |
| **advisory_z2_balanced** | 7.5% | **37.9%** | 37.9% | 16.7% | **+11.2%p** ❌ |
| **advisory_z2_conservative** | 10.0% | **35.0%** | 33.3% | 21.7% | **+8.3%p** ❌ |

**관찰:**
- ✅ **advisory_z2_focus, advisory_z23_focus만 ΔP(Z2) ≥ 15%p 달성**
- ❌ **advisory_z2_balanced, advisory_z2_conservative는 ΔP(Z2) < 15%p (FAIL)**
- 📊 **Z2 비중과 PnL 간 강한 양의 상관관계** (R² ≈ 0.95)
- 📊 **Z1/Z4 Tail 커버 증가 → PnL 감소** (분산 증가 = 성능 저하)

### 3.3 상세 실행 결과

#### advisory_z2_focus (Baseline)
**Run 1:**
- PnL: $5.37, Trades: 120, Duration: 1200.6s
- Zone: Z1=3.3%, Z2=52.5%, Z3=35.8%, Z4=8.3%

**Run 2:**
- PnL: $5.21, Trades: 120, Duration: 1200.5s
- Zone: Z1=6.7%, Z2=49.2%, Z3=35.0%, Z4=9.2%

**평균:** PnL $5.29 ± $0.11, Z2 50.8%

---

#### advisory_z23_focus (신규, Best Candidate)
**Run 1:**
- PnL: $5.13, Trades: 120, Duration: 1200.6s
- Zone: Z1=0.0%, Z2=46.7%, Z3=47.5%, Z4=5.8%

**Run 2:**
- PnL: $5.10, Trades: 120, Duration: 1200.5s
- Zone: Z1=2.5%, Z2=45.8%, Z3=45.8%, Z4=5.8%

**평균:** PnL $5.12 ± $0.02, Z2 46.2%, Z3 46.7%

**특징:**
- Z2+Z3 집중 (92.9%), Z1/Z4 최소화 (7.1%)
- Baseline 대비 -3.2% PnL (통계적 유의성 낮음, std 0.02)
- ΔP(Z2) +19.5%p (AC2 PASS ✅)

---

#### advisory_z2_balanced (신규)
**Run 1:**
- PnL: $4.72, Trades: 120, Duration: 1200.5s
- Zone: Z1=6.7%, Z2=37.5%, Z3=38.3%, Z4=17.5%

**Run 2:**
- PnL: $4.79, Trades: 120, Duration: 1200.6s
- Zone: Z1=8.3%, Z2=38.3%, Z3=37.5%, Z4=15.8%

**평균:** PnL $4.76 ± $0.05, Z2 37.9%

**특징:**
- Z1/Z4 Tail 커버 증가 (24.2%)
- Baseline 대비 -10.0% PnL (유의미한 하락)
- ΔP(Z2) +11.2%p (AC2 FAIL ❌)

---

#### advisory_z2_conservative (신규)
**Run 1:**
- PnL: $4.64, Trades: 120, Duration: 1200.5s
- Zone: Z1=9.2%, Z2=35.0%, Z3=34.2%, Z4=21.7%

**Run 2:**
- PnL: $4.60, Trades: 120, Duration: 1200.5s
- Zone: Z1=10.8%, Z2=35.0%, Z3=32.5%, Z4=21.7%

**평균:** PnL $4.62 ± $0.02, Z2 35.0%

**특징:**
- 가장 균형 잡힌 분포 (Z1~Z4 모두 10% 이상)
- Baseline 대비 -12.7% PnL (가장 큰 하락)
- ΔP(Z2) +8.3%p (AC2 FAIL ❌)

---

## 4. Acceptance Criteria 검증

### AC1: Unit Test 전부 PASS ✅
- 기존 D90-0/2 테스트: 25/25 PASS
- D90-3 신규 테스트: 16/16 PASS
- **Total: 41/41 PASS** ✅

### AC2: ΔP(Z2) ≥ 15%p 유지 ⚠️
- **advisory_z2_focus:** +24.1%p ✅
- **advisory_z23_focus:** +19.5%p ✅
- **advisory_z2_balanced:** +11.2%p ❌
- **advisory_z2_conservative:** +8.3%p ❌

**판정:** 2/4 프로파일 PASS (50%) → **CONDITIONAL PASS** ⚠️

### AC3: PnL Uplift ≥ +5% (vs Strict) ✅
- **advisory_z2_focus:** +23.9% ✅
- **advisory_z23_focus:** +19.9% ✅
- **advisory_z2_balanced:** +11.5% ✅
- **advisory_z2_conservative:** +8.2% ✅

**판정:** 4/4 프로파일 PASS (100%) → **PASS** ✅

### AC4: Zone 분포 균형 ⚠️
**기준:**
- Z2 비중: 40~55% 범위
- Z1/Z4 비중: 각각 5% 이상
- Z3 비중: 25% 이상

| Profile | Z2 (40~55%) | Z1 (≥5%) | Z4 (≥5%) | Z3 (≥25%) | 판정 |
|---------|-------------|----------|----------|-----------|------|
| advisory_z2_focus | 50.8% ✅ | 5.0% ✅ | 8.8% ✅ | 35.4% ✅ | **PASS** ✅ |
| advisory_z23_focus | 46.2% ✅ | 1.2% ❌ | 5.8% ✅ | 46.7% ✅ | **FAIL** ❌ |
| advisory_z2_balanced | 37.9% ❌ | 7.5% ✅ | 16.7% ✅ | 37.9% ✅ | **FAIL** ❌ |
| advisory_z2_conservative | 35.0% ❌ | 10.0% ✅ | 21.7% ✅ | 33.3% ✅ | **FAIL** ❌ |

**판정:** 1/4 프로파일 PASS (25%) → **CONDITIONAL PASS** ⚠️

### AC5: 실행 로그 정리 ✅
- 로그 디렉터리: `logs/d87-3/d90_3_*` (8개 디렉터리)
- 요약 파일: `logs/d87-3/d90_3_profile_sweep/summary.json`, `summary.md`
- 프로파일별 KPI, Zone 분포 정리 완료

**판정:** **PASS** ✅

### AC6: Duration 정확도 ✅
- 모든 실행: 1200.5~1200.6초 (±0.6초 이내)
- 목표 ±5초 이내 달성

**판정:** **PASS** ✅

### AC7: Fatal Error 0건 ✅
- 8/8 실행 성공, 0건 실패

**판정:** **PASS** ✅

---

## 5. 핵심 발견 (Key Findings)

### 5.1 Z2 집중도와 PnL의 강한 양의 상관관계
- **R² ≈ 0.95** (Z2% vs PnL)
- Z2 50% → PnL $5.29
- Z2 46% → PnL $5.12 (-3.2%)
- Z2 38% → PnL $4.76 (-10.0%)
- Z2 35% → PnL $4.62 (-12.7%)

**결론:** **Z2 집중도가 PnL의 가장 강력한 예측 변수**

### 5.2 Zone 분산 증가 → PnL 감소
- Z1/Z4 Tail 커버 증가 (7% → 24%) → PnL -10%
- 균형 잡힌 분포 (Z1~Z4 모두 10% 이상) → PnL -12.7%

**결론:** **Zone 분산은 PnL에 부정적 영향** (Tail 이벤트 커버 < Z2 집중)

### 5.3 advisory_z23_focus의 잠재력
- Z2+Z3 집중 (92.9%) → PnL $5.12
- Baseline 대비 -3.2% (std 0.02, 통계적 유의성 낮음)
- Z3 비중 증가 (35% → 47%) → PnL 소폭 하락

**결론:** **Z3 비중 증가는 PnL 개선에 기여하지 않음** (Z2 > Z3)

### 5.4 Baseline (advisory_z2_focus)의 최적성
- D90-0/1/2에서 일관되게 최고 성능
- D90-3에서도 4개 프로파일 중 최고 PnL ($5.29)
- Zone 분포 균형 (AC4 유일 PASS)

**결론:** **advisory_z2_focus는 현재 최적 프로파일** (변경 불필요)

---

## 6. 결론

### 6.1 D90-3 Acceptance Criteria 종합 판정

| AC | 기준 | 결과 | 판정 |
|----|------|------|------|
| AC1 | Unit Test 전부 PASS | 41/41 PASS | ✅ PASS |
| AC2 | ΔP(Z2) ≥ 15%p | 2/4 프로파일 PASS | ⚠️ CONDITIONAL |
| AC3 | PnL Uplift ≥ +5% | 4/4 프로파일 PASS | ✅ PASS |
| AC4 | Zone 분포 균형 | 1/4 프로파일 PASS | ⚠️ CONDITIONAL |
| AC5 | 실행 로그 정리 | 완료 | ✅ PASS |
| AC6 | Duration 정확도 | ±0.6초 | ✅ PASS |
| AC7 | Fatal Error 0건 | 0건 | ✅ PASS |

**최종 판정:** ✅ **PASS (CONDITIONAL)**

**이유:**
- Critical AC (AC1, AC3, AC5, AC6, AC7) 모두 PASS ✅
- High Priority AC (AC2, AC4) 일부 PASS ⚠️
- **신규 프로파일 중 Baseline 대비 PnL 개선한 것은 없음**
- **하지만 Z2 집중도와 PnL의 강한 상관관계를 검증** (R² ≈ 0.95)

### 6.2 Best Profile 선정

**Winner:** **advisory_z2_focus** (Baseline 유지)

**이유:**
1. 최고 PnL: $5.29 (Strict 대비 +23.9%)
2. ΔP(Z2) +24.1%p (목표 ≥15%p의 1.6배)
3. Zone 분포 균형 (AC4 유일 PASS)
4. D90-0/1/2에서 일관된 최고 성능

**Runner-up:** **advisory_z23_focus**

**이유:**
1. Baseline 대비 -3.2% (통계적 유의성 낮음)
2. ΔP(Z2) +19.5%p (AC2 PASS)
3. Z2+Z3 집중 전략의 가능성 확인
4. 1h/3h LONGRUN에서 재검증 필요

### 6.3 권장 사항

#### 단기 (D90-4/5)
1. **advisory_z2_focus를 Production 기본 프로파일로 유지**
2. **advisory_z23_focus를 실험적 프로파일로 보존** (YAML 외부화 시 포함)
3. **advisory_z2_balanced, advisory_z2_conservative 제거 고려** (PnL/ΔP(Z2) 모두 미달)

#### 중기 (D91+)
1. **1h/3h LONGRUN에서 advisory_z23_focus 재검증**
   - 20m 샘플 사이즈 (120 trades)는 통계적 유의성 낮음
   - 1h (360 trades) 이상에서 Baseline 대비 성능 재평가
2. **Z2 집중도 미세 조정 (2.8~3.2 범위)**
   - Z2 가중치 3.0 → 3.1/3.2 실험
   - Z3 가중치 1.5 → 1.3/1.4 실험
3. **Multi-Symbol 환경에서 프로파일별 성능 비교**
   - 심볼별 최적 프로파일 탐색
   - TopN Arbitrage 통합 시 프로파일 선택 로직

---

## 7. 리스크 및 한계

### 7.1 리스크
1. **SHORT PAPER 한계 (20m × 2회)**
   - 샘플 사이즈 작음 (120 trades/run)
   - PnL 변동성 높음 (std $0.02~$0.11)
   - 통계적 유의성 낮음 (특히 advisory_z23_focus -3.2%)

2. **단일 Calibration 의존**
   - D86-1 Calibration (2025-12-07) 고정
   - 시장 변동성 변화 시 재검증 필요

3. **단일 심볼 (BTC/KRW)**
   - Multi-Symbol 환경에서 성능 미검증
   - 심볼별 최적 프로파일 다를 수 있음

### 7.2 한계
1. **Z2 집중도 외 변수 미탐색**
   - Z3 가중치 미세 조정 (1.3~1.7 범위)
   - Z1/Z4 가중치 조합 최적화
   - Bayesian Optimization 미적용

2. **PnL 변동성 원인 미분석**
   - 왜 Z2 집중도가 PnL과 강한 상관관계를 갖는가?
   - Z3 비중 증가가 PnL에 부정적인 이유는?
   - Fill Ratio, Spread, Latency 등 세부 메트릭 분석 필요

3. **20m 단위 성능 변동성**
   - 동일 프로파일도 run1/run2 간 PnL 차이 (최대 $0.16)
   - 시간대/시장 상황에 따른 성능 변화 가능성

---

## 8. Next Steps

### D90-4: YAML 외부화 (Optional)
- 프로파일 정의를 `config/zone_profiles.yaml`로 외부화
- 코드 수정 없이 프로파일 추가/변경 가능
- advisory_z2_focus, advisory_z23_focus만 포함

### D91: Production PAPER (6~12h LONGRUN)
- advisory_z2_focus 기본 프로파일로 6~12h 검증
- advisory_z23_focus 실험적 프로파일로 병렬 검증
- 장기 안정성, PnL 일관성, ΔP(Z2) 유지 확인

### D92+: Multi-Symbol 통합
- TopN Arbitrage에 Zone Profile 적용
- 심볼별 독립적인 프로파일 선택
- 포트폴리오 레벨 PnL 최적화

---

**작성:** Windsurf AI (D90-3 Validation Phase)  
**최종 업데이트:** 2025-12-10 14:20 KST  
**Status:** ✅ **PASS (CONDITIONAL)** - Baseline 유지, advisory_z23_focus 보존
