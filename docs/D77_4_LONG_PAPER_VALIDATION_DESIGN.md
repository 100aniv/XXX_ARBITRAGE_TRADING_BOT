# D77-4: TopN Arbitrage Long PAPER Validation (≥1h) - 설계 문서

**Status:** 📋 **DESIGN**  
**작성일:** 2025-12-03  
**작성자:** arbitrage-lite Development Team

---

## 1. 목표 정의

### 1.1 목적

**D77-4의 핵심 목적:**

TopN Arbitrage 엔진을 **실제 시장 데이터(Upbit/Binance Public API) + PAPER 모드**에서 **최소 1시간 이상** 연속 실행하면서, D77-1/2/3에서 구축한 **모니터링 & 알림 스택 전체**가 설계된 대로 동작하는지 **엔드투엔드로 검증**합니다.

**검증 대상:**
1. **Trading KPI:** PnL, 승률, 포지션 수, 스프레드 동작
2. **Risk Management:** Guard 트리거 패턴, Fail-safe 동작
3. **Monitoring Stack:** D77-1 Prometheus Metrics, D77-2 Grafana Dashboard
4. **Alerting Stack:** D76 AlertManager, D77-3 Runbook/Playbook
5. **Performance:** Loop latency, CPU, 메모리, 장기 안정성

**최종 판단 기준:**

> "장기 PAPER를 돌렸을 때, 시스템이 안전하고 의도대로 리스크를 제어하면서 수익 구조가 합리적인가?"

**차별점 (vs D77-0/D77-0-RM):**
- D77-0: Mock 5분 → 기술적 구조 검증
- D77-0-RM: Real 10분 → Real Market 통합 검증
- **D77-4: Real 1h+** → **장기 안정성 + 모니터링/알림 스택 종합 검증**

---

### 1.2 실행 조건

| 항목 | 설정 | 비고 |
|------|------|------|
| **데이터 소스** | `--data-source real` | Upbit/Binance Public API |
| **Universe** | `--topn-size 50` (최소) | Top50 고정 또는 유연하게 |
| **실행 시간** | `--run-duration-seconds 3600` (최소) | 1h = 3600s, 테스트용으로는 60s 가능 |
| **모니터링** | `--monitoring-enabled` | D77-1 Prometheus Metrics (/metrics) |
| **Alerting** | 자동 활성화 | D76 AlertManager + D77-3 Runbook/Playbook |
| **Environment** | `local_dev` or `paper` | D78-0 Settings 기준 |
| **KPI 출력** | `--kpi-output-path logs/d77-4/...` | JSON 형식 |

---

### 1.3 측정할 KPI 목록

#### Trading KPI (11개)
1. **Total Trades** - 총 거래 수 (Entry + Exit)
2. **Entry Trades** - 진입 거래 수
3. **Exit Trades** - 청산 거래 수
4. **Round Trips** - 완전한 entry → exit 사이클
5. **Win Rate (%)** - 수익 난 포지션의 비율
6. **Total PnL (USD)** - 총 실현 손익
7. **Gross PnL (USD)** - 수수료/슬리피지 제외 손익
8. **Net PnL (USD)** - 수수료/슬리피지 포함 최종 손익
9. **Max Drawdown (USD)** - 최대 낙폭
10. **Average Win (USD)** - 수익 거래 평균
11. **Average Loss (USD)** - 손실 거래 평균

#### Risk Management KPI (6개)
12. **Guard Triggers (Total)** - RiskGuard 발동 총 횟수
13. **Guard Triggers by Type** - Exchange/Route/Symbol/Global/CrossExchange별 발동
14. **Guard False Positives** - 명백한 오탐 횟수 (수동 판단)
15. **Guard Block Duration (avg)** - 차단 지속 시간 평균
16. **Position Limit Hits** - 포지션 한도 도달 횟수
17. **Emergency Stops** - 긴급 정지 발동 횟수

