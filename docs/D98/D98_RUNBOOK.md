# D98 Runbook: Production LIVE Mode 운영 가이드

**작성일**: 2025-12-18  
**대상**: 운영자 (Operator)  
**목적**: LIVE 모드 실행, 모니터링, 중단, 롤백 절차

---

## ⚠️ 중요 안전 원칙

1. **LIVE 모드는 실자금 거래**: 모든 주문이 실제 거래소에 전송됨
2. **Fail-Closed 안전장치**: 실수로 실행되지 않도록 다층 보호
3. **사용자 승인 필수**: LIVE 실행 전 반드시 사용자 승인 획득
4. **단계적 램프업**: PAPER → LIVE(소액) → LIVE(점진 확대)
5. **Kill-switch 항시 대기**: 비정상 징후 시 즉시 중단

---

## 1. 사전 준비 (Pre-flight)

### 1.1 Preflight 체크 실행

**명령어**:
```bash
python scripts/d98_live_preflight.py --dry-run --output docs/D98/evidence/live_preflight_dryrun.json
```

**점검 항목**:
- [ ] 환경 변수 (ARBITRAGE_ENV, 시크릿)
- [ ] LIVE 안전장치 상태
- [ ] DB/Redis 연결
- [ ] 거래소 Health (API 응답)
- [ ] 오픈 포지션/오더 확인
- [ ] Git 안전 (.env.live 커밋 방지)

**결과**:
- ✅ 모든 항목 PASS → 다음 단계 진행
- ❌ 하나라도 FAIL → 문제 해결 후 재실행

---

### 1.2 LIVE ARM 환경변수 설정

**안전 장치**: LIVE 모드는 다음 3가지 환경변수가 **모두** 설정되어야만 실행됨

```bash
# 1. LIVE 리스크 확인 (ACK)
export LIVE_ARM_ACK="I_UNDERSTAND_LIVE_RISK"

# 2. ARM 타임스탬프 (10분 이내 유효)
export LIVE_ARM_AT=$(date +%s)

# 3. 최대 거래 금액 (USD)
export LIVE_MAX_NOTIONAL_USD=100.0
```

**주의사항**:
- `LIVE_ARM_AT`은 10분 후 자동 만료 (재사용 방지)
- `LIVE_MAX_NOTIONAL_USD`는 10~1000 범위만 허용
- 환경변수 설정 후 즉시 실행 (10분 이내)

---

### 1.3 .env 파일 준비

**LIVE 전용 환경 파일**: `.env.live` (절대 커밋 금지)

```bash
# LIVE 모드
ARBITRAGE_ENV=live

# 거래소 API (READ-WRITE 권한)
UPBIT_ACCESS_KEY=<LIVE_KEY>
UPBIT_SECRET_KEY=<LIVE_SECRET>
BINANCE_API_KEY=<LIVE_KEY>
BINANCE_API_SECRET=<LIVE_SECRET>

# 알림 (Telegram 필수)
TELEGRAM_BOT_TOKEN=<TOKEN>
TELEGRAM_CHAT_ID=<CHAT_ID>

# DB/Redis
POSTGRES_DSN=postgresql://...
REDIS_URL=redis://...

# 모니터링
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9100
```

**검증**:
```bash
# .env.live가 .gitignore에 포함되어 있는지 확인
grep -q ".env.live" .gitignore && echo "✅ Safe" || echo "❌ DANGER"
```

---

## 2. LIVE 실행 (단계적 램프업)

### 2.1 Phase 1: LIVE 소액 테스트 (5분)

**목표**: 실자금 환경에서 최소 규모로 정상 작동 확인

**명령어**:
```bash
# 환경변수 로드
source .env.live

# LIVE ARM 설정
export LIVE_ARM_ACK="I_UNDERSTAND_LIVE_RISK"
export LIVE_ARM_AT=$(date +%s)
export LIVE_MAX_NOTIONAL_USD=50.0

# 5분 소액 테스트 실행
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --universe top10 \
  --duration-minutes 5 \
  --kpi-output-path logs/live/live_5min_test.json \
  --data-source real
```

**모니터링 체크리스트**:
- [ ] 첫 1분: Entry 시도 1회 이상
- [ ] 첫 2분: Exit 완료 1회 이상
- [ ] Loop latency < 50ms
- [ ] CPU < 50%, Memory < 200MB
- [ ] Telegram 알림 수신
- [ ] Prometheus 메트릭 수집 정상

**중단 조건** (즉시 Ctrl+C):
- ❌ 3분 경과해도 Entry 0회
- ❌ Loop latency > 100ms 지속
- ❌ CPU > 80% 지속
- ❌ 예외/에러 발생

