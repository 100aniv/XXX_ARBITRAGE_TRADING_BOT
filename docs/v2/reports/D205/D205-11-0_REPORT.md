# D205-11-0: SSOT 레일 복구 + Redis/DB 계측 추가

## 최종 상태: 🔄 IN PROGRESS

**목표:**
- D205-11 섹션 SSOT 복구 (축약/삭제 제거)
- D205-11-1 정식 편입 (umbrella 하위 단계)
- Redis/DB 계측 범위 추가 (AC-7/8 충족)
- Gate 3단 + SSOT Docs Check 100% PASS

---

## 문제 분석 (SSOT 위반 3가지)

### 문제 1: D_ROADMAP.md D205-11 섹션 축약/삭제 (CRITICAL)

**증거:** `D_ROADMAP.md` Line 3506-3525 (패치 bf80486..a54abec 이전)

**현재 상태 (문제):**
```markdown
#### D205-11: Latency Profiling (ms 단위 계측)
**상태:** PLANNED ⏳
**커밋:** [pending]
...
**Gate 조건:**
- Gate 0 FAIL
- latency p95 < 100ms (목표치)
```

**문제점:**
1. ❌ 목표(Goal) 섹션 누락: "ms 단위 계측" 한 줄만
2. ❌ Do/Don't 섹션 누락
3. ❌ AC 체크리스트 전부 삭제됨
4. ❌ Redis/DB/Logging 병목 계측 범위 누락
5. ❌ Evidence 요구사항 불완전: `optimization_results.json` 한 줄만

**SSOT 위반 근거:**
- "기존 목표 / AC / 증거 요구사항 절대 삭제 금지" (D_PROMPT_TEMPLATE.md)

---

### 문제 2: D205-11-1이 로드맵에 없음 (CRITICAL)

**증거:**
- 코드 존재: `arbitrage/v2/observability/latency_profiler.py`
- Report 존재: `docs/v2/reports/D205/D205-11-1_LATENCY_PROFILING_REPORT.md`
- Evidence 존재: `logs/evidence/d205_11_1_latency_20260105_010226/`
- 로드맵 부재: D_ROADMAP.md에 D205-11-1 섹션 없음

**문제점:**
❌ **SSOT 불일치**: 실행물(코드/리포트/증거)이 존재하나, SSOT(로드맵)에 해당 단계가 정의되지 않음.

**SSOT 위반 근거:**
- "새 D번호 생성 전 D_ROADMAP에 섹션(목표+AC+Next) 먼저 존재해야 함" (전역 규칙)

---

### 문제 3: Redis 병목 계측 범위 누락 (HIGH)

**증거:**
- D205-11 목표: "DB I/O/로깅 병목" 언급
- Redis 언급 없음: Rate Limit Counter, Dedup Key 등 핫루프 호출 미계측

**문제점:**
⚠️ **병목 후보 누락**: V2 아키텍처는 Redis를 Hot Path로 사용. Redis read/write latency가 병목일 가능성 높으나 계측 대상에서 빠짐.

**SSOT 위반 근거:**
- "Redis/DB 포함 병목 계측 원칙" (프롬프트 Step 5)

---

## 해결 방법 (Step 3 완료)

### 1. D_ROADMAP.md 전체 복구 ✅

**변경 내용:**
- D205-11을 Umbrella로 재정의
- D205-11-1: Instrumentation Baseline (COMPLETED) 정식 편입
- D205-11-0: SSOT 레일 복구 + Redis/DB 계측 (IN PROGRESS) 추가
- D205-11-2: Bottleneck Fix (PLANNED, 조건부) 추가

**복구된 항목:**
- ✅ 목표/범위 Do/Don't 전체 복구
- ✅ AC 체크리스트 복구 (D205-11-1: 9개, D205-11-0: 7개, D205-11-2: 5개)
- ✅ Evidence 요구사항 완전화
- ✅ Redis/DB/Logging 병목 계측 범위 명시

---

## AC 달성 현황

| AC | 내용 | 상태 | 증거 |
|----|------|------|------|
| AC-1 | D_ROADMAP D205-11 완전 복구 | ✅ DONE | D_ROADMAP.md Line 3506-3673 |
| AC-2 | D205-11-1 정식 편입 | ✅ DONE | D_ROADMAP.md Line 3533-3587 |
| AC-3 | Redis read/write(ms) 계측 | ⏳ PENDING | wrapper 구현 필요 |
| AC-4 | DB write(ms) 계측 | ⏳ PENDING | wrapper 구현 필요 |
| AC-5 | Gate 3단 PASS | ⏳ PENDING | pytest 실행 필요 |
| AC-6 | SSOT Docs Check PASS | ⏳ PENDING | check_ssot_docs.py 필요 |
| AC-7 | Evidence 패키징 | ⏳ PENDING | latency_summary.json 업데이트 |

