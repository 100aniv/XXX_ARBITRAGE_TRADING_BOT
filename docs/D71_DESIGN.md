# D71: FAILURE_INJECTION & AUTO_RECOVERY – Design Document

**Status:** ⏳ D71-0 (환경 준비 및 설계) COMPLETED  
**Next:** D71-1 (구현) TODO

---

## Executive Summary

D71은 ArbitrageLiveRunner의 **실패 복구 및 자동 재시작** 메커니즘을 검증하는 단계입니다.

**목표:**
- WebSocket/Redis/DB 장애 시 자동 복구
- Runner 프로세스 강제 종료 후 RESUME_FROM_STATE 정상 동작
- Network latency/손상된 snapshot 등 극단 상황 대응
- Zero position loss, zero duplicate orders

**핵심 질문:**
1. WS 연결이 끊기면 자동으로 재연결되는가?
2. Redis가 죽었다 살아나면 상태가 복구되는가?
3. Runner가 강제 종료되면 RESUME_FROM_STATE로 재시작 가능한가?
4. 실패 시 손실·중복 주문·상태 꼬임이 없는가?

---

## D71 Roadmap

### D71-0: FAILURE_INJECTION_PREP (✅ COMPLETED)

**목표:** 환경 준비 및 시나리오 설계

**완료 사항:**
- ✅ `scripts/test_d71_failure_scenarios.py` skeleton 생성
- ✅ 5개 failure 시나리오 정의
- ✅ 모니터링 요구사항 명세
- ✅ `docs/D71_DESIGN.md` 템플릿 생성

**산출물:**
- scripts/test_d71_failure_scenarios.py (~400 lines, skeleton)
- docs/D71_DESIGN.md (본 문서)

---

### D71-1: FAILURE_INJECTION_IMPLEMENTATION (⏳ TODO)

**목표:** 실패 주입 로직 구현

**구현 항목:**
1. **FailureInjector 클래스**
   - WS drop/reconnect 시뮬레이션
   - Redis connection 중단/재시작
   - Network latency 주입
   - DB snapshot 손상 시뮬레이션

2. **FailureMonitor 클래스**
   - 실시간 메트릭 수집 (WS latency, loop latency, Redis RTT)
   - 복구 시간 측정 (MTTR)
   - 상태 검증 (position loss, duplicate orders)

3. **시나리오별 구현**
   - Scenario 1: WS Drop & Reconnect
   - Scenario 2: Redis Failure & Recovery
   - Scenario 3: Runner Kill & RESUME
   - Scenario 4: Network Latency Spike
   - Scenario 5: Snapshot Corruption

**예상 변경:**
- arbitrage/live_runner.py: +100 lines (reconnection hooks)
- arbitrage/binance_ws.py: +50 lines (WS reconnect logic)
- arbitrage/state_store.py: +50 lines (fallback logic)
- scripts/test_d71_failure_scenarios.py: +600 lines (구현)

---

### D71-2: AUTO_RECOVERY_TESTS (⏳ TODO)

**목표:** 자동 복구 검증

**테스트 시나리오:**
- 5개 failure 시나리오 모두 PASS
- MTTR 목표치 달성
- 회귀 테스트 (D65-D70) PASS

**산출물:**
- docs/D71_REPORT.md

---

## Failure Scenarios

### Scenario 1: WebSocket Drop & Reconnect

**시뮬레이션:**
- Phase 1: Runner 정상 실행 (30초)
- Phase 2: WS connection drop 주입 (5초)
- Phase 3: 자동 reconnect 대기
- Phase 4: Reconnect 후 정상 트레이딩 재개 (30초)

**성공 기준:**
- MTTR < 10초
- Loop latency 증가 < 200ms during reconnect
- Reconnect 후 첫 Entry 정상 발생
- Position loss = 0
- Duplicate orders = 0

**구현 방법 (D71-1):**
- `binance_ws.py` / `upbit_ws.py`에 reconnect 로직 추가
- WS connection drop 감지 → 자동 reconnect
- Reconnect 중에도 loop는 계속 실행 (데이터만 stale)

---

