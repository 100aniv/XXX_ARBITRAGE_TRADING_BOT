# D18 Docker-based Paper/Shadow Mode Live Stack Validation

## 📋 개요

D18은 D17의 Paper/Shadow 모드 엔진을 **Docker 스택에 통합**하여 엔드-투-엔드 검증하는 단계입니다.

**핵심 목표:**
- Docker Compose 스택에서 Paper/Shadow 트레이더 실행
- SimulatedExchange + D17 시나리오 기반 검증
- Redis 상태 관리 통합
- SafetyModule 안전 장치 검증
- 실거래 없이 전체 엔진 플로우 검증

---

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Stack (D18)                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  arbitrage-paper-trader (NEW)                        │   │
│  │  - PaperTrader (arbitrage/paper_trader.py)          │   │
│  │  - SimulatedExchange (D17)                          │   │
│  │  - SafetyModule + StateManager                      │   │
│  │  - Scenario: basic_spread_win.yaml                 │   │
│  └──────────────────────────────────────────────────────┘   │
│         │                                                     │
│         ├─→ Redis (상태 저장)                                │
│         └─→ Logs (로그 기록)                                 │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  arbitrage-core (기존)                              │   │
│  │  - LiveTrader (실거래 모드)                         │   │
│  │  - D15 고성능 모듈                                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  arbitrage-dashboard (기존)                         │   │
│  │  - FastAPI 백엔드                                   │   │
│  │  - /health, /metrics, /positions 엔드포인트       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Redis + PostgreSQL (기존)                          │   │
│  │  - 상태 관리 및 데이터 저장                         │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 빠른 시작

### 1. 가상환경 활성화

```bash
# Windows
abt_bot_env\Scripts\activate

# macOS/Linux
source abt_bot_env/bin/activate
```

### 2. Docker 이미지 빌드

```bash
cd infra
docker-compose build
```

### 3. Docker 스택 시작

```bash
# 최소 필수 서비스 시작
docker-compose up -d redis postgres arbitrage-dashboard arbitrage-paper-trader

# 또는 전체 스택 시작
docker-compose up -d
```

### 4. 상태 확인

```bash
# 컨테이너 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f arbitrage-paper-trader
```

### 5. Smoke Test 실행

```bash
# 프로젝트 루트에서 (venv 활성화 상태)
python scripts/docker_paper_smoke.py
```

---

## 📊 상세 검증 절차

### STEP 1 — Docker 이미지 빌드

```bash
cd infra
docker-compose build
```

**예상 출력:**
```
Building arbitrage-paper-trader
Step 1/20 : FROM python:3.14-slim
...
Successfully built <image_id>
```

### STEP 2 — Docker 스택 시작

```bash
docker-compose up -d redis postgres arbitrage-dashboard arbitrage-paper-trader
```

**예상 출력:**
```
Creating arbitrage-redis ... done
Creating arbitrage-postgres ... done
Creating arbitrage-dashboard ... done
Creating arbitrage-paper-trader ... done
```

### STEP 3 — 컨테이너 상태 확인

```bash
docker-compose ps
```

**예상 출력:**
```
NAME                          STATUS              PORTS
arbitrage-redis               Up 2 minutes        0.0.0.0:6380->6379/tcp
arbitrage-postgres            Up 2 minutes        5432/tcp
arbitrage-dashboard           Up 1 minute         0.0.0.0:8001->8001/tcp
arbitrage-paper-trader        Up 1 minute (healthy)
```

### STEP 4 — Paper Trader 로그 확인

```bash
docker-compose logs -f arbitrage-paper-trader
```

