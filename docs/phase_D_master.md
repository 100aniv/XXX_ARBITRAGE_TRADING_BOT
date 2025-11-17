# PHASE D – Live Integration & Infra Hardening

## 개요

PHASE D는 PHASE C에서 구현한 Paper Trading 기반의 아비트라지 봇을 실제 운영 환경으로 전환하기 위한 단계입니다.

**목표**:
- PostgreSQL/TimescaleDB 기반 데이터 저장소 구현
- Redis 캐시 및 실시간 모니터링 준비
- Docker-compose 기반 인프라 자동화
- Live API 연동 준비 (PHASE E 예정)

**PHASE D 구성**:
- MODULE D1: PostgresStorage Implementation & CSV → DB Migration ✅ (완료)
- MODULE D2: Redis Cache & Health Monitoring ✅ (진행 중)
- MODULE D3: Docker-compose App Integration (예정)
- MODULE D4: Live API Connector Stubs (예정)

---

## MODULE D1 – PostgresStorage Implementation & CSV → DB Migration

### 목표

1. **PostgresStorage 실제 구현**
   - psycopg2 기반 동기 구현
   - 자동 테이블 생성
   - BaseStorage 인터페이스 완전 구현

2. **CSV → PostgreSQL 마이그레이션**
   - 기존 CSV 로그를 DB로 이관
   - Idempotent 설계 (중복 방지)
   - 트랜잭션 기반 안정성

3. **Backend 선택 메커니즘**
   - config.storage.backend 기반 자동 선택
   - 연결 실패 시 CSV로 자동 fallback
   - psycopg2 미설치 시 명확한 에러 메시지

### 구현 내용

#### 1. arbitrage/storage.py – PostgresStorage 구현

**특징**:
- psycopg2 기반 동기 구현 (향후 asyncpg로 확장 가능)
- 자동 테이블 생성 (CREATE TABLE IF NOT EXISTS)
- 인덱스 자동 생성 (성능 최적화)
- 트랜잭션 기반 데이터 무결성

**메서드**:
- `log_spread()`: 스프레드 기회 저장
- `log_position_open()`: 포지션 진입 저장
- `log_position_close()`: 포지션 청산 저장
- `log_order()`: 주문 레그 저장
- `log_error()`: 에러 로그 저장
- `load_positions()`: 포지션 로드

**테이블 구조** (docs/DB_SCHEMA.md 참조):
```
positions:  포지션 진입/청산 정보
orders:     주문 레그 정보
spreads:    스프레드 기회 스냅샷
trades:     거래 내역
fx_rates:   환율 정보
```

#### 2. config/base.yml – PostgreSQL 설정 추가

```yaml
storage:
  backend: csv  # csv | postgres | hybrid
  postgres:
    dsn: postgresql://arbitrage:arbitrage@localhost:5432/arbitrage
    schema: public
    enable_timescale: false
```

**사용 예시**:
```bash
# CSV 모드 (기본)
python scripts/run_paper.py

# PostgreSQL 모드 (docker-compose 필요)
docker-compose -f infra/docker-compose.yml up -d postgres
# config/base.yml에서 backend: postgres로 변경
python scripts/run_paper.py
```

#### 3. scripts/migrate_csv_to_postgres.py – 마이그레이션 스크립트

**기능**:
- CSV 파일 읽기 (positions.csv, orders.csv, spreads.csv)
- PostgreSQL로 INSERT
- Idempotent 설계 (중복 방지)
- 상세 로그 출력

**사용법**:
```bash
# 기본 마이그레이션
python scripts/migrate_csv_to_postgres.py --config config/base.yml

# Dry-run (실제 INSERT 없이 요약만 출력)
python scripts/migrate_csv_to_postgres.py --config config/base.yml --dry-run

# 테스트용 제한 (처음 100개 행만)
python scripts/migrate_csv_to_postgres.py --config config/base.yml --limit 100
```

#### 4. get_storage() 팩토리 함수 업데이트

```python
def get_storage(config: Dict) -> BaseStorage:
    """
    backend 설정값에 따라 저장소 선택:
    - "csv": CsvStorage (항상 사용 가능)
    - "postgres": PostgresStorage (psycopg2 필요, DB 연결 필요)
    - "hybrid": CSV + Redis (PHASE D2 예정)
    
    연결 실패 시 자동으로 CSV로 fallback
    """
```

### 테스트 & 검증

