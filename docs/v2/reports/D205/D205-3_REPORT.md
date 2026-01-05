# D205-3 REUSE AUDIT

**작성일:** 2025-12-30 22:09 UTC+09:00  
**목적:** KPI/Reporting SSOT 복구 - 재사용 모듈 스캔 결과

---

## 스캔 결과: 재사용 가능한 모듈 (✅ 존재)

### 1. Reporting Aggregator (✅ 재사용)
**경로:** `arbitrage/v2/reporting/aggregator.py`

**기능:**
- `aggregate_pnl_daily()`: v2_trades에서 daily PnL 집계
- `aggregate_ops_daily()`: v2_orders/fills에서 operational metrics 집계

**산출물 스키마:**
```python
# PnL Metrics
{
    "date": date,
    "gross_pnl": float,
    "net_pnl": float,
    "fees": float,
    "volume": float,
    "trades_count": int,
    "wins": int,
    "losses": int,
    "winrate_pct": float,
    "avg_spread": None,  # TODO
    "max_drawdown": None,  # TODO
    "sharpe_ratio": None,  # TODO
}

# Ops Metrics
{
    "date": date,
    "orders_count": int,
    "fills_count": int,
    "rejects_count": int,
    "fill_rate_pct": float,
    "avg_slippage_bps": None,  # TODO
    "latency_p50_ms": None,  # TODO
    "latency_p95_ms": None,  # TODO
    "api_errors": 0,  # Paper=0, LIVE 시 집계
    "rate_limit_hits": 0,  # Paper=0, LIVE 시 집계
    "reconnects": 0,  # Paper=0, LIVE 시 집계
    "avg_cpu_pct": None,  # TODO
    "avg_memory_mb": None,  # TODO
}
```

**재사용 방식:**
- ✅ **그대로 재사용**: 이미 v2_trades.realized_pnl 기반 집계 구현됨
- ❌ **수정 불필요**: 스키마 완성도 높음

---

### 2. Reporting Writer (✅ 재사용)
**경로:** `arbitrage/v2/reporting/writer.py`

**기능:**
- `upsert_pnl_daily()`: v2_pnl_daily 테이블에 upsert
- `upsert_ops_daily()`: v2_ops_daily 테이블에 upsert

**특징:**
- ✅ Idempotent (ON CONFLICT ... DO UPDATE)
- ✅ 동일 날짜 재실행 시 UPDATE됨

**재사용 방식:**
- ✅ **그대로 재사용**: DB 저장 로직 완성

---

### 3. Daily Report CLI (✅ 재사용)
**경로:** `arbitrage/v2/reporting/run_daily_report.py`

**기능:**
- 단일 명령으로 PnL + Ops 집계 → DB 저장 → JSON 산출

**산출물:**
```json
{
  "date": "2025-12-30",
  "run_id_prefix": "d204_2_smoke_20251230_1825",
  "pnl": { ... },
  "ops": { ... },
  "generated_at": "2025-12-30T18:27:18.413184"
}
```

**재사용 방식:**
- ✅ **paper_chain에서 호출**: 체인 종료 후 자동 리포트 생성

---

### 4. Test Suite (✅ 재사용)
**경로:** `tests/test_d205_1_reporting.py`

**검증 항목:**
- ✅ `aggregate_pnl_daily()` 필수 키 존재
- ✅ `aggregate_ops_daily()` 필수 키 존재
- ✅ `upsert_pnl_daily()` DB 저장
- ✅ `upsert_ops_daily()` DB 저장
- ✅ Full pipeline (집계 → upsert)

**재사용 방식:**
- ✅ **Gate Fast에 포함**: 이미 test suite 존재

---

## 스캔 결과: 수정 필요한 모듈 (❌ 문제)

### 1. PaperRunner KPI (❌ PnL 필드 누락)
**경로:** `arbitrage/v2/harness/paper_runner.py`

**현재 KPI 스키마:**
```python
@dataclass
class KPICollector:
    start_time: float
    opportunities_generated: int
    intents_created: int
    mock_executions: int
    db_inserts_ok: int
    db_inserts_failed: int
    error_count: int
    errors: List[str]
    db_last_error: str
    memory_mb: float
    cpu_pct: float
```

**문제점:**
- ❌ **net_pnl 필드 없음**
- ❌ **closed_trades 필드 없음**
- ❌ **winrate_pct 필드 없음**
- ❌ **fees 필드 없음**

**결과:**
- ❌ `kpi_{phase}.json`에 PnL 데이터가 없어서 전략 검증 불가능
- ❌ "PnL > 0 검증" 증거를 제출할 수 없음

