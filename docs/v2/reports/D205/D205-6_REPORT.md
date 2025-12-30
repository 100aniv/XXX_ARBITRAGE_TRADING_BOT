# D205-6: ExecutionQuality v1 — Slippage/Partial Fill Cost Model + net_edge_after_exec

**작성일:** 2025-12-31

## Status

**Current:** DONE ✅  
**Last Updated:** 2025-12-31  
**Commit:** 135a224dbf614513d7bf55301716094c4bd8d460  
**Branch:** rescue/d99_15_fullreg_zero_fail

## 목표

실제 체결 비용(슬리피지/부분체결)을 반영한 `net_edge_after_exec_bps` 계산

## 구현 완료 내용

### D205-6: ExecutionQuality v1 모델
- **SimpleExecutionQualityModel**: 선형 비용 모델 구현
  - `spread_cost_bps`: 양쪽 taker fee 가정 (기본 25 bps)
  - `slippage_cost_bps`: notional / top_size 비율 기반 선형 증가
  - `partial_fill_risk_bps`: size 부족 시 페널티 (기본 20 bps)
  - `net_edge_after_exec_bps`: edge - total_exec_cost

### 스키마 확장
- **MarketTick**: size 필드 4개 추가 (optional, 하위 호환성 유지)
  - `upbit_bid_size`, `upbit_ask_size`, `binance_bid_size`, `binance_ask_size`
- **DecisionRecord**: execution quality 필드 3개 추가 (optional)
  - `exec_cost_bps`, `net_edge_after_exec_bps`, `exec_model_version`

### ReplayRunner 통합
- ReplayRunner에서 ExecutionQuality 계산 자동 수행
- 기존 데이터(size 없음) → 보수적 페널티 (20 bps) 적용
- 신규 데이터(size 있음) → 실제 비용 계산

## 구현 파일

### 신규 모듈 (3개)
1. **arbitrage/v2/execution_quality/__init__.py**: 모듈 진입점
2. **arbitrage/v2/execution_quality/schemas.py**: ExecutionCostBreakdown 스키마
3. **arbitrage/v2/execution_quality/model_v1.py**: SimpleExecutionQualityModel

### 수정 파일 (3개)
1. **arbitrage/v2/replay/schemas.py**: MarketTick/DecisionRecord 확장
2. **arbitrage/v2/replay/replay_runner.py**: ExecutionQuality 통합
3. **arbitrage/v2/replay/recorder.py**: Git 메타 추가 (SSOT 수정)

## 테스트 결과

### 유닛 테스트 (11개)
- **test_d205_6_execution_quality.py**: 11/11 PASS (0.18s)
  - SimpleExecutionQualityModel 초기화 검증
  - Size 없을 때 보수적 페널티 검증
  - Size 있을 때 슬리피지 계산 검증
  - 슬리피지 단조성 검증 (notional 증가 → cost 비감소)
  - 부분체결 페널티 임계값 검증
  - MarketTick size 필드 호환성 검증
  - DecisionRecord execution quality 필드 검증

### Gate Fast
- **Gate Fast**: 137/137 PASS (69.52s)
  - 기존 126개 + D205-6 11개 = 137개 전체 PASS

### Smoke Test
- **Record**: 10 ticks recorded (20s)
- **Replay**: 10 ticks → 10 decisions, input_hash 일치 ✅
- **ExecutionQuality**: 기존 데이터(size 없음) → exec_cost_bps=null (하위 호환성 OK)

## AC (Acceptance Criteria) 검증

- [x] ExecutionQuality v1 모델 구현 (선형 모델)
- [x] MarketTick size 필드 추가 (optional, 하위 호환성)
- [x] DecisionRecord execution quality 필드 추가
- [x] ReplayRunner 통합 (자동 계산)
- [x] 슬리피지 단조성 검증 (notional 증가 → cost 비감소)
- [x] Size 없을 때 보수적 페널티 적용
- [x] 유닛 테스트 11개 (100% PASS)
- [x] Gate Fast PASS (137/137)
- [x] Record/Replay Smoke PASS

## Evidence

### Smoke Test
- **Record**: `logs/evidence/d205_5_record_replay_20251231_022642/`
  - 10 ticks, git_sha_short 포함 ✅
- **Replay**: `logs/evidence/d205_6_replay_smoke_20251231_022705/`
  - 10 decisions, input_hash: `2bf4999c85db1574`
  - exec_cost_bps: null (기존 데이터 하위 호환)

### Gate Results
- **Gate Fast**: 137/137 PASS (69.52s)
- **Duration**: 1분 9초

## 한계 및 개선 방향

### v1 한계
1. **선형 모델**: 실제 시장 impact는 비선형일 가능성
2. **보수적 페널티**: size 없을 때 20 bps 고정 (시장 상황 무관)
3. **단일 notional**: 100,000 KRW 고정 (실제 주문 크기 고려 안 함)

### v2 개선 방향 (D205-7+)
1. **비선형 모델**: notional^1.2 같은 지수 함수
2. **동적 페널티**: 시장 변동성 기반 페널티 조정
3. **Multi-level aggregation**: L2 orderbook 여러 레벨 합산
4. **Historical calibration**: 실제 Fill Event 데이터 기반 보정

## 의존성

- **Depends on**: D205-5 (Record/Replay SSOT) ✅
- **Blocks**: D205-7 (Parameter Sweep + ExecutionQuality 튜닝)

## 다음 단계

- **D205-7**: Parameter Sweep (리플레이 기반 튜닝)
  - ExecutionQuality 파라미터(alpha, penalty) 최적화
  - 회귀 테스트 자동화 (replay → diff → PASS/FAIL)

---

## 참고 자료

- SSOT: `docs/v2/SSOT_RULES.md`
- V1 FillModel: `arbitrage/execution/fill_model.py` (재사용 참조)
- Architecture: `docs/v2/V2_ARCHITECTURE.md`
