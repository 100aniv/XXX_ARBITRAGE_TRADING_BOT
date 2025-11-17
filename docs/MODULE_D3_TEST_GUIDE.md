# MODULE D3 – Docker App Integration & Monitoring Skeleton
## 테스트 & 검증 가이드

---

## 테스트 시나리오

### 시나리오 1: 로컬 모드 (Docker 없음) – 기존 기능 유지

**목표**: Docker 추가 후에도 기존 로컬 워크플로우가 100% 유지되는지 확인

**명령어**:
```bash
# 1. 헬스 체크 실행
python scripts/run_health_check.py

# 2. 출력 확인
# 예상:
# ────────────────────────────────────────────────────────────
# Arbitrage-Lite: Health Check Report
# ────────────────────────────────────────────────────────────
# 
# [REDIS     ] ⊘  DISABLED  Redis disabled in config
# [POSTGRES  ] ⊘  SKIP      Backend is 'csv', not postgres
# [CSV       ] ✅ OK        CSV storage at data
# 
# Overall:       ✅ OK
# ────────────────────────────────────────────────────────────

# 3. Paper 실행 (짧은 시간)
timeout 5 python scripts/run_paper.py || true

# 4. CSV 파일 생성 확인
ls -la data/positions.csv
```

**예상 결과**:
- ✅ 헬스 체크 정상 실행
- ✅ Paper 모드 정상 실행
- ✅ CSV 파일 생성됨
- ✅ 기존과 동일하게 동작

---

### 시나리오 2: Docker 이미지 빌드

**목표**: Dockerfile이 정상적으로 빌드되는지 확인

**명령어**:
```bash
# 1. 이미지 빌드
docker build -t arbitrage-app .

# 2. 빌드 진행 상황 확인
# 예상 출력:
# Sending build context to Docker daemon  ...
# Step 1/10 : FROM python:3.11-slim
# ...
# Successfully built <image_id>
# Successfully tagged arbitrage-app:latest

# 3. 이미지 확인
docker images | grep arbitrage-app

# 예상 출력:
# REPOSITORY      TAG       IMAGE ID       CREATED        SIZE
# arbitrage-app   latest    <image_id>     <time>         <size>

# 4. 이미지에서 헬스 체크 실행
docker run --rm arbitrage-app python scripts/run_health_check.py

# 예상 출력: 헬스 체크 결과 (CSV OK, Redis/Postgres SKIP)
```

**예상 결과**:
- ✅ 이미지 빌드 성공
- ✅ 이미지 태그 정상
- ✅ 컨테이너에서 헬스 체크 실행 가능

---

### 시나리오 3: Docker-compose 스택 시작

**목표**: 모든 서비스가 정상적으로 시작되는지 확인

**명령어**:
```bash
# 1. 프로젝트 루트에서 docker-compose 디렉토리로 이동
cd infra

# 2. 전체 스택 시작
docker-compose up -d

# 3. 서비스 상태 확인
docker-compose ps

# 예상 출력:
# NAME                        COMMAND                  SERVICE             STATUS
# arbitrage-postgres          "postgres"               postgres            Up (healthy)
# arbitrage-redis             "redis-server ..."       redis               Up (healthy)
# arbitrage-adminer           "entrypoint.sh ..."      adminer             Up
# arbitrage-app               "python scripts/..."     arbitrage-app       Up
# arbitrage-redis-exporter    "/redis_exporter"        redis-exporter      Up
# arbitrage-postgres-exporter "/bin/postgres_exporter" postgres-exporter   Up

# 4. 각 서비스 상태 확인
docker-compose logs --tail=20

# 5. 특정 서비스 로그 확인
docker-compose logs -f arbitrage-app
```

**예상 결과**:
- ✅ 모든 서비스 Up 상태
- ✅ postgres, redis, adminer, arbitrage-app 모두 실행 중
- ✅ redis-exporter, postgres-exporter 실행 중

---

### 시나리오 4: 봇 서비스 로그 확인

**목표**: 봇 서비스가 정상적으로 실행되고 로그가 출력되는지 확인

