# D17 Paper/Shadow Mode Guide

## 📋 개요

D17은 D15/D16 기반 Live Arbitrage Core를 **Paper/Shadow 모드**로 검증하는 단계입니다.

- **Paper Mode**: 완전 시뮬레이션 (SimulatedExchange)
- **Shadow Mode**: 실시간 가격 + 시뮬 주문 (실계좌 영향 없음)
- **Live Mode**: 실거래 (강력한 방어 로직)

---

## 🚀 빠른 시작

### 1. Paper Mode (시뮬레이션)

```bash
# 기본 수익 시나리오
python -m pytest tests/test_d17_paper_engine.py::TestPaperEngine::test_basic_spread_win_scenario -v

# 모든 시나리오
python -m pytest tests/test_d17_paper_engine.py -v
```

### 2. Shadow Mode (실시간 가격, 시뮬 주문)

```bash
# 환경 설정
export LIVE_MODE=false
export SHADOW_MODE=true
export UPBIT_API_KEY=your_key
export UPBIT_SECRET_KEY=your_secret

# 실행
python -m arbitrage.engine --mode shadow
```

### 3. Live Mode (실거래 - 주의!)

```bash
# 강력한 방어 로직 필수
export LIVE_MODE=true
export I_UNDERSTAND_THE_RISK=true

# 실행
python -m arbitrage.engine --mode live
```

---

## 📊 시나리오 구조

### basic_spread_win.yaml

```yaml
name: "basic_spread_win"
steps:
  - t: 0
    upbit_bid: 50_000_000
    upbit_ask: 50_100_000
    binance_bid: 38_461
    binance_ask: 38_500

expected_outcomes:
  min_trades: 1
  min_pnl: 10_000
  circuit_breaker_triggered: false
```

**검증 항목:**
- ✅ 신호 생성
- ✅ 주문 체결
- ✅ PnL 계산
- ✅ 안전 장치 미발동

### choppy_market.yaml

```yaml
name: "choppy_market"
steps:
  - t: 0: 초기 상태
  - t: 1: 스프레드 역전
  - t: 2: 급격한 변동
  - t: 3: 안정화
```

**검증 항목:**
- ✅ 슬리피지 처리
- ✅ 부분 체결
- ✅ 손실 관리

### stop_loss_trigger.yaml

```yaml
name: "stop_loss_trigger"
expected_outcomes:
  circuit_breaker_triggered: true
  safety_violations: 1
```

**검증 항목:**
- ✅ 회로차단기 발동
- ✅ 거래 중단
- ✅ 손실 제한

---

## 🧪 테스트 실행

### SimulatedExchange 단위 테스트

```bash
python -m pytest tests/test_d17_simulated_exchange.py -v

# 예상 결과
======================== 11 passed in 0.25s ========================
```

**테스트 항목:**
- 초기화
- 잔액 조회
- 가격 설정
- 시장가 주문 (매수/매도)
- 부분 체결
- 슬리피지
- 수수료
- 주문 취소
- 주문 상태 조회
- 통계

### 페이퍼 엔진 E2E 테스트

```bash
python -m pytest tests/test_d17_paper_engine.py -v

# 예상 결과
======================== 3 passed in 0.50s ========================
```

**테스트 항목:**
- 정상 수익 시나리오
- 변동성 시나리오
- 손실/회로차단 시나리오

---

## 🔄 전체 플로우

```
1. 시나리오 로드 (YAML)
   ├─ 가격 데이터
   ├─ 리스크 프로필
   └─ 예상 결과

2. 엔진 초기화
   ├─ SimulatedExchange 생성
   ├─ SafetyModule 생성
   └─ StateManager 연결

3. 시뮬레이션 실행
   ├─ 각 스텝마다 가격 업데이트
   ├─ 신호 생성
   ├─ 안전 검사
   └─ 주문 체결

4. 결과 검증
   ├─ 거래 수
   ├─ PnL
   ├─ 회로차단기 발동
   └─ 안전 위반
```

---

## 📈 성능 메트릭

### 기본 수익 시나리오

```
시나리오: basic_spread_win
거래 수: 1
총 수수료: ~2,500 KRW
PnL: ~10,000 KRW
회로차단기: 미발동
```

