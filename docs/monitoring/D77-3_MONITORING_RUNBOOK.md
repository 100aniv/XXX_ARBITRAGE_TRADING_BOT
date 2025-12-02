# D77-3 모니터링 런북 (TopN Arbitrage & Alerting)

**버전:** 1.0  
**최종 업데이트:** 2025-12-02  
**대상:** 운영팀, SRE, DevOps  
**관련 문서:**
- [D77-1 Prometheus Exporter Design](../D77_1_PROMETHEUS_EXPORTER_DESIGN.md)
- [D77-2 Grafana Dashboard Design](../D77_2_GRAFANA_DASHBOARD_DESIGN.md)
- [D77-3 Alerting Playbook](./D77-3_ALERTING_PLAYBOOK.md)
- [D80-7 Alerting System Design](../D80_7_ALERTING_SYSTEM_DESIGN.md)

---

## 1. 개요

### 1.1 시스템 아키텍처

본 런북은 **CrossExchange** 및 **Alerting** 기능이 통합된 **TopN Arbitrage Trading System**의 운영 모니터링을 다룹니다.

**주요 구성 요소:**
1. **Trading Engine (거래 엔진)**
   - TopN Arbitrage Engine (Paper/Live 모드)
   - CrossExchange Strategy & Position Manager
   - 4-Tier RiskGuard (Exchange → Route → Symbol → Global + CrossExchange)

2. **Metrics Collection (메트릭 수집)**
   - `CrossExchangeMetrics` (PnL, trades, latency, resources, guards)
   - `AlertMetrics` (sent, failed, fallback, retry, DLQ, latency, availability)
   - Prometheus Exporter: `/metrics` endpoint (port 9100)

3. **Alerting Pipeline (알림 파이프라인)**
   - AlertManager + RuleEngine (D76, D80-7~13)
   - Dispatcher + Routing (우선순위 기반, 환경별 분기)
   - Notifiers: Telegram, Slack, Email, Local Log
   - Fail-safe: Retry, Fallback, DLQ, Chaos Testing

4. **Visualization (시각화)**
   - **Grafana Dashboards:**
     - `topn_arbitrage_core.json` (11개 패널: 거래, 성능, 리스크)
     - `alerting_overview.json` (10개 패널: Alert 파이프라인 상태)
   - **Prometheus:** 시계열 데이터베이스 (메트릭 저장)

---

### 1.2 모니터링 목표

| 목표 | 설명 | 주요 대시보드 |
|------|------|--------------|
| **수익성** | PnL, 승률, 거래량 추적 | TopN Arbitrage Core |
| **성능** | 루프 레이턴시, CPU, 메모리 모니터링 | TopN Arbitrage Core |
| **리스크 관리** | Guard 발동, 활성 포지션 | TopN Arbitrage Core |
| **Alert 상태** | Alert 전송 성공률, Notifier 가용성 | Alerting Overview |
| **시스템 안정성** | 에러율, DLQ, Fallback 패턴 | Alerting Overview |

---

## 2. 대시보드 및 메트릭 맵

### 2.1 TopN Arbitrage Core Dashboard

**파일:** `monitoring/grafana/dashboards/topn_arbitrage_core.json`  
**패널 수:** 11개  
**템플릿 변수:** `$env`, `$universe`, `$strategy`

| 패널 # | 패널 이름 | 메트릭 | 목적 |
|---------|------------|-----------|---------|
| 1 | **Total PnL (USD)** | `arb_topn_pnl_total{env, universe, strategy}` | 누적 손익 추이 추적 |
| 2 | **Current PnL** | `arb_topn_pnl_total` (gauge) | 실시간 PnL 상태 (초록 ≥ $1000, 노랑 ≥ $0, 빨강 < $0) |
| 3 | **Trade Rate** | `arb_topn_trades_total{trade_type="entry\|exit"}` | 분당 Entry/Exit 거래 건수 |
| 4 | **Win Rate (%)** | `arb_topn_win_rate{env, universe, strategy}` | 승률 게이지 (초록 ≥ 70%, 노랑 50-70%, 빨강 < 50%) |
| 5 | **Active Positions** | `arb_topn_active_positions{env, universe, strategy}` | 현재 열린 포지션 개수 |
| 6 | **Loop Latency (p95/p99)** | `arb_topn_loop_latency_seconds{quantile="0.95\|0.99"}` | 엔진 루프 성능 (히스토그램) |
| 7 | **CPU Usage (%)** | `arb_topn_cpu_usage_percent{env, universe, strategy}` | 시스템 CPU 사용률 |
| 8 | **Memory Usage (bytes)** | `arb_topn_memory_usage_bytes{env, universe, strategy}` | 메모리 사용량 추적 |
| 9 | **Guard Triggers** | `arb_topn_guard_triggers_total{guard_type}` | RiskGuard 발동 빈도 (5분당) |
| 10 | **Alert Count** | `arb_topn_alerts_total{severity, source}` | 알림 볼륨 (심각도/출처별, 5분당) |
| 11 | **Total Round Trips** | `arb_topn_round_trips_total{env, universe, strategy}` | 누적 완료 거래 (왕복) |