#### 1. CSV 모드 기본 동작 확인

```bash
# config/base.yml에서 backend: csv 확인
python scripts/run_paper.py

# 데이터 확인
ls -la data/
cat data/positions.csv
```

**예상 결과**: 기존과 동일하게 CSV 파일이 생성됨

#### 2. PostgreSQL 모드 기본 동작 확인

```bash
# PostgreSQL 서버 시작
docker-compose -f infra/docker-compose.yml up -d postgres

# 연결 확인
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT version();"

# config/base.yml에서 backend: postgres로 변경
sed -i 's/backend: csv/backend: postgres/' config/base.yml

# Paper 실행 (짧은 시간)
python scripts/run_paper.py

# DB 확인
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT COUNT(*) FROM positions;"
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT * FROM positions LIMIT 5;"
```

**예상 결과**: positions, orders 테이블에 데이터가 INSERT됨

#### 3. CSV → PostgreSQL 마이그레이션 테스트

```bash
# PostgreSQL 서버 시작
docker-compose -f infra/docker-compose.yml up -d postgres

# CSV 데이터 확인 (기존 로그)
wc -l data/positions.csv data/orders.csv data/spreads.csv

# Dry-run으로 요약 확인
python scripts/migrate_csv_to_postgres.py --config config/base.yml --dry-run

# 실제 마이그레이션
python scripts/migrate_csv_to_postgres.py --config config/base.yml

# DB 확인
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT COUNT(*) FROM positions;"

# 동일 스크립트 재실행 (Idempotency 확인)
python scripts/migrate_csv_to_postgres.py --config config/base.yml

# 데이터 중복 없음 확인
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT COUNT(*) FROM positions;"
```

**예상 결과**: 마이그레이션 후 데이터가 DB에 저장되고, 재실행해도 중복 없음

#### 4. Fallback 동작 확인

```bash
# PostgreSQL 서버 중지
docker-compose -f infra/docker-compose.yml down

# config/base.yml에서 backend: postgres 유지
# psycopg2 미설치 상태에서 실행
python scripts/run_paper.py

# 예상: WARNING 로그 출력 후 CSV로 fallback하여 정상 실행
```

**예상 결과**: WARNING 로그 출력 후 CSV로 자동 fallback

### 주의사항

#### 1. psycopg2 의존성

PostgreSQL 모드를 사용하려면 psycopg2 설치 필요:
```bash
pip install psycopg2-binary
```

CSV 모드에서는 psycopg2가 필요 없음 (지연 import 사용)

#### 2. 데이터베이스 설정

docker-compose 기본 설정:
- Host: localhost
- Port: 5432
- User: arbitrage
- Password: arbitrage
- Database: arbitrage

프로덕션 환경에서는 환경 변수로 관리:
```bash
export DATABASE_URL="postgresql://user:pass@host:5432/db"
# config/base.yml에서 postgres.dsn: ${DATABASE_URL} 사용
```

#### 3. 마이그레이션 주의사항

- CSV 파일이 없으면 스킵 (경고 로그만 출력)
- 마이그레이션 중 에러 발생 시 해당 행만 스킵
- Dry-run 모드로 먼저 확인 후 실행 권장

### 알려진 제한사항

1. **Redis 미구현**: PHASE D2에서 구현 예정
2. **Live API 미구현**: PHASE E에서 구현 예정
3. **모니터링 미구현**: PHASE D3에서 구현 예정
4. **TimescaleDB 미활성화**: enable_timescale=false (향후 활성화 가능)

### 다음 단계 (MODULE D2)

- Redis 캐시 구현 (FX 환율, 스프레드 스냅샷)
- 헬스 모니터링 (heartbeat 기반)
- 메트릭 집계 (일일 PnL 등)

---

## MODULE D2 – Redis Cache & Health Monitoring

### 목표

1. **Redis 기반 캐시 구현**
   - FX 환율 캐시 (TTL 기반)
   - 스프레드 스냅샷 캐시 (선택적)
   - 헬스 체크 heartbeat 저장

2. **헬스 모니터링 시스템**
   - Redis 연결 상태 확인
   - PostgreSQL 연결 상태 확인
   - CSV 저장소 상태 확인

3. **선택적 의존성 처리**
   - redis-py 미설치 시 graceful fallback
   - Redis 비활성화 시 무시
   - 연결 실패 시 자동 복구

### 구현 내용

#### 1. arbitrage/redis_client.py – Redis 클라이언트 (새 파일)

