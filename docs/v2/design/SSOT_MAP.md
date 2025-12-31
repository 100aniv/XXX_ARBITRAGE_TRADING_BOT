# V2 SSOT 맵 (Single Source of Truth)

**작성일:** 2025-12-29  
**목적:** V2 개발/운영에서 참조할 SSOT를 도메인별로 1개씩 확정

---

## 📜 SSOT 원칙

1. **1 도메인 = 1 SSOT**: 같은 정보를 여러 곳에 중복 저장 금지
   - **예외:** `.windsurfrule`에는 Step0 부트스트랩(읽을 문서/순서/충돌 시 중단)만 허용
   - 나머지 SSOT 정의/상세는 `SSOT_MAP.md`, `SSOT_RULES.md`가 유일 SSOT
2. **SSOT 변경 시 전파**: SSOT 수정 후 참조 문서 동기화 필수
3. **SSOT 위치 명확화**: 모든 팀원이 SSOT 위치를 알아야 함
4. **SSOT 검증**: Gate 테스트로 SSOT 정합성 검증

---

## 🗺️ 도메인별 SSOT 정의 (7종 필수)

**필수 SSOT 7종:**
1. Process SSOT - `D_ROADMAP.md`
2. Runtime Config SSOT - `config/v2/config.yml`
3. Secrets SSOT - `.env.v2.example` (템플릿), `.env.v2` (실제, gitignore)
4. Data SSOT - `db/migrations/v2_schema.sql`
5. Cache/Locks SSOT - Redis keyspace 규칙
6. Monitoring SSOT - Prometheus/Grafana 설정
7. Evidence SSOT - `logs/evidence/` 규칙

**추가 SSOT (V2 특화):**
- Rulebook SSOT - `docs/v2/SSOT_RULES.md`
- Architecture SSOT - `docs/v2/V2_ARCHITECTURE.md`
- Test SSOT - `pytest.ini`
- Record/Replay SSOT - `docs/v2/design/REPLAY_FORMAT.md` (D205-5)
- ExecutionQuality SSOT - `docs/v2/design/EXECUTION_QUALITY.md` (D205-6)
- Tuning Pipeline SSOT - `docs/v2/design/TUNING_PIPELINE.md` (D205-7)
- Admin Control SSOT - `docs/v2/design/ADMIN_CONTROL.md` (D206-4)

---

### 1️⃣ Process SSOT (프로세스/로드맵)

#### 📄 `D_ROADMAP.md`

**역할:**
- 전체 프로젝트 로드맵 (D1~D206+)
- V1/V2 마일스톤 정의
- Phase별 완료 조건

**주의사항:**
- 로드맵은 D_ROADMAP.md가 유일 SSOT
- 로컬 로드맵 복사본 생성 금지
- 프로젝트 진행 상황은 D_ROADMAP.md에만 기록

---
- 문서 작성 시 (D 번호 인용)

**업데이트 규칙:**
- D200-1 완료 시 → D_ROADMAP.md에 DONE 마크
- 새 Phase 시작 시 → 세부 D 번호 추가
- 변경 시 커밋 메시지에 "[ROADMAP]" 태그

**현재 상태:**
- ✅ D200-0 DONE (V2 Kickoff)
- 🔄 D200-1 IN_PROGRESS (이번 턴)
- ⏳ D201~D206 계획됨

---

### 2️⃣ Rulebook SSOT (개발 규칙)

#### 📄 `docs/v2/SSOT_RULES.md`

**역할:**
- V2 개발 강제 규칙
- GATE 검증 정책
- 파괴적 변경 금지 원칙
- 경로/네임스페이스 규칙

**금지 사항:**
- ❌ SSOT_RULES_V2.1.md 등 버전 분기 금지
- ❌ 개인 규칙 파일 생성 금지
- ❌ .windsurfrule과 중복 금지