**수정 방안 (Step 1):**
```python
@dataclass
class KPICollector:
    # 기존 필드 유지
    start_time: float
    opportunities_generated: int
    intents_created: int
    mock_executions: int
    db_inserts_ok: int
    db_inserts_failed: int
    error_count: int
    errors: List[str]
    db_last_error: str
    memory_mb: float
    cpu_pct: float
    
    # D205-3: PnL 필드 추가
    closed_trades: int = 0
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    fees: float = 0.0
    wins: int = 0
    losses: int = 0
    winrate_pct: float = 0.0
```

**구현 위치:**
- `_record_trade_complete()`: trade 완료 시 KPI 업데이트
  - `self.kpi.closed_trades += 1`
  - `self.kpi.gross_pnl += realized_pnl`
  - `self.kpi.net_pnl = self.kpi.gross_pnl - self.kpi.fees`
  - `self.kpi.fees += total_fee`
  - `self.kpi.wins += 1 if realized_pnl > 0 else 0`
  - `self.kpi.losses += 1 if realized_pnl <= 0 else 0`
  - `self.kpi.winrate_pct = (wins / closed_trades) * 100 if closed_trades > 0 else 0`

---

### 2. Paper Chain (⚠️ daily_report 호출 누락)
**경로:** `arbitrage/v2/harness/paper_chain.py`

**현재 동작:**
- ✅ runner 실행
- ✅ chain_summary.json 생성
- ❌ **daily_report 생성 누락**

**수정 방안 (Step 1):**
```python
# paper_chain.py에서 runner 종료 후:
from arbitrage.v2.reporting.run_daily_report import main as generate_daily_report

# 1. runner 실행 완료
# 2. daily_report 생성
subprocess.run([
    sys.executable, "-m", "arbitrage.v2.reporting.run_daily_report",
    "--date", today.strftime("%Y-%m-%d"),
    "--run-id-prefix", run_id,
    "--output-dir", str(output_dir),
], check=True)
```

---

## 재사용 vs 신규 작성 결정

| 모듈 | 상태 | 재사용 | 신규 작성 | 수정 필요 |
|------|------|--------|-----------|----------|
| **aggregator.py** | ✅ | 100% | 0% | 0% |
| **writer.py** | ✅ | 100% | 0% | 0% |
| **run_daily_report.py** | ✅ | 100% | 0% | 0% |
| **test_d205_1_reporting.py** | ✅ | 100% | 0% | 0% |
| **paper_runner.py KPI** | ❌ | 70% | 0% | 30% (PnL 필드 추가) |
| **paper_chain.py** | ⚠️ | 90% | 0% | 10% (daily_report 호출) |

---

## 결론

### ✅ 재사용 가능 (4개 모듈)
1. `arbitrage/v2/reporting/aggregator.py` (그대로)
2. `arbitrage/v2/reporting/writer.py` (그대로)
3. `arbitrage/v2/reporting/run_daily_report.py` (그대로)
4. `tests/test_d205_1_reporting.py` (그대로)

### ❌ 수정 필요 (2개 모듈)
1. `arbitrage/v2/harness/paper_runner.py`: KPI에 PnL 필드 추가
2. `arbitrage/v2/harness/paper_chain.py`: daily_report 자동 호출 추가

### 📋 다음 단계 (Step 1)
1. `paper_runner.py` KPI 스키마 확장 (7개 필드 추가)
2. `_record_trade_complete()` KPI 업데이트 로직 추가
3. `paper_chain.py` daily_report 자동 호출 추가
4. Gate Fast 실행하여 검증

---

## 참고: 기존 daily_report 산출물 (증거)

**경로:** `logs/evidence/d205_2_reopen_20251230_1817_859d241/d2_pnl_verification.json/daily_report_2025-12-30.json`

```json
{
  "date": "2025-12-30",
  "run_id_prefix": "d204_2_smoke_20251230_1825",
  "pnl": {
    "gross_pnl": 6520036.89617953,
    "net_pnl": 6520023.76617953,
    "fees": 13.13,
    "volume": 5252.0,
    "trades_count": 52,
    "wins": 52,
    "losses": 0,
    "winrate_pct": 100.0
  },
  "ops": {
    "orders_count": 104,
    "fills_count": 104,
    "rejects_count": 0,
    "fill_rate_pct": 100.0
  },
  "generated_at": "2025-12-30T18:27:18.413184"
}
```

**확인:**
- ✅ PnL 데이터 존재 (gross_pnl, net_pnl, fees, trades_count, wins, losses, winrate_pct)
- ✅ Ops 데이터 존재 (orders_count, fills_count, fill_rate_pct)
- ✅ 이 구조를 `kpi_{phase}.json`에도 반영해야 함

---

**Step 0 완료:** ✅ 재사용 모듈 스캔 및 수정 필요 항목 식별 완료
