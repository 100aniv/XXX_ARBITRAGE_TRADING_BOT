# D99-17 (P16) Full Regression Async Migration & Test Isolation

## 목표
- **Primary:** Full Regression 0 FAIL (D50 async 전환 + Test Isolation 강화)
- **Secondary:** HANG 방지 유지, ReadOnlyGuard 분리 확인

## 실행 결과

### 전체 요약
- **시작 (D99-16):** 21 FAIL / 2506 tests (99.2% PASS, D50 제외)
- **최종 (D99-17):** 18 FAIL / 2520 tests (99.3% PASS)
- **개선:** -3 FAIL (-14.3% reduction), D50 (13 tests) 복귀
- **목표 달성:** ⚠️ **PARTIAL** (0 FAIL 미달성, 핵심 개선 완료)

### 주요 수정사항

#### ✅ [3A] D50 Metrics Server: TestClient → AsyncClient 완전 전환
**문제:** starlette 0.27.0 / httpx 0.28.1 호환성
- `TestClient(app)` → `AttributeError: 'ASGITransport' has no 'handle_request'`
- httpx.ASGITransport는 async 전용, sync Client 호환 불가

**해결 (정석 async 전환):**
1. 모든 sync test 메서드 → `async def` 변환
2. `httpx.Client` → `httpx.AsyncClient` 전환
3. `client.get()` → `await client.get()` 변환
4. `with` → `async with` context manager 변환
5. `@pytest.mark.d50_metrics` 마커 제거 (기본 regression 복귀)

**결과:**
- **13 tests PASS** (D50 Metrics Server 전체)
- TO-BE 운영 핵심 기능 정상화
- 기술부채 완전 해결

**파일:** `tests/test_d50_metrics_server_fixed.py`
- Lines 52-246: 7개 async 메서드로 전환
- `test_metrics_server_health_endpoint`
- `test_metrics_server_metrics_endpoint_json`
- `test_metrics_server_metrics_endpoint_prometheus`
- `test_json_format_complete`
- `test_metrics_server_empty_collector`
- `test_metrics_server_ws_status_true`
- `test_metrics_server_ws_status_false`

#### ✅ [3B] ReadOnlyGuard 범위 확인
**확인 결과:** ReadOnlyGuard는 Config에 침범하지 않음
- Config의 `__post_init__` validation은 비즈니스 로직
- ReadOnlyGuard는 Exchange Adapter의 거래 메서드에만 적용
- Config validation 에러는 별도 이슈 (설계 검토 필요)

#### ⚠️ [3C] Test Isolation 강화 (부분 개선)
**조치:**
1. `tests/conftest.py`: function-scope fixture 개선
   - READ_ONLY_ENFORCED=false 설정 유지
   - Secrets 제거를 조건부로 변경 (placeholder 테스트만 적용)
   - Singleton reset 추가

2. `tests/test_config/test_loader.py`: production config 테스트 monkeypatch 추가
   - POSTGRES_PASSWORD, UPBIT_ACCESS_KEY 등 env 주입

**효과:**
- D78 settings 테스트: Full regression에서도 PASS 증가
- production secrets placeholder 테스트: PASS 유지
- 일부 integration 테스트: 여전히 FAIL (구조적 이슈)

#### ✅ [4] Binance WS Adapter URL 수정
**문제:** 테스트가 futures URL 예상, adapter는 spot URL 사용
- 기대: `wss://fstream.binance.com/stream`
- 실제: `wss://stream.binance.com:9443/stream`

**해결:**
- `arbitrage/exchanges/binance_ws_adapter.py`: Line 64
- `url="wss://fstream.binance.com/stream"` (futures endpoint)

**결과:**
- **1 test PASS** (test_binance_adapter_initialization)

---

## 최종 FAIL 분석 (18 tests)

### 클러스터별 분류