**명령어**:
```bash
# 1. 봇 서비스 로그 실시간 확인
docker-compose logs -f arbitrage-app

# 2. 예상 로그:
# arbitrage-app  | 2025-11-15 10:30:45,123 [INFO] arbitrage.bot_service: [BOT] Initializing bot service...
# arbitrage-app  | 2025-11-15 10:30:45,234 [INFO] arbitrage.bot_service: [BOT] Storage initialized: CsvStorage
# arbitrage-app  | 2025-11-15 10:30:45,345 [INFO] arbitrage.bot_service: [BOT] Redis client initialized (available=False)
# arbitrage-app  | 2025-11-15 10:30:45,456 [INFO] arbitrage.bot_service: [BOT] Metrics collector initialized
# arbitrage-app  | 2025-11-15 10:30:45,567 [INFO] arbitrage.bot_service: [BOT] Config: fx_mode=static storage_backend=csv redis_enabled=False
# arbitrage-app  | 2025-11-15 10:30:45,678 [INFO] arbitrage.bot_service: [BOT] Starting bot service loop (interval=30s, mode=paper)
# arbitrage-app  | 2025-11-15 10:30:45,789 [INFO] arbitrage.bot_service: [BOT] [METRICS] pnl=0₩ win_rate=0.0% trades=0 open_pos=0 daily_pnl=0₩ avg_duration=0s
# arbitrage-app  | 2025-11-15 10:30:45,890 [DEBUG] arbitrage.bot_service: [BOT] heartbeat - symbols=['BTC', 'ETH'] backend=csv redis=disabled
# ...

# 3. 로그 중지 (Ctrl+C)
```

**예상 결과**:
- ✅ 봇 서비스 정상 초기화
- ✅ 저장소, Redis, 메트릭 수집기 초기화됨
- ✅ 루프 시작 및 메트릭 출력
- ✅ 30초 간격으로 반복 실행

---

### 시나리오 5: Redis Heartbeat 확인

**목표**: 봇 서비스가 Redis에 heartbeat를 작성하는지 확인

**전제조건**:
- Docker-compose 스택 실행 중
- config/base.yml에서 redis.enabled: true로 설정

**명령어**:
```bash
# 1. config/base.yml 수정 (Redis 활성화)
sed -i 's/enabled: false/enabled: true/' ../config/base.yml

# 2. 봇 서비스 재시작
docker-compose restart arbitrage-app

# 3. 로그 확인 (Redis 연결 확인)
docker-compose logs arbitrage-app | grep -i redis

# 예상 출력:
# [BOT] Redis client initialized (available=True)

# 4. Redis 접속
docker-compose exec redis redis-cli

# 5. Heartbeat 확인
> KEYS "arb:heartbeat:*"
1) "arb:heartbeat:bot_service"

> GET "arb:heartbeat:bot_service"
"2025-11-15T10:30:45.123456+00:00"

> TTL "arb:heartbeat:bot_service"
60

# 6. 시간 경과 후 다시 확인 (TTL 감소)
> TTL "arb:heartbeat:bot_service"
55

# 7. Redis 종료
> exit
```

**예상 결과**:
- ✅ Redis 연결 성공 (available=True)
- ✅ bot_service heartbeat 키 생성됨
- ✅ 타임스탐프 값 저장됨
- ✅ TTL이 60초 이하로 설정됨
- ✅ 시간 경과 시 TTL 감소

**정리**:
```bash
# config 복원
sed -i 's/enabled: true/enabled: false/' ../config/base.yml

# 봇 서비스 재시작
docker-compose restart arbitrage-app
```

---

### 시나리오 6: Exporter 메트릭 확인

**목표**: Redis/PostgreSQL Exporter에서 메트릭이 수집되는지 확인

**명령어**:
```bash
# 1. Redis Exporter 메트릭 확인
curl http://localhost:9121/metrics | head -30

# 예상 출력:
# # HELP redis_up Whether the Redis server is up
# # TYPE redis_up gauge
# redis_up 1
# # HELP redis_connected_clients Number of connected clients
# # TYPE redis_connected_clients gauge
# redis_connected_clients 1
# ...

# 2. PostgreSQL Exporter 메트릭 확인
curl http://localhost:9187/metrics | head -30

# 예상 출력:
# # HELP pg_up Whether the last scrape of the PostgreSQL server was successful
# # TYPE pg_up gauge
# pg_up 1
# # HELP pg_static_build_info Statically set build info metric
# # TYPE pg_static_build_info gauge
# pg_static_build_info{...} 1
# ...

# 3. 메트릭 수 확인
curl http://localhost:9121/metrics | wc -l
curl http://localhost:9187/metrics | wc -l

# 예상: 각각 100+ 라인
```

**예상 결과**:
- ✅ Redis Exporter에서 메트릭 수집 가능
- ✅ PostgreSQL Exporter에서 메트릭 수집 가능
- ✅ Prometheus 형식의 메트릭 출력

---

### 시나리오 7: 봇 서비스 로컬 실행

**목표**: Docker 없이 로컬에서 봇 서비스 실행 가능한지 확인

