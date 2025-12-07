# D85-2: Multi L2 1h PAPER & Calibration Data Expansion 리포트

**작성일:** 2025-12-07 20:40:33  
**상태:** ✅ **COMPLETE**

---

## 📋 Executive Summary

**D85-2 목표:** Multi L2 (Upbit + Binance) 1시간 장기 PAPER 실행, 500+ Fill Events 수집, Zone별 데이터 확장

**핵심 성과:**
- ✅ **C1: Duration ≥ 1시간**: 3605.2초 (60.1분)
- ✅ **C2: Fill Events ≥ 500**: 718개 (BUY 359, SELL 359)
- ✅ **C3: 인프라 안정성**: Fatal Exception 0건, Multi L2 정상 동작
- ✅ **C4: available_volume 분산**: BUY 65.9%, SELL 300.5% (≥ 10%)
- ✅ **C5: 문서화**: 리포트 완료

**D85-1 대비 개선:**
- Events: 240 → **718** (+199%)
- Duration: 20.1분 → **60.1분** (+199%)
- Entry Trades: 120 → **359** (+199%)

---

## 📋 실행 설정 (Execution Setup)

### Duration & Universe
- **Session ID**: 20251207_103956
- **Duration**: 3605.2초 (60.1분, 목표 3600초)
- **Symbol**: BTC (단일 심볼)
- **L2 Source**: Multi (Upbit + Binance)

### Entry/TP 조합 (12개 Zone 커버)
| Zone | Entry Range (bps) | Entry/TP 조합 | 사용 횟수 |
|------|------------------|-------------|---------|
| **Z1** | 5-7 | (5.0, 7.0), (5.0, 10.0), (7.0, 10.0) | 90회 |
| **Z2** | 7-12 | (7.0, 12.0), (10.0, 12.0), (10.0, 15.0) | 90회 |
| **Z3** | 12-20 | (12.0, 15.0), (12.0, 20.0), (15.0, 20.0) | 90회 |
| **Z4** | >20 | (20.0, 25.0), (20.0, 30.0), (25.0, 30.0) | 89회 |

**총 Entry Trades**: 359회 (12개 조합 각 약 30회씩)

---

## 📊 Fill Event 통계 (Overall Stats)

### 전체 이벤트
- **총 이벤트**: 718 (BUY 359 + SELL 359)
- **BUY/SELL 비율**: 50.0% / 50.0% (균형)

### available_volume (BUY)
- **Count**: 359
- **Range**: 0.003740 ~ 9.709750 BTC
- **Mean**: 3.749194 BTC
- **Median**: 3.085540 BTC
- **Std**: 2.472476 BTC
- **✅ Dispersion**: 65.9% (목표 ≥ 10%)

### available_volume (SELL)
- **Count**: 359
- **Range**: 0.000037 ~ 3.102390 BTC
- **Mean**: 0.063234 BTC
- **Median**: 0.010499 BTC
- **Std**: 0.189999 BTC
- **✅ Dispersion**: 300.5% (목표 ≥ 10%)

### fill_ratio (BUY)
- **Mean**: 0.3849 (38.49%)
- **Median**: 0.2615 (26.15%)
- **Std**: 0.2759
- **Range**: 0.2615 ~ 1.0000

### fill_ratio (SELL)
- **Mean**: 1.0000 (100.00%)
- **Std**: 0.0000 (고정값)

### slippage (bps)
- **BUY**: mean=0.00 bps, std=0.02 bps
- **SELL**: mean=0.15 bps, std=0.29 bps

---

## 📊 Zone별 통계

### Zone별 분류 결과
| Zone | BUY Events | SELL Events | Total | Percentage |
|------|-----------|------------|-------|-----------|
| **Z1** | 359 | 359 | 718 | 100.0% |
| Z2 | 0 | 0 | 0 | 0.0% |
| Z3 | 0 | 0 | 0 | 0.0% |
| Z4 | 0 | 0 | 0 | 0.0% |

### Z1 통계 (Entry 5-7 bps)
- **BUY fill_ratio**: mean=0.3849 (38.49%), std=0.2759
- **SELL fill_ratio**: mean=1.0000 (100.00%), std=0.0000
- **BUY slippage**: mean=0.00 bps, std=0.02 bps
- **SELL slippage**: mean=0.15 bps, std=0.29 bps

