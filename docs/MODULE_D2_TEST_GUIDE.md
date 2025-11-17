# MODULE D2 – Redis Cache & Health Monitoring
## 테스트 & 검증 가이드

---

## 테스트 시나리오

### 시나리오 1: Redis 비활성화 상태 (기본값)

**목표**: Redis 비활성화 시 모든 기능이 정상 동작하는지 확인

**명령어**:
```bash
# 1. config/base.yml 확인
grep -A 4 "^redis:" config/base.yml
# 출력: enabled: false

# 2. 헬스 체크 실행
python scripts/run_health_check.py

# 3. 출력 확인
# 예상:
# [REDIS     ] ⊘  DISABLED  Redis disabled in config
# [POSTGRES  ] ⊘  SKIP      Backend is 'csv', not postgres
# [CSV       ] ✅ OK        CSV storage at data
# Overall:       ✅ OK
```

**예상 결과**:
- ✅ REDIS 상태가 DISABLED로 표시됨
- ✅ 종료 코드 0 (성공)
- ✅ Paper 모드 정상 실행 (Redis 없이도 동작)

**검증 명령어**:
```bash
# Paper 실행 (짧은 시간)
timeout 5 python scripts/run_paper.py || true

# CSV 파일 생성 확인
ls -la data/positions.csv

# 로그에서 Redis 관련 메시지 없음 확인
```

---

### 시나리오 2: Redis 활성화 & 서버 실행

**목표**: Redis 활성화 시 연결 및 캐시 저장 확인

**전제조건**:
- Docker 설치됨
- redis-py 설치됨: `pip install redis`

**명령어**:
```bash
# 1. Redis 서버 시작
docker-compose -f infra/docker-compose.yml up -d redis
sleep 3

# 2. Redis 연결 확인
docker-compose -f infra/docker-compose.yml exec redis redis-cli ping
# 출력: PONG

# 3. config/base.yml 수정 (Redis 활성화)
sed -i 's/enabled: false/enabled: true/' config/base.yml

# 4. 헬스 체크 실행
python scripts/run_health_check.py

# 5. 출력 확인
# 예상:
# [REDIS     ] ✅ OK       Connected to redis://localhost:6379/0
# [POSTGRES  ] ⊘  SKIP     Backend is 'csv', not postgres
# [CSV       ] ✅ OK       CSV storage at data
# Overall:       ✅ OK
```

**예상 결과**:
- ✅ REDIS 상태가 OK로 표시됨
- ✅ 종료 코드 0 (성공)

**정리**:
```bash
# config 복원
sed -i 's/enabled: true/enabled: false/' config/base.yml

# Redis 서버 중지
docker-compose -f infra/docker-compose.yml stop redis
```

---

### 시나리오 3: Redis 다운 (연결 실패)

**목표**: Redis 서버가 없을 때 에러 처리 확인

**명령어**:
```bash
# 1. config/base.yml에서 redis.enabled: true로 설정
sed -i 's/enabled: false/enabled: true/' config/base.yml

# 2. Redis 서버 미실행 상태에서 헬스 체크 실행
python scripts/run_health_check.py

# 3. 출력 확인
# 예상:
# [REDIS     ] ❌ ERROR    Connection failed: ...
# [POSTGRES  ] ⊘  SKIP     Backend is 'csv', not postgres
# [CSV       ] ✅ OK       CSV storage at data
# Overall:       ❌ ERROR
```

**예상 결과**:
- ✅ REDIS 상태가 ERROR로 표시됨
- ✅ 종료 코드 1 (실패)

**정리**:
```bash
# config 복원
sed -i 's/enabled: true/enabled: false/' config/base.yml
```

---

### 시나리오 4: FX 환율 Redis 발행

**목표**: Paper 실행 중 FX 환율이 Redis에 저장되는지 확인

