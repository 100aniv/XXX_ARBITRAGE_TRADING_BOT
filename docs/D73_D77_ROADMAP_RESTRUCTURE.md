# D73-D77 로드맵 재구조화

이 문서는 기존 D_ROADMAP.md의 D73-D89 섹션을 재구조화한 내용입니다.

**재구조화 목적:**
1. Multi-Symbol Engine을 최우선순위로 배치 (D73)
2. Performance & Scalability를 상용급 봇 대비 명확히 정의 (D74)
3. Profitability 중심 Strategy & Tuning을 독립 페이즈로 분리 (D75)
4. Alerting (Telegram)을 독립 페이즈로 명확화 (D76)
5. Real-time Monitoring Dashboard를 최종 기능 페이즈로 배치 (D77)
6. D99 Done Criteria를 D77과 명시적으로 연결

---

## 기존 구조 (변경 전)

```
D73-D74: 모니터링/운영/UI
D75-D79: PERFORMANCE OPTIMIZATION
D80-D89: MULTI-SYMBOL
D90-D94: HYPERPARAMETER TUNING
D95-D96: ADVANCED BACKTEST
D97-D98: OPERATION & DEPLOYMENT
D99: FINAL QA & RELEASE
```

## 신규 구조 (변경 후)

```
D73: Multi-Symbol Engine Foundation
D74: Multi-Symbol Performance & Scalability  
D75: Strategy & Tuning v2 (Profitability)
D76: Alerting Infrastructure (Telegram)
D77: Real-time Monitoring Dashboard (Prometheus/Grafana)
D78~: 기존 D90+ 내용 (HYPERPARAMETER TUNING, BACKTEST, etc.)
D99: FINAL QA & RELEASE (D77 Dashboard 요구사항 명시)
```

---

## D_ROADMAP.md 수정 지침

**삭제할 섹션:**
- Line 716-774: " 블럭 D – 모니터링/운영/UI" ~ "Keyspace 검사에서 symbol 분리/TTL 100% 검증"

**추가할 섹션:**
아래 D73-D77 내용으로 교체

---

# D73-D77 상세 내용 (한글)

⸻

## 🚀 D73 – 멀티심볼 엔진 기반 구축
**상태:** ⏳ TODO

**목표:**  
단일 심볼(BTC/USDT) 구조를 멀티심볼 체계로 확장. Top-N 심볼 동시 처리 기반 마련.

### D73-1: Symbol Universe Provider

**작업:**
- SymbolUniverse 모듈 생성 (4가지 모드)
  - SINGLE: 단일 심볼 (현재 상태)
  - FIXED_LIST: 고정 심볼 리스트 (예: ["BTC/USDT", "ETH/USDT"])
  - TOP_N: 거래량 기준 상위 N개 (예: Top-20)
  - FULL_MARKET: 전체 시장 (거래소 전체 심볼)
- 거래소별 심볼 리스트 조회 API 통합 (Binance, Upbit)
- 심볼 필터링 로직 (거래량, 스프레드, 유동성 기준)

**완료 조건:**
- 4가지 모드 모두 동작 (config 기반 전환)
- Top-20 심볼 리스트 실시간 조회 가능
- 심볼 변경 시 엔진 재시작 없이 적용

### D73-2: Per-Symbol Engine Loop

**작업:**
- 심볼별 독립 코루틴 구조 구현
- Shared scheduler + per-symbol task 관리
- PortfolioManager 초안 (symbol bucket, exposure allocation)
- Multi-symbol StateStore 통합 (KeyBuilder 활용)

**구현 예시:**
```python
async def run_multi_symbol_engine():
    symbols = universe.get_symbols()  # Top-20
    tasks = [
        asyncio.create_task(
            run_symbol_engine(symbol, shared_portfolio, shared_guard)
        )
        for symbol in symbols
    ]
    await asyncio.gather(*tasks)
```

**완료 조건:**
- 5개 심볼 동시 운용 PAPER 테스트 PASS
- 심볼별 독립적인 포지션/PnL 추적
- StateStore에 심볼별 키 저장/복원 검증