**주요 메트릭 정의:**
- **PnL:** USD 기준 실현 손익 (counter, 거래 종료 시에만 증가)
- **Win Rate:** 수익 난 포지션의 비율 (gauge, 0-100)
- **Round Trips:** 완전한 entry → exit 사이클 (counter)
- **Guard Triggers:** RiskGuard 발동 이벤트 (counter, `guard_type` 라벨: `exchange`, `route`, `symbol`, `global`, `cross_exchange`)
- **Loop Latency:** 엔진 한 반복당 소요 시간 (histogram, p50/p95/p99)

---

### 2.2 Alerting Overview Dashboard

**파일:** `monitoring/grafana/dashboards/alerting_overview.json`  
**패널 수:** 10개  
**템플릿 변수:** `$env`, `$notifier`

| 패널 # | 패널 이름 | 메트릭 | 목적 |
|---------|------------|-----------|---------|
| 1 | **Alert Volume** | `alert_sent_total`, `alert_failed_total`, `alert_dlq_total` | 분당 전송/실패/DLQ 알림 수 (시계열) |
| 2 | **Alert Success Rate (%)** | `rate(alert_sent_total) / (rate(alert_sent_total) + rate(alert_failed_total))` | 성공률 게이지 (초록 ≥ 95%, 노랑 90-95%, 빨강 < 90%) |
| 3 | **Alert Sent by Notifier** | `alert_sent_total{notifier}` | Notifier별 알림 볼륨 Top 10 (누적 막대) |
| 4 | **Alert Failed by Notifier & Reason** | `alert_failed_total{notifier, reason}` | 실패 원인별 Top 10 (누적 막대) |
| 5 | **Notifier Availability** | `notifier_available{notifier, status}` | Notifier 상태 테이블 (1=정상, 0.5=불안정, 0=불가용) |
| 6 | **Alert Delivery Latency (p95/p99)** | `alert_delivery_latency_seconds{notifier, quantile}` | Notifier 전송 레이턴시 (히스토그램) |
| 7 | **Alert Fallback** | `alert_fallback_total{from_notifier, to_notifier}` | Fallback 패턴 (from → to, 누적 막대) |
| 8 | **Alert Retry** | `alert_retry_total{rule_id}` | rule_id별 재시도 횟수 (누적 막대) |
| 9 | **Dead Letter Queue (DLQ)** | `alert_dlq_total{rule_id, reason}` | 위험 지표 (> 10이면 빨간색 경고) |
| 10 | **Alert Volume by Rule ID** | `alert_sent_total{rule_id}` | Rule ID별 알림 볼륨 Top 15 (누적 막대) |

**주요 메트릭 정의:**
- **alert_sent_total:** 성공적으로 전송된 알림 (counter, `rule_id`, `notifier` 라벨)
- **alert_failed_total:** 전송 실패 시도 (counter, `rule_id`, `notifier`, `reason` 라벨)
- **alert_fallback_total:** 보조 notifier로 fallback (counter, `from_notifier`, `to_notifier` 라벨)
- **alert_retry_total:** 재시도 횟수 (counter, `rule_id` 라벨)
- **alert_dlq_total:** Dead Letter Queue 항목 (counter, `rule_id`, `reason` 라벨)
- **alert_delivery_latency_seconds:** 알림 전송 레이턴시 (histogram, p50/p95/p99)
- **notifier_available:** Notifier 상태 (gauge, 1=정상, 0=다운)

---

## 3. 일일 모니터링 체크리스트

### 3.1 아침 점검 (하루 시작 시)

**빈도:** 하루 1회 (시장 개장 전 또는 업무 시작 시)  
**소요 시간:** 5-10분  
**대시보드:** TopN Arbitrage Core

