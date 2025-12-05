# D82-9: TP 13-15 bps Fine-tuning & Real PAPER Validation

**Last Updated:** 2025-12-05 20:25 KST  
**Status:** ✅ PAPER EXECUTION COMPLETE (5 runs completed, results analyzed)

---

## 📋 목차

1. [요약](#요약)
2. [배경 & 동기](#배경--동기)
3. [후보 분석 & 선정](#후보-분석--선정)
4. [Real PAPER Runner 설계](#real-paper-runner-설계)
5. [실행 결과](#실행-결과)
6. [분석 & 해석](#분석--해석)
7. [Acceptance Criteria](#acceptance-criteria)
8. [산출물](#산출물)

---

## 📖 요약

### 목표

D82-8 결과 분석 기반으로 TP Threshold를 13-15 bps로 하향 조정하여:
1. **TP 도달 가능성 증가** (D82-8 Win Rate 0% 문제 해결)
2. **실제 수익성 검증** (PnL > 0)
3. **운영 가능한 Threshold 최종 확정**

### 핵심 성과 (인프라)

| 성과 | 결과 | 비고 |
|------|------|------|
| **후보 분석 스크립트** | ✅ 완료 | 5개 후보 선정 (모두 Edge > 0) |
| **PAPER Runner** | ✅ 완료 | D82-8 Runner 재사용 |
| **Unit Tests** | ✅ 10/10 PASS | 후보 분석 + Runner |
| **Regression Tests** | ✅ 32/32 PASS | D82-5/7/8 회귀 없음 |
| **Total Tests** | ✅ **42/42 PASS** | 모든 테스트 통과 |
| **Real PAPER 실행** | ✅ 완료 | 5조합 × 10분 = 50분 |

---

## 🎯 배경 & 동기

### D82-6 / D82-7 / D82-8 회고

| Task | Entry (bps) | TP (bps) | Effective Edge | Trade Activity | Win Rate | PnL | 문제 |
|------|-------------|----------|----------------|----------------|----------|-----|------|
| **D82-6** | 0.3-0.7 | 1.0-2.0 | **-1.14** (마이너스) | 높음 (2 entries) | 0% | -$750 | 구조적 손실 |
| **D82-7** | 14-18 | 19-25 | **+16.48** (플러스) | 거의 없음 (1 entry) | 0% | $0 | 거래 미발생 |
| **D82-8** | 10-14 | 15-20 | **미검증** | 높음 (6-7 entries) | **0%** | **-$3,500** | **TP 과도** |

### D82-8의 핵심 발견

✅ **성공 요소:**
- Entry 10-14 bps는 거래 발생 확인 (6 RT)
- 인프라 안정 (Latency 13-14ms, CPU 35%, Memory 150MB)
- Edge Monitor 정상 작동

❌ **실패 요소:**
- TP 15-20 bps는 현재 시장 변동성 대비 달성 불가
- 모든 조합 Win Rate 0% (exit_reason: time_limit)
- PnL 악화 (D82-6 대비 4.7배 손실 증가)

### D82-9의 가설

**가설:** TP를 13-15 bps로 낮추면 TP 도달 가능성이 증가하여 Win Rate와 PnL이 개선될 것이다.

**근거:**
- D82-8에서 Entry 10-14는 거래 발생 확인 (적절)
- TP 15-20은 모두 time_limit → 너무 높음
- TP를 -2~-5 bps 낮추면 TP 도달 가능성 증가

---

## 🔬 후보 분석 & 선정

### 분석 기준

**구조적 안전성 (필수):**
```
Effective Edge = (Entry + TP) / 2 - Slippage - Fee > 0
                = (Entry + TP) / 2 - 2.14 - 9.0 > 0
```

**Trade-off 고려:**
- Entry ↓ → 거래 기회 ↑ (D82-8에서 검증)
- TP ↓ → Win Rate ↑ (가설)
- Edge ↑ → 구조적 안전성 ↑

### 초기 범위 탐색 (TP 10-12 bps)

**문제 발견:** TP 10-12 bps는 구조적으로 Edge 마이너스!

| Entry | TP | Effective Edge | Structural Safety |
|-------|-----|----------------|-------------------|
| 10.0  | 10.0 | **-1.14** | ❌ |
| 10.0  | 11.0 | **-0.64** | ❌ |
| 10.0  | 12.0 | **-0.14** | ❌ |
| 12.0  | 12.0 | **+0.86** | ✅ (단 1개만) |

**결론:** TP 10-12는 너무 낮음. D82-7 최소값 (min_tp=19)과 괴리 너무 큼.

### 현실적 범위 재조정 (TP 13-15 bps)

**조정 근거:**
- D82-7 분석: min_tp = 19 bps (구조적 최소값)
- D82-8 실험: TP 15-20 bps (Win Rate 0%)
- **D82-9 목표:** TP 13-15 bps (D82-8 대비 -2~-5 bps 낮춤)

### 선정된 5개 후보

| # | Entry (bps) | TP (bps) | Edge (bps) | Priority | Rationale |
|---|-------------|----------|------------|----------|-----------|
| **1** | **10.0** | **13.0** | **+0.36** | 1 | Entry 최저 + TP 최저. 거래 기회 최대화 + TP 도달 가능성 향상 |
| **2** | **10.0** | **14.0** | **+0.86** | 2 | Entry 최저 + TP 중간. Trade Activity 최고, Win Rate 기대 |
| **3** | **12.0** | **13.0** | **+1.36** | 3 | Entry 중간 + TP 최저. 균형적 접근 |
| **4** | **12.0** | **14.0** | **+1.86** | 4 | Entry 중간 + TP 중간. 보수적 균형점 |
| **5** | **10.0** | **15.0** | **+1.36** | 5 | Entry 최저 + TP 중상. D82-8 (10/15)와 동일, 재검증 목적 |

**공통 특징:**
- ✅ 모두 Effective Edge > 0 (구조적 안전)
- ✅ Entry 10-14 bps (D82-8에서 거래 발생 확인)
- ✅ TP 13-15 bps (D82-8 대비 -2~-7 bps 낮춤)

---

## 💻 Real PAPER Runner 설계

### 핵심 설계 원칙

1. **기존 인프라 재사용**
   - D82-8 Runner 구조 재사용
   - Runtime Edge Monitor 활성화
   - `run_d77_0_topn_arbitrage_paper.py` 호출

2. **후보 JSON 기반 실행**
   - `logs/d82-9/selected_candidates.json` 로드
   - 각 후보를 순차 실행
   - Duration: 20분 (기본) or 1시간 (권장)

3. **출력 구조**
   ```
   logs/d82-9/
   ├── selected_candidates.json         # 후보 리스트
   ├── runs/
   │   ├── d82-9-E10p0_TP13p0-<timestamp>_kpi.json
   │   ├── d82-9-E10p0_TP14p0-<timestamp>_kpi.json
   │   └── ...
   ├── edge_monitor/
   │   ├── d82-9-E10p0_TP13p0-<timestamp>_edge.jsonl
   │   ├── d82-9-E10p0_TP14p0-<timestamp>_edge.jsonl
   │   └── ...
   └── paper_summary.json                # Sweep 요약
   ```

### Usage

```powershell
# Dry-run (명령만 출력)
python scripts/run_d82_9_paper_candidates_longrun.py --dry-run

# 20분 실행 (기본, 빠른 검증용)
python scripts/run_d82_9_paper_candidates_longrun.py

# 1시간 실행 (권장, 충분한 RT 확보)
python scripts/run_d82_9_paper_candidates_longrun.py --run-duration-seconds 3600
```

### Acceptance Criteria

**최소 1개 조합이라도:**
- Round Trips ≥ 10
- Win Rate > 0% (time_limit 아닌 take_profit 청산)
- PnL USD ≥ 0

**인프라 안정성 (D82-8과 동일):**
- Loop Latency < 25ms
- CPU < 50%
- Memory < 200MB

---

## 📊 실행 결과

### 실행 정보

- **시작 시각:** 2025-12-05 19:32 KST
- **종료 시각:** 2025-12-05 20:24 KST
- **소요 시간:** 52분 (환경 정리 포함)
- **실행 상태:** ✅ **COMPLETE** (5개 조합 모두 정상 완료)
- **Duration per run:** 10분 (600초)

### Result Summary Table

| # | Entry (bps) | TP (bps) | Entries | RT | Win Rate | PnL (USD) | Avg Slip (bps) | Latency (ms) | Score | Status |
|---|-------------|----------|---------|-----|----------|-----------|----------------|--------------|-------|--------|
| **1** | **10.0** | **14.0** | 2 | 2 | **0.0%** | **-$823.59** | 2.14 | 14.29 | -82357 | ❌ FAIL |
| 2 | 12.0 | 13.0 | 3 | 2 | 0.0% | -$850.11 | 2.14 | 14.71 | -85010 | ❌ |
| 3 | 10.0 | 13.0 | 3 | 2 | 0.0% | -$925.91 | 2.14 | 16.50 | -92590 | ❌ |
| 4 | 10.0 | 15.0 | 3 | 2 | 0.0% | -$1036.68 | 2.14 | 15.19 | -103667 | ❌ |
| 5 | 12.0 | 14.0 | 4 | **3** | 0.0% | -$2720.05 | 2.14 | 14.48 | -272002 | ❌ |

**실제 결과:**
- ❌ 모든 조합 Win Rate 0% (time_limit 청산)
- ❌ 모든 조합 PnL 마이너스 (-$824 ~ -$2,720)
- ✅ Round Trips 2-3 (거래는 발생)
- ✅ 인프라 안정 (Latency 14-16ms, CPU 35%, Memory 150MB)
- **Best candidate:** Entry 10.0, TP 14.0 (Composite Score: -82357)

---

## 🔍 분석 & 해석

### D82-6 / D82-7 / D82-8 / D82-9 비교

| 지표 | D82-6 | D82-7 | D82-8 | **D82-9 (실제)** |
|------|-------|-------|-------|--------------------|
| **Entry Range** | 0.3-0.7 | 14-18 | 10-14 | **10-12** |
| **TP Range** | 1.0-2.0 | 19-25 | 15-20 | **13-15** |
| **Effective Edge** | -1.14 bps | +16.48 bps | 미검증 | **+0.36~+1.86** |
| **평균 Entries** | 2.0 | 1.0 | 6.7 | **3.0** |
| **평균 RT** | 1.0 | 0.0 | 6.0 | **2.2** |
| **Win Rate** | 0% | 0% | 0% | **0%** ❌ |
| **평균 PnL** | -$750 | $0 | -$3,500 | **-$1,271** |
| **Duration** | 6분 | 3분 | 20분 | **10분** |

### 가설 검증

**가설 1:** TP 13-15는 TP 15-20보다 도달 가능성이 높다.
- **검증 방법:** Win Rate > 0%, exit_reason에 'take_profit' 포함
- **결과:** ❌ **REJECTED** - 여전히 Win Rate 0% (모두 time_limit 청산)
- **원인 분석:** 10분 Duration이 짧았거나, TP 13-15도 여전히 높음

**가설 2:** TP 도달 시 PnL이 개선된다.
- **검증 방법:** PnL ≥ 0
- **결과:** ❌ **REJECTED** - 모든 조합 PnL 마이너스 (-$824 ~ -$2,720)
- **원인 분석:** TP 미도달 + Buy Slippage 2.14 bps 누적

**가설 3:** Effective Edge +0.36~+1.86는 운영 가능하다.
- **검증 방법:** RT ≥ 10, PnL > 0, 인프라 안정
- **결과:** ⚠️ **PARTIAL** - 인프라는 안정 (Latency 14-16ms), 단 RT 2-3으로 부족
- **원인 분석:** 10분 Duration으로는 충분한 RT 확보 불가

### 핵심 발견

**1. TP 13-15도 여전히 도달 불가**
- D82-8 (TP 15-20): Win Rate 0%
- D82-9 (TP 13-15): Win Rate 0% (동일)
- **결론:** TP 하향만으로는 문제 해결 안 됨

**2. Duration 10분은 불충분**
- 평균 RT 2.2 (D82-8의 6.0 대비 63% 감소)
- 통계적 유의성 부족

**3. PnL 개선 (D82-8 대비 64% 감소)**
- D82-8: 평균 -$3,500
- D82-9: 평균 -$1,271 (36% 수준)
- 손실 규모는 줄었으나 여전히 마이너스

**4. 인프라는 안정**
- Latency 14-16ms (목표 < 25ms 충족)
- CPU 35%, Memory 150MB (안정적)
- Edge Monitor 정상 작동

---

## ✅ Acceptance Criteria

| Criteria | Target | 결과 | 비고 |
|----------|--------|------|------|
| **최소 1개 조합 RT ≥ 10** | 10+ RT | ❌ 2-3 RT | Duration 10분 부족 |
| **최소 1개 조합 Win Rate > 0%** | > 0% | ❌ 0% | TP 여전히 도달 불가 |
| **최소 1개 조합 PnL ≥ 0** | ≥ $0 | ❌ -$824 ~ -$2,720 | Slippage 누적 손실 |
| **Loop Latency < 25ms** | < 25ms avg | ✅ 14-16ms | 인프라 안정 |
| **CPU < 50%** | < 50% avg | ✅ 35% | 리소스 효율적 |
| **Edge Monitor 정상 작동** | Snapshot 생성 | ✅ | JSONL 파일 생성 확인 |
| **Unit Tests PASS** | 100% PASS | ✅ 10/10 | 후보 분석 + Runner |
| **Regression Tests PASS** | 100% PASS | ✅ 32/32 | D82-5/7/8 회귀 없음 |
| **Total Tests** | 100% PASS | ✅ **42/42** | 모든 테스트 통과 |

**종합 판단:** ❌ **NO-GO** (TP 하향 전략 실패)
- ✅ 인프라 안정성 확인 (Latency, CPU, Memory)
- ❌ Win Rate 0% (가설 1 기각)
- ❌ PnL 마이너스 (가설 2 기각)
- ❌ RT 2-3 (Duration 부족)

---

## 💡 최종 추천

### 시나리오 B 발생: 모든 조합 Criteria 미충족 ❌

**원인 분석:**
1. **TP 13-15도 여전히 높음** - 현재 시장 변동성 대비 도달 불가
2. **Duration 10분 부족** - RT 2-3으로 통계적 유의성 부족
3. **Buy Slippage 누적** - 2.14 bps × 3 entries = -6.4 bps 누적
4. **Partial Fill 비율 높음** - Fill Ratio 26% (1/4만 체결)

**제안 조치 (우선순위):**

**Option 1: WebSocket L2 Orderbook 우선 도입 (권장)** ⭐
- D82-6/7/8/9 모두 Mock Fill Model 기반 (슬리피지 과대 추정 가능)
- L2 Orderbook으로 실제 슬리피지 추정 시 TP 범위 재평가
- 예상: TP 10-12 bps도 가능해질 수 있음

**Option 2: 20분+ Long-run 재실행**
- Duration 20분 or 1시간으로 재실행
- RT 10+ 확보하여 통계적 유의성 확보
- 단, Win Rate 0% 문제는 미해결 가능성

**Option 3: Entry 상향 조정**
- Entry 14-18 bps로 상향 (D82-7 스타일)
- 거래 기회는 줄지만 TP 도달 가능성 증가
- 단, D82-7에서도 거래 미발생 문제 있었음

**권장 경로:** Option 1 → D83-x WebSocket L2 Orderbook 도입

---

## 🚀 향후 작업

### 단기 (D82-9 완료 후)
1. ✅ **Real PAPER 실행 완료** (5조합 × 10분)
2. ✅ **결과 분석 및 문서 업데이트** (현재 문서)
3. ❌ **Threshold 확정 불가** - 모든 조합 Criteria 미충족
4. **Next:** D83-x WebSocket L2 Orderbook 도입 (필수)

### 중기 (D83-x)
1. **WebSocket L2 Orderbook 통합**
   - 실시간 슬리피지 추정
   - Threshold를 더 공격적으로 낮춰도 안전

2. **Long-run Validation (3h/6h/12h)**
   - 선정된 Threshold로 장시간 검증
   - 통계적 유의성 확보

### 장기 (D85-x)
1. **Bayesian Optimization**
   - Runtime Edge Monitor 피드백 활용
   - Grid Search → Bayesian Opt 전환

2. **Adaptive Threshold**
   - 변동성 기반 동적 조정
   - Edge Monitor 실시간 피드백

---

## 📝 산출물

### 코드

| 파일 | 설명 | 라인 수 | 테스트 |
|------|------|---------|--------|
| `scripts/analyze_d82_9_tp_candidates.py` | 후보 분석 & 선정 | ~380 | 10/10 PASS |
| `scripts/run_d82_9_paper_candidates_longrun.py` | PAPER Runner | ~450 | Dry-run OK |
| `tests/test_d82_9_tp_finetuning.py` | Unit Tests | ~320 | 10/10 PASS |
| **Total** | | **~1,150** | **42/42 PASS** |

### 문서

| 파일 | 설명 | 상태 |
|------|------|------|
| `docs/D82_9_TP_FINE_TUNING_PAPER.md` | 실험 설계 & 결과 분석 | ✅ 초안 완료 |
| `D_ROADMAP.md` | D82-9 섹션 추가 | ⏳ 업데이트 예정 |

### 로그 & 데이터

| 파일 | 설명 | 상태 |
|------|------|------|
| `logs/d82-9/selected_candidates.json` | 선정된 5개 후보 | ✅ 생성 완료 |
| `logs/d82-9/runs/<run_id>_kpi.json` | 조합별 KPI (5개) | ✅ 생성 완료 |
| `logs/d82-9/edge_monitor/<run_id>_edge.jsonl` | Edge Monitor Snapshot (5개) | ✅ 생성 완료 |
| `logs/d82-9/paper_summary.json` | Sweep 요약 | ✅ 생성 완료 |

---

## 🎯 핵심 인사이트

### 1. TP 10-12 bps는 구조적으로 불가능

D82-7 분석 (min_tp=19)과 실제 계산이 일치:
- TP < 13 bps는 Effective Edge < 0 (구조적 손실)
- 현실적 하한: TP 13 bps (Edge +0.36)

### 2. D82-8 → D82-9: TP만 조정

Entry 10-14 bps는 D82-8에서 거래 발생 확인 (적절):
- Entry는 유지
- TP만 15-20 → 13-15로 하향 (-2~-5 bps)

### 3. Trade-off 존재

- TP ↓ → Win Rate ↑ (TP 도달 가능성)
- TP ↓ → Edge ↓ (구조적 안전성)
- **최적 균형점 탐색:** TP 13-15 bps

### 4. 검증 철학 확립

D82-9부터 공식 표준:
1. 이론 설계 (Edge 분석)
2. ~~백테스트~~ → **직접 PAPER** (현재 시스템)
3. 리얼 PAPER 계단 검증 (20분 → 1h → 3h+)
4. LIVE 승격

---

**Last Updated:** 2025-12-05 20:25 KST  
**Status:** ❌ NO-GO (TP 하향 전략 실패, WebSocket L2 필요)  
**Next Steps:**
1. D83-x: WebSocket L2 Orderbook 도입 (슬리피지 재평가)
2. L2 기반으로 TP 10-12 bps 재검토
3. D_ROADMAP.md 업데이트 (D82-9 NO-GO 반영)

---
