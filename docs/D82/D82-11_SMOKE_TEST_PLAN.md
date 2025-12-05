# D82-11: Recalibrated TP/Entry PAPER Smoke Test Plan

**Status:** 🔨 Implementation  
**Date:** 2025-12-05  
**Author:** AI Assistant

---

## 📋 목표

D82-10에서 Edge 모델 재보정을 통해 선정된 **8개 TP/Entry 후보**를 실제 PAPER 환경에서 단계적으로 검증하는 Smoke Test 하네스를 구현합니다.

### 배경

**D82-10 결과:**
- D82-9 실측 비용 구조(Slippage 2.14 bps, Fee 9.0 bps) 기반 Edge 재계산
- Edge >= 0 조건을 만족하는 8개 후보 선정
- Top 5 추천: (16,18), (14,18), (16,16), (12,18), (14,16)

**D82-11 역할:**
- D82-10에서 선정된 후보들의 **실제 PAPER 검증 하네스** 구현
- 10분 → 20분 → 60분 단계적 Smoke Test 지원
- 이 단계에서는 **인프라 + 러너 + 하네스 준비**가 목표
- 실제 장기 실행(3~12h)은 **D82-12 이상**으로 이관

### 범위

**✅ 이번 단계 (D82-11 Implementation):**
- Smoke Test 러너 스크립트 구현
- 후보 로딩/정렬/필터링 로직
- KPI 요약 및 Summary JSON 출력
- Unit/구조 테스트 (pytest + mock)
- 30~60초 초단기 엔드투엔드 smoke 검증

**⏳ 다음 단계 (D82-11 Validation):**
- 실제 10분/20분/60분 PAPER 실행
- Duration별 KPI 분석 및 후보 평가
- Edge 모델 예측 vs 실측 비교
- GO/NO-GO 판단 및 D82-12 장기 테스트 설계

---

## 📥 입력

### 1. 후보 JSON

**파일:** `logs/d82-10/recalibrated_tp_entry_candidates.json`

**구조:**
```json
{
  "metadata": {
    "source": "D82-9 recalibrated edge model",
    "scenarios": ["optimistic", "realistic", "conservative"],
    "created_at": "2025-12-05",
    "cost_profile_source": "logs/d82-10/d82_9_cost_profile.json"
  },
  "candidates": [
    {
      "entry_bps": 16,
      "tp_bps": 18,
      "edge_optimistic": 3.728799219689856,
      "edge_realistic": 3.728799219689579,
      "edge_conservative": 3.7287992196892272,
      "is_structurally_safe": true,
      "is_recommended": true,
      "rationale": "Realistic Edge >= 0.5 bps (recommended)"
    }
  ]
}
```

**필드 설명:**
- `entry_bps`: Entry threshold (bps)
- `tp_bps`: Take Profit threshold (bps)
- `edge_optimistic`: Optimistic 시나리오 Edge (bps)
- `edge_realistic`: Realistic 시나리오 Edge (bps)
- `edge_conservative`: Conservative 시나리오 Edge (bps)
- `is_structurally_safe`: Conservative Edge >= 0
- `is_recommended`: Realistic Edge >= 0.5 bps
- `rationale`: 선정 근거

### 2. 기존 D82-9 인프라

**재사용 요소:**
- PAPER Runner 패턴: `scripts/run_d82_9_paper_candidates_longrun.py`
- KPI 파일 구조: `logs/d82-9/runs/*_kpi.json`
- KPI 파서: `scripts/analyze_d82_9_kpi_deepdive.py`
- Runtime Edge Monitor (선택): `logs/d82-9/edge_monitor/*_edge.jsonl`

---

## 📤 출력

### 1. Directory 구조

```
logs/d82-11/
├── runs/
│   ├── d82-11-600-E16p0_TP18p0-20251205215000_kpi.json
│   ├── d82-11-600-E14p0_TP18p0-20251205220000_kpi.json
│   └── ...
├── edge_monitor/  (선택)
│   ├── d82-11-600-E16p0_TP18p0-20251205215000_edge.jsonl
│   └── ...
└── d82_11_summary_600.json
└── d82_11_summary_1200.json
└── d82_11_summary_3600.json
```

