# Docker 운영 가이드 (D15 고성능 버전)

## 📋 목차

1. [전제 조건](#전제-조건)
2. [로컬 venv 환경 검증](#로컬-venv-환경-검증)
3. [Docker 이미지 빌드](#docker-이미지-빌드)
4. [docker-compose 실행](#docker-compose-실행)
5. [대시보드 접속](#대시보드-접속)
6. [모니터링 및 로그](#모니터링-및-로그)
7. [실거래 모드 전환](#실거래-모드-전환)
8. [문제 해결](#문제-해결)

---

## 전제 조건

### 필수 설치

- **Docker**: 20.10+ (또는 Docker Desktop)
- **Docker Compose**: 2.0+
- **Python**: 3.11+ (로컬 테스트용)
- **Git**: 코드 관리

### 설치 확인

```bash
docker --version
docker-compose --version
python --version
```

### 프로젝트 구조

```
arbitrage-lite/
├── Dockerfile                    # arbitrage-core용
├── Dockerfile.dashboard          # dashboard용
├── requirements.txt              # Python 의존성
├── infra/
│   ├── docker-compose.yml        # 컨테이너 오케스트레이션
│   └── .env.example              # 환경변수 템플릿
├── ml/
│   └── volatility_model.py        # D15 LSTM 모델
├── arbitrage/
│   ├── portfolio_optimizer.py     # D15 포트폴리오 최적화
│   ├── risk_quant.py              # D15 정량 리스크
│   └── live_loop.py               # 메인 봇 루프
├── dashboard/
│   └── server.py                  # FastAPI 대시보드
└── tests/
    ├── test_d15_volatility.py     # D15 성능 테스트
    ├── test_d15_portfolio.py       # D15 성능 테스트
    └── test_d15_risk_quant.py      # D15 성능 테스트
```

---

## 로컬 venv 환경 검증

### 1단계: venv 활성화

```bash
# Linux/Mac
source abt_bot_env/bin/activate

# Windows
abt_bot_env\Scripts\activate
```

### 2단계: 의존성 설치 (이미 설치된 경우 생략 가능)

```bash
pip install -r requirements.txt
```

### 3단계: D15 성능 테스트 실행

**변동성 모델 테스트:**
```bash
python tests/test_d15_volatility.py
```

**예상 출력:**
```
=== D15 High-Performance Volatility Model Tests ===

TEST 1: Model Initialization with GPU Support
  ✅ Predictor initialized
  Device: cpu (또는 cuda)
  Sequence length: 20

...

TEST 7: Large-Scale Data Processing (Performance Test)
  Recorded 10,000 volatilities in 0.05ms
  History length: 1000
  Throughput: 220752842 records/sec

=== All Tests Completed ===
```

**포트폴리오 최적화 테스트:**
```bash
python tests/test_d15_portfolio.py
```

**예상 출력:**
```
=== D15 High-Performance Portfolio Optimization Tests ===

...

TEST 9: Large-Scale Data Processing (Performance Test)
  Batch add (100 assets, 1000 obs): 22.92ms
  Correlation matrix (100x100): 27.37ms
  Risk parity weights: 17.82ms
  Total: 68.11ms

=== All Tests Completed ===
```

**정량 리스크 관리 테스트:**
```bash
python tests/test_d15_risk_quant.py
```

**예상 출력:**
```
=== D15 High-Performance Quantitative Risk Management Tests ===

...

TEST 11: Large-Scale Data Processing (Performance Test)
  Record 10K returns + 10K PnL: 0.06ms
  Calculate VaR 95%, 99%, ES: 0.71ms
  Calculate Max DD, Sharpe: 0.23ms
  Total: 1.01ms

=== All Tests Completed ===
```

### 성능 기준선 확인

| 테스트 | 기준선 | 상태 |
|--------|--------|------|
| 변동성 기록 10K | 0.05ms | ✅ |
| 상관관계 행렬 100×100 | 27ms | ✅ |
| VaR/ES 계산 10K | 0.71ms | ✅ |
| Max DD + Sharpe 10K | 0.23ms | ✅ |
| 포트폴리오 전체 100×1000 | 68ms | ✅ |

**모든 테스트가 통과하면 Docker 환경으로 진행 가능합니다.**

---

## Docker 이미지 빌드

### 1단계: 프로젝트 루트로 이동

```bash
cd /path/to/arbitrage-lite
```

### 2단계: arbitrage-core 이미지 빌드

```bash
docker build -f Dockerfile -t arbitrage-core:latest .
```

**빌드 확인:**
```bash
docker images | grep arbitrage-core
```

### 3단계: dashboard 이미지 빌드

```bash
docker build -f Dockerfile.dashboard -t arbitrage-dashboard:latest .
```

**빌드 확인:**
```bash
docker images | grep arbitrage-dashboard
```

### 4단계: 이미지 크기 확인

```bash
docker images | grep arbitrage
```

**예상 크기:**
- `arbitrage-core`: ~1.2GB (PyTorch 포함)
- `arbitrage-dashboard`: ~600MB (multi-stage build)

---

## docker-compose 실행

### 1단계: 환경변수 설정

```bash
cd infra

# .env 파일 생성
cp .env.example .env

# 텍스트 에디터로 .env 수정
# - DB_PASSWORD: 강력한 비밀번호로 변경
# - UPBIT_API_KEY, UPBIT_SECRET_KEY: 실거래 모드일 경우만 필요
# - LIVE_MODE: false (기본, paper mode)
```

### 2단계: 컨테이너 빌드 및 시작

```bash
# 이미지 빌드 (처음 1회만)
docker-compose build

# 컨테이너 시작 (백그라운드)
docker-compose up -d

# 또는 포그라운드 (로그 실시간 확인)
docker-compose up
```

### 3단계: 서비스 상태 확인

```bash
# 모든 컨테이너 상태
docker-compose ps

# 예상 출력:
# NAME                    STATUS
# arbitrage-postgres      Up (healthy)
# arbitrage-redis         Up (healthy)
# arbitrage-core          Up (healthy)
# arbitrage-dashboard     Up (healthy)
# arbitrage-adminer       Up
# arbitrage-prometheus    Up (healthy)
# arbitrage-grafana       Up (healthy)
```

### 4단계: 헬스 체크

```bash
# arbitrage-core 헬스 체크
docker-compose exec arbitrage-core python -c "import sys; sys.exit(0)"

# dashboard 헬스 체크
curl -f http://localhost:8001/health

# PostgreSQL 헬스 체크
docker-compose exec postgres pg_isready -U arbitrage

# Redis 헬스 체크
docker-compose exec redis redis-cli ping
```

---

## 대시보드 접속

### 1단계: 대시보드 URL 확인

```
http://localhost:8001
```

### 2단계: 대시보드 기능

**실시간 메트릭:**
- 현재 포트폴리오 상태
- 변동성 예측 (D15)
- 리스크 메트릭 (VaR, ES, MDD, Sharpe)
- 신호/실행 로그

**WebSocket 실시간 업데이트:**
- 메트릭 자동 갱신 (1초 주기)
- 신호 생성 실시간 알림
- 실행 결과 실시간 표시

### 3단계: 모니터링 대시보드

**Grafana (시각화):**
```
http://localhost:3000
```
- 기본 계정: admin / admin
- 메트릭: CPU, 메모리, 거래량, 수익률

**Prometheus (메트릭 수집):**
```
http://localhost:9090
```
- 메트릭 쿼리 및 분석

**Adminer (DB 관리):**
```
http://localhost:8080
```
- 데이터베이스 직접 조회
- 테이블 구조 확인

---

## 모니터링 및 로그

### 1단계: 실시간 로그 확인

```bash
# arbitrage-core 로그
docker-compose logs -f arbitrage-core

# dashboard 로그
docker-compose logs -f arbitrage-dashboard

# 모든 서비스 로그
docker-compose logs -f
```

### 2단계: 로그 파일 위치

```bash
# 호스트 머신에서 로그 확인
cat ../logs/arbitrage-core.log
cat ../logs/dashboard.log
```

### 3단계: 성능 메트릭 모니터링

**Redis에서 메트릭 조회:**
```bash
docker-compose exec redis redis-cli

# Redis CLI에서:
GET arbitrage:metrics:volatility_pred_ms
GET arbitrage:metrics:portfolio_opt_ms
GET arbitrage:metrics:risk_calc_ms
```

### 4단계: 컨테이너 리소스 사용량

```bash
# 실시간 모니터링
docker stats

# 예상 출력:
# CONTAINER                CPU %    MEM USAGE / LIMIT
# arbitrage-core           2.5%     1.2G / 2G
# arbitrage-dashboard      0.5%     300M / 1G
# arbitrage-postgres       1.0%     500M / 2G
# arbitrage-redis          0.2%     100M / 512M
```

---

## 실거래 모드 전환

### ⚠️ 주의: 실거래 전 필수 체크리스트

```
[ ] 1. 로컬 venv에서 모든 D15 테스트 통과
[ ] 2. Docker 환경에서 paper mode 정상 작동 확인
[ ] 3. API 키 설정 확인 (UPBIT_API_KEY, UPBIT_SECRET_KEY)
[ ] 4. LiveGuard 설정 확인:
      - max_position_size: 1M KRW
      - max_daily_loss: 500K KRW
      - max_trades_per_hour: 10
[ ] 5. Safety 모듈 활성화 (SAFETY_MODE=true)
[ ] 6. 포지션 크기 제한 설정
[ ] 7. 일일 손실 제한 설정
[ ] 8. 긴급 정지 버튼 테스트
[ ] 9. 대시보드 모니터링 준비
[ ] 10. 로그 모니터링 준비
[ ] 11. 팀 공지 및 승인
```

### 1단계: .env 파일 수정

```bash
cd infra
nano .env  # 또는 vim, VS Code 등

# 변경 사항:
LIVE_MODE=true              # false → true
SAFETY_MODE=true            # 그대로 유지
UPBIT_API_KEY=your_key      # 실제 키 입력
UPBIT_SECRET_KEY=your_secret # 실제 키 입력
```

### 2단계: 컨테이너 재시작

```bash
# 변경사항 적용
docker-compose down
docker-compose up -d

# 로그 확인
docker-compose logs -f arbitrage-core
```

### 3단계: 대시보드에서 실시간 모니터링

```
http://localhost:8001
```

**모니터링 항목:**
- LiveGuard 상태 (활성/비활성)
- Safety 알림 (경고/차단)
- 포지션 크기 (제한 대비)
- 일일 손실 (제한 대비)
- 신호/실행 로그

### 4단계: 긴급 정지 (필요 시)

```bash
# 컨테이너 정지
docker-compose down

# 또는 특정 서비스만 정지
docker-compose stop arbitrage-core
```

---

## 문제 해결

### 문제 1: Docker 이미지 빌드 실패

**증상:**
```
ERROR: failed to solve with frontend dockerfile.v0
```

**해결:**
```bash
# 1. 디스크 공간 확인
df -h

# 2. Docker 캐시 정리
docker system prune -a

# 3. 다시 빌드
docker build -f Dockerfile -t arbitrage-core:latest .
```

### 문제 2: 컨테이너 시작 실패

**증상:**
```
arbitrage-core exited with code 1
```

**해결:**
```bash
# 1. 로그 확인
docker-compose logs arbitrage-core

# 2. 환경변수 확인
docker-compose config | grep -A 20 arbitrage-core

# 3. 의존성 확인
docker-compose ps

# 4. 컨테이너 재시작
docker-compose restart arbitrage-core
```

### 문제 3: 대시보드 접속 불가

**증상:**
```
curl: (7) Failed to connect to localhost port 8001
```

**해결:**
```bash
# 1. 대시보드 컨테이너 상태 확인
docker-compose ps arbitrage-dashboard

# 2. 포트 확인
docker-compose port dashboard 8001

# 3. 로그 확인
docker-compose logs dashboard

# 4. 헬스 체크
docker-compose exec dashboard curl -f http://localhost:8001/health
```

### 문제 4: 성능 저하

**증상:**
```
변동성 예측: 50ms (기준: 5ms)
포트폴리오 최적화: 200ms (기준: 27ms)
```

**해결:**
```bash
# 1. 리소스 사용량 확인
docker stats

# 2. 컨테이너 리소스 제한 확인
docker-compose config | grep -A 10 resources

# 3. 데이터베이스 쿼리 성능 확인
docker-compose exec postgres psql -U arbitrage -d arbitrage -c "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# 4. 필요 시 리소스 증설
# docker-compose.yml에서 deploy.resources 수정
```

### 문제 5: 데이터베이스 연결 오류

**증상:**
```
psycopg2.OperationalError: could not connect to server
```

**해결:**
```bash
# 1. PostgreSQL 상태 확인
docker-compose ps postgres

# 2. 헬스 체크
docker-compose exec postgres pg_isready -U arbitrage

# 3. 환경변수 확인
docker-compose config | grep DB_

# 4. 데이터 초기화 (주의: 데이터 손실)
docker-compose down -v
docker-compose up -d
```

### 문제 6: Redis 연결 오류

**증상:**
```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379
```

**해결:**
```bash
# 1. Redis 상태 확인
docker-compose ps redis

# 2. 헬스 체크
docker-compose exec redis redis-cli ping

# 3. 포트 확인
docker-compose port redis 6379

# 4. Redis 재시작
docker-compose restart redis
```

---

## 정리 및 종료

### 1단계: 컨테이너 정지

```bash
# 모든 컨테이너 정지 (데이터 유지)
docker-compose stop

# 모든 컨테이너 제거 (데이터 유지)
docker-compose down

# 모든 컨테이너 + 볼륨 제거 (데이터 삭제)
docker-compose down -v
```

### 2단계: 이미지 정리

```bash
# 사용하지 않는 이미지 제거
docker image prune

# 모든 arbitrage 이미지 제거
docker rmi arbitrage-core:latest arbitrage-dashboard:latest
```

### 3단계: 전체 정리

```bash
# Docker 시스템 정리 (주의: 모든 컨테이너/이미지 영향)
docker system prune -a
```

---

## 참고 문서

- `docs/ROLE.md` - 프로젝트 규칙
- `docs/DOCKER_D15_PLAN.md` - Docker 아키텍처 설계
- `D15_IMPLEMENTATION_SUMMARY.md` - D15 고성능 구현
- `D15_FINAL_CHECKLIST.md` - D15 검증 완료

---

## 지원 및 문의

문제 발생 시:
1. 로그 확인 (`docker-compose logs`)
2. 헬스 체크 실행
3. 문제 해결 섹션 참고
4. 필요 시 팀에 보고