**특징**:
- redis-py 지연 import (선택적 의존성)
- 연결 실패 시 graceful fallback
- 키 네이밍 컨벤션 중앙화
- 싱글톤 패턴 (get_redis_client)

**메서드**:
- `set_fx_rate()`: 환율 캐시 저장
- `get_fx_rate()`: 환율 캐시 조회
- `set_heartbeat()`: 헬스 heartbeat 저장
- `get_heartbeat()`: 헬스 heartbeat 조회
- `set_spread_snapshot()`: 스프레드 스냅샷 저장
- `get_spread_snapshot()`: 스프레드 스냅샷 조회
- `ping()`: 연결 테스트

**키 네이밍**:
```
{prefix}:fx:usdkrw
{prefix}:heartbeat:paper_runner
{prefix}:spread:BTC
```

#### 2. arbitrage/health.py – 헬스 모니터링 (새 파일)

**특징**:
- HealthStatus 데이터클래스
- 각 컴포넌트별 상태 확인
- 상태 집계 및 포맷팅

**함수**:
- `check_redis()`: Redis 연결 상태 확인
- `check_postgres()`: PostgreSQL 연결 상태 확인
- `check_csv_storage()`: CSV 저장소 상태 확인
- `aggregate_status()`: 상태 집계
- `format_health_report()`: 리포트 포맷팅

**상태 값**:
- `OK`: 정상
- `WARN`: 경고
- `ERROR`: 에러
- `SKIP`: 사용하지 않음
- `DISABLED`: 비활성화

#### 3. scripts/run_health_check.py – 헬스 체크 스크립트 (새 파일)

**기능**:
- 설정 파일 로드
- 모든 컴포넌트 헬스 체크 실행
- 인간 친화적 리포트 출력
- 종료 코드 반환 (0=OK, 1=ERROR)

**사용법**:
```bash
python scripts/run_health_check.py
python scripts/run_health_check.py --config config/base.yml
python scripts/run_health_check.py --verbose
```

**출력 예시**:
```
────────────────────────────────────────────────────────────
Arbitrage-Lite: Health Check Report
────────────────────────────────────────────────────────────

[REDIS     ] ✅ OK       Connected to redis://localhost:6379/0
[POSTGRES  ] ✅ OK       Connected to localhost:5432/arbitrage
[CSV       ] ✅ OK       CSV storage at data

Overall:       ✅ OK
────────────────────────────────────────────────────────────
```

#### 4. config/base.yml – Redis 설정 추가

```yaml
redis:
  enabled: false                    # Redis 기능 활성화 여부
  url: redis://localhost:6379/0     # Redis 서버 URL
  prefix: arb                       # 키 프리픽스
  health_ttl_seconds: 60            # 헬스 체크 TTL (초)
```

#### 5. arbitrage/fx.py – Redis 통합 (수정)

**변경 사항**:
- `_publish_fx_to_redis()` 함수 추가
- `get_usdkrw()` 함수에서 Redis에 환율 발행
- 기존 동작 100% 유지 (Redis 비활성화 시)

### 테스트 & 검증

#### 1. Redis 비활성화 시나리오

```bash
# config/base.yml에서 redis.enabled: false 확인
grep "enabled:" config/base.yml

# 헬스 체크 실행
python scripts/run_health_check.py

# 예상: REDIS = DISABLED, 나머지 OK
```

**예상 결과**: ✅ REDIS 상태가 DISABLED로 표시됨

#### 2. Redis 활성화 시나리오

```bash
# Redis 서버 시작
docker-compose -f infra/docker-compose.yml up -d redis
sleep 3

# config/base.yml에서 redis.enabled: true로 변경
sed -i 's/enabled: false/enabled: true/' config/base.yml

# 헬스 체크 실행
python scripts/run_health_check.py

# 예상: REDIS = OK
```

**예상 결과**: ✅ REDIS 상태가 OK로 표시됨

#### 3. Redis 다운 시나리오

```bash
# Redis 서버 중지
docker-compose -f infra/docker-compose.yml stop redis

# 헬스 체크 실행
python scripts/run_health_check.py

# 예상: REDIS = ERROR, 종료 코드 1
```

**예상 결과**: ✅ REDIS 상태가 ERROR로 표시되고, 종료 코드 1 반환

#### 4. FX 환율 Redis 발행 확인