### 변동성 시나리오

```
시나리오: choppy_market
거래 수: 0-2
총 수수료: ~5,000 KRW
PnL: -50,000 ~ 0 KRW
회로차단기: 미발동
```

### 손실 시나리오

```
시나리오: stop_loss_trigger
거래 수: 1
총 수수료: ~2,500 KRW
PnL: -100,000 KRW
회로차단기: 발동
```

---

## 🛡️ 안전 검사

### Paper Mode

```python
# SimulatedExchange만 사용
# 실계좌 영향 없음
# 네트워크 호출 없음
```

### Shadow Mode

```python
# 실시간 가격 구독 (WebSocket)
# 주문은 SimulatedExchange에만 기록
# 실계좌 변경 없음
```

### Live Mode

```python
# 방어 로직 1: LIVE_MODE=true 필수
# 방어 로직 2: I_UNDERSTAND_THE_RISK=true 필수
# 방어 로직 3: 최대 포지션 크기 제한
# 방어 로직 4: 일일 손실 제한
# 방어 로직 5: 회로차단기
```

---

## 🔧 커스텀 시나리오

### 새 시나리오 생성

```yaml
# configs/d17_scenarios/my_scenario.yaml

name: "my_scenario"
description: "내 시나리오"

symbols:
  - upbit: "KRW-BTC"
    binance: "BTCUSDT"

steps:
  - t: 0
    upbit_bid: 50_000_000
    upbit_ask: 50_100_000
    binance_bid: 38_461
    binance_ask: 38_500

risk_profile:
  max_position_krw: 1_000_000
  max_daily_loss_krw: 500_000
  min_spread_pct: 0.1
  slippage_bps: 5

expected_outcomes:
  min_trades: 1
  min_pnl: 10_000
  circuit_breaker_triggered: false
```

### 시나리오 실행

```python
from tests.test_d17_paper_engine import PaperEngineSimulator

engine = PaperEngineSimulator("configs/d17_scenarios/my_scenario.yaml")
result = await engine.run()
print(result)
```

---

## 📝 로그 해석

### 정상 실행

```
INFO: Simulated upbit exchange connected
INFO: Order placed: abc123 buy 1.0 @ 50100000 (filled: 1.0)
INFO: Trade recorded: daily_loss=0, total_loss=0, trades_today=1
INFO: Metrics updated: positions=1 orders=1
```

### 안전 장치 발동

```
WARNING: Order rejected: daily_loss - Daily loss 600000 exceeds limit 500000
WARNING: Circuit breaker activated: loss ratio 5.2%
INFO: Trading halted due to circuit breaker
```

### 부분 체결

```
INFO: Order placed: def456 buy 1.0 @ 50100000 (filled: 0.8)
WARNING: Partial fill detected: 80% filled
```

---

## 🎯 다음 단계

### D18: 백테스트/성과 분석

```bash
# 과거 데이터로 백테스트
python -m arbitrage.backtest --data historical_prices.csv --mode paper

# 성과 분석
python -m arbitrage.analyze --output report.html
```

### D19: 실시간 모니터링

```bash
# 대시보드
http://localhost:8001

# Slack 알림
export SLACK_WEBHOOK_URL=...
```

---

## ❓ FAQ

**Q: Paper Mode와 Shadow Mode의 차이?**

A: Paper Mode는 완전 시뮬레이션, Shadow Mode는 실시간 가격을 사용하지만 주문은 시뮬레이션됩니다.

**Q: Live Mode는 언제 켜나?**

A: Paper/Shadow 모드에서 충분히 검증한 후, 작은 포지션으로 시작하세요.

**Q: 시나리오를 추가하려면?**

A: `configs/d17_scenarios/` 디렉토리에 YAML 파일을 추가하면 됩니다.

**Q: 슬리피지는 어떻게 설정?**

A: 시나리오 YAML의 `slippage_bps` 필드를 수정하세요.

---

## 📚 참고 문서

- `docs/D16_LIVE_ARCHITECTURE.md` - D16 아키텍처
- `docs/ROLE.md` - 프로젝트 규칙
- `docs/D17_IMPLEMENTATION_SUMMARY.md` - D17 구현 요약
