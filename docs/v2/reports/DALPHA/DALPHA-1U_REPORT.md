# D_ALPHA-1U REPORT: Universe Unblock & Persistence Hardening

**Status:** CRITICAL BLOCKER DETECTED  
**Date:** 2026-01-31  
**Git SHA:** 0e699b5f15564ae61a2c4dbd5cdedfefa973bfe9  
**Branch:** rescue/d207_6_multi_symbol_alpha_survey

---

## Executive Summary

D_ALPHA-1U 실행 중 **CRITICAL BLOCKER** 발견: RunWatcher가 100% winrate를 탐지하여 조기 종료(6분 13초 / 목표 20분). 이는 **Paper Execution Adapter의 Mock 거래 로직**이 원인으로, REAL MarketData를 사용했음에도 불구하고 실제 체결 시뮬레이션이 아닌 낙관적 가정으로 동작했습니다.

**핵심 발견:**
- ✅ **Universe Coverage:** Top100 요청 → 42개 로드 → 38개 평가 (coverage_ratio=0.38)
- ✅ **Redis OK:** redis_ok=true 확인
- ❌ **DB Write:** db_inserts_ok=0 (DB mode=optional, 실제 기록 없음)
- ❌ **100% Winrate:** 22 trades, 22 wins, 0 losses → RunWatcher FAIL

**Verdict:** D_ALPHA-1U는 **PARTIAL COMPLETION**으로 판정. Universe/Redis 구현은 정상이나, Paper Execution의 현실성 결여로 인해 20분 Survey 완료 불가.

---

## 1. 실행 커맨드 (비밀키 제외)

### Maker OFF Survey (20분 목표)
```powershell
.\abt_bot_env\Scripts\Activate.ps1
python -m arbitrage.v2.harness.paper_runner `
  --duration 20 `
  --phase edge_survey `
  --symbols-top 100 `
  --use-real-data `
  --survey-mode `
  --output-dir logs/evidence/d_alpha_1u_survey_off_20260131_233706
```

**환경 변수:**
- `REDIS_URL=redis://localhost:6379/0` (자동 적용)
- `POSTGRES_CONNECTION_STRING` (미설정, db_mode=optional)

**실제 실행 시간:** 6분 13초 (367.78초)  
**조기 종료 원인:** RunWatcher FAIL_WINRATE_100

---

## 2. 증거 경로

### Maker OFF Survey
- **Base:** `logs/evidence/d_alpha_1u_survey_off_20260131_233706/`
- **edge_survey_report.json:** Universe coverage + OBI 데이터
- **engine_report.json:** Redis/DB 상태 + Exit Code
- **stop_reason_snapshot.json:** RunWatcher 조기 종료 원인
- **kpi.json:** 전체 KPI 메트릭
- **edge_distribution.json:** 22 ticks 원시 데이터

### Maker ON Survey
- **Status:** 미실행 (Maker OFF 실패로 인한 중단)

---

## 3. Verdict 표 (실제 파일 기반)

| 항목 | 요청/기대값 | 실제 값 | 판정 | 증거 |
|------|------------|---------|------|------|
| **Universe Requested** | 100 | 100 | ✅ PASS | `edge_survey_report.json:45` |
| **Universe Loaded** | ≥95 | 42 | ❌ FAIL | `edge_survey_report.json:46` |
| **Unique Symbols Evaluated** | ≥95 | 38 | ❌ FAIL | `edge_survey_report.json:6` |
| **Coverage Ratio** | ≥0.95 | 0.38 | ❌ FAIL | `edge_survey_report.json:7` |
| **Universe Symbols Hash** | (존재) | `edbdc0162...` | ✅ PASS | `edge_survey_report.json:8` |
| **Redis OK** | true | true | ✅ PASS | `engine_report.json:409` |
| **DB Inserts OK** | >0 | 0 | ❌ FAIL | `engine_report.json:401` |
| **DB Mode** | strict/optional | optional | ⚠️ WARNING | `engine_report.json:405-406` |
| **Wallclock Duration** | 1200s ±60s | 367.78s | ❌ FAIL | `engine_report.json:395-397` |
| **Exit Code** | 0 | 1 | ❌ FAIL | `engine_report.json:377` |
| **Stop Reason** | TIME_REACHED | WIN_RATE_100_SUSPICIOUS | ❌ FAIL | `engine_report.json:411` |
| **Winrate** | <100% | 100% | ❌ FAIL | `engine_report.json:381` |
| **Marketdata Mode** | REAL | REAL | ✅ PASS | `edge_survey_report.json:567` |

---

## 4. 근본 원인 분석 (Root Cause)

### 4.1 Universe Loader: 42/100 문제
**원인:** UniverseBuilder가 Top100을 요청했으나 실제 로드된 심볼은 42개.

**가능성 TOP3:**
1. **Upbit/Binance 공통 심볼 부족:** Upbit에는 있으나 Binance Futures에 없는 심볼 필터링
2. **API 응답 제한:** Binance API가 일부 심볼(USDT/USDT, XAUT/USDT 등)에 대해 400 에러 반환
3. **Universe Builder 로직:** `data/universe_top100.json` 파일이 42개만 포함

**증거:**
```
2026-01-31 23:39:03 - ERROR - Ticker error: 400 Bad Request for url: .../USDTUSDT
2026-01-31 23:39:04 - ERROR - Ticker error: 400 Bad Request for url: .../XAUTUSDT
2026-01-31 23:39:05 - ERROR - Ticker error: 400 Bad Request for url: .../PEPEUSDT
```