### D73-3: Multi-Symbol RiskGuard

**작업:**
- RiskGuard 계층 구조 확장
  - GlobalGuard: 전체 포트폴리오 한도
  - PortfolioGuard: 노출 한도
  - SymbolGuard[]: 심볼별 한도
- 심볼별 Guard 상태 Redis 저장/로드
- Portfolio 리스크 집계 로직

**Guard 계층 구조:**
```
GlobalGuard
├── PortfolioGuard (max_total_exposure)
├── SymbolGuard[BTC/USDT] (max_symbol_position, cooldown)
├── SymbolGuard[ETH/USDT]
└── ...
```

**완료 조건:**
- 심볼별 Guard 트리거 정상 동작
- Portfolio 총 노출 한도 체크
- Redis keyspace 검증 (심볼별 키 분리)

### D73-4: Small-Scale Integration Test

**작업:**
- Top-10 심볼 PAPER 모드 통합 테스트
- 5분 캠페인 실행 (Entry/Exit/PnL 검증)
- Multi-symbol snapshot 저장/복원 테스트

**완료 조건:**
- Top-10 심볼 5분 캠페인 장애 없이 완료
- 심볼별 PnL 정확히 계산
- Snapshot resume 후 모든 심볼 상태 복원

**D73 전체 완료 조건:**
- ✅ 4가지 Universe 모드 모두 동작
- ✅ Top-10 심볼 PAPER 테스트 PASS
- ✅ Multi-symbol RiskGuard 정상 동작
- ✅ Snapshot 저장/복원 100%
- ✅ 문서화: D73_MULTISYMBOL_FOUNDATION.md

⸻

## 🚀 D74 – 멀티심볼 성능 및 확장성
**상태:** ⏳ TODO

**목표:**  
상용급 봇 대비 성능 경쟁력 확보. Top-20/50/100 단계별 스케일 검증.

### D74-1: 성능 목표 및 벤치마크 정의

**작업:**
- 상용급 봇 성능 기준 조사 (latency, throughput, 동시 심볼 수)
- 성능 목표 설정 및 측정 지표 정의
- Micro-benchmark 도구 개발 (loop latency, Redis latency, WS latency)

**성능 목표 (vs 상용급 봇):**

| 지표 | 상용급 봇 | 목표 | 현재 |
|------|----------|------|------|
| Loop latency (avg) | <5ms | <10ms | ~15ms |
| Loop latency (p99) | <15ms | <25ms | ~50ms |
| 동시 심볼 수 | 50-100 | 20-50 | 1 |
| WS reconnect MTTR | <3s | <5s | ~20s |
| CPU usage (20 symbols) | <60% | <70% | N/A |
| Memory drift | <2% | <5% | TBD |

**완료 조건:**
- 상용급 봇 벤치마크 리포트 작성
- 성능 목표 합의 및 문서화
- Micro-benchmark 도구 구현 완료

### D74-2: Profiling 및 병목 분석

**작업:**
- cProfile/py-spy 기반 profiling
- Event loop 병목 분석
- Redis/PostgreSQL 쿼리 최적화 기회 파악
- WS 구독 오버헤드 측정

**분석 항목:**
- Event loop 단일화 필요성
- Redis pipeline/MGET 배치 처리
- PostgreSQL asyncpg 마이그레이션
- In-memory snapshot 캐싱

**완료 조건:**
- Profiling 리포트 작성 (상위 10개 병목)
- 최적화 우선순위 결정
- Before/After 비교 플랜

### D74-3: Performance Optimization Pass 1

**작업:**
- 이벤트 루프 단일화 (single async engine loop)
- Redis 커넥션 풀 + Pipeline 배치 처리
- MetricsCollector 배치 플러시 (zero-alloc 구조)
- WS 멀티심볼 구독 최적화 (single WS multiplexing)

**완료 조건:**
- Loop latency avg < 10ms, p99 < 25ms
- Redis latency < 1ms (pipeline 사용 시)
- GC pressure 30% 감소

### D74-4: Load Testing (Top-20/50/100)

