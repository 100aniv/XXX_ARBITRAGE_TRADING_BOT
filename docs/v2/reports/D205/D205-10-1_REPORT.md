# D205-10-1: Threshold Sensitivity Sweep (브랜치 작업)

**⚠️ 브랜치 귀속:** 이 문서는 D205-10의 브랜치 작업(D205-10-1)입니다.  
**과거 오라벨:** D205-11 (SSOT 복구로 인해 D205-10-1로 재분류)

## 최종 상태: ⚠️ PARTIAL (Infrastructure 검증 완료, Real Data 미완료)

### 1. 목표

**D205-10-0에서 확장된 작업:**
- Threshold Sensitivity Analysis (buffer_bps sweep)
- DecisionTrace 유효성 검증 (reject_reasons negative-control)
- 최적 buffer 선택 후 20m smoke 재검증

**브랜치 관계:**
- D205-10-0 (완료): reject_reasons + buffer_bps 0.0 조정
- D205-10-1 (본 문서): buffer_bps 민감도 분석 및 최적값 선택

**핵심 질문:**
- buffer_bps를 어떤 값으로 설정해야 **손실을 줄이면서 거래가 유지되는가?**
- reject_reasons 계측이 **실제로 동작하는가?** (항상 0이면 존재 의미 없음)

---

## 2. 구현 계획

### 2.1. Threshold Sensitivity Sweep

**스크립트:** `scripts/run_d205_11_threshold_sweep.py` (신규)

**후보 buffer_bps 리스트:** [0, 1, 2, 3, 5, 8, 10]

**각 후보마다:**
- 2분 짧은 러닝
- KPI 수집: opportunities, intents, closed_trades, net_pnl, error_count
- 결과를 `sweep_summary.json`에 저장

**Best 선택 기준:**
- closed_trades > 0
- error_count == 0
- net_pnl이 가장 덜 나쁜/가장 좋은 값 (가능하면 >= 0 우선)

---

### 2.2. DecisionTrace 유효성 검증

**방법:**
- buffer_bps를 매우 큰 값(999)으로 강제한 30초 precheck 실행
- **기대:** intents=0, reject_reasons 중 profitable_false(또는 edge_bps_below_zero) > 0

**검증 통과 조건:**
- reject_reasons 카운트가 실제로 증가함 → "DecisionTrace가 실제로 동작한다"

---

## 3. 테스트 결과

### 3.1. Threshold Sensitivity Sweep (✅ Infrastructure PASS)

**실행:** `scripts/run_d205_10_1_sweep.py --duration-minutes 2 --db-mode off`
**실행 시간:** 2026-01-03 15:38~15:49 (약 11분, 5개 buffer * 2분 + overhead)
**Mode:** MOCK (Real data 미사용)

| Buffer (bps) | Opportunities | Intents | Closed Trades | Gross PnL | Net PnL | Error Count |
|--------------|---------------|---------|---------------|-----------|---------|-------------|
| 0            | 119           | 238     | 119           | -89.62    | -119.74 | 0           |
| 2            | 119           | 238     | 119           | -89.62    | -119.74 | 0           |
| 5            | 119           | 238     | 119           | -89.62    | -119.74 | 0           |
| 8            | 119           | 238     | 119           | -89.62    | -119.74 | 0           |
| 10           | 119           | 238     | 119           | -89.62    | -119.74 | 0           |

**Best Buffer 선정:** 0 bps (모두 동일, MOCK 모드 제한)
**Selection Logic:** ✅ PASS (closed_trades > 0, error_count == 0, net_pnl 최대)

**MOCK 모드 제한사항:**
- 모든 buffer에서 동일한 시뮬레이션 결과
- buffer_bps 변경이 실제 결과에 영향 없음
- Real threshold sensitivity는 `--use-real-data` 필요

### 3.2. DecisionTrace 유효성 검증 (⚠️ PARTIAL)

**MOCK 모드 결과:**
- reject_reasons: 모든 항목 0
- profitable_false: 0 (MOCK 데이터는 항상 profitable=True)
- negative-control: FAIL (Real data 필요)

