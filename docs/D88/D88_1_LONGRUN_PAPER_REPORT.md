# D88-1: LONGRUN PAPER Validation Report (Cycle Mode)

**Status:** ✅ **COMPLETE**  
**Date:** 2025-12-09  
**Related:** D88-0 (Entry BPS Diversification), D87-4 (Zone Selection Design)

---

## 1. Overview

### 1.1 목적 (Objective)

D88-0에서 구현한 Entry BPS Diversification (5~25bps, cycle 모드)를 장시간 PAPER 실행 환경에서 검증하고, 인프라 안정성과 Zone 분산 효과를 확인한다.

**핵심 목표:**
- **인프라 안정성 검증:** 3시간 LONGRUN에서 Duration Guard, Fill Model, WebSocket 안정성 확인
- **Zone 분산 검증:** Z1~Z4 균등 분포 유지 (D87-6의 "Z2 100%" 문제 해소)
- **Advisory vs Strict A/B 비교:** Zone Preference 로직 효과 측정 시도

### 1.2 실행 환경

- **Symbol:** BTC/USDT (Upbit)
- **L2 Source:** Real WebSocket (Upbit WS API)
- **Calibration:** `logs/d86-1/calibration_20251207_123906.json`
- **Entry BPS Profile:** cycle 모드 (Z1→Z2→Z3→Z4 순환)
  - Z1: 6.0 bps
  - Z2: 9.5 bps
  - Z3: 16.0 bps
  - Z4: 25.0 bps
- **TP BPS:** 12.0 bps (고정)
- **Infrastructure:** Redis, PostgreSQL, Prometheus, Grafana (Docker Compose)

---

## 2. 실행 시나리오 요약

총 4개 세션 (Short A/B 30m + Long A/B 3h) 실행:

| Session Name | Duration | Fill Model Mode | Entry BPS Mode | Entry BPS Range | Session Tag | Date |
|--------------|----------|-----------------|----------------|-----------------|-------------|------|
| **Advisory 30m** | 1800s (30분) | advisory | cycle | 5.0~25.0 bps | d88_1_advisory_30m | 2025-12-09 01:10~01:40 |
| **Strict 30m** | 1800s (30분) | strict | cycle | 5.0~25.0 bps | d88_1_strict_30m | 2025-12-09 01:40~02:10 |
| **Advisory 3h** | 10800s (3시간) | advisory | cycle | 5.0~25.0 bps | d88_1_advisory_3h | 2025-12-09 02:10~05:10 |
| **Strict 3h** | 10800s (3시간) | strict | cycle | 5.0~25.0 bps | d88_1_strict_3h | 2025-12-09 05:11~08:11 |

**실행 명령어 (예시):**
```bash
python scripts/run_d84_2_calibrated_fill_paper.py \
  --duration-seconds 10800 \
  --l2-source real \
  --fillmodel-mode advisory \
  --calibration-path logs/d86-1/calibration_20251207_123906.json \
  --entry-bps-mode cycle \
  --entry-bps-min 5.0 \
  --entry-bps-max 25.0 \
  --session-tag d88_1_advisory_3h
```

---

## 3. 결과 요약 테이블

### 3.1 Short A/B (30m) 결과

| Metric | Advisory 30m | Strict 30m | Delta (A-S) |
|--------|--------------|------------|-------------|
| **Target Duration** | 1800.0s | 1800.0s | - |
| **Actual Duration** | 1800.97s (+0.97s) | 1800.94s (+0.94s) | +0.03s |
| **Entry Trades** | 180 | 180 | 0 |
| **Fill Events** | 360 | 360 | 0 |
| **Total PnL** | $6.28 | $6.08 | +$0.20 |
| **Z1 Trades** | 45 (25.0%) | 45 (25.0%) | 0 |
| **Z2 Trades** | 45 (25.0%) | 45 (25.0%) | 0 |
| **Z3 Trades** | 45 (25.0%) | 45 (25.0%) | 0 |
| **Z4 Trades** | 45 (25.0%) | 45 (25.0%) | 0 |
| **Unmatched** | 0 (0.0%) | 0 (0.0%) | 0 |

### 3.2 Long A/B (3h) 결과