**작업:**
- Top-20 심볼 load test (5분/30분/1시간)
- Top-50 심볼 soak test (1시간)
- Top-100 심볼 endurance test (현실성 검토)
- 성능 메트릭 자동 수집 및 리포트

**완료 조건:**
- Top-20: CPU < 70%, latency < 10ms (5분 이상)
- Top-50: CPU < 80%, latency < 15ms (1시간 안정)
- 성능 리포트 작성 (D74_PERFORMANCE_REPORT.md)

**D74 전체 완료 조건:**
- ✅ 성능 벤치마크 리포트 완성
- ✅ Loop latency < 10ms (avg), < 25ms (p99)
- ✅ Top-20 심볼 1시간 안정 운용
- ✅ CPU < 70%, Memory drift < 5%
- ✅ 문서화: D74_PERFORMANCE_SCALABILITY.md

⸻

## 🚀 D75 – 전략 및 튜닝 v2 (수익성 중심)
**상태:** ⏳ TODO

**목표:**  
수익성 중심의 전략 파라미터 튜닝. Backtest + Tuning 파이프라인 구축.

### D75-1: 수익성 KPI 정의

**작업:**
- 수익성 지표 정의 및 계산 로직 구현
  - PnL (Profit and Loss)
  - MDD (Maximum Drawdown)
  - Sharpe Ratio
  - Win Rate (승률)
  - Average Trade Duration
  - Risk-adjusted Return
- KPI 추적 모듈 (arbitrage/profitability_tracker.py)

**완료 조건:**
- 6개 KPI 실시간 계산
- Redis/PostgreSQL 저장
- CLI 모니터링 도구에서 조회 가능

### D75-2: Multi-Symbol Tuning Pipeline

**작업:**
- Tuning orchestrator 설계 (3단계)
  1. Random search (broad exploration)
  2. Bayesian optimization (smart search)
  3. Local grid search (fine-tuning)
- tuning_results DB 스키마 (결과/메타/seed)
- Tuning worker 구조 (distributed queue)

**Tuning Parameters:**
- min_profit_threshold (0.001~0.005)
- max_position_size (100~2000 USDT)
- cooldown_seconds (30~300s)
- symbol_weight (volume/volatility based)

**완료 조건:**
- 100+ 파라미터 시나리오 자동 실행
- Tuning 결과 DB 저장 및 재현 가능
- Best params 추천 알고리즘 구현

### D75-3: Backtest + Tuning Integration

**작업:**
- Backtest 엔진과 Tuning 파이프라인 통합
- Walk-forward optimization (train/validate rolling)
- Tuning 결과 시각화 (heatmap, param sensitivity)

**완료 조건:**
- Walk-forward 튜닝 1회 완료 (7일 train + 3일 validate)
- Sharpe ratio 10% 이상 개선 증빙
- Tuning 리포트 작성 (D75_TUNING_REPORT.md)

### D75-4: Strategy v2 Design Update

**작업:**
- 수익성 개선을 위한 전략 설계 업데이트
- Adaptive slippage 모델링 (실측 데이터 기반)
- Dynamic symbol selection (AI 기반 우선순위)

**완료 조건:**
- 전략 v2 설계 문서 작성
- Adaptive slippage 프로토타입
- SYSTEM_DESIGN.md 업데이트

**D75 전체 완료 조건:**
- ✅ 6개 수익성 KPI 정의 및 구현
- ✅ 100+ 파라미터 시나리오 튜닝 완료
- ✅ Walk-forward 튜닝 Sharpe 10% 개선
- ✅ 전략 v2 설계 문서화
- ✅ 문서화: D75_STRATEGY_TUNING_V2.md

⸻

## 🚀 D76 – 알림 인프라 (Telegram 통합)
**상태:** ⏳ TODO

**목표:**  
실시간 알림 시스템 구축. Telegram 봇 통합으로 24/7 모니터링 지원.

### D76-1: Alert Taxonomy & Severity Mapping

