# D205-10-1: Threshold Sensitivity Sweep (브랜치 작업)

**⚠️ 브랜치 귀속:** 이 문서는 D205-10의 브랜치 작업(D205-10-1)입니다.  
**과거 오라벨:** D205-11 (SSOT 복구로 인해 D205-10-1로 재분류)

## 최종 상태: ⏳ PLANNED

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

### 3.1. Threshold Sensitivity Sweep

[완료 대기 중]

### 3.2. DecisionTrace 유효성 검증

[완료 대기 중]

### 3.3. 20m Smoke (Best buffer_bps)

[완료 대기 중]

---

## 4. 변경 파일 목록

1. `scripts/run_d205_11_threshold_sweep.py` (신규, D205-10-1용)
2. `scripts/run_d205_11_negative_control.py` (신규, DecisionTrace 검증)
3. `D_ROADMAP.md` (D205-10 브랜치 체계 + D205-11 원래 의미 복구)
4. `docs/v2/reports/D205/D205-10_REPORT.md` (D205-10-0으로 스코프 명확화)
5. `docs/v2/reports/D205/D205-10-1_REPORT.md` (본 파일, D205-11에서 rename됨)

---

## 5. AC 검증 상태

- [ ] **D205-10-1-1:** Threshold Sensitivity Sweep 실행 (buffer 0/2/5/8/10 bps)
- [ ] **D205-10-1-2:** Best buffer 선택 (closed_trades > 0, error_count == 0, net_pnl 최대)
- [ ] **D205-10-1-3:** DecisionTrace 유효성 검증 (negative-control PASS)
- [ ] **D205-10-1-4:** Gate 3단 PASS (doctor/fast/regression)
- [ ] **D205-10-1-5:** 20m smoke PASS (best buffer_bps)
- [ ] **D205-10-1-6:** Evidence 생성 (sweep_summary.json, manifest.json)

---

## 6. 알려진 이슈

없음 (작업 시작 전)

---

## 7. 다음 단계

1. **Step 3:** Threshold Sensitivity Sweep 실행
2. **Step 4:** DecisionTrace 유효성 검증
3. **Step 5:** Gate 3단
4. **Step 6:** 20m Smoke 재실행
5. **Step 7-10:** Evidence + 문서 + Git

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
