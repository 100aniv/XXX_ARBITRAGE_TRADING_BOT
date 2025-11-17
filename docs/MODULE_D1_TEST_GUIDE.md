# MODULE D1 – PostgresStorage Implementation & CSV → DB Migration
## 테스트 & 검증 가이드

---

## 테스트 시나리오

### 시나리오 1: CSV 모드 기본 동작 확인 (기존 호환성)

**목표**: backend: csv 설정 시 기존과 동일하게 동작하는지 확인

**명령어**:
```bash
# 1. config/base.yml 확인
grep "backend:" config/base.yml
# 출력: backend: csv

# 2. Paper 실행 (짧은 시간, Ctrl+C로 중단)
python scripts/run_paper.py

# 3. CSV 파일 생성 확인
ls -la data/
# 출력: positions.csv, orders.csv, spreads.csv 등

# 4. 데이터 확인
head -5 data/positions.csv
head -5 data/orders.csv
```

**예상 결과**:
- ✅ CSV 파일이 정상적으로 생성됨
- ✅ 기존과 동일한 로그 포맷
- ✅ 에러 없이 정상 실행

---

### 시나리오 2: PostgreSQL 모드 기본 동작 확인

**목표**: backend: postgres 설정 시 DB에 데이터가 저장되는지 확인

**전제조건**:
- Docker 설치됨
- psycopg2-binary 설치됨: `pip install psycopg2-binary`

**명령어**:
```bash
# 1. PostgreSQL 서버 시작
docker-compose -f infra/docker-compose.yml up -d postgres

# 2. 연결 확인 (약 10초 대기)
sleep 10
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT version();"
# 출력: PostgreSQL 버전 정보

# 3. 테이블 확인
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "\dt"
# 출력: positions, orders, spreads, trades, fx_rates 테이블 목록

# 4. config/base.yml 수정 (backend: postgres로 변경)
sed -i 's/backend: csv/backend: postgres/' config/base.yml

# 5. Paper 실행 (짧은 시간, Ctrl+C로 중단)
python scripts/run_paper.py

# 6. DB 데이터 확인
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT COUNT(*) as position_count FROM positions;"
# 출력: position_count 값 (0 이상)

docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT * FROM positions LIMIT 3;"
# 출력: 포지션 데이터

# 7. 정리
docker-compose -f infra/docker-compose.yml down
```

**예상 결과**:
- ✅ PostgreSQL 연결 성공
- ✅ 테이블 자동 생성됨
- ✅ Paper 실행 후 positions, orders 테이블에 데이터 INSERT됨
- ✅ CSV 파일도 함께 생성됨 (dual-write 아님, 단일 backend만 사용)

---

### 시나리오 3: CSV → PostgreSQL 마이그레이션 테스트

**목표**: 기존 CSV 로그를 PostgreSQL로 마이그레이션하고 Idempotency 확인

**전제조건**:
- data/ 디렉토리에 positions.csv, orders.csv, spreads.csv 파일 있음
- Docker 설치됨
- psycopg2-binary 설치됨

**명령어**:
```bash
# 1. PostgreSQL 서버 시작
docker-compose -f infra/docker-compose.yml up -d postgres
sleep 10

# 2. CSV 파일 행 수 확인
echo "=== CSV 파일 행 수 ==="
wc -l data/positions.csv data/orders.csv data/spreads.csv 2>/dev/null || echo "CSV 파일이 없습니다"

# 3. Dry-run으로 마이그레이션 요약 확인
echo "=== Dry-run 마이그레이션 ==="
python scripts/migrate_csv_to_postgres.py --config config/base.yml --dry-run

# 4. 실제 마이그레이션 실행
echo "=== 실제 마이그레이션 ==="
python scripts/migrate_csv_to_postgres.py --config config/base.yml

# 5. DB 데이터 확인
echo "=== DB 데이터 확인 ==="
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT COUNT(*) as position_count FROM positions;"
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT COUNT(*) as order_count FROM orders;"
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT COUNT(*) as spread_count FROM spreads;"

# 6. Idempotency 확인 (동일 스크립트 재실행)
echo "=== Idempotency 확인: 동일 스크립트 재실행 ==="
python scripts/migrate_csv_to_postgres.py --config config/base.yml

# 7. 데이터 중복 없음 확인
echo "=== 재실행 후 데이터 확인 (중복 없어야 함) ==="
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT COUNT(*) as position_count FROM positions;"

# 8. 정리
docker-compose -f infra/docker-compose.yml down
```