### 2. Summary JSON 스키마

**파일:** `logs/d82-11/d82_11_summary_{duration}.json`

```json
{
  "metadata": {
    "duration_seconds": 600,
    "top_n": 3,
    "candidates_source": "logs/d82-10/recalibrated_tp_entry_candidates.json",
    "created_at": "2025-12-05T21:50:00",
    "d82_11_implementation_version": "1.0"
  },
  "candidates": [
    {
      "entry_bps": 16.0,
      "tp_bps": 18.0,
      "edge_optimistic": 3.73,
      "edge_realistic": 3.73,
      "edge_conservative": 3.73,
      "run_id": "d82-11-600-E16p0_TP18p0-20251205215000",
      "kpi_path": "logs/d82-11/runs/d82-11-600-E16p0_TP18p0-20251205215000_kpi.json",
      "kpi_summary": {
        "round_trips_completed": 7,
        "win_rate_pct": 28.6,
        "tp_exit_pct": 14.3,
        "timeout_exit_pct": 85.7,
        "total_pnl_usd": 12.34,
        "avg_pnl_per_rt_usd": 1.76,
        "buy_fill_ratio_avg": 30.5,
        "sell_fill_ratio_avg": 100.0,
        "slippage_avg_bps": 2.14,
        "loop_latency_avg_ms": 18.5
      },
      "status": "ok"
    }
  ],
  "summary_stats": {
    "total_runs": 3,
    "successful_runs": 3,
    "failed_runs": 0,
    "total_round_trips": 21,
    "avg_round_trips": 7.0,
    "total_pnl_usd": 36.0,
    "avg_pnl_usd": 12.0
  }
}
```

**`status` 필드 값:**
- `"ok"`: 정상 실행 완료
- `"no_trades"`: Round Trips = 0
- `"error"`: 실행 중 오류 발생
- `"timeout"`: 엔진 타임아웃

### 3. 개별 KPI JSON

D82-9와 동일한 구조를 유지하되, `run_id` prefix만 `d82-11-`로 변경:

```json
{
  "run_id": "d82-11-600-E16p0_TP18p0-20251205215000",
  "entry_bps": 16.0,
  "tp_bps": 18.0,
  "duration_sec": 600,
  "round_trips_completed": 7,
  "win_rate_pct": 28.6,
  "exit_reasons": {
    "tp": 2,
    "stop_loss": 0,
    "time_limit": 5
  },
  "...": "..."
}
```

---

## 🔧 테스트 전략

### 1. Unit Tests (pytest + mock)

**테스트 파일:** `tests/test_d82_11_smoke_test.py`

**테스트 항목:**

| Test | Description | Method |
|------|-------------|--------|
| `test_load_candidates` | JSON 파일 파싱 & 8개 후보 로딩 | Fixture JSON |
| `test_select_top_n_sorting` | `edge_realistic` 내림차순 정렬 | Mock candidates |
| `test_cli_dry_run` | CLI 파싱 & dry-run 모드 | subprocess/CliRunner |
| `test_summary_json_structure` | Summary JSON 스키마 검증 | Mock KPI |
| `test_run_id_generation` | `d82-11-{duration}-E{entry}_TP{tp}-{timestamp}` 형식 | Unit test |
| `test_kpi_parsing` | D82-9 KPI 파서 재사용 검증 | Mock KPI file |

### 2. Integration Tests

**Smoke Test (30~60초):**
```bash
python scripts/run_d82_11_smoke_test.py \
  --duration-seconds 30 \
  --top-n 2 \
  --summary-output logs/d82-11/d82_11_summary_30.json
```

**검증 항목:**
- Exit code = 0
- `logs/d82-11/runs/*.json` 생성 확인
- Summary JSON 구조 검증
- KPI 필드 존재성 확인

### 3. Regression Tests

**D82-9/D82-10 회귀 방지:**
```bash
pytest tests/test_d82_9_tp_finetuning.py
pytest tests/test_d82_10_edge_recalibration.py
pytest tests/test_d82_11_smoke_test.py
```