**작업:**
- Alert 분류 체계 정의 (4단계)
  - P0: Critical (서비스 다운)
  - P1: High (성능 저하, 높은 에러율)
  - P2: Medium (컴포넌트 장애)
  - P3: Low (경고)
- Alert 조건 정의 (20+ rules)
- Alert rule 엔진 설계

**Alert Rules 예시:**
- P0: Engine crashed, DB connection lost
- P1: Loop latency > 50ms (5분 이상), Error rate > 10/min
- P2: WS disconnected, Redis timeout
- P3: Low trading activity, Config validation warning

**완료 조건:**
- Alert taxonomy 문서화
- 20개 alert rule 정의
- Severity mapping 검증

### D76-2: Telegram Notifier Implementation

**작업:**
- Telegram Bot API 통합 (python-telegram-bot)
- Alert 메시지 포맷 설계 (severity별 emoji, 상세 정보)
- Rate limiting (alert storm 방지)
- Config 기반 Telegram 설정 (bot token, chat ID)

**메시지 포맷 예시:**
```
🔴 [P0] Engine Crashed
Time: 2025-11-21 14:30:22
Session: prod-20251121-143022
Reason: Redis connection timeout
Action: Auto-recovery initiated
```

**완료 조건:**
- Telegram 봇 생성 및 연동
- Alert 메시지 발송 정상 동작
- Rate limiting 검증 (max 10 msg/min)

### D76-3: Alert Rule Engine Integration

**작업:**
- LoggingManager에 Alert hook 추가
- MetricsCollector에서 threshold 기반 alert 발생
- RiskGuard trigger 시 alert 발송
- Alert history PostgreSQL 저장

**Integration Points:**
- LoggingManager: ERROR/CRITICAL 로그 → P1/P0 alert
- MetricsCollector: latency/error rate threshold → P1 alert
- RiskGuard: Guard trigger → P2 alert
- StateStore: Snapshot save failed → P2 alert

**완료 조건:**
- 3개 integration point 구현
- Alert history 테이블 생성
- End-to-end alert flow 검증

### D76-4: Incident Simulation & RUNBOOK Update

**작업:**
- PAPER 모드에서 incident simulation (10+ scenarios)
- Alert 발송 테스트 및 검증
- RUNBOOK.md 및 TROUBLESHOOTING.md 업데이트 (alert 대응 절차)

**Simulation Scenarios:**
- Redis connection loss
- High loop latency spike
- RiskGuard daily loss limit hit
- WS reconnect storm

**완료 조건:**
- 10개 시나리오 시뮬레이션 PASS
- Alert 발송 100% 정확도
- RUNBOOK/TROUBLESHOOTING 업데이트 완료

**D76 전체 완료 조건:**
- ✅ Alert taxonomy 및 20+ rules 정의
- ✅ Telegram 봇 통합 완료
- ✅ Alert rule engine 구현
- ✅ 10개 incident simulation PASS
- ✅ 문서화: D76_ALERTING_INFRASTRUCTURE.md

⸻

## 🚀 D77 – 실시간 모니터링 대시보드 (Prometheus/Grafana)
**상태:** ⏳ TODO

**목표:**  
실시간 모니터링 대시보드 구축. **D99 Done Criteria 충족 (Core KPI 10종 이상)**.

### D77-1: Prometheus Exporter Implementation

**작업:**
- Prometheus exporter endpoint 구현 (/metrics)
- Core metrics 노출 (10+ metrics)
  - Trading: trades_total, pnl_total, win_rate
  - Performance: loop_latency_seconds, ws_latency_seconds
  - System: cpu_usage_percent, memory_usage_bytes
  - Risk: guard_triggers_total, open_positions_count
  - State: snapshot_save_total, snapshot_restore_total
- prometheus_client 라이브러리 통합
- Metrics scrape 주기 설정 (15s)

**완료 조건:**
- /metrics endpoint 정상 동작
- 10개 이상 metric 노출
- Prometheus scraping 검증

### D77-2: Grafana Dashboard Creation