**예상 결과**:
- ✅ Dry-run에서 마이그레이션할 행 수 요약 출력
- ✅ 실제 마이그레이션 후 DB에 데이터 저장됨
- ✅ 재실행해도 데이터 중복 없음 (Idempotent)
- ✅ 마이그레이션 로그에 "inserted", "updated", "errors" 통계 출력

---

### 시나리오 4: Fallback 동작 확인

**목표**: PostgreSQL 연결 실패 시 CSV로 자동 fallback되는지 확인

**명령어**:
```bash
# 1. config/base.yml에서 backend: postgres로 설정
sed -i 's/backend: csv/backend: postgres/' config/base.yml

# 2. PostgreSQL 서버 미실행 상태에서 Paper 실행
echo "=== PostgreSQL 미실행 상태에서 Paper 실행 ==="
python scripts/run_paper.py 2>&1 | grep -E "(WARNING|ERROR|Falling back)"
# 출력: WARNING 로그 + "Falling back to CSV storage"

# 3. CSV 파일 생성 확인 (fallback 동작)
ls -la data/positions.csv
# 출력: 파일 존재

# 4. config/base.yml 복원
sed -i 's/backend: postgres/backend: csv/' config/base.yml
```

**예상 결과**:
- ✅ WARNING 로그 출력: "PostgreSQL backend connection failed"
- ✅ "Falling back to CSV storage" 메시지 출력
- ✅ CSV 파일이 정상적으로 생성됨 (fallback 동작 확인)

---

### 시나리오 5: psycopg2 미설치 상태 확인

**목표**: psycopg2 미설치 시 ImportError 처리 확인

**명령어**:
```bash
# 1. psycopg2 임시 제거 (가상환경에서만)
pip uninstall -y psycopg2-binary

# 2. config/base.yml에서 backend: postgres로 설정
sed -i 's/backend: csv/backend: postgres/' config/base.yml

# 3. Paper 실행
echo "=== psycopg2 미설치 상태에서 Paper 실행 ==="
python scripts/run_paper.py 2>&1 | grep -E "(ERROR|WARNING|Falling back|psycopg2)"
# 출력: ERROR 로그 + "psycopg2 is not installed"

# 4. CSV 파일 생성 확인
ls -la data/positions.csv

# 5. psycopg2 복원
pip install psycopg2-binary

# 6. config/base.yml 복원
sed -i 's/backend: postgres/backend: csv/' config/base.yml
```

**예상 결과**:
- ✅ ERROR 로그: "psycopg2 is not installed"
- ✅ "Falling back to CSV storage" 메시지 출력
- ✅ CSV 파일이 정상적으로 생성됨

---

## 빠른 테스트 (한 번에 실행)

```bash
#!/bin/bash

echo "=========================================="
echo "MODULE D1 – PostgresStorage Test Suite"
echo "=========================================="

# 테스트 1: CSV 모드
echo -e "\n[TEST 1] CSV 모드 기본 동작"
grep "backend:" config/base.yml
timeout 5 python scripts/run_paper.py || true
ls -la data/positions.csv 2>/dev/null && echo "✅ CSV 파일 생성됨" || echo "❌ CSV 파일 없음"

# 테스트 2: PostgreSQL 모드
echo -e "\n[TEST 2] PostgreSQL 모드 기본 동작"
docker-compose -f infra/docker-compose.yml up -d postgres
sleep 10
sed -i 's/backend: csv/backend: postgres/' config/base.yml
timeout 5 python scripts/run_paper.py || true
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT COUNT(*) FROM positions;" && echo "✅ DB 데이터 저장됨" || echo "❌ DB 연결 실패"
docker-compose -f infra/docker-compose.yml down

# 테스트 3: CSV 복원
echo -e "\n[TEST 3] CSV 모드 복원"
sed -i 's/backend: postgres/backend: csv/' config/base.yml
grep "backend:" config/base.yml

echo -e "\n=========================================="
echo "테스트 완료"
echo "=========================================="
```

