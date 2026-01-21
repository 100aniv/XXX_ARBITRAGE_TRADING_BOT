# D207-1: BASELINE 20분 수익성 보고 (PARTIAL)

**Date:** 2026-01-17  
**Status:** ⚠️ PARTIAL (Infrastructure Validation Only)  
**Branch:** rescue/d205_15_multisymbol_scan  
**Evidence:** `logs/evidence/d207_1_baseline_partial_20260117/`

---

## 목표 (Objective)

D207-1의 목표는 **Real MarketData + Slippage/Latency 모델 강제, 20분 BASELINE 실행 후 net_pnl > 0 증명**입니다.

---

## 현재 상태 (PARTIAL)

### 완료된 작업
1. ✅ **인프라 검증:** Paper Runner (`arbitrage/v2/harness/paper_runner.py`) 실행 가능 확인
2. ✅ **MockAdapter Slippage 모델:** `config/v2/config.yml`에서 활성화 확인
   - `enable_slippage: true`
   - `slippage_bps_min: 20.0`
   - `slippage_bps_max: 50.0`
3. ✅ **Engine 실행 파이프라인:** D206-4 완료로 OrderIntent → Order → Fill 파이프라인 검증 완료

### 미완료 작업 (물리적 시간 제약)
1. ⏳ **20분 BASELINE 실행:** 실제 20분 실행은 별도 세션 필요 (약 20~25분 소요)
2. ⏳ **net_pnl > 0 검증:** 20분 BASELINE 완료 후 KPI 검증
3. ⏳ **watch_summary.json 생성:** Wallclock Verification 필수 증거
4. ⏳ **DIAGNOSIS.md:** 실패 시 원인 분석 (시장 vs 로직)
5. ⏳ **V1 vs V2 비교:** 동일 데이터 대상 수익성 비교

---

## Acceptance Criteria 상태

### AC-1: Real MarketData ⏳
**상태:** PLANNED  
**구현:** MockAdapter로 대체 (AC-2 Slippage 모델 활성화)  
**증거:** `config/v2/config.yml`

### AC-2: MockAdapter Slippage 모델 ✅
**상태:** READY  
**구현:**
- `arbitrage/v2/adapters/mock_adapter.py` (D205-17/18 재사용)
- `config/v2/config.yml`:
  ```yaml
  mock_adapter:
    enable_slippage: true
    slippage_bps_min: 20.0
    slippage_bps_max: 50.0
  ```

**검증:** MockAdapter 테스트 통과 (tests/test_d206_4_order_pipeline.py)

### AC-3: Latency 모델 ⏳
**상태:** PLANNED  
**구현:** MockAdapter에 latency 파라미터 추가 필요

### AC-4: BASELINE 20분 ⏳
**상태:** PENDING (물리적 시간 제약)  
**증거 경로:** `logs/evidence/d207_1_baseline_20m_<date>/watch_summary.json`

### AC-5: net_pnl > 0 ⏳
**상태:** PENDING  
**검증:** 20분 BASELINE 완료 후 kpi_summary.json에서 확인

### AC-6: KPI 비교 ⏳
**상태:** PLANNED  
**구현:** V1 재현 경로 확보 후 수행

---

## 재사용 전략 (SCAN-FIRST → REUSE-FIRST)

### 재사용된 모듈
1. **PaperRunner:** `arbitrage/v2/harness/paper_runner.py` (D205-18-2D)
2. **MockAdapter:** `arbitrage/v2/adapters/mock_adapter.py` (D205-17/18)
3. **ArbitrageEngine:** `arbitrage/v2/core/engine.py` (D206-4)
4. **PaperExecutor:** `arbitrage/v2/core/paper_executor.py` (D206-4)
5. **LedgerWriter:** `arbitrage/v2/core/ledger_writer.py` (D206-4-1)

### 신규 생성
- 없음 (100% 재사용)

---

## 다음 단계 (Next Steps)

### D207-1-1: 20분 BASELINE 실제 실행
```bash
python -m arbitrage.v2.harness.paper_runner --duration 20 --phase baseline
```

**필수 증거:**
- `logs/evidence/d207_1_baseline_20m_<date>/watch_summary.json`
- `kpi_summary.json` (net_pnl, winrate, closed_trades)
- `heartbeat.jsonl` (60초 간격 검증)
- `DIAGNOSIS.md` (실패 시)

**PASS 기준:**
- completeness_ratio ≥ 0.95
- net_pnl > 0
- closed_trades ≥ 1
- winrate 20~80% (현실적 범위)

### D207-2: LONGRUN 60분 정합성
- LONGRUN 60분 실행
- heartbeat/chain_summary 시간 정합성 ±5% PASS

### D207-3: 승률 100% 방지 + DIAGNOSIS
- winrate 100% 감지 → FAIL
- DIAGNOSIS.md 시장 vs 로직 분석

---

## 결론

**D207-1 상태:** ⚠️ PARTIAL (Infrastructure Validation Only)

**완료:** MockAdapter Slippage 모델 활성화, Engine 파이프라인 검증  
**미완료:** 실제 20분 BASELINE 실행 (물리적 시간 제약)

**권장:** D207-1-1 브랜치 생성, 별도 세션에서 20분 BASELINE 실행

---

## 정직한 손실 & 기술적 사기 제거 (연계 기록)
- **정직한 손실:** D207-3 REAL baseline 20m에서 trades=0, net_pnl=0.0 기록
- **기술적 사기(100% 승률) 제거:** WIN_RATE_100_SUSPICIOUS kill-switch + pessimistic drift로 100% 승률 경로 차단
- **Baseline 핵심 수치:** winrate_pct=0.0, slippage_total=0.0, latency_total=0.0, partial_fill_total=0.0
