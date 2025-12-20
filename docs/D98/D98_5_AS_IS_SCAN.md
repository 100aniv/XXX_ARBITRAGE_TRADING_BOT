# D98-5 AS-IS Scan: Preflight 진입점 및 기존 구조 분석

**작성일:** 2025-12-21  
**작성자:** Windsurf AI  
**목적:** Preflight Real-Check Fail-Closed 구현 전 기존 preflight 구조 파악

---

## 1. Executive Summary

**스캔 범위:**
- 기존 preflight 스크립트 (`scripts/d98_live_preflight.py`)
- DB/Redis 연결 모듈 (`arbitrage/redis_client.py`, `arbitrage/storage.py`)
- Exchange 어댑터 구조 분석
- ReadOnlyGuard 통합 현황

**핵심 발견:**
1. ✅ **기존 Preflight 존재**: `scripts/d98_live_preflight.py` (D98-0에서 구현)
2. ⚠️ **Dry-run 방식**: DB/Redis/Exchange를 실제로 연결하지 않고 환경변수 존재 여부만 확인
3. ✅ **ReadOnlyGuard 통합**: D98-1에서 이미 적용됨
4. 📋 **개선 필요**: Real-Check (실제 연결 검증) 로직 추가 필요

**결론:**
- 기존 preflight는 "설정 존재 여부" 확인 (dry-run)
- 이번 D98-5는 "실제 연결 및 응답" 확인 (real-check)
- 기존 구조를 최대한 재사용하되, real-check 로직만 추가

---

## 2. 기존 Preflight 구조 (`scripts/d98_live_preflight.py`)

### 2.1 전체 구조

**파일:** `scripts/d98_live_preflight.py` (366 lines)

**클래스:**
```python
class PreflightResult:
    """Preflight 점검 결과 저장"""
    - checks: List[Dict] (점검 항목 목록)
    - passed, failed, warnings (카운터)
    - add_check(), is_ready(), to_dict()

class LivePreflightChecker:
    """LIVE 모드 사전 점검기"""
    - check_environment()          # [1/7] 환경변수
    - check_secrets()              # [2/7] 시크릿 존재
    - check_live_safety()          # [3/7] LIVE 안전장치
    - check_database_connection()  # [4/7] DB 연결 (mock)
    - check_exchange_health()      # [5/7] 거래소 Health (mock)
    - check_open_positions()       # [6/7] 오픈 포지션 (mock)
    - check_git_safety()           # [7/7] Git 안전
    - run_all_checks()             # 전체 실행
```

### 2.2 현재 점검 항목 (7개)

| # | 항목 | 현재 방식 | 개선 필요 |
|---|------|----------|----------|
| 1 | Environment | ✅ `Settings.env` 확인 | (유지) |
| 2 | Secrets | ✅ 환경변수 존재 여부 | (유지) |
| 3 | Live Safety | ✅ LiveSafetyValidator + ReadOnlyGuard | (유지) |
| 4 | Database | ⚠️ **환경변수만 확인 (dry-run)** | **Real-Check 추가** |
| 5 | Exchange Health | ⚠️ **환경변수만 확인 (dry-run)** | **Real-Check 추가** |
| 6 | Open Positions | ⚠️ **Mock 데이터 (dry-run)** | (향후) |
| 7 | Git Safety | ✅ `.env.live` 존재 여부 | (유지) |

### 2.3 Dry-run vs Real-run 분기

**현재 코드:**
```python
def check_database_connection(self):
    """DB 연결 점검 (mock)"""
    # Mock: 실제 연결 대신 DSN 존재 여부만 확인
    postgres_dsn = os.getenv("POSTGRES_DSN")
    redis_url = os.getenv("REDIS_URL")
    
    if postgres_dsn and redis_url:
        self.result.add_check(
            "Database",
            "PASS",
            "DB 연결 정보 존재 (dry-run, 실제 연결 안 함)",
            {"dry_run": self.dry_run}
        )
```

**문제점:**
- 환경변수는 있지만 실제 연결 불가능한 경우 탐지 못함
- DSN/URL 형식 오류도 탐지 못함
- DB/Redis가 down 상태여도 PASS