**예상 로그:**
```
arbitrage-paper-trader | 2025-11-15 11:02:30,123 [INFO] arbitrage.paper_trader: Initializing PaperTrader with scenario: configs/d17_scenarios/basic_spread_win.yaml
arbitrage-paper-trader | 2025-11-15 11:02:30,234 [INFO] arbitrage.paper_trader: Scenario: basic_spread_win
arbitrage-paper-trader | 2025-11-15 11:02:30,345 [INFO] arbitrage.paper_trader: Steps: 5
arbitrage-paper-trader | 2025-11-15 11:02:30,456 [INFO] arbitrage.paper_trader: Starting paper trader run...
arbitrage-paper-trader | 2025-11-15 11:02:30,567 [INFO] arbitrage.paper_trader: Exchange connected
arbitrage-paper-trader | 2025-11-15 11:02:30,678 [INFO] arbitrage.paper_trader: Order placed: order_123 (spread=0.50%)
arbitrage-paper-trader | 2025-11-15 11:02:30,789 [INFO] arbitrage.paper_trader: Exchange disconnected
arbitrage-paper-trader | 2025-11-15 11:02:30,890 [INFO] arbitrage.paper_trader: Paper trader run completed: {'scenario': 'basic_spread_win', 'trades': 1, 'signals': 1, ...}
```

### STEP 5 — API 헬스 체크

```bash
curl http://localhost:8001/health
```

**예상 응답:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-15T11:02:31Z"
}
```

### STEP 6 — Redis 상태 확인

```bash
docker exec arbitrage-redis redis-cli ping
```

**예상 응답:**
```
PONG
```

### STEP 7 — Smoke Test 실행

```bash
python scripts/docker_paper_smoke.py
```

**예상 출력:**
```
======================================================================
D18 Docker Paper/Shadow Mode Smoke Test
======================================================================

[1] Checking Docker...
✅ Docker is running

[2] Checking container status...
✅ arbitrage-redis: Up 3 minutes
✅ arbitrage-paper-trader: Up 2 minutes (healthy)
✅ arbitrage-dashboard: Up 2 minutes (healthy)

[3] Checking Redis connection...
✅ Redis connected

[4] Checking Redis keys...
✅ Redis keys found: 5 keys - ['paper_trader_result', ...]

[5] Checking API health...
✅ API healthy: {'status': 'healthy', ...}

[6] Checking paper trader logs...
Paper trader logs (last 30 lines):
----------------------------------------------------------------------
...
Paper trader run completed: {'scenario': 'basic_spread_win', 'trades': 1, ...}
----------------------------------------------------------------------

[7] Checking paper trader completion...
✅ Paper trader completed successfully

======================================================================
SMOKE TEST SUMMARY
======================================================================
✅ arbitrage-redis_status: running
✅ arbitrage-paper-trader_status: running
✅ arbitrage-dashboard_status: running
✅ redis_connection: ok
✅ redis_keys: found
✅ api_health: healthy
✅ paper_trader_completion: completed

✅ SMOKE TEST PASSED
```

---

## 🔧 환경변수 설정

### arbitrage-paper-trader 서비스

| 환경변수 | 기본값 | 설명 |
|---------|--------|------|
| `APP_ENV` | `docker` | 실행 환경 |
| `PAPER_MODE` | `true` | Paper 모드 활성화 |
| `LIVE_MODE` | `false` | 실거래 비활성화 |
| `SCENARIO_FILE` | `configs/d17_scenarios/basic_spread_win.yaml` | 시나리오 파일 경로 |
| `REDIS_HOST` | `redis` | Redis 호스트 (컨테이너 내부) |
| `REDIS_PORT` | `6379` | Redis 포트 (컨테이너 내부) |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |

### 시나리오 변경

docker-compose.yml에서 `SCENARIO_FILE` 환경변수를 변경하여 다른 시나리오 실행 가능:

```yaml
environment:
  SCENARIO_FILE: "configs/d17_scenarios/choppy_market.yaml"
```

---

## 📝 시나리오 파일

### 기본 시나리오 (basic_spread_win.yaml)

```yaml
name: basic_spread_win
description: 정상 수익 시나리오
steps:
  - t: 0
    upbit_bid: 100000
    upbit_ask: 100100
  - t: 1
    upbit_bid: 100000
    upbit_ask: 100100
  # ... 더 많은 스텝
