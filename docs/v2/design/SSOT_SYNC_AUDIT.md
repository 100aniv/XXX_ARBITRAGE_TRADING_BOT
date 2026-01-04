# SSOT 문서 정합성 감사 (D205-9-PRE)

**작성일:** 2026-01-01  
**목적:** Redis/DB 관련 문서 괴리 분석 및 정합성 검증

---

## STEP 1️⃣ 문서 스캔 결과

### 1. D_ROADMAP.md (Redis/DB 관련 문구)

**발견 위치:** D202-1 섹션

```
- **V2 활용:**
  - Market data cache (TTL 100ms)
  - Engine state 저장
  - Rate limiting 카운터
- **완료 시기:** D202-1 (MarketData)
```

**분석:**
- Redis를 "필수 구성요소"로 명시 (D202-1에서 이미 사용)
- 하지만 "필수성(Required)" vs "선택성(Optional)" 구분 명확하지 않음
- D205-9에서 Redis readiness 언급 없음

---

### 2. SSOT_MAP.md (DB/Redis 정의)

**발견 위치:** Lines 116-118

```
**SSOT 정의:**
- 주문/체결/거래/PnL의 **유일 원천**은 v2_schema.sql이 정의한 테이블
- 다른 저장소(파일, Redis)는 캐시일 뿐, DB가 진실
- 코드에서 직접 CREATE TABLE 실행 절대 금지
```

**분석:**
- ✅ DB = Truth (명확함)
- ⚠️ Redis = "캐시일 뿐" (필수성 약함)
- ❌ Redis가 "Truth는 아니지만 Runtime Required"라는 구분 없음

---

### 3. REDIS_KEYSPACE.md (Redis 역할)

**발견 위치:** Lines 1-14

```
**목적:** Redis key 네이밍 규칙 및 TTL 정책 SSOT 확정

## 📜 핵심 원칙
1. **네이밍 규칙 강제**: 모든 V2 key는 `v2:` prefix 필수
2. **환경 격리**: dev/prod 환경별 key 충돌 방지
3. **TTL 필수**: 모든 캐시는 TTL 설정 (메모리 누수 방지)
4. **타입 명시**: key 이름에 타입 힌트 포함 (권장)
```

**분석:**
- ✅ Redis keyspace 규칙 명확함
- ❌ "왜 Redis가 필수인가?" 근거 없음
- ❌ "DB 없으면 어떻게 되는가?" 명시 없음

---

### 4. D205-9_REPORT.md (Prerequisites)

**발견 위치:** Lines 62-65

```
### 환경 요구사항
- PostgreSQL (선택: `--db-mode optional`)
- 실시간 시장 데이터 연결 (Upbit, Binance)
- Python 환경 (`abt_bot_env`)
```

**분석:**
- ❌ **"PostgreSQL (선택)"** ← SSOT 철학과 충돌
- ❌ Redis 언급 없음
- ❌ "Realistic Paper Validation"이 DB/Redis readiness를 검증하는지 불명확

---

### 5. V2_ARCHITECTURE.md (인프라 계층)

**발견 위치:** Lines 1-50 (아직 완전 스캔 필요)

```
## 🎯 Design Goals

### 1. Engine-Centric (Not Script-Centric)
### 2. Semantic Layer (Not Exchange-Specific)
### 3. Mock-First Testing
```

**분석:**
- ✅ Engine 중심 설계 명확함
- ❌ DB/Redis 계층 구조 명시 없음
- ❌ "Mock-First"와 "Real Data" 간 인프라 차이 불명확

---

## 괴리 분석 (3가지 핵심 불일치)

### 괴리 1️⃣: Redis의 "위상" 불일치

| 문서 | 표현 | 문제 |
|------|------|------|
| D_ROADMAP | Redis 필수 (D202-1) | 명확함 ✅ |
| SSOT_MAP | Redis = 캐시 | 필수성 약함 ⚠️ |
| REDIS_KEYSPACE | Keyspace 규칙만 | 근거 없음 ❌ |
| D205-9_REPORT | Redis 언급 없음 | 누락 ❌ |

**결론:** "Redis = Truth는 아니지만 Runtime Required"를 명확히 정의해야 함

---

### 괴리 2️⃣: DB의 "선택성" 표현

| 문서 | 표현 | 문제 |
|------|------|------|
| SSOT_MAP | DB = Truth | 명확함 ✅ |
| D205-9_REPORT | PostgreSQL (선택) | SSOT 철학과 충돌 ❌ |

**결론:** D205-9에서 "DB optional" 표현 제거 필요

---

### 괴리 3️⃣: D205-9 AC에 Redis/DB readiness 누락

| 항목 | 현황 | 필요 |
|------|------|------|
| Prerequisites | DB만 명시 | DB + Redis 둘 다 명시 필요 |
| AC | Real MarketData만 | DB Ledger + Redis Counter 검증 추가 필요 |

**결론:** D205-9를 "실전 유사 검증"으로 정의하려면 인프라 readiness 필수

---

## STEP 2️⃣ 통일 기준 (3문장)

### 문장 1️⃣: DB는 Ledger/Truth/Audit (최종 원천)
```
DB(PostgreSQL v2_schema.sql)는 주문/체결/거래/PnL의 유일한 원천(SSOT)이며,
모든 거래 기록은 DB 테이블(v2_orders, v2_fills, v2_trades, v2_ledger)에 기록되어야 한다.
파일, Redis, 메모리는 캐시일 뿐 Truth가 아니다.
```

