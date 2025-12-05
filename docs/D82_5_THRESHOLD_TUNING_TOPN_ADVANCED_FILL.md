# D82-5: Threshold Tuning Infrastructure (TopN + AdvancedFillModel)

**Status:** 🚧 IN PROGRESS  
**Created:** 2025-12-05  
**Author:** Windsurf AI + User  

---

## 개요

D82-5는 **Entry/TP 임계값 튜닝 실험 인프라** 구축 단계입니다. AdvancedFillModel(D81-1), Trade Logger(D80-3), TopN 엔진(D82-1~D82-4) 위에서 **체계적으로 threshold를 변경하며 실험할 수 있는 기반**을 마련합니다.

### 역할 정의

**D82-5의 목표는 "수익률 최적화를 지금 당장 완성"하는 것이 아닙니다.**  
→ 스프레드 임계값 / TP 임계값을 바꾸면 **Entry 수, Win Rate, PnL 구조가 어떻게 변하는지 정량적으로 비교할 수 있는 연구 프레임워크**를 만드는 것입니다.

---

## 선행 단계 요약 (AS-IS)

### D80-3: Trade-level Spread & Liquidity Logging ✅

**완료일:** 2025-12-04  
**핵심:**
- `arbitrage/logging/trade_logger.py` (350+ lines)
- `TradeLogEntry` dataclass: 30+ 필드 (스프레드, 호가, 체결, PnL)
- JSONL 파일 저장: `logs/d80-3/trades/{run_id}/{universe}_trade_log.jsonl`
- Universe별 분리 (`top20_trade_log.jsonl`, `top50_trade_log.jsonl`)

**활용:**
- D82-5에서 각 threshold 조합별 평균 스프레드/슬리피지 계산에 사용

---

### D80-4: Realistic Fill & Slippage Model ✅

**완료일:** 2025-12-04  
**핵심:**
- `SimpleFillModel`: Partial Fill + Linear Slippage
- `ExecutionResult`에 `buy_slippage_bps`, `sell_slippage_bps`, `buy_fill_ratio`, `sell_fill_ratio` 추가
- Validation Profile `fill_model` 구현
- PAPER 모드 100% 승률 구조 제거

**Long-run 검증:**
- D82-1: 12h PAPER (540 round trips, slippage ~0.5 bps)
- D82-4: 20min PAPER (6 round trips, win_rate 0%, CONDITIONAL GO)

**활용:**
- D82-5에서 SimpleFillModel과 AdvancedFillModel 비교 실험 가능

---

### D81-1: AdvancedFillModel + Real PAPER Validation ✅

**완료일:** 2025-12-05  
**핵심:**
- `AdvancedFillModel`: Multi-level virtual L2 orderbook, non-linear market impact
- 12분 Real PAPER: **Partial Fill 4건** 발생 (avg buy fill ratio 0.26)
- Slippage: 2.14 bps (SimpleFillModel 대비 증가)
- KPI: `logs/d81-1/kpi_advanced_fill_retry1.json`

**파라미터 조정 히스토리:**
- 1차 시도 (실패): `base_volume_multiplier=0.4`, `available_volume_factor=2.0` → Partial fill 0건
- 2차 시도 (성공): `base_volume_multiplier=0.15`, `available_volume_factor=1.0` → Partial fill 4건

**교훈:**
- AdvancedFillModel 파라미터는 partial fill 발생에 매우 민감
- 파라미터 fine-tuning 필요성 확인

**활용:**
- D82-5에서 AdvancedFillModel을 기본 Fill Model로 사용
- `.env.paper`의 `FILL_MODEL_TYPE=advanced` 고정

---

### D82-4: TopN Long-Run PAPER Validation (20분) ✅

**완료일:** 2025-12-04  
**핵심:**
- 20분 Real PAPER 결과:
  - Entry: 7건 (목표 10건 대비 70%)
  - Round Trips: 6건
  - Win Rate: 0% (모든 Exit = time_limit)
  - Loop Latency: 13.79ms (안정성 우수)
- **Threshold 튜닝 효과**: Entry 1.0 → 0.5 bps로 50% 감소 → Entry 75% 증가 (4→7건)
- **Known Issues**:
  - 실제 spread 분포가 0.3~0.7 bps에 집중
  - TP threshold (2 bps) 미도달로 Win Rate 0%

**현재 설정 (`.env.paper`):**
```
TOPN_ENTRY_MIN_SPREAD_BPS=0.5  # Entry threshold (D82-4 tuned)
TOPN_EXIT_TP_SPREAD_BPS=2.0    # TP threshold
TOPN_MAX_HOLDING_SECONDS=180.0  # Max holding time (3분)
```

