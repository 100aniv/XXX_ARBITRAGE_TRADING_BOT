# MODULE D10 – Live Trading Switch, Telegram Integration, Ops & Monitoring

## 개요

MODULE D10은 시스템을 "실거래 준비 완료" (D9)에서 "실제 운영 가능한 실거래 모드"로 전환합니다.

### 핵심 기능

1. **명확한 모드 분리**: mock / paper / live
2. **다층 실거래 보호**: 환경 변수 + 확인 파일 + 안전 검증 + 드라이런
3. **Telegram 알림 통합**: 선택적 실제 연동
4. **성능 모니터링**: 루프 지연, WebSocket 지연, Redis heartbeat 추적
5. **운영 안전성**: 모든 실거래는 fail-closed 설계

---

## 설정 가이드

### 1. config/live.yml 모드 설정

```yaml
mode:
  current: "mock"  # mock | paper | live

live_guards:
  require_env_flag: true              # LIVE_TRADING=1 필수
  require_manual_confirm_file: true   # .live_trading_ok 파일 필수
  require_safety_pass: true           # D8 안전 검증 필수
  dry_run_on_startup: true            # 시작 시 드라이런 강제
  dry_run_cycles: 3                   # 드라이런 사이클 수
```

### 2. Telegram 알림 설정 (선택사항)

```yaml
alert:
  enabled: true
  telegram_enabled: false  # true로 변경하면 실제 연동
  telegram:
    bot_token: ""          # 환경 변수: TELEGRAM_BOT_TOKEN
    chat_id: ""            # 환경 변수: TELEGRAM_CHAT_ID
    timeout_seconds: 5
```

---

## 실행 모드별 동작

### Mock 모드 (기본값)

```bash
# config.mode.current = "mock"
python scripts/run_live.py --once --mock
```

**특징:**
- 완전 시뮬레이션
- 실제 API 호출 없음
- WebSocket 선택사항
- 항상 안전

### Paper 모드

```bash
# config.mode.current = "paper"
python scripts/run_live.py --once
```

**특징:**
- 실제 시세 (REST + WebSocket)
- 모의 주문 (실제 주문 없음)
- 안전 검증 실행
- 리스크 없음

### Live 모드

```bash
# config.mode.current = "live"
# 환경 변수 설정
export LIVE_TRADING=1
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"

# 확인 파일 생성
touch .live_trading_ok

# 실행
python scripts/run_live.py
```

**특징:**
- 실제 시세 + 실제 주문
- 모든 보호 활성화
- 드라이런 강제 (처음 N 사이클)
- 실거래 차단 시 자동 paper 모드로 전환

---

## 실거래 보호 메커니즘

### 1. 환경 변수 확인

```bash
export LIVE_TRADING=1
```

**검증:**
```python
os.environ.get("LIVE_TRADING") == "1"
```

### 2. 확인 파일 확인

```bash
# 프로젝트 루트에 생성
touch .live_trading_ok
```

**검증:**
```python
os.path.exists(".live_trading_ok")
```

### 3. 안전 검증 확인

D8 SafetyValidator의 모든 검증이 통과해야 함:
- 신호 신뢰도 > 0.3
- 슬리피지 < 0.30%
- 포지션 사이즈 < 300,000₩
- 일일 손실 < 150,000₩

### 4. 드라이런 사이클

처음 N 사이클은 강제로 paper 모드:

```yaml
dry_run_cycles: 3  # 처음 3 사이클은 모의거래
```

**드라이런 중:**
- 모든 주문이 paper 모드로 실행
- 안전 검증은 정상 실행
- 메트릭은 정상 수집

---

## 테스트 시나리오

### TEST 1: 모드 및 보호 로직 (순수 Python)

```bash
python test_d10_live_guard.py
```

**검증 항목:**
- ✅ Mock 모드: 항상 안전
- ✅ Paper 모드: 항상 안전
- ✅ Live 모드 (환경 변수 없음): 차단
- ✅ Live 모드 (환경 변수 있음): 파일 없으면 차단
- ✅ 드라이런 사이클: 처음 N 사이클 강제 paper

### TEST 2: Live API + D10 통합 (Mock 모드)

```bash
python scripts/run_live.py --once --mock
```

**검증 항목:**
- ✅ LiveGuard 초기화
- ✅ 실거래 차단 배너 출력
- ✅ 메트릭에 live=❌ 표시
- ✅ 모든 엔진 정상 작동