**명령어**:
```bash
# 1. 프로젝트 루트로 이동
cd ..

# 2. 봇 서비스 실행 (짧은 시간)
timeout 10 python scripts/run_bot_service.py --interval 5 --verbose || true

# 3. 예상 출력:
# 2025-11-15 10:30:45,123 [INFO] arbitrage.bot_service: [BOT] Initializing bot service...
# 2025-11-15 10:30:45,234 [INFO] arbitrage.bot_service: [BOT] Storage initialized: CsvStorage
# 2025-11-15 10:30:45,345 [INFO] arbitrage.bot_service: [BOT] Redis client initialized (available=False)
# 2025-11-15 10:30:45,456 [INFO] arbitrage.bot_service: [BOT] Metrics collector initialized
# 2025-11-15 10:30:45,567 [INFO] arbitrage.bot_service: [BOT] Config: fx_mode=static storage_backend=csv redis_enabled=False
# 2025-11-15 10:30:45,678 [INFO] arbitrage.bot_service: [BOT] Starting bot service loop (interval=5s, mode=paper)
# 2025-11-15 10:30:45,789 [INFO] arbitrage.bot_service: [BOT] [METRICS] pnl=0₩ win_rate=0.0% trades=0 open_pos=0 daily_pnl=0₩ avg_duration=0s
# 2025-11-15 10:30:50,890 [INFO] arbitrage.bot_service: [BOT] [METRICS] pnl=0₩ win_rate=0.0% trades=0 open_pos=0 daily_pnl=0₩ avg_duration=0s
# ...
# 2025-11-15 10:31:00,000 [INFO] arbitrage.bot_service: [BOT] Shutting down (completed 2 iterations)
```

**예상 결과**:
- ✅ 봇 서비스 정상 초기화
- ✅ 5초 간격으로 메트릭 출력
- ✅ Graceful shutdown (timeout 후 정상 종료)

---

### 시나리오 8: 서비스 종료 및 정리

**목표**: 모든 서비스가 정상적으로 종료되는지 확인

**명령어**:
```bash
# 1. 프로젝트 루트에서 docker-compose 디렉토리로 이동
cd infra

# 2. 서비스 상태 확인
docker-compose ps

# 3. 서비스 종료
docker-compose down

# 4. 예상 출력:
# Stopping arbitrage-app ... done
# Stopping arbitrage-postgres-exporter ... done
# Stopping arbitrage-redis-exporter ... done
# Stopping arbitrage-adminer ... done
# Stopping arbitrage-redis ... done
# Stopping arbitrage-postgres ... done
# Removing arbitrage-app ... done
# Removing arbitrage-postgres-exporter ... done
# Removing arbitrage-redis-exporter ... done
# Removing arbitrage-adminer ... done
# Removing arbitrage-redis ... done
# Removing arbitrage-postgres ... done
# Removing network arbitrage_arbitrage-network

# 5. 서비스 종료 확인
docker-compose ps

# 예상 출력: (비어있음)
```

**예상 결과**:
- ✅ 모든 서비스 정상 종료
- ✅ 컨테이너 제거됨
- ✅ 네트워크 제거됨

---

## 빠른 테스트 (한 번에 실행)

```bash
#!/bin/bash

echo "=========================================="
echo "MODULE D3 – Docker App Integration Test"
echo "=========================================="

# 테스트 1: 로컬 모드 (Docker 없음)
echo -e "\n[TEST 1] 로컬 모드 – 헬스 체크"
python scripts/run_health_check.py | grep -E "(Overall|REDIS|POSTGRES|CSV)"

# 테스트 2: Docker 이미지 빌드
echo -e "\n[TEST 2] Docker 이미지 빌드"
docker build -t arbitrage-app . > /dev/null 2>&1 && echo "✅ 이미지 빌드 성공" || echo "❌ 이미지 빌드 실패"

# 테스트 3: Docker-compose 스택 시작
echo -e "\n[TEST 3] Docker-compose 스택 시작"
cd infra
docker-compose up -d > /dev/null 2>&1
sleep 10

# 테스트 4: 서비스 상태 확인
echo -e "\n[TEST 4] 서비스 상태 확인"
docker-compose ps | grep -E "(arbitrage-app|arbitrage-postgres|arbitrage-redis)"

# 테스트 5: 봇 서비스 로그 확인
echo -e "\n[TEST 5] 봇 서비스 로그 (최근 5줄)"
docker-compose logs --tail=5 arbitrage-app

# 테스트 6: Redis Heartbeat 확인
echo -e "\n[TEST 6] Redis Heartbeat 확인"
docker-compose exec redis redis-cli KEYS "arb:heartbeat:*" 2>/dev/null || echo "⊘ Redis 비활성화"

# 테스트 7: Exporter 메트릭 확인
echo -e "\n[TEST 7] Exporter 메트릭 확인"
curl -s http://localhost:9121/metrics | head -3 && echo "✅ Redis Exporter OK" || echo "❌ Redis Exporter 실패"
curl -s http://localhost:9187/metrics | head -3 && echo "✅ PostgreSQL Exporter OK" || echo "❌ PostgreSQL Exporter 실패"

# 정리
echo -e "\n[CLEANUP] 서비스 종료"
docker-compose down > /dev/null 2>&1
cd ..

echo -e "\n=========================================="
echo "테스트 완료"
echo "=========================================="
```