---

## 검증 체크리스트

### PostgresStorage 구현
- [ ] PostgresStorage 클래스 정의됨
- [ ] psycopg2 지연 import 구현됨
- [ ] 자동 테이블 생성 (CREATE TABLE IF NOT EXISTS)
- [ ] 인덱스 자동 생성
- [ ] log_position_open() 구현
- [ ] log_position_close() 구현
- [ ] log_order() 구현
- [ ] log_spread() 구현
- [ ] load_positions() 구현

### get_storage() 팩토리 함수
- [ ] backend: "csv" → CsvStorage 반환
- [ ] backend: "postgres" → PostgresStorage 반환
- [ ] psycopg2 미설치 시 CSV로 fallback
- [ ] DB 연결 실패 시 CSV로 fallback
- [ ] 명확한 WARNING 로그 출력

### 마이그레이션 스크립트
- [ ] CSV 파일 읽기 (positions, orders, spreads)
- [ ] PostgreSQL INSERT
- [ ] Idempotent 설계 (중복 방지)
- [ ] --dry-run 옵션
- [ ] --limit 옵션
- [ ] 상세 로그 출력

### 설정 파일
- [ ] config/base.yml에 storage 섹션
- [ ] backend: csv (기본값)
- [ ] postgres.dsn 설정
- [ ] postgres.schema 설정

### 문서
- [ ] docs/phase_D_master.md 작성
- [ ] MODULE D1 섹션 상세 설명
- [ ] 테스트 시나리오 문서화
- [ ] ARB_PHASE_INDEX.md 업데이트

---

## 문제 해결

### 문제: "psycopg2 is not installed"

**해결책**:
```bash
pip install psycopg2-binary
```

### 문제: "Failed to connect to DB: connection refused"

**해결책**:
```bash
# PostgreSQL 서버 시작
docker-compose -f infra/docker-compose.yml up -d postgres
sleep 10

# 연결 확인
docker-compose -f infra/docker-compose.yml exec postgres psql -U arbitrage -d arbitrage -c "SELECT 1;"
```

### 문제: "permission denied" (마이그레이션 스크립트)

**해결책**:
```bash
chmod +x scripts/migrate_csv_to_postgres.py
```

### 문제: "CSV 파일이 없습니다"

**해결책**:
```bash
# 먼저 Paper 모드로 CSV 로그 생성
python scripts/run_paper.py  # Ctrl+C로 중단

# 그 후 마이그레이션 실행
python scripts/migrate_csv_to_postgres.py --config config/base.yml
```

---

## 성능 고려사항

### CSV 모드
- 파일 I/O 기반 (느림)
- 메모리 효율적
- 네트워크 불필요

### PostgreSQL 모드
- DB 연결 기반 (빠름)
- 메모리 사용량 증가
- 네트워크 필요
- 인덱스로 쿼리 최적화

### 권장사항
- **개발/테스트**: CSV 모드
- **프로덕션**: PostgreSQL 모드 (docker-compose 사용)

---

## 다음 단계

### MODULE D2 – Redis Cache & Health Monitoring
- Redis 기반 FX 환율 캐시
- 스프레드 스냅샷 캐시
- 헬스 모니터링 (heartbeat)

### MODULE D3 – Docker-compose App Integration
- arbitrage-app 컨테이너
- Prometheus 메트릭 수집
- Grafana 대시보드

### MODULE D4 – Live API Connector Stubs
- Upbit Live API 연동 준비
- Binance Live API 연동 준비