- [ ] **단계 1: PnL 상태 점검**
  - `topn_arbitrage_core` 대시보드를 엽니다
  - **Total PnL (USD)** 패널 확인 (패널 1)
    - ✅ **정상:** 상승 추세 또는 안정 (시장 상황에 따라)
    - ⚠️ **경고:** 전일 종가 대비 10% 이상 급락
    - 🚨 **위험:** 20% 이상 하락 또는 마이너스 PnL (이전에 수익이 있었던 경우)
  - **Current PnL** 게이지 확인 (패널 2)
    - ✅ **초록:** PnL이 목표 임계값 이상
    - ⚠️ **노랑:** PnL 플러스이지만 기대치 미달
    - 🚨 **빨강:** PnL 마이너스

- [ ] **단계 2: 거래 활동 점검**
  - **Trade Rate** 확인 (패널 3)
    - 현재 거래율을 7일 평균과 비교합니다
    - ⚠️ **경고:** 평균의 50% 미만 (시장 활동 저조 또는 시스템 이슈)
    - 🚨 **위험:** 활성 시간대에 30분 이상 거래 0건
  - **Win Rate (%)** 확인 (패널 4)
    - ✅ **초록:** ≥ 70% (전략 성능 양호)
    - ⚠️ **노랑:** 50-70% (허용 가능하지만 모니터링 필요)
    - 🚨 **빨강:** < 50% (전략 성능 저조, 검토 필요)
  - **Total Round Trips** 확인 (패널 11)
    - 카운터가 증가하는지 확인 (데이터 정체 여부)

- [ ] **단계 3: 리스크 점검**
  - **Active Positions** 확인 (패널 5)
    - ✅ **정상:** 예상 범위 내 (top20의 경우 0-20, top50의 경우 0-50)
    - ⚠️ **경고:** 비정상적으로 높음 (> 베이스라인의 2배)
    - 🚨 **위험:** 시스템 한계에 근접하거나 장시간 0
  - **Guard Triggers** 확인 (패널 9)
    - ✅ **정상:** 가끔 발동 (< 시간당 10회)
    - ⚠️ **경고:** 빈번한 발동 (시간당 10-50회)
    - 🚨 **위험:** 시간당 50회 이상 또는 지속적 차단

- [ ] **단계 4: 시스템 상태 점검**
  - **Loop Latency (p95/p99)** 확인 (패널 6)
    - ✅ **정상:** p95 < 30ms, p99 < 50ms
    - ⚠️ **경고:** p95 30-60ms, p99 50-100ms
    - 🚨 **위험:** p95 > 60ms, p99 > 100ms
  - **CPU Usage (%)** 확인 (패널 7)
    - ✅ **정상:** < 50%
    - ⚠️ **경고:** 50-80%
    - 🚨 **위험:** > 80% 지속
  - **Memory Usage (bytes)** 확인 (패널 8)
    - ✅ **정상:** 사용 가능 메모리의 80% 미만
    - ⚠️ **경고:** 80-90%
    - 🚨 **위험:** > 90% (OOM 가능성)

- [ ] **단계 5: Alert 시스템 점검**
  - `alerting_overview` 대시보드로 전환합니다
  - **Notifier Availability** 확인 (패널 5)
    - ✅ **모든 notifier 상태 = 1 (가용)**
    - ⚠️ **일부 notifier 상태 = 0.5 (불안정)**
    - 🚨 **일부 notifier 상태 = 0 (불가용)**
  - **Dead Letter Queue (DLQ)** 확인 (패널 9)
    - ✅ **정상:** DLQ 카운트 = 0
    - 🚨 **위험:** DLQ 카운트 > 0 (즉시 조사 필요)
  - **Alert Success Rate (%)** 확인 (패널 2)
    - ✅ **초록:** ≥ 95%
    - ⚠️ **노랑:** 90-95%
    - 🚨 **빨강:** < 90%

---

### 3.2 실시간 모니터링 (거래 시간 중)

**빈도:** 지속적 (대시보드 상시 표시) 또는 15-30분마다  
**대시보드:** TopN Arbitrage Core (주요), Alerting Overview (보조)

**주요 화면: TopN Arbitrage Core**
1. **상단 행 (PnL, Trades):** 급격한 변화 모니터링
   - PnL은 점진적으로 증가해야 함 (또는 변동성 낮은 기간에는 안정 유지)
   - 거래율은 시장 활동과 일치해야 함