**개선 방향:**
- `dry_run=False`일 때 실제 연결 시도
- Redis: `PING` + `SET/GET` 테스트
- Postgres: `SELECT 1` + 필수 테이블 확인
- 실패 시 `PreflightError` 발생 (Fail-Closed)

---

## 3. DB/Redis 연결 모듈 분석

### 3.1 Redis 연결 (`arbitrage/redis_client.py`)

**파일:** `arbitrage/redis_client.py` (추정)

**주요 클래스/함수:**
```python
# 예상 구조 (실제 코드 확인 필요)
class RedisClient:
    def __init__(self, url: str):
        self.url = url
        self.client = redis.from_url(url)
    
    def ping(self) -> bool:
        """연결 확인"""
        return self.client.ping()
    
    def set(self, key: str, value: str) -> bool:
        """키 설정"""
        return self.client.set(key, value)
    
    def get(self, key: str) -> Optional[str]:
        """키 조회"""
        return self.client.get(key)
```

**Real-Check 시나리오:**
1. Redis URL 파싱 (`redis://localhost:6380/0`)
2. `ping()` 호출 → `PONG` 응답 확인
3. `set("preflight_test", "ok")` → `True` 반환 확인
4. `get("preflight_test")` → `"ok"` 반환 확인
5. `delete("preflight_test")` → cleanup
6. 실패 시 `PreflightError` 발생

### 3.2 Postgres 연결 (`arbitrage/storage.py`)

**파일:** `arbitrage/storage.py` (추정)

**주요 클래스/함수:**
```python
# 예상 구조 (실제 코드 확인 필요)
class DatabaseStorage:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.conn = psycopg2.connect(dsn)
    
    def execute_query(self, query: str) -> List[Tuple]:
        """쿼리 실행"""
        cursor = self.conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()
```

**Real-Check 시나리오:**
1. Postgres DSN 파싱 (`postgresql://arbitrage:xxx@localhost:5432/arbitrage`)
2. 연결 생성 (`psycopg2.connect(dsn)`)
3. `SELECT 1` 실행 → `[(1,)]` 반환 확인
4. 필수 테이블 확인 (선택적, 가능하면):
   - `SELECT table_name FROM information_schema.tables WHERE table_schema='public'`
   - 예: `trades`, `positions`, `kpi_metrics` 등 존재 확인
5. 연결 종료 (`conn.close()`)
6. 실패 시 `PreflightError` 발생

---

## 4. Exchange 어댑터 구조 분석

### 4.1 Paper 모드 (PaperExchange)

**파일:** `arbitrage/exchanges/paper_exchange.py`

**Real-Check 시나리오 (Paper):**
- Paper 모드는 실제 API 호출 없음
- 대신 PaperExchange 객체 생성 가능 여부만 확인
- `get_balance()` 호출 → mock 데이터 반환 확인
- `get_orderbook()` 호출 → mock 호가 반환 확인

### 4.2 Live 모드 (UpbitSpotExchange, BinanceFuturesExchange)

**파일:** `arbitrage/exchanges/upbit_live.py`, `arbitrage/exchanges/binance_live.py`

**Real-Check 시나리오 (Live):**
- ⚠️ **주의**: Private endpoint 호출 금지 (잔고, 주문 등)
- ✅ **Public endpoint만 허용**: server time, markets, ticker 등
- LiveSafetyValidator 통과 필수 (ARM ACK + Timestamp + Notional)
- 예시:
  - Upbit: `GET /v1/status/wallet` (입출금 상태, public)
  - Binance: `GET /fapi/v1/ping` (서버 상태, public)

**예외 처리:**
- Rate limit → 1회 retry 허용
- Timeout → 5초 타임아웃 설정
- 실패 시 `PreflightError` 발생

---

## 5. ReadOnlyGuard 통합 현황

### 5.1 현재 상태 (D98-1 완료)