```bash
# Redis 서버 시작
docker-compose -f infra/docker-compose.yml up -d redis

# config/base.yml에서 redis.enabled: true로 변경
sed -i 's/enabled: false/enabled: true/' config/base.yml

# Paper 실행 (짧은 시간)
timeout 5 python scripts/run_paper.py || true

# Redis에서 FX 환율 확인
docker-compose -f infra/docker-compose.yml exec redis redis-cli KEYS "arb:fx:*"
docker-compose -f infra/docker-compose.yml exec redis redis-cli GET "arb:fx:usdkrw"

# 예상: arb:fx:usdkrw 키에 1350.0 값 저장됨
```

**예상 결과**: ✅ Redis에 FX 환율이 저장됨

### 주의사항

#### 1. redis-py 의존성

Redis 기능을 사용하려면 redis-py 설치 필요:
```bash
pip install redis
```

Redis 비활성화 시에는 설치 불필요.

#### 2. Redis 설정

docker-compose 기본 설정:
- Host: localhost
- Port: 6379
- Database: 0

프로덕션 환경에서는 환경 변수로 관리:
```bash
export REDIS_URL="redis://user:pass@host:6379/0"
# config/base.yml에서 redis.url: ${REDIS_URL} 사용
```

#### 3. TTL 관리

- FX 환율 TTL: config.redis.health_ttl_seconds (기본값: 60초)
- Heartbeat TTL: config.redis.health_ttl_seconds (기본값: 60초)
- 스프레드 스냅샷 TTL: 60초 (고정)

TTL 만료 후 키는 자동으로 삭제됨.

### 알려진 제한사항

1. **FX 읽기 미구현**: 현재는 Redis에 쓰기만 함 (읽기는 향후)
2. **모니터링 미구현**: Prometheus/Grafana는 PHASE D3에서 구현
3. **배경 작업 미구현**: 헬스 체크는 수동 호출만 가능 (스케줄러는 D3)

### 다음 단계 (MODULE D3)

- Prometheus 메트릭 수집
- Grafana 대시보드
- Docker-compose app 컨테이너 추가
- 백그라운드 헬스 모니터링 스케줄러

---

## MODULE D3 – Docker App Integration & Monitoring Skeleton

### 목표

1. **Dockerized App Container**
   - arbitrage-app 서비스 추가
   - Paper mode only (실거래 없음)
   - 안전한 daemon-like 루프

2. **Monitoring Skeleton**
   - Redis Exporter (metrics 수집)
   - PostgreSQL Exporter (DB 메트릭)
   - Prometheus/Grafana 준비 (D4에서 활성화)

3. **메트릭 수집 기반 구축**
   - 경량 메트릭 모듈
   - Prometheus 텍스트 형식 지원
   - 향후 HTTP /metrics 엔드포인트로 확장

### 구현 내용

#### 1. Dockerfile (새 파일)

**특징**:
- Python 3.11-slim 기반
- 시스템 패키지 설치 (psycopg2 등)
- requirements.txt 기반 의존성 설치
- 헬스 체크 포함

**사용법**:
```bash
docker build -t arbitrage-app .
docker run --rm arbitrage-app python scripts/run_health_check.py
```

#### 2. docker-compose.yml – 업데이트

**추가된 서비스**:

**arbitrage-app**:
- 빌드: Dockerfile 기반
- 환경: PYTHONUNBUFFERED, APP_ENV
- 의존성: postgres, redis (healthcheck 대기)
- 볼륨: 코드 바인드 마운트, data, logs 디렉토리
- 명령: python scripts/run_bot_service.py
- 헬스 체크: 30초 간격

**redis-exporter**:
- 이미지: oliver006/redis_exporter:latest
- 포트: 9121
- 환경: REDIS_ADDR=redis:6379
- 목적: Redis 메트릭 수집 (D4에서 Prometheus로 수집)

**postgres-exporter**:
- 이미지: prometheuscommunity/postgres-exporter:latest
- 포트: 9187
- 환경: DATA_SOURCE_NAME (PostgreSQL 연결)
- 목적: PostgreSQL 메트릭 수집 (D4에서 Prometheus로 수집)

#### 3. scripts/run_bot_service.py (새 파일)

**특징**:
- 안전한 daemon-like 루프
- Paper mode only (실거래 없음)
- Graceful shutdown (Ctrl+C, SIGTERM)
- Redis heartbeat 작성 (선택적)
- 메트릭 수집 및 로깅