**활용:**
- D82-5 실험의 베이스라인
- Entry/TP threshold 튜닝 필요성 확인

---

## TO-BE: D82-5 실험 인프라

### 1. 튜닝 파라미터 세트

**Grid Search 조합:**

| Parameter | Values (bps) | Default |
|-----------|--------------|---------|
| **Entry Threshold** | [0.3, 0.5, 0.7] | 0.5 (D82-4) |
| **TP Threshold** | [1.0, 1.5, 2.0] | 2.0 (D82-4) |

**Total Combinations:** 3 × 3 = **9 조합**

**Max Holding Time (고정):** 180초 (3분)
- 첫 단계에서는 고정값 하나만 사용
- 추후 확장 시 [180, 300, 600] 등으로 확대 가능

---

### 2. 실험 목표

각 조합별로 **6~10분 Real PAPER**를 실행하여 다음 지표 수집:

| Metric | Source | Description |
|--------|--------|-------------|
| **Entry 수** | KPI JSON | 진입 거래 수 |
| **Round Trips** | KPI JSON | 완료된 라운드 트립 수 |
| **Win Rate (%)** | KPI JSON | 승률 |
| **Avg Spread (bps)** | Trade Log | 평균 진입 스프레드 |
| **Avg Slippage (bps)** | KPI JSON | 평균 슬리피지 (buy/sell) |
| **PnL (USD)** | KPI JSON | 총 손익 |
| **Loop Latency (ms)** | KPI JSON | 평균 루프 레이턴시 |

**결과 저장:**
- KPI JSON: `logs/d82-5/runs/{run_id}_kpi.json`
- Trade Log: `logs/d82-5/trades/{run_id}/top20_trade_log.jsonl`
- Summary: `logs/d82-5/threshold_sweep_summary.json`

---

### 3. 실험 디자인

**Duration:** 6분 (360초) per 조합
- 빠른 iteration을 위해 짧게 설정
- 안정성 검증은 D82-4에서 완료 (20분)
- 나중에 20분/1시간/12시간으로 확장 가능

**TopN Size:** 20 (기본값)
- Top20으로 고정하여 변수 최소화
- 추후 Top50/Top100 확장 가능

**Validation Profile:** `topn_research`
- D82-x/D77-x용 validation criteria
- Entry ≥ 1, Round Trips ≥ 1, Win Rate informational

**Data Source:** Real
- `--data-source real`
- Real Upbit TopN data 사용

---

### 4. Runner 스크립트 설계

**파일:** `scripts/run_d82_5_threshold_sweep.py` (신규)

**역할:**
- 여러 threshold 조합에 대해 `run_d77_0_topn_arbitrage_paper.py`를 서브프로세스로 실행
- 각 실행의 KPI 파일과 Trade Log를 읽어 종합 Summary JSON 생성

**CLI 인터페이스:**
```bash
python scripts/run_d82_5_threshold_sweep.py \
  --entry-bps-list "0.3,0.5,0.7" \
  --tp-bps-list "1.0,1.5,2.0" \
  --run-duration-seconds 360 \
  --topn-size 20 \
  --validation-profile topn_research \
  --dry-run  # 명령만 출력 (실제 실행 X)
```

**기본값:**
- Entry: `[0.3, 0.5, 0.7]`
- TP: `[1.0, 1.5, 2.0]`
- Duration: `360` (6분)
- TopN: `20`
- Dry-run: `False`

**내부 실행 로직:**
1. 각 (entry_bps, tp_bps) 조합에 대해:
   - 고유 `run_id` 생성: `d82-5-E{entry}_TP{tp}-{timestamp}`
   - `kpi_output_path`: `logs/d82-5/runs/{run_id}_kpi.json`
   - Trade Log: `logs/d82-5/trades/{run_id}/top20_trade_log.jsonl`
2. 환경변수 override:
   ```bash
   $env:TOPN_ENTRY_MIN_SPREAD_BPS={entry_bps}
   $env:TOPN_EXIT_TP_SPREAD_BPS={tp_bps}
   python scripts/run_d77_0_topn_arbitrage_paper.py ...
   ```
3. 실행 완료 후:
   - KPI JSON 로드
   - Trade Log JSONL 파싱 (평균 스프레드 계산)
   - Summary 항목 추가