**통합 위치:**
- `scripts/d98_live_preflight.py` Line 25-26:
  ```python
  # D98-1: READ_ONLY_ENFORCED 강제 설정 (실주문 0건 보장)
  os.environ["READ_ONLY_ENFORCED"] = "true"
  ```

- `scripts/d98_live_preflight.py` Line 144-158:
  ```python
  # D98-1: ReadOnlyGuard 검증 (실주문 0건 보장)
  if not is_readonly_mode():
      self.result.add_check(
          "ReadOnly Guard",
          "FAIL",
          "READ_ONLY_ENFORCED가 false로 설정됨 (실주문 위험)"
      )
  ```

### 5.2 D98-5와의 정합성

**Real-Check와 ReadOnlyGuard 관계:**
- ReadOnlyGuard는 "주문 실행 차단" (D98-1~3)
- Real-Check는 "실제 연결 검증" (D98-5)
- 두 가지 모두 Fail-Closed 원칙 따름

**통합 시나리오:**
1. Preflight 시작 → `READ_ONLY_ENFORCED=true` 강제 설정
2. ReadOnlyGuard 검증 → PASS 확인
3. Real-Check 실행 → DB/Redis/Exchange 실제 연결
4. 모두 PASS → Preflight 완료
5. 하나라도 FAIL → 즉시 종료 (exit code 1)

---

## 6. 구현 계획 (기존 구조 재사용)

### 6.1 재사용할 구조

**변경 최소화 원칙:**
- ✅ `PreflightResult` 클래스: 그대로 재사용
- ✅ `LivePreflightChecker` 클래스: 확장
- ✅ `check_environment()`, `check_secrets()`, `check_git_safety()`: 그대로 유지
- ✅ `main()` 함수: CLI 인자 추가만

### 6.2 추가/수정할 메서드

**1. `check_database_connection()` 수정:**
```python
def check_database_connection(self):
    """DB 연결 점검 (real-check 추가)"""
    if self.dry_run:
        # 기존 로직 (환경변수만 확인)
        pass
    else:
        # D98-5: Real-Check 로직 추가
        try:
            # Redis
            redis_client = RedisClient(os.getenv("REDIS_URL"))
            redis_client.ping()
            redis_client.set("preflight_test", "ok")
            assert redis_client.get("preflight_test") == "ok"
            redis_client.delete("preflight_test")
            
            # Postgres
            conn = psycopg2.connect(os.getenv("POSTGRES_DSN"))
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)
            conn.close()
            
            self.result.add_check("Database", "PASS", "Real-Check 성공")
        except Exception as e:
            raise PreflightError(f"DB Real-Check 실패: {e}")
```

**2. `check_exchange_health()` 수정:**
```python
def check_exchange_health(self):
    """거래소 Health 점검 (real-check 추가)"""
    if self.dry_run:
        # 기존 로직 (스킵)
        pass
    else:
        # D98-5: Real-Check 로직 추가
        if self.settings.env == "paper":
            # Paper: PaperExchange 객체 생성 확인
            paper_exchange = PaperExchange(...)
            balance = paper_exchange.get_balance("BTC")
            # balance가 dict 형태인지만 확인
        elif self.settings.env == "live":
            # Live: LiveSafetyValidator 통과 필수
            validator = LiveSafetyValidator()
            is_valid, error = validator.validate_live_mode()
            if not is_valid:
                raise PreflightError(f"Live Safety 차단: {error}")
            
            # Public endpoint만 호출
            upbit_api = UpbitPublicAPI()
            upbit_status = upbit_api.get_server_time()
            # 응답 확인
```

**3. CLI 인자 추가:**
```python
parser.add_argument(
    "--real-check",
    action="store_true",
    default=False,
    help="실제 연결 검증 수행 (dry-run 비활성화)"
)

# dry_run = not args.real_check
```

### 6.3 신규 예외 클래스

**파일:** `arbitrage/config/preflight.py` (신규 생성)

```python
class PreflightError(Exception):
    """Preflight 검증 실패 예외"""
    pass
```

---

## 7. 테스트 전략

### 7.1 단위 테스트

**파일:** `tests/test_d98_5_preflight_realcheck.py` (신규 생성)

