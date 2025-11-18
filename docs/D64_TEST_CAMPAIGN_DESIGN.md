# D64 테스트/캠페인 설계 문서

**작성일:** 2025-11-18  
**목적:** "아비트라지 정상 동작 확인용" 표준 캠페인 정의

---

## 🎯 캠페인 목표

D_ROADMAP.md에 따라, 다음을 검증하기 위한 표준 캠페인을 정의합니다:

1. **Entry/Exit 정상 발생 여부**
2. **PnL 계산 정확성**
3. **Winrate 계산 가능 여부**
4. **심볼별 독립성**
5. **Guard 정상 동작**
6. **슬리피지/수수료 반영**

---

## 📋 표준 캠페인 정의

### C1: 단일 심볼 1H Paper (BTC)

**목표:**
- 최소한의 Entry/Exit 사이클 검증
- PnL/Winrate 계산 확인

**설정:**
```yaml
duration: 60분
symbols: [KRW-BTC]
mode: paper
data_source: rest
min_spread_bps: 30.0
max_position_usd: 1000.0
max_open_trades: 1
```

**검증 지표:**
| 지표 | 최소 기준 | 목표 |
|------|----------|------|
| Entry 횟수 | ≥ 10 | ≥ 50 |
| Exit 횟수 | ≥ 5 | ≥ 25 |
| Winrate | 계산 가능 (0/0 아님) | 30~70% |
| PnL | ≠ $0.00 | 의미 있는 값 |
| 평균 Loop Time | < 1000ms | < 500ms |
| ERROR 로그 | 0건 | 0건 |

**실행 명령:**
```cmd
cd C:\Users\bback\Desktop\부업\9) 코인 자동매매\arbitrage-lite
.\trading_bot_env\Scripts\activate

REM 환경 초기화
python scripts\infra_cleanup.py --skip-docker

REM C1 실행
python scripts\run_multisymbol_longrun.py ^
  --config configs/live/arbitrage_multisymbol_longrun.yaml ^
  --symbols KRW-BTC ^
  --scenario C1_SINGLE_1H ^
  --duration-minutes 60 ^
  --log-level INFO
```

---

### C2: 멀티심볼 1H Paper (BTC+ETH)

**목표:**
- 멀티심볼 Entry/Exit 독립성 확인
- 심볼별 PnL 추적 검증

**설정:**
```yaml
duration: 60분
symbols: [KRW-BTC, KRW-ETH]
mode: paper
data_source: rest
min_spread_bps: 30.0
max_position_usd: 1000.0
max_open_trades: 1  # 심볼당
```

**검증 지표:**
| 지표 | 최소 기준 | 목표 |
|------|----------|------|
| 심볼별 Entry | 각 ≥ 5 | 각 ≥ 25 |
| 심볼별 Exit | 각 ≥ 3 | 각 ≥ 15 |
| 심볼별 Winrate | 계산 가능 | 30~70% |
| 심볼별 PnL | ≠ $0.00 | 의미 있는 값 |
| 포트폴리오 PnL | = Σ(심볼별 PnL) | 정확한 합산 |
| 심볼 간 간섭 | 없음 | 완전 독립 |

**실행 명령:**
```cmd
python scripts\run_multisymbol_longrun.py ^
  --config configs/live/arbitrage_multisymbol_longrun.yaml ^
  --symbols KRW-BTC,KRW-ETH ^
  --scenario C2_MULTI_1H ^
  --duration-minutes 60 ^
  --log-level INFO
```

---

### C3: 멀티심볼 6H Paper (BTC+ETH+BTCUSDT)

**목표:**
- 장시간 안정성 확인
- 메모리 leak/크래시 없음 확인
- WS 재연결 테스트

**설정:**
```yaml
duration: 360분 (6시간)
symbols: [KRW-BTC, KRW-ETH, BTCUSDT]
mode: paper
data_source: rest  # 또는 ws (WS 테스트 시)
min_spread_bps: 30.0
max_position_usd: 1000.0
max_open_trades: 2  # 심볼당
```

**검증 지표:**
| 지표 | 최소 기준 | 목표 |
|------|----------|------|
| 실행 시간 | 360분 완료 | 크래시 없음 |
| 총 Entry | ≥ 100 | ≥ 500 |
| 총 Exit | ≥ 50 | ≥ 250 |
| 메모리 사용량 | < 500MB | < 300MB |
| CPU 사용량 | < 20% | < 10% |
| WS 재연결 (WS 모드) | 정상 복구 | 0 데이터 손실 |

**실행 명령:**
```cmd
python scripts\run_multisymbol_longrun.py ^
  --config configs/live/arbitrage_multisymbol_longrun.yaml ^
  --symbols KRW-BTC,KRW-ETH,BTCUSDT ^
  --scenario C3_MULTI_6H ^
  --duration-minutes 360 ^
  --log-level INFO
```

---

## 🧪 특수 테스트 시나리오

### T1: 의도적 이익 시나리오