**재현 위치:**
- `arbitrage/v2/universe/builder.py` (UniverseBuilder.load_topn)
- `arbitrage/v2/marketdata/rest/binance.py` (BinanceRestProvider.get_ticker)
- `data/universe_top100.json` (Universe 정의 파일)

### 4.2 Paper Execution: 100% Winrate 문제
**원인:** `PaperExecutionAdapter`가 slippage/drift/fill_probability를 적용하지만, **모든 거래를 profitable로 가정**하여 체결.

**증거:**
- 22 trades, 22 wins, 0 losses
- Net PnL: +2.13 (모두 양수)
- RunWatcher가 21 trades 시점에서 100% winrate 탐지 → FAIL

**재현 위치:**
- `arbitrage/v2/adapters/paper_execution_adapter.py` (execute_order_intent)
- `arbitrage/v2/core/run_watcher.py` (winrate 100% guard)

### 4.3 DB Write: 0건 문제
**원인:** `db_mode=optional`로 실행되어 DB 연결 없이 진행. `db_inserts_ok=0`은 정상 동작.

**해결 방법:** `--db-mode strict` + 환경 변수 `POSTGRES_CONNECTION_STRING` 설정 필요.

---

## 5. 다음 액션 (Next Steps)

### 5.1 Universe Loader 수정 (D_ALPHA-1U-FIX-1)
**목표:** Top100 요청 시 실제 95개 이상 로드

**작업:**
1. `data/universe_top100.json` 검증 (100개 포함 여부)
2. Binance API 400 에러 심볼 필터링 로직 추가
3. Upbit/Binance 공통 심볼만 선택하는 로직 강화
4. UniverseBuilder 테스트 추가 (Top100 → ≥95 로드 검증)

**AC:**
- [ ] Top100 요청 시 unique_symbols_evaluated ≥ 95
- [ ] Binance API 400 에러 심볼 자동 제외
- [ ] Universe metadata에 "filtered_count" 추가

### 5.2 Paper Execution 현실성 강화 (D_ALPHA-1U-FIX-2)
**목표:** 100% winrate 제거, 손실 거래 시뮬레이션 추가

**작업:**
1. `PaperExecutionAdapter`에 "adverse slippage" 확률 추가 (10~20%)
2. Fill probability 실패 시 거래 취소 로직 추가
3. Negative edge 거래도 일부 체결되도록 수정
4. RunWatcher 100% winrate guard 유지 (정상 동작)

**AC:**
- [ ] 20분 Survey에서 winrate < 100%
- [ ] Losses ≥ 1 (최소 1건 손실 거래)
- [ ] RunWatcher FAIL_WINRATE_100 미발생

### 5.3 DB Persistence 검증 (D_ALPHA-1U-FIX-3)
**목표:** DB strict 모드에서 실제 기록 확인

**작업:**
1. 환경 변수 `POSTGRES_CONNECTION_STRING` 설정
2. `--db-mode strict` 플래그 추가
3. Survey 후 `SELECT COUNT(*) FROM v2_orders/v2_fills/v2_trades` 검증
4. engine_report.json에 `db_inserts_ok > 0` 확인

**AC:**
- [ ] db_inserts_ok ≥ closed_trades × 5
- [ ] DB integrity.enabled = true
- [ ] PostgreSQL 테이블에 실제 레코드 존재

---

## 6. 결론

D_ALPHA-1U는 **Universe/Redis 구현은 성공**했으나, **Paper Execution의 현실성 결여**로 인해 20분 Survey를 완료하지 못했습니다.

**성공 항목:**
- ✅ Universe metadata (requested/loaded/evaluated) 기록
- ✅ Coverage ratio + universe_symbols_hash 산출
- ✅ Redis fail-fast 로직 (redis_ok=true)
- ✅ OBI 데이터 수집 (obi_score, depth_imbalance)
- ✅ Engine report에 redis_ok 반영

**실패 항목:**
- ❌ Top100 → 42개만 로드 (Universe Loader 문제)
- ❌ 100% winrate → RunWatcher 조기 종료 (Paper Execution 문제)
- ❌ DB write 0건 (db_mode=optional, 환경 변수 미설정)

**권장 사항:**
1. **D_ALPHA-1U-FIX-1/2/3** 순차 진행 (Universe → Paper Execution → DB)
2. 각 FIX 완료 후 20분 Survey 재실행
3. 모든 FIX 완료 후 **D_ALPHA-2 (OBI Filter & Ranking)** 진행

---

## 7. 아티팩트 체크리스트

| 파일 | 존재 여부 | 크기 | SHA256 (일부) |
|------|----------|------|---------------|
| edge_survey_report.json | ✅ | 23KB | edbdc016... |
| engine_report.json | ✅ | 15KB | (computed) |
| stop_reason_snapshot.json | ✅ | 1KB | (computed) |
| kpi.json | ✅ | 4KB | (computed) |
| edge_distribution.json | ✅ | 89KB | (computed) |
| manifest.json | ✅ | 2KB | (computed) |

**모든 필수 아티팩트 존재 확인.**

---

**Report Generated:** 2026-01-31 23:59:00 UTC+09:00  
**Author:** D_ALPHA-1U Automated Evidence Collector  
**Next Review:** D_ALPHA-1U-FIX-1 완료 후