| Metric | Advisory 3h | Strict 3h | Delta (A-S) |
|--------|-------------|-----------|-------------|
| **Target Duration** | 10800.0s | 10800.0s | - |
| **Actual Duration** | 10800.97s (+0.97s) | 10800.12s (+0.12s) | +0.85s |
| **Entry Trades** | 1079 | 1079 | 0 |
| **Fill Events** | 2158 | 2158 | 0 |
| **Total PnL** | $37.23 | $37.38 | -$0.15 |
| **Z1 Trades** | 269 (24.9%) | 269 (24.9%) | 0 |
| **Z2 Trades** | 270 (25.0%) | 270 (25.0%) | 0 |
| **Z3 Trades** | 270 (25.0%) | 270 (25.0%) | 0 |
| **Z4 Trades** | 270 (25.0%) | 270 (25.0%) | 0 |
| **Unmatched** | 0 (0.0%) | 0 (0.0%) | 0 |

---

## 4. Acceptance Criteria vs Result

D88-1 검증 기준과 실제 결과:

| Criteria | Target | Short A/B (30m) | Long A/B (3h) | Status |
|----------|--------|-----------------|---------------|--------|
| **C1: Duration Accuracy** | ±30초 | Advisory: +0.97s<br>Strict: +0.94s | Advisory: +0.97s<br>Strict: +0.12s | ✅ PASS |
| **C2: Fill Events Generation** | ≥100개/세션 | Advisory: 360<br>Strict: 360 | Advisory: 2158<br>Strict: 2158 | ✅ PASS |
| **C3: All Zones Covered** | Z1~Z4 ≥1개 | Z1~Z4 각 45개 | Z1~Z4 각 269~270개 | ✅ PASS |
| **C4: No Z2 Dominance** | Z2 < 90% | Z2 = 25.0% | Z2 = 25.0% | ✅ PASS |
| **C5: Low Unmatched Rate** | < 5% | 0.0% | 0.0% | ✅ PASS |
| **C6: Fatal Error** | 0건 | 0건 | 0건 | ✅ PASS |

**최종 판정:** ✅ **6/6 PASS** - 인프라 관점에서 완벽한 안정성 확인

---

## 5. 해석 & 인사이트

### 5.1 핵심 성과 (Key Achievements)

#### ✅ Z2 100% 편중 문제 완전 해소
- **D87-6 문제:** 모든 트레이드가 Z2에만 집중 (100%)
- **D88-1 결과:** Z1~Z4 각 25% 균등 분포 (cycle 모드 효과)
- **장시간 안정성:** 30분 → 3시간까지 분포 유지 (269~270개/Zone)

#### ✅ 인프라 상용급 안정성 검증
- **Duration Guard:** 목표 대비 ±1초 오차 (목표: ±30초)
- **Fill Events:** 2158개/3시간 (평균 0.6개/초) 안정 생성
- **Fatal Error:** 0건 (6시간 30분 총 실행 시간 동안)
- **PnL 정합성:** Advisory ≈ Strict (차이 < $1)

#### ✅ 재현 가능한 테스트 환경 구축
- cycle 모드로 동일한 Entry BPS 시퀀스 보장
- Zone 분포 예측 가능 (Z1~Z4 각 25%)
- 회귀 테스트용 기준선 확보

### 5.2 발견된 한계 (Discovered Limitations)

#### ⚠️ Zone Preference 효과 미관측
- **현상:** Advisory vs Strict의 Zone 분포가 완전히 동일 (각 25%)
- **원인 분석:**
  1. **cycle 모드 특성:** 고정된 시퀀스 (Z1→Z2→Z3→Z4 반복)로 인해 Advisory/Strict 모두 동일한 Entry BPS 흐름 사용
  2. **Zone Selection 무력화:** Entry BPS가 이미 Zone을 결정하므로, Fill Model의 Zone Preference 로직이 작동할 여지 없음
  3. **TP BPS 고정:** TP = 12.0bps 고정으로 Zone 매칭에 변수 부족
  
- **영향:**
  - Zone Selection (D87-4)의 실전 효과 검증 불가
  - Advisory의 "Z2 우선" 전략이 실제로 ΔP(Z2) 향상에 기여하는지 미확인
  - Strict의 "모든 Zone 균등" 전략과의 차이 측정 불가

#### ⚠️ Structural A/B Test Limitation
- cycle 모드는 **재현성**에는 유리하지만, **A/B 테스트**에는 부적합
- Advisory/Strict가 서로 다른 Zone 선호도를 가지더라도, 입력(Entry BPS)이 동일하면 출력(Zone 분포)도 동일

---

## 6. Known Limitations & Next Steps

### 6.1 한계 정리

| Limitation | Impact | Severity |
|------------|--------|----------|
| **cycle 모드 → 동일 시퀀스** | Advisory/Strict A/B 차이 없음 | HIGH |
| **TP BPS 고정 (12.0)** | Zone 매칭 변수 부족 | MEDIUM |
| **로그 디렉터리 경로** | `logs/d87-3`에 저장 (의도: `logs/d88-1`) | LOW |

