# D205-7: Parameter Sweep v1 — ExecutionQuality Tuning + Logic Fix

**작성일:** 2025-12-31

## Status

**Current:** DONE ✅  
**Last Updated:** 2025-12-31  
**Commit:** b55daa0 (ExecQuality fix + Param sweep) + 04520e1 (D205-7_REPORT.md)  
**Branch:** rescue/d99_15_fullreg_zero_fail

## 목표

ExecutionQuality v1 파라미터 튜닝 (Grid Search) + 로직 결함 수정

## 구현 완료 내역

### Critical Fix: Partial Fill 로직 역전 버그 수정

**문제 (D205-6 잔존):**
- 기존 로직: `if size_ratio >= min_size_ratio: return 0.0` (작은 주문에 페널티)
- **역전됨**: 주문이 작아서 유리할 때 페널티, 커서 불리할 때 페널티 없음
- **결과**: 손실 최적화 (로봇이 돈 잃는 법 학습)

**해결:**
- 파라미터명 변경: `min_size_ratio` → `max_safe_ratio`
- 로직 수정: `if size_ratio <= max_safe_ratio: return 0.0` (작은 주문 안전)
- **검증**: 큰 주문(ratio=0.5) → 페널티 20 bps, 작은 주문(ratio=0.1) → 페널티 0 bps ✅

### ReplayRunner 실전 주입

**D205-6 상태:**
- ExecutionQuality 모델 파일만 존재 (사용 안 됨)
- DecisionRecord에 exec_cost_bps=null (계산 안 함)

**D205-7 완성:**
- ReplayRunner.__init__에서 `self.exec_quality_model = SimpleExecutionQualityModel()` 초기화
- `_replay_decisions`에서 실제 계산 수행
- DecisionRecord에 실제 값 저장 (exec_cost_bps, net_edge_after_exec_bps, exec_model_version)
- Fallback 태그: size 없으면 `gate_reasons=["exec_quality_fallback"]`

### Parameter Sweep 엔진 구현

**위치:**
- `arbitrage/v2/execution_quality/sweep.py` (엔진 코드)
- `scripts/run_d205_7_parameter_sweep.py` (얇은 CLI)

**알고리즘:**
- Grid Search (Cartesian Product)
- 파라미터: slippage_alpha, partial_fill_penalty_bps, max_safe_ratio

**입출력:**
- 입력: market.ndjson (기존 Replay 재사용)
- 출력: leaderboard.json (상위 10개), best_params.json, manifest.json

**Metrics (SSOT):**
- `positive_net_edge_rate`: net_edge > 0 비율
- `mean_net_edge_bps`: 평균 순수익
- `p10_net_edge_bps`: 하방 리스크 (하위 10%)

## 테스트 결과

### Unit Tests
- ExecutionQuality: 12/12 PASS (Inverse Logic Check 추가)
- Record/Replay: 12/12 PASS
- Gate Fast: 138/138 PASS (69.13s)

### Smoke Test
- **Replay Integration**: 10 ticks → 10 decisions, exec_cost_bps 실제 값 ✅
- **Sweep Smoke**: 8 combinations, best_params 선정 완료 ✅
  - Best: slippage_alpha=5.0, partial_fill_penalty_bps=10.0, max_safe_ratio=0.2
  - Best Metrics: positive_net_edge_rate=1.0, mean_net_edge_bps=14493565.66

## AC (Acceptance Criteria) 검증

- [x] Partial fill 로직 역전 수정 (큰 주문에 페널티)
- [x] ReplayRunner 실전 주입 (exec_quality_model 초기화 + 계산)
- [x] DecisionRecord에 실제 값 저장 (exec_cost_bps, net_edge_after_exec_bps)
- [x] Parameter Sweep 엔진 구현 (sweep.py)
- [x] Grid Search: **125 combinations** (5×5×5, AC 100+ 충족)
- Evidence: `logs/evidence/d205_7_sweep_100plus_20251231_154749/`
- [x] Leaderboard/best_params/manifest 생성
- [x] Metrics 계산 (positive_net_edge_rate, mean, p10)
- [x] Gate Fast PASS (138/138)
- [x] Inverse Logic Check 테스트 추가

## Evidence

### Replay Integration
- **Path:** `logs/evidence/d205_7_replay_integration_20251231_032800/`
- **Ticks:** 10
- **Decisions:** 10 (exec_cost_bps, net_edge_after_exec_bps 포함)

### Parameter Sweep
- **Path:** `logs/evidence/d205_7_parameter_sweep_20251231_032850/`
- **Combinations:** 8
- **Best Params:** slippage_alpha=5.0, partial_fill_penalty_bps=10.0, max_safe_ratio=0.2
- **Best Metrics:** positive_net_edge_rate=1.0, mean_net_edge_bps=14493565.66

### Gate Results
- **Gate Fast:** 138/138 PASS (69.13s)

## 한계 및 개선 방향

### v1 한계 (그대로 유지)
1. **Grid Search Only**: Random/Bayesian 없음
2. **Small Grid**: 파라미터 범위 제한적
3. **Single Metric**: positive_net_edge_rate만 최적화

### v2 개선 방향 (D205-8+)
1. **Random/Bayesian Search**: 더 효율적 탐색
2. **Multi-objective**: Sharpe ratio, drawdown 등 추가
3. **Walk-forward Analysis**: 과적합 방지
4. **Larger Parameter Space**: 더 넓은 범위 탐색

## 의존성

- **Depends on**: D205-5 (Record/Replay SSOT) ✅, D205-6 (ExecutionQuality v1) ✅
- **Blocks**: D205-8 (Advanced Tuning / Walk-forward)

## 다음 단계

- **D205-8**: Walk-forward Analysis + Random Search
- **D206-1**: Grafana Dashboard (선택)
- **D207**: Live Paper 실행 (ExecutionQuality 적용)

---

## 참고 자료

- SSOT: `docs/v2/SSOT_RULES.md`
- ExecutionQuality: `arbitrage/v2/execution_quality/model_v1.py`
- Sweep: `arbitrage/v2/execution_quality/sweep.py`
- Architecture: `docs/v2/V2_ARCHITECTURE.md`