**참조자:**
- V2 코드 작성 시 (네임스페이스 확인)
- Gate 실행 전 (doctor/fast/regression)
- 코드 리뷰 시 (규칙 준수 체크)

**업데이트 규칙:**
- 새 규칙 추가 시 → 섹션 추가 + 예시 코드
- 규칙 위반 발견 시 → SSOT_RULES.md 업데이트 + 위반 수정
- 변경 시 커밋 메시지에 "[RULES]" 태그

**현재 상태:**
- ✅ V2 Kickoff 시 생성 (197 lines)
- 🔄 D200-1에서 Runtime Config 규칙 추가 예정

---

### 4️⃣ Data SSOT (데이터베이스 스키마)

#### 📄 `db/migrations/v2_schema.sql`

**역할:**
- V2 전용 DB 스키마 정의
- **SSOT 테이블 (5개):**
  - `v2_orders`: 주문 기록 (Paper/LIVE 모두)
  - `v2_fills`: 체결 기록 (1 order → N fills)
  - `v2_trades`: 차익거래 기록 (Entry → Exit)
  - `v2_ledger`: 원장 기록 (집계용)
  - `v2_pnl_daily`: 일별 PnL 집계 (리포팅용)
- Index, Constraint, View
- Migration 이력 관리

**SSOT 정의:**
- 주문/체결/거래/PnL의 **유일 원천**은 v2_schema.sql이 정의한 테이블
- 다른 저장소(파일, Redis)는 캐시일 뿐, DB가 진실
- 코드에서 직접 CREATE TABLE 실행 절대 금지

**금지 사항:**
- ❌ v2_schema_v2.sql, v2_schema_prod.sql 등 분기 금지
- ❌ 코드에서 직접 CREATE TABLE 실행 금지
- ❌ V1 테이블 직접 수정 금지 (별도 스키마 사용)

**참조자:**
- DB 초기화 시 (migration 실행)
- ORM/Query 작성 시 (스키마 참조)
- PnL 리포팅 시 (집계 쿼리)

**업데이트 규칙:**
- 스키마 변경 시 → 새 migration 파일 생성 (v2_001_add_column.sql)
- 변경 시 커밋 메시지에 "[DB]" 태그
- Rollback script 필수 포함

**현재 상태:**
- ✅ D200-1에서 v2_schema.sql 생성 완료 (265 lines, 5개 테이블)
- 🔄 D204-1에서 본격 활용 (orders/fills/trades CRUD)

---

### 5️⃣ Cache/Locks SSOT (Redis 키스페이스)

#### 📄 `docs/v2/design/REDIS_KEYSPACE.md`

**역할:**
- Redis key 네이밍 규칙: `v2:{env}:{run_id}:{domain}:{key}`
- TTL 정책 (market_data: 100ms, config: 1h)
- Lock prefix: `v2:lock:{resource}`
- Rate limit counter prefix: `v2:ratelimit:{exchange}:{endpoint}`

**금지 사항:**
- ❌ 네이밍 규칙 무시 (v2_prefix 없는 키)
- ❌ 환경별 key 충돌 (dev/prod 격리 필수)
- ❌ TTL 없는 캐시 (메모리 누수)

**참조자:**
- MarketData Provider (캐싱)
- RateLimitManager (카운터)
- Engine (상태 저장)

**업데이트 규칙:**
- 새 keyspace 추가 시 → REDIS_KEYSPACE.md 업데이트
- TTL 변경 시 → 근거 문서화
- 변경 시 커밋 메시지에 "[REDIS]" 태그

**현재 상태:**
- ⏳ D200-1에서 skeleton 생성 예정 (이번 턴)
- 🔄 D202-1에서 MarketData 캐시 구현

---

### 6️⃣ Monitoring SSOT (모니터링 설정)

#### 📄 `monitoring/prometheus/prometheus.v2.yml`

**역할:**
- V2 전용 scrape config
- Metric endpoint 정의 (v2_engine, v2_adapter)
- Alerting rules (latency > 100ms, error rate > 1%)
- Grafana dashboard source: `monitoring/grafana/dashboards/v2_overview.json`