모든 테스트 100% PASS 유지.

---

## 🎯 Acceptance Criteria

### D82-11 Implementation (이번 단계)

**✅ PASS 조건:**

1. **코드 구조:**
   - [x] `scripts/run_d82_11_smoke_test.py` 구현
   - [x] 후보 로딩/정렬 helper (재사용 가능)
   - [x] D82-9 Runner 패턴 재사용
   - [x] KPI 요약 로직 구현

2. **테스트:**
   - [x] `tests/test_d82_11_smoke_test.py` (최소 6개 테스트)
   - [x] D82-9/D82-10 테스트 100% PASS 유지
   - [x] 30~60초 초단기 smoke 성공

3. **출력:**
   - [x] Summary JSON 생성 (`d82_11_summary_{duration}.json`)
   - [x] 개별 KPI JSON 생성 (`runs/*_kpi.json`)
   - [x] 스키마 검증 통과

4. **문서:**
   - [x] `D82-11_SMOKE_TEST_PLAN.md` (이 문서)
   - [x] `D_ROADMAP.md` 업데이트 (D82-11 섹션 추가)

### D82-11 Validation (다음 단계)

**⏳ PENDING 조건:**

1. **10분 Smoke Test (Top 3):**
   - RT >= 5
   - Win Rate > 0%
   - PnL >= 0
   - TP Exit % > 0%

2. **20분 Validation (통과 후보):**
   - RT >= 10
   - Win Rate >= 10%
   - PnL > 0
   - TP Exit % >= 5%

3. **60분 Confirmation (안정성):**
   - RT >= 30
   - Win Rate >= 20%
   - PnL > $10
   - Loop Latency < 25ms

---

## 🔄 Runner 구현 설계

### 1. CLI 인터페이스

**스크립트:** `scripts/run_d82_11_smoke_test.py`

```bash
python scripts/run_d82_11_smoke_test.py \
  --duration-seconds 600 \
  --candidates-json logs/d82-10/recalibrated_tp_entry_candidates.json \
  --top-n 3 \
  --summary-output logs/d82-11/d82_11_summary_600.json \
  --dry-run  # optional
```

**파라미터:**
- `--duration-seconds` (required): 600 / 1200 / 3600
- `--candidates-json` (optional): default = `logs/d82-10/recalibrated_tp_entry_candidates.json`
- `--top-n` (optional): default = 3
- `--summary-output` (optional): default = `logs/d82-11/d82_11_summary_{duration}.json`
- `--dry-run` (flag): 커맨드만 출력, 실제 실행 없음
- `--enable-edge-monitor` (flag): Runtime Edge Monitor 활성화

### 2. 후보 로딩 & 정렬

**Helper Functions:**

```python
def load_recalibrated_candidates(path: Path) -> List[Dict[str, Any]]:
    """Load candidates from D82-10 JSON."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["candidates"]

def select_top_n_candidates(
    candidates: List[Dict[str, Any]], 
    n: int
) -> List[Dict[str, Any]]:
    """
    Select top N candidates by sorting:
    1. edge_realistic (desc)
    2. edge_conservative (desc)
    """
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (
            -c["edge_realistic"],
            -c["edge_conservative"]
        )
    )
    return sorted_candidates[:n]
```

### 3. 엔진 실행 연동

**D82-9 패턴 재사용:**