**검증된 항목:**
- ✅ reject_reasons 필드 존재
- ✅ KPICollector.bump_reject() 메서드 작동
- ⚠️ 실제 reject 발생은 Real data 필요

### 3.3. 20m Smoke (Best buffer_bps) (⏭️ SKIP)

**이유:** MOCK 모드에서는 buffer 변경 효과 없음
**대안:** Real data 모드에서 별도 실행 필요

---

## 4. 변경 파일 목록

### Added (2개)
1. **scripts/run_d205_10_1_sweep.py** (신규, 323줄)
   - Threshold Sensitivity Sweep 자동화
   - buffer_bps [0,2,5,8,10] 순차 실행
   - Best buffer 선정 로직 (3단계 조건)
   - Negative-control 분석

2. **scripts/run_d205_10_1_smoke_best_buffer.py** (신규, 139줄)
   - Best buffer로 20m smoke 실행
   - sweep_summary.json 로드
   - AC-5 검증

### Modified (2개)
3. **D_ROADMAP.md** (+8, -8)
   - D205-10-1 상태: PLANNED → PARTIAL
   - Evidence 경로 추가
   - AC 달성 현황 업데이트 (4/6 PASS)

4. **docs/v2/reports/D205/D205-10-1_REPORT.md** (본 파일)
   - 테스트 결과 업데이트
   - AC 검증 상태 업데이트
   - MOCK 모드 제한사항 문서화

---

## 5. AC 검증 상태

- [x] **D205-10-1-1:** Threshold Sensitivity Sweep 실행 (buffer 0/2/5/8/10 bps) — ✅ Infrastructure PASS
- [x] **D205-10-1-2:** Best buffer 선택 (closed_trades > 0, error_count == 0, net_pnl 최대) — ✅ Logic PASS
- [~] **D205-10-1-3:** DecisionTrace 유효성 검증 (negative-control PASS) — ⚠️ PARTIAL (Real data 필요)
- [x] **D205-10-1-4:** Gate 3단 PASS (doctor/fast/regression) — ✅ 33/33 PASS
- [~] **D205-10-1-5:** 20m smoke PASS (best buffer_bps) — ⏭️ SKIP (MOCK 제한)
- [x] **D205-10-1-6:** Evidence 생성 (sweep_summary.json, manifest.json) — ✅ PASS

**달성률:** 4/6 PASS (Infrastructure), 2/6 PARTIAL/SKIP (Real data)

---

## 6. 알려진 이슈

### 6.1. MOCK 모드 제한사항
- **문제:** MOCK 데이터에서 buffer_bps 변경이 결과에 영향 없음
- **원인:** 고정 시뮬레이션 (spread/edge 계산에 buffer 미반영)
- **영향:** Threshold sensitivity 측정 불가
- **해결:** `--use-real-data` 플래그로 Real MarketData 사용

### 6.2. Negative-control 검증 불가
- **문제:** MOCK 모드에서 reject_reasons 모두 0
- **원인:** MOCK 데이터는 항상 profitable=True
- **영향:** DecisionTrace 실제 작동 검증 불가
- **해결:** Real data 또는 buffer_bps=999 강제 negative 테스트

---

## 7. 다음 단계

### 7.1. D205-10-2 (Optional): Real Data Sweep
- `--use-real-data` 플래그로 재실행
- 실제 threshold sensitivity 측정
- Negative-control 검증

### 7.2. D205-11: Latency Profiling
- Intent Loss 해결 완료 후 진행
- Latency 병목 분석

### 7.3. D205-12: Admin Control
- Paper/Live 전환 메커니즘
- Safety Guard 구현

---

## 8. Appendix

### 8.1. buffer_bps 후보 선정 근거

- **0 bps:** 현재 기준 (D205-10에서 설정)
- **1-3 bps:** 최소 버퍼 (네트워크 지연/슬리피지 최소 보상)
- **5 bps:** 이전 기준 (D205-10 이전)
- **8-10 bps:** 보수적 버퍼 (안전성 우선)

### 8.2. DecisionTrace Negative-Control 원리

- buffer_bps=999 → 모든 candidate가 profitable=False
- 기대: reject_reasons["profitable_false"] > 0
- 실패 시: reject_reasons 로직 버그 의심
