# D87-5: Zone Selection SHORT PAPER Validation Plan

**작성일:** 2025-12-08  
**상태:** 📋 **PLAN**

---

## 1. 배경

### D87-3 SHORT_VALIDATION 결과 (Before)
- **실행:** Advisory 30m + Strict 30m (2025-12-08)
- **결과:** Infrastructure PASS / Functional FAIL
  - Duration Guard: ✅ PASS (30.0분 정확 완주)
  - Fill Events: ✅ PASS (360개씩 수집)
  - **Zone 분포 차이:** ❌ **0%p** (목표: Z2 +5%p)
- **근본 원인:** FillModelIntegration의 additive bias (+5, +10)가 route 선택에 충분히 영향 못 미침

### D87-4 Zone-aware Route Selection (Solution)
- **변경:** Additive → Multiplicative Zone Preference
  ```python
  # AS-IS (D87-1/2): adjusted_score = base_score + bias
  # TO-BE (D87-4): adjusted_score = base_score * zone_pref
  ```
- **Mode별 Zone Preference Weight:**
  - `none`: Z1~Z4 모두 1.0 (neutral)
  - `advisory`: Z2=1.05, Z1/Z4=0.90, Z3=0.95
  - `strict`: Z2=1.15, Z1/Z4=0.80, Z3=0.85
- **효과 (base_score=60.0 기준):**
  - Advisory: Z2=63.0, Z1=54.0 → 차이 9점 (17%)
  - Strict: Z2=69.0, Z1=48.0 → 차이 21점 (44%)
- **테스트:** 13 tests, 100% PASS (Unit level)

### D87-5의 역할
**D87-4의 multiplicative zone preference가 실제 PAPER 환경에서 Zone 분포 차이를 만들어내는지 실전 검증.**

---

## 2. 실행 조건

### 2.1 Duration
- Advisory: **30분** (1800초 ±30초 허용)
- Strict: **30분** (1800초 ±30초 허용)
- **총 실행 시간:** 약 60분

### 2.2 Mode
- `--fillmodel-mode advisory`: Zone Preference = {Z2: 1.05, Z1/Z4: 0.90, Z3: 0.95}
- `--fillmodel-mode strict`: Zone Preference = {Z2: 1.15, Z1/Z4: 0.80, Z3: 0.85}

### 2.3 Universe & Data Source
- **L2 Source:** `--l2-source real` (Upbit WebSocket)
- **Symbol:** BTC/KRW (기본값)
- **Calibration:** `logs/d86-1/calibration_20251207_123906.json`
  - Z1: Entry 5-7 bps, BUY fill_ratio 0.2615 (26%)
  - Z2: Entry 7-12 bps, BUY fill_ratio 0.6307 (63%)
  - Z3: Entry 12-20 bps, BUY fill_ratio 0.2615 (26%)
  - Z4: Entry 20-30 bps, BUY fill_ratio 0.2615 (26%)

### 2.4 환경
- Python 3.14.0
- Docker: PostgreSQL, Redis, Prometheus, Grafana 모두 RUNNING
- DB/Redis 클린업 완료 (FLUSHALL)

---

## 3. 수집할 KPI

### 3.1 Zone 분포 (핵심 지표)
**Advisory vs Strict 비교:**
- **P(Z1):** Z1 트레이드 비중
- **P(Z2):** Z2 트레이드 비중 (고 fill ratio 구간)
- **P(Z3):** Z3 트레이드 비중
- **P(Z4):** Z4 트레이드 비중

**예상:**
- Strict: P(Z2) ↑, P(Z1/Z4) ↓
- Advisory: P(Z2) 약간 ↑, P(Z1/Z4) 약간 ↓

### 3.2 Zone별 RouteHealthScore
- **avg_score(Z1):** Z1 평균 점수
- **avg_score(Z2):** Z2 평균 점수
- **avg_score(Z3):** Z3 평균 점수
- **avg_score(Z4):** Z4 평균 점수

**예상:**
- Strict: score(Z2) >> score(Z1/Z4) (21점 차이)
- Advisory: score(Z2) > score(Z1/Z4) (9점 차이)

### 3.3 FillModelAdvice 관련
- **advice_count:** FillModelAdvice 호출 수
- **zone_selection_count:** Zone별 선택 횟수
- **adjustment_effect:** Zone preference 적용 전후 점수 변화

### 3.4 트레이딩 성과 (Sanity Check)
- **entry_trades:** Entry 트레이드 수
- **fill_events:** Fill Events 수 (BUY + SELL)
- **win_rate:** 승률
- **total_pnl:** 총 PnL
- **max_drawdown:** 최대 낙폭

---

## 4. 비교 기준 (Thresholds)

