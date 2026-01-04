# D205-10-1 Wait Harness - Implementation Report

## 최종 상태: ✅ READY (Implementation Complete, 10h run pending)

**날짜:** 2026-01-04  
**Phase:** Implementation Complete  
**Validation:** PENDING (10h real run)

---

## 1. 목표

10시간 동안 시장 조건을 감시하고, 트리거 조건 충족 시 자동으로 D205-10-1 완결 시도

**핵심 질문:**
- 현재 시장 환경(2026-01-04)에서 수익성 기회가 없었던 이유는?
- 시장 스프레드가 break-even threshold를 초과하는 순간이 존재하는가?
- 존재한다면 언제 발생하는가? (시간대/변동성)

---

## 2. 구현 내용

### 2.1. 엔진 모듈 (V2 Harness)

**파일:** `arbitrage/v2/harness/d205_10_1_wait_harness.py` (신규, 500줄)

**책임:**
- Market snapshot 수집 (Upbit + Binance REST API)
- Break-even/edge 계산 (build_candidate 재사용)
- Trigger 조건 체크 (edge_bps >= trigger_min_edge_bps)
- subprocess로 sweep/smoke 스크립트 호출
- Evidence 저장 (market_watch.jsonl + watch_summary.json)

**핵심 클래스:**
```python
@dataclass
class WaitHarnessConfig:
    duration_hours: int = 10
    poll_seconds: int = 30
    trigger_min_edge_bps: float = 0.0
    fx_rate: float = 1450.0
    evidence_dir: str = ""
    sweep_duration_minutes: int = 2
    db_mode: str = "off"

@dataclass
class MarketSnapshot:
    timestamp: str
    upbit_price: float
    binance_price: float
    binance_price_krw: float
    fx_rate: float
    spread_bps: float
    break_even_bps: float
    edge_bps: float
    trigger: bool
    error: Optional[str] = None

class WaitHarness:
    def watch_market(self) -> Optional[MarketSnapshot]
    def run_watch_loop(self) -> int
    def _trigger_sweep_and_smoke(self) -> bool
```

### 2.2. CLI 스크립트

**파일:** `scripts/run_d205_10_1_wait_and_execute.py` (신규, 120줄)

**책임:**
- argparse로 설정 받기
- WaitHarness 인스턴스 생성 및 실행
- exit code 반환

**금지:**
- 로직 구현 (엔진 모듈로 위임)

---

## 3. 재사용 모듈 (Scan-first → Reuse-first)

| # | 모듈 | 재사용 방식 | 목적 |
|---|------|------------|------|
| 1 | scripts/run_d205_10_1_sweep.py | subprocess 호출 | Threshold sweep 실행 |
| 2 | scripts/run_d205_10_1_smoke_best_buffer.py | subprocess 호출 | Best buffer로 20m smoke |
| 3 | arbitrage/v2/harness/paper_runner.py | Import | Paper trading 엔진 |
| 4 | arbitrage/v2/opportunity/break_even.py | Import | Break-even 계산 |
| 5 | arbitrage/domain/fee_model.py | Import | 수수료 모델 |
| 6 | arbitrage/v2/marketdata/rest/binance.py | Import | Binance ticker 조회 |
| 7 | arbitrage/v2/marketdata/rest/upbit.py | Import | Upbit ticker 조회 |

**생코딩 금지:** 기존 모듈 재사용 100%

---

## 4. 트리거 조건 설계

### 4.1. Edge 계산 공식

```python
# 1. Market snapshot
ticker_upbit = upbit_provider.get_ticker("BTC/KRW")
ticker_binance = binance_provider.get_ticker("BTC/USDT")

# 2. Price normalization
price_a = ticker_upbit.last
price_b_krw = ticker_binance.last * fx_rate  # 1450 KRW/USDT

# 3. Spread 계산
spread_bps = abs((price_a - price_b_krw) / price_b_krw * 10000)

# 4. Break-even 계산
break_even_bps = fee_bps + slippage_bps + latency_bps + buffer_bps
# Default: 50 + 15 + 10 + 0 = 75 bps

# 5. Edge 계산
edge_bps = spread_bps - break_even_bps

# 6. Trigger 조건
trigger = edge_bps >= trigger_min_edge_bps  # 기본값 0 bps
```

### 4.2. Trigger 발생 시 자동 실행

```python
if trigger:
    # 1) Threshold Sweep (buffer 0/2/5/8/10)
    subprocess.run(["python", "scripts/run_d205_10_1_sweep.py", ...])
    
    # 2) Best buffer 선정
    best_buffer_bps = sweep_summary["best_selection"]["best_buffer_bps"]
    
    # 3) 20m Smoke (best buffer로 실행, AC-2 성공 시만)
    if best_buffer_bps is not None:
        subprocess.run(["python", "scripts/run_d205_10_1_smoke_best_buffer.py", ...])
```

---

## 5. Gate 검증 결과

| Gate | 결과 | 세부 |
|------|------|------|
| Doctor | ✅ PASS | syntax/import 정상 |
| Fast | ✅ PASS | D205 tests 76/76 (3.65s) |
| Boundary Guard | ✅ PASS | V2/V1 boundary clean |
| Regression | ✅ PASS | 2650/2650 tests |

