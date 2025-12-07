# D85-1: Multi L2 Long PAPER & Calibration Data Collection 리포트

**작성일:** 2025-12-07 20:40:33
**상태:** ✅ **COMPLETE**

---

## 📋 실행 개요

- **Events 파일**: `logs\d85-2\fill_events_20251207_103956.jsonl`
- **Calibration 파일**: `logs\d84\d84_1_calibration.json`
- **L2 Source**: Multi (Upbit + Binance)
- **총 이벤트 수**: 718
- **BUY 이벤트**: 359
- **SELL 이벤트**: 359

## 📊 available_volume 분석

### BUY available_volume

- Count: 359
- Min: 0.003740
- Max: 9.709750
- Mean: 3.749194
- Median: 3.085540
- Std: 2.472476
- **✅ DISPERSED** (std=65.9% of mean)

### SELL available_volume

- Count: 359
- Min: 0.000037
- Max: 3.102390
- Mean: 0.063234
- Median: 0.010499
- Std: 0.189999
- **✅ DISPERSED** (std=300.5% of mean)

## 📊 fill_ratio 분석

### BUY fill_ratio (전체)

- Count: 359
- Min: 0.2615 (26.15%)
- Max: 1.0000 (100.00%)
- Mean: 0.3849 (38.49%)
- Median: 0.2615 (26.15%)
- Std: 0.2759

### SELL fill_ratio (전체)

- Count: 359
- Min: 1.0000 (100.00%)
- Max: 1.0000 (100.00%)
- Mean: 1.0000 (100.00%)
- Median: 1.0000 (100.00%)
- Std: 0.0000

## 📊 Zone별 fill_ratio 분석

### Z1

- **총 이벤트**: 718 (BUY=359, SELL=359)

- **BUY fill_ratio**: mean=0.3849 (38.49%), std=0.2759
- **SELL fill_ratio**: mean=1.0000 (100.00%), std=0.0000
- **BUY slippage**: mean=0.00 bps, std=0.02 bps
- **SELL slippage**: mean=0.15 bps, std=0.29 bps

### Zone 간 비교

| Zone | BUY Events | BUY Fill Ratio (mean) | SELL Events | SELL Fill Ratio (mean) |
|------|------------|----------------------|-------------|------------------------|
| Z1 | 359 | 0.3849 (38.49%) | 359 | 1.0000 (100.00%) |

## 📊 Calibration 예측 vs 실측

- **BUY Fill Ratio**:
  - Calibration 예측: 0.2615
  - 실측 평균: 0.3849
  - 차이: 0.1234

- **SELL Fill Ratio**:
  - Calibration 예측: 1.0000
  - 실측 평균: 1.0000
  - 차이: 0.0000

## 📊 Slippage (bps)

- **BUY**: mean=0.00 bps, std=0.02 bps
- **SELL**: mean=0.15 bps, std=0.29 bps

## 🎯 Acceptance Criteria

- ✅ **C2: Fill Events 수 충족**: 718개 (≥ 100)
- ✅ **C4: available_volume 분산 확인**: BUY 65.9%, SELL 300.5%

## 🏁 결론

⚠️ **Zone별 데이터 부족**: Multi-zone 분석 불가

**현재까지의 한계:**

- D85-1은 데이터 수집 단계이며, Zone별 차이가 명확히 드러나지 않을 수 있음
- 더 많은 데이터(500+ events)와 다양한 시장 조건이 필요
- 현재 Calibration은 D82 데이터 기반이므로, Zone별 보정 효과가 제한적

**다음 단계:**

1. **D85-2**: 장기 실행 (1시간+, 500+ events) 재실행
2. **D85-3**: 다양한 시장 조건 (변동성 높은 구간) 데이터 수집
3. **D86**: Zone별 차이가 명확한 Calibration 재작성

---

**리포트 생성 완료**