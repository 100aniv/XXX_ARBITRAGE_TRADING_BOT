# D77-4 Validation Phase - 완전 자동화 실행 계획서 (Part 1/2)

**작성일:** 2025-12-03 | **버전:** v2.0 (자동화)  
**범위:** 오케스트레이터 기반 완전 자동화 실행 + 모니터링 + 분석

---

## 🔍 1단계: 설계 문서 정합성 검증 완료

### 확인 결과
- ✅ KPI 32종 정의 (Trading 11개, Risk 6개, Performance 7개, Alerting 8개)
- ✅ Acceptance Criteria (Critical 6개, High Priority 6개, Medium Priority 4개)
- ✅ CLI 옵션 (--run-duration-seconds, --topn-size, --kpi-output-path) 모두 구현됨
- ✅ Unit Tests 11/11 PASS (45.14s)

---

## ⚡ 2단계: 60초 스모크 테스트 (자동화)

### 2.1 환경 정리 (d77_4_env_checker 수행)

**자동 수행 항목:**
1. 기존 PAPER Runner 프로세스 탐지 및 종료
2. Docker Redis/PostgreSQL 컨테이너 상태 확인 및 자동 기동
3. Redis FLUSHDB, PostgreSQL alert 테이블 정리
4. logs/d77-4/<run_id>/ 디렉토리 자동 생성

### 2.2 PAPER Runner 실행 (오케스트레이터가 서브프로세스로 실행)

**오케스트레이터가 자동 실행:**
- 독립 프로세스로 Runner 기동
- 실시간 로그 스트리밍 및 패턴 감시
- KPI 출력 경로: logs/d77-4/<run_id>/smoke_60s_kpi.json

### 2.3 실행 중 모니터링 (d77_4_monitor 수행)

**자동 감시 항목:**
- 로그 스트림에서 ERROR/CRITICAL/Traceback/DLQ 패턴 탐지
- Prometheus /metrics 주기적 폴링 (10초 간격)
  - loop_latency_seconds (p99)
  - process_cpu_usage_percent
  - process_memory_usage_mb
  - alert_dlq_total
  - notifier_available
- 자동 중단 조건 발동 시 Runner 프로세스 종료 및 원인 기록

### 2.4 자동 판단 (d77_4_analyzer 수행)

**판단 로직:**
- KPI JSON 파일 존재 및 필드 유효성 검증
- Round Trips ≥ 1, Crash Count = 0, DLQ = 0 확인
- PASS 시 → 1시간 본 실행 자동 진행
- FAIL 시 → monitor_summary.json에 실패 원인 기록, 오케스트레이터 중단

---

## 🚀 3단계: 1시간 본 실행 (자동화)

### 3.1 환경 재확인 (d77_4_env_checker 재수행)

**자동 수행:**
- 스모크 테스트와 동일한 환경 정리 재실행
- 디스크 여유 공간 체크 (>10GB)
- Grafana 접근성 확인 (선택적)

### 3.2 PAPER Runner 실행 (오케스트레이터)

**자동 실행:**
- TopN Size: 50, Duration: 3600s, Data Source: real
- 시작 시간 자동 기록 → logs/d77-4/<run_id>/metadata.json
- 병렬 모니터링 프로세스 자동 기동

### 3.3 실시간 모니터링 체크리스트

#### 3.3.1 Core Dashboard 모니터링 (매 5분, 총 12회)

**URL:** `http://localhost:3000/d/d77-topn-core/topn-arbitrage-core`

| 패널 | 초록 ✅ | 노랑 ⚠️ | 빨강 🚨 |
|------|---------|---------|---------|
| **Total PnL** | 증가/안정 | 5~10% 하락 | 10%+ 하락 → **중단** |
| **Win Rate** | ≥ 70% | 50~69% | < 50% → **중단** |
| **Loop Latency p99** | < 50ms | 50~100ms | > 100ms → **중단** |
| **CPU Usage** | < 50% | 50~80% | > 80% → **중단** |
| **Guard Triggers/h** | < 10 | 10~50 | > 50 → 점검 |

#### 3.3.2 Alerting Dashboard 모니터링 (매 10분, 총 6회)

**URL:** `http://localhost:3000/d/d77-alerting/alerting-overview`

| 패널 | 초록 ✅ | 빨강 🚨 |
|------|---------|---------|
| **Alert Success Rate** | ≥ 95% | < 90% → **중단** |
| **DLQ Count** | 0 | > 0 → **중단** |
| **Notifier Availability** | 1.0 | 0.0 → **중단** |

### 3.4 즉시 중단 조건 (자동화)

**중단 우선순위 1 (Critical 위반):**
```
1. Python Crash (Traceback)
2. DLQ > 0
3. Notifier Down (Availability = 0.0)
4. Loop Latency p99 > 100ms (5분 이상)
5. CPU > 80% (10분 이상)
6. Memory 시간당 증가율 > 10%

→ 즉시 Ctrl+C → 로그 저장 → 디버깅
```

**중단 우선순위 2 (High Priority, 관찰 지속):**
```
1. Win Rate < 50% (30분 이상)
2. Round Trips 정체 (30분 동안 0 변화)
3. Guard Triggers > 50/h (1시간 평균)
4. Alert Success Rate < 90% (30분 이상)

→ 경고 로그, 실행 계속, 사후 분석 시 CONDITIONAL GO 근거
```

### 3.5 실행 후 자동 수집 (d77_4_analyzer)

**자동 수집 항목:**
1. KPI JSON 파일 검증 및 로드
2. 콘솔 로그 분석 (ERROR/WARNING 카운트)
3. Prometheus 최종 메트릭 스냅샷 저장
4. 모니터링 요약 (monitor_summary.json) 통합

**출력:**
- analysis_result.json (KPI 32종 + Criteria 검증 결과)

---

## 🛠️ 디버깅 플로우

### Case 1: Crash (Exception)
```
1. logs/d77-4/*_error.log 확인
2. Traceback에서 원인 파악 (Redis? API? Config?)
3. 수정 → 2.1부터 재실행
```

### Case 2: Round Trips = 0
```
1. KPI JSON에서 entry_trades, exit_trades 확인
2. 둘 다 0 → TopN Provider/시장 데이터 문제
3. Entry > 0, Exit = 0 → Exit Strategy 문제
4. 수정 → 재실행
```

### Case 3: DLQ > 0
```
1. PostgreSQL alert_deliveries 테이블 확인:
   docker exec arbitrage-postgres psql -U arbitrage -d arbitrage -c "SELECT * FROM alert_deliveries WHERE status='DLQ';"
2. 실패 원인 (Telegram token? Notifier down?)
3. 수정 → 재실행
```

### Case 4: Loop Latency > 100ms
```
1. 로그에서 "Iteration [N]" 간격 확인
2. Prometheus loop_latency_seconds_histogram 확인
3. 원인: API 레이턴시? DB 쿼리? CPU 병목?
4. 수정 → 재실행
```

### Case 5: Memory Leak
```
1. KPI JSON memory_usage_mb 추이
2. 시간당 증가율: (메모리_60분 - 메모리_0분) / 메모리_0분 * 100
3. > 10% → Python memory_profiler 사용
4. 수정 → 재실행
```

---

**다음 문서:** D77_4_VALIDATION_DECISION_TREE.md (사후 분석 + GO/NO-GO 판단)