---

### 2.2 Phase 2: LIVE 중간 규모 (30분)

**목표**: 안정성 검증 및 PnL 추이 확인

**명령어**:
```bash
# LIVE ARM 설정 (재설정 필요)
export LIVE_ARM_ACK="I_UNDERSTAND_LIVE_RISK"
export LIVE_ARM_AT=$(date +%s)
export LIVE_MAX_NOTIONAL_USD=100.0

# 30분 실행
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --universe top20 \
  --duration-minutes 30 \
  --kpi-output-path logs/live/live_30min.json \
  --data-source real
```

**KPI 목표**:
- Round trips ≥ 5
- Win rate ≥ 50%
- Total PnL ≥ -$10 (손실 제한)
- Loop latency (avg) < 30ms

---

### 2.3 Phase 3: LIVE 본격 운영 (1시간+)

**목표**: Production 규모 운영

**명령어**:
```bash
# LIVE ARM 설정 (최대 금액)
export LIVE_ARM_ACK="I_UNDERSTAND_LIVE_RISK"
export LIVE_ARM_AT=$(date +%s)
export LIVE_MAX_NOTIONAL_USD=500.0

# 1시간 실행
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --universe top50 \
  --duration-minutes 60 \
  --kpi-output-path logs/live/live_1h.json \
  --data-source real
```

**점진 확대 계획**:
- Day 1: $100/trade, 5분씩 5회 (총 25분)
- Day 2: $200/trade, 30분씩 2회 (총 1시간)
- Day 3: $500/trade, 1시간씩 2회 (총 2시간)
- Day 4+: $500/trade, 연속 운영

---

## 3. 모니터링 (10종 KPI)

### 3.1 실시간 모니터링 (필수)

**콘솔 로그**:
```bash
tail -f logs/live/live_*.log
```