**책임**:
1. 설정 파일 로드
2. 저장소 초기화 (CSV 또는 PostgreSQL)
3. Redis 클라이언트 초기화
4. 메트릭 수집기 초기화
5. 반복 루프:
   - Redis heartbeat 작성
   - 메트릭 수집
   - 상태 로깅
   - 대기 (기본값: 30초)

**사용법**:
```bash
python scripts/run_bot_service.py
python scripts/run_bot_service.py --config config/base.yml --interval 10 --verbose
```

**로그 예시**:
```
[BOT] Initializing bot service...
[BOT] Storage initialized: CsvStorage
[BOT] Redis client initialized (available=False)
[BOT] Metrics collector initialized
[BOT] Config: fx_mode=static storage_backend=csv redis_enabled=False
[BOT] Starting bot service loop (interval=30s, mode=paper)
[BOT] [METRICS] pnl=0₩ win_rate=0.0% trades=0 open_pos=0 daily_pnl=0₩ avg_duration=0s
[BOT] heartbeat - symbols=['BTC', 'ETH'] backend=csv redis=disabled
...
[BOT] Shutting down (completed 10 iterations)
```

#### 4. arbitrage/metrics.py (새 파일)

**특징**:
- 메모리 기반 메트릭 저장
- Prometheus 텍스트 형식 지원
- 경량 구현 (D3 스켈레톤)

**클래스/함수**:

**MetricSnapshot**:
```python
@dataclass
class MetricSnapshot:
    timestamp: datetime
    total_pnl_krw: float
    win_rate: float
    num_trades: int
    num_open_positions: int
    daily_pnl_krw: float
    avg_trade_duration_seconds: int
```

**함수**:
- `compute_basic_metrics()`: 기본 메트릭 계산 (D3: 스텁, D4: 실제 구현)
- `to_prometheus_format()`: Prometheus 텍스트 형식 변환
- `format_metrics_summary()`: 로그용 요약 포맷팅
- `get_metrics_collector()`: 싱글톤 반환

**Prometheus 형식 예시**:
```
# HELP arbitrage_total_pnl_krw Total PnL in KRW
# TYPE arbitrage_total_pnl_krw gauge
arbitrage_total_pnl_krw 0.0

# HELP arbitrage_win_rate Win rate (0.0 ~ 1.0)
# TYPE arbitrage_win_rate gauge
arbitrage_win_rate 0.0

...
```

### 테스트 & 검증

#### 1. 로컬 모드 (Docker 없음)

```bash
# 헬스 체크 (기존 기능)
python scripts/run_health_check.py

# Paper 실행 (기존 기능)
timeout 5 python scripts/run_paper.py || true

# 예상 결과: 기존과 동일하게 동작
```

**예상 결과**: ✅ 기존 워크플로우 100% 유지

#### 2. Docker 이미지 빌드

```bash
# 이미지 빌드
docker build -t arbitrage-app .

# 빌드 확인
docker images | grep arbitrage-app

# 예상 결과: arbitrage-app 이미지 생성됨
```

**예상 결과**: ✅ 이미지 빌드 성공

#### 3. Docker-compose 스택 실행

```bash
# 전체 스택 시작
cd infra
docker-compose up -d

# 서비스 상태 확인
docker-compose ps

# 예상 결과:
# NAME                    STATUS
# arbitrage-postgres      Up (healthy)
# arbitrage-redis         Up (healthy)
# arbitrage-adminer       Up
# arbitrage-app           Up
# arbitrage-redis-exporter Up
# arbitrage-postgres-exporter Up
```

**예상 결과**: ✅ 모든 서비스 정상 실행

#### 4. 봇 서비스 로그 확인

```bash
# 로그 확인 (실시간)
docker-compose logs -f arbitrage-app

# 예상 로그:
# [BOT] Initializing bot service...
# [BOT] Storage initialized: CsvStorage
# [BOT] Redis client initialized (available=False)
# [BOT] Starting bot service loop (interval=30s, mode=paper)
# [BOT] [METRICS] pnl=0₩ win_rate=0.0% trades=0 open_pos=0 daily_pnl=0₩ avg_duration=0s
# ...
```

**예상 결과**: ✅ 봇 서비스 정상 실행 및 로깅

#### 5. Redis Heartbeat 확인