**금지 사항:**
- ❌ prometheus.yml 직접 수정 (v2.yml만 수정)
- ❌ Grafana dashboard를 수동으로만 관리 (JSON 소스 필수)
- ❌ Metric 네이밍 불일치 (v2_ prefix 필수)

**참조자:**
- Engine 초기화 시 (metrics exporter 시작)
- Grafana (dashboard rendering)
- Alertmanager (alert routing)

**업데이트 규칙:**
- 새 metric 추가 시 → prometheus.v2.yml + Grafana dashboard 동시 업데이트
- 변경 시 커밋 메시지에 "[MONITORING]" 태그

**현재 상태:**
- ✅ monitoring/prometheus/prometheus.yml 존재 (V1)
- ⏳ prometheus.v2.yml 생성 예정 (D205-2)

---

### 7️⃣ Evidence SSOT (실행 증거 저장)

#### 📄 `docs/v2/design/EVIDENCE_FORMAT.md`

**역할:**
- Evidence 저장 경로 규칙: `logs/evidence/<run_id>/` (YYYYMMDD_HHMMSS_<d-number>_<short_hash>)
- 필수 산출물: manifest.json, gate.log, git_info.json, cmd_history.txt
- 선택 산출물: kpi_summary.json (Paper), error.log (실패 시)
- 자동 생성 규칙: watchdog/just 실행 시 evidence 자동 생성

**금지 사항:**
- ❌ docs/v2/evidence/ 경로 사용 금지 (logs/evidence/만 사용)
- ❌ 규칙 무시한 임의 경로 저장
- ❌ 민감 정보 포함 (API key, password)
- ❌ 증거 없는 PASS 선언

**참조자:**
- Smoke/Paper Harness (evidence 저장)
- Gate 검증 (evidence 읽기)
- 사후 분석 (KPI 집계)

**업데이트 규칙:**
- 새 evidence 필드 추가 시 → EVIDENCE_FORMAT.md 업데이트 + schema 정의
- 자동 생성 규칙 변경 시 → tools/evidence_pack.py 동시 업데이트
- 변경 시 커밋 메시지에 "[EVIDENCE]" 태그

**현재 상태:**
- ✅ D200-2에서 EVIDENCE_FORMAT.md 생성 (EVIDENCE_SPEC.md는 DEPRECATED)
- ✅ tools/evidence_pack.py 유틸 생성
- 🔄 D205-6 이후 edge_after_cost, slippage_bps 필드 추가 예정

---

### 8️⃣ Record/Replay SSOT (리플레이 기록/재현)

#### 📄 `docs/v2/design/REPLAY_FORMAT.md`

**역할:**
- NDJSON 기록 포맷 정의 (market.ndjson, decisions.ndjson)
- 리플레이 엔진 인터페이스
- 재현성 검증 규칙 (diff = 0)

**금지 사항:**
- ❌ 압축/최적화 포맷 (기본 NDJSON만)
- ❌ 비결정적 로직 (동일 입력 → 동일 출력)
- ❌ 리플레이 없이 파라미터 튜닝 (D205-7 진입 금지)

**참조자:**
- D205-5 (Record/Replay 구현)
- D205-7 (Parameter Sweep - 리플레이 기반 튜닝)
- Gate 테스트 (회귀 검증)

**업데이트 규칙:**
- 새 필드 추가 시 → REPLAY_FORMAT.md 업데이트 + schema 정의
- 포맷 변경 시 → 리플레이 엔진 동기화
- 변경 시 커밋 메시지에 "[REPLAY]" 태그

**현재 상태:**
- ⏳ D205-5에서 생성 예정
- 🔄 market.ndjson/decisions.ndjson 포맷 정의

---

### 9️⃣ ExecutionQuality SSOT (실행 품질 지표)

