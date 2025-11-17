# D52 WebSocket Long-run Test Plan

**작성일:** 2025-11-17  
**상태:** ✅ 정의 완료

---

## 📋 Executive Summary

D52는 **WebSocket 기반 시스템의 실제 시장 환경에서의 안정성**을 검증합니다.

**목표:**
- WS 재연결 / 메시지 누락 / snapshot delay 자동 감지
- 1h / 6h / 24h 롱런 수행 가능성 검증
- "WS 기반이 실제 시장에서 24시간 버틸 수 있는가" 확인

---

## 🎯 WebSocket 특화 실패 기준

### 1. Snapshot Latency (스냅샷 지연)

**메트릭:** `ws_latency_ms` = 마지막 snapshot timestamp → 현재 시간 차이

**기준:**
- ✅ 정상: < 100ms
- ⚠️ 주의: 100ms ~ 500ms
- ❌ 경고: 500ms ~ 2000ms
- ❌ 에러: > 2000ms

**S1 (1시간):**
- 허용: 500ms 이상 지속 < 5회

**S2 (6시간):**
- 허용: 500ms 이상 지속 < 20회

**S3 (24시간):**
- 허용: 500ms 이상 지속 < 100회

---

### 2. WebSocket 재연결 (Reconnect)

**메트릭:** `ws_reconnect_count` = 시간당 재연결 횟수

**기준:**
- ✅ 정상: 0회/시간
- ⚠️ 주의: 1~5회/시간
- ❌ 경고: > 5회/시간
- ❌ 에러: > 20회/시간

**S1 (1시간):**
- 허용: 최대 5회

**S2 (6시간):**
- 허용: 평균 < 2회/시간 (총 < 12회)

**S3 (24시간):**
- 허용: 평균 < 1회/시간 (총 < 24회)

---

### 3. 메시지 갭 (Message Gap)

**메트릭:** `ws_message_gap_count` = 연속 snapshot None 횟수

**기준:**
- ✅ 정상: 0회
- ⚠️ 주의: 1~3회 연속
- ❌ 경고: 4~5회 연속
- ❌ 에러: > 5회 연속

**모든 시나리오:**
- 허용: 5회 이상 연속 < 1회

---

### 4. 루프 시간 (Loop Time)

**메트릭:** `loop_time_ms` = 루프 실행 시간

**기준:**
- ✅ 정상: < 1000ms
- ⚠️ 주의: 1000ms ~ 1500ms
- ❌ 경고: 1500ms ~ 3000ms
- ❌ 에러: > 3000ms

**모든 시나리오:**
- 평균: < 1500ms
- 최대: < 3000ms

---

## 📊 시나리오 정의

### S1: 1시간 WS 롱런 (개발·재연결 테스트용)

**목적:** WS 재연결 정책 검증, 기본 안정성 확인

**입력:**
```yaml
config: configs/live/arbitrage_live_ws_longrun.yaml
data_source: "ws"  # 강제
ws.enabled: true   # 강제
duration: 60분
mode: "paper"
```

**테스트 실패 기준:**
- ws_latency_ms > 500ms 지속 > 5회
- ws_reconnect_count > 5회
- ws_message_gap_count > 5회 연속
- loop_time_ms 평균 > 1500ms
- 에러 로그 > 10개

**예상 결과:**
```
Duration: 60.0s
Loops: 60
WS Latency Avg: < 100ms
WS Reconnects: 0~2회
Trades Opened: 2~5
Avg Loop Time: 1000±150ms
```

---

### S2: 6시간 WS 롱런 (야간 테스트용)

**목적:** 장시간 WS 안정성, 재연결 정책 검증

**입력:**
```yaml
config: configs/live/arbitrage_live_ws_longrun.yaml
data_source: "ws"  # 강제
ws.enabled: true   # 강제
duration: 360분 (6시간)
mode: "paper"
```

**테스트 실패 기준:**
- ws_latency_ms > 500ms 지속 > 20회
- ws_reconnect_count 평균 > 2회/시간 (총 > 12회)
- ws_message_gap_count > 5회 연속 > 1회
- loop_time_ms 평균 > 1500ms 또는 증가 추세
- 에러 로그 > 50개

**예상 결과:**
```
Duration: 360.0s
Loops: 360
WS Latency Avg: < 150ms
WS Reconnects: 0~12회 (평균 < 2회/시간)
Trades Opened: 10~20
Avg Loop Time: 1000±200ms
Memory Delta: < 100MB
```

---

### S3: 24시간 WS 롱런 (실제 "준-운영" 검증용)

**목적:** 실제 운영 환경 시뮬레이션, 일일 사이클 검증

**입력:**
```yaml
config: configs/live/arbitrage_live_ws_longrun.yaml
data_source: "ws"  # 강제
ws.enabled: true   # 강제
duration: 1440분 (24시간)
mode: "paper"
```

**테스트 실패 기준:**
- ws_latency_ms > 500ms 지속 > 100회
- ws_reconnect_count 평균 > 1회/시간 (총 > 24회)
- ws_message_gap_count > 5회 연속 > 2회
- loop_time_ms 평균 > 1500ms 또는 증가 추세
- 에러 로그 > 200개