```bash
# Redis 접속
docker-compose exec redis redis-cli

# Heartbeat 확인
> KEYS "arb:heartbeat:*"
1) "arb:heartbeat:bot_service"

> GET "arb:heartbeat:bot_service"
"2025-11-15T10:30:45.123456+00:00"

> TTL "arb:heartbeat:bot_service"
60
```

**예상 결과**: ✅ Redis에 bot_service heartbeat 저장됨

#### 6. Exporter 메트릭 확인

```bash
# Redis Exporter 메트릭
curl http://localhost:9121/metrics | head -20

# PostgreSQL Exporter 메트릭
curl http://localhost:9187/metrics | head -20

# 예상 결과: Prometheus 형식의 메트릭 출력
```

**예상 결과**: ✅ Exporter에서 메트릭 수집 가능

#### 7. 서비스 종료

```bash
# 서비스 종료
docker-compose down

# 예상 결과: 모든 컨테이너 정상 종료
```

**예상 결과**: ✅ 서비스 정상 종료

### 주의사항

#### 1. Paper Mode Only

- 실거래 API 없음 (D4에서 추가)
- 모든 거래는 시뮬레이션
- 실제 자금 위험 없음

#### 2. 로컬 개발 모드

- 코드 바인드 마운트 (수정 시 자동 반영)
- 데이터/로그 디렉토리 마운트
- 개발 편의성 최적화

#### 3. 모니터링 준비

- Redis/PostgreSQL Exporter 포함
- Prometheus/Grafana는 D4에서 활성화
- 메트릭 API는 D4에서 구현

### 알려진 제한사항

1. **메트릭 계산 미구현**: 현재는 0 또는 기본값 (D4에서 구현)
2. **HTTP /metrics 엔드포인트 없음**: D4에서 추가
3. **실거래 로직 없음**: D4에서 추가
4. **Prometheus/Grafana 비활성화**: D4에서 활성화

### 다음 단계 (MODULE D4)

- Prometheus 활성화 및 설정
- Grafana 대시보드 구성
- HTTP /metrics 엔드포인트 구현
- 실제 메트릭 계산 로직
- Live API 연동 준비

---

## MODULE D4 – Live API Integration & Monitoring Stack

### 목표

1. **Live API 통합**
   - Upbit REST/WebSocket 모듈
   - Binance REST/WebSocket 모듈
   - Mock mode (credentials 없을 때 자동 전환)
   - Rate limiting 내장

2. **메트릭 서버 구현**
   - FastAPI 기반 HTTP 서버
   - /metrics 엔드포인트 (Prometheus 형식)
   - 실시간 메트릭 계산

3. **Prometheus + Grafana 통합**
   - docker-compose에 prometheus, grafana 서비스 추가
   - prometheus.yml 설정
   - 자동 데이터 수집

4. **Bot Service 확장**
   - Live 모드 지원
   - 메트릭 서버 통합
   - Redis heartbeat 확장

### 구현 내용

#### 1. arbitrage/live_api.py (새 파일)

**특징**:
- LiveAPIBase 추상 클래스
- OrderRequest, OrderResponse, TickerData 데이터클래스
- MockLiveAPI (테스트용)
- get_live_api() 팩토리 함수

**메서드**:
- connect() / disconnect()
- get_ticker(symbol)
- place_order(order)
- cancel_order(order_id)
- get_balance()
- get_open_orders(symbol)

#### 2. arbitrage/upbit_live.py (새 파일)

**특징**:
- UpbitLiveAPI 클래스 (LiveAPIBase 상속)
- Mock mode 지원
- Rate limiting 내장
- 실제 구현은 D4 확장에서 추가

#### 3. arbitrage/binance_live.py (새 파일)

**특징**:
- BinanceLiveAPI 클래스 (LiveAPIBase 상속)
- Mock mode 지원
- Rate limiting 내장
- 실제 구현은 D4 확장에서 추가

#### 4. arbitrage/metrics_server.py (새 파일)

**특징**:
- FastAPI 기반 HTTP 서버
- /metrics 엔드포인트 (Prometheus 형식)
- /health 헬스 체크
- 선택적 import (FastAPI 없으면 비활성화)

#### 5. scripts/run_live.py (업데이트)

**특징**:
- Live 모드 실행 스크립트
- Mock mode 자동 활성화
- 메트릭 서버 통합
- --once, --interval, --mock 옵션

**사용법**:
```bash
python scripts/run_live.py --once --mock
python scripts/run_live.py --interval 10
```

#### 6. config/live.yml (새 파일)