**작업:**
- Grafana 대시보드 템플릿 생성 (3개 대시보드)
  1. **System Health Dashboard**
     - Service status, Uptime, Error rate
     - CPU/Memory usage
     - Redis/PostgreSQL status
  2. **Trading KPIs Dashboard**
     - PnL timeline, Win rate
     - Trades per hour
     - Symbol heatmap (multi-symbol)
  3. **Risk & Guard Dashboard**
     - Open positions, Exposure
     - Guard triggers
     - Drawdown timeline
- Panel 설계 및 PromQL 쿼리 작성

**완료 조건:**
- 3개 대시보드 생성 완료
- 모든 panel 데이터 정상 표시
- Dashboard JSON export

### D77-3: Alertmanager Integration

**작업:**
- Prometheus Alertmanager 설정
- Alert rules 작성 (YAML)
- Grafana alert → Telegram 연동 (D76 통합)
- Alert routing 및 grouping 설정

**Alert Rules 예시:**
```yaml
groups:
  - name: arbitrage_alerts
    rules:
      - alert: HighLoopLatency
        expr: loop_latency_seconds > 0.050
        for: 5m
        labels:
          severity: P1
        annotations:
          summary: "Loop latency too high"
      
      - alert: HighErrorRate
        expr: rate(errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: P1
        annotations:
          summary: "Error rate exceeded threshold"
```

**완료 조건:**
- Alertmanager 설정 완료
- 5개 alert rule 정상 동작
- Grafana → Telegram 알림 검증

### D77-4: D99 Done Criteria 검증 ⭐

**작업:**
- **D99 Done Criteria 명시적 연결**
  - "모니터링 대시보드에서 Core KPI 10종 이상 노출 + Alert"
- Core KPI 10종 확인 및 문서화
- Dashboard 최종 검증 및 운영팀 인수

**Core KPI 10종:**
1. Total PnL (실시간)
2. Win Rate (%)
3. Trades per Hour
4. Loop Latency (avg, p99)
5. WS Latency (avg)
6. CPU Usage (%)
7. Memory Usage (MB)
8. Open Positions Count
9. Guard Triggers per Hour
10. Snapshot Save Success Rate (%)

**완료 조건:**
- Core KPI 10종 대시보드에서 실시간 노출
- Alert 5종 이상 정상 동작
- 운영팀 인수 완료 (handoff 문서)
- D77_MONITORING_DASHBOARD.md 작성

**D77 전체 완료 조건:**
- ✅ Prometheus exporter 구현 (10+ metrics)
- ✅ Grafana 3개 대시보드 생성
- ✅ Alertmanager 통합 (Telegram 연동)
- ✅ **Core KPI 10종 노출 (D99 Done Criteria 충족)**
- ✅ 운영팀 인수 완료
- ✅ 문서화: D77_MONITORING_DASHBOARD.md

---

## D99 Done Criteria 업데이트

**기존 (D97-D98에 포함):**
```
- 모니터링 대시보드에서 Core KPI 10종 이상 노출 + Alert
```

**신규 (D77 명시적 연결):**
```
- D77 완료: 실시간 모니터링 대시보드 (Prometheus/Grafana)
  - Core KPI 10종 대시보드 노출
  - Alert 5종 이상 Telegram 연동
  - 운영팀 인수 완료
```

---

## SYSTEM_DESIGN.md 업데이트 필요 사항

### 1. Multi-Symbol Architecture 섹션

**기존 (Line 277-360):**
```markdown
### Target State (D80-D89 PHASE18+)
```

**변경:**
```markdown
### Target State (D73-D74)
멀티심볼 엔진은 D73-D74에서 구현됩니다.
- D73: Multi-Symbol Engine Foundation
- D74: Performance & Scalability
```

### 2. Performance Optimization 섹션

**기존 (Line 432-496):**
```markdown
### 상용급 성능 최적화 10대 항목 (D75-D79)
```

**변경:**
```markdown
### 상용급 성능 최적화 10대 항목 (D74)
D74에서 상용급 봇 대비 성능 경쟁력을 확보합니다.
```

### 3. 새로운 섹션 추가

**위치:** Performance Optimization 섹션 이후

