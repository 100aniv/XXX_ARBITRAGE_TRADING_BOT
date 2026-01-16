# V2 마이그레이션 전략

**작성일:** 2025-12-29  
**목적:** V1 기능/인프라를 V2로 가져오는 방식을 2레벨로 정리

---

## 🎯 마이그레이션 원칙

1. **점진적 전환**: V1과 V2 공존 기간 허용 (D200~D205)
2. **기능 우선순위**: 핵심 기능 먼저, 편의 기능 나중
3. **무정지 원칙**: V1 동작 중단 금지
4. **검증 강제**: V2 기능 활성화 전 100% 테스트 필수
5. **롤백 가능**: 문제 시 V1 복귀 가능 상태 유지

---

## 📊 마이그레이션 레벨 정의

### 🟢 Level 1: 즉시 재사용 (바로 연결)
- V1 코드/인프라를 수정 없이 또는 최소 수정으로 V2에서 직접 사용
- V2 Phase 1 (D200~D201)에서 완료

### 🟡 Level 2: 레퍼런스만 (문서/코드 참조)
- V1 코드를 직접 사용하지 않고, 설계/로직만 참조하여 V2에서 재작성
- V2 Phase 2~3 (D202~D205)에서 진행

### 🔴 Level 3: 폐기 (사용 안 함)
- V2에서 사용하지 않음
- 사유와 함께 문서화하여 보관

---

## 🗂️ 도메인별 마이그레이션 전략

### 1️⃣ 인프라 (Docker/DB/Redis/모니터링)

#### 🟢 Level 1: 즉시 재사용

**PostgreSQL + TimescaleDB**
- **V1 경로:** `infra/docker-compose.yml` (line 40-78)
- **V2 활용:**
  - Trade history 저장 (v2_trades 테이블)
  - PnL aggregation (v2_pnl_daily, v2_pnl_weekly, v2_pnl_monthly)
  - TimescaleDB hypertable로 시계열 최적화
- **마이그레이션 작업:**
  1. `db/migrations/v2_schema.sql` 생성
  2. V2 테이블 생성 (V1 테이블과 분리)
  3. Engine에서 DB connection 설정
- **완료 시기:** D200-1 (이번 턴)
- **검증:** pytest로 DB 연결 테스트

**Redis**
- **V1 경로:** `infra/docker-compose.yml` (line 83-115)
- **V2 활용:**
  - Market data cache (TTL 100ms)
  - Engine state 저장
  - Rate limiting 카운터
- **마이그레이션 작업:**
  1. 포트 통일 (6380 호스트, 6379 컨테이너)
  2. V2 key prefix 추가 (`v2:market:`, `v2:state:`)
  3. Adapter에서 Redis 연결
- **완료 시기:** D202-1 (MarketData)
- **검증:** Redis PING 테스트

**Prometheus + Grafana**
- **V1 경로:** `infra/docker-compose.yml` (line 412-467)
- **V2 활용:**
  - Engine cycle latency 수집
  - Adapter execution time 추적
  - PnL metrics 시각화
- **마이그레이션 작업:**
  1. `monitoring/prometheus/prometheus.v2.yml` 생성
  2. V2 exporter 엔드포인트 추가 (`/metrics`)
  3. Grafana dashboard `v2_overview.json` 생성
- **완료 시기:** D205-2 (Reporting)
- **검증:** Prometheus scraping 확인

---

#### 🔴 Level 3: 폐기

**V1 Live Loop**
- **V1 경로:** `arbitrage/live_loop.py`, `arbitrage/live_runner.py`
- **사유:** V1 아키텍처 의존, V2 Engine과 호환 불가
- **대체:** `arbitrage.v2.core.engine.ArbitrageEngine`
- **보관:** docs/v1/ 참조용

**Paper Trader (D18)**
- **V1 경로:** `arbitrage/paper_trader.py`
- **사유:** V1 전용, V2는 Harness 통합
- **대체:** `arbitrage.v2.harness.smoke_runner.SmokeRunner`
- **보관:** docs/v1/ 참조용