### 4.1 Strict vs Advisory Zone 분포 차이

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| **ΔP(Z2)** | ≥ **5%p** | Strict의 Z2 집중 효과 (이론값: +10~15%p) |
| **ΔP(Z1)** | ≤ **-3%p** | Strict의 Z1 회피 효과 |
| **ΔP(Z4)** | ≤ **-3%p** | Strict의 Z4 회피 효과 |

**계산 예시:**
```python
ΔP(Z2) = P(Z2)_strict - P(Z2)_advisory
# 예: Strict 50%, Advisory 40% → ΔP(Z2) = +10%p ✅ PASS
```

### 4.2 Zone별 평균 점수 차이

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| **score(Z2)_strict** | > score(Z2)_advisory | Strict의 Z2 우대 효과 |
| **score(Z1)_strict** | < score(Z1)_advisory | Strict의 Z1 패널티 효과 |
| **Δscore(Z2, Z1)_strict** | > Δscore(Z2, Z1)_advisory | Strict의 차별화 효과 증폭 |

**이론값 (base_score=60.0 기준):**
- Advisory: score(Z2)=63.0, score(Z1)=54.0 → Δ=9점
- Strict: score(Z2)=69.0, score(Z1)=48.0 → Δ=21점

### 4.3 D87-3 대비 개선

| Metric | D87-3 Result | D87-5 Target |
|--------|--------------|--------------|
| **ΔP(Z2)** | **0%p** ❌ | **≥5%p** ✅ |
| **ΔP(Z1/Z4)** | **0%p** ❌ | **≤-3%p** ✅ |
| **Zone 차별화** | **없음** ❌ | **명확함** ✅ |

---

## 5. Acceptance Criteria (D87-5)

| ID | Criteria | Threshold | Priority |
|----|----------|-----------|----------|
| **C1** | Duration 완주 | Advisory 30.0±0.5분, Strict 30.0±0.5분 | **CRITICAL** |
| **C2** | Fill Events 충분성 | ≥ 100개/세션 | **CRITICAL** |
| **C3** | Zone 분포 차이 (Z2) | ΔP(Z2) ≥ 5%p | **CRITICAL** |
| **C4** | Zone 분포 차이 (Z1/Z4) | ΔP(Z1) + ΔP(Z4) ≤ -3%p | **HIGH** |
| **C5** | Zone 점수 차별화 | Δscore(Z2, Z1)_strict > Δscore(Z2, Z1)_advisory | **HIGH** |
| **C6** | 인프라 안정성 | Fatal Exception 0건, WebSocket Reconnect ≤ 2회 | **CRITICAL** |
| **C7** | D87-1~4 회귀 테스트 | 전체 PASS | **CRITICAL** |

**C2 Fill Events 충분성 근거 (D87-5 현실화):**
- Runner 구조: 1초 루프, 10초마다 1 trade 생성 (`iteration % 10 == 0`)
- 30분 (1800초) → 최대 180 trades
- CalibratedFillModel: 1 trade → 평균 0.7~1.5 fill_events (BUY + SELL partial fills)
- 기대 fill_events: 180 trades × 1.0 avg = **120~270개**
- **최소 임계값 100개**: 통계적 유의성을 위한 충분한 샘플 크기
- ~~이전 값 300개~~: Runner 구조 대비 비현실적 → 수정

**Overall PASS 조건:**
- **CRITICAL (4개) 전체 PASS**
- **HIGH (2개) 중 최소 1개 PASS**

---

## 6. 실행 플로우

### 6.1 환경 준비 (Pre-flight)
1. 기존 Python arbitrage 프로세스 kill
2. Docker 상태 확인 (PostgreSQL, Redis, Prometheus, Grafana)
3. Redis FLUSHALL (이전 세션 상태 초기화)
4. DB 클린업 (필요시)
5. logs/d87-5/ 디렉토리 준비

### 6.2 테스트 실행
```bash
pytest tests/test_d87_1_* tests/test_d87_2_* tests/test_d87_3_* tests/test_d87_4_* tests/test_d87_5_* -v
```
- **기대 결과:** 전체 PASS

### 6.3 SHORT PAPER 실행 (30m+30m)
```bash
python scripts/d87_5_zone_selection_short_validation.py
```
- **Advisory 30m**
  - Duration: 1800초
  - Timeout: 2100초 (30m + 5분)
  - Output: logs/d87-5/d87_5_advisory_30m/
- **Strict 30m**
  - Duration: 1800초
  - Timeout: 2100초
  - Output: logs/d87-5/d87_5_strict_30m/