**내용:**
```markdown
## Alerting & Monitoring

### Alerting Infrastructure (D76)
- Telegram Bot 통합
- P0-P3 Severity mapping
- 20+ Alert rules
- Incident simulation

### Real-time Dashboard (D77)
- Prometheus exporter
- Grafana 3개 대시보드
- Alertmanager 통합
- Core KPI 10종 (D99 Done Criteria)
```

---

## 적용 방법

### 1. D_ROADMAP.md 수정

1. Line 716-774 삭제 (기존 D73-D89 내용)
2. 위의 "D73-D77 상세 내용" 삽입
3. D78 이후는 기존 D90+ 내용을 번호만 변경

### 2. SYSTEM_DESIGN.md 수정

1. Multi-Symbol Architecture 섹션: "D80-D89" → "D73-D74"로 변경
2. Performance Optimization 섹션: "D75-D79" → "D74"로 변경
3. Alerting & Monitoring 섹션 추가

### 3. D99 Done Criteria 수정

D_ROADMAP.md의 D99 섹션에서:
```markdown
**Done Criteria:**
- 24h 연속 실행 중 장애 0, latency/p99 정상 범위, leak 없음
- 모든 회귀 테스트 스위트 GREEN (D65~D99, hyperparam/backtest 포함)
- D77 Dashboard 완료: Core KPI 10종 노출 + Alert 5종 연동  ← 추가
- Docs/Runbook/Monitoring 최신 상태, 운영팀 인수 완료
- 릴리즈 패키지 배포 체크리스트 완료, 사용자 인수 OK
```

### 4. Git Commit

```bash
git add D_ROADMAP.md docs/SYSTEM_DESIGN.md docs/D73_D77_ROADMAP_RESTRUCTURE.md
git commit -m "[ROADMAP] D73-D77 재구조화 - Multi-Symbol → Performance → Tuning → Alerting → Dashboard

- D73: Multi-Symbol Engine Foundation (기존 D80-D89 앞당김)
- D74: Multi-Symbol Performance & Scalability (상용급 봇 대비 명확화)
- D75: Strategy & Tuning v2 (수익성 중심 독립 페이즈)
- D76: Alerting Infrastructure (Telegram 통합 독립 페이즈)
- D77: Real-time Monitoring Dashboard (최종 기능 페이즈, D99 Done Criteria 연결)

변경 사유:
- Multi-Symbol을 최우선순위로 배치 (실제 가치 제공)
- Performance를 상용급 봇 대비 명확히 정의
- Alerting/Dashboard를 독립 페이즈로 분리 (복잡도 관리)
- D99 Done Criteria와 D77 명시적 연결

영향:
- D_ROADMAP.md: D73-D77 재구조화, D78+ 번호 변경
- SYSTEM_DESIGN.md: Multi-Symbol/Performance 참조 업데이트
- 기존 D78-D89는 D90+ 이후로 이동
"
```

---

## 요약

### 변경 전후 비교

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| Multi-Symbol | D80-D89 (후순위) | D73 (최우선) |
| Performance | D75-D79 (일반) | D74 (상용급 봇 대비 명확) |
| Tuning | D90-D94 (분산) | D75 (수익성 중심 독립) |
| Alerting | (없음/분산) | D76 (Telegram 독립 페이즈) |
| Dashboard | D73-D74 (애매) | D77 (최종 페이즈, D99 연결) |

### 핵심 개선 사항

1. **Multi-Symbol 우선순위 상승**: 실제 가치 제공을 위해 최우선 배치
2. **Performance 명확화**: 상용급 봇 대비 경쟁력 측정 가능
3. **Profitability 독립**: 수익성 중심 튜닝을 별도 페이즈로 명확화
4. **Alerting 독립**: Telegram 통합을 명시적 페이즈로 분리
5. **Dashboard 최종 배치**: 모든 기능 완성 후 통합 모니터링 구축
6. **D99 연결 명확화**: Dashboard의 Core KPI 10종을 D99 Done Criteria와 직접 연결

---

**문서 생성 일시:** 2025-11-21  
**작성자:** Cascade AI  
**버전:** 1.0