**Dashboard (FastAPI + WebSocket)**
- **V1 경로:** `dashboard/server.py`, `api/server.py`
- **사유:** V1 전용 API, V2는 Grafana 우선
- **대체:** D205-2에서 Grafana 대시보드
- **보관:** FastAPI는 나중에 재검토 (DEFER)

---

### 2️⃣ 거래소 어댑터

#### 🟡 Level 2: 레퍼런스만

**Upbit Spot Adapter**
- **V1 경로:** `arbitrage/exchanges/upbit_spot.py`
- **V2 참조 항목:**
  - MARKET 주문 규약 (BUY=price, SELL=volume)
  - Symbol 변환 (BTC/KRW → KRW-BTC)
  - Rate limiting 로직
  - Error handling 패턴
- **V2 재작성:**
  - `arbitrage/v2/adapters/upbit_adapter.py` (✅ 이미 생성됨)
  - OrderIntent 기반 translate_intent()
  - Mock mode 기본값
- **완료 시기:** D201-2
- **검증:** test_upbit_adapter.py (payload 검증)

**Binance Futures Adapter**
- **V1 경로:** `arbitrage/exchanges/binance_futures.py`
- **V2 참조 항목:**
  - MARKET 주문 규약 (quantity)
  - Symbol 변환 (BTC/USDT)
  - Position management
  - Leverage 설정
- **V2 재작성:**
  - `arbitrage/v2/adapters/binance_adapter.py` (신규 생성 예정)
  - OrderIntent 기반 translate_intent()
  - Mock mode 기본값
- **완료 시기:** D201-3
- **검증:** test_binance_adapter.py (payload 검증)

---

#### 🔴 Level 3: 폐기

**Simulated Exchange**
- **V1 경로:** `arbitrage/exchanges/simulated_exchange.py`
- **사유:** V1 paper mode 전용
- **대체:** `arbitrage.v2.adapters.mock_adapter.MockAdapter`
- **보관:** V1 테스트 참조용

---

### 3️⃣ 마켓 데이터

#### 🟡 Level 2: 레퍼런스만

**REST API Collector**
- **V1 경로:** `refer/rest_collector.py`
- **V2 참조 항목:**
  - Upbit/Binance REST API 호출 패턴
  - Rate limiting 처리
  - Error retry 로직
- **V2 재작성:**
  - `arbitrage/v2/market_data/rest_provider.py` (신규 생성 예정)
  - Adapter와 분리된 독립 모듈
  - Cache 통합 (Redis)
- **완료 시기:** D202-1
- **검증:** test_rest_provider.py

**WebSocket L2 Provider**
- **V1 경로:** `arbitrage/exchanges/upbit_l2_ws_provider.py`, `binance_l2_ws_provider.py`
- **V2 참조 항목:**
  - WebSocket 연결 관리
  - Reconnect 로직
  - L2 orderbook parsing
- **V2 재작성:**
  - `arbitrage/v2/market_data/ws_provider.py` (신규 생성 예정)
  - 멀티 거래소 통합
  - Health check 추가
- **완료 시기:** D202-2
- **검증:** test_ws_provider.py (연결/재연결 시나리오)

---

### 4️⃣ Strategy & Execution

#### 🟡 Level 2: 레퍼런스만

**ArbitrageCore (D37 MVP)**
- **V1 경로:** `arbitrage/arbitrage_core.py`
- **V2 참조 항목:**
  - Fee/Slippage 계산 로직
  - Break-even spread 공식
  - PnL 계산
- **V2 재작성:**
  - `arbitrage/v2/strategy/opportunity_detector.py` (신규 생성 예정)
  - Config 기반 threshold 설정
  - Fee model 분리
- **완료 시기:** D203-1
- **검증:** test_opportunity_detector.py (수식 검증)

**CrossExchangeExecutor**
- **V1 경로:** `arbitrage/cross_exchange/executor.py`
- **V2 참조 항목:**
  - 양방향 주문 실행 로직
  - Rollback 처리
  - Latency 측정