#### 📄 `docs/v2/design/EXECUTION_QUALITY.md`

**역할:**
- edge_after_cost, slippage_bps, partial_fill_rate 정의
- 가짜 낙관 방지 규칙 (winrate 100% → FAIL)
- latency p50/p95 기준

**금지 사항:**
- ❌ 승률 중심 KPI (edge_after_cost 중심)
- ❌ winrate 100% PASS 처리 (현실 미반영 경고)
- ❌ slippage 모델 없이 체결 가정

**참조자:**
- D205-6 (ExecutionQuality v1 구현)
- D205-9 (현실적 Paper Validation)
- KPICollector (edge_after_cost 필드)

**업데이트 규칙:**
- 새 지표 추가 시 → EXECUTION_QUALITY.md 업데이트
- 가짜 낙관 방지 규칙 변경 시 → SSOT_RULES.md 동기화
- 변경 시 커밋 메시지에 "[EXEC_QUALITY]" 태그

**현재 상태:**
- ⏳ D205-6에서 생성 예정
- 🔄 edge_after_cost 중심 KPI 전환

---

### 🔟 Tuning Pipeline SSOT (파라미터 튜닝)

#### 📄 `docs/v2/design/TUNING_PIPELINE.md`

**역할:**
- Parameter Sweep 포맷 (Random/Grid)
- Pareto frontier 시각화 규칙
- 최적 파라미터 선정 기준

**금지 사항:**
- ❌ 리플레이 없이 튜닝 (D205-5 필수)
- ❌ 수동 파라미터 조정 (자동 sweep 우선)
- ❌ 단일 지표 최적화 (edge_after_cost + trades_count 균형)

**참조자:**
- D205-7 (Parameter Sweep v1)
- 리플레이 엔진 (고속 조합 테스트)
- Grafana (sweep 결과 시각화)

**업데이트 규칙:**
- 새 파라미터 추가 시 → sweep 범위 정의
- 최적화 기준 변경 시 → Pareto frontier 재정의
- 변경 시 커밋 메시지에 "[TUNING]" 태그

**현재 상태:**
- ⏳ D205-7에서 생성 예정
- 🔄 Random/Grid search 기초 구현

---

### 1️⃣1️⃣ Admin Control SSOT (운영자 제어)

#### 📄 `docs/v2/design/ADMIN_CONTROL.md`

**역할:**
- Stop/Pause/Blacklist 인터페이스
- Emergency flatten 규칙 (paper: 포지션 초기화)
- Risk limit override 정책
- Admin 명령 audit log

**금지 사항:**
- ❌ Grafana만으로 제어 (별도 Control 인터페이스 필수)
- ❌ Admin 명령 audit log 누락
- ❌ 재시작 없이 반영 불가능한 설정 (실시간 반영 필수)

**참조자:**
- D206-4 (Admin Control Panel 구현)
- Grafana (button panel)
- Failure Injection (장애 대응 제어)

**업데이트 규칙:**
- 새 제어 기능 추가 시 → ADMIN_CONTROL.md 업데이트
- audit log 포맷 변경 시 → 문서 동기화
- 변경 시 커밋 메시지에 "[ADMIN]" 태그

**현재 상태:**
- ⏳ D206-4에서 생성 예정
- 🔄 최소 제어 기능 (Stop/Pause/Blacklist/Flatten)

---

### 추가 SSOT (V2 특화)

#### Architecture Contract SSOT

##### 📄 `docs/v2/V2_ARCHITECTURE.md`

**역할:**
- Engine-Centric 아키텍처 정의
- OrderIntent/Adapter/Engine 계약
- MARKET 의미 규약 (BUY=quote_amount, SELL=base_qty)
- V1→V2 Migration Path

**금지 사항:**
- ❌ V2_ARCHITECTURE_v2.md 등 버전 분기 금지
- ❌ 아키텍처 변경 시 V2_ARCHITECTURE_NEW.md 생성 금지
- ❌ 코드와 문서 불일치 방치 금지