**명령어**:
```bash
# 1. Redis 서버 시작
docker-compose -f infra/docker-compose.yml up -d redis
sleep 3

# 2. config/base.yml 수정 (Redis 활성화)
sed -i 's/enabled: false/enabled: true/' config/base.yml

# 3. Paper 실행 (짧은 시간)
timeout 5 python scripts/run_paper.py || true

# 4. Redis에서 FX 환율 확인
docker-compose -f infra/docker-compose.yml exec redis redis-cli KEYS "arb:fx:*"
# 출력: 1) "arb:fx:usdkrw"

docker-compose -f infra/docker-compose.yml exec redis redis-cli GET "arb:fx:usdkrw"
# 출력: "1350"

# 5. TTL 확인
docker-compose -f infra/docker-compose.yml exec redis redis-cli TTL "arb:fx:usdkrw"
# 출력: 60 (또는 그 이하)
```

**예상 결과**:
- ✅ Redis에 `arb:fx:usdkrw` 키 생성됨
- ✅ 값이 1350 (또는 설정된 환율값)
- ✅ TTL이 60초 이하

**정리**:
```bash
# config 복원
sed -i 's/enabled: true/enabled: false/' config/base.yml

# Redis 서버 중지
docker-compose -f infra/docker-compose.yml stop redis
```

---

### 시나리오 5: redis-py 미설치 상태

**목표**: redis-py 미설치 시 graceful fallback 확인

**명령어**:
```bash
# 1. redis-py 임시 제거 (가상환경에서만)
pip uninstall -y redis

# 2. config/base.yml에서 redis.enabled: true로 설정
sed -i 's/enabled: false/enabled: true/' config/base.yml

# 3. 헬스 체크 실행
python scripts/run_health_check.py

# 4. 출력 확인
# 예상:
# [REDIS     ] ❌ ERROR    redis-py not installed (pip install redis)
# [POSTGRES  ] ⊘  SKIP     Backend is 'csv', not postgres
# [CSV       ] ✅ OK       CSV storage at data
# Overall:       ❌ ERROR
```

**예상 결과**:
- ✅ 명확한 에러 메시지 출력
- ✅ 종료 코드 1 (실패)

**정리**:
```bash
# redis-py 복원
pip install redis

# config 복원
sed -i 's/enabled: true/enabled: false/' config/base.yml
```

---

### 시나리오 6: PostgreSQL 연결 상태 확인

**목표**: PostgreSQL 연결 상태 확인 기능 검증

**명령어**:
```bash
# 1. PostgreSQL 서버 시작
docker-compose -f infra/docker-compose.yml up -d postgres
sleep 10

# 2. config/base.yml 수정 (backend: postgres)
sed -i 's/backend: csv/backend: postgres/' config/base.yml

# 3. 헬스 체크 실행
python scripts/run_health_check.py

# 4. 출력 확인
# 예상:
# [REDIS     ] ⊘  DISABLED  Redis disabled in config
# [POSTGRES  ] ✅ OK        Connected to localhost:5432/arbitrage
# [CSV       ] ⊘  SKIP      Backend is 'postgres', not csv
# Overall:       ✅ OK
```

**예상 결과**:
- ✅ POSTGRES 상태가 OK로 표시됨
- ✅ CSV 상태가 SKIP으로 표시됨

**정리**:
```bash
# config 복원
sed -i 's/backend: postgres/backend: csv/' config/base.yml

# PostgreSQL 서버 중지
docker-compose -f infra/docker-compose.yml stop postgres
```

---

## 빠른 테스트 (한 번에 실행)

```bash
#!/bin/bash

echo "=========================================="
echo "MODULE D2 – Redis Cache Test Suite"
echo "=========================================="

# 테스트 1: Redis 비활성화
echo -e "\n[TEST 1] Redis 비활성화 상태"
grep "enabled:" config/base.yml
python scripts/run_health_check.py | grep -E "(REDIS|Overall)"

# 테스트 2: Redis 활성화
echo -e "\n[TEST 2] Redis 활성화 상태"
docker-compose -f infra/docker-compose.yml up -d redis
sleep 3
sed -i 's/enabled: false/enabled: true/' config/base.yml
python scripts/run_health_check.py | grep -E "(REDIS|Overall)"

# 테스트 3: FX 환율 발행
echo -e "\n[TEST 3] FX 환율 Redis 발행"
timeout 5 python scripts/run_paper.py || true
docker-compose -f infra/docker-compose.yml exec redis redis-cli GET "arb:fx:usdkrw"

# 정리
echo -e "\n[CLEANUP] 설정 복원"
sed -i 's/enabled: true/enabled: false/' config/base.yml
docker-compose -f infra/docker-compose.yml stop redis

echo -e "\n=========================================="
echo "테스트 완료"
echo "=========================================="
```