- **V2 재작성:**
  - `arbitrage/v2/execution/executor.py` (신규 생성 예정)
  - OrderIntent 기반 실행
  - Adapter 호출 표준화
- **완료 시기:** D204-1
- **검증:** test_executor.py (mock adapter)

---

#### 🔴 Level 3: 폐기

**Zone Preference (D87/D89)**
- **V1 경로:** `arbitrage/cross_exchange/zone_preference.py`
- **사유:** V2에서 단순화, 불필요한 복잡도
- **대체:** Config에서 threshold 단순 설정
- **보관:** 복잡한 전략 재검토 시 참조

**Duration Guard (D87-3)**
- **V1 경로:** `arbitrage/alerting/duration_guard.py`
- **사유:** V2는 Engine cycle 기반, 불필요
- **대체:** Engine health check로 대체
- **보관:** docs/v1/ 참조

---

### 5️⃣ Risk & Safety

#### 🟡 Level 2: 레퍼런스만

**RiskGuard (D79)**
- **V1 경로:** `arbitrage/cross_exchange/risk_guard.py`
- **V2 참조 항목:**
  - Daily loss limit 체크
  - Max position size 검증
  - Cooldown 로직
- **V2 재작성:**
  - `arbitrage/v2/safety/risk_guard.py` (신규 생성 예정)
  - Config 기반 limits
  - Engine 레벨 통합
- **완료 시기:** D204-2
- **검증:** test_risk_guard.py (limit 초과 시나리오)

**LiveGuard**
- **V1 경로:** `liveguard/safety.py`, `liveguard/risk_limits.py`
- **V2 참조 항목:**
  - Preflight checks
  - Real-time monitoring
  - Emergency stop
- **V2 재작성:**
  - V2는 READ_ONLY 강제, LIVE는 D206+ 이후
  - LiveGuard는 DEFER (LIVE 준비 시 재검토)
- **완료 시기:** D206+ (DEFER)

---

### 6️⃣ 모니터링 & 알림

#### 🟢 Level 1: 즉시 재사용

**Prometheus Textfile Collector**
- **V1 경로:** `monitoring/textfile-collector/preflight.prom`
- **V2 활용:**
  - V2 preflight 결과를 `.prom` 포맷으로 저장
  - Node Exporter가 수집
- **마이그레이션 작업:**
  1. V2 preflight 결과를 `v2_preflight.prom`에 저장
  2. Prometheus scrape config 추가
- **완료 시기:** D200-2
- **검증:** Prometheus에서 메트릭 조회

---

#### 🟡 Level 2: 레퍼런스만

**Alert Manager (D80-9)**
- **V1 경로:** `arbitrage/alerting/aggregator.py`
- **V2 참조 항목:**
  - Alert 우선순위 (P0~P3)
  - Alert routing 로직
  - Telegram 알림
- **V2 재작성:**
  - V2는 로깅 우선, 알림은 D205+ 이후
  - Alert는 DEFER
- **완료 시기:** D205+ (DEFER)

---

### 7️⃣ Config & Secrets

#### 🟢 Level 1: 즉시 재사용

**환경 변수 구조**
- **V1 경로:** `.env.paper`, `.env.live`, `.env.example`
- **V2 활용:**
  - API Keys 저장 구조 재사용
  - DB/Redis 접속 정보
- **마이그레이션 작업:**
  1. `.env.v2.example` 생성 (V2 전용 템플릿)
  2. V2 필요 변수만 포함
  3. .gitignore 확인
- **완료 시기:** D200-1 (이번 턴)
- **검증:** load_dotenv() 테스트

---

#### 🟡 Level 2: 레퍼런스만

**YAML Config 구조**
- **V1 경로:** `config/base.yml`, `configs/*.yaml`
- **V2 참조 항목:**
  - Exchange 설정 구조
  - Strategy 파라미터 패턴