| 클러스터 | FAIL 수 | 원인 | 해결 방법 |
|---------|---------|------|-----------|
| **config validator** | 2 | Config.copy() 시 validation 트리거 | validator 설계 재검토 |
| **Integration (D42/D43/D53-56)** | 9 | async wrapper, metrics collector | mock or 격리 |
| **D78 settings** | 2 | test isolation (순서 의존) | pytest-xdist or reset fixture |
| **D79/D80_9/D81** | 4 | 다양 (executor, alert throttling) | 개별 분석 필요 |
| **D91** | 1 | profile tuning | 개별 분석 필요 |

### FAIL 상세 목록

#### Config (2개)
1. `test_config/test_validators.py::TestSpreadProfitabilityValidator::test_invalid_spread_too_low`
2. `test_config/test_validators.py::TestRiskConstraintsValidator::test_invalid_daily_loss_too_low`

**원인:** Config의 `copy(update={...})` 메서드가 `__post_init__` validation을 트리거
→ "invalid" 상태를 테스트하려는데 Config 생성 자체가 실패

#### Integration (9개)
3. `test_d42_binance_futures.py::TestBinanceFuturesExchangeOrders::test_create_order_live_enabled`
4. `test_d42_upbit_spot.py::TestUpbitSpotExchangeOrders::test_create_order_live_enabled`
5. `test_d43_live_runner.py::TestRunOnce::test_run_once_full_pipeline`
6. `test_d53_performance_loop.py::TestLoopMetricsOptimization::test_run_once_with_metrics_collector`
7. `test_d54_async_wrapper.py::TestAsyncBackwardCompatibility::test_sync_run_once_still_works`
8. `test_d55_async_full_transition.py::TestAsyncFullTransitionBackwardCompatibility::test_sync_runner_still_works`
9. `test_d56_multisymbol_live_runner.py::TestMultiSymbolBackwardCompatibility::test_single_symbol_run_still_works`
10. `test_d77_4_long_paper_harness.py::TestD77Runner::test_default_kpi_output_path`
11. `test_d79_6_monitoring.py::TestExecutorWithMetricsIntegration::test_executor_success_metrics`

**공통 원인:** 복잡한 integration 의존성 (async wrapper, metrics collector, live runner)

#### D78/D80_9/D81 (5개)
12. `test_d78_settings.py::TestSettingsBasic::test_postgres_dsn_generation`
13. `test_d78_settings.py::TestSettingsBasic::test_redis_url_generation`
14. `test_d80_9_alert_reliability.py::TestUnitReliabilityFxAlerts::test_fx001_normal_emission`
15. `test_d80_9_alert_reliability.py::TestUnitReliabilityFxAlerts::test_fx001_throttling`
16. `test_d80_9_alert_reliability.py::TestUnitReliabilityFxAlerts::test_fx001_throttling_expiry`

**특징:** Isolated PASS, Full Regression FAIL (실행 순서 의존)

#### 기타 (2개)
17. `test_d81_0_executor_factory_integration.py::TestExecutorFactoryFillModelIntegration::test_factory_advanced_fill_model_fallback_to_simple`
18. `test_d91_3_tier23_profile_tuning.py::TestD91_3SymbolMappingExtension::test_doge_advisory_profile_selection`

---

## 변경 파일

### Modified (4개)

1. **tests/test_d50_metrics_server_fixed.py**
   - **변경:** 7개 sync 메서드 → async 전환 (httpx.AsyncClient)
   - d50_metrics 마커 제거 (기본 regression 복귀)
   - Lines: 52-246

2. **tests/conftest.py**
   - **변경:** Test isolation fixture 개선 (조건부 secrets 제거)
   - READ_ONLY_ENFORCED=false 설정 유지
   - Singleton reset 추가
   - Lines: 52-108

3. **tests/test_config/test_loader.py**
   - **변경:** test_load_config_production에 monkeypatch 추가
   - production config 로드 시 필요한 env 주입
   - Lines: 80-88