### 6.4 분석 & 리포트
```bash
python scripts/analyze_d87_3_fillmodel_ab_test.py \
    --advisory-dir logs/d87-5/d87_5_advisory_30m \
    --strict-dir logs/d87-5/d87_5_strict_30m \
    --calibration-path logs/d86-1/calibration_20251207_123906.json \
    --output logs/d87-5/d87_5_ab_summary.json
```
- **Output:**
  - logs/d87-5/d87_5_ab_summary.json (Zone 분포, 점수, PnL)
  - docs/D87/D87_5_STATUS.md (최종 판정)

### 6.5 문서 업데이트
- docs/D87/D87_5_STATUS.md (실행 결과, AC 평가, 최종 판정)
- D_ROADMAP.md (D87-5 섹션 추가)

### 6.6 Git Commit
```bash
git add .
git commit -m "[D87-5] Zone Selection Short PAPER Validation (Advisory vs Strict)"
```

---

## 7. 모니터링 체크리스트

### 7.1 실행 중 (Real-time)
- [ ] Entry Trades 발생 (매 5분 체크)
- [ ] Fill Events 누적 (목표: 300+/세션)
- [ ] FillModelAdvice 호출 (로그 확인)
- [ ] Zone 선택 분포 (실시간 카운트)
- [ ] WebSocket 연결 상태 (Upbit L2)
- [ ] Error/Warning 로그 (Fatal 0건 유지)

### 7.2 실행 후 (Post-mortem)
- [ ] Duration 정확도 (30.0±0.5분)
- [ ] KPI 파일 생성 (final_kpi.json)
- [ ] Fill Events 파일 생성 (fill_events_*.jsonl)
- [ ] Zone 분포 계산 (Analyzer)
- [ ] Advisory vs Strict 차이 (ΔP, Δscore)
- [ ] Acceptance Criteria 평가

---

## 8. 예상 결과

### 8.1 D87-3 vs D87-5 비교

| Metric | D87-3 (Before) | D87-5 (After) | Improvement |
|--------|----------------|---------------|-------------|
| **ΔP(Z2)** | **0%p** | **≥5%p** | ✅ 5~10%p |
| **ΔP(Z1/Z4)** | **0%p** | **≤-3%p** | ✅ -3~-5%p |
| **score(Z2)_strict** | ~63.0 | ~69.0 | ✅ +6점 |
| **score(Z1)_strict** | ~54.0 | ~48.0 | ✅ -6점 |
| **Zone 차별화** | **없음** | **명확함** | ✅ 2.3배 증폭 |

### 8.2 성공 시나리오 (PASS)
- Advisory: P(Z2) = 40~45%, P(Z1) = 25~30%, P(Z3) = 20~25%, P(Z4) = 5~10%
- Strict: P(Z2) = 50~60%, P(Z1) = 15~20%, P(Z3) = 15~20%, P(Z4) = 5~10%
- **ΔP(Z2) = +10~15%p** ✅
- **Δscore(Z2, Z1):** Advisory 9점 → Strict 21점 ✅

### 8.3 실패 시나리오 (FAIL)
- Advisory와 Strict의 Zone 분포 차이가 여전히 0~2%p 미만
- D87-4 zone_preference가 실제 환경에서 작동하지 않음
- 추가 디버깅 필요 (SignalEngine, ArbEngine 레벨)

---

## 9. 위험 요소 & 대응

### 9.1 위험: Zone 분포 차이가 여전히 미미함
**대응:**
- FillModelIntegration 로그 분석 (adjust_route_score 호출 확인)
- ArbRoute evaluate() 로그 분석 (zone_pref 적용 여부)
- SignalEngine 레벨 추가 디버깅

### 9.2 위험: 환경 제약 (세션 타임아웃)
**대응:**
- 30m+30m는 1시간 이내 완료 (D87-3 3h+3h 대비 안전)
- 필요시 15m+15m으로 축소 가능

### 9.3 위험: WebSocket 불안정
**대응:**
- D83-1 검증 완료 (5분 PAPER, 0 reconnect)
- 자동 재연결 메커니즘 (exponential backoff)
- Fallback: Mock L2 Provider

---

## 10. 산출물 체크리스트

- [ ] docs/D87/D87_5_ZONE_SELECTION_VALIDATION_PLAN.md (본 문서)
- [ ] scripts/d87_5_zone_selection_short_validation.py (실행 하네스)
- [ ] tests/test_d87_5_zone_selection_short_validation.py (테스트)
- [ ] logs/d87-5/d87_5_ab_summary.json (분석 결과)
- [ ] docs/D87/D87_5_STATUS.md (최종 판정)
- [ ] D_ROADMAP.md (D87-5 섹션 추가)
- [ ] Git commit: [D87-5] Zone Selection Short PAPER Validation

---

**작성자:** Windsurf AI  
**최종 수정:** 2025-12-08