- **V2 재작성:**
  - `config/v2/config.yml` (신규 생성)
  - Dataclass 기반 validation
- **완료 시기:** D200-1 (이번 턴)
- **검증:** test_v2_config.py

---

### 8️⃣ 테스트 & 하네스

#### 🟡 Level 2: 레퍼런스만

**D98 Preflight Tests**
- **V1 경로:** `tests/test_d98_preflight.py`
- **V2 참조 항목:**
  - Preflight check 패턴
  - Gate 검증 로직
- **V2 재작성:**
  - `tests/test_v2_preflight.py` (신규 생성 예정)
  - V2 컴포넌트 검증
- **완료 시기:** D200-2
- **검증:** Gate 실행 시 자동 검증

**Paper Test Harness**
- **V1 경로:** `scripts/run_d64_paper_test.py` 등
- **V2 참조 항목:**
  - 테스트 duration 설정
  - KPI 수집 패턴
  - Evidence 저장 구조
- **V2 재작성:**
  - `arbitrage/v2/harness/paper_runner.py` (신규 생성 예정)
  - SmokeRunner 확장
  - 표준 evidence 포맷
- **완료 시기:** D204-1
- **검증:** 20m smoke test

---

## 📅 마이그레이션 타임라인

### Phase 1: Foundation (D200~D205)
- **D200-1 (현재):**
  - ✅ SSOT 확정
  - ✅ Config SSOT 생성
  - ✅ .env.v2.example 생성
  - ✅ 인프라 SSOT 확정 (infra/docker-compose.yml)

- **D200-2:**
  - ⏳ V2 Harness 표준화
  - ⏳ Evidence 포맷 SSOT
  - ⏳ Preflight v2 테스트

- **D201-1:**
  - ⏳ Adapter Contract Tests
  - ⏳ OrderIntent validation

- **D201-2/D201-3:**
  - ⏳ UpbitAdapter / BinanceAdapter 완성
  - ⏳ Payload 검증 100% PASS

- **D202-1:**
  - ⏳ REST MarketData Provider
  - ⏳ Redis cache 통합

- **D202-2:**
  - ⏳ WebSocket Provider
  - ⏳ L2 orderbook 통합

- **D203-1:**
  - ⏳ Opportunity Detector
  - ⏳ Fee/Slippage 공식 검증

- **D203-2:**
  - ⏳ Backtest/Paper gate 기준

- **D204-1/D204-2:**
  - ⏳ Executor 구현
  - ⏳ Risk Guard 통합
  - ⏳ 20m/1h smoke tests

- **D205-1~12:**
  - ⏳ PnL SSOT schema
  - ⏳ Profit Loop (측정/튜닝/검증)
  - ⏳ Admin Control (제어 인터페이스)
  - ⏳ 현실적 KPI 검증 (winrate 50~80%, edge > 0)

### Phase 2: Engine Intelligence (D206~D213)
- **D206:** 엔진 내재화 (V1 도메인 모델 통합, 수익 로직 이식)
- **D207:** 리스크 제어 (RiskGuard, Position Manager)
- **D208:** Safe Launch (Preflight, 운영 프로토콜)
- **D209:** LIVE 설계 (Adapter, 제어 인터페이스, Runbook)
- **D210:** V1 인프라 재사용
- **D211:** V1 전략 로직 완전 이식
- **D212:** Safe Launch 검증
- **D213:** LIVE 설계 검증

**의사결정 포인트 (D209 완료 후):**
- **Fast Track:** D209 완료 → D220+ LIVE (Phase 3 스킵)
- **Commercial Track:** D209 완료 → D214~D219 (상용급 강화) → D220+ LIVE

### Phase 3: HFT & Commercial Readiness (D214~D219)
- **D214:** HFT 알파 모델 (OBI, Avellaneda-Stoikov)
- **D215:** Backtesting/Replay 엔진
- **D216:** Multi-Symbol 동시 실행
- **D217:** HFT Latency Optimization
- **D218:** Admin UI/UX Dashboard
- **D219:** ML-based Parameter Optimization

