# D99-6: Full Regression FAIL Triage (원인군 분류)

**Author:** Windsurf AI  
**Date:** 2025-12-22 ~ 2025-12-23  
**Status:** 🚧 IN PROGRESS (Phase 3 진행 중 - Docker ON SSOT 기준)

---

## Executive Summary

**D99-6 Phase 2 (P1 Fix Pack) 완료 상태:**

**Phase 0 (D99-5 완료 직후):**
- **Total:** 2495 tests
- **Passed:** 2338 (93.5%)
- **Failed:** 126 (5.0%)
- **Skipped:** 31 (1.2%)

**Phase 1 (P0 Fix - 2025-12-22 16:19 KST):**
- **Passed:** 2340 (93.7%) ⬆️ +2
- **Failed:** 124 (5.0%) ⬇️ -2개 감소
- **Duration:** 113.38s
- **P0 Fix:** websocket-client + env vars (conftest)

**Phase 2 (P1 Fix - 2025-12-22 18:45 KST):**
- **Passed:** 2352 (94.3%) ⬆️ +12
- **Failed:** 112 (4.5%) ⬇️ **-12개 감소**
- **Skipped:** 31 (1.2%)
- **Duration:** 108.85s (1분 48초)
- **P1 Fix:**
  1. ✅ SimulatedExchange.connect/disconnect/get_balance/get_ticker 추가
  2. ✅ CrossExchangeRiskGuard._check_cross_sync_rules(adjusted_config) 시그니처 수정
  3. ✅ CrossExchangeExecutor.__init__(integration, enable_rollback) 백워드 호환

**누적 감소:** 126 → 112 (14개 감소, 11.1%)

**Phase 3 (P3 Fix - 2025-12-23 00:03 KST, Docker ON SSOT):**
- **Baseline:** 119 FAIL (Docker ON 상태에서 재측정)
- **Passed:** 2358 (94.6%) ⬆️ +6
- **Failed:** 106 (4.2%) ⬇️ **-13개 감소**
- **Skipped:** 31 (1.2%)
- **Duration:** 212.94s (3분 32초)
- **P3 Fix:**
  1. ✅ TelegramNotifier.is_available() - 빈 문자열 처리 로직 수정 (-1)
  2. ✅ SimulatedExchange.get_ticker() - Price 객체 반환 추가 (-9)
  3. ✅ Order 생성자 - exchange, created_at, updated_at 파라미터 수정 (-3)

**누적 감소 (P0+P1+P3):** 119 → 106 (13개 감소, 10.9%)

**D99-6 목표:** 119 → 99 이하 (-20 이상) | **현재 진행률: 65% (13/20)**

---

## FAIL 원인군 분류 (Triage)

### 원인군 1: 환경변수/시크릿 누락 (Priority: P0)

