# D205-5: Record/Replay SSOT — 작업 완료 보고서

**작업 ID:** D205-5  
**상태:** DONE ✅  
**작성일:** 2025-12-31  
**커밋:** 7a95ca7 (initial) + 5181cbc (AC verification)  
**브랜치:** rescue/d99_15_fullreg_zero_fail

---

## 목표

NDJSON 기록 포맷 SSOT 정의 및 동일 입력 → 동일 결정 재현 (회귀 테스트 기반)

## 구현 완료 내용

### 1) Record 기능
- **모듈:** `arbitrage/v2/replay/recorder.py`
- **출력:** `market.ndjson` (MarketTick 스키마)
- **기능:** 실시간 시장 데이터 기록

### 2) Replay 기능
- **모듈:** `arbitrage/v2/replay/replay_runner.py`
- **입력:** `market.ndjson`
- **출력:** `decisions.ndjson` (DecisionRecord 스키마)
- **기능:** 동일 입력 → 동일 결정 재현

### 3) Schemas (SSOT)
- **모듈:** `arbitrage/v2/replay/schemas.py`
- **MarketTick:** timestamp, symbol, upbit_bid/ask, binance_bid/ask, size 등
- **DecisionRecord:** spread_bps, gate_passed, fx_krw_per_usdt_used, quote_mode 등

### 4) CLI Wrapper
- **스크립트:** `scripts/run_d205_5_record_replay.py`
- **모드:** `--mode record` / `--mode replay`
- **FX 주입:** `--fx-krw-per-usdt` (기본값: 1450.0)

## Evidence

### Record Evidence
**폴더:** `logs/evidence/d205_5_record_replay_20251231_022642/`
- manifest.json (git_sha: 7a95ca7, ticks: 10)
- market.ndjson (10 ticks, BTC/KRW)
- kpi.json

### Replay Evidence
**폴더:** `logs/evidence/d205_5_replay_20251231_154604/`
- manifest.json (git_sha: 5181cbc, decisions: 10)
- decisions.ndjson (10 decisions)

### 결정론 재현성 검증
- **input_hash:** `2bf4999c85db1574`
- **ticks_count:** 10
- **decisions_count:** 10
- **Status:** PASS (동일 입력 → 동일 결정)

## AC (Acceptance Criteria) 검증

- [x] NDJSON 포맷 SSOT 정의 (`arbitrage/v2/replay/schemas.py`)
- [x] market.ndjson 기록 (10 ticks)
- [x] decisions.ndjson 기록 (10 decisions)
- [x] 리플레이 엔진: 동일 market.ndjson → 동일 decisions.ndjson
- [x] 회귀 테스트 자동화 (`tests/test_d205_5_record_replay.py`)

## 테스트 결과

### Unit Tests
- **tests/test_d205_5_record_replay.py:** 12/12 PASS

### Gate Results
- **Doctor:** PASS
- **Fast:** 140/140 PASS
- **Regression:** PASS

## 재현 방법

### Record
```bash
python scripts/run_d205_5_record_replay.py \
  --mode record \
  --symbols BTC/KRW \
  --duration-sec 20 \
  --sample-interval-sec 2.0 \
  --out-evidence-dir logs/evidence/d205_5_record_<timestamp>
```

### Replay
```bash
python scripts/run_d205_5_record_replay.py \
  --mode replay \
  --input-file logs/evidence/d205_5_record_<timestamp>/market.ndjson \
  --out-evidence-dir logs/evidence/d205_5_replay_<timestamp> \
  --fx-krw-per-usdt 1450
```

## 의존성

- **Depends on:** D205-4 (Reality Wiring) ✅
- **Blocks:** D205-6 (ExecutionQuality), D205-7 (Parameter Sweep)

## 다음 단계

- **D205-6:** ExecutionQuality v1 (슬리피지/부분체결 모델)
- **D205-7:** Parameter Sweep v1 (100+ combos 튜닝)

---

## 참고 자료

- SSOT: `docs/v2/SSOT_RULES.md`
- Replay Format: `arbitrage/v2/replay/schemas.py`
- Architecture: `docs/v2/V2_ARCHITECTURE.md`
