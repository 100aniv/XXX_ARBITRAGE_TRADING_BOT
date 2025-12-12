# D92-5 Exit Logic Redesign Plan

**Date:** 2025-12-13  
**Status:** 📋 PLAN (D92-4 스윕 결과 기반)

---

## 🎯 목표

D92-4 Parameter Sweep에서 발견된 근본 문제 해결:
- ✗ Win rate 0% (모든 거래 손실)
- ✗ TP/SL 트리거 0회 (TIME_LIMIT 100%)
- ✗ 수수료/슬리피지 > 스프레드 이익

**목표:**
1. TP/SL 조건을 현실적으로 재설계 → 최소 10% 거래에서 트리거
2. TIME_LIMIT 청산 로직 개선 → 무조건 손실 방지
3. 수수료/슬리피지 모델 검증 → 승률 30% 이상 달성

---

## 📊 D92-4 스윕 결과 요약

### 전체 실행 결과

| Threshold | Duration | RT | Win/Loss | PnL (USD) | Exit Reasons |
|-----------|----------|----|----|-----------|--------------|
| 5.0 bps | 60m | 2 | 0W/2L | -$10.31 | TIME_LIMIT: 100% |
| 4.8 bps | 60m | 7 | 0W/7L | -$11.0K | TIME_LIMIT: 100% |
| 4.5 bps | 12m | 4 | 0W/4L | -$17.8K | TIME_LIMIT: 100% |

### 핵심 문제

1. **TP/SL이 한 번도 트리거되지 않음**
   - 현재 설정값이 시장 변동성 대비 도달 불가능
   - 모든 포지션이 TIME_LIMIT으로만 청산

2. **TIME_LIMIT 청산 = 항상 손실**
   - 무조건 시장가 청산 → 스프레드 역전 시 손실
   - 최소 손실 조건 없음

3. **수수료/슬리피지가 과다**
   - Entry 스프레드 이익을 모두 상쇄
   - Paper mode 비용 모델 검증 필요

---

## 🔍 Phase 1: 현재 상태 파악

### 1.1 TP/SL 설정값 확인

**조사 대상:**
- `run_d77_0_topn_arbitrage_paper.py`: TP/SL 로직 위치
- `configs/paper/topn_arb_baseline.yaml`: 설정 파일
- 실제 코드에서 사용되는 TP/SL 값

**확인 사항:**
- TP: 몇 bps? (예: 10 bps?)
- SL: 몇 bps? (예: -5 bps?)
- 계산 방식: 절대값? Entry 대비 상대값?

### 1.2 실제 시장 스프레드 변동성 분석

**데이터 소스:**
- D92-4 스윕 로그 (C1~C3)
- Entry 시 스프레드 vs Exit 시 스프레드

**분석 항목:**
- 스프레드 범위: Min/Max/Avg/P50/P95
- Entry 후 스프레드 변화 패턴
- TIME_LIMIT 시점의 스프레드 분포

### 1.3 수수료/슬리피지 모델 확인

**조사 대상:**
- Paper mode에서 적용되는 수수료율
- 슬리피지 계산 로직 (고정값? 동적?)
- Entry vs Exit 비용 분해

---

## 🛠️ Phase 2: Exit 로직 재설계

### 2.1 TP/SL 재설계

**현실적인 값 도출:**
1. D92-4 로그에서 스프레드 변동성 분석
2. P50 스프레드 변화를 기준으로 TP/SL 설정
3. 목표: 최소 10% 거래에서 TP 또는 SL 트리거

**예상 조정:**
```python
# 기존 (추정)
TP = +10 bps  # 너무 높음
SL = -5 bps   # 너무 낮음

# 재설계 (예시)
TP = +3 bps   # P75 스프레드 변화 기준
SL = -2 bps   # P25 스프레드 변화 기준
```

### 2.2 TIME_LIMIT 청산 로직 개선

**현재 (추정):**
```python
if time_limit_reached:
    exit_at_market_price()  # 무조건 청산
```

**개선안 1: 최소 손실 조건**
```python
if time_limit_reached:
    if current_pnl > -max_acceptable_loss:
        exit_at_market_price()
    else:
        # 손실이 너무 크면 대기 또는 손절 연장
        extend_time_limit(60)  # 1분 연장
```