#### Performance KPI (7개)
18. **Loop Latency (avg)** - 엔진 루프 평균 레이턴시 (ms)
19. **Loop Latency (p95)** - 95 percentile 레이턴시
20. **Loop Latency (p99)** - 99 percentile 레이턴시
21. **CPU Usage (avg %)** - 평균 CPU 사용률
22. **Memory Usage (peak MB)** - 최대 메모리 사용량
23. **Error Rate (%)** - 전체 루프 대비 에러 발생 비율
24. **Crash/HANG Count** - 크래시 또는 행(HANG) 발생 횟수

#### Alerting KPI (8개)
25. **Alert Sent (Total)** - 전송 성공 알림 수
26. **Alert Failed (Total)** - 전송 실패 알림 수
27. **Alert Retry (Total)** - 재시도 알림 수
28. **Alert DLQ (Total)** - Dead Letter Queue 항목 수
29. **Alert Success Rate (%)** - (Sent / (Sent + Failed)) * 100
30. **Notifier Availability (%)** - Notifier별 가용성 (Telegram/Slack/Email)
31. **Fallback Usage (Total)** - 보조 Notifier 사용 횟수
32. **Alert Delivery Latency (p95)** - 알림 전송 레이턴시 95%ile

---

### 1.4 Acceptance Criteria (초안)

D77-4 Long PAPER Validation을 **PASS**로 간주하기 위한 기준:

#### Critical (반드시 충족)
- [C1] **1h+ 연속 실행** 완료 (Uncaught exception / HANG = 0)
- [C2] **Core KPI 32종** 모두 수집 및 리포트 작성
- [C3] **Crash/HANG Count = 0** (전체 실행 기간 동안)
- [C4] **Alert DLQ = 0** (Dead Letter Queue 0건)
- [C5] **Prometheus /metrics** 엔드포인트 1h 동안 정상 응답
- [C6] **Grafana Dashboard** 데이터 정상 표시 (수동 확인)

#### High Priority (권장)
- [H1] **Loop Latency p99** ≤ 80ms (D77-3 Runbook 기준)
- [H2] **CPU Usage (avg)** ≤ 70% (장기 실행 기준)
- [H3] **Memory Usage** 증가율 ≤ 10%/hour (메모리 leak 방지)
- [H4] **Alert Success Rate** ≥ 95% (D77-3 Runbook 기준)
- [H5] **Guard False Positive** ≤ 5% (전체 Guard 발동 대비)
- [H6] **Round Trips** ≥ 10 (최소 10회 완전한 사이클)

#### Medium Priority (참고)
- [M1] **Win Rate** 50~80% 범위 (전략 특성상 납득 가능한 분포)
- [M2] **PnL** 플러스 또는 "전략 특성상 납득 가능한 분포" (무조건 플러스 아님)
- [M3] **Exit Reasons** 다양성 (TP/SL/Time/Reversal 모두 발생)
- [M4] **Notifier Availability** 100% (Telegram/Slack 모두 정상)

**CONDITIONAL GO 기준:**
- Critical (C1~C6) 모두 충족 + High Priority 4개 이상 충족 → **CONDITIONAL GO**
- 나머지 항목은 개선 권장사항으로 남기고 다음 단계 진행 가능

**NO-GO 기준:**
- Critical 1개라도 미충족 → **NO-GO** (재검증 필요)

---

## 2. 실행 설계

### 2.1 Runner 선택

**옵션 분석:**

**Option 1: 기존 `run_d77_0_topn_arbitrage_paper.py` 재사용**
- ✅ 장점: 이미 구현됨, --data-source real 지원, KPI 수집 로직 완비
- ✅ 장점: D77-1 Prometheus Metrics 통합 완료
- ⚠️ 단점: 1h 실행을 위한 추가 옵션 필요 (--run-duration-seconds)
- **판단:** **재사용 권장** (최소 수정으로 D77-4 목표 달성 가능)

**Option 2: 새로운 `run_d77_4_long_paper.py` 작성**
- ✅ 장점: D77-4 전용 설정/로직 분리 가능
- ❌ 단점: 중복 코드 발생, 유지보수 부담
- **판단:** 불필요 (기존 Runner로 충분)

**최종 선택:** **Option 1 (기존 Runner 재사용)**

---

### 2.2 Runner 수정 사항