risk_profile:
  slippage_bps: 5.0
  max_position_krw: 1000000
  max_daily_loss_krw: 500000
  min_spread_pct: 0.1
expected_outcomes:
  min_trades: 1
  min_pnl: 10000
  circuit_breaker_triggered: false
```

### 다른 시나리오

- `choppy_market.yaml`: 변동성 시나리오
- `stop_loss_trigger.yaml`: 손실/회로차단 시나리오

---

## 🧪 테스트 검증

### D16 + D17 회귀 테스트

```bash
# venv 활성화 상태에서
python -m pytest tests/test_d16_*.py tests/test_d17_*.py -v --tb=short
```

**예상 결과:**
```
===================== 62 passed in 0.58s ========================
```

---

## 🛑 문제 해결

### 1. Docker 빌드 실패

```bash
# 캐시 제거 후 재빌드
docker-compose build --no-cache
```

### 2. Redis 연결 실패

```bash
# Redis 상태 확인
docker-compose logs redis

# Redis 재시작
docker-compose restart redis
```

### 3. Paper Trader 실행 실패

```bash
# 로그 확인
docker-compose logs arbitrage-paper-trader

# 시나리오 파일 경로 확인
docker exec arbitrage-paper-trader ls -la configs/d17_scenarios/
```

### 4. API 헬스 체크 실패

```bash
# Dashboard 로그 확인
docker-compose logs arbitrage-dashboard

# Dashboard 재시작
docker-compose restart arbitrage-dashboard
```

---

## 📊 모니터링

### 실시간 로그 모니터링

```bash
# Paper trader 로그
docker-compose logs -f arbitrage-paper-trader

# 모든 서비스 로그
docker-compose logs -f
```

### Redis 모니터링

**컨테이너 내부에서 접속:**
```bash
# Redis CLI 접속 (컨테이너 내부)
docker exec -it arbitrage-redis redis-cli

# 모든 키 조회
> KEYS *

# 특정 키 값 조회
> GET paper_trader_result
```

**호스트에서 접속:**
```bash
# 호스트 포트 6380 사용 (docker-compose.yml에서 6380:6379 매핑)
redis-cli -h localhost -p 6380 ping

# 모든 키 조회
redis-cli -h localhost -p 6380 KEYS "*"
```

### 메트릭 조회

```bash
# API 메트릭
curl http://localhost:8001/metrics/live

# 포지션 조회
curl http://localhost:8001/positions

# 신호 조회
curl http://localhost:8001/signals
```

---

## 🧹 정리

### 컨테이너 중지

```bash
docker-compose down
```

### 데이터 초기화

```bash
docker-compose down -v
```

### 이미지 제거

```bash
docker-compose down --rmi all
```

---

## ✅ 체크리스트

D18 검증 완료 시 다음을 확인하세요:

- [ ] Docker 이미지 빌드 성공
- [ ] 모든 컨테이너 정상 실행
- [ ] Redis 연결 성공
- [ ] API /health 엔드포인트 응답 정상
- [ ] Paper trader 로그에 "Paper trader run completed" 메시지 출력
- [ ] Smoke test 모두 통과
- [ ] D16 + D17 회귀 테스트 모두 통과
- [ ] D15 고성능 기준선 유지

---

## 📚 참고 문서

- [D15 고성능 모듈](D15_IMPLEMENTATION_SUMMARY.md)
- [D16 실거래 아키텍처](D16_LIVE_ARCHITECTURE.md)
- [D17 Paper/Shadow 모드](D17_PAPER_MODE_GUIDE.md)
- [Docker Compose 설정](../infra/docker-compose.yml)

---

## 🎯 다음 단계 (D19+)

- D19: 실거래 모드 (LIVE_MODE=true) 검증
- D20: 모니터링 + 대시보드 고도화
- D21: 성능 최적화 및 스케일링
