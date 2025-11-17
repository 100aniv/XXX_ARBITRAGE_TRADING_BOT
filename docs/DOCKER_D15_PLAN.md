# Docker 아키텍처 설계 (D15 고성능 버전 기준)

## 📋 개요

이 문서는 **arbitrage-lite D15 고성능 버전**을 Docker 컨테이너 환경에서 안정적으로 운영하기 위한 아키텍처 설계입니다.

**핵심 목표:**
- D15 고성능 기준선 유지 (성능 저하 금지)
- 개발(venv) + 컨테이너 환경 동시 지원
- 실거래 안전성 보장 (LiveGuard, Safety 모듈 연계)
- 확장성 확보 (D16 이후 기능 추가 용이)

---

## 🏗️ 컨테이너 토폴로지

### 타겟 구성 (docker-compose)

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Network (arbitrage-network)       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  PostgreSQL  │  │    Redis     │  │   Adminer    │      │
│  │   (5432)     │  │   (6379)     │  │   (8080)     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ▲                  ▲                                  │
│         │                  │                                  │
│  ┌──────┴──────────────────┴──────────────────────────────┐ │
│  │                                                          │ │
│  │  ┌─────────────────────────────────────────────────┐   │ │
│  │  │   arbitrage-core (메인 봇)                      │   │ │
│  │  │   - live_loop + signal/execution               │   │ │
│  │  │   - risk/portfolio 모듈 (D15)                  │   │ │
│  │  │   - 포트: 내부 통신만 (외부 노출 X)           │   │ │
│  │  └─────────────────────────────────────────────────┘   │ │
│  │                                                          │ │
│  │  ┌─────────────────────────────────────────────────┐   │ │
│  │  │   dashboard (FastAPI + WebSocket)              │   │ │
│  │  │   - 실시간 메트릭 시각화                        │   │ │
│  │  │   - 포트: 8001 (외부 노출)                     │   │ │
│  │  └─────────────────────────────────────────────────┘   │ │
│  │                                                          │ │
│  └──────────────────────────────────────────────────────────┘ │
│         ▲                                                      │
│         │ (메트릭 수집: Redis/DB)                             │
│         │                                                      │
│  ┌──────┴──────────────────────────────────────────────────┐ │
│  │  모니터링 스택 (Prometheus, Grafana)                    │ │
│  │  - Prometheus: 9090                                     │ │
│  │  - Grafana: 3000                                        │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 서비스 목록

| 서비스 | 역할 | 포트 | 상태 |
|--------|------|------|------|
| **postgres** | 시계열 데이터 저장 (TimescaleDB) | 5432 | 기존 |
| **redis** | 실시간 메트릭/캐시 | 6379 | 기존 |
| **arbitrage-core** | 메인 봇 (D15 모듈 포함) | 내부 | 신규 |
| **dashboard** | FastAPI 대시보드 | 8001 | 개선 |
| **adminer** | DB 관리 UI | 8080 | 기존 |
| **prometheus** | 메트릭 수집 | 9090 | 기존 |
| **grafana** | 시각화 | 3000 | 기존 |

---

## 🔧 각 컨테이너 상세 설계

### 1. arbitrage-core (메인 봇)

**역할:**
- 실시간 시그널 생성 (arbitrage/signal.py)
- 포트폴리오 최적화 (arbitrage/portfolio_optimizer.py - D15)
- 리스크 관리 (arbitrage/risk_quant.py - D15)
- 변동성 예측 (ml/volatility_model.py - D15)
- 실행 (arbitrage/execution.py)

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드
COPY . .

# 환경 변수
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=docker

# 헬스 체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# 진입점: live_loop 실행
CMD ["python", "-m", "arbitrage.live_loop"]
```

**환경 변수 (.env에서 주입):**
```
# 데이터베이스
DB_HOST=postgres
DB_PORT=5432
DB_NAME=arbitrage
DB_USER=arbitrage
DB_PASSWORD=<strong_password>

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Exchange API (실거래 모드)
UPBIT_API_KEY=<your_key>
UPBIT_SECRET_KEY=<your_secret>
BINANCE_API_KEY=<your_key>
BINANCE_SECRET_KEY=<your_secret>

# 운영 모드
LIVE_MODE=false  # true: 실거래, false: paper/simulation
SAFETY_MODE=true  # LiveGuard, Safety 모듈 활성화