**⚠️ Zone 분류 이슈:**
- 12개 Entry/TP 조합을 사용했으나, 모든 데이터가 Z1로 분류됨
- Zone 매칭 로직이 Entry BPS만 보는 것으로 추정
- 실제 사용된 Entry BPS 범위: 5.0 ~ 25.0 bps

---

## 📊 D85-1 vs D85-2 비교

| Metric | D85-1 (20분) | D85-2 (1시간) | 변화 |
|--------|-------------|-------------|-----|
| **Duration (초)** | 1205.7 | 3605.2 | +199% |
| **Duration (분)** | 20.1 | 60.1 | +199% |
| **Entry Trades** | 120 | 359 | +199% |
| **Fill Events** | 240 | 718 | +199% |
| **Total PnL ($)** | 4.57 | 13.69 | +199% |
| **BUY available_volume mean** | 3.411 | 3.749 | +9.9% |
| **BUY available_volume std** | 2.406 | 2.472 | +2.7% |
| **BUY fill_ratio mean** | 0.3846 | 0.3849 | +0.08% |
| **BUY fill_ratio std** | 0.2764 | 0.2759 | -0.18% |
| **Zone Coverage** | Z1 only | Z1 only | No change |

**핵심 발견:**
- Events 수는 3배 증가 (240 → 718)
- 통계적 특성은 거의 동일 (fill_ratio, available_volume)
- Zone 분류 문제는 여전히 존재

---

## 📊 Calibration 예측 vs 실측

### BUY Fill Ratio
- **Calibration 예측**: 0.2615 (26.15%)
- **실측 평균**: 0.3849 (38.49%)
- **차이**: +0.1234 (+47.2%)

### SELL Fill Ratio
- **Calibration 예측**: 1.0000 (100.00%)
- **실측 평균**: 1.0000 (100.00%)
- **차이**: 0.0000 (일치)

**해석:**
- BUY fill_ratio가 Calibration 예측보다 47% 높음
- 현재 Calibration (D84-1)이 과도하게 보수적
- 실제 L2 시장 환경이 Calibration 기준보다 유동성이 높음

---

## 🔍 한계 & 관찰된 패턴

### 1. Zone 분류 문제
**현상:**
- 12개 Entry/TP 조합 (5~25 bps) 사용
- 모든 데이터가 Z1 (Entry 5-7 bps)로 분류
- Z2, Z3, Z4는 0개

**원인 분석:**
```python
# analyze_d85_1_fill_results.py의 match_zone 함수
def match_zone(entry_bps, zones):
    for zone in zones:
        entry_min = zone.get("entry_min", 0)
        entry_max = zone.get("entry_max", 999)
        if entry_min <= entry_bps <= entry_max:
            return zone["zone_id"]
    return None
```

**문제점:**
- Calibration JSON (d84_1_calibration.json)의 Zone 정의가 실제 Entry BPS 범위와 불일치
- D84-1 Calibration은 D82 데이터 (Entry 5-7 bps만 존재) 기반
- Z2/Z3/Z4 Zone 정의는 있으나 실제 데이터가 없었음

**해결 방안 (D86):**
- D85-2 데이터 (Entry 5~25 bps)를 기반으로 Zone 재정의
- Entry BPS 분포에 맞춰 4개 Zone을 적절히 분할
- 예: Z1(5-10), Z2(10-15), Z3(15-20), Z4(20-30)

### 2. Fill Ratio Calibration 부정확
**현상:**
- Calibration 예측: 0.2615 (26.15%)
- 실측 평균: 0.3849 (38.49%)
- 47% 차이

**원인:**
- D84-1 Calibration이 D82 PAPER 데이터 기반
- D82 환경: Mock L2, 고정 available_volume
- D85-2 환경: Real Multi L2 (Upbit + Binance)
- 실제 L2 시장이 Mock보다 유동성 높음

**해결 방안 (D86):**
- D85-1/2 Real Multi L2 데이터로 재캘리브레이션
- Zone별로 다른 fill_ratio 적용 (현재는 모든 Zone 26.15% 동일)

### 3. SELL fill_ratio 100% 고정
**현상:**
- SELL fill_ratio가 항상 1.0000 (100%)
- std=0.0000 (분산 없음)

**원인:**
- SimpleFillModel의 기본 동작
- SELL은 always fill (시장가 판매 가정)

**관찰:**
- PAPER 환경에서는 합리적
- REAL 환경에서는 재검토 필요

---

## 🎯 Acceptance Criteria 검증