**예상 결과:**
```
Duration: 1440.0s
Loops: 1440
WS Latency Avg: < 200ms
WS Reconnects: 0~24회 (평균 < 1회/시간)
Trades Opened: 50~100
Avg Loop Time: 1000±250ms
Memory Delta: < 200MB
Hourly Pattern: 안정적
```

---

## 🔍 WS 특화 관찰 항목

### 1. Snapshot Latency

**측정 방법:**
```python
ws_latency_ms = (현재 시간 - snapshot.timestamp) * 1000
```

**추적:**
- 최근 snapshot의 지연 시간
- 평균 지연 시간
- 최대 지연 시간
- 500ms 이상 지속 횟수

---

### 2. Reconnect Events

**추적:**
- 시간당 재연결 횟수
- 재연결 원인 (timeout, error, heartbeat fail 등)
- 재연결 소요 시간
- 재연결 중 snapshot None 발생

---

### 3. Message Gap

**추적:**
- 연속 snapshot None 횟수
- 메시지 갭 발생 시간
- 갭 복구 시간
- 갭 중 루프 시간 변화

---

### 4. 루프 시간 분석

**추적:**
- WS 모드 vs REST 모드 비교
- 재연결 중 루프 시간 변화
- 지연 시간과 루프 시간 상관관계

---

## 📋 WS 롱런 후 점검 항목

### 1. WS 연결 상태

- [ ] Upbit WS 연결 횟수
- [ ] Binance WS 연결 횟수
- [ ] 평균 연결 유지 시간
- [ ] 최대 연결 유지 시간

### 2. Snapshot 품질

- [ ] 평균 지연 시간
- [ ] 최대 지연 시간
- [ ] 지연 > 500ms 횟수
- [ ] 지연 > 2000ms 횟수

### 3. 메시지 처리

- [ ] 총 메시지 수신
- [ ] 메시지 손실 여부
- [ ] 연속 None 최대 횟수
- [ ] 메시지 갭 복구 시간

### 4. 성능 비교

- [ ] REST vs WS 루프 시간 비교
- [ ] WS 모드 오버헤드
- [ ] 메모리 사용량 비교

---

## 🛠️ 실행 방법

### S1 (1시간 WS 롱런)

```bash
python -m scripts.run_ws_longrun \
  --config configs/live/arbitrage_live_ws_longrun.yaml \
  --scenario S1 \
  --duration-minutes 60
```

### S2 (6시간 WS 롱런)

```bash
python -m scripts.run_ws_longrun \
  --config configs/live/arbitrage_live_ws_longrun.yaml \
  --scenario S2 \
  --duration-minutes 360
```

### S3 (24시간 WS 롱런)

```bash
python -m scripts.run_ws_longrun \
  --config configs/live/arbitrage_live_ws_longrun.yaml \
  --scenario S3 \
  --duration-minutes 1440
```

---

## ⚠️ WS 롱런 주의사항

### 1. 네트워크 환경

- 안정적인 인터넷 연결 필수
- 방화벽/프록시 설정 확인
- 대역폭 충분 확인

### 2. 시스템 리소스

- CPU: 최소 2 cores
- 메모리: 최소 512MB
- 디스크: 최소 1GB (로그용)

### 3. 모니터링

- 롱런 중 주기적 상태 확인
- 비정상 신호 발견 시 즉시 기록
- 네트워크 끊김 발생 시 자동 재연결 확인

### 4. 결과 기록

- 모든 WS 롱런 결과 저장
- 재연결 이벤트 기록
- 지연 시간 분포 분석

---

## 📈 성공 기준

### S1 (1시간)
- ✅ ws_latency_ms 평균 < 100ms
- ✅ ws_reconnect_count < 5회
- ✅ 루프 시간 평균 < 1500ms
- ✅ 에러 로그 < 10개

### S2 (6시간)
- ✅ ws_latency_ms 평균 < 150ms
- ✅ ws_reconnect_count < 12회 (평균 < 2회/시간)
- ✅ 루프 시간 평균 < 1500ms
- ✅ 루프 시간 증가 추세 없음
- ✅ 에러 로그 < 50개

### S3 (24시간)
- ✅ ws_latency_ms 평균 < 200ms
- ✅ ws_reconnect_count < 24회 (평균 < 1회/시간)
- ✅ 루프 시간 평균 < 1500ms
- ✅ 루프 시간 증가 추세 없음
- ✅ 에러 로그 < 200개
- ✅ 메모리 누수 없음
- ✅ 일일 사이클 패턴 안정적

---

## 🚀 다음 단계

### D53: Performance Tuning & Optimization

**목표:**
- WS 지연 시간 최적화
- 재연결 정책 개선
- 루프 시간 최적화

---

**D52 WebSocket Long-run Test Plan 정의 완료.** ✅

**작성자:** Cascade AI  
**작성일:** 2025-11-17  
**상태:** ✅ 정의 완료