### 6.2 D88-2 방향 (Next Steps)

**목표:** Entry BPS random 모드로 Advisory vs Strict A/B 재검증

#### D88-2-1: Random Mode A/B Short Run (30m + 30m)
- **Entry BPS Mode:** random (5.0~25.0bps 균일 분포)
- **Seed:** Advisory ≠ Strict (서로 다른 seed 사용)
- **기대 효과:**
  - Advisory: Z2 선호 → ΔP(Z2) ≥ +3%p 예상
  - Strict: 균등 분포 → Z1~Z4 각 25% 유지
- **Acceptance Criteria:**
  - C1~C6 (기존 유지)
  - C7: |ΔP(Z2)| ≥ 3%p (Advisory vs Strict)
  - C8: |ΔSize(Z2)| ≥ 3%p (Zone별 평균 Fill Size 차이)

#### D88-2-2: Random Mode A/B Long Run (3h + 3h)
- Short Run에서 효과 확인 후 실행
- 장시간 환경에서 Zone Preference 효과 지속성 검증

#### D88-2-3: 결과 판단 기준
- **효과 관측 (PASS):** ΔP(Z2) ≥ 3%p 또는 ΔSize(Z2) ≥ 3%p
- **효과 미미 (CONDITIONAL PASS):** 1%p ≤ Δ < 3%p
- **효과 없음 (FAIL):** Δ < 1%p → Zone Selection 로직 재설계 필요

---

## 7. 산출물 (Deliverables)

### 7.1 로그 및 결과 파일

#### Short A/B (30m)
- **Advisory 30m:**
  - KPI: `logs/d87-3/d88_1_advisory_30m/kpi_20251208_161001.json`
  - Fill Events: `logs/d87-3/d88_1_advisory_30m/fill_events_20251208_161001.jsonl`
  - Zone Analysis: `logs/d87-3/d88_1_advisory_30m/zone_distribution_analysis.json`
  
- **Strict 30m:**
  - KPI: `logs/d87-3/d88_1_strict_30m/kpi_20251208_164014.json`
  - Fill Events: `logs/d87-3/d88_1_strict_30m/fill_events_20251208_164014.jsonl`
  - Zone Analysis: `logs/d87-3/d88_1_strict_30m/zone_distribution_analysis.json`

#### Long A/B (3h)
- **Advisory 3h:**
  - KPI: `logs/d87-3/d88_1_advisory_3h/kpi_20251208_171056.json`
  - Fill Events: `logs/d87-3/d88_1_advisory_3h/fill_events_20251208_171056.jsonl`
  - Zone Analysis: `logs/d87-3/d88_1_advisory_3h/zone_distribution_analysis.json`
  
- **Strict 3h:**
  - KPI: `logs/d87-3/d88_1_strict_3h/kpi_20251208_201132.json`
  - Fill Events: `logs/d87-3/d88_1_strict_3h/fill_events_20251208_201132.jsonl`
  - Zone Analysis: `logs/d87-3/d88_1_strict_3h/zone_distribution_analysis.json`

### 7.2 문서
- **이 문서:** `docs/D88/D88_1_LONGRUN_PAPER_REPORT.md`

---

## 8. 결론 (Conclusion)

D88-1에서 Entry BPS Diversification (cycle 모드)의 **인프라 안정성**과 **Zone 분산 효과**를 성공적으로 검증했다.

**핵심 성과:**
- ✅ Z2 100% 편중 문제 완전 해소 (Z1~Z4 각 25%)
- ✅ 3시간 LONGRUN 안정성 검증 (Duration ±1초, Fatal Error 0건)
- ✅ 재현 가능한 테스트 환경 구축 (cycle 모드)

**핵심 한계:**
- ⚠️ Advisory vs Strict Zone Preference 효과 미관측 (cycle 모드 특성)
- ⚠️ Zone Selection (D87-4) 실전 효과 검증 불가

**다음 단계:**
- **D88-2:** random 모드 A/B 재검증으로 Zone Preference 효과 실증
- **목표:** ΔP(Z2) ≥ 3%p 달성

**최종 판정:** ✅ **D88-1 COMPLETE** - 인프라/Zone 분산은 PASS, Zone Selection 효과는 D88-2에서 재검증 예정

---

**Status:** ✅ **D88-1 COMPLETE**  
**Date:** 2025-12-09  
**Total Execution Time:** 약 6시간 30분 (Short 1h + Long 6h)