**진행률:** 2/7 AC 달성 (28.6%)

---

## 코드 변경 계획 (Step 5)

### Redis Latency Wrapper (최소)

**파일:** `arbitrage/v2/infra/redis_latency.py` (신규 또는 기존 래퍼 확장)

**기능:**
- Redis GET/SET/INCR/DECR latency 계측
- time.perf_counter() 기반
- LatencyProfiler 연계 (새 stage: REDIS_READ, REDIS_WRITE 추가)

**재사용 원칙:**
- ✅ 기존 Redis client wrapper가 있으면 확장
- ❌ 새 Redis client 생성 금지

### DB Latency Wrapper (최소)

**파일:** `arbitrage/v2/storage/*` (기존 모듈 확장)

**기능:**
- INSERT/UPDATE latency 계측
- v2_orders, v2_fills, v2_trades 테이블만
- LatencyProfiler 연계 (새 stage: DB_WRITE 추가)

**재사용 원칙:**
- ✅ 기존 DB writer가 있으면 확장
- ❌ 새 ORM/쿼리 빌더 생성 금지

---

## Gate 결과 (예상)

| Gate | 예상 결과 | 세부 |
|------|-----------|------|
| Doctor | ⏳ PENDING | pytest --collect-only |
| Fast | ⏳ PENDING | test_latency_profiler.py 확장 필요 (Redis/DB 계측 테스트) |
| Regression | ⏳ PENDING | test_d98_preflight.py (기존 유지) |
| SSOT Docs Check | ⏳ PENDING | check_ssot_docs.py (D_ROADMAP 정합성) |

---

## Evidence 구성

**폴더:** `logs/evidence/STEP0_BOOTSTRAP_D205_11_0_20260105_013900/`

**파일 목록:**
- ✅ bootstrap_env.txt (환경 정보)
- ✅ SCAN_REUSE_SUMMARY.md (재사용 모듈 TOP 5)
- ✅ PROBLEM_ANALYSIS.md (문제 분석 증거)
- ✅ DOCS_READING_CHECKLIST.md (SSOT 문서 정독)
- ⏳ latency_summary.json (Redis/DB 계측 결과 추가 예정)
- ⏳ gate_results.txt (Gate 3단 결과)
- ⏳ manifest.json (run metadata)

---

## 다음 단계

### Step 5: 코드 최소 착수 (진행 예정)
- Redis/DB latency wrapper 구현
- LatencyProfiler에 REDIS_READ/REDIS_WRITE/DB_WRITE stage 추가
- PaperRunner에 Redis/DB 계측 훅 추가

### Step 6: Gate 3단 + SSOT Docs Check
- Doctor/Fast/Regression 실행
- check_ssot_docs.py 실행
- 모든 Gate 100% PASS 확인

### Step 7: Evidence 패키징
- latency_summary.json 업데이트 (Redis/DB 포함)
- manifest.json 생성
- README.md 재현 명령 업데이트

### Step 8: ROADMAP 최종 동기화
- D_ROADMAP.md 상태 업데이트 (IN PROGRESS → COMPLETED)
- AC 체크박스 업데이트

### Step 9: Git commit + push
- SSOT 스타일 커밋 메시지
- Compare URL 생성

---

## 재현 명령어

### Bootstrap (완료)
```bash
# 환경 확인
python --version  # Python 3.14.0
git log -1 --format="%H %h %s"  # a54abec [D205-11-1] ...

# 문서 스캔
find arbitrage/v2 -name "*latency*" -o -name "*metrics*"
```

### Gate 3단 (예정)
```bash
pytest --collect-only tests/test_latency_profiler.py
pytest tests/test_latency_profiler.py -v
pytest tests/test_d98_preflight.py -v
```

### SSOT Docs Check (예정)
```bash
python scripts/check_ssot_docs.py
```

---

## 최종 평가

**상태:** 🔄 IN PROGRESS (2/7 AC, 28.6%)  
**품질:** SSOT 복구 완료, 코드 구현 대기  
**다음 작업:** Step 5 (Redis/DB wrapper 최소 구현)
