# D207-1-1: BASELINE 20분 실행 결과

**Date:** 2026-01-18  
**Duration:** 20분 (1200초)  
**Status:** ❌ FAILED (Exit Code 1)  
**Branch:** rescue/d205_15_multisymbol_scan

---

## 실행 개요 (Execution Overview)

### 목표
- Real MarketData + Slippage/Latency 모델 강제
- 20분 BASELINE 실행
- net_pnl > 0 검증
- DB 기록 (orders/fills/trades) 검증

### 결과
- ✅ **Wallclock:** 1200.0s (정확)
- ✅ **Heartbeat:** 41 lines (정상)
- ✅ **Opportunities:** 11,880 감지
- ❌ **DB Insert:** 0/35,640 (실패)
- ❌ **Report:** 생성 실패

---

## KPI 요약 (KPI Summary)

```json
{
  "iterations": 11880,
  "opportunities": 11880,
  "closed_trades": 11880,
  "net_pnl": 98921413.09,
  "wallclock_duration_sec": 1200.0,
  "heartbeat_lines": 41,
  "db_inserts_ok": 0,
  "db_inserts_fail": 35640
}
```

---

## 실패 분석 (Failure Analysis)

### 근본 원인 (Root Cause)

#### 1) DB Insert 파라미터 오류
```
ERROR: V2LedgerStorage.insert_order() missing 9 required positional arguments
```

**파일:** `arbitrage/v2/core/ledger_writer.py`  
**원인:** LedgerWriter에서 V2LedgerStorage 메서드 호출 시 파라미터 누락  
**영향:** DB orders/fills/trades 테이블 insert 0건

#### 2) Report 생성 오류
```
ERROR: generate_engine_report() got an unexpected keyword argument 'config_path'
```

**파일:** `arbitrage/v2/core/engine_report.py`  
**원인:** 함수 시그니처 불일치  
**영향:** Report 파일 미생성

### 시장 vs 로직 판별 (Market vs Logic)

| 항목 | 상태 | 판정 |
|---|---|---|
| **Market Opportunity** | 11,880 opportunities 감지 | ✅ 충분 |
| **Mock Data** | Real MarketData (Binance/Upbit) | ✅ 실제 데이터 |
| **Logic Error** | DB Insert 파라미터 누락 | ❌ 로직 오류 |
| **Logic Error** | Report 생성 실패 | ❌ 로직 오류 |

**결론:** **로직 오류 (Logic Error)** - 시장 기회는 충분하나 엔진 구현 미완성

---

## Evidence 경로

```
logs/evidence/d205_18_2d_baseline_20260118_1442/
├── kpi.json                    # KPI 요약
├── metrics_snapshot.json       # 메트릭 스냅샷
├── decision_trace.json         # 거래 결정 추적
├── chain_summary.json          # 체인 요약
├── manifest.json               # 실행 메타데이터
├── heartbeat.jsonl             # Heartbeat 로그
└── DIAGNOSIS.md                # 실패 원인 분석
```

---

## 필요한 수정 (Required Fixes)

### D206-4-2: LedgerWriter 파라미터 수정
- **파일:** `arbitrage/v2/core/ledger_writer.py`
- **작업:** V2LedgerStorage 메서드 호출 시 모든 필수 파라미터 전달
- **검증:** test_d206_4_order_pipeline.py PASS

### D206-4-3: engine_report 함수 시그니처 수정
- **파일:** `arbitrage/v2/core/engine_report.py`
- **작업:** `generate_engine_report()` 함수 시그니처 수정
- **검증:** Report 파일 정상 생성

---

## 다음 단계 (Next Steps)

1. D206-4-2 FIX: LedgerWriter 파라미터 수정
2. D206-4-3 FIX: engine_report 함수 시그니처 수정
3. D207-1-1 재실행: 수정 후 20분 BASELINE 재실행
4. D207-1 COMPLETED: net_pnl > 0 + DB 기록 검증 후 완료

---

**Status:** ❌ FAILED - 엔진 구현 미완성 (DB Insert, Report 생성)