**구성**:
- upbit: API 설정 (enabled, api_key, api_secret, rate_limit)
- binance: API 설정
- mode: paper | backtest | live
- mock_mode: 자동 mock 전환
- metrics_server: 포트, 호스트 설정

#### 7. infra/prometheus.yml (새 파일)

**설정**:
- Global scrape interval: 15s
- Jobs:
  - prometheus (자신)
  - redis-exporter (9121)
  - postgres-exporter (9187)
  - arbitrage-metrics (8000)

#### 8. infra/docker-compose.yml (업데이트)

**추가 서비스**:
- prometheus: 메트릭 수집 (포트 9090)
- grafana: 대시보드 (포트 3000)

**추가 volumes**:
- prometheus_data
- grafana_data

### 테스트 & 검증

#### 1. Live API 테스트

```bash
# Mock 모드 테스트
python scripts/run_live.py --once --mock

# 예상 출력:
# [LIVE] Starting Live Trading Service (PHASE D4)
# [LIVE] Storage initialized: CsvStorage
# [LIVE] Upbit API initialized (mock=True)
# [LIVE] Binance API initialized (mock=True)
# [LIVE] Metrics collector initialized
# [LIVE] Starting loop (interval=30s, once=True, mock=True)
# [LIVE] Upbit BTC-KRW: bid=50000000.0, ask=50001000.0
# [LIVE] Binance BTCUSDT: bid=50000.0, ask=50010.0
# [LIVE] Metrics: [METRICS] pnl=0₩ win_rate=0.0% trades=0 open_pos=0 daily_pnl=0₩ avg_duration=0s
# [LIVE] Exiting (--once mode)
# [LIVE] Shutting down (completed 1 iterations)
```

#### 2. Docker-compose 스택 테스트

```bash
# 스택 시작
docker-compose -f infra/docker-compose.yml up -d

# 서비스 상태 확인
docker-compose -f infra/docker-compose.yml ps

# 예상 결과:
# NAME                        STATUS
# arbitrage-prometheus        Up (healthy)
# arbitrage-grafana           Up (healthy)
# arbitrage-app               Up
# arbitrage-redis             Up (healthy)
# arbitrage-postgres          Up (healthy)
# redis-exporter              Up
# postgres-exporter           Up
# adminer                     Up
```

#### 3. Prometheus 메트릭 확인

```bash
# Prometheus 접속
curl http://localhost:9090/api/v1/targets

# 예상: 모든 targets healthy

# 메트릭 조회
curl http://localhost:9090/api/v1/query?query=up
```

#### 4. Grafana 접속

```bash
# Grafana 접속
http://localhost:3000

# 기본 계정: admin / admin
# 데이터 소스 자동 설정: Prometheus (http://prometheus:9090)
```

#### 5. Arbitrage 메트릭 확인

```bash
# 메트릭 엔드포인트 확인
curl http://localhost:8000/metrics

# 예상 출력:
# # HELP arbitrage_total_pnl_krw Total PnL in KRW
# # TYPE arbitrage_total_pnl_krw gauge
# arbitrage_total_pnl_krw 0.0
# ...
```

### 주의사항

#### 1. Mock Mode

- API KEY가 없으면 자동으로 mock mode 활성화
- Mock mode에서는 실제 거래 없음
- 테스트 및 개발용

#### 2. FastAPI 선택적 설치

- FastAPI 없으면 메트릭 서버 비활성화
- 기본 기능은 정상 작동

#### 3. Rate Limiting

- Upbit: 10 req/s (기본값)
- Binance: 10 req/s (기본값)
- 설정에서 조정 가능

### 알려진 제한사항

1. **실제 API 구현 미완성**: 현재는 mock/스텁 상태
2. **WebSocket 미구현**: REST API만 구현
3. **주문 실행 미완성**: 주문 로직은 D4 확장에서 추가
4. **Grafana 대시보드 템플릿 미제공**: D4 확장에서 추가

### 다음 단계 (MODULE D5 예정)

- 실제 Upbit/Binance API 구현
- WebSocket 실시간 시세 수집
- 주문 실행 로직 완성
- Grafana 대시보드 커스터마이징
- 실거래 모드 안정화

---

## 참고

- **docs/DB_SCHEMA.md**: PostgreSQL 테이블 설계
- **infra/docker-compose.yml**: Docker 인프라 구성
- **config/base.yml**: 설정 파일