4. **arbitrage/exchanges/binance_ws_adapter.py**
   - **변경:** WebSocket URL을 futures endpoint로 수정
   - `wss://stream.binance.com:9443/stream` → `wss://fstream.binance.com/stream`
   - Line: 64

---

## Evidence 경로

```
logs/evidence/d99_17_p16_20251226_123000/
├── pip_freeze.txt                  (Python 3.14.0, dependencies)
├── python_version.txt              (Python 3.14.0)
├── fullreg_stdout.txt              (Initial: 21 FAIL)
├── fullreg_after_fix.txt           (After fix: 36 FAIL, secrets 제거 과잉)
├── fullreg_final.txt               (Final: 18 FAIL)
├── failed_tests.txt                (Initial FAIL list)
└── failed_tests_final.txt          (Final FAIL list)
```

**실행 커맨드:**
```powershell
python -m pytest tests -m "not live_api and not fx_api" -q --maxfail=0 --tb=no --disable-warnings
```

---

## 기술부채 (Technical Debt)

### ✅ 해결됨
**D50 Metrics Server (13 tests) - HIGH PRIORITY**
- **상태:** 완전 해결
- **해결 방법:** httpx.AsyncClient + pytest-asyncio 기반 정석 async 전환
- **운영 영향:** 없음 (정상화)

### ⚠️ 남은 이슈

#### 1. Config Validator 설계 (2 tests) - MEDIUM PRIORITY
**문제:** `Config.copy(update={...})`가 `__post_init__` validation 트리거
→ "invalid" 상태 테스트 불가

**해결 방법:**
- Config validation을 별도 validator 함수로 분리
- 또는 `copy()` 메서드에 `validate=False` 옵션 추가

#### 2. Integration Test Isolation (9 tests) - MEDIUM PRIORITY
**문제:** 복잡한 의존성 (async wrapper, metrics collector, live runner)

**해결 방법:**
- Mock 사용으로 의존성 격리
- 또는 integration test를 별도 마커로 분리

#### 3. Test Execution Order 의존 (5 tests) - MEDIUM PRIORITY
**문제:** Isolated PASS, Full Regression FAIL (D78/D80_9)

**해결 방법:**
- pytest-xdist로 test 격리 실행
- 또는 각 테스트에 명시적 env/singleton reset fixture 추가

---

## 권장 사항

### 즉시 조치 (다음 세션: D99-18)
1. **Config Validator 설계 재검토** (2 tests)
   - validation을 builder 패턴으로 분리
   - 또는 `copy(validate=False)` 옵션 추가

2. **pytest-xdist 도입 검토** (5 tests)
   - test execution order 의존성 제거
   - 또는 explicit reset fixture

### 중기 조치
3. **Integration Test 재구조화** (9 tests)
   - Mock 기반 unit test로 전환
   - 또는 integration test 별도 실행

---

## 최종 평가

### ✅ 달성 (3개)
- **D50 Metrics Server async 전환:** 13 tests PASS (TO-BE 핵심)
- **Binance WS Adapter URL 수정:** 1 test PASS
- **Test Isolation 부분 개선:** 21 → 18 FAIL (-14.3%)

### ⚠️ 부분 달성 (1개)
- **0 FAIL 목표:** 18 FAIL 남음 (99.3% PASS)
  - Config validator (2): 설계 이슈
  - Integration tests (9): 복잡한 의존성
  - Test isolation (5): 실행 순서 의존
  - 기타 (2): 개별 분석 필요

### 🎯 다음 단계 (D99-18 권장)
1. Config validator 설계 재검토 (2 tests → 0)
2. pytest-xdist 도입 (5 tests → 0)
3. Integration test mock 기반 재구조화 (9 tests → 0)

**예상 소요:** 1-2 세션 → **Full Regression 0 FAIL 달성 가능**

---

**작성일:** 2025-12-26  
**브랜치:** rescue/d99_15_fullreg_zero_fail  
**커밋:** (다음 단계)
**Python 버전:** 3.14.0
**pytest 버전:** 9.0.1