**Summary JSON 스키마:**
```json
{
  "sweep_metadata": {
    "start_time": "2025-12-05T10:00:00",
    "end_time": "2025-12-05T11:30:00",
    "total_runs": 9,
    "duration_per_run_sec": 360
  },
  "results": [
    {
      "entry_bps": 0.3,
      "tp_bps": 1.0,
      "run_id": "d82-5-E0.3_TP1.0-20251205100000",
      "duration_sec": 360,
      "entries": 12,
      "round_trips": 10,
      "win_rate_pct": 55.0,
      "avg_spread_bps": 0.42,
      "avg_buy_slippage_bps": 2.3,
      "avg_sell_slippage_bps": 2.1,
      "pnl_usd": 12.3,
      "loop_latency_avg_ms": 16.2,
      "kpi_path": "logs/d82-5/runs/d82-5-E0.3_TP1.0-20251205100000_kpi.json",
      "trade_log_path": "logs/d82-5/trades/d82-5-E0.3_TP1.0-20251205100000/top20_trade_log.jsonl"
    },
    ...
  ]
}
```

**저장 경로:**
- `logs/d82-5/threshold_sweep_summary.json`

---

### 5. Acceptance Criteria (D82-5 자체 PASS 기준)

| Criteria | Target | 비고 |
|----------|--------|------|
| **Runner 정상 동작** | 9개 조합 모두 KPI/Summary 생성 | 필수 |
| **Summary JSON 생성** | `threshold_sweep_summary.json` 존재 | 필수 |
| **회귀 없음** | 기존 D80/D81/D82 테스트 100% PASS | 필수 |
| **문서 정리** | D_ROADMAP + 설계 문서 업데이트 | 필수 |
| **수익률 플러스** | - | **NOT REQUIRED** |

**중요:** D82-5는 **튜닝 인프라 구축** 단계이므로, 실제 수익률이 플러스가 되어야 PASS는 아닙니다.  
→ 리서치/튜닝 인프라 완성이 목표이며, 실제 수익률 최적화는 이 기반 위에서 장기적으로 진행합니다.

---

## 구현 전략

### Config 확장

**기존 설정 (AS-IS):**
- `TopNEntryExitConfig` 클래스 존재 (`arbitrage/config/settings.py`)
- 환경변수: `TOPN_ENTRY_MIN_SPREAD_BPS`, `TOPN_EXIT_TP_SPREAD_BPS`
- `Settings.from_env()`에서 로드

**D82-5 전략:**
- **Config 구조 변경 없음**
- Runner 스크립트에서 환경변수 override로 threshold 변경
- 기본 동작은 `.env.paper` 값 사용 (회귀 방지)

**예시:**
```python
import os
os.environ["TOPN_ENTRY_MIN_SPREAD_BPS"] = "0.3"
os.environ["TOPN_EXIT_TP_SPREAD_BPS"] = "1.0"

# Run paper script
subprocess.run([...])
```

---

### 엔진/도메인 변경 금지

**변경하지 않음:**
- `arbitrage/execution/fill_model.py`
- `arbitrage/execution/executor.py`
- `arbitrage/strategy/*`
- `arbitrage/risk/*`

**D82-5는 실험 Runner + 분석 Glue 코드만 추가합니다.**

---

## 향후 확장 포인트

### 1. Bayesian Optimization으로 확장

현재는 Grid Search (3×3=9조합)이지만, 추후 Bayesian/Random Search로 확장 가능:
- `scikit-optimize` 또는 `optuna` 사용
- Objective: PnL, Sharpe Ratio, Win Rate 등
- PHASE25 튜닝 클러스터와 연계 가능

### 2. Multi-universe 확장

- Top20 vs Top50 vs Top100 비교
- Universe별 최적 threshold 탐색

### 3. Multi-exchange 확장 (D84-x)

- Upbit-Binance Cross-exchange Inventory Cost 모델링과 결합
- Exchange별 threshold 차등 적용

### 4. Adaptive Threshold (D83-x)

- 변동성 기반 동적 threshold 조정
- 시간대별 threshold 최적화

### 5. Long-run 실험

- 20분/1시간/12시간 실행으로 확장
- 충분한 샘플 확보 후 통계적 유의성 검증

---

## 파일 구조

### 신규 파일

```
scripts/
  run_d82_5_threshold_sweep.py         (신규, ~400 lines)
  
tests/
  test_d82_5_threshold_sweep_runner.py (신규, ~200 lines)
  
docs/
  D82_5_THRESHOLD_TUNING_TOPN_ADVANCED_FILL.md (신규, 본 문서)
  
logs/
  d82-5/
    runs/
      {run_id}_kpi.json                (각 조합별 KPI)
    trades/
      {run_id}/
        top20_trade_log.jsonl          (각 조합별 Trade Log)
    threshold_sweep_summary.json       (종합 Summary)
```

