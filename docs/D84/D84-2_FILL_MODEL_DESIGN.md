# D84-2: CalibratedFillModel 장기 PAPER 검증 설계

**작성일:** 2025-12-06  
**상태:** 📋 설계 단계  
**작성자:** Windsurf AI

---

## 📋 개요

### 배경
- D84-0/1에서 CalibratedFillModel + FillEventCollector + Calibrator 인프라 구현 완료
- D83-0/0.5에서 L2 Orderbook 통합 및 스모크 검증 완료
- D84-1은 유닛 테스트만 수행, 실제 장기 PAPER 실행은 미완료

### D84-2 목표
CalibratedFillModel을 실제 PAPER 환경에서 **20분 이상 실행**하여:
1. Zone별 Fill Ratio 보정이 실제로 작동하는지 검증
2. 50개 이상의 Fill Event 수집
3. L2 Orderbook + CalibratedFillModel 통합 동작 확인

---

## 🎯 구체적 목표

### 실행 목표
- **심볼**: BTC 단일
- **Fill Model**: CalibratedFillModel (d84_1_calibration.json 사용)
- **L2 Provider**: MockMarketDataProvider (D83-0.5와 동일)
- **Duration**: 
  - 스모크 테스트: 300초 (5분)
  - 본 실행: 1200초 (20분)

### 데이터 수집 목표
- **Fill Events**: 50개 이상 (25개 BUY + 25개 SELL)
- **JSONL 저장**: `logs/d84-2/fill_events_<session_id>.jsonl`
- **KPI 저장**: `logs/d84-2/kpi_<session_id>.json`

### 검증 목표
- Zone별 Fill Ratio가 Calibration 데이터와 일치하는지 확인
- SimpleFillModel(100% 체결) 대비 CalibratedFillModel의 차이 관측
- available_volume 분산 유지 (D83-0.5 수준)

---

## 🏗️ 구현 계획

### 1️⃣ Runner 구현
**파일명**: `scripts/run_d84_2_calibrated_fill_paper.py`

**핵심 기능**:
- D83-0.5 Runner 기반으로 작성 (최대 재사용)
- CalibratedFillModel 사용 (d84_1_calibration.json 로드)
- MockMarketDataProvider + FillEventCollector 통합
- CLI 인자: `--duration-seconds`, `--smoke` 등

**실행 흐름**:
```
1. Calibration JSON 로드 (logs/d84/d84_1_calibration.json)
2. MockMarketDataProvider 생성 (L2 시뮬레이션)
3. FillEventCollector 생성 (JSONL 저장)
4. CalibratedFillModel 생성 (Calibration 적용)
5. ExecutorFactory로 PaperExecutor 생성
6. 지정 시간 동안 PAPER 루프 실행
7. FillEventCollector 요약 출력
8. KPI JSON 저장
```

### 2️⃣ 분석 스크립트 구현
**파일명**: `scripts/analyze_d84_2_fill_results.py`

**핵심 기능**:
- Fill Events JSONL 로드
- Calibration JSON 로드
- Zone별 통계 계산:
  - 평균 fill_ratio, 표준편차
  - available_volume 분포
  - Calibration 예측값 vs 실측값 비교
- 리포트 MD 파일 자동 생성

**출력**:
- 콘솔 요약 (한국어)
- `docs/D84/D84-2_FILL_MODEL_VALIDATION_REPORT.md`

### 3️⃣ 테스트 구현
**파일명**: `tests/test_d84_2_runner_config.py`, `tests/test_d84_2_fill_analysis.py`

**테스트 항목**:
- Runner가 CalibratedFillModel을 올바르게 초기화하는지
- Calibration JSON 파싱이 정상 동작하는지
- 분석 스크립트가 작은 샘플로 통계를 올바르게 계산하는지

---

## 📊 Acceptance Criteria

### ✅ 구현 완료 조건
1. **Runner 구현**
   - `run_d84_2_calibrated_fill_paper.py` 작성 완료
   - CalibratedFillModel + L2 + FillEventCollector 통합
   - CLI 인자 지원 (--duration-seconds, --smoke 등)

2. **분석 스크립트 구현**
   - `analyze_d84_2_fill_results.py` 작성 완료
   - Zone별 통계 계산 정상 동작
   - 리포트 MD 자동 생성

3. **테스트**
   - 새 테스트 3개 이상 추가
   - 기존 테스트 포함 전체 PASS (D83-0, D84-1 등)

### ✅ 실행 완료 조건
1. **스모크 테스트 (5분)**
   - 에러 없이 완료
   - Fill Events 10개 이상 수집
   - JSONL/KPI 파일 생성 확인

2. **본 실행 (20분)**
   - 에러 없이 완료
   - Fill Events 50개 이상 수집
   - Zone별 fill_ratio 분산 확인

3. **분석 완료**
   - 리포트 MD 생성
   - Zone별 통계 계산 완료
   - Calibration 예측 vs 실측 비교 완료

---

## 🔬 예상 결과 시나리오

### Scenario A: Zone별 차이 관측 (Optimistic)
- Z1 (Entry 5-7): fill_ratio ~26%
- Z2 (Entry 7-10): fill_ratio ~26%
- Z4 (Entry 14-16): fill_ratio ~26%
- **판정**: ⚠️ D82 데이터 한계 재확인 (모든 Zone 동일)

### Scenario B: available_volume 분산 유지 (Realistic)
- BUY/SELL available_volume std > 10% of mean (D83-0.5와 동일)
- fill_ratio는 Calibration 값 적용됨
- **판정**: ✅ Infrastructure 정상 동작 확인

### Scenario C: 데이터 부족 (Pessimistic)
- Fill Events < 50개
- 통계적 유의성 부족
- **판정**: ⚠️ 실행 시간 연장 필요

---

## 📁 산출물

### 새 파일
```
scripts/
  run_d84_2_calibrated_fill_paper.py (새 파일)
  analyze_d84_2_fill_results.py (새 파일)

tests/
  test_d84_2_runner_config.py (새 파일)
  test_d84_2_fill_analysis.py (새 파일)

docs/D84/
  D84-2_FILL_MODEL_DESIGN.md (이 문서)
  D84-2_FILL_MODEL_VALIDATION_REPORT.md (실행 후 생성)

logs/d84-2/
  fill_events_<session_id>.jsonl (실행 후 생성)
  kpi_<session_id>.json (실행 후 생성)
```

---

## 🚀 실행 계획

### 1단계: 구현
1. Runner 스크립트 작성
2. 분석 스크립트 작성
3. 테스트 코드 작성

### 2단계: 테스트
1. `pytest` 전체 실행 (기존 + 새 테스트)
2. Dry-run으로 Runner 동작 확인

### 3단계: 실행
1. 스모크 테스트 (5분)
2. 본 실행 (20분)
3. 분석 스크립트 실행

### 4단계: 문서화
1. 리포트 MD 생성
2. D_ROADMAP 업데이트
3. Git Commit

---

**다음 단계**: Runner 스크립트 구현