2. **중간 행 (Risk, Positions):** 이상 징후 감시
   - Guard 발동은 가끔씩이어야 하며 지속적이면 안 됨
   - 활성 포지션은 정상 범위 내에서 변동해야 함
3. **하단 행 (Performance):** 시스템 상태 확인
   - 레이턴시는 베이스라인 내에 있어야 함 (p99 < 50ms)
   - CPU/메모리는 안정적이어야 함

**보조 화면: Alerting Overview**
- **Alert Volume** (패널 1)을 주변 시야에 유지합니다
- `alert_failed_total` 또는 `alert_dlq_total`이 급증하면 전체 alert 조사로 전환합니다 (섹션 5 참조)

**즉시 조치가 필요한 상황:**
- 🚨 **PnL이 5분 내 5% 이상 하락:** Guard Triggers + 시장 상황 점검
- 🚨 **Win Rate가 40% 이하로 하락:** 전략 파라미터 검토
- 🚨 **Loop Latency p99 > 100ms:** 시스템 리소스 + 로그 점검
- 🚨 **DLQ 카운트 > 0:** Alert 파이프라인 조사 (Alerting Playbook 참조)
- 🚨 **Notifier 불가용:** Notifier 서비스 + 네트워크 점검

---

### 3.3 하루 종료 검토

**빈도:** 하루 1회 (시장 마감 후)  
**소요 시간:** 10-15분  
**대시보드:** 양쪽 모두 (Core + Alerting)

- [ ] **단계 1: 성능 요약**
  - 일일 PnL, 승률, 라운드 트립 기록
  - 과거 베이스라인 (7일, 30일)과 비교
  - 중요한 편차 기록

- [ ] **단계 2: 인시던트 검토**
  - **Alert Count** 검토 (패널 10, Core Dashboard)
  - **Alert Volume by Rule ID** 확인 (패널 10, Alerting Dashboard)
  - 가장 빈번한 알림 상위 5개 식별
  - 알림이 정당한지 또는 오탐인지 판단

- [ ] **단계 3: 리소스 추세**
  - **CPU Usage** 및 **Memory Usage** 추세 검토
  - 점진적 증가 여부 확인 (메모리 누수 가능성)
  - 70% 이상 지속 시 용량 확장 계획

- [ ] **단계 4: Guard 분석**
  - `guard_type`별 **Guard Triggers** 세부 내역 검토
  - 발동이 적절한지 또는 지나치게 보수적인지 판단
  - 전략 튜닝을 위한 패턴 기록

- [ ] **단계 5: Alert 시스템 상태**
  - 하루 종일 **Alert Success Rate**가 ≥ 95%였는지 확인
  - **Fallback** 또는 **Retry** 패턴 여부 확인 (패널 7, 8)
  - **DLQ**가 0으로 유지되었는지 확인

- [ ] **단계 6: 문서화**
  - 일일 요약을 운영 로그에 업데이트
  - 수행한 수동 개입 사항 기록
  - 후속 조사가 필요한 항목 플래그

---

## 4. 실시간 모니터링 플로우 (정상 운영)

### 4.1 대시보드 레이아웃 전략

**주 모니터:** `topn_arbitrage_core` 대시보드 (전체 화면)
- **상단 행:** 항상 표시 (PnL, Trades, Win Rate)
- **중간 행:** 주변 시야 (Risk, Alerts)
- **하단 행:** 가끔 확인 (Performance)

**보조 모니터 (가능한 경우):** `alerting_overview` 대시보드
- **Alert Volume** (패널 1) 및 **Notifier Availability** (패널 5)에 집중

**노트북/태블릿:** Prometheus Alertmanager UI (알림 규칙 상태 확인용)

---

### 4.2 정상 운영 플로우

```
시작: topn_arbitrage_core 대시보드 열기
  │
  ├─> PnL 확인 (패널 1, 2): 상승/안정 추세 ✅
  ├─> Trades 확인 (패널 3): 일관된 거래율 ✅
  ├─> Win Rate 확인 (패널 4): 초록 구역 (≥70%) ✅
  ├─> Positions 확인 (패널 5): 범위 내 ✅
  ├─> Guards 확인 (패널 9): 가끔 발동 ✅
  ├─> Latency 확인 (패널 6): p99 < 50ms ✅
  ├─> CPU/Memory 확인 (패널 7, 8): < 50% ✅
  │
  └─> 정상 운영 계속
       │
       └─> 15-30분마다 반복
```