**개선안 2: 스프레드 조건 추가**
```python
if time_limit_reached:
    if current_spread < entry_spread * 0.5:
        # 스프레드가 충분히 좁아지면 청산
        exit_at_market_price()
    else:
        # 스프레드가 여전히 넓으면 대기
        wait_for_better_spread()
```

### 2.3 수수료/슬리피지 모델 조정

**검증 항목:**
1. Paper mode 수수료율이 실제 거래소와 일치하는지
2. 슬리피지가 과다 적용되는지
3. Entry 스프레드 > (수수료 + 슬리피지) 조건 확보

**목표:**
- 최소 Entry 스프레드 = (수수료 + 슬리피지) × 1.5
- 승률 30% 이상 달성

---

## 🧪 Phase 3: 검증 및 테스트

### 3.1 단위 테스트

**신규 테스트:**
- `test_d92_5_tp_sl_trigger.py`: TP/SL 트리거 조건 검증
- `test_d92_5_time_limit_logic.py`: TIME_LIMIT 청산 로직 검증
- `test_d92_5_cost_model.py`: 수수료/슬리피지 계산 검증

**목표:** 100% PASS

### 3.2 10분 스모크 테스트

**실행:**
```powershell
python scripts/run_d92_1_topn_longrun.py --top-n 10 --duration-minutes 10 --mode advisory
```

**성공 기준:**
- TP 또는 SL 트리거 ≥ 1회
- Win rate > 0%
- TIME_LIMIT < 100%

### 3.3 60분 베이스 테스트

**실행:**
```powershell
python scripts/run_d92_1_topn_longrun.py --top-n 10 --duration-minutes 60 --mode advisory
```

**성공 기준:**
- Win rate ≥ 30%
- TP/SL 트리거 비율 ≥ 10%
- PnL > 0 (또는 최소 손실 < -$100)

---

## 📝 Acceptance Criteria

### Critical (필수)

1. **C1: TP/SL 트리거 발생**
   - 60분 테스트에서 TP 또는 SL 최소 1회 이상 트리거
   - TIME_LIMIT 비율 < 90%

2. **C2: Win rate 개선**
   - Win rate > 0% (D92-4에서 0%였음)
   - 목표: 30% 이상

3. **C3: PnL 개선**
   - 60분 테스트 PnL > -$100 (D92-4에서 -$11K)
   - 목표: PnL > 0

### High Priority (권장)

1. **H1: Exit reason 다양화**
   - TP: ≥ 5%
   - SL: ≥ 5%
   - TIME_LIMIT: ≤ 90%

2. **H2: 비용 구조 검증**
   - Entry 스프레드 > (수수료 + 슬리피지) × 1.5
   - 평균 RT당 순이익 > 0

3. **H3: 재현성**
   - 동일 조건에서 3회 반복 테스트 시 유사한 결과

---

## 🚀 실행 계획

### Step 1: 현재 상태 파악 (1시간)
- TP/SL 설정값 확인
- 스프레드 변동성 분석
- 수수료/슬리피지 모델 확인

### Step 2: Exit 로직 재설계 (2시간)
- TP/SL 값 재계산
- TIME_LIMIT 로직 개선
- 수수료/슬리피지 조정

### Step 3: 단위 테스트 (1시간)
- 신규 테스트 작성
- 100% PASS 확인

### Step 4: 통합 테스트 (2시간)
- 10분 스모크 테스트
- 60분 베이스 테스트
- Acceptance Criteria 검증

### Step 5: 문서화 및 커밋 (1시간)
- D92_5_SESSION_SUMMARY.md 작성
- D_ROADMAP.md 업데이트
- Git commit (한글 메시지)

**총 예상 시간:** 7시간

---

## 📌 참고 자료

- D92-4 스윕 결과: `docs/D92/D92_4_SESSION_SUMMARY.md`
- D92-4 로그: `logs/d77-0/d82-0-top_10-2025121*_kpi_summary.json`
- 현재 Exit 로직: `scripts/run_d77_0_topn_arbitrage_paper.py`
- TP/SL 설정: `configs/paper/topn_arb_baseline.yaml` (추정)
