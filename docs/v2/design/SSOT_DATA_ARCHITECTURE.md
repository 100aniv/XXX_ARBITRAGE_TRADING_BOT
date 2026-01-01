# SSOT Data Architecture (Cold Path vs Hot Path)

**작성일:** 2026-01-01  
**목적:** DB(Truth) vs Redis(Required) 구분을 헌법급으로 정의  
**참조:** SSOT_MAP.md, REDIS_KEYSPACE.md, V2_ARCHITECTURE.md

---

## 📋 핵심 계약 (Contract)

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

## 🏗️ Architecture Layers

### Cold Path (PostgreSQL)

**역할:**
- Ledger/Truth (최종 원장)
- Audit Trail (감사 기록)
- Replay Source (재현 데이터)

**테이블:**
- `v2_orders`: 주문 기록 (Paper/LIVE 모두)
- `v2_fills`: 체결 기록 (1 order → N fills)
- `v2_trades`: 차익거래 기록 (Entry → Exit)
- `v2_ledger`: 원장 기록 (집계용)
- `v2_pnl_daily`: 일별 PnL 집계 (리포팅용)

**성능 요구사항:**
- 낮음 (배치 기반, 초당 수십 건)
- 정확성 > 속도

**필수 조건:**
- Paper/Live 모두 필수
- 없으면: 감사/재현 불가 (FAIL)

---

### Hot Path (Redis)

**역할:**
- Rate Limit Counters (API 요청 제한)
- Dedup Keys (중복 주문 방지)
- Hot-state (엔진 상태, 메모리 기반)

**Key Domains:**
- `v2:ratelimit:{exchange}:{endpoint}` - Rate limit counter
- `v2:dedup:{order_id}` - 중복 주문 방지
- `v2:state:engine` - 엔진 상태
- `v2:market:{exchange}:{symbol}` - 시장 데이터 캐시

**성능 요구사항:**
- 높음 (ms 단위, 초당 수천 건)
- 속도 > 정확성 (손실 허용, 재계산 가능)

**필수 조건:**
- Paper/Live 모두 필수
- 없으면: Rate Limit 우회, 중복 주문, 상태 손실 (FAIL)

---

## 📊 비교표

| 항목 | Cold Path (DB) | Hot Path (Redis) |
|------|---|---|
| **Truth** | ✅ Yes | ❌ No |
| **Required** | ✅ Yes | ✅ Yes |
| **Persistence** | ✅ Permanent | ❌ Ephemeral (TTL) |
| **Performance** | 낮음 (배치) | 높음 (ms) |
| **Audit** | ✅ Yes | ❌ No |
| **Replay** | ✅ Yes | ❌ No |
| **Paper Mode** | ✅ Required | ✅ Required |
| **Live Mode** | ✅ Required | ✅ Required |

---

## 🚨 실패 시나리오

### Scenario 1: DB 없음
```
상황: PostgreSQL 미기동 또는 초기화 실패
결과: 
  - 거래 기록 불가 (v2_orders/fills/trades 저장 불가)
  - 감사/재현 불가
  - 배포 후 "어떤 거래가 실행됐는지" 추적 불가
판정: ❌ FAIL (Paper/Live 모두)
```

### Scenario 2: Redis 없음
```
상황: Redis 미기동 또는 연결 실패
결과:
  - Rate Limit 우회 → 거래소 계정 차단
  - 중복 주문 발생 → 손실 위험
  - 엔진 상태 손실 → 포지션 추적 불가
판정: ❌ FAIL (Paper/Live 모두)
```

### Scenario 3: DB 있지만 Redis 없음 (V1 패턴)
```
상황: "DB만 있으면 되지 않나?" 생각
결과:
  - Paper 테스트는 "성공"하는 것처럼 보임
  - Live 배포 후 Rate Limit 우회로 계정 차단
  - "Paper에서는 잘 되는데 Live에서 왜 안 되지?" 현상
판정: ⚠️ PARTIAL (Paper는 "거짓 성공", Live는 FAIL)
```

---

## ✅ D205-9 검증 기준

### Prerequisites (필수 선행 조건)
- ✅ Docker: PostgreSQL up
- ✅ Docker: Redis up
- ✅ Real MarketData: Upbit + Binance 연결 가능

### AC (Acceptance Criteria)
- ✅ DB Readiness: PostgreSQL 초기화 성공, v2_schema 마이그레이션 완료
- ✅ Redis Readiness: Redis 연결 성공, Rate Limit Counter 동작 확인
- ✅ Real MarketData: Upbit + Binance 둘 다 OK
- ✅ DB Ledger: v2_orders/fills/trades 증거 (strict mode, 250+ rows)
- ✅ Fake-Optimism 감지: winrate 100% → 즉시 중단
- ✅ closed_trades > 10
- ✅ edge_after_cost > 0
- ✅ error_count = 0, db_inserts_failed = 0

### Evidence Files
```
logs/evidence/d205_9_paper_smoke_YYYYMMDD_HHMM/
├── manifest.json              # git_sha, cmdline, config
├── result.json                # AC 검증 결과
├── kpi_smoke.json             # KPI (closed_trades, winrate, etc)
├── db_ledger_counts.json      # v2_orders/fills/trades row count
├── redis_readiness.json       # Redis connection + counter test
└── paper.log                  # 실행 로그
```

---

## 🔗 참조 문서

- **SSOT_MAP.md**: 전체 SSOT 정의 (DB/Redis/Monitoring)
- **REDIS_KEYSPACE.md**: Redis key 네이밍 규칙 및 TTL 정책
- **V2_ARCHITECTURE.md**: V2 설계 목표 (Infrastructure Parity 포함)
- **D205-9_REPORT.md**: Realistic Paper Validation 보고서
- **D_ROADMAP.md**: D205-9 Prerequisites + AC 명시

---

## 📝 업데이트 규칙

### DB 스키마 변경 시
1. 새 migration 파일 생성 (v2_NNN_description.sql)
2. 커밋 메시지에 "[DB]" 태그
3. 본 문서의 "Cold Path" 섹션 업데이트

### Redis Keyspace 변경 시
1. REDIS_KEYSPACE.md 업데이트
2. 커밋 메시지에 "[REDIS]" 태그
3. 본 문서의 "Hot Path" 섹션 업데이트

### D205-9 이후 변경 시
1. D_ROADMAP.md의 D205-9 섹션 업데이트
2. 본 문서의 "D205-9 검증 기준" 섹션 업데이트
3. 새 Evidence 파일 경로 추가

---

## 최종 원칙

> **"Paper 모드가 Live 모드와 동일한 인프라(DB + Redis)를 사용해야만,**  
> **배포 시 surprises가 없고, 실전 유사 검증이 의미가 있다."**

이 원칙을 위반하면:
- Paper에서 "성공"하는 것처럼 보이지만
- Live에서 Rate Limit 우회, 중복 주문, 상태 손실 등으로 실패
- 결과적으로 "Paper 검증이 무의미"해짐

따라서 **D205-9부터는 DB + Redis 모두 필수**.