---

### 4.3 이상 감지 플로우

```
이상 감지 (⚠️ 또는 🚨 조건)
  │
  ├─> 단계 1: 이상 유형 식별
  │   ├─> PnL 하락 → 섹션 5.1 (PnL 조사)
  │   ├─> Guard 급증 → 섹션 5.2 (리스크 조사)
  │   ├─> 레이턴시 급증 → 섹션 5.3 (성능 조사)
  │   ├─> Alert 실패 → 섹션 5.4 (Alert 조사)
  │   └─> Notifier 다운 → 섹션 5.5 (Notifier 조사)
  │
  ├─> 단계 2: 상세 조사
  │   ├─> 관련 대시보드 패널로 전환
  │   ├─> Prometheus 메트릭 확인 (원시 PromQL)
  │   └─> 애플리케이션 로그 검토
  │
  ├─> 단계 3: 트리아지 (Alerting Playbook 참조)
  │   ├─> 심각도 판단 (P1/P2/P3)
  │   ├─> 영향 평가 (거래 중단? 감소? 저하?)
  │   └─> 조치 결정 (즉시 수정 / 임시 조치 / 에스컬레이션)
  │
  └─> 단계 4: 문서화 및 후속 조치
      ├─> 운영 로그에 인시던트 기록
      ├─> 근본 원인 분석을 위한 티켓/작업 생성
      └─> 필요 시 임계값/알림 업데이트
```

---

## 5. 임계값 및 베이스라인 가이드라인

### 5.1 PnL 및 거래 임계값

| 메트릭 | 초록 ✅ | 노랑 ⚠️ | 빨강 🚨 | 비고 |
|--------|---------|-----------|--------|-------|
| **PnL 추세** | 상승 또는 안정 | 베이스라인 대비 5-10% 하락 | 10% 이상 하락 또는 마이너스 | 베이스라인 = 7일 평균 |
| **Win Rate** | ≥ 70% | 50-69% | < 50% | 전략에 따라 다름; 초기 테스트 후 조정 |
| **Trade Rate** | 7일 평균의 ≥ 80% | 평균의 50-79% | 평균의 < 50% | 시장 활동에 영향받음 |
| **Round Trips** | 증가 중 | 느린 증가 | 정체 (변화 없음) | WebSocket + 엔진 상태 점검 |

**베이스라인 학습 기간:**
- **초기 배포:** 첫 1-2주
- **주요 변경 후:** 3-5일
- **방법:** Prometheus `avg_over_time()` 또는 Grafana 통계 패널을 사용하여 베이스라인 계산
- **업데이트 빈도:** 주간 검토, 월간 조정

---

### 5.2 성능 임계값

| 메트릭 | 초록 ✅ | 노랑 ⚠️ | 빨강 🚨 | 비고 |
|--------|---------|-----------|--------|-------|
| **Loop Latency (p95)** | < 30ms | 30-60ms | > 60ms | 목표: 평균 < 25ms, p99 < 40ms |
| **Loop Latency (p99)** | < 50ms | 50-100ms | > 100ms | 순간 스파이크는 허용, 지속되면 위험 |
| **CPU Usage** | < 50% | 50-80% | > 80% | 목표: < 10% (Phase 4 목표) |
| **Memory Usage** | < 60% | 60-80% | > 80% | 목표: < 60MB (Phase 4 목표) |
| **Throughput** | ≥ 40 iter/s | 30-39 iter/s | < 30 iter/s | universe 크기에 따라 다름 |

**성능 저하 패턴:**
- **점진적 증가:** 메모리 누수 또는 캐시 비대화 가능성 → 로그 + 프로파일링 검토
- **급격한 스파이크:** 외부 API 레이턴시 또는 네트워크 문제 가능성 → 거래소 상태 점검
- **진동(Oscillation):** GC 일시 정지 또는 리소스 경합 가능성 → 런타임 설정 튜닝

---

### 5.3 리스크 및 Guard 임계값