---

## 검증 체크리스트

### Redis 클라이언트 구현
- [ ] RedisClient 클래스 정의됨
- [ ] redis-py 지연 import 구현됨
- [ ] 연결 실패 시 graceful fallback
- [ ] set_fx_rate() 구현됨
- [ ] get_fx_rate() 구현됨
- [ ] set_heartbeat() 구현됨
- [ ] get_heartbeat() 구현됨
- [ ] set_spread_snapshot() 구현됨
- [ ] get_spread_snapshot() 구현됨
- [ ] ping() 구현됨

### 헬스 모니터링 모듈
- [ ] HealthStatus 데이터클래스 정의됨
- [ ] check_redis() 함수 구현됨
- [ ] check_postgres() 함수 구현됨
- [ ] check_csv_storage() 함수 구현됨
- [ ] aggregate_status() 함수 구현됨
- [ ] format_health_report() 함수 구현됨

### 헬스 체크 스크립트
- [ ] run_health_check.py 작성됨
- [ ] 설정 파일 로드 기능
- [ ] 모든 컴포넌트 체크 실행
- [ ] 인간 친화적 리포트 출력
- [ ] 종료 코드 반환 (0=OK, 1=ERROR)

### FX 모듈 통합
- [ ] _publish_fx_to_redis() 함수 추가됨
- [ ] get_usdkrw()에서 Redis 발행 호출
- [ ] 기존 동작 100% 유지 (Redis 비활성화 시)

### 설정 파일
- [ ] config/base.yml에 redis 섹션 추가
- [ ] redis.enabled 설정
- [ ] redis.url 설정
- [ ] redis.prefix 설정
- [ ] redis.health_ttl_seconds 설정

### 문서
- [ ] docs/REDIS_KEYS.md 작성됨
- [ ] docs/phase_D_master.md 업데이트됨
- [ ] MODULE D2 섹션 상세 설명
- [ ] 테스트 시나리오 문서화
- [ ] docs/ARB_PHASE_INDEX.md 업데이트됨

---

## 문제 해결

### 문제: "redis-py is not installed"

**해결책**:
```bash
pip install redis
```

### 문제: "Failed to connect to Redis: Connection refused"

**해결책**:
```bash
# Redis 서버 시작
docker-compose -f infra/docker-compose.yml up -d redis
sleep 3

# 연결 확인
docker-compose -f infra/docker-compose.yml exec redis redis-cli ping
```

### 문제: "permission denied" (헬스 체크 스크립트)

**해결책**:
```bash
chmod +x scripts/run_health_check.py
```

### 문제: "No module named 'arbitrage'"

**해결책**:
```bash
# 프로젝트 루트에서 실행
cd /path/to/arbitrage-lite
python scripts/run_health_check.py
```

---

## 성능 고려사항

### Redis 활성화 시
- FX 환율 조회 시 Redis에 자동 저장 (비동기 아님)
- 저장 실패 시 로그만 출력 (에러 아님)
- Paper 모드 성능 영향 미미

### Redis 비활성화 시
- 모든 Redis 작업 스킵
- 성능 영향 없음
- 기존 CSV 모드와 동일

---

## 다음 단계

### MODULE D3 – Docker-compose App Integration
- Prometheus 메트릭 수집
- Grafana 대시보드
- arbitrage-app 컨테이너 추가
- 백그라운드 헬스 모니터링 스케줄러

---

## 참고

- **arbitrage/redis_client.py**: Redis 클라이언트 구현
- **arbitrage/health.py**: 헬스 모니터링 모듈
- **scripts/run_health_check.py**: 헬스 체크 스크립트
- **docs/REDIS_KEYS.md**: Redis 키 네이밍 컨벤션
- **docs/phase_D_master.md**: PHASE D 전체 계획
- **config/base.yml**: 설정 파일