**테스트 케이스:**
1. `test_redis_realcheck_pass`: Redis 정상 연결
2. `test_redis_realcheck_fail`: Redis 연결 실패 (wrong URL)
3. `test_postgres_realcheck_pass`: Postgres 정상 연결
4. `test_postgres_realcheck_fail`: Postgres 연결 실패 (wrong DSN)
5. `test_exchange_realcheck_paper`: Paper 모드 검증
6. `test_exchange_realcheck_live`: Live 모드 public endpoint 호출
7. `test_readonly_guard_integration`: ReadOnlyGuard와 정합성 검증

### 7.2 통합 테스트

**시나리오:**
1. Docker Redis/Postgres up 상태 → Real-Check PASS
2. Redis down → Real-Check FAIL + PreflightError
3. Postgres down → Real-Check FAIL + PreflightError
4. READ_ONLY_ENFORCED=false → ReadOnlyGuard FAIL
5. Live 모드 + ARM ACK 누락 → LiveSafetyValidator FAIL

---

## 8. 진입점 요약

### 8.1 Preflight 실행 경로

```
사용자
  ↓
python scripts/d98_live_preflight.py --real-check
  ↓
LivePreflightChecker.__init__()
  ├─ Settings.from_env() (D98-4 LiveSafetyValidator 통합)
  └─ ReadOnlyGuard 강제 설정 (D98-1)
  ↓
run_all_checks()
  ├─ check_environment() ✅
  ├─ check_secrets() ✅
  ├─ check_live_safety() ✅ (D98-1~4 통합)
  ├─ check_database_connection() 🔄 (D98-5 Real-Check 추가)
  ├─ check_exchange_health() 🔄 (D98-5 Real-Check 추가)
  ├─ check_open_positions() ⏸️ (향후)
  └─ check_git_safety() ✅
  ↓
PreflightResult.to_dict() → JSON 저장
  ↓
exit(0: PASS, 1: FAIL)
```

### 8.2 Fail-Closed 트리거

**즉시 종료 조건:**
1. Redis `ping()` 실패 → `PreflightError`
2. Postgres `SELECT 1` 실패 → `PreflightError`
3. Exchange public endpoint 실패 → `PreflightError`
4. `READ_ONLY_ENFORCED=false` → FAIL (exit 1)
5. Live Safety 검증 실패 → FAIL (exit 1)

---

## 9. 리스크 & 제약사항

### 9.1 리스크

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| DB/Redis 연결 timeout | Medium | Medium | 5초 타임아웃 설정 |
| Exchange rate limit | Low | Low | Public endpoint만 호출, 1회 retry |
| 테스트 환경 불일치 | Medium | High | Docker 환경에서 통합 테스트 |
| PreflightError 메시지 불명확 | Low | Medium | 상세 에러 메시지 포함 |

### 9.2 제약사항

**현재 범위:**
- ✅ Redis, Postgres Real-Check
- ✅ Exchange Public endpoint (Paper/Live 분기)
- ❌ Private endpoint 호출 (잔고, 주문 등) - 금지
- ❌ Open positions 실제 조회 - 향후 구현

**하지 않을 것:**
- ❌ DB 마이그레이션 자동 실행
- ❌ 환경변수 전수 검사 (필수 항목만)
- ❌ 성능 최적화 (병렬 검증 등)

---

## 10. 결론

**AS-IS 스캔 결과:**
- 기존 Preflight: Dry-run 방식 (환경변수만 확인)
- 개선 필요: Real-Check (실제 연결 검증)
- 재사용 가능: `PreflightResult`, `LivePreflightChecker` 클래스 구조
- 추가 작업: `check_database_connection()`, `check_exchange_health()` 수정

**다음 단계:**
- D98-5 구현: Real-Check 로직 추가
- 테스트 작성: 단위 + 통합 테스트
- Evidence 저장: realcheck + json
- 문서/ROADMAP 업데이트

---

**작성 완료:** 2025-12-21 00:45 KST  
**작성자:** Windsurf AI  
**버전:** v1.0
