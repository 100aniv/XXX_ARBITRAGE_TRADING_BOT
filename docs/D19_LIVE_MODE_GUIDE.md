# D19 Live Trading Mode Safety Validation Guide

**Document Version:** 1.0  
**Date:** 2025-11-15  
**Status:** ✅ Complete  

---

## 📋 목차

1. [개요](#개요)
2. [모드 정의](#모드-정의)
3. [환경 변수 설정](#환경-변수-설정)
4. [Live Mode 진입 조건](#live-mode-진입-조건)
5. [Shadow Live Mode 동작](#shadow-live-mode-동작)
6. [Live Mode 안전 게이트](#live-mode-안전-게이트)
7. [실거래 모드 활성화 절차](#실거래-모드-활성화-절차)
8. [테스트 및 검증](#테스트-및-검증)
9. [문제 해결](#문제-해결)
10. [체크리스트](#체크리스트)

---

## 개요

D19는 **Live Trading Mode Safety Validation**을 구현합니다. 실거래 모드 진입 조건을 엄격하게 제한하고, 조건을 만족하지 않을 때는 자동으로 Shadow Live Mode로 동작하여 안전성을 보장합니다.

### 핵심 원칙

- **기본값: Shadow Live Mode** — 실거래는 기본적으로 비활성화
- **명시적 활성화** — Live Mode는 모든 조건을 명시적으로 만족할 때만 활성화
- **다층 방어** — 환경 변수, API 키, RiskLimits, SafetyModule 등 여러 단계의 검증
- **로그 기반 감시** — 모든 주문 시도가 로그에 기록되어 감시 가능

---

## 모드 정의

### 1. Paper Mode (D17/D18)

**목적:** 시뮬레이션 환경에서 전체 엔진 플로우 검증

**특징:**
- SimulatedExchange 사용 (실제 거래소 연결 없음)
- YAML 시나리오 파일 기반 실행
- 실시간 가격 수집 없음
- 완전히 결정론적 (deterministic)

**활성화 방법:**
```yaml
# docker-compose.yml
arbitrage-paper-trader:
  environment:
    PAPER_MODE: "true"
    SCENARIO_FILE: "configs/d17_scenarios/basic_spread_win.yaml"
```

---

### 2. Shadow Live Mode (권장 기본값)

**목적:** 실시간 가격 + 신호 생성 + 주문 로그만 기록 (실제 거래 없음)

**특징:**
- 실시간 가격 수집 (Upbit/Binance)
- 신호 생성 로직 실행
- 주문 시도를 로그에 기록 (`[SHADOW_LIVE]` 프리픽스)
- Mock Order 반환 (상태 추적용)
- 실제 API 호출 없음
- 위험 없는 검증 환경

**활성화 조건:**
```
LIVE_MODE=false  또는
DRY_RUN=true     또는
SAFETY_MODE=false 또는
API 키 미설정     또는
RiskLimits 미설정
```

**로그 예시:**
```
[SHADOW_LIVE] Would place order: upbit buy 1.0 BTC @ 50000000
```

---

### 3. Live Mode (실거래)

**목적:** 실제 Upbit/Binance 주문 발행

**특징:**
- 실시간 가격 수집
- 신호 생성 및 실행
- 실제 API 호출로 주문 발행
- SafetyModule 안전 검사 필수
- 회로차단기, 일일 손실 제한 등 모든 안전 장치 활성화

**활성화 조건 (모두 만족해야 함):**
```
LIVE_MODE=true       AND
SAFETY_MODE=true     AND
DRY_RUN=false        AND
API 키 모두 설정     AND
RiskLimits 유효하게 설정
```

**로그 예시:**
```
[LIVE] Order placed: order_id_12345
```

---

## 환경 변수 설정

### 주요 환경 변수

| 환경 변수 | 기본값 | 설명 | 예시 |
|----------|--------|------|------|
| `LIVE_MODE` | `false` | 실거래 모드 활성화 | `true` / `false` |
| `SAFETY_MODE` | `true` | 안전 모드 활성화 | `true` / `false` |
| `DRY_RUN` | `true` | 드라이런 모드 | `true` / `false` |
| `UPBIT_API_KEY` | (없음) | Upbit API 키 | `your_upbit_key` |
| `UPBIT_SECRET_KEY` | (없음) | Upbit 시크릿 키 | `your_upbit_secret` |
| `BINANCE_API_KEY` | (없음) | Binance API 키 | `your_binance_key` |
| `BINANCE_SECRET_KEY` | (없음) | Binance 시크릿 키 | `your_binance_secret` |
| `REDIS_HOST` | `localhost` | Redis 호스트 | `redis` (Docker) |
| `REDIS_PORT` | `6379` | Redis 포트 | `6379` |

### 모드별 환경 변수 조합

#### Shadow Live Mode (권장)
```bash
LIVE_MODE=false
SAFETY_MODE=true
DRY_RUN=true
```

#### Live Mode (실거래)
```bash
LIVE_MODE=true
SAFETY_MODE=true
DRY_RUN=false
UPBIT_API_KEY=your_key
UPBIT_SECRET_KEY=your_secret
BINANCE_API_KEY=your_key
BINANCE_SECRET_KEY=your_secret
```

---

## Live Mode 진입 조건

### 조건 1: LIVE_MODE=true

```python
if not self.live_mode:
    # Shadow Live Mode로 동작
    logger.warning("Live Mode disabled: LIVE_MODE=false → Shadow Live Mode")
```

### 조건 2: SAFETY_MODE=true

```python
if not self.safety_mode:
    # Shadow Live Mode로 동작
    logger.warning("Live Mode disabled: SAFETY_MODE=false → Shadow Live Mode")
```

### 조건 3: DRY_RUN=false

```python
if self.dry_run:
    # Shadow Live Mode로 동작
    logger.warning("Live Mode disabled: DRY_RUN=true → Shadow Live Mode")
```

### 조건 4: API 키 모두 설정

```python
if not all([upbit_api_key, upbit_secret_key, binance_api_key, binance_secret_key]):
    # Shadow Live Mode로 동작
    logger.warning("Live Mode disabled: Missing API keys → Shadow Live Mode")
```

### 조건 5: RiskLimits 유효하게 설정

```python
if not risk_limits or risk_limits.max_position_size <= 0 or risk_limits.max_daily_loss <= 0:
    # Shadow Live Mode로 동작
    logger.warning("Live Mode disabled: Invalid RiskLimits → Shadow Live Mode")
```

### 조건 검증 결과

```python
# 모든 조건 만족
if self.live_enabled:
    logger.info("✅ Live Mode ENABLED - All conditions satisfied")
```

---

## Shadow Live Mode 동작

### 주문 실행 흐름

```python
async def _place_order(self, ...):
    if not self.live_enabled:
        # Shadow Live Mode: 로그만 남기고 실제 거래는 하지 않음
        logger.info(f"[SHADOW_LIVE] Would place order: {exchange} {side} {quantity} @ {price}")
        
        # Mock Order 반환 (상태 추적용)
        mock_order = Order(...)
        self._orders[mock_order.order_id] = mock_order
        self.state_manager.set_order(mock_order)
        return mock_order
    
    # Live Mode: 실제 거래 실행
    self._assert_live_mode_safety()
    return await self.upbit.place_order(...)
```

### 로그 모니터링

Shadow Live Mode에서 주문 시도를 모니터링하려면:

```bash
# 실시간 로그 확인
docker-compose logs -f arbitrage-live-trader | grep SHADOW_LIVE

# 또는 로그 파일 확인
tail -f logs/arbitrage.log | grep SHADOW_LIVE
```

---

## Live Mode 안전 게이트

### 안전 검사 항목

Live Mode 주문 실행 전 다음 조건들을 검사:

```python
def _assert_live_mode_safety(self):
    # 1. Live Mode 활성화 확인
    if not self.live_enabled:
        raise RuntimeError("Live Mode not enabled")
    
    # 2. 회로차단기 상태 확인
    if self.safety.state.circuit_breaker_active:
        raise RuntimeError("Circuit breaker is active - trading halted")
    
    # 3. 일일 손실 제한 확인
    if self.safety.state.daily_loss >= self.safety.limits.max_daily_loss:
        raise RuntimeError("Daily loss limit exceeded")
```

### 회로차단기 (Circuit Breaker)

**목적:** 큰 손실 발생 시 자동으로 거래 중지

**활성화 조건:**
- 일일 손실이 설정된 임계값 초과

**복구 방법:**
- 쿨다운 시간 경과 후 자동 복구
- 또는 수동으로 `reset_daily()` 호출

**로그:**
```
[ERROR] Circuit breaker is active - trading halted
```

---

## 실거래 모드 활성화 절차

### STEP 1: 환경 준비

```bash
# 1. 가상환경 활성화
abt_bot_env\Scripts\activate

# 2. API 키 설정 (.env 파일)
cat > .env << EOF
UPBIT_API_KEY=your_upbit_key
UPBIT_SECRET_KEY=your_upbit_secret
BINANCE_API_KEY=your_binance_key
BINANCE_SECRET_KEY=your_binance_secret
EOF

# 3. 환경 변수 확인
echo $UPBIT_API_KEY
```

### STEP 2: RiskLimits 설정

```python
# arbitrage/live_trader.py 또는 설정 파일에서
risk_limits = RiskLimits(
    max_position_size=1_000_000,      # 최대 포지션 크기 (KRW)
    max_daily_loss=500_000,            # 최대 일일 손실 (KRW)
    max_trades_per_hour=100,           # 시간당 최대 거래 수
    min_spread_pct=0.1                 # 최소 수익 스프레드 (%)
)
```

### STEP 3: Shadow Live Mode 테스트

```bash
# Shadow Live Mode에서 신호 생성 및 로그 확인
docker-compose up -d arbitrage-live-trader

# 로그 모니터링
docker-compose logs -f arbitrage-live-trader | grep SHADOW_LIVE

# 예상 로그:
# [SHADOW_LIVE] Would place order: upbit buy 1.0 BTC @ 50000000
# [SHADOW_LIVE] Would place order: binance sell 1.0 BTCUSDT @ 50100000
```

### STEP 4: Live Mode 활성화

```bash
# docker-compose.yml에서 환경 변수 수정
arbitrage-live-trader:
  environment:
    LIVE_MODE: "true"
    SAFETY_MODE: "true"
    DRY_RUN: "false"
    UPBIT_API_KEY: ${UPBIT_API_KEY}
    UPBIT_SECRET_KEY: ${UPBIT_SECRET_KEY}
    BINANCE_API_KEY: ${BINANCE_API_KEY}
    BINANCE_SECRET_KEY: ${BINANCE_SECRET_KEY}

# 재시작
docker-compose restart arbitrage-live-trader
```

### STEP 5: 실거래 모니터링

```bash
# 실시간 로그 확인
docker-compose logs -f arbitrage-live-trader

# 예상 로그:
# [LIVE] Order placed: order_id_12345
# [INFO] Signal executed: BTC spread=0.20% pnl=50000
```

### STEP 6: 긴급 중지

```bash
# 즉시 거래 중지 (컨테이너 종료)
docker-compose stop arbitrage-live-trader

# 또는 회로차단기 활성화 (손실 제한 초과)
# 자동으로 거래 중지됨
```

---

## 테스트 및 검증

### D19 테스트 실행

```bash
# D19 Live Mode 테스트만 실행
python -m pytest tests/test_d19_live_mode.py -v

# D16 + D17 + D19 전체 회귀 테스트
python -m pytest tests/test_d16_*.py tests/test_d17_*.py tests/test_d19_*.py -v
```

### 테스트 시나리오

#### 1. Shadow Mode 검증
```python
def test_shadow_mode_when_live_mode_false():
    trader = LiveTrader(..., live_mode=False)
    assert trader.live_enabled == False
```

#### 2. Live Mode 진입 조건
```python
def test_live_mode_all_conditions_satisfied():
    trader = LiveTrader(..., live_mode=True, safety_mode=True, dry_run=False)
    assert trader.live_enabled == True
```

#### 3. 안전 게이트
```python
def test_circuit_breaker_blocks_live_orders():
    trader.safety.state.circuit_breaker_active = True
    with pytest.raises(RuntimeError, match="Circuit breaker is active"):
        trader._assert_live_mode_safety()
```

---

## 문제 해결

### 문제 1: Live Mode가 활성화되지 않음

**증상:**
```
[WARNING] Live Mode disabled: LIVE_MODE=false → Shadow Live Mode
```

**해결:**
```bash
# 환경 변수 확인
echo $LIVE_MODE

# 설정
export LIVE_MODE=true
```

### 문제 2: API 키 오류

**증상:**
```
[WARNING] Live Mode disabled: Missing API keys → Shadow Live Mode
```

**해결:**
```bash
# API 키 설정 확인
echo $UPBIT_API_KEY
echo $BINANCE_API_KEY

# .env 파일에서 설정
source .env
```

### 문제 3: RiskLimits 유효하지 않음

**증상:**
```
ValueError: Invalid risk limits
```

**해결:**
```python
# RiskLimits 값 확인
risk_limits = RiskLimits(
    max_position_size=1_000_000,  # > 0
    max_daily_loss=500_000         # > 0
)
```

### 문제 4: 회로차단기 활성화됨

**증상:**
```
[ERROR] Circuit breaker is active - trading halted
```

**해결:**
```bash
# 1. 거래 중지 (자동)
# 2. 쿨다운 시간 경과 대기 (기본 300초)
# 3. 또는 수동으로 reset_daily() 호출

# 로그 확인
docker-compose logs arbitrage-live-trader | grep "circuit_breaker"
```

---

## 체크리스트

### 실거래 모드 활성화 전 확인사항

- [ ] 가상환경 활성화 확인
- [ ] API 키 설정 확인 (`echo $UPBIT_API_KEY` 등)
- [ ] RiskLimits 값 유효성 확인 (max_position_size > 0, max_daily_loss > 0)
- [ ] Redis/Postgres 연결 확인
- [ ] Shadow Live Mode에서 신호 생성 확인
- [ ] 로그에 `[SHADOW_LIVE]` 메시지 확인
- [ ] D19 테스트 모두 통과 확인
- [ ] 소액으로 테스트 (실제 거래 시작 전)

### 실거래 중 모니터링

- [ ] 실시간 로그 확인 (`docker-compose logs -f`)
- [ ] 주문 실행 로그 확인 (`[LIVE] Order placed`)
- [ ] 손실 제한 모니터링
- [ ] 회로차단기 상태 확인
- [ ] 포지션 크기 확인
- [ ] 거래 빈도 확인

### 긴급 상황 대응

- [ ] 거래 중지 명령 준비 (`docker-compose stop`)
- [ ] 손실 제한값 설정 확인
- [ ] 회로차단기 쿨다운 시간 확인
- [ ] 긴급 연락처 확보

---

## 관련 문서

- [D15 Implementation Summary](D15_IMPLEMENTATION_SUMMARY.md)
- [D16 Live Architecture](D16_LIVE_ARCHITECTURE.md)
- [D17 Paper Mode Guide](D17_PAPER_MODE_GUIDE.md)
- [D18 Docker Paper Validation](D18_DOCKER_PAPER_VALIDATION.md)

---

**문서 작성자:** Cascade AI  
**최종 수정:** 2025-11-15  
**상태:** ✅ Production Ready