**참조자:**
- Adapter 구현 시 (인터페이스 확인)
- OrderIntent 생성 시 (규약 준수)
- 코드 리뷰 시 (계약 위반 체크)

**업데이트 규칙:**
- 인터페이스 변경 시 → V2_ARCHITECTURE.md 먼저 수정 + 코드 동기화
- 새 컴포넌트 추가 시 → 계약 섹션 추가
- 변경 시 커밋 메시지에 "[ARCH]" 태그

**현재 상태:**
- ✅ V2 Kickoff 시 생성 (412 lines)
- 🔄 D201-1에서 Adapter Contract Tests 추가 예정

---

### 2️⃣ Runtime Config SSOT (실행 설정)

#### 📄 `config/v2/config.yml`

**역할:**
- 거래소별 설정 (fee, min_order, rate_limit)
- Strategy 파라미터 (threshold, order_size_policy)
- Safety limits (max_daily_loss, max_position)
- Universe 정의 (symbols, allowlist/denylist)

**금지 사항:**
- ❌ config_v2_prod.yml, config_v2_dev.yml 등 환경별 분기 금지
- ❌ 코드에 하드코딩된 설정값 금지
- ❌ Secrets (API key) 포함 금지

**참조자:**
- Engine 초기화 시 (EngineConfig 로드)
- Adapter 생성 시 (거래소 설정 참조)
- Smoke/Paper 테스트 시 (테스트 파라미터)

**업데이트 규칙:**
- 설정 변경 시 → config.yml 수정 + validation 테스트 실행
- 새 파라미터 추가 시 → dataclass 업데이트 + 기본값 설정
- 변경 시 커밋 메시지에 "[CONFIG]" 태그

**현재 상태:**
- ✅ D200-1에서 생성 완료 (155 lines)
- 🔄 D201-2/D201-3에서 거래소 설정 추가 예정

---

### 3️⃣ Secrets SSOT (인증 정보)

#### 📄 `.env.v2.example` (템플릿)
#### 📄 `.env.v2` (실제 값, gitignore)

**역할:**
- API Keys (UPBIT_ACCESS_KEY, BINANCE_API_KEY)
- DB/Redis 비밀번호
- JWT Secret (미래용)

**금지 사항:**
- ❌ config.yml에 API Key 저장 절대 금지
- ❌ 코드에 하드코딩 절대 금지
- ❌ Git에 .env.v2 커밋 절대 금지

**참조자:**
- Adapter 생성 시 (API Key 로드)
- DB/Redis 연결 시 (접속 정보)

**업데이트 규칙:**
- 새 Secret 추가 시 → .env.v2.example에만 추가 (값은 빈 문자열)
- 실제 값은 .env.v2에만 (로컬 환경)
- .gitignore 확인 필수

**현재 상태:**
- ✅ .env.paper, .env.live 존재 (V1)
- ⏳ .env.v2.example 생성 예정 (이번 턴)

---

### 6️⃣ Test SSOT (테스트 전략)

#### 📄 `pytest.ini`

**역할:**
- pytest 설정 (marker, asyncio_mode)
- Test discovery 규칙
- Coverage 설정

**참조자:**
- Gate 실행 시 (doctor/fast/regression)
- 로컬 테스트 실행 시

**업데이트 규칙:**
- 새 marker 추가 시 → pytest.ini 등록
- V2 테스트 경로 추가 시 → testpaths 업데이트

**현재 상태:**
- ✅ V1 설정 존재
- 🔄 V2 marker 추가 예정 (v2_unit, v2_integration)

---

### 7️⃣ Infra SSOT (인프라 설정)

#### 📄 `infra/docker-compose.yml`

**역할:**
- Docker 서비스 정의 (Postgres, Redis, Prometheus, Grafana)
- 포트 매핑
- Volume 설정
- Health check