**Prometheus 메트릭** (http://localhost:9100/metrics):
1. `arbitrage_loop_latency_ms` (< 50ms 목표)
2. `arbitrage_round_trips_total` (증가 추이)
3. `arbitrage_pnl_usd_total` (실시간 PnL)
4. `arbitrage_win_rate` (≥ 50%)
5. `arbitrage_cpu_percent` (< 50%)
6. `arbitrage_memory_mb` (< 200MB)
7. `arbitrage_exchange_errors_total` (< 5/min)
8. `arbitrage_rate_limit_wait_seconds` (< 1s)
9. `arbitrage_open_positions` (≤ max_concurrent)
10. `arbitrage_failed_fills_total` (= 0)

**Grafana 대시보드**: http://localhost:3000
- Real-time PnL 차트
- Loop latency histogram
- Exchange health status
- Alert 히스토리

---

### 3.2 이상 징후 (즉시 중단)

| 징후 | 임계값 | 조치 |
|-----|--------|------|
| Loop latency | > 100ms (1분 지속) | Kill-switch |
| CPU | > 80% (2분 지속) | Kill-switch |
| Memory | > 300MB | Kill-switch |
| PnL 급락 | < -$50 (30분 이내) | Kill-switch |
| Exchange 에러 | > 10/min | Kill-switch |
| Rate limit hit | > 5회 (10분) | Kill-switch |
| Entry 0회 | 5분 경과 | 조사 후 판단 |
| Exit 0회 | 10분 경과 | 조사 후 판단 |

---

## 4. Kill-Switch (긴급 중단)

### 4.1 수동 중단

**방법 1**: Ctrl+C (graceful shutdown)
```bash
# 콘솔에서 Ctrl+C 입력
# → SIGINT 시그널 → 현재 포지션 청산 → KPI JSON 저장 → 종료
```

**방법 2**: SIGTERM (권장)
```bash
# 프로세스 ID 확인
ps aux | grep run_d77_0

# SIGTERM 전송
kill -TERM <PID>

# 10초 대기 후 강제 종료
sleep 10
kill -9 <PID>
```

**방법 3**: Kill-switch 스크립트 (미구현)
```bash
# TODO: D98-1에서 구현 예정
python scripts/kill_switch.py --reason "manual_stop"
```

---

### 4.2 자동 중단 (Guard)

**Kill-switch 조건** (코드 레벨):
- Daily loss > $300
- Single trade loss > $100
- Open positions > 10
- Memory > 500MB
- Consecutive errors > 5

**구현 위치**: `arbitrage/guards/` (D98-1에서 구현 예정)

---

## 5. 중단 후 점검

### 5.1 KPI 확인

**KPI JSON 파일 확인**:
```bash
cat logs/live/live_*.json | jq '.summary'
```

**점검 항목**:
- [ ] exit_code == 0 (정상 종료)
- [ ] round_trips_completed (목표 대비)
- [ ] total_pnl_usd (손익)
- [ ] win_rate (≥ 50%)
- [ ] failed_fills_count (= 0)
- [ ] kill_switch_triggered (false)

---

### 5.2 거래소 잔고 확인

**Upbit**:
```bash
# TODO: 잔고 조회 스크립트
python scripts/check_upbit_balance.py
```

**Binance**:
```bash
# TODO: 잔고 조회 스크립트
python scripts/check_binance_balance.py
```

**Reconciliation**:
- [ ] Bot PnL vs 거래소 실제 PnL 일치
- [ ] Open positions = 0
- [ ] Open orders = 0

---

### 5.3 로그 분석

**에러 로그 추출**:
```bash
grep -i "error\|exception\|fail" logs/live/live_*.log > logs/live/errors.txt
```

**주요 확인 사항**:
- Exchange API 에러
- Rate limit 에러
- Fill model 실패
- DB/Redis 연결 에러

---

## 6. 롤백 절차

### 6.1 LIVE → PAPER 전환

**긴급 시나리오**: LIVE 모드에서 심각한 문제 발생

**절차**:
1. Kill-switch 실행 (Ctrl+C 또는 SIGTERM)
2. 모든 오픈 포지션 수동 청산 (거래소 웹/앱)
3. 환경변수 변경:
   ```bash
   export ARBITRAGE_ENV=paper
   unset LIVE_ARM_ACK
   unset LIVE_ARM_AT
   unset LIVE_MAX_NOTIONAL_USD
   ```
4. PAPER 모드 재실행으로 전환
5. 원인 분석 및 수정
6. D98 Preflight 재실행
7. LIVE 재시도 (Phase 1부터)

---

### 6.2 코드 롤백

**Git 롤백**:
```bash
# 이전 안정 버전으로 롤백
git log --oneline -10
git checkout <STABLE_COMMIT_SHA>

# 의존성 재설치
pip install -r requirements.txt

# DB 마이그레이션 롤백 (필요 시)
alembic downgrade -1
```

---

## 7. 포스트모템 (사후 분석)

### 7.1 문제 발생 시

**기록 항목**:
- 발생 시각 (UTC)
- 증상 (로그, 메트릭)
- 원인 (추정)
- 조치 사항
- 재발 방지책

**보고서 위치**: `docs/D98/incidents/YYYY-MM-DD_incident.md`

---

### 7.2 정상 운영 시

**일일 리포트**:
- Total runtime (hours)
- Round trips (count)
- Total PnL (USD)
- Win rate (%)
- Max drawdown (USD)
- Exchange API 에러 (count)
- Rate limit 발생 (count)

**주간 리포트**:
- Weekly PnL (USD)
- Avg win rate (%)
- Best/worst day
- 개선 사항

---

## 8. 체크리스트 (Quick Reference)

### 8.1 LIVE 실행 전

- [ ] D98 Preflight PASS
- [ ] .env.live 준비 (커밋 안 됨)
- [ ] LIVE ARM 환경변수 설정
- [ ] Telegram 알림 테스트
- [ ] Prometheus/Grafana 실행 중
- [ ] 사용자 승인 획득

---

### 8.2 LIVE 실행 중

- [ ] 콘솔 로그 실시간 모니터링
- [ ] Prometheus 메트릭 확인 (5분마다)
- [ ] Grafana 대시보드 열어두기
- [ ] Telegram 알림 수신 확인
- [ ] 이상 징후 즉시 대응

---

### 8.3 LIVE 실행 후

- [ ] KPI JSON 확인
- [ ] 거래소 잔고 reconciliation
- [ ] 에러 로그 분석
- [ ] 일일 리포트 작성
- [ ] 개선 사항 문서화

---

## 9. 연락처 (긴급)

**운영자**: <사용자 이메일>  
**Telegram 봇**: <봇 링크>  
**Grafana**: http://localhost:3000  
**Prometheus**: http://localhost:9100  

**긴급 시나리오별 대응**:
- 거래소 API 장애 → 수동 청산 (웹/앱)
- Bot 크래시 → Kill-switch → 로그 분석
- PnL 급락 → 즉시 중단 → 포지션 확인
- Network 문제 → 재연결 대기 (최대 5분)

---

**문서 버전**: 1.0  
**최종 수정**: 2025-12-18  
**다음 리뷰**: D98-1 완료 후