### Scenario 2: Redis Failure & Recovery

**시뮬레이션:**
- Phase 1: Runner 정상 실행 (30초)
- Phase 2: Redis container stop (10초)
- Phase 3: Redis container start
- Phase 4: 자동 reconnect 및 state 재로드 (30초)

**성공 기준:**
- MTTR < 30초
- Redis 중단 중에도 loop 실행 (state save 실패만 로그)
- Redis 복구 후 state 일치성 100%
- PostgreSQL snapshot에서 state 재로드 정상
- Position loss = 0

**구현 방법 (D71-1):**
- `state_store.py`에 Redis fallback 로직 추가
- Redis 연결 실패 시 graceful degradation (메모리 모드)
- Redis 복구 시 PostgreSQL snapshot에서 재로드

---

### Scenario 3: Runner Kill & RESUME_FROM_STATE

**시뮬레이션:**
- Phase 1: Runner 정상 실행 (30초)
- Phase 2: 활성 포지션 있는 상태에서 SIGKILL
- Phase 3: 수동으로 RESUME_FROM_STATE 재시작
- Phase 4: 이전 세션 상태 복원 확인 (30초)

**성공 기준:**
- MTTR < 60초 (kill → detect → restart → restore)
- Snapshot 로드 성공률 100%
- Active positions 복원 정확도 100%
- Metrics 연속성 유지 (PnL, winrate, equity)
- Duplicate orders = 0

**구현 방법 (D71-1):**
- D70 RESUME_FROM_STATE 기능 활용
- Kill 후 snapshot 무결성 검증
- Active positions 정확히 복원되는지 확인

---

### Scenario 4: Network Latency Spike

**시뮬레이션:**
- Phase 1: Runner 정상 실행 (30초)
- Phase 2: Network latency 3초 주입 (20초)
- Phase 3: Latency 정상화 (30초)

**성공 기준:**
- Loop latency 증가 < 500ms (latency injection 포함)
- WS timeout → reconnect 정상 동작
- Redis timeout → fallback 정상 동작
- Entry/Exit 정확도 유지 (100%)

**구현 방법 (D71-1):**
- Network latency injection 헬퍼 함수
- Timeout 로직 검증
- Loop latency 모니터링

---

### Scenario 5: Snapshot Corruption & Fallback

**시뮬레이션:**
- Phase 1: Runner 정상 실행 (30초)
- Phase 2: Snapshot 저장
- Phase 3: Snapshot에 손상 데이터 주입 (config 필드 삭제)
- Phase 4: RESUME_FROM_STATE 시도 → Fallback 확인

**성공 기준:**
- Snapshot corruption 감지율 100%
- validate_snapshot() 정상 동작
- Fallback to Redis state 또는 CLEAN_RESET
- 크래시 없이 graceful degradation

**구현 방법 (D71-1):**
- D70 validate_snapshot() 활용
- Corruption injection 헬퍼 함수
- Fallback 메커니즘 검증

---

## Monitoring Requirements

D71 테스트는 다음 메트릭을 실시간 기록해야 함:

### 1. WebSocket 메트릭
- WS 메시지 수신 시간 vs 처리 시간 (ms)
- Reconnection 소요 시간 (ms)
- Drop → Reconnect 전체 시간 (ms)

### 2. Loop Latency
- 루프 시작 → 종료 시간 (ms)
- 정상 범위: 100-200ms
- 허용 최대: 500ms

### 3. Redis Round-Trip Time
- SET/GET 요청 → 응답 시간 (ms)
- 정상 범위: < 5ms
- 타임아웃: 1000ms

### 4. Snapshot Save/Restore Time
- PostgreSQL 스냅샷 저장 시간 (ms)
- 스냅샷 로드 시간 (ms)
- 정상 범위: < 100ms

### 5. 포지션 상태 변화
- Entry/Exit 이벤트 타임스탬프
- Active positions 개수 추적
- Position lost/duplicate 감지

### 6. RiskGuard 발동 패턴
- Daily loss 증가 추적
- Rejection 발생 시각
- 복구 후 상태 일치 여부