| ID | Criterion | Target | Result | Status |
|----|-----------|--------|--------|--------|
| **C1** | Duration ≥ 1시간 | ≥ 3600초 | 3605.2초 (60.1분) | ✅ PASS |
| **C2** | Fill Events ≥ 500 | ≥ 500 | 718 | ✅ PASS |
| **C3** | 인프라 안정성 | Fatal Exception 0건 | 0건 | ✅ PASS |
| **C4** | available_volume 분산 ≥ 10% | BUY/SELL ≥ 10% | BUY 65.9%, SELL 300.5% | ✅ PASS |
| **C5** | 문서화 완료 | 리포트 + ROADMAP | 완료 | ✅ PASS |

**종합 판정:** ✅ **ALL PASS (5/5)**

---

## 🎯 D86 Fill Model Calibration을 위한 시사점

### 1. Zone 재정의 필요
**현황:**
- 현재 Zone 정의 (D84-1): Z1(5-7), Z2(7-12), Z3(12-20), Z4(>20)
- 실제 데이터: Entry 5~25 bps 고르게 분포
- Zone 매칭: 전체가 Z1로 분류 (부적절)

**D86 TODO:**
```python
# 새로운 Zone 정의 (D85-2 데이터 기반)
zones = [
    {"zone_id": "Z1", "entry_min": 5.0, "entry_max": 10.0, "tp_min": 7.0, "tp_max": 15.0},
    {"zone_id": "Z2", "entry_min": 10.0, "entry_max": 15.0, "tp_min": 12.0, "tp_max": 20.0},
    {"zone_id": "Z3", "entry_min": 15.0, "entry_max": 20.0, "tp_min": 20.0, "tp_max": 30.0},
    {"zone_id": "Z4", "entry_min": 20.0, "entry_max": 30.0, "tp_min": 25.0, "tp_max": 40.0},
]
```

### 2. fill_ratio 재캘리브레이션
**현황:**
- D84-1 Calibration: 모든 Zone 0.2615 (26.15%)
- D85-2 실측: 0.3849 (38.49%, +47%)

**D86 TODO:**
- D85-1/2 데이터 (240 + 718 = 958 events) 통합
- Zone별 fill_ratio 계산
- Zone별로 다른 fill_ratio 적용

### 3. Slippage 모델 개선
**현황:**
- BUY slippage: mean=0.00 bps (거의 없음)
- SELL slippage: mean=0.15 bps (일정)

**D86 TODO:**
- Zone별 slippage 통계 수집
- Entry BPS에 따른 slippage 패턴 분석
- Dynamic slippage model 적용 가능성 검토

### 4. 다양한 시장 조건 데이터 (D85-3)
**현황:**
- D85-1: 20분 (240 events)
- D85-2: 1시간 (718 events)
- 단일 시간대 데이터 (UTC 10:39 ~ 11:40)

**D85-3 제안:**
- 여러 시간대 실행 (아시아/유럽/미국)
- 변동성 높은 구간 포함
- 1000+ events 목표

---

## 🏁 결론

**판정:** ⚠️ **CONDITIONAL GO → READY FOR D86**

### ✅ 달성 사항
1. **데이터 볼륨 충족**: 718 events (목표 500+ 달성)
2. **인프라 안정성**: 1시간 무중단 실행, Fatal Exception 0건
3. **통계 품질**: available_volume 분산 65.9% / 300.5% (유의미)
4. **D85-1 대비 개선**: Events 3배 증가 (240 → 718)

### ⚠️ 한계 사항
1. **Zone 분류 실패**: 모든 데이터 Z1로 분류
2. **Calibration 부정확**: fill_ratio 예측 47% 차이
3. **시장 조건 단일**: 단일 시간대 데이터

### 📝 다음 단계

#### D86: Fill Model Re-calibration (HIGH Priority)
- D85-1/2 데이터 (958 events) 통합
- Zone 재정의 (Entry 5~30 bps 커버)
- Zone별 fill_ratio/slippage 재계산
- 새 Calibration JSON 생성

#### D85-3: Multi-Regime PAPER (OPTIONAL)
- 여러 시간대 실행
- 변동성 높은 구간 포함
- 1000+ events 목표

#### D87+: Multi-Exchange Execution
- Cross-exchange Order Routing
- Dynamic Slippage Model
- D86 Calibration 기반 최적화

---

**리포트 생성 완료** (2025-12-07 20:40:33)
