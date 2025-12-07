# D84-2: CalibratedFillModel 장기 PAPER 검증 리포트

**작성일:** 2025-12-07 18:07:05
**상태:** ✅ **COMPLETE**

---

## 📋 실행 개요

- **Events 파일**: `logs\d84-2\fill_events_20251207_090139.jsonl`
- **Calibration 파일**: `logs\d84\d84_1_calibration.json`
- **총 이벤트 수**: 60
- **BUY 이벤트**: 30
- **SELL 이벤트**: 30

## 📊 available_volume 분석

### BUY available_volume

- Count: 30
- Min: 0.004630
- Max: 9.263020
- Mean: 3.888486
- Median: 3.420160
- Std: 2.774635
- **✅ DISPERSED** (std=71.4% of mean)

### SELL available_volume

- Count: 30
- Min: 0.000067
- Max: 0.221513
- Mean: 0.025217
- Median: 0.003355
- Std: 0.044895
- **✅ DISPERSED** (std=178.0% of mean)

## 📊 fill_ratio 분석

### BUY fill_ratio

- Count: 30
- Min: 0.2615 (26.15%)
- Max: 0.2615 (26.15%)
- Mean: 0.2615 (26.15%)
- Median: 0.2615 (26.15%)
- Std: 0.0000
- **⚠️ FIXED** (std < 0.01)

### SELL fill_ratio

- Count: 30
- Min: 1.0000 (100.00%)
- Max: 1.0000 (100.00%)
- Mean: 1.0000 (100.00%)
- Median: 1.0000 (100.00%)
- Std: 0.0000
- **⚠️ FIXED** (std < 0.01)

## 📊 Calibration 예측 vs 실측

- **BUY Fill Ratio**:
  - Calibration 예측: 0.2615
  - 실측 평균: 0.2615
  - 차이: 0.0000

- **SELL Fill Ratio**:
  - Calibration 예측: 1.0000
  - 실측 평균: 1.0000
  - 차이: 0.0000

## 📊 Slippage (bps)

- **BUY**: mean=0.01 bps, std=0.04 bps
- **SELL**: mean=0.28 bps, std=0.37 bps

## 🏁 결론

- ✅ Fill Events 수 충족: 60개 (≥ 50)
- ✅ available_volume 분산 확인: BUY 71.4%, SELL 178.0%
- ✅ BUY Fill Ratio Calibration 적용 확인 (차이 0.0000)

---

**리포트 생성 완료**