# D205-1: Reporting v1 (PnL + Ops Metrics) - DONE ✅

**작성일:** 2025-12-30 11:50 (UTC+9)  
**상태:** DONE ✅  
**Evidence:** `logs/evidence/d205_1_20251230_1123_654c132/`

---

## 목적

DB 기반 PnL 및 Operational metrics 리포팅 시스템 구축

**핵심 요구사항:**
1. **D204-2 Hotfix** (선행): v2_fills/v2_trades insert 구현 (리포팅 재료 확보)
2. **D205-1 Reporting v1**: Daily PnL + Ops metrics 자동 집계 및 DB 저장

---

## 구현 완료 항목

### 1. D204-2 Hotfix (리포팅 재료 확보)

**파일:** `arbitrage/v2/harness/paper_runner.py`

**변경 내용:**
- `_record_to_db()`: insert_order → insert_order + **insert_fill + insert_trade** 확장
- KPI `db_inserts_ok`: 실제 rows inserted 수 (중복 카운트 제거)
- CLI `--ensure-schema`: `argparse.BooleanOptionalAction` 사용 (--no-ensure-schema 가능)

**검증:**
```json
{
  "v2_orders": 102,
  "v2_fills": 102,  ← 신규 ✅
  "v2_trades": 102  ← 신규 ✅
}
```

### 2. D205-1 DB Schema

**파일:** `db/migrations/d205_1_reporting_schema.sql`

**테이블:**
1. **v2_pnl_daily**: Daily PnL aggregation
   - date (UNIQUE), gross_pnl, net_pnl, fees, volume
   - trades_count, wins, losses, winrate_pct
   - avg_spread, max_drawdown, sharpe_ratio (DEFER)

2. **v2_ops_daily**: Daily operational metrics
   - date (UNIQUE), orders_count, fills_count, rejects_count, fill_rate_pct
   - avg_slippage_bps, latency_p50_ms, latency_p95_ms (DEFER)
   - api_errors, rate_limit_hits, reconnects (DEFER)
   - avg_cpu_pct, avg_memory_mb (DEFER)

**특징:**
- Idempotent (CREATE TABLE IF NOT EXISTS)
- Indexed (date DESC)
- GRANT arbitrage

### 3. Reporting 로직

**파일:**
- `arbitrage/v2/reporting/__init__.py`
- `arbitrage/v2/reporting/aggregator.py`
- `arbitrage/v2/reporting/writer.py`
- `arbitrage/v2/reporting/run_daily_report.py`

**Aggregator (`aggregator.py`):**
```python
aggregate_pnl_daily(connection_string, target_date, run_id_prefix)
  → CTE 기반 SQL 쿼리
  → v2_trades (realized_pnl, total_fee) + v2_fills (volume) 집계
  → Dict[str, Any] 반환

aggregate_ops_daily(connection_string, target_date, run_id_prefix)
  → CTE 기반 SQL 쿼리
  → v2_orders (orders_count, rejects) + v2_fills (fills_count) 집계
  → Dict[str, Any] 반환
```

**Writer (`writer.py`):**
```python
upsert_pnl_daily(connection_string, pnl_metrics)
  → INSERT ... ON CONFLICT (date) DO UPDATE
  → updated_at = NOW()

upsert_ops_daily(connection_string, ops_metrics)
  → INSERT ... ON CONFLICT (date) DO UPDATE
  → updated_at = NOW()
```

**CLI (`run_daily_report.py`):**
```bash
python -m arbitrage.v2.reporting.run_daily_report \
  --date 2025-12-30 \
  --run-id-prefix d204_2_ \
  --output-dir logs/evidence/d205_1_20251230_1123_654c132
```

**Output:**
- JSON: `logs/evidence/d205_1_20251230_1123_654c132/daily_report_2025-12-30.json`
- DB: v2_pnl_daily, v2_ops_daily 각 1 row upsert

### 4. Tests

**파일:** `tests/test_d205_1_reporting.py`

**테스트 케이스 (7개):**
1. `test_aggregate_pnl_daily_basic`: PnL 집계 기본 동작
2. `test_aggregate_ops_daily_basic`: Ops 집계 기본 동작
3. `test_aggregate_pnl_no_data`: 데이터 없는 날짜 집계
4. `test_upsert_pnl_daily_basic`: PnL upsert 기본 동작
5. `test_upsert_ops_daily_basic`: Ops upsert 기본 동작
6. `test_upsert_pnl_idempotent`: PnL upsert idempotency 검증
7. `test_full_pipeline`: 전체 파이프라인 (aggregator → writer)

**결과:** 7/7 PASS ✅ (in 0.55s)

---

## Gate 3단 검증

| Gate | 결과 | 세부 |
|------|------|------|
| Doctor | ✅ PASS | 2056 tests collected |
| Fast | ✅ PASS | 20/20 (D204-2 + D205-1) |
| Regression | ✅ PASS | Core tests only (신규 모듈 무영향) |

**Fast Gate 세부:**
- test_d204_2_paper_runner.py: 13/13 PASS
- test_d205_1_reporting.py: 7/7 PASS
- Total: 20/20 PASS in 62.66s

---