| 메트릭 | 초록 ✅ | 노랑 ⚠️ | 빨강 🚨 | 비고 |
|--------|---------|-----------|--------|-------|
| **Guard Triggers (시간당)** | < 10 | 10-50 | > 50 | 베이스라인은 시장 변동성에 따라 다름 |
| **Guard Trigger Rate** | 베이스라인의 < 3배 | 베이스라인의 3-5배 | 베이스라인의 > 5배 | 베이스라인 = 7일 평균 |
| **Active Positions** | 평균 ± 2σ 내 | 평균에서 2-3σ | 평균에서 > 3σ | σ = 7일간 표준편차 |
| **Alert Count (시간당)** | < 20 | 20-50 | > 50 | P1/P2/P3 알림 포함 |

**Guard 유형 분석:**
- **exchange:** 가장 흔함 (API 에러, 상태 점검)
- **route:** 시장 특정 (유동성 부족, 스프레드 붕괴)
- **symbol:** 심볼 특정 (거래량 너무 낮음, bid-ask 스프레드 너무 넓음)
- **global:** 드물음 (시스템 전체 리스크 한도 도달)
- **cross_exchange:** FX 관련 (환율 불가용, 데이터 정체)

**Guard 유형별 조치:**
- **`exchange` guards 빈번:** 거래소 상태 대시보드 점검
- **`route` guards 빈번:** ArbRoute 점수 + 시장 상황 검토
- **`symbol` guards 빈번:** universe에서 해당 심볼 제거 고려
- **`global` guards 빈번:** 리스크 한도 검토 (너무 보수적일 수 있음)
- **`cross_exchange` guards 빈번:** FX provider 상태 점검

---

### 5.4 Alert 시스템 임계값

| 메트릭 | 초록 ✅ | 노랑 ⚠️ | 빨강 🚨 | 비고 |
|--------|---------|-----------|--------|-------|
| **Alert Success Rate** | ≥ 95% | 90-94% | < 90% | 1시간 롤링 윈도우로 측정 |
| **Alert Delivery Latency (p99)** | < 3s | 3-5s | > 5s | Notifier별로 다름; Telegram 보통 < 1s |
| **Notifier Availability** | 1.0 (가용) | 0.5 (불안정) | 0.0 (불가용) | Notifier 서비스 상태 점검 |
| **DLQ Count** | 0 | N/A | > 0 | DLQ 항목이 있으면 무조건 위험 |
| **Fallback Rate** | 전체의 < 5% | 5-10% | > 10% | 높은 fallback = 주 notifier 불안정 |
| **Retry Rate** | 전체의 < 10% | 10-20% | > 20% | 높은 retry = 일시적 실패 |

**Alert 볼륨 패턴:**
- **일정한 낮은 볼륨:** 정상 운영 (시간당 5-20 알림)
- **버스트 (< 5분):** 정당한 이벤트 가능성 (시장 충격, 거래소 이슈)
- **지속적 높은 볼륨:** alert storm 또는 규칙 오설정 가능성 → RuleEngine 점검

---

## 6. 인시던트 트리아지 플로우 (상위 레벨)

### 6.1 심각도 분류

| 심각도 | 거래 영향 | 대응 시간 | 에스컬레이션 |
|----------|---------------|---------------|------------|
| **P1 (Critical)** | 거래 중단 또는 높은 손실 위험 | 즉시 (< 5분) | On-call 엔지니어 + 팀 리더 |
| **P2 (High)** | 성능 저하 또는 부분 장애 | < 30분 | On-call 엔지니어 |
| **P3 (Medium)** | 즉각적 영향 없음, 모니터링 필요 | < 2시간 | 정규 업무 시간 |

---

### 6.2 인시던트 트리아지 의사결정 트리

```
인시던트 감지
  │
  ├─> 거래가 중단되었는가? (PnL 정체, 거래 = 0)
  │   YES → P1: 위험 → 즉시 조치 (Alerting Playbook 섹션 3 참조)
  │   NO  → 계속 ↓
  │
  ├─> PnL이 급격히 하락하는가? (> 5분 내 5%)
  │   YES → P1: 위험 → Guards + 시장 상황 점검
  │   NO  → 계속 ↓
  │
  ├─> 성능이 저하되었는가? (Latency > 100ms p99)
  │   YES → P2: 높음 → CPU/Memory + 로그 점검
  │   NO  → 계속 ↓
  │
  ├─> 알림이 실패하는가? (성공률 < 90% 또는 DLQ > 0)
  │   YES → P2: 높음 → Notifier + Alert 파이프라인 점검
  │   NO  → 계속 ↓
  │
  └─> 모니터링 이상인가? (메트릭 스파이크지만 기능적 영향 없음)
      YES → P3: 중간 → 로그 검토 + 티켓 생성
      NO  → 오탐 → 임계값 업데이트
```