```python
def execute_single_run(
    candidate: Dict[str, Any],
    duration_sec: int,
    run_index: int,
    total_runs: int,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """
    Execute single candidate PAPER run.
    
    Reuses D82-9 subprocess pattern:
    - Calls run_d77_0_topn_arbitrage_paper.py
    - Sets TOPN_ENTRY_MIN_SPREAD_BPS, TOPN_EXIT_TP_SPREAD_BPS
    - Generates KPI JSON
    """
    entry_bps = candidate["entry_bps"]
    tp_bps = candidate["tp_bps"]
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    run_id = f"d82-11-{duration_sec}-E{entry_bps}_TP{tp_bps}-{timestamp}"
    
    # Output paths
    runs_dir = Path("logs/d82-11/runs")
    runs_dir.mkdir(parents=True, exist_ok=True)
    kpi_path = runs_dir / f"{run_id}_kpi.json"
    
    # Build command (same as D82-9)
    cmd = [
        sys.executable,
        "scripts/run_d77_0_topn_arbitrage_paper.py",
        "--duration", str(duration_sec),
        "--kpi-output", str(kpi_path),
    ]
    
    env_vars = os.environ.copy()
    env_vars["TOPN_ENTRY_MIN_SPREAD_BPS"] = str(entry_bps)
    env_vars["TOPN_EXIT_TP_SPREAD_BPS"] = str(tp_bps)
    
    if args.dry_run:
        logger.info(f"[DRY-RUN] {' '.join(cmd)}")
        return {"status": "dry_run", "run_id": run_id}
    
    # Execute
    result = subprocess.run(
        cmd,
        env=env_vars,
        capture_output=True,
        text=True,
        timeout=duration_sec + 60,
    )
    
    # Parse KPI
    kpi_summary = parse_kpi_file(kpi_path) if kpi_path.exists() else {}
    
    return {
        "entry_bps": entry_bps,
        "tp_bps": tp_bps,
        "edge_realistic": candidate["edge_realistic"],
        "run_id": run_id,
        "kpi_path": str(kpi_path),
        "kpi_summary": kpi_summary,
        "status": "ok" if result.returncode == 0 else "error",
    }
```

### 4. KPI 요약

**D82-9 파서 재사용:**

```python
def parse_kpi_file(kpi_path: Path) -> Dict[str, Any]:
    """
    Parse D82-9 KPI JSON and extract summary metrics.
    
    Reuses analyze_d82_9_kpi_deepdive.py logic.
    """
    with open(kpi_path, "r", encoding="utf-8") as f:
        kpi = json.load(f)
    
    # Extract key metrics
    total_exits = sum(kpi.get("exit_reasons", {}).values())
    tp_exits = kpi.get("exit_reasons", {}).get("tp", 0)
    timeout_exits = kpi.get("exit_reasons", {}).get("time_limit", 0)
    
    return {
        "round_trips_completed": kpi.get("round_trips_completed", 0),
        "win_rate_pct": kpi.get("win_rate_pct", 0.0),
        "tp_exit_pct": (tp_exits / total_exits * 100) if total_exits > 0 else 0.0,
        "timeout_exit_pct": (timeout_exits / total_exits * 100) if total_exits > 0 else 0.0,
        "total_pnl_usd": kpi.get("total_pnl_usd", 0.0),
        "avg_pnl_per_rt_usd": kpi.get("avg_pnl_per_rt_usd", 0.0),
        "buy_fill_ratio_avg": kpi.get("buy_fill_ratio_avg", 0.0),
        "sell_fill_ratio_avg": kpi.get("sell_fill_ratio_avg", 0.0),
        "slippage_avg_bps": kpi.get("slippage_avg_bps", 0.0),
        "loop_latency_avg_ms": kpi.get("loop_latency_avg_ms", 0.0),
    }
```

---

## 📊 실행 계획 (Validation 단계)

### Phase 1: 10분 Smoke Test

**목적:** 기본 동작 확인 & 초기 필터링

**대상:** Top 3 후보
- (16, 18): Edge +3.73 bps
- (14, 18): Edge +2.73 bps
- (16, 16): Edge +2.73 bps

**실행:**
```bash
python scripts/run_d82_11_smoke_test.py \
  --duration-seconds 600 \
  --top-n 3 \
  --summary-output logs/d82-11/d82_11_summary_600.json
```

**Acceptance:**
- 모든 후보 RT >= 5
- 최소 1개 후보 Win Rate > 0%
- 최소 1개 후보 PnL >= 0

### Phase 2: 20분 Validation

**목적:** 안정성 확인

**대상:** Phase 1 통과 후보 (최소 2개)