# 로깅
LOG_LEVEL=INFO
LOG_DIR=/app/logs
```

**볼륨:**
- `/app/data` - 데이터 저장 (모델, 캐시)
- `/app/logs` - 로그 파일
- `/app/config` - 설정 파일

**네트워크:**
- `arbitrage-network` (내부 통신)

**의존성:**
- `postgres` (service_healthy)
- `redis` (service_healthy)

---

### 2. dashboard (FastAPI)

**역할:**
- 실시간 메트릭 시각화 (WebSocket)
- 포트폴리오 상태 모니터링
- 리스크 메트릭 표시 (VaR, ES, MDD, Sharpe)
- 변동성 예측 결과 표시
- 거래 신호/실행 로그 조회

**Dockerfile:**
```dockerfile
FROM python:3.11-slim as builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

COPY . .

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "-m", "dashboard.server"]
```

**환경 변수:**
```
# 데이터베이스
DB_HOST=postgres
DB_PORT=5432
DB_NAME=arbitrage
DB_USER=arbitrage
DB_PASSWORD=<strong_password>

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# 대시보드
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8001
DASHBOARD_WORKERS=4

# 로깅
LOG_LEVEL=INFO
```

**포트:**
- `8001` (외부 노출)

**볼륨:**
- `/app/logs` - 로그 파일

**의존성:**
- `postgres` (service_healthy)
- `redis` (service_healthy)

---

### 3. PostgreSQL + TimescaleDB

**역할:**
- 시계열 데이터 저장 (OHLCV, 신호, 실행 기록)
- 포트폴리오 상태 히스토리
- 리스크 메트릭 히스토리

**환경 변수:**
```
POSTGRES_DB=arbitrage
POSTGRES_USER=arbitrage
POSTGRES_PASSWORD=<strong_password>
TIMESCALEDB_TELEMETRY=off
```

**볼륨:**
- `db_data:/var/lib/postgresql/data`

---

### 4. Redis

**역할:**
- 실시간 메트릭 캐시 (현재 포트폴리오, 리스크 수치)
- 신호/실행 큐
- 세션 관리 (대시보드)

**환경 변수:**
```
# 기본값 사용 (redis:7-alpine)
```

**볼륨:**
- `redis_data:/data`

---

## 🚀 운영 모드 개념

### DEV (개발 모드)

**환경:** 로컬 머신, venv 사용

**실행:**
```bash
# 1. venv 활성화
source abt_bot_env/bin/activate  # Linux/Mac
# 또는
abt_bot_env\Scripts\activate  # Windows

# 2. 테스트 실행 (D15 성능 검증)
python tests/test_d15_volatility.py
python tests/test_d15_portfolio.py
python tests/test_d15_risk_quant.py

# 3. 로컬 실행 (paper mode)
python -m arbitrage.live_loop

# 4. 대시보드 (별도 터미널)
python -m dashboard.server
```

**특징:**
- 빠른 개발/디버깅
- 전체 스택 로컬 실행 가능
- 성능 기준선 검증 용이

---

### DOCKER-LOCAL (컨테이너 모드)

**환경:** 단일 머신, docker-compose 사용

**실행:**
```bash
# 1. .env 파일 생성 (infra/.env)
DB_PASSWORD=strong_password_here
UPBIT_API_KEY=your_key
UPBIT_SECRET_KEY=your_secret
BINANCE_API_KEY=your_key
BINANCE_SECRET_KEY=your_secret
LIVE_MODE=false
SAFETY_MODE=true

# 2. 이미지 빌드
cd infra
docker-compose build

# 3. 스택 시작
docker-compose up -d

# 4. 로그 확인
docker-compose logs -f arbitrage-core
docker-compose logs -f dashboard

# 5. 대시보드 접속
# http://localhost:8001

# 6. 종료
docker-compose down
```

**특징:**
- 실거래 환경과 유사
- 데이터베이스/Redis 격리
- 모니터링 스택 포함
- 확장성 확보

---

### PROD (프로덕션 모드)

**환경:** 서버/클라우드 (Kubernetes, Docker Swarm 등)

**고려사항:**
- `.env` 파일 → 시크릿 관리 (AWS Secrets Manager, HashiCorp Vault)
- 리소스 제한 설정 (CPU, 메모리)
- 로그 수집 (ELK, Datadog)
- 백업 전략 (PostgreSQL, Redis)
- SSL/TLS 설정
- 헬스 체크 강화

---

## 📊 성능 기준선 유지 전략

### D15 고성능 코드 경로

**arbitrage-core 컨테이너 내:**
```
live_loop
  ├─ signal.py (신호 생성)
  ├─ ml/volatility_model.py (D15 - GPU 자동 감지)
  │  ├─ record_volatilities_batch() [0.05ms / 10K]
  │  └─ predict_batch() [< 5ms]
  ├─ arbitrage/portfolio_optimizer.py (D15 - NumPy 벡터화)
  │  ├─ add_returns_batch() [Pandas 벡터화]
  │  ├─ calculate_correlation_matrix() [27ms / 100×100]
  │  └─ get_optimal_weights() [< 5ms]
  ├─ arbitrage/risk_quant.py (D15 - NumPy 벡터화)
  │  ├─ record_returns_batch() [0.06ms / 10K]
  │  ├─ calculate_var() [0.71ms / 10K]
  │  └─ stress_test_batch() [< 1ms]
  └─ execution.py (실행)