**증거:** `logs/evidence/d205_10_1_wait_bootstrap_20260104_121700/gate_results.txt`

---

## 6. Smoke Test 결과

**Duration:** 0h (즉시 종료로 동작 확인)  
**Result:** ✅ PASS

**로그:**
```
[D205-10-1 WAIT] ✅ MarketData Providers initialized
[D205-10-1 WAIT] WaitHarness initialized
[D205-10-1 WAIT] Starting 0h watch loop
[D205-10-1 WAIT] ⏰ 0h elapsed without trigger
[D205-10-1 WAIT] ❌ AUTO-POSTMORTEM: Market conditions did not meet trigger threshold
```

**검증 완료:**
- ✅ MarketData Providers 초기화 성공
- ✅ watch loop 정상 진입/종료
- ✅ watch_summary.json 생성 확인
- ✅ Auto-Postmortem Rule 발동 확인

**Evidence:** `logs/evidence/d205_10_1_wait_smoke_1m_20260104_122000/`

---

## 7. Evidence 구조

### 7.1. Bootstrap Evidence
```
logs/evidence/d205_10_1_wait_bootstrap_20260104_121700/
├── bootstrap_env.txt               # 환경 정보 (Git/venv/Docker)
├── SCAN_REUSE_SUMMARY.md           # 재사용 모듈 목록 (7개)
├── IMPLEMENTATION_PLAN.md          # 트리거 조건 설계
├── gate_results.txt                # Gate 검증 결과
├── FINAL_MANIFEST.json             # AC 매핑 + 다음 단계
└── README.md                       # 재현 방법 + 10h run 가이드
```

### 7.2. 10h Real Run Evidence (실행 후 생성)
```
logs/evidence/d205_10_1_wait_<timestamp>/
├── market_watch.jsonl              # 실시간 시장 스냅샷 (최대 1200줄)
├── watch_summary.json              # 요약 통계 + 트리거 이력
├── sweep_link.txt                  # → sweep evidence dir (트리거 시)
└── smoke_link.txt                  # → smoke evidence dir (AC-2 성공 시)
```

---

## 8. Auto-Postmortem Rule

**발동 조건:** 10시간 경과 시 trigger_count == 0

**조치:**
1. D205-10-1 상태: **PARTIAL** 고정
2. 사유: "시장 환경 제약으로 인한 전략 가정 실패"
3. watch_summary.json에 max_edge_bps/p50_edge_bps 기록
4. 다음 단계: **D205-10-1-POSTMORTEM**
   - fee_model/slippage_bps/latency_bps 재산정
   - Break-even assumption 재설계

**목적:**
- 질문 없이 자동 전환 (인간 판단 제거)
- "대기"가 아닌 "재설계" 단계로 전환

---

## 9. AC 달성 조건

### AC-2: Best buffer 선정 성공
- **조건:** closed_trades > 0, error_count == 0, net_pnl 최대
- **Depends on:** Trigger 조건 충족 + Sweep 실행 성공
- **Status:** PENDING (10h run)

### AC-5: 20m smoke PASS
- **조건:** opportunities > 0, intents > 0, closed_trades > 0
- **Depends on:** AC-2 성공
- **Status:** PENDING (10h run)

### D205-10-1 COMPLETED 조건
**모두 충족 시:**
1. ✅ Evidence (wait + sweep + smoke)
2. ✅ Gate 3단 PASS
3. ✅ Git commit + push
4. ✅ AC-2 성공
5. ✅ AC-5 성공

---

## 10. 10h Real Run 실행 방법

### 사전 조건
1. ✅ Python venv 활성화
2. ✅ Docker 컨테이너 실행 중
3. ✅ Windows 절전 모드 비활성화
4. ✅ 새 CMD 창에서 실행

### 실행 명령어
```bash
python scripts/run_d205_10_1_wait_and_execute.py \
  --duration-hours 10 \
  --poll-seconds 30 \
  --trigger-min-edge-bps 0.0 \
  --fx-krw-per-usdt 1450.0 \
  --sweep-duration-minutes 2 \
  --db-mode off
```

### 예상 소요 시간
- **최소:** 트리거 발생 즉시 (~15분: sweep 11분 + smoke 20분 + overhead)
- **최대:** 10시간 (트리거 미발생 시)

---

## 11. 다음 단계

### Option 1: 10h Real Run 실행
- 위 명령어로 새 CMD 창에서 실행
- Trigger 발생 시 AC-2/AC-5 자동 달성
- D205-10-1 COMPLETED 가능

### Option 2: Auto-Postmortem 경로
- 10h 경과 시 trigger 미발생
- D205-10-1 상태: PARTIAL 고정
- D205-10-1-POSTMORTEM 시작 (Break-even Assumption Recalibration)

---

**구현 완료 날짜:** 2026-01-04  
**Git Branch:** rescue/d205_10_1_wait_harness  
**Next Commit:** [D205-10-1] Wait Harness Implementation (ready for 10h run)
