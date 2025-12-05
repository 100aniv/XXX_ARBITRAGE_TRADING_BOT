# D82-8: Intermediate Threshold Long-run Real PAPER & Runtime Edge Monitor

**Last Updated:** 2025-12-05 17:45 KST  
**Status:** 🟡 IN PROGRESS (Sweep 실행 중, 문서 초안 완료)

---

## 📋 목차

1. [요약](#요약)
2. [배경 & 동기](#배경--동기)
3. [실험 설계](#실험-설계)
4. [Runtime Edge Monitor 구현](#runtime-edge-monitor-구현)
5. [실행 결과](#실행-결과)
6. [분석 & 해석](#분석--해석)
7. [최종 추천](#최종-추천)
8. [향후 작업](#향후-작업)
9. [Acceptance Criteria](#acceptance-criteria)

---

## 📖 요약

### 목표

D82-6과 D82-7의 Gap을 메우는 **Intermediate Threshold Zone (Entry 10-14, TP 12-20 bps)**에서 Long-run Real PAPER를 실행하여:

1. **구조적으로 플러스 Zone** (Effective Edge > 0)
2. **실제 거래량 확보** (Round Trips ≥ 10)
3. **실제 수익성 검증** (PnL > 0)

→ **"운영 가능한 Threshold 후보"** 선정

### 핵심 성과

| 성과 | 결과 | 비고 |
|------|------|------|
| **Runtime Edge Monitor 구현** | ✅ 완료 | Rolling Window (50 trades), JSONL 로깅 |
| **Long-run Runner 구현** | ✅ 완료 | 3조합 × 20분 = 60분 |
| **Unit Tests** | ✅ 12/12 PASS | Edge Monitor 전용 테스트 |
| **Regression Tests** | ✅ 20/20 PASS | D82-5/7 회귀 없음 |
| **Long-run 실행** | 🟡 진행 중 | 17:36 시작, 예상 완료 18:36 |

---

## 🎯 배경 & 동기

### AS-IS 현황 (D82-6 / D82-7)

**D82-6: Entry 0.3-0.7, TP 1.0-2.0 bps**
- **문제:** 구조적 마이너스 Zone
- Effective Edge: **-1.14 bps** (손실 확정)
- 평균 슬리피지 2.14 bps > Entry threshold (0.3-0.7 bps)
- 결과: 9/9 조합 모두 손실, 평균 PnL **-305.92 bps**

**D82-7: Entry 14-18, TP 19-25 bps**
- **문제:** 구조적 플러스 but 거래 미발생
- Effective Edge: **+16.48 bps** (구조적으로 안전)
- 결과: 9/9 조합 모두 1 entry, 0 round trips
- 해석: Threshold 너무 높아 거래 기회 부족

### Gap 분석

| Zone | Entry (bps) | TP (bps) | Effective Edge | Trade Activity | 문제 |
|------|-------------|----------|----------------|----------------|------|
| **D82-6** | 0.3-0.7 | 1.0-2.0 | **마이너스** | 많음 | 구조적 손실 |
| **❓ Intermediate** | **10-14** | **12-20** | **???** | **???** | **미검증** |
| **D82-7** | 14-18 | 19-25 | 플러스 | 거의 없음 | 거래 기회 부족 |

**핵심 질문:**
- Intermediate Zone에서 **Effective Edge > 0** + **Trade Activity 충분**한 "Sweet Spot" 존재하는가?
- 만약 존재한다면, **최적 Entry/TP 조합**은 무엇인가?

---

## 🔬 실험 설계

### Threshold 조합 선정 (3개)

**근거:** D82-6/7 Edge 분석 결과 + 슬리피지/수수료 고려

| # | Entry (bps) | TP (bps) | Rationale |
|---|-------------|----------|-----------|
| 1 | **10.0** | **15.0** | 가장 낮은 threshold, 거래 기회 최대화. D82-6 (0.7/2.0) 대비 14.3배, D82-7 (14/19) 대비 71% |
| 2 | **12.0** | **18.0** | 중간 균형점. Slippage (2.14) + Fee (9.0) + Margin (0.86) 커버. Trade-off 최적화 목표 |
| 3 | **14.0** | **20.0** | Intermediate Zone 최상단. D82-7 하한 (14/19)과 유사, 구조적 안전성 + 거래량 확보 검증 |

**계산 근거:**
```
p95_slippage = 2.14 bps (D82-6/7 실측)
fee = 9.0 bps (Upbit 5 + Binance 4)
safety_margin = 0.5 ~ 2.0 bps

min_entry = p95_slip + fee + margin
          = 2.14 + 9.0 + 0.86
          = 12.0 bps

min_tp = min_entry + p95_slip + margin
       = 12.0 + 2.14 + 0.86
       = 15.0 bps
```

### 실행 파라미터

| 파라미터 | 값 | 근거 |
|----------|-----|------|
| **Duration per run** | 1200초 (20분) | Round Trips ≥ 10 목표 |
| **Total combinations** | 3 | 핵심 조합만 선택 |
| **Total duration** | 60분 (3 × 20분) | 1시간급 Long-run |
| **TopN size** | 20 | 기존 D82 시리즈와 일관성 |
| **Validation profile** | `none` | Long-run에서 overhead 제거 |
| **Edge Monitor** | Enabled | Rolling Window 50 trades |

### Acceptance Criteria

| Criteria | Target | 중요도 |
|----------|--------|--------|
| **최소 1개 조합 Round Trips ≥ 10** | 10+ RT | **CRITICAL** |
| **최소 1개 조합 Effective Edge > 0** | Edge > 0 | **CRITICAL** |
| **최소 1개 조합 PnL > 0** | PnL > $0 | HIGH |
| **Loop Latency < 25ms** | < 25ms avg | HIGH |
| **CPU < 50%** | < 50% avg | MEDIUM |
| **Edge Monitor 정상 작동** | Snapshot 생성 | MEDIUM |

---

## 💻 Runtime Edge Monitor 구현

### 설계 원칙

**목적:**
- Real PAPER 실행 중에 Rolling Window 기준으로 Effective Edge, Slippage, PnL 통계를 실시간 계산/로깅
- D85-x Tuning Cluster, Adaptive Threshold에서 재사용 가능한 데이터 구조

**핵심 기능:**
1. **Rolling Window:** 최근 N개 트레이드 기준 (기본 50개)
2. **Effective Edge 계산:** `Spread - Slippage - Fee`
3. **PnL 통계:** USD 및 bps 단위
4. **Win Rate 추적:** Win/Loss 카운트
5. **JSONL 로깅:** 타임스탬프별 Snapshot 기록

### 데이터 구조

**EdgeSnapshot:**
```python
@dataclass
class EdgeSnapshot:
    timestamp: str
    window_size: int
    
    # Edge 통계
    avg_spread_bps: float
    avg_slippage_bps: float
    avg_fee_bps: float
    effective_edge_bps: float  # spread - slippage - fee
    
    # PnL 통계
    avg_pnl_bps: float
    total_pnl_usd: float
    
    # 거래 통계
    total_trades: int
    win_count: int
    loss_count: int
    win_rate: float
```

**RuntimeEdgeMonitor:**
```python
class RuntimeEdgeMonitor:
    def __init__(self, window_size=50, output_path, enabled=True, fee_bps=9.0)
    def record_trade(self, trade: TradeLogEntry)
    def get_current_snapshot(self) -> Optional[EdgeSnapshot]
    def get_summary(self) -> Dict[str, Any]
```

### 테스트 결과

**Unit Tests:** 12/12 PASS (0.11초)
- Initialization
- Disabled monitor
- Single trade recording
- Rolling window behavior
- Snapshot generation (sufficient/insufficient data)
- Win rate calculation
- Edge calculation with non-zero slippage
- Snapshot logging to JSONL
- get_summary method
- Realistic trading scenario integration

**핵심 검증:**
- ✅ Rolling Window 정상 작동 (오래된 트레이드 자동 제거)
- ✅ Effective Edge = Spread - Slippage - Fee 계산 정확
- ✅ JSONL 로깅 정상 (타임스탬프별 Snapshot 기록)
- ✅ Win Rate 계산 정확
- ✅ Disabled 모드 정상 작동

---

## 📊 실행 결과

### 실행 정보

- **시작 시각:** 2025-12-05 17:36:19 KST
- **종료 시각:** TBD (예상 18:36 KST)
- **실제 소요 시간:** TBD (예상 60분)
- **실행 상태:** 🟡 **IN PROGRESS**

### Result Summary Table

| Rank | Entry (bps) | TP (bps) | Rationale | Entries | RT | Win Rate | PnL (USD) | Eff. Edge (bps) | Avg Slip (bps) | Latency (ms) | Status |
|------|-------------|----------|-----------|---------|-----|----------|-----------|-----------------|----------------|--------------|--------|
| 1    | 10.0        | 15.0     | 최저 threshold | TBD | TBD | TBD | TBD | TBD | TBD | TBD | 진행 중 |
| 2    | 12.0        | 18.0     | 중간 균형점 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | 대기 중 |
| 3    | 14.0        | 20.0     | Zone 최상단 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | 대기 중 |

**주:** 실행 완료 후 업데이트 예정

### Edge Monitor Snapshot 샘플

**예시 (Entry 10.0, TP 15.0, 첫 50 trades 기준):**
```json
{
  "timestamp": "2025-12-05T17:50:00",
  "window_size": 50,
  "avg_spread_bps": 12.5,
  "avg_slippage_bps": 2.14,
  "avg_fee_bps": 9.0,
  "effective_edge_bps": 1.36,
  "avg_pnl_bps": -5.2,
  "total_pnl_usd": -250.0,
  "total_trades": 50,
  "win_count": 18,
  "loss_count": 32,
  "win_rate": 0.36
}
```

**주:** 실제 데이터는 실행 완료 후 업데이트

---

## 🔍 분석 & 해석

### D82-6 / D82-7 / D82-8 비교

| 지표 | D82-6 | D82-7 | D82-8 | 변화 |
|------|-------|-------|-------|------|
| **Entry Range** | 0.3-0.7 | 14-18 | **10-14** | D82-6 대비 +14.3배 |
| **TP Range** | 1.0-2.0 | 19-25 | **12-20** | D82-6 대비 +7.5배 |
| **Effective Edge** | -1.14 bps | +16.48 bps | **TBD** | TBD |
| **평균 Entries** | 2.0 | 1.0 | **TBD** | TBD |
| **평균 Round Trips** | 1.0 | 0.0 | **TBD** | TBD |
| **평균 PnL** | -$750 | $0 | **TBD** | TBD |
| **Duration** | 6분 | 3분 | **20분** | +233% |

**분석 예상:**
1. **Trade Activity:** D82-7 (1 entry, 0 RT) → D82-8 (예상 5-15 entries, 3-10 RT)
2. **Effective Edge:** D82-6 (마이너스) vs D82-7 (플러스 but 미검증) → D82-8 (실제 검증)
3. **PnL:** D82-6 (손실), D82-7 (거래 없음) → D82-8 (실제 수익성 검증)

### Trade-off 곡선 분석

**가설:**
```
Entry/TP Threshold ↑
→ Effective Edge ↑ (구조적 안전성 증가)
→ Trade Activity ↓ (거래 기회 감소)
→ Actual PnL ??? (최적 균형점 탐색 필요)
```

**D82-8 목표:**
- **Sweet Spot 발견:** Edge > 0 + Trade Activity 충분 + PnL > 0
- **최적 Threshold 식별:** Entry 10-14 / TP 12-20 중 어느 조합이 최적인가?

### 인프라 안정성

**모니터링 항목:**
- Loop Latency: 목표 < 25ms (p99 < 40ms)
- CPU Usage: 목표 < 50%
- Memory: 목표 < 200MB
- Edge Monitor: Snapshot 생성 빈도 및 정확도

**주:** 실행 완료 후 실제 데이터로 업데이트

---

## 💡 최종 추천

### 추천 Threshold 후보

**(실행 완료 후 업데이트)**

**시나리오 1: Entry 10.0, TP 15.0이 최적인 경우**
- **근거:** 거래 기회 최대화 + Edge 플러스 + PnL 플러스
- **추천:** Entry 10, TP 15 bps로 `.env.paper` 업데이트
- **주의사항:** 변동성 높을 시 Edge 감소 가능

**시나리오 2: Entry 12.0, TP 18.0이 최적인 경우**
- **근거:** 균형잡힌 Trade-off
- **추천:** Entry 12, TP 18 bps로 설정
- **장점:** 중간 안전성 확보

**시나리오 3: 모든 조합이 여전히 거래 부족인 경우**
- **근거:** Threshold 추가 하향 필요
- **추천:** D82-9에서 Entry 8, TP 10 테스트
- **리스크:** 구조적 Edge 감소 가능성

---

## 🚀 향후 작업

### 단기 (D82-9 ~ D83-x)

1. **TP Threshold 미세 조정**
   - 문제: TP 15-20 bps가 여전히 높을 수 있음
   - 해결: TP 10-12 bps 추가 테스트

2. **Multi-Duration 실험**
   - 문제: 20분이 충분한 샘플 수를 제공하는가?
   - 해결: 1시간 / 3시간 / 12시간 Long-run 테스트

3. **WebSocket L2 Orderbook 통합 (D83-x)**
   - 목적: 실시간 슬리피지 추정
   - 기대 효과: Threshold를 더 공격적으로 낮춰도 안전

### 중기 (D84-x ~ D85-x)

4. **Multi-Universe 비교 (D84-x)**
   - Top20 vs Top50 vs Top100
   - Universe별 최적 Threshold 탐색

5. **Bayesian Optimization (D85-x)**
   - Grid Search → Bayesian Opt로 전환
   - 탐색 효율성 극대화

6. **Adaptive Threshold (D85-x+)**
   - 변동성 기반 동적 Threshold 조정
   - Edge Monitor 실시간 피드백 활용

### 장기 (D86-x+)

7. **Multi-Exchange Fill Model 고도화**
   - 거래소별 슬리피지 모델링
   - Partial Fill 유도 메커니즘 최적화

8. **Production Deployment**
   - Live Mode 전환
   - Risk Management 강화
   - Monitoring & Alerting

---

## ✅ Acceptance Criteria

| Criteria | Target | 결과 | 비고 |
|----------|--------|------|------|
| **최소 1개 조합 Round Trips ≥ 10** | 10+ RT | TBD | 거래량 충분성 검증 |
| **최소 1개 조합 Effective Edge > 0** | Edge > 0 | TBD | 구조적 수익 가능성 |
| **최소 1개 조합 PnL > 0** | PnL > $0 | TBD | 실제 수익성 검증 |
| **Loop Latency < 25ms** | < 25ms avg | TBD | 인프라 안정성 |
| **CPU < 50%** | < 50% avg | TBD | 리소스 효율성 |
| **Edge Monitor 정상 작동** | Snapshot 생성 | ✅ | Unit Tests 12/12 PASS |
| **Unit Tests PASS** | 100% PASS | ✅ 12/12 | Edge Monitor 테스트 |
| **Regression Tests PASS** | 100% PASS | ✅ 20/20 | D82-5/7 회귀 없음 |
| **문서화 완료** | D82_8 리포트 + D_ROADMAP | 🟡 | 초안 완료, 결과 대기 |

**종합 판단:** (실행 완료 후 업데이트)
- ✅ **GO:** 모든 CRITICAL 기준 달성
- ⚠️ **CONDITIONAL GO:** 일부 기준 미달, 조건부 진행
- ❌ **NO-GO:** CRITICAL 기준 실패, 재검증 필요

---

## 📝 산출물

### 코드

| 파일 | 설명 | 라인 수 | 테스트 |
|------|------|---------|--------|
| `arbitrage/logging/trade_logger.py` | Runtime Edge Monitor 추가 | +220 | 12/12 PASS |
| `scripts/run_d82_8_intermediate_threshold_longrun.py` | Long-run Runner | ~450 | - |
| `tests/test_d82_8_edge_monitor.py` | Edge Monitor Unit Tests | ~340 | 12/12 PASS |

### 문서

| 파일 | 설명 | 상태 |
|------|------|------|
| `docs/D82_8_INTERMEDIATE_THRESHOLD_LONGRUN_PAPER.md` | 본 문서 | 🟡 초안 완료 |
| `D_ROADMAP.md` | D82-8 섹션 추가 예정 | 대기 중 |

### 로그

| 파일 | 설명 | 상태 |
|------|------|------|
| `logs/d82-8/intermediate_threshold_longrun_summary.json` | Sweep Summary | 생성 중 |
| `logs/d82-8/runs/<run_id>_kpi.json` | 조합별 KPI | 생성 중 |
| `logs/d82-8/edge_monitor/<run_id>_edge.jsonl` | Edge Monitor Snapshot | 생성 중 |

---

**Last Updated:** 2025-12-05 17:45 KST  
**Status:** 🟡 IN PROGRESS (Sweep 실행 중, 문서 초안 완료)

**Next Steps:**
1. Sweep 완료 대기 (예상 18:36 KST)
2. 결과 분석 및 문서 업데이트
3. D_ROADMAP.md 업데이트
4. Git commit

---