---

## 검증 체크리스트

### Dockerfile
- [ ] Python 3.11-slim 기반
- [ ] 시스템 패키지 설치 (gcc, postgresql-client)
- [ ] requirements.txt 설치
- [ ] 소스 코드 복사
- [ ] 환경 변수 설정
- [ ] 헬스 체크 정의
- [ ] CMD 설정

### docker-compose.yml
- [ ] arbitrage-app 서비스 추가
- [ ] redis-exporter 서비스 추가
- [ ] postgres-exporter 서비스 추가
- [ ] 모든 서비스 depends_on 설정
- [ ] 포트 매핑 정의
- [ ] 볼륨 마운트 설정
- [ ] 헬스 체크 정의
- [ ] 네트워크 설정

### scripts/run_bot_service.py
- [ ] 설정 파일 로드
- [ ] 저장소 초기화
- [ ] Redis 클라이언트 초기화
- [ ] 메트릭 수집기 초기화
- [ ] 메인 루프 구현
- [ ] Graceful shutdown (SIGINT, SIGTERM)
- [ ] Redis heartbeat 작성
- [ ] 메트릭 수집 및 로깅
- [ ] 명령줄 인자 처리

### arbitrage/metrics.py
- [ ] MetricSnapshot 데이터클래스
- [ ] compute_basic_metrics() 함수
- [ ] to_prometheus_format() 함수
- [ ] format_metrics_summary() 함수
- [ ] MetricsCollector 클래스
- [ ] get_metrics_collector() 싱글톤

### 문서
- [ ] docs/phase_D_master.md MODULE D3 섹션 추가
- [ ] MODULE_D3_TEST_GUIDE.md 작성
- [ ] docs/ARB_PHASE_INDEX.md 업데이트 (active_module=D3)

---

## 문제 해결

### 문제: Docker 빌드 실패 ("No such file or directory")

**해결책**:
```bash
# 프로젝트 루트에서 빌드
cd /path/to/arbitrage-lite
docker build -t arbitrage-app .
```

### 문제: docker-compose 서비스 시작 실패

**해결책**:
```bash
# 로그 확인
docker-compose logs arbitrage-app

# 이미지 재빌드
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### 문제: "Connection refused" (Redis/PostgreSQL)

**해결책**:
```bash
# 서비스 상태 확인
docker-compose ps

# 헬스 체크 상태 확인
docker-compose exec postgres pg_isready -U arbitrage
docker-compose exec redis redis-cli ping

# 서비스 재시작
docker-compose restart postgres redis
```

### 문제: 포트 충돌 (5432, 6379 등)

**해결책**:
```bash
# 포트 사용 확인
lsof -i :5432
lsof -i :6379

# 기존 서비스 종료
docker-compose down
docker ps -a | grep arbitrage | awk '{print $1}' | xargs docker rm -f
```

---

## 성능 고려사항

### 메모리 사용
- arbitrage-app: ~100MB
- postgres: ~200MB
- redis: ~50MB
- exporters: ~50MB 각각
- **총합**: ~500MB

### CPU 사용
- 봇 서비스: 30초 간격 루프 (거의 사용 안 함)
- exporters: 주기적 메트릭 수집 (미미)

### 디스크 사용
- PostgreSQL 데이터: 초기 ~10MB
- Redis 데이터: 초기 ~1MB
- 로그: 일일 ~10MB

---

## 다음 단계

### MODULE D4 – Live API & Monitoring Stack
- Prometheus 활성화 및 설정
- Grafana 대시보드 구성
- HTTP /metrics 엔드포인트 구현
- 실제 메트릭 계산 로직
- Live API 연동 준비

---

## 참고

- **Dockerfile**: 봇 애플리케이션 컨테이너
- **infra/docker-compose.yml**: 전체 스택 정의
- **scripts/run_bot_service.py**: 봇 서비스 스크립트
- **arbitrage/metrics.py**: 메트릭 수집 모듈
- **docs/phase_D_master.md**: PHASE D 전체 계획
