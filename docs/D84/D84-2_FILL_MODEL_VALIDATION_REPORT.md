# D84-2: CalibratedFillModel 장기 PAPER 검증 리포트

**작성일:** 2025-12-07 14:18:56
**상태:** ✅ **COMPLETE**

---

## 📋 실행 개요

- **Events 파일**: `logs\d84-2\fill_events_20251207_051343.jsonl`
- **Calibration 파일**: `logs\d84\d84_1_calibration.json`
- **총 이벤트 수**: 60
- **BUY 이벤트**: 30
- **SELL 이벤트**: 30

## 📊 available_volume 분석

### BUY available_volume

- Count: 30
- Min: 0.000190
- Max: 1.158767
- Mean: 0.211946
- Median: 0.032821
- Std: 0.400762
- **✅ DISPERSED** (std=189.1% of mean)

### SELL available_volume

- Count: 30
- Min: 0.000034
- Max: 0.138703
- Mean: 0.035973
- Median: 0.002400
- Std: 0.044776
- **✅ DISPERSED** (std=124.5% of mean)

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

- **BUY**: mean=0.08 bps, std=0.19 bps
- **SELL**: mean=0.29 bps, std=0.39 bps

## 🏁 결론

- ✅ Fill Events 수 충족: 60개 (≥ 50)
- ✅ available_volume 분산 확인: BUY 189.1%, SELL 124.5%
- ✅ BUY Fill Ratio Calibration 적용 확인 (차이 0.0000)

---

**리포트 생성 완료**