```

### 성능 모니터링

**Redis 메트릭:**
```
arbitrage:metrics:volatility_pred_ms  # 변동성 예측 시간
arbitrage:metrics:portfolio_opt_ms    # 포트폴리오 최적화 시간
arbitrage:metrics:risk_calc_ms        # 리스크 계산 시간
arbitrage:metrics:signal_latency_ms   # 신호 생성 지연
```

**Prometheus 쿼리:**
```
# 변동성 예측 성능
rate(arbitrage_volatility_pred_ms[5m])

# 포트폴리오 최적화 성능
rate(arbitrage_portfolio_opt_ms[5m])

# 리스크 계산 성능
rate(arbitrage_risk_calc_ms[5m])
```

### 성능 저하 감지 및 대응

**조건:**
- 변동성 예측 > 10ms (기준: 5ms)
- 포트폴리오 최적화 > 50ms (기준: 27ms)
- 리스크 계산 > 5ms (기준: 0.71ms)

**대응:**
1. 컨테이너 리소스 확인 (CPU, 메모리)
2. 데이터베이스 쿼리 성능 확인
3. 코드 프로파일링 (cProfile, py-spy)
4. 필요 시 롤백 또는 최적화

---

## 🔐 실거래 안전성

### LiveGuard + Safety 모듈 연계

**arbitrage-core 시작 시:**
```python
# arbitrage/live_loop.py
from arbitrage.live_guard import LiveGuard
from arbitrage.safety import SafetyModule

if LIVE_MODE:
    guard = LiveGuard(
        max_position_size=1000000,  # 1M KRW
        max_daily_loss=500000,       # 500K KRW
        max_trades_per_hour=10
    )
    safety = SafetyModule(
        circuit_breaker_threshold=0.05,  # 5% 손실
        emergency_stop_enabled=True
    )
```

**대시보드 표시:**
- LiveGuard 상태 (활성/비활성)
- Safety 알림 (경고/차단)
- 포지션 크기 제한 상태

---

## 📈 확장성 (D16 이후)

### D16 기능 추가 시 고려사항

**1. 자동 모델 재학습 파이프라인**
```
arbitrage-core
  └─ ml/volatility_model.py
      └─ train_pipeline (새 컨테이너 또는 스케줄)
```

**2. 포트폴리오/리스크 알림 시스템**
```
arbitrage-core
  └─ notifications/slack.py
  └─ notifications/telegram.py
```

**3. 백테스트/성과 분석 모듈**
```
docker-compose.yml
  └─ backtest-engine (새 서비스)
  └─ analytics-api (새 서비스)
```

**4. 데이터 파이프라인**
```
docker-compose.yml
  └─ kafka (메시지 큐)
  └─ spark (데이터 처리)
```

---

## 📝 체크리스트

### 개발 환경 (venv)
- [ ] `requirements.txt` 설치 완료
- [ ] D15 테스트 모두 통과
- [ ] 성능 기준선 확인

### Docker 환경 (docker-compose)
- [ ] Dockerfile 작성/검증
- [ ] docker-compose.yml 작성/검증
- [ ] .env 파일 템플릿 생성
- [ ] 이미지 빌드 성공
- [ ] 컨테이너 시작 성공
- [ ] 헬스 체크 통과
- [ ] 대시보드 접속 가능
- [ ] 메트릭 수집 확인

### 성능 검증
- [ ] arbitrage-core 성능 기준선 유지
- [ ] dashboard 응답 시간 < 500ms
- [ ] 메모리 사용량 안정적

### 실거래 안전성
- [ ] LiveGuard 활성화
- [ ] Safety 모듈 활성화
- [ ] 포지션 크기 제한 설정
- [ ] 일일 손실 제한 설정
- [ ] 긴급 정지 버튼 테스트

---

## 🔗 참고 문서

- `docs/ROLE.md` - 프로젝트 규칙
- `D15_IMPLEMENTATION_SUMMARY.md` - D15 고성능 구현
- `D15_FINAL_CHECKLIST.md` - D15 검증 완료
- `docs/DOCKER_D15_GUIDE.md` - Docker 운영 가이드 (다음 단계)