### 문장 2️⃣: Redis는 Truth는 아님, 하지만 Paper/Live 런타임 Required
```
Redis는 DB와 달리 최종 원천(Truth)이 아니지만,
Paper/Live 런타임에서 Rate Limit Counter, Dedup Key, Hot-state 저장소로 필수(Required)이다.
Redis 없으면 Rate Limit 우회, 중복 주문, 상태 손실 위험이 발생한다.
```

### 문장 3️⃣: D205-9는 DB/Redis readiness가 Prereq + AC
```
D205-9(Realistic Paper Validation)는 "실전 유사 검증"이므로,
DB 초기화 성공, Redis 연결 성공, Ledger 기록 정상이 Prerequisite이다.
AC에는 "DB Ledger 증가 검증" + "Redis Counter 동작 검증"이 포함된다.
```

---

## STEP 3️⃣ 신설 문서 계획

### 신설: `docs/v2/design/SSOT_DATA_ARCHITECTURE.md`

**목적:** Cold Path (DB) vs Hot Path (Redis) 구분을 헌법급으로 정의

**구조:**
```
# SSOT Data Architecture (Cold Path vs Hot Path)

## Cold Path (PostgreSQL)
- Ledger/Truth, Audit, Replay source
- 모든 거래 기록의 최종 원천
- 성능 요구사항: 낮음 (배치 기반)

## Hot Path (Redis)
- Rate Limit counters, Dedup keys, Hot-state
- Truth는 아니지만 Runtime Required
- 성능 요구사항: 높음 (ms 단위)

## Contract
- DB 없으면: 감사/재현 불가 (FAIL)
- Redis 없으면: Rate Limit 우회, 중복 주문 (FAIL)
- 둘 다 필수 (Paper/Live 모두)
```

---

## 다음 단계 (STEP 2️⃣ 진행 준비)

### 수정 대상 문서 (우선순위)

1. **SSOT_MAP.md** (가장 중요)
   - Line 118: "Redis는 캐시일 뿐" → "Redis는 Truth는 아니지만 Runtime Required"로 수정

2. **D205-9_REPORT.md**
   - Line 63: "PostgreSQL (선택)" → "PostgreSQL (필수)" 또는 제거
   - Prerequisites에 "Redis up" 추가
   - AC에 "Redis Counter 동작 검증" 추가

3. **D_ROADMAP.md** (D205-9 섹션)
   - Prerequisites에 "Redis/DB up" 명시
   - AC에 "RateLimit Counter (Redis) 동작 확인" 추가

4. **REDIS_KEYSPACE.md**
   - 서두에 "왜 Redis가 필수인가?" 근거 추가

5. **V2_ARCHITECTURE.md**
   - "Infra Layer" 섹션 추가 (Cold Path vs Hot Path)

---

## STEP 2️⃣ 시간 검증 체크 항목 (D205-10-2 이후)

### 장기 실행 작업 Wallclock Verification

**목적:** "3h 완료", "10h 실행" 같은 시간 기반 완료 선언의 허위를 원천 차단

**체크 항목:**

1. **watch_summary.json 존재 여부**
   - [ ] 장기 실행(≥1h) 작업에 watch_summary.json 생성 확인
   - [ ] 필수 필드 26개 모두 존재 확인

2. **monotonic_elapsed_sec 기반 시간 검증**
   - [ ] `monotonic_elapsed_sec` 존재 (SSOT)
   - [ ] `started_at_utc`, `ended_at_utc` ISO 8601 형식
   - [ ] `completeness_ratio` 계산 정확성

3. **stop_reason enum 검증**
   - [ ] stop_reason이 유효한 enum 값 중 하나
   - [ ] TIME_REACHED | TRIGGER_HIT | EARLY_INFEASIBLE | ERROR | INTERRUPTED

4. **문서/리포트에서 시간 언급 검증**
   - [ ] "Nh 완료" 문구가 watch_summary.json에서 추출한 값인지 확인
   - [ ] 인간이 손으로 쓴 시간 문구 금지
   - [ ] 문서에서 `monotonic_elapsed_sec` 또는 UTC timestamp 인용 확인

5. **상태 판단 규칙 준수**
   - [ ] COMPLETED: `stop_reason = TIME_REACHED` + `completeness_ratio ≥ 0.95`
   - [ ] PARTIAL: `stop_reason = EARLY_INFEASIBLE` 또는 `completeness < 0.95`
   - [ ] FAILED: `stop_reason = ERROR`

6. **Evidence 무결성**
   - [ ] f.flush() + os.fsync(f.fileno()) 사용 확인
   - [ ] 모든 종료 경로(정상/예외/Ctrl+C)에서 생성 보장
   - [ ] 60초마다 주기적 갱신 확인 (heartbeat)

**적용 대상:**
- D205-10-2 Wait Harness v2 이후 모든 장기 대기 작업
- Phased Run / Early-Stop 포함 작업
- Wait Harness / 모니터링 작업

**참조:**
- EVIDENCE_FORMAT.md: watch_summary.json 섹션
- D_TEST_TEMPLATE.md: Wallclock Verification 섹션
- D_PROMPT_TEMPLATE.md: Wallclock Verification 규칙

---

## 증거 파일 위치

```
docs/v2/design/SSOT_SYNC_AUDIT.md (본 문서)
```

**상태:** ✅ STEP 1️⃣ 완료, STEP 2️⃣ 준비 완료