**금지 사항:**
- ❌ docker-compose.v2.yml 등 분기 금지
- ❌ docker/docker-compose.yml과 중복 금지 (infra/ 버전이 SSOT)

**참조자:**
- 로컬 개발 시 (docker-compose up)
- CI/CD 파이프라인
- 배포 스크립트

**업데이트 규칙:**
- 서비스 추가/변경 시 → infra/docker-compose.yml만 수정
- Health check 변경 시 → 테스트 후 커밋
- 변경 시 커밋 메시지에 "[INFRA]" 태그

**현재 상태:**
- ✅ infra/docker-compose.yml (519 lines)
- ⚠️ docker/docker-compose.yml 중복 존재 (정리 필요)
- 🔄 D200-1에서 SSOT 확정 (infra/ 유지, docker/ 보관)

---

### 8️⃣ Monitoring SSOT (모니터링 설정)

#### 📄 `monitoring/prometheus/prometheus.v2.yml`

**역할:**
- V2 전용 scrape config
- Metric endpoint 정의
- Alert rules

**참조자:**
- Prometheus 컨테이너 (설정 로드)
- Grafana (datasource)

**업데이트 규칙:**
- 새 exporter 추가 시 → scrape config 추가
- 변경 시 Prometheus reload 필요

**현재 상태:**
- ⏳ prometheus.v2.yml 생성 예정 (D200-2)
- ✅ prometheus.yml, prometheus.fx.yml 존재 (V1 참조용)

---

## 📊 SSOT 계층 구조

```
docs/D_ROADMAP.md (최상위 프로세스)
    ↓
docs/v2/SSOT_RULES.md (개발 규칙)
    ↓
docs/v2/V2_ARCHITECTURE.md (설계 계약)
    ↓
config/v2/config.yml (실행 설정)
    ↓
.env.v2 (Secrets)
```

---

## 🔍 SSOT 검증 절차

### Gate 실행 전

```bash
# 1. SSOT 파일 존재 확인
test -f docs/D_ROADMAP.md || exit 1
test -f docs/v2/SSOT_RULES.md || exit 1
test -f docs/v2/V2_ARCHITECTURE.md || exit 1
test -f config/v2/config.yml || exit 1

# 2. SSOT 중복 확인
find . -name "D_ROADMAP*.md" | wc -l  # 1개여야 함
find . -name "SSOT_RULES*.md" | wc -l  # 1개여야 함

# 3. Config 검증
python -c "from arbitrage.v2.core.config import load_config; load_config('config/v2/config.yml')"
```

### Gate 실행 시

```bash
# Doctor Gate: SSOT 파일 존재 확인
pytest --collect-only

# Fast Gate: Config 로드 테스트
pytest tests/test_v2_config.py -v

# Regression Gate: 전체 SSOT 정합성
pytest tests/test_d98_preflight.py -v
```

---

## 🚨 SSOT 위반 사례 (금지)

### ❌ 사례 1: 로드맵 분기
```
docs/D_ROADMAP.md
docs/D_ROADMAP_V2.md          # 금지!
docs/v2/V2_ROADMAP.md          # 금지!
```

### ❌ 사례 2: Config 환경별 분기
```
config/v2/config.yml
config/v2/config_prod.yml      # 금지!
config/v2/config_dev.yml       # 금지!
```
**올바른 방법:** 환경 변수로 오버라이드 (`.env.v2`)

### ❌ 사례 3: 아키텍처 버전 분기
```
docs/v2/V2_ARCHITECTURE.md
docs/v2/V2_ARCHITECTURE_v2.md  # 금지!
docs/v2/V2_ARCHITECTURE_NEW.md # 금지!
```
**올바른 방법:** V2_ARCHITECTURE.md 직접 수정 + 변경 이력은 Git

---

## 📚 참조 매트릭스