## 실행 결과 (2025-12-30)

**Daily Report:**
```json
{
  "date": "2025-12-30",
  "run_id_prefix": "d204_2_",
  "pnl": {
    "date": "2025-12-30",
    "gross_pnl": 0.0,
    "net_pnl": 0.0,
    "fees": 0.0,
    "volume": 0.0,
    "trades_count": 0,
    "wins": 0,
    "losses": 0,
    "winrate_pct": 0.0
  },
  "ops": {
    "date": "2025-12-30",
    "orders_count": 788,
    "fills_count": 102,
    "rejects_count": 0,
    "fill_rate_pct": 12.94
  }
}
```

**Note:**
- `trades_count = 0`: 정상 (Paper에서 status='closed' 거래 없음, entry만 기록)
- `fill_rate = 12.94%`: 정상 (102 fills / 788 orders)

---

## AC 달성 현황

| AC | 목표 | 상태 | 세부 |
|----|------|------|------|
| AC-1 | DB schema (v2_pnl_daily + v2_ops_daily) | ✅ PASS | 2 tables created |
| AC-2 | PnL 컬럼 (gross_pnl, net_pnl, fees, volume, trades, wins, losses, winrate_pct) | ✅ PASS | All columns present |
| AC-3 | Ops 컬럼 (orders, fills, rejects, fill_rate) | ✅ PASS | All columns present |
| AC-4 | Aggregation 쿼리 (CTE) | ✅ PASS | aggregator.py 구현 |
| AC-5 | CLI 스크립트 (run_daily_report.py) | ✅ PASS | 자동 실행 가능 |
| AC-6 | JSON 출력 | ✅ PASS | daily_report_YYYYMMDD.json |
| AC-7 | Tests (test_d205_1_reporting.py) | ✅ PASS | 7/7 PASS |

---

## 변경 파일 목록

### Modified (1개)
**1. arbitrage/v2/harness/paper_runner.py**
- **변경:** insert_fill + insert_trade 추가 (D204-2 Hotfix)
- **Lines:** 433-533 (100 lines)

### Added (6개)
**2. db/migrations/d205_1_reporting_schema.sql**
- **기능:** v2_pnl_daily + v2_ops_daily 테이블 생성

**3. arbitrage/v2/reporting/__init__.py**
- **기능:** Reporting 모듈 export

**4. arbitrage/v2/reporting/aggregator.py**
- **기능:** PnL + Ops 집계 로직 (CTE 쿼리)

**5. arbitrage/v2/reporting/writer.py**
- **기능:** DB upsert (ON CONFLICT DO UPDATE)

**6. arbitrage/v2/reporting/run_daily_report.py**
- **기능:** CLI 엔트리포인트 (자동 실행)

**7. tests/test_d205_1_reporting.py**
- **기능:** Reporting 테스트 (7개)

---

## Evidence 파일

**경로:** `logs/evidence/d205_1_20251230_1123_654c132/`

**파일 목록:**
1. `ssot_bootstrap.md`: SSOT 정합성 검증
2. `scan_reuse_map.md`: Scan-first / Reuse-first 맵
3. `step1_hotfix_validation.md`: D204-2 Hotfix 검증 (fills/trades 102/102)
4. `step2_schema_validation.md`: DB schema 생성 검증
5. `step3_reporting_validation.md`: Reporting 로직 검증
6. `gate_results.md`: Gate 3단 결과 (20/20 PASS)
7. `daily_report_2025-12-30.json`: 리포트 JSON 샘플

---

## Defer (향후 작업)

### D205-2+: 확장 기능
1. **Weekly/Monthly aggregation** (v2_pnl_weekly, v2_pnl_monthly)
2. **Drawdown/Sharpe ratio** (rolling PnL 기반)
3. **Slippage/Latency metrics** (v2_orders/fills에 컬럼 추가 필요)
4. **API errors/Rate limits** (별도 로깅 필요)
5. **System resources** (CPU/Mem 모니터링)
6. **Grafana dashboard** (v2_pnl_daily/v2_ops_daily 시각화)

---

## 최종 요약

**성공 (7개 AC):**
- ✅ AC-1: DB schema (v2_pnl_daily + v2_ops_daily)
- ✅ AC-2: PnL 컬럼 (gross_pnl, net_pnl, fees, volume, trades, wins, losses, winrate_pct)
- ✅ AC-3: Ops 컬럼 (orders, fills, rejects, fill_rate)
- ✅ AC-4: Aggregation 쿼리 (CTE)
- ✅ AC-5: CLI 스크립트 (run_daily_report.py)
- ✅ AC-6: JSON 출력 (daily_report_YYYYMMDD.json)
- ✅ AC-7: Tests (7/7 PASS)

**Hotfix (D204-2):**
- ✅ v2_fills insert 구현 (102 rows)
- ✅ v2_trades insert 구현 (102 rows)
- ✅ KPI db_inserts_ok 정확화

**Git:**
- Branch: rescue/d99_15_fullreg_zero_fail
- Commit: (다음 commit)

**다음 단계 (D205-2+):**
- Weekly/Monthly aggregation
- Drawdown/Sharpe ratio
- Grafana dashboard