### 7. 에러 발생 로그
- 에러 타입 및 스택 트레이스
- 발생 빈도 (초당 에러 수)
- 자동 복구 성공/실패

### 8. Recovery 소요 시간 (MTTR)
- Failure 발생 → Detection
- Detection → Recovery 시작
- Recovery 완료 → 정상 동작
- 전체 MTTR

---

## Target MTTR (Mean Time To Recovery)

| Failure Type | Target MTTR | Max Acceptable |
|--------------|-------------|----------------|
| WS Drop | < 10초 | 30초 |
| Redis Failure | < 30초 | 60초 |
| Runner Kill | < 60초 | 120초 |
| Network Latency | < 5초 | 10초 |
| Snapshot Corruption | < 10초 | 30초 |

---

## Acceptance Criteria (D71 전체)

| Criterion | Status | Target |
|-----------|--------|--------|
| D71-0: 환경 준비 및 설계 | ✅ DONE | Skeleton + Design |
| D71-1: Failure Injection 구현 | ⏳ TODO | 5 scenarios |
| D71-2: Auto-Recovery 검증 | ⏳ TODO | 5/5 PASS |
| MTTR 목표치 달성 | ⏳ TODO | 모든 시나리오 |
| Position loss = 0 | ⏳ TODO | 모든 시나리오 |
| Duplicate orders = 0 | ⏳ TODO | 모든 시나리오 |
| 회귀 테스트 PASS | ⏳ TODO | D65-D70 |
| docs/D71_REPORT.md | ⏳ TODO | Final report |

---

## Implementation Notes (D71-1)

### WS Reconnection Logic
```python
# arbitrage/binance_ws.py
class BinanceWebSocket:
    async def _reconnect(self):
        """WS 재연결 로직"""
        max_retries = 5
        retry_delay = 2.0  # exponential backoff
        
        for attempt in range(max_retries):
            try:
                await self._connect()
                logger.info(f"[WS] Reconnected after {attempt+1} attempts")
                return True
            except Exception as e:
                logger.warning(f"[WS] Reconnect attempt {attempt+1} failed: {e}")
                await asyncio.sleep(retry_delay * (2 ** attempt))
        
        logger.error("[WS] Max reconnect attempts reached")
        return False
```

### Redis Fallback Logic
```python
# arbitrage/state_store.py
class StateStore:
    def save_state_to_redis(self, session_id, state_data):
        """Redis 저장 (fallback 포함)"""
        try:
            # Redis save
            self.redis.set(key, data)
        except redis.ConnectionError as e:
            logger.warning(f"[STATE_STORE] Redis unavailable, fallback to memory: {e}")
            # Graceful degradation: 메모리에만 저장
            self._memory_cache[session_id] = state_data
            return False
        return True
```

### Runner Kill Detection
```python
# scripts/test_d71_failure_scenarios.py
async def scenario_3_runner_kill_resume():
    # Phase 1: Start runner
    runner_process = start_runner_process()
    await asyncio.sleep(30)
    
    # Phase 2: Kill runner (SIGKILL)
    runner_process.kill()
    await asyncio.sleep(2)
    
    # Phase 3: Restart with RESUME_FROM_STATE
    runner_process = start_runner_process(mode="RESUME_FROM_STATE")
    
    # Phase 4: Verify state restored
    verify_state_continuity()
```

---

## Next Steps

**D71-1 TODO:**
1. FailureInjector 클래스 구현
2. FailureMonitor 클래스 구현
3. 5개 시나리오 구현
4. WS reconnect 로직 추가 (binance_ws.py, upbit_ws.py)
5. Redis fallback 로직 추가 (state_store.py)
6. 테스트 실행 및 검증

**D71-2 TODO:**
1. 5/5 시나리오 PASS 달성
2. MTTR 목표치 측정
3. 회귀 테스트 (D65-D70)
4. docs/D71_REPORT.md 작성
5. Git commit

---

**D71-0 STATUS: ✅ COMPLETED**  
**D71-1 STATUS: ⏳ TODO**  
**D71 Overall STATUS: ⏳ IN PROGRESS**