| 작업 | 참조 SSOT |
|------|-----------|
| V2 코드 작성 | SSOT_RULES.md → V2_ARCHITECTURE.md → config.yml |
| Adapter 구현 | V2_ARCHITECTURE.md (인터페이스) → config.yml (설정) |
| 테스트 작성 | pytest.ini → SSOT_RULES.md (Gate 규칙) |
| 로드맵 확인 | D_ROADMAP.md |
| 인프라 배포 | infra/docker-compose.yml |
| 모니터링 설정 | prometheus.v2.yml → grafana dashboards |
| Secrets 관리 | .env.v2.example (템플릿) → .env.v2 (로컬) |

---

## 🎯 D200-1 조치 사항

- ✅ SSOT_MAP.md 생성 (현재 문서)
- ⏳ config/v2/config.yml 생성 (Runtime Config SSOT)
- ⏳ .env.v2.example 생성 (Secrets 템플릿)
- ⏳ infra/docker-compose.yml SSOT 확정
- ⏳ D_ROADMAP.md에 V2 섹션 상세 추가

---

## 🔁 V1→V2 재사용 맵핑 (Reuse-First 강제)

**목적:** V2는 "리셋"이 아니라 "수술"이다. V1 인프라를 최대한 재사용한다.

### 재사용 대상 모듈 (V1 → V2 매핑)

| V2 기능 | V1 재사용 모듈 | 재사용 방식 | 비고 |
|---------|---------------|------------|------|
| Alert Storage | `arbitrage/alerting/storage/postgres_storage.py` | 그대로 재사용 | PostgreSQL 기반 알림 저장소 |
| Alert Manager | `arbitrage/alerting/manager.py` | 그대로 재사용 | 알림 관리자 |
| Rate Limiter | `arbitrage/infrastructure/rate_limiter.py` | 그대로 재사용 | 거래소별 레이트 리밋 |
| Prometheus Exporter | `arbitrage/monitoring/prometheus_exporter.py` | 그대로 재사용 | 메트릭 수집 |
| Evidence Pack | `arbitrage/monitoring/evidence_pack.py` | 그대로 재사용 | 실행 증거 저장 |
| Gate Runner | `scripts/run_gate_with_evidence.py` | 그대로 재사용 | Gate 3단 검증 |
| Config Loader | `config/base.py` | 확장 (V2 섹션 추가) | 설정 관리 |
| Exchange Adapters | `arbitrage/exchanges/*.py` | 확장 (OrderIntent 지원) | 거래소 어댑터 |

### 신규 생성 허용 모듈 (V1 없음)

| V2 기능 | 신규 파일 | 근거 |
|---------|----------|------|
| Engine-Centric Flow | `arbitrage/v2/engine.py` | V1에 없던 중앙 엔진 패턴 |
| OrderIntent | `arbitrage/v2/domain/order_intent.py` | V1에 없던 주문 의도 추상화 |
| MarketData Interfaces | `arbitrage/v2/marketdata/interfaces.py` | V1에 없던 데이터 계약 |
| Break-even Threshold (D203-1) | `arbitrage/v2/domain/break_even.py` | V1에 공식 없음, V1 FeeModel 재사용 |
| Opportunity Detector (D203-2) | `arbitrage/v2/opportunity/detector.py` | V1에 detector 없음, SpreadModel 로직 참조 |

### 금지 사항

- ❌ `arbitrage/v2/alerting/postgres_storage_v2.py` 같은 중복 모듈 생성
- ❌ `arbitrage/v2/monitoring/new_prometheus_exporter.py` 같은 재발명
- ❌ V1 모듈 대체 없이 새 모듈로 전환

### 예외 처리

신규 모듈 생성 시:
1. `docs/v2/design/INFRA_REUSE_INVENTORY.md`에 사유 기록
2. D 리포트에 "왜 기존 것을 못 쓰는지" 명시
3. Gate PASS 후에만 진행

---

**결론:** V2는 8개 도메인에서 8개 SSOT 운영. 중복/분기 절대 금지. Gate로 정합성 강제.
