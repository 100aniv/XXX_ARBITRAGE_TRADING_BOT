# D44: Paper Live Runner E2E + RiskGuard 하드닝

## 개요

D44는 D43의 ArbitrageLiveRunner를 **운영 수준으로 하드닝**하는 단계입니다.

**목표:**
- RiskGuard를 통한 리스크 관리
- Paper 모드 호가 변동 시뮬레이션
- 60초 안정적 실행
- 최소 1회 이상 거래 신호 생성 (조건부)

---

## 구현 사항

### 1. RiskGuard 클래스 (D44)

**파일:** `arbitrage/live_runner.py`

```python
class RiskGuardDecision(Enum):
    OK = "OK"
    TRADE_REJECTED = "TRADE_REJECTED"
    SESSION_STOP = "SESSION_STOP"

class RiskGuard:
    def check_trade_allowed(trade, num_active_orders) -> RiskGuardDecision
    def update_daily_loss(pnl_usd) -> None
```

**기능:**
- 거래당 최대 명목가 확인 (`max_notional_per_trade`)
- 최대 동시 거래 수 확인 (`max_open_trades`)
- 일일 최대 손실 확인 (`max_daily_loss`)
- 세션 종료 조건 판정

### 2. ArbitrageLiveRunner 확장 (D44)

**변경 사항:**
- `_risk_guard: RiskGuard` 인스턴스 추가
- `execute_trades()` 메서드에 RiskGuard 체크 추가
- `run_forever()` 메서드에 session_stop 체크 추가
- `_inject_paper_prices()` 메서드 추가 (Paper 시뮬레이션)

**Paper 호가 변동 시뮬레이션:**
- 5초마다 스프레드 주입
- LONG_A_SHORT_B 신호 생성 시도
- 환율 정규화: 1 BTC = 100,000 KRW = 40,000 USDT

### 3. 설정 파일 개선

**파일:** `configs/live/arbitrage_live_paper_example.yaml`

```yaml
risk_limits:
  max_notional_per_trade: 5000.0
  max_daily_loss: 10000.0
  max_open_trades: 1

paper_simulation:
  enable_price_volatility: true
  volatility_range_bps: 100
  spread_injection_interval: 5
```

### 4. CLI 업데이트

**파일:** `scripts/run_arbitrage_live.py`

- RiskLimits 로드 및 설정
- Paper 시뮬레이션 설정 로드
- ArbitrageLiveConfig에 전달

---

## 실행 방법

### 기본 실행 (60초)

```bash
python -m scripts.run_arbitrage_live \
  --config configs/live/arbitrage_live_paper_example.yaml \
  --mode paper \
  --max-runtime-seconds 60 \
  --log-level INFO
```

### 예상 출력

```
Duration: 60.0s
Loops: 60
Trades Opened: 0 (또는 >= 1)
Trades Closed: 0
Total PnL: $0.00
Active Orders: 0
Avg Loop Time: 1000.46ms
```

---

## RiskGuard 동작 방식

### 거래 허용 여부 판정

1. **거래당 최대 명목가 확인**
   - `trade.notional_usd > max_notional_per_trade` → TRADE_REJECTED

2. **최대 동시 거래 수 확인**
   - `num_active_orders >= max_open_trades` → TRADE_REJECTED

3. **일일 최대 손실 확인**
   - `daily_loss_usd >= max_daily_loss` → SESSION_STOP

### 세션 종료 조건

- RiskGuard가 SESSION_STOP을 반환하면 루프 종료
- 로그: `[D44_RISKGUARD] Session stopped by RiskGuard`

---

## 테스트

### D44 RiskGuard 테스트

```bash
pytest tests/test_d44_risk_guard.py -v
```

**결과:** 10/10 ✅

### D44 Live Paper Scenario 테스트

```bash
pytest tests/test_d44_live_paper_scenario.py -v
```

**결과:** 3/3 ✅

---

## 로그 해석

### 정상 실행

```
[D44_RISKGUARD] Initialized: max_notional=5000.0, max_daily_loss=10000.0, max_open_trades=1
[D43_LIVE] Starting live loop: interval=1.0s, max_runtime=60s
[D44_PAPER] Injected prices: A(bid=95000.0, ask=95000.0), B(bid=42000.0, ask=42000.0)
[D43_LIVE] Max runtime exceeded: 60.0s > 60s
```

### 거래 거절

```
[D44_RISKGUARD] Trade rejected: notional=6000.0 > max=5000.0
```

### 세션 종료

```
[D44_RISKGUARD] Session stop: daily_loss=1000.0 >= max=1000.0
[D44_RISKGUARD] Session stopped by RiskGuard
```

---

## 제약 사항 및 주의사항

### 1. 거래 신호 생성 미흡

**현재 상태:** 60초 실행 중 거래 신호가 생성되지 않음 (Trades Opened = 0)

**원인:**
- ArbitrageEngine의 스프레드 계산 로직이 매우 엄격함
- Paper 호가 주입이 실제 거래 신호를 생성하기에 충분하지 않음
- 환율 정규화 로직이 엔진에 반영되지 않음

**해결 방법 (D45+):**
- ArbitrageEngine의 스프레드 계산 로직 검토
- Paper 호가 주입 알고리즘 개선
- 실제 시장 데이터 기반 테스트

### 2. PnL 계산 단순화

- 현재 PnL은 항상 $0.00 (거래가 없기 때문)
- 실제 수수료/슬리피지 반영 미흡

### 3. 호가 정규화 미흡

- 두 거래소의 통화 단위 차이 (KRW vs USDT)를 완전히 처리하지 못함
- 환율 고정값 사용 (1 BTC = 100,000 KRW = 40,000 USDT)

### 4. Paper 시뮬레이션 제한

- 호가 변동이 단순하고 인공적임
- 실제 시장 조건을 반영하지 못함

---

## 다음 단계 (D45+)

1. **ArbitrageEngine 스프레드 계산 로직 검토**
   - 환율 정규화 로직 추가
   - 스프레드 계산 알고리즘 개선

2. **Paper 호가 주입 개선**
   - 더 현실적인 호가 변동 시뮬레이션
   - 동적 환율 적용

3. **실제 API 연동 준비**
   - Upbit/Binance 실 API 구현
   - 실시간 호가 수신

4. **모니터링 대시보드**
   - Grafana 등을 통한 실시간 모니터링
   - 거래 통계 시각화

---

## 결론

D44는 **Paper 모드 라이브 러너를 운영 수준으로 하드닝**했습니다.

✅ **완료:**
- RiskGuard 구현 및 통합
- Paper 호가 변동 시뮬레이션
- 60초 안정적 실행
- 포괄적 테스트

⚠️ **제약:**
- 거래 신호 생성 미흡 (엔진 로직 이슈)
- PnL 계산 단순화
- 호가 정규화 미흡

🚀 **다음 단계:**
- D45: ArbitrageEngine 개선
- D46: 실제 API 연동
- D47: 모니터링 대시보드