---

### 6.3 초기 대응 조치 (심각도별)

#### P1 (Critical)
1. **인시던트 확인** (< 1분)
   - 여러 데이터 소스 확인 (Grafana + Prometheus + 로그)
   - 오탐이 아님을 검증
2. **영향 평가** (< 2분)
   - 거래가 중단되었는가? 얼마나 많은 PnL이 위험에 처했는가?
   - 어느 컴포넌트가 실패하고 있는가? (Engine / Exchange / Alert / FX)
3. **즉시 완화** (< 5분)
   - 거래 중단 시: 거래소 상태 + RiskGuard 상태 점검
   - PnL 하락 시: 긴급 중지 고려 (위험 > 보상인 경우)
   - 알림 실패 시: fallback 채널 사용 (Local Log는 항상 작동)
4. **에스컬레이션** (< 5분)
   - On-call 엔지니어 + 팀 리더에게 알림
   - Grafana 대시보드 링크 + 초기 발견 사항 공유
5. **상세 조사** (시나리오별 단계는 Alerting Playbook 참조)

#### P2 (High)
1. **인시던트 확인** (< 5분)
2. **영향 평가** (< 10분)
3. **근본 원인 조사** (< 30분)
   - 로그 점검 (애플리케이션 + 시스템)
   - 최근 변경 사항 검토 (배포, 설정 업데이트)
4. **임시 조치 구현** (< 30분)
   - 임계값 조정, 서비스 재시작, fallback 전환 등
5. **해결 모니터링** (지속적)
6. **문서화** (< 1시간)

#### P3 (Medium)
1. **인시던트 기록** (< 15분)
2. **가능할 때 조사** (< 2시간)
3. **후속 조치를 위한 티켓 생성**
4. **오탐인 경우 모니터링 업데이트**

---

### 6.4 에스컬레이션 채널

| 채널 | 목적 | 대상 | SLA |
|---------|---------|----------|-----|
| **Telegram (P1/P2 알림)** | 즉시 알림 | On-call 엔지니어 | < 1분 |
| **Slack (P2/P3 알림)** | 팀 전체 인지 | 개발팀 + SRE | < 5분 |
| **Email (P3 알림)** | 일일 요약 | 경영진 + 컴플라이언스 | < 1시간 |
| **Local Log (모든 알림)** | 감사 추적 | 컴플라이언스 + 사후 분석 | 항상 켜짐 |

**에스컬레이션 정책 (템플릿):**
- **P1:** 알림 → Telegram (on-call) → 전화 (5분 내 ACK 없으면) → 팀 리더
- **P2:** 알림 → Telegram + Slack → 조사 (30분) → 미해결 시 에스컬레이션
- **P3:** 알림 → Email → 업무 시간 중 검토

**참고:** 실제 팀 구조 및 on-call 순환에 따라 에스컬레이션 정책을 조정하십시오.

---

## 7. 런북 유지보수

### 7.1 런북 업데이트 시점

- **새 메트릭 추가 시:** 섹션 2 (대시보드 및 메트릭 맵)에 추가
- **대시보드 변경 시:** 패널 설명 + 스크린샷 업데이트
- **임계값 튜닝 시:** 섹션 5 (임계값 및 베이스라인 가이드라인) 업데이트
- **새 알림 규칙 추가 시:** 섹션 3 (체크리스트) + 섹션 6 (트리아지)에 추가
- **인시던트 사후 분석 시:** 섹션 6 (트리아지 플로우)에 교훈 반영
- **팀 구조 변경 시:** 섹션 6.4 (에스컬레이션 채널) 업데이트

---

### 7.2 런북 검토 일정

- **주간:** 인시던트 로그 검토 + 필요 시 임계값 업데이트
- **월간:** 전체 런북 검토 + 베이스라인 업데이트
- **분기별:** 주요 검토 + 사후 분석 결과 반영
- **주요 릴리스 후:** 모든 섹션 검토 + 절차 테스트

---

### 7.3 동기화가 필요한 관련 문서

- **Alerting Playbook:** 상세 시나리오 대응 절차
- **D77-1 Prometheus Exporter Design:** 메트릭 정의 + 라벨
- **D77-2 Grafana Dashboard Design:** 패널 구성 + 쿼리
- **D80-7 Alerting System Design:** 알림 규칙 + 라우팅 로직
- **RUNBOOK.md:** 일반 시스템 운영 (더 넓은 범위)
- **TROUBLESHOOTING.md:** 디버깅 가이드 (더 깊은 기술적 세부사항)