### 수정 파일

```
D_ROADMAP.md                           (D82-5 섹션 추가)
```

---

## 실행 가이드

### 1. Dry-run (명령만 출력)

```powershell
$env:ARBITRAGE_ENV="paper"
python scripts/run_d82_5_threshold_sweep.py \
  --entry-bps-list "0.3,0.5,0.7" \
  --tp-bps-list "1.0,1.5,2.0" \
  --run-duration-seconds 360 \
  --topn-size 20 \
  --dry-run
```

**예상 출력:**
```
[D82-5] Threshold Sweep Configuration
  Entry BPS: [0.3, 0.5, 0.7]
  TP BPS: [1.0, 1.5, 2.0]
  Total Combinations: 9
  Duration per run: 360s (6 minutes)
  Total estimated time: 54 minutes

[DRY-RUN] Would execute:
  Run 1/9: Entry=0.3, TP=1.0
    CMD: $env:TOPN_ENTRY_MIN_SPREAD_BPS="0.3"; $env:TOPN_EXIT_TP_SPREAD_BPS="1.0"; python scripts/run_d77_0_topn_arbitrage_paper.py ...
  ...
```

### 2. 실제 실행 (6분 × 9조합 = 54분)

```powershell
$env:ARBITRAGE_ENV="paper"
python scripts/run_d82_5_threshold_sweep.py \
  --entry-bps-list "0.3,0.5,0.7" \
  --tp-bps-list "1.0,1.5,2.0" \
  --run-duration-seconds 360 \
  --topn-size 20
```

**실행 중 모니터링:**
- 각 조합 실행 시 콘솔 로그 출력
- KPI/Trade Log 저장 확인
- Summary JSON 업데이트 확인

### 3. 결과 분석

```powershell
# Summary JSON 확인
cat logs/d82-5/threshold_sweep_summary.json | jq '.results[] | {entry_bps, tp_bps, entries, win_rate_pct, pnl_usd}'
```

**분석 포인트:**
- Entry threshold 낮출수록 Entry 수 증가?
- TP threshold 낮출수록 Win Rate 증가?
- 최적 조합 (Entry, TP) 탐색
- Slippage/Spread 트레이드오프 분석

---

## 테스트 전략

### 단위 테스트

**파일:** `tests/test_d82_5_threshold_sweep_runner.py`

**테스트 항목:**
1. Threshold 조합 생성 로직
2. KPI JSON 로드 및 파싱
3. Trade Log JSONL 파싱 (평균 스프레드 계산)
4. Summary JSON 생성
5. Dry-run 모드 동작

**Mock/Fixture 사용:**
- 실제 PAPER 실행 없음
- KPI/Trade Log는 fixture JSON 사용

### 회귀 테스트

**필수 PASS:**
- D80-3: Trade Logger (8 tests)
- D80-4: Fill Model (11 tests) + Executor Integration (5 tests)
- D81-1: Advanced Fill Model (10 tests) + Integration (5 tests)

**실행 명령:**
```powershell
$env:ARBITRAGE_ENV="paper"
$env:PYTHONPATH="c:\Users\bback\Desktop\부업\9) 코인 자동매매\arbitrage-lite"
abt_bot_env\Scripts\pytest.exe tests/test_d80_3*.py tests/test_d80_4*.py tests/test_d81_1*.py tests/test_d82_5*.py -v
```

---

## 결론

D82-5는 **Entry/TP threshold 튜닝 실험 인프라**를 구축하는 단계입니다.

**핵심 산출물:**
1. `run_d82_5_threshold_sweep.py`: Grid search runner
2. `threshold_sweep_summary.json`: 9개 조합 결과 종합
3. 설계 문서 + 테스트 + D_ROADMAP 업데이트

**성공 기준:**
- ✅ Runner 정상 동작 (9개 조합 모두 KPI/Summary 생성)
- ✅ 회귀 없음 (기존 테스트 100% PASS)
- ✅ 문서 정리 (D_ROADMAP + 설계 문서)
- ❌ 수익률 플러스 (NOT REQUIRED)

**다음 단계:**
- D83-x: WebSocket L2 Orderbook (real-time depth)
- D84-x: Multi-exchange Advanced Fill Model
- D85-x: Hyperparameter Tuning Cluster (Bayesian optimization)

---

**Status:** 🚧 IN PROGRESS → ✅ COMPLETE (구현 완료 후 업데이트)