**기존 `run_d77_0_topn_arbitrage_paper.py`에 추가할 최소 변경:**

#### 1. CLI 옵션 추가
```python
parser.add_argument(
    "--run-duration-seconds",
    type=int,
    default=None,
    help="실행 시간 (초). 지정하면 --duration-minutes 무시",
)
parser.add_argument(
    "--topn-size",
    type=int,
    default=20,
    help="TopN 심볼 개수 (10/20/50/100)",
)
parser.add_argument(
    "--kpi-output-path",
    type=str,
    default=None,
    help="KPI 출력 JSON 파일 경로 (예: logs/d77-4/d77-4-<timestamp>_kpi_summary.json)",
)
```

#### 2. Duration 계산 로직 수정
```python
# --run-duration-seconds 우선, 없으면 --duration-minutes 사용
if args.run_duration_seconds:
    duration_seconds = args.run_duration_seconds
    duration_minutes = duration_seconds / 60.0
else:
    duration_minutes = args.duration_minutes
    duration_seconds = duration_minutes * 60
```

#### 3. TopN 모드 유연화
```python
# --topn-size 기반 TopNMode 선택
topn_size_to_mode = {
    10: TopNMode.TOP_10,
    20: TopNMode.TOP_20,
    50: TopNMode.TOP_50,
    100: TopNMode.TOP_100,
}
universe_mode = topn_size_to_mode.get(args.topn_size, TopNMode.TOP_20)
```

#### 4. 주기적 KPI 로깅 (1분 간격)
```python
# 60s마다 중간 KPI 로깅
if iteration % 600 == 0:  # 100ms * 600 = 60s
    logger.info(f"[D77-4] 중간 KPI (t={iteration//600}min): ...")
    self._log_interim_kpi()
```

---

### 2.3 실행 명령어 예시

#### 테스트용 (60초)
```bash
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --data-source real \
  --topn-size 50 \
  --run-duration-seconds 60 \
  --monitoring-enabled \
  --kpi-output-path logs/d77-4/d77-4-test-60s_kpi_summary.json
```

#### 실제 검증용 (1시간)
```bash
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --data-source real \
  --topn-size 50 \
  --run-duration-seconds 3600 \
  --monitoring-enabled \
  --kpi-output-path logs/d77-4/d77-4-1h_kpi_summary.json
```

#### 장기 검증용 (12시간)
```bash
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --data-source real \
  --topn-size 50 \
  --run-duration-seconds 43200 \
  --monitoring-enabled \
  --kpi-output-path logs/d77-4/d77-4-12h_kpi_summary.json
```

---

## 3. 모니터링 & 알림 통합

### 3.1 D77-3 Runbook/Playbook 기반 운영 가이드

**D77-4 Long PAPER 실행 시 운영자가 따라야 할 절차:**

#### 실행 전 (Pre-flight Check)
1. **환경 확인:**
   - Redis/PostgreSQL 정상 동작 확인
   - Settings (D78-0) 로드 확인
   - Telegram/Slack Notifier credentials 확인