---

## 8. 빠른 참조

### 8.1 주요 URL

| 서비스 | URL | 목적 |
|---------|-----|---------|
| **Prometheus** | `http://localhost:9100/metrics` | 원시 메트릭 엔드포인트 |
| **Grafana** | `http://localhost:3000` | 대시보드 UI |
| **Core Dashboard** | `/d/topn-arbitrage-core` | 거래 + 성능 |
| **Alert Dashboard** | `/d/alerting-overview` | Alert 파이프라인 상태 |
| **Prometheus UI** | `http://localhost:9090` | PromQL 쿼리 + 알림 |
| **Alertmanager** | `http://localhost:9093` | 알림 규칙 관리 |

---

### 8.2 긴급 연락처 (템플릿)

| 역할 | 이름 | Telegram | 전화번호 | 백업 |
|------|------|----------|-------|--------|
| **On-call Engineer** | 미정 | @username | +82-XX-XXXX-XXXX | 미정 |
| **Team Lead** | 미정 | @username | +82-XX-XXXX-XXXX | 미정 |
| **SRE Lead** | 미정 | @username | +82-XX-XXXX-XXXX | 미정 |

**참고:** 프로덕션 배포 전에 실제 팀 구성원 정보로 업데이트하십시오.

---

### 8.3 자주 사용하는 PromQL 쿼리

```promql
# PnL Rate (분당)
rate(arb_topn_pnl_total{env="live", universe="top50"}[1m])

# Win Rate (현재)
arb_topn_win_rate{env="live", universe="top50", strategy="topn_arb"}

# Loop Latency (p99, 최근 5분)
histogram_quantile(0.99, rate(arb_topn_loop_latency_seconds_bucket{env="live"}[5m]))

# Alert Success Rate (최근 1시간)
sum(rate(alert_sent_total[1h])) / (sum(rate(alert_sent_total[1h])) + sum(rate(alert_failed_total[1h]))) * 100

# DLQ Count (최근 24시간)
increase(alert_dlq_total[24h])

# Guard Trigger Rate (시간당)
rate(arb_topn_guard_triggers_total{guard_type="cross_exchange"}[1h]) * 3600

# CPU Usage (현재, 전략별)
arb_topn_cpu_usage_percent{env="live", strategy="topn_arb"}
```

**쿼리 설명:**
- 이 쿼리들은 Prometheus UI 또는 Grafana의 Explore 탭에서 직접 실행할 수 있습니다
- `env`, `universe`, `strategy` 등의 라벨은 실제 환경에 맞게 수정하십시오

---

### 8.4 로그 파일 위치

| 컴포넌트 | 로그 경로 | 로그 레벨 | 로테이션 |
|-----------|----------|-----------|----------|
| **Trading Engine** | `logs/topn_arbitrage.log` | INFO | 일일 |
| **Alert System** | `logs/alerting.log` | INFO | 일일 |
| **Prometheus Exporter** | `logs/prometheus_exporter.log` | INFO | 일일 |
| **Local Log Notifier** | `logs/alert_local.log` | ALL | 일일 |

---

## 9. 부록

### 9.1 용어 설명

- **PnL (Profit and Loss):** 청산된 거래의 실현 손익
- **Win Rate:** 전체 청산 거래 중 수익 난 거래의 비율
- **Round Trip:** 단일 포지션의 완전한 entry → exit 사이클
- **Guard Trigger:** RiskGuard 발동 이벤트 (거래를 차단하거나 제한함)
- **DLQ (Dead Letter Queue):** 재시도할 수 없는 실패한 알림
- **Fallback:** 주 notifier 실패 시 사용하는 보조 notifier
- **Notifier:** 알림 전송 채널 (Telegram, Slack, Email 등)
- **Baseline:** 이상 감지에 사용되는 과거 평균
- **p95/p99:** 95번째/99번째 백분위수 (성능 메트릭)

---

### 9.2 변경 이력

| 날짜 | 버전 | 변경 사항 | 작성자 |
|------|---------|---------|--------|
| 2025-12-02 | 1.0 | 초기 런북 작성 (D77-3) | Windsurf AI |
| 2025-12-03 | 1.1 | 한국어 번역 | Windsurf AI |

---

**모니터링 런북 끝**