### TEST 3: 알림 시스템 (D10 확장)

```bash
python test_d10_alert.py
```

**검증 항목:**
- ✅ 알림 비활성화: 메시지 없음
- ✅ Telegram 비활성화: 스텁 모드
- ✅ Telegram 자격증명 없음: 경고 + 스텁
- ✅ 모든 알림 유형 정상

---

## 성능 메트릭 (D10)

### 메트릭 필드

```python
loop_latency_ms: float          # 루프 지연 (ms)
ws_lag_ms: float                # WebSocket 지연 (ms)
redis_heartbeat_age_ms: float   # Redis heartbeat 나이 (ms)
num_live_trades_today: int      # 오늘 실거래 수
num_paper_trades_today: int     # 오늘 모의거래 수
last_live_trade_ts: str         # 마지막 실거래 시간 (ISO)
live_block_reasons: str         # 실거래 차단 사유 (;로 구분)
```

### 메트릭 출력 예시

```
[METRICS] pnl=0₩ trades=0 open_pos=0 exposure=0₩ realized_pnl=0₩ signals=0 exec_rate=0.0% safety_rejections=0 sl_triggers=0 loop_ms=1.2 live=❌
```

---

## Telegram 알림 설정 (선택사항)

### 1. Telegram 봇 생성

1. Telegram에서 @BotFather 검색
2. `/newbot` 명령 실행
3. 봇 이름 입력 (예: arbitrage_bot)
4. 봇 토큰 받기 (예: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### 2. 채팅 ID 얻기

1. 봇에 메시지 보내기
2. `https://api.telegram.org/bot<TOKEN>/getUpdates` 접속
3. `chat.id` 값 확인

### 3. 환경 변수 설정

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
export TELEGRAM_CHAT_ID="987654321"
```

### 4. config/live.yml 활성화

```yaml
alert:
  telegram_enabled: true
```

### 5. 테스트

```bash
python -c "
from arbitrage.alert import AlertSystem
config = {
    'enabled': True,
    'telegram_enabled': True,
    'telegram': {
        'bot_token': '',
        'chat_id': '',
        'timeout_seconds': 5
    }
}
alert = AlertSystem(config)
alert.alert_stoploss_triggered('BTC-KRW', 49400000.0)
"
```

---

## 운영 체크리스트

### 실거래 전 확인사항

- [ ] `config.mode.current = "live"` 확인
- [ ] `export LIVE_TRADING=1` 설정
- [ ] `.live_trading_ok` 파일 생성
- [ ] D8 안전 검증 통과 확인
- [ ] 드라이런 사이클 완료 확인 (처음 N 사이클)
- [ ] 메트릭에 `live=✅` 표시 확인
- [ ] Telegram 알림 설정 (선택사항)
- [ ] 로그 파일 모니터링 준비

### 운영 중 모니터링

```bash
# 로그 실시간 모니터링
tail -f logs/live.log | grep -E "METRICS|LIVE|ERROR"

# 메트릭 조회
curl http://localhost:8000/metrics
```

### 긴급 중지

```bash
# 프로세스 종료
pkill -f "python scripts/run_live.py"

# 또는 Ctrl+C
```

---

## 하위 호환성

- ✅ D1-D9 완벽 호환
- ✅ Mock 모드 변경 없음
- ✅ Paper 모드 변경 없음
- ✅ 기존 설정 유지 (mode.current 기본값 = "mock")

---

## 문제 해결

### 실거래가 차단되는 경우

```bash
# 1. 모드 확인
grep "mode:" config/live.yml

# 2. 환경 변수 확인
echo $LIVE_TRADING

# 3. 확인 파일 확인
ls -la .live_trading_ok

# 4. 안전 검증 확인
python test_d8_safety.py

# 5. 로그 확인
tail -f logs/live.log | grep "LIVE TRADING"
```

### Telegram 알림이 안 오는 경우

```bash
# 1. 자격증명 확인
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID

# 2. 알림 활성화 확인
grep "telegram_enabled:" config/live.yml

# 3. 테스트 알림 전송
python test_d10_alert.py

# 4. 로그 확인
tail -f logs/live.log | grep "Telegram"
```

---

## 다음 단계 (MODULE D11 예정)

- 실거래 모드 장기 운영 테스트
- 성능 최적화 및 튜닝
- 고급 리스크 모델링
- 자동 손절매 최적화
- 포트폴리오 리밸런싱 고도화