**실행:**
```bash
python scripts/run_d82_11_smoke_test.py \
  --duration-seconds 1200 \
  --top-n 2 \
  --summary-output logs/d82-11/d82_11_summary_1200.json
```

**Acceptance:**
- RT >= 10
- Win Rate >= 10%
- PnL > 0
- TP Exit % >= 5%

### Phase 3: 60분 Confirmation

**목적:** 실전 준비 확인

**대상:** Phase 2 통과 후보 (최소 1개)

**실행:**
```bash
python scripts/run_d82_11_smoke_test.py \
  --duration-seconds 3600 \
  --top-n 1 \
  --summary-output logs/d82-11/d82_11_summary_3600.json
```

**Acceptance:**
- RT >= 30
- Win Rate >= 20%
- PnL > $10
- Loop Latency < 25ms
- CPU < 50%

---

## 🔍 예상 결과 & 판단 기준

### Scenario 1: Full Success ✅

**조건:**
- Top 3 모두 10분 통과
- 최소 2개 20분 통과
- 최소 1개 60분 통과

**판단:**
- **GO to D82-12 Long Run (3~12h)**
- 통과 후보로 장기 실전 검증 진행

### Scenario 2: Partial Success ⚠️

**조건:**
- 1~2개만 통과
- RT는 발생하지만 Win Rate < 10%

**판단:**
- **ANALYZE Mock Fill Model**
- D82-9와 동일한 26% Fill Ratio 문제 재발 가능성
- D83-x (L2 Orderbook) 우선순위 상향

### Scenario 3: Full Failure ❌

**조건:**
- 모든 후보 RT < 5 (10분 기준)
- Win Rate = 0%

**판단:**
- **NO-GO to Edge Model Review**
- D82-7 가정 vs 현재 시장 regime 불일치
- D77-4 baseline 재검증 필요

---

## 🚨 Known Issues & Mitigation

### 1. Mock Fill Model Pessimism

**문제:**
- D82-9에서 Buy Fill Ratio 26.15% 관측
- 이는 D77-4 (100% WR)과 100배 차이

**완화 방안:**
- D82-11에서도 동일 현상 발생 시, Fill Ratio 통계 집계
- D83-x L2 Orderbook 통합을 다음 단계 최우선 과제로 설정

### 2. TP Threshold 도달 불가

**문제:**
- D82-9에서 TP 13-15 bps는 100% timeout
- D82-11에서 TP 14-18 bps도 동일 문제 가능성

**완화 방안:**
- 10분 Smoke에서 TP Exit % 집중 모니터링
- 0%인 경우 즉시 다음 후보로 넘어가지 말고,
- 20분/60분에서 TP 도달 가능성 추가 확인

### 3. Infrastructure Bottleneck

**문제:**
- Loop Latency > 25ms
- CPU > 50%

**완화 방안:**
- KPI에 인프라 메트릭 포함
- 문제 발생 시 D82-11 단계 조기 종료하고 인프라 개선 우선

---

## 📝 Next Steps

### D82-11 Implementation (이번 단계)

1. ✅ 설계 문서 작성 (이 문서)
2. ⏳ Helper 함수 구현 (load/select candidates)
3. ⏳ `run_d82_11_smoke_test.py` 구현
4. ⏳ `test_d82_11_smoke_test.py` 작성
5. ⏳ 30~60초 초단기 smoke 실행
6. ⏳ Roadmap 업데이트
7. ⏳ Git 커밋

### D82-11 Validation (다음 단계)

1. 10분 Smoke Test (Top 3)
2. 20분 Validation (통과 후보)
3. 60분 Confirmation (최종 후보)
4. KPI 분석 & Edge 모델 비교
5. GO/NO-GO 판단
6. D82-12 Long Run 또는 D83-x L2 Orderbook 진행

### D82-12+ (장기 계획)

- 3~12시간 Long Run PAPER
- 24시간+ Live 준비 검증
- Performance/Risk 메트릭 수집
- Production deployment 준비

---

**Document Created:** 2025-12-05  
**Author:** AI Assistant  
**Status:** Implementation In Progress