**목표:**
- PnL 계산 로직 검증 (양수)

**방법:**
- Price feed 조작하여 "무조건 이기는 아비트라지" 생성
- Entry 스프레드 > Exit 스프레드 보장

**기대 결과:**
- PnL > 0
- Winrate = 100%

---

### T2: 의도적 손실 시나리오

**목표:**
- PnL 계산 로직 검증 (음수)

**방법:**
- Price feed 조작하여 "무조건 지는 아비트라지" 생성
- Entry 스프레드 < Exit 스프레드 보장

**기대 결과:**
- PnL < 0
- Winrate = 0%

---

### T3: Guard 발동 시나리오

**목표:**
- RiskGuard 정상 동작 확인

**방법:**
- 일일 손실 한도를 낮게 설정 (예: $100)
- T2 시나리오 실행하여 손실 유도

**기대 결과:**
- 손실이 한도에 도달하면 거래 중단
- 로그에 "BLOCK" 메시지 출력

---

### T4: WS 재연결 시나리오

**목표:**
- WS 연결 끊김 시 자동 복구 확인

**방법:**
- WS 모드로 실행 중 네트워크 끊기
- 또는 WS 서버 강제 종료

**기대 결과:**
- WS 재연결 성공
- 데이터 손실 없음
- 거래 계속 진행

---

## 📊 검증 체크리스트

### 모든 캠페인 공통

- [ ] Entry 발생 여부
- [ ] Exit 발생 여부
- [ ] Winrate 계산 가능 (0/0 아님)
- [ ] PnL ≠ $0.00
- [ ] Guard 정상 동작
- [ ] 슬리피지/수수료 반영
- [ ] ERROR/CRITICAL 로그 0건
- [ ] 크래시 없음

### C1 (단일 심볼 1H)

- [ ] Entry ≥ 10회
- [ ] Exit ≥ 5회
- [ ] Winrate 30~70%
- [ ] 평균 Loop Time < 1000ms

### C2 (멀티심볼 1H)

- [ ] 심볼별 Entry ≥ 5회
- [ ] 심볼별 Exit ≥ 3회
- [ ] 심볼별 Winrate 계산 가능
- [ ] 포트폴리오 PnL = Σ(심볼별 PnL)
- [ ] 심볼 간 간섭 없음

### C3 (멀티심볼 6H)

- [ ] 360분 완료 (크래시 없음)
- [ ] 총 Entry ≥ 100회
- [ ] 총 Exit ≥ 50회
- [ ] 메모리 < 500MB
- [ ] CPU < 20%

---

## 🔧 캠페인 실행 프로세스

### 1. 환경 준비
```cmd
# Docker 확인
docker ps

# Redis 확인
redis-cli ping

# venv 활성화
.\trading_bot_env\Scripts\activate

# 환경 초기화
python scripts\infra_cleanup.py --skip-docker
```

### 2. 캠페인 실행
```cmd
# C1/C2/C3 중 선택하여 실행
python scripts\run_multisymbol_longrun.py ...
```

### 3. 실시간 모니터링
```cmd
# 로그 tail (별도 터미널)
Get-Content logs\*.log -Wait -Tail 50

# Redis 상태 확인
redis-cli
> KEYS *
> GET arbitrage:session:*
```

### 4. 결과 분석
```cmd
# 로그 분석
python scripts\analyze_longrun_logs.py --log-file logs\...log

# 메트릭 확인
python scripts\export_metrics.py --session-id ...
```

---

## 📝 리포트 템플릿

각 캠페인 실행 후 다음 형식으로 리포트 작성:

```markdown
# [캠페인명] 실행 결과

**실행 시각:** YYYY-MM-DD HH:MM:SS  
**실행 시간:** N분  
**심볼:** [...]

## 메트릭

| 지표 | 값 | 기준 | 상태 |
|------|-----|------|------|
| Entry | N회 | ≥ X | ✅/❌ |
| Exit | N회 | ≥ X | ✅/❌ |
| Winrate | N% | 계산 가능 | ✅/❌ |
| PnL | $N | ≠ $0.00 | ✅/❌ |

## 로그 샘플

```
[timestamp] Entry: ...
[timestamp] Exit: ...
[timestamp] PnL: ...
```

## 이슈

- [ ] 이슈 1
- [ ] 이슈 2

## 결론

✅ PASS / ❌ FAIL
```

---

## 🎯 D64 Done 조건과의 연계

D64는 "문제 점검"이 목표이므로:

- ✅ 이 문서 작성 완료
- ✅ 캠페인 정의 완료
- ❌ 실제 캠페인 실행은 **D65에서 수행**

D65 TRADE_LIFECYCLE_FIX에서:
- C1 실행 → Entry/Exit/PnL 검증
- 문제 발견 시 즉시 수정 → 재실행
- 모든 기준 충족 시 D65 완료

---

**작성자:** Windsurf Cascade (AI)  
**검증:** D_ROADMAP.md 기준  
**상태:** ✅ 완료