2. **모니터링 스택 확인:**
   - Prometheus 실행 확인 (별도 실행 또는 내장 서버)
   - Grafana 접속 확인 (http://localhost:3000)
   - D77-2 Dashboard Import 완료 확인

3. **Alerting 스택 확인:**
   - D76 AlertManager 정상 로드 확인
   - RuleEngine 환경 감지 정상 확인 (PROD/DEV)
   - Telegram Bot Token 유효성 확인

#### 실행 중 (Real-time Monitoring)
**우선순위별 패널 확인 순서 (D77-3 Runbook 기준):**

**P0 (매 5분 확인):**
1. **TopN Arbitrage Core Dashboard → Panel 1: Total PnL**
   - 급격한 하락 확인 (빨간색 경고)
   - → 이상 시: D77-3 Alerting Playbook **Section 3.7 (Excessive Loss)** 참조

2. **TopN Arbitrage Core Dashboard → Panel 6: Loop Latency (p99)**
   - p99 > 80ms 지속 확인
   - → 이상 시: D77-3 Alerting Playbook **Section 3.2 (High Loop Latency)** 참조

3. **Alerting Overview Dashboard → Panel 9: Dead Letter Queue (DLQ)**
   - DLQ > 0 확인 (즉시 조치)
   - → 이상 시: D77-3 Alerting Playbook **Section 4.1 (Alert System Failures)** 참조

**P1 (매 15분 확인):**
4. **TopN Arbitrage Core Dashboard → Panel 9: Guard Triggers**
   - 비정상적으로 높은 발동 빈도 확인 (> 10회/분)
   - → 이상 시: D77-3 Alerting Playbook **Section 3.4 (RiskGuard Overactive)** 참조

5. **TopN Arbitrage Core Dashboard → Panel 3: Trades per Hour**
   - 거래 빈도 급락 확인 (< 5 trades/h)
   - → 이상 시: D77-3 Alerting Playbook **Section 3.3 (Low Trading Activity)** 참조

**P2 (매 30분 확인):**
6. **TopN Arbitrage Core Dashboard → Panel 7-8: CPU/Memory Usage**
   - 메모리 증가 추세 확인 (leak 의심)
   - → 이상 시: D77-3 Monitoring Runbook **Section 6.2 (Memory Leak)** 참조

7. **Alerting Overview Dashboard → Panel 2: Alert Success Rate**
   - 성공률 < 95% 확인
   - → 이상 시: D77-3 Alerting Playbook **Section 4.2 (Notifier Degradation)** 참조

#### 실행 후 (Post-execution Analysis)
1. **KPI 파일 확인:**
   - `logs/d77-4/d77-4-<timestamp>_kpi_summary.json` 열기
   - **Acceptance Criteria** 체크리스트 작성

2. **로그 파일 분석:**
   - `logs/d77-0/paper_session_<timestamp>.log` 확인
   - ERROR/WARNING 라인 수 집계
   - Guard 트리거 패턴 분석

3. **리포트 작성:**
   - D77_4_LONG_PAPER_VALIDATION_REPORT_TEMPLATE.md 기반
   - Executive Summary, KPI Results, Acceptance Criteria, 결론 작성

---

### 3.2 Alert 시나리오 매핑

**D77-4 실행 중 발생 가능한 Alert와 Playbook 매핑:**

| Alert Rule ID | Alert 이름 | 심각도 | Playbook 섹션 | 예상 발생 빈도 |
|---------------|------------|--------|---------------|----------------|
| `D76-P0-01` | Redis Connection Lost | P0 | 3.1 (FX Provider Down) | Low |
| `D76-P1-02` | High Loop Latency | P1 | 3.2 (High Loop Latency) | Medium |
| `D76-P1-03` | Exchange Health DOWN | P1 | 3.1 (FX Provider Down) | Low |
| `D76-P1-04` | RiskGuard Overactive | P1 | 3.4 (RiskGuard Overactive) | Medium |
| `D76-P2-05` | Low Trading Activity | P2 | 3.3 (Low Trading Activity) | Medium |
| `D76-P2-06` | Memory Usage High | P2 | 6.2 (Memory Leak) | Low |
| `D76-P3-07` | Notifier Degraded | P3 | 4.2 (Notifier Degradation) | Low |

**Alert 테스트 방법 (선택 사항):**
- D76-4 Incident Simulation 스크립트 사용:
  ```bash
  python scripts/run_d76_4_incident_simulation.py --scenario high_loop_latency --env paper
  ```

---

## 4. 테스트 설계

### 4.1 Unit Test (Harness 로직)

**파일:** `tests/test_d77_4_long_paper_harness.py`

**테스트 케이스 (10개):**

1. `test_cli_args_parsing` - CLI 옵션 파싱 정상 확인
2. `test_run_duration_seconds_priority` - --run-duration-seconds 우선 적용 확인
3. `test_topn_size_mode_mapping` - TopN size → TopNMode 매핑 확인
4. `test_kpi_output_path` - KPI 파일 생성 확인
5. `test_short_run_10s` - 10초 짧은 실행 정상 종료 확인
6. `test_metrics_endpoint_alive` - Prometheus /metrics 엔드포인트 정상 응답 확인
7. `test_kpi_collection_complete` - 32종 KPI 모두 수집 확인
8. `test_no_crash_during_run` - 실행 중 exception 0 확인
9. `test_graceful_shutdown` - SIGINT/SIGTERM 정상 종료 확인
10. `test_log_file_creation` - 로그 파일 생성 확인

**실행 시간:**
- 전체 테스트: 30~60초 (10초 실행 * 여러 케이스)

---

### 4.2 Integration Test (Manual)

**실제 1h+ 실행은 사람이 수동으로 수행:**

**절차:**
1. 환경 준비 (Redis/PostgreSQL 실행, Settings 설정)
2. Grafana 실행 및 Dashboard Import
3. D77-4 Runner 실행 (1h or 12h)
4. 운영자가 D77-3 Runbook에 따라 실시간 모니터링
5. 실행 완료 후 KPI 파일 확인
6. 리포트 작성 (D77_4_LONG_PAPER_VALIDATION_REPORT_TEMPLATE.md 기반)

**테스트 환경 권장:**
- 전용 서버 또는 장시간 가능한 로컬 환경
- 최소 CPU 2 cores, RAM 4GB, 디스크 여유 공간 10GB

---

## 5. 파일 구조

### 5.1 신규 파일

| 파일 | 역할 | 라인 수 (예상) |
|------|------|----------------|
| `docs/D77_4_LONG_PAPER_VALIDATION_DESIGN.md` | 설계 문서 (this file) | ~600 |
| `docs/D77_4_LONG_PAPER_VALIDATION_REPORT_TEMPLATE.md` | 리포트 템플릿 | ~400 |
| `tests/test_d77_4_long_paper_harness.py` | Unit Test | ~350 |
| `logs/d77-4/` | KPI 출력 디렉토리 | - |

### 5.2 수정 파일

| 파일 | 수정 내용 | 라인 수 변화 |
|------|-----------|--------------|
| `scripts/run_d77_0_topn_arbitrage_paper.py` | CLI 옵션 추가 (--run-duration-seconds, --topn-size, --kpi-output-path) | +50 |
| `D_ROADMAP.md` | D77-4 섹션 추가 | +40 |

**총 변경량:** ~1,400 lines (신규 + 수정)

---

## 6. Acceptance Criteria Summary

### Implementation Phase (이 설계 문서 기준)

- [ ] **D77-4 설계 문서** 작성 완료 (this file)
- [ ] **리포트 템플릿** 작성 완료
- [ ] **Runner CLI 옵션** 추가 (--run-duration-seconds, --topn-size, --kpi-output-path)
- [ ] **Unit Tests** 10/10 PASS
- [ ] **테스트 실행** 10초 샘플 정상 완료
- [ ] **문서화** D_ROADMAP.md 업데이트

### Validation Phase (실제 1h+ 실행 후)

- [ ] **1h+ 실행** 완료 (Crash/HANG = 0)
- [ ] **Core KPI 32종** 수집 및 리포트 작성
- [ ] **Prometheus /metrics** 1h 동안 정상 응답
- [ ] **Grafana Dashboard** 데이터 정상 표시
- [ ] **Alert DLQ = 0**
- [ ] **Acceptance Criteria** 체크리스트 작성

---

## 7. 실행 가이드 (운영자용)

### 7.1 사전 준비

**1단계: 인프라 확인**
```bash
# Redis
redis-cli ping  # PONG 응답 확인

# PostgreSQL
psql -U postgres -c "SELECT 1"  # 1 응답 확인

# Python 환경
python --version  # 3.8+ 확인
pip list | grep prometheus  # prometheus_client 설치 확인
```

**2단계: Settings 설정 (D78-0)**
```bash
# .env 파일 생성 (paper 환경)
python scripts/setup_env.py --env paper

# 검증
python scripts/validate_env.py --env paper --verbose
```

**3단계: Grafana 실행 (선택 사항)**
```bash
# Docker Compose로 Grafana 실행
docker-compose up -d grafana

# 브라우저에서 http://localhost:3000 접속
# Dashboard Import: monitoring/grafana/dashboards/*.json
```

---

### 7.2 실행

**테스트 실행 (60초):**
```bash
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --data-source real \
  --topn-size 50 \
  --run-duration-seconds 60 \
  --monitoring-enabled \
  --kpi-output-path logs/d77-4/d77-4-test-60s_kpi_summary.json
```

**실제 검증 실행 (1시간):**
```bash
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --data-source real \
  --topn-size 50 \
  --run-duration-seconds 3600 \
  --monitoring-enabled \
  --kpi-output-path logs/d77-4/d77-4-1h_kpi_summary.json
```

**실행 중 모니터링:**
- Grafana: http://localhost:3000/d/topn-arbitrage-core
- Prometheus: http://localhost:9100/metrics
- 로그: `tail -f logs/d77-0/paper_session_<timestamp>.log`

---

### 7.3 실행 후 분석

**1단계: KPI 파일 확인**
```bash
cat logs/d77-4/d77-4-1h_kpi_summary.json | jq .
```

**2단계: Acceptance Criteria 체크**
```bash
# Acceptance Criteria 체크리스트 작성
# D77_4_LONG_PAPER_VALIDATION_REPORT_TEMPLATE.md 참조
```

**3단계: 리포트 작성**
```bash
# 템플릿 복사
cp docs/D77_4_LONG_PAPER_VALIDATION_REPORT_TEMPLATE.md \
   docs/D77_4_LONG_PAPER_VALIDATION_REPORT.md

# 실제 결과 작성
# (수동 편집)
```

---

## 8. 리스크 & 완화 전략

### 8.1 Known Risks

| 리스크 | 확률 | 영향도 | 완화 전략 |
|--------|------|--------|-----------|
| **R1: 1h 실행 중 크래시** | Medium | High | • 사전 Unit Test 철저히 수행<br>• 10분 실행 먼저 검증 후 1h 진행 |
| **R2: Memory Leak** | Low | High | • psutil로 주기적 메모리 모니터링<br>• 메모리 증가 추세 자동 경고 |
| **R3: Network 장애 (Upbit API)** | Medium | Medium | • Retry 로직 내장<br>• Cache 활용 (TopN Provider 1h TTL) |
| **R4: Alert DLQ 발생** | Low | High | • D76 AlertManager Retry 로직 검증<br>• Telegram Bot Token 사전 확인 |
| **R5: Grafana Dashboard 데이터 누락** | Low | Medium | • Prometheus scrape_interval 조정<br>• /metrics 엔드포인트 주기적 health check |

---

## 9. Success Criteria (최종)

**D77-4를 "COMPLETE"로 간주하기 위한 최종 기준:**

### Implementation Phase
- [x] 설계 문서 작성 (this file)
- [ ] 리포트 템플릿 작성
- [ ] Runner CLI 옵션 추가
- [ ] Unit Tests 10/10 PASS
- [ ] 테스트 실행 (10초 샘플) 정상 완료
- [ ] D_ROADMAP.md 업데이트
- [ ] Git 커밋

### Validation Phase (실제 1h+ 실행 후)
- [ ] Critical Criteria (C1~C6) 모두 충족
- [ ] High Priority (H1~H6) 4개 이상 충족
- [ ] 리포트 작성 완료
- [ ] **판단:** CONDITIONAL GO 또는 COMPLETE

---

## 10. Next Steps

### Immediate (D77-4 Implementation)
1. 리포트 템플릿 작성
2. Runner CLI 옵션 추가
3. Unit Tests 구현
4. 테스트 실행 (10초 샘플)
5. D_ROADMAP.md 업데이트
6. Git 커밋

### Short-term (D77-4 Validation)
1. 1h 실제 실행 (수동)
2. Acceptance Criteria 체크
3. 리포트 작성
4. 판단: GO / CONDITIONAL GO / NO-GO

### Long-term (Post-D77-4)
- D78: Authentication & Secrets Layer
- D79: Cross-Exchange Arbitrage Stack
- D80: Multi-Currency Support
- D81~D85: Production Operations

---

**문서 버전:** 1.0  
**최종 수정일:** 2025-12-03  
**상태:** 📋 **DESIGN COMPLETE**
