# D84-2: CalibratedFillModel 장기 PAPER 검증 리포트

**작성일:** 2025-12-07 17:25:38
**상태:** ✅ **COMPLETE**

---

## 📋 실행 개요

- **Events 파일**: `logs\d84-2\fill_events_20251207_082028.jsonl`
- **Calibration 파일**: `logs\d84\d84_1_calibration.json`
- **총 이벤트 수**: 60
- **BUY 이벤트**: 30
- **SELL 이벤트**: 30

## 📊 available_volume 분석

### BUY available_volume

- Count: 30
- Min: 0.000075
- Max: 0.239792
- Mean: 0.065995
- Median: 0.029182
- Std: 0.077324
- **✅ DISPERSED** (std=117.2% of mean)

### SELL available_volume

- Count: 30
- Min: 0.000037
- Max: 0.675578
- Mean: 0.076867
- Median: 0.006751
- Std: 0.170180
- **✅ DISPERSED** (std=221.4% of mean)

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

- **BUY**: mean=0.19 bps, std=0.33 bps
- **SELL**: mean=0.20 bps, std=0.34 bps

## 🏁 결론

- ✅ Fill Events 수 충족: 60개 (≥ 50)
- ✅ available_volume 분산 확인: BUY 117.2%, SELL 221.4%
- ✅ BUY Fill Ratio Calibration 적용 확인 (차이 0.0000)

---

**리포트 생성 완료**