### Phase 4: LIVE Deployment (D220+)
- D209 (LIVE 설계) 완료 후 즉시 진행 가능
- Phase 3 (D214~D219) 완료 여부 무관

---

## 🎯 마이그레이션 성공 기준

### ✅ Phase 1 완료 조건
- [ ] Config SSOT 생성 + validation 테스트 PASS
- [ ] .env.v2.example 생성 + gitignore 확인
- [ ] Adapter payload 검증 100% PASS
- [ ] Gate (doctor/fast/regression) 100% PASS
- [ ] MarketData REST/WS 통합
- [ ] Opportunity detection 수식 검증
- [ ] 20m smoke test PASS
- [ ] 1h paper test PASS
- [ ] Profit Loop (측정/튜닝/검증) 완료
- [ ] Admin Control (제어 인터페이스) 완료
- [ ] 현실적 KPI 검증 (winrate 50~80%, edge > 0)

### ✅ Phase 2 완료 조건
- [ ] V1 도메인 모델 통합 (D206)
- [ ] 리스크 제어 구현 (D207)
- [ ] Safe Launch 완료 (D208)
- [ ] LIVE 설계 완료 (D209)
- [ ] V1 인프라 재사용 (D210)
- [ ] V1 전략 로직 완전 이식 (D211)
- [ ] Safe Launch 검증 (D212)
- [ ] LIVE 설계 검증 (D213)
- [ ] Gate (doctor/fast/regression) 100% PASS

### ✅ Phase 3 완료 조건 (선택적)
- [ ] HFT 알파 모델 (D214)
- [ ] Backtesting 엔진 (D215)
- [ ] Multi-Symbol 실행 (D216)
- [ ] Latency Optimization (D217)
- [ ] Admin UI (D218)
- [ ] ML Optimization (D219)

### ✅ Phase 4 완료 조건
- [ ] LIVE Adapter 구현 (D220)
- [ ] LIVE Gate Unlock (D221)
- [ ] LIVE Pilot (D222)
- [ ] LIVE Scale-up (D223)

---

## 🚨 마이그레이션 리스크 & 대응

### 리스크 1: V1/V2 인터페이스 불일치
- **증상:** V1 코드 참조 시 V2 인터페이스와 맞지 않음
- **대응:** V2_ARCHITECTURE.md에 계약 명확히 정의 + 테스트로 강제

### 리스크 2: Config/Secrets 누락
- **증상:** V2 실행 시 환경 변수 누락 에러
- **대응:** .env.v2.example을 완전하게 작성 + validation 테스트

### 리스크 3: 인프라 중복
- **증상:** docker/와 infra/에 docker-compose.yml 중복
- **대응:** infra/를 SSOT로 확정 + docker/ 보관 또는 삭제

### 리스크 4: Phase 3을 필수 게이트로 오독
- **증상:** D209 완료 후에도 D214~D219를 반드시 수행해야 한다고 오인
- **대응:** D_ROADMAP.md에 "의사결정 포인트" 명시 + SSOT_RULES.md에 Fast/Commercial Track 분리

### 리스크 4: V1 코드 직접 import
- **증상:** V2 코드에서 `from arbitrage.live_runner import ...` 등
- **대응:** Import 금지 규칙 SSOT_RULES.md에 명시 + lint 검증

---

## 📚 참조 문서

- **인프라 인벤토리:** `docs/v2/design/INFRA_REUSE_INVENTORY.md`
- **SSOT 맵:** `docs/v2/design/SSOT_MAP.md`
- **V2 아키텍처:** `docs/v2/V2_ARCHITECTURE.md`
- **V2 규칙:** `docs/v2/SSOT_RULES.md`
- **로드맵:** `docs/D_ROADMAP.md`

---

**결론:** V1→V2 마이그레이션은 "즉시 재사용 (11개) + 레퍼런스 (13개) + 폐기 (6개)" 3단계 전략. Phase 1~4 (D200~D206)에 걸쳐 점진적 전환.