**특징:** `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `BINANCE_SECRET_KEY` 등 환경변수 누락

**대표 에러:**
```
config.base.ConfigError: Production requires POSTGRES_PASSWORD environment variable
```

**영향 범위:**
- test_config/ (환경 설정 관련 테스트)
- test_d29_k8s_orchestrator.py (K8s 설정)
- 기타 Production 환경 테스트

**추정 FAIL 개수:** 15~20개

**수정 우선순위:** **HIGH** (환경 설정은 기본)

**다음 액션:**
1. `config/loader.py` 검토 (환경변수 기본값 설정)
2. `.env.example` 생성 (필수 환경변수 명시)
3. CI/CD 환경변수 설정 (GitHub Actions secrets)

---

### 원인군 2: 의존성 누락 (Priority: P0) - ✅ FIXED (Phase 1)

**특징:** `yaml`, `pyyaml` 등 필수 패키지 미설치

**대표 에러:**
```
ModuleNotFoundError: No module named 'yaml'
```

**영향 범위:**
- test_d29_k8s_orchestrator.py (yaml 파싱)
- K8s 관련 테스트

**추정 FAIL 개수:** 5~10개

**수정 우선순위:** **HIGH** (의존성은 requirements.txt에 명시)

**다음 액션:**
1. `requirements.txt` 검토 (pyyaml 추가)
2. `pip install -r requirements.txt` 재실행
3. `pip check` 검증

---

### 원인군 3: 인터페이스/메서드 누락 (Priority: P1) - ⚠️ PARTIAL (Phase 2)

**특징:** 클래스/객체에 필요한 메서드가 없음 (예: `connect()`, `copy()`)

**대표 에러:**
```
AttributeError: 'SimulatedExchange' object has no attribute 'connect'
AttributeError: 'ArbitrageConfig' object has no attribute 'copy'
```

**영향 범위:**
- test_d17_paper_engine.py (SimulatedExchange)
- test_config/test_validators.py (ArbitrageConfig)
- test_d29_k8s_orchestrator.py (기타 인터페이스)

**추정 FAIL 개수:** 20~30개

**수정 우선순위:** **HIGH** (코드 구조 문제)

**다음 액션:**
1. `arbitrage/exchanges/simulated.py` 검토 (connect() 메서드 추가)
2. `config/base.py` 검토 (copy() 메서드 추가)
3. 기타 누락된 메서드 확인

---

### 원인군 4: 인프라 미기동 (Priority: P1)

**특징:** PostgreSQL, Redis 등 외부 서비스 미연결

**대표 에러:**
```
psycopg2.OperationalError: could not connect to server
redis.exceptions.ConnectionError: Connection refused
```

**영향 범위:**
- test_d50_metrics_server.py (Redis/Postgres)
- test_d79_* (모니터링 관련)
- test_d80_* (통합 테스트)

**추정 FAIL 개수:** 30~40개

**수정 우선순위:** **MEDIUM** (인프라 설정은 별도 단계)

**다음 액션:**
1. Docker Compose 상태 확인 (`docker-compose ps`)
2. Redis/Postgres 초기화 (`FLUSHALL`, 스키마 생성)
3. 테스트 전 인프라 상태 체크 스크립트 추가

---

### 원인군 5: 진짜 회귀 (Regression) (Priority: P2)

**특징:** 코드 변경으로 인한 실제 기능 손상

**대표 에러:**
```
AssertionError: assert False
ValueError: [구체적 비즈니스 로직 에러]
```

**영향 범위:**
- test_d87_* (Fill Model - D99-3에서 일부 수정)
- test_d89_0_zone_preference.py (D87-4 복원 부작용)
- test_d91_* (Tier 프로파일)
- test_d98_* (ReadOnly Guard)

**추정 FAIL 개수:** 40~50개

**수정 우선순위:** **MEDIUM** (비즈니스 로직 검토 필요)

**다음 액션:**
1. 각 FAIL 테스트 개별 실행 (재현 확인)
2. 최근 커밋 로그 검토 (변경 범위 파악)
3. 단위 테스트 → 통합 테스트 순서로 디버깅

---

## Top 3 원인군 FIX 계획

### Phase 1: 환경변수/의존성 (원인군 1, 2)

**목표:** 20~30개 FAIL 해결

**작업:**
1. `requirements.txt` 업데이트 (pyyaml 추가)
2. `config/loader.py` 기본값 설정
3. `.env.example` 생성
4. `pip install -r requirements.txt` 재실행

**예상 소요 시간:** 30분

**검증:**
```bash
abt_bot_env\Scripts\python.exe -m pytest tests/test_config/ -v
abt_bot_env\Scripts\python.exe -m pytest tests/test_d29_k8s_orchestrator.py -v
```

---

### Phase 2: 인터페이스/메서드 (원인군 3)

**목표:** 20~30개 FAIL 해결

**작업:**
1. `arbitrage/exchanges/simulated.py` → `connect()` 메서드 추가
2. `config/base.py` → `copy()` 메서드 추가
3. 기타 누락된 메서드 확인 및 추가

**예상 소요 시간:** 1시간

**검증:**
```bash
abt_bot_env\Scripts\python.exe -m pytest tests/test_d17_paper_engine.py -v
abt_bot_env\Scripts\python.exe -m pytest tests/test_config/test_validators.py -v
```

---

### Phase 3: 인프라 미기동 (원인군 4)

**목표:** 30~40개 FAIL 해결

**작업:**
1. Docker Compose 상태 확인 및 시작
2. Redis/Postgres 초기화
3. 테스트 전 인프라 체크 스크립트 추가

**예상 소요 시간:** 1시간

**검증:**
```bash
docker-compose ps
abt_bot_env\Scripts\python.exe -m pytest tests/test_d50_metrics_server.py -v
```

---

## 나머지 원인군 (Phase 4+)

### 원인군 5: 진짜 회귀 (40~50개)

**상태:** 다음 세션 범위

**이유:**
- 개별 테스트 재현 필요
- 비즈니스 로직 검토 필요
- 커밋 히스토리 분석 필요

---

## Evidence Path

**D99-6 증거 폴더:**
```
docs/D99/evidence/d99_6_fail_triage_20251222_HHMM/
├── step0_fail_list.txt (126개 FAIL 목록)
├── step1_env_var_fix.txt (원인군 1 FIX 결과)
├── step2_dependency_fix.txt (원인군 2 FIX 결과)
├── step3_interface_fix.txt (원인군 3 FIX 결과)
├── step4_infra_fix.txt (원인군 4 FIX 결과)
└── step5_full_regression_rerun.txt (재실행 결과)
```

---

## AC (Acceptance Criteria)

| AC | 목표 | 상태 | 세부사항 |
|----|------|------|---------|
| AC-1 | FAIL 원인군 분류 | ✅ PASS | 5개 원인군 분류 완료 |
| AC-2 | Top 3 원인군 FIX | ⏳ IN PROGRESS | 환경변수/의존성/인터페이스 |
| AC-3 | Full Regression 재실행 | ⏳ PENDING | 126 FAIL → 감소 검증 |
| AC-4 | 문서 동기화 | ⏳ PENDING | D99_REPORT/CHECKPOINT/ROADMAP |
| AC-5 | Git commit + push | ⏳ PENDING | D99-6 완료 후 |

---

## Next Steps

1. **Phase 1 FIX:** 환경변수/의존성 (30분)
2. **Phase 2 FIX:** 인터페이스/메서드 (1시간)
3. **Phase 3 FIX:** 인프라 미기동 (1시간)
4. **Full Regression 재실행:** 126 FAIL → 감소 검증
5. **문서 동기화 + Git commit**

---

## 참고: FAIL 분류 상세 (로그 기반)

### 환경변수 누락 (15개 추정)
- test_config/test_environments.py
- test_config/test_loader.py
- test_d29_k8s_orchestrator.py

### 의존성 누락 (5개 추정)
- test_d29_k8s_orchestrator.py (yaml)

### 인터페이스 누락 (25개 추정)
- test_d17_paper_engine.py (SimulatedExchange.connect)
- test_d17_simulated_exchange.py (SimulatedExchange.connect)
- test_config/test_validators.py (ArbitrageConfig.copy)

### 인프라 미기동 (35개 추정)
- test_d50_metrics_server.py (13개)
- test_d79_6_monitoring.py (다수)
- test_d80_* (다수)

### 진짜 회귀 (46개 추정)
- test_d89_0_zone_preference.py (4개)
- test_d91_3_tier23_profile_tuning.py (다수)
- test_d98_2_integration_readonly.py (다수)
- 기타 통합 테스트
