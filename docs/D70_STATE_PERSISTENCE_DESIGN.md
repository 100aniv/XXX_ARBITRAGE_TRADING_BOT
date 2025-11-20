# D70 – STATE_PERSISTENCE & RECOVERY: Design Specification

**작성일:** 2025-11-20  
**상태:** D70-1 (설계 & 영향도 분석)  
**목적:** CLEAN_RESET vs RESUME_FROM_STATE 모드 설계 및 상태 영속화 전략 정의

---

## 1. Design Goals (설계 목표)

### 1.1 핵심 요구사항

1. **재시작 안정성:** 엔진 크래시 후 재시작 시 일관된 상태 복원
2. **모드 선택:** CLEAN_RESET (완전 초기화) vs RESUME_FROM_STATE (중간 재시작)
3. **데이터 무결성:** Redis/DB/메모리 상태 간 모순 없음
4. **최소 침투:** 기존 엔진 코어 로직 최소 수정
5. **성능:** 상태 저장/복원이 루프 성능에 영향 최소화

### 1.2 Non-Goals (범위 외)

- 분산 시스템 상태 동기화
- 실시간 백업/복제
- 트랜잭션 롤백
- 타임머신 (과거 시점 복원)

---

## 2. State Categories (상태 카테고리)

### 2.1 Session State (세션 상태)

**저장 대상:**
```python
{
    "session_id": "session_20251120_010203",
    "start_time": 1700000000.0,
    "mode": "paper",  # paper | live | backtest
    "paper_campaign_id": "C1",
    "config": {
        "symbol_a": "KRW-BTC",
        "symbol_b": "BTCUSDT",
        "min_spread_bps": 30.0,
        # ... ArbitrageLiveConfig 전체
    },
    "loop_count": 1234,
    "status": "running"  # running | stopped | crashed
}
```

**저장 위치:** Redis + PostgreSQL  
**TTL:** Redis (1일), PostgreSQL (영구)  
**복원 시:** 세션 ID로 조회하여 config/상태 복원

---

### 2.2 Position State (포지션 상태)

**저장 대상:**
```python
{
    "session_id": "session_20251120_010203",
    "active_orders": {
        "1700000001.0": {
            "trade": {
                "side": "LONG_A_SHORT_B",
                "notional_usd": 5000.0,
                "entry_spread_bps": 35.0,
                "open_timestamp": 1700000001.0,
                "is_open": True
            },
            "order_a": {
                "order_id": "ORDER_A_123",
                "symbol": "KRW-BTC",
                "side": "BUY",
                "qty": 0.05,
                "price": 100500.0,
                "status": "FILLED"
            },
            "order_b": {
                "order_id": "ORDER_B_123",
                "symbol": "BTCUSDT",
                "side": "SELL",
                "qty": 0.05,
                "price": 40400.0,
                "status": "FILLED"
            }
        }
    },
    "paper_position_open_times": {
        "12345": 1700000001.0
    }
}
```

**저장 위치:** Redis (실시간) + PostgreSQL (스냅샷)  
**업데이트 주기:** 거래 개설/종료 시  
**복원 시:** 활성 주문 목록 복원, Paper 모드 Exit 신호 생성 재개

---

### 2.3 Metrics State (메트릭 상태)

**저장 대상:**
```python
{
    "session_id": "session_20251120_010203",
    "total_trades_opened": 50,
    "total_trades_closed": 45,
    "total_winning_trades": 30,
    "total_pnl_usd": 123.45,
    "max_dd_usd": -15.67,
    
    # D67: 멀티심볼 포트폴리오
    "per_symbol_pnl": {
        "BTCUSDT": 80.00,
        "ETHUSDT": 43.45
    },
    "per_symbol_trades_opened": {
        "BTCUSDT": 30,
        "ETHUSDT": 20
    },
    "per_symbol_trades_closed": {
        "BTCUSDT": 27,
        "ETHUSDT": 18
    },
    "per_symbol_winning_trades": {
        "BTCUSDT": 18,
        "ETHUSDT": 12
    },
    "portfolio_initial_capital": 10000.0,
    "portfolio_equity": 10123.45
}
```

**저장 위치:** Redis (실시간) + PostgreSQL (스냅샷)  
**업데이트 주기:** 거래 종료 시  
**복원 시:** 메트릭 누적 계속

---

### 2.4 Risk/Guard State (리스크/가드 상태)

**저장 대상:**
```python
{
    "session_id": "session_20251120_010203",
    "session_start_time": 1700000000.0,
    "daily_loss_usd": 25.50,
    
    # D58: Multi-Symbol state
    "per_symbol_loss": {
        "BTCUSDT": 10.00,
        "ETHUSDT": 15.50
    },
    "per_symbol_trades_rejected": {
        "BTCUSDT": 5,
        "ETHUSDT": 3
    },
    "per_symbol_trades_allowed": {
        "BTCUSDT": 30,
        "ETHUSDT": 20
    },
    
    # D60: Capital & Position Limits
    "per_symbol_capital_used": {
        "BTCUSDT": 5000.0,
        "ETHUSDT": 3000.0
    },
    "per_symbol_position_count": {
        "BTCUSDT": 2,
        "ETHUSDT": 1
    }
}
```

**저장 위치:** Redis (실시간) + PostgreSQL (스냅샷)  
**업데이트 주기:** 거래 실행/종료 시  
**복원 시:** 일일 손실 누적 계속, 리스크 한도 체크 재개

---

## 3. Storage Strategy (저장 전략)

### 3.1 Redis (Real-time State)

**용도:** 실시간 상태 저장/조회

**Key Namespace:**
```
arbitrage:state:{session_id}:{category}

예시:
- arbitrage:state:session_20251120_010203:session
- arbitrage:state:session_20251120_010203:positions
- arbitrage:state:session_20251120_010203:metrics
- arbitrage:state:session_20251120_010203:risk_guard
```

**TTL 전략:**
- 활성 세션: TTL 없음 (명시적 삭제)
- 종료 세션: 1일 후 자동 삭제

**장점:**
- 빠른 읽기/쓰기
- 실시간 업데이트 가능

**단점:**
- Redis 재시작 시 소실 (persistence 설정 필요)
- 메모리 제한

---

### 3.2 PostgreSQL (Persistent Snapshots)

**용도:** 영구 저장 및 히스토리 추적

**테이블 설계:**

#### 3.2.1 `session_snapshots` 테이블

```sql
CREATE TABLE IF NOT EXISTS session_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- 세션 메타데이터
    session_start_time TIMESTAMP NOT NULL,
    mode VARCHAR(20) NOT NULL,  -- paper | live | backtest
    paper_campaign_id VARCHAR(50),
    config JSONB NOT NULL,
    
    -- 세션 상태
    loop_count INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,  -- running | stopped | crashed
    
    -- 스냅샷 타입
    snapshot_type VARCHAR(20) NOT NULL,  -- periodic | on_trade | on_stop
    
    UNIQUE(session_id, created_at)
);

CREATE INDEX idx_session_snapshots_session ON session_snapshots(session_id);
CREATE INDEX idx_session_snapshots_created ON session_snapshots(created_at DESC);
```

#### 3.2.2 `position_snapshots` 테이블

```sql
CREATE TABLE IF NOT EXISTS position_snapshots (
    snapshot_id INTEGER REFERENCES session_snapshots(snapshot_id) ON DELETE CASCADE,
    position_key VARCHAR(50) NOT NULL,  -- trade.open_timestamp
    
    -- 거래 정보
    trade_data JSONB NOT NULL,
    order_a_data JSONB NOT NULL,
    order_b_data JSONB NOT NULL,
    
    -- Paper 모드 추가 정보
    position_open_time TIMESTAMP,
    
    PRIMARY KEY (snapshot_id, position_key)
);

CREATE INDEX idx_position_snapshots_snapshot ON position_snapshots(snapshot_id);
```

#### 3.2.3 `metrics_snapshots` 테이블

```sql
CREATE TABLE IF NOT EXISTS metrics_snapshots (
    snapshot_id INTEGER REFERENCES session_snapshots(snapshot_id) ON DELETE CASCADE,
    
    -- 전체 메트릭
    total_trades_opened INTEGER NOT NULL,
    total_trades_closed INTEGER NOT NULL,
    total_winning_trades INTEGER NOT NULL,
    total_pnl_usd DECIMAL(20, 8) NOT NULL,
    max_dd_usd DECIMAL(20, 8) NOT NULL,
    
    -- 멀티심볼 메트릭 (JSONB)
    per_symbol_pnl JSONB,
    per_symbol_trades_opened JSONB,
    per_symbol_trades_closed JSONB,
    per_symbol_winning_trades JSONB,
    
    -- 포트폴리오
    portfolio_initial_capital DECIMAL(20, 8) NOT NULL,
    portfolio_equity DECIMAL(20, 8) NOT NULL,
    
    PRIMARY KEY (snapshot_id)
);
```

#### 3.2.4 `risk_guard_snapshots` 테이블

```sql
CREATE TABLE IF NOT EXISTS risk_guard_snapshots (
    snapshot_id INTEGER REFERENCES session_snapshots(snapshot_id) ON DELETE CASCADE,
    
    -- 리스크 가드 상태
    session_start_time TIMESTAMP NOT NULL,
    daily_loss_usd DECIMAL(20, 8) NOT NULL,
    
    -- 멀티심볼 리스크 (JSONB)
    per_symbol_loss JSONB,
    per_symbol_trades_rejected JSONB,
    per_symbol_trades_allowed JSONB,
    per_symbol_capital_used JSONB,
    per_symbol_position_count JSONB,
    
    PRIMARY KEY (snapshot_id)
);
```

**스냅샷 주기:**
- **Periodic:** 5분마다 자동 스냅샷
- **On Trade:** 거래 개설/종료 시
- **On Stop:** 세션 종료 시

**장점:**
- 영구 저장
- 히스토리 추적 가능
- 복잡한 쿼리 가능

**단점:**
- 쓰기 속도 느림
- 스토리지 용량 필요

---

### 3.3 Hybrid Strategy (하이브리드 전략)

**실시간 상태:** Redis  
**영구 저장:** PostgreSQL

**동기화 전략:**
1. **Write:** Redis 먼저 → PostgreSQL 비동기 (백그라운드)
2. **Read (복원 시):** PostgreSQL 최신 스냅샷 → Redis 로드
3. **일관성:** PostgreSQL 스냅샷 ID를 Redis에 저장

---

## 4. Mode Design (모드 설계)

### 4.1 CLEAN_RESET Mode

**목적:** 완전 초기화 후 새 세션 시작

**동작:**
1. Redis에서 이전 세션 상태 삭제
2. PostgreSQL에 종료 스냅샷 저장 (선택)
3. 모든 메모리 상태 초기화
4. 새 `session_id` 생성
5. 정상 시작

**사용 시나리오:**
- 새로운 Paper 캠페인 시작
- 파라미터 변경 후 재시작
- 테스트 환경 초기화

**플로우:**
```
Start
  ↓
Check Redis for old session
  ↓
Delete old session (if exists)
  ↓
Initialize new session
  ↓
Create session_id
  ↓
Save initial snapshot to PostgreSQL
  ↓
Run
```

---

### 4.2 RESUME_FROM_STATE Mode

**목적:** 이전 세션 상태 복원 후 계속 실행

**동작:**
1. PostgreSQL에서 최신 스냅샷 조회
2. Redis에 상태 로드
3. `ArbitrageLiveRunner` 상태 복원
4. `RiskGuard` 상태 복원
5. `PaperExecutor` 포지션 복원
6. 일관성 검증
7. 계속 실행

**사용 시나리오:**
- 엔진 크래시 후 재시작
- 유지보수 재시작
- 인프라 업그레이드

**플로우:**
```
Start
  ↓
Load latest snapshot from PostgreSQL
  ↓
Validate snapshot (integrity check)
  ↓
Load state to Redis
  ↓
Restore ArbitrageLiveRunner state
  ↓
Restore RiskGuard state
  ↓
Restore PaperExecutor positions
  ↓
Verify consistency (Redis vs Memory)
  ↓
Resume execution
```

---

### 4.3 Mode Selection

**CLI 인자:**
```bash
# CLEAN_RESET (기본값)
python scripts/run_d65_campaigns.py --mode clean

# RESUME_FROM_STATE
python scripts/run_d65_campaigns.py --mode resume --session-id session_20251120_010203
```

**환경 변수:**
```bash
export ARBITRAGE_RESUME_MODE=true
export ARBITRAGE_SESSION_ID=session_20251120_010203
```

---

## 5. State Lifecycle (상태 생명주기)

### 5.1 Session Start (세션 시작)

#### CLEAN_RESET:
```python
1. Generate session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
2. Initialize all state variables
3. Save initial snapshot to PostgreSQL
4. Save session metadata to Redis
5. Start loop
```

#### RESUME_FROM_STATE:
```python
1. Load session_id from CLI/env
2. Query PostgreSQL for latest snapshot
3. Validate snapshot integrity
4. Load state to Redis
5. Restore ArbitrageLiveRunner state
6. Restore RiskGuard state
7. Restore PaperExecutor positions
8. Verify consistency
9. Resume loop from loop_count + 1
```

---

### 5.2 During Execution (실행 중)

**상태 업데이트 시점:**

1. **거래 개설 시:**
   ```python
   # Update Redis
   redis.hset(f"arbitrage:state:{session_id}:positions", trade_key, trade_data)
   
   # Async: Save snapshot to PostgreSQL
   background_task(save_position_snapshot, session_id, trade_data)
   ```

2. **거래 종료 시:**
   ```python
   # Update Redis
   redis.hdel(f"arbitrage:state:{session_id}:positions", trade_key)
   redis.hincrby(f"arbitrage:state:{session_id}:metrics", "total_trades_closed", 1)
   redis.hincrbyfloat(f"arbitrage:state:{session_id}:metrics", "total_pnl_usd", pnl)
   
   # Update RiskGuard
   redis.hincrbyfloat(f"arbitrage:state:{session_id}:risk_guard", "daily_loss_usd", loss)
   
   # Async: Save snapshot to PostgreSQL
   background_task(save_metrics_snapshot, session_id, metrics_data)
   ```

3. **주기적 스냅샷 (5분마다):**
   ```python
   # Save full snapshot to PostgreSQL
   save_full_snapshot(session_id, all_state_data)
   ```

---

### 5.3 Session End (세션 종료)

**정상 종료:**
```python
1. Save final snapshot to PostgreSQL (snapshot_type='on_stop')
2. Update session status to 'stopped'
3. Keep Redis state (TTL 1일)
4. Log summary
```

**비정상 종료 (크래시):**
```python
# 다음 시작 시:
1. Detect crashed session (status='running' but process not alive)
2. Update status to 'crashed' in PostgreSQL
3. RESUME_FROM_STATE 모드로 복원 가능
```

---

## 6. Consistency Guarantees (일관성 보장)

### 6.1 Redis vs PostgreSQL

**원칙:**
- Redis = 실시간 상태 (최신)
- PostgreSQL = 스냅샷 (약간 지연)

**복원 시:**
1. PostgreSQL 최신 스냅샷 로드
2. Redis에 로드
3. Redis를 SSOT로 사용

### 6.2 Redis vs Memory

**원칙:**
- Memory = 실행 중 SSOT
- Redis = 영속화 레이어

**업데이트 순서:**
1. Memory 상태 변경
2. Redis 동기 업데이트
3. PostgreSQL 비동기 업데이트

**복원 시:**
1. Redis → Memory 로드
2. Memory를 SSOT로 사용

### 6.3 Validation (검증)

**복원 시 검증 항목:**
1. **Config 일치:** 복원된 config와 현재 config 비교
2. **포지션 수량:** 활성 주문 수가 합리적인지
3. **PnL 범위:** 메트릭이 정상 범위 내인지
4. **타임스탬프:** 스냅샷이 너무 오래되지 않았는지 (< 1일)

**검증 실패 시:**
- 경고 로그 출력
- 사용자에게 CLEAN_RESET 권장
- 강제 종료 (안전 모드)

---

## 7. Error Handling (에러 처리)

### 7.1 Redis 연결 실패

**복원 시:**
- PostgreSQL 스냅샷만 사용
- In-memory fallback
- 경고 로그

**실행 중:**
- In-memory 상태 유지
- PostgreSQL 스냅샷만 저장
- 경고 로그

### 7.2 PostgreSQL 연결 실패

**복원 시:**
- Redis 상태만 사용 (있으면)
- 없으면 CLEAN_RESET 강제

**실행 중:**
- Redis 상태만 저장
- 경고 로그
- 주기적 재연결 시도

### 7.3 스냅샷 손상

**복원 시:**
- 이전 스냅샷 시도
- 모두 실패 시 CLEAN_RESET 강제

---

## 8. Acceptance Criteria (인수 기준)

### 8.1 Scenario 1: 단일 심볼 포지션 복원

**Setup:**
1. Paper 모드 시작
2. 1개 포지션 오픈
3. 엔진 강제 종료 (Ctrl+C)

**Test:**
1. RESUME_FROM_STATE 모드로 재시작
2. 포지션 복원 확인
3. Exit 신호 생성 확인
4. PnL 계산 정상 확인

**Expected:**
- ✅ 포지션 1개 복원
- ✅ `_total_trades_opened = 1`
- ✅ Paper Exit 신호 생성 재개
- ✅ 거래 종료 후 PnL 누적 정상

---

### 8.2 Scenario 2: 멀티 심볼 포트폴리오 복원

**Setup:**
1. Paper 모드 시작 (BTC + ETH)
2. BTC 2개, ETH 1개 포지션 오픈
3. BTC 1개 청산 (PnL +$10)
4. 엔진 강제 종료

**Test:**
1. RESUME_FROM_STATE 모드로 재시작
2. 활성 포지션 복원 확인 (BTC 1개, ETH 1개)
3. 메트릭 복원 확인
4. 추가 거래 실행 후 포트폴리오 PnL 정상 확인

**Expected:**
- ✅ 활성 포지션 2개 복원 (BTC 1, ETH 1)
- ✅ `_per_symbol_pnl = {"BTCUSDT": 10.0, "ETHUSDT": 0.0}`
- ✅ `_total_trades_closed = 1`
- ✅ 추가 거래 후 PnL 누적 정상

---

### 8.3 Scenario 3: RiskGuard 상태 복원

**Setup:**
1. Paper 모드 시작
2. 5개 거래 실행 (3승 2패, 손실 -$20)
3. `daily_loss_usd = 20.0`
4. 엔진 강제 종료

**Test:**
1. RESUME_FROM_STATE 모드로 재시작
2. RiskGuard 상태 복원 확인
3. 추가 손실 거래 실행
4. 일일 손실 한도 체크 정상 확인

**Expected:**
- ✅ `daily_loss_usd = 20.0` 복원
- ✅ 추가 손실 시 누적 정상
- ✅ 한도 초과 시 SESSION_STOP 정상 동작

---

### 8.4 Scenario 4: CLEAN_RESET vs RESUME 선택

**Setup:**
1. Paper 모드 실행 중 (포지션 열림)
2. 엔진 강제 종료

**Test 1 (CLEAN_RESET):**
1. `--mode clean`으로 재시작
2. 모든 상태 초기화 확인
3. 새 세션 ID 생성 확인

**Expected:**
- ✅ 이전 포지션 무시
- ✅ 메트릭 0으로 초기화
- ✅ 새 `session_id` 생성

**Test 2 (RESUME_FROM_STATE):**
1. `--mode resume --session-id <old_id>`로 재시작
2. 이전 상태 복원 확인

**Expected:**
- ✅ 이전 포지션 복원
- ✅ 메트릭 누적 계속
- ✅ 동일 `session_id` 사용

---

### 8.5 Scenario 5: 스냅샷 손상 처리

**Setup:**
1. Paper 모드 실행
2. PostgreSQL 스냅샷 수동 손상 (JSONB 필드 깨뜨리기)
3. 엔진 강제 종료

**Test:**
1. RESUME_FROM_STATE 모드로 재시작
2. 스냅샷 검증 실패 확인
3. 이전 스냅샷 시도 확인
4. 모두 실패 시 CLEAN_RESET 강제 확인

**Expected:**
- ✅ 손상된 스냅샷 감지
- ✅ 이전 스냅샷 시도
- ✅ 모두 실패 시 에러 메시지 + 종료
- ✅ 사용자에게 CLEAN_RESET 권장

---

## 9. Performance Considerations (성능 고려사항)

### 9.1 Redis 쓰기 오버헤드

**예상 영향:**
- 거래당 +1~2ms (Redis 쓰기)
- 루프당 영향 최소 (비동기 가능)

**최적화:**
- 배치 업데이트 (HMSET)
- 비동기 쓰기 (백그라운드 스레드)

### 9.2 PostgreSQL 스냅샷 오버헤드

**예상 영향:**
- 스냅샷당 +10~50ms
- 5분마다 1회 → 루프 영향 없음

**최적화:**
- 비동기 쓰기 (백그라운드 스레드)
- 배치 INSERT

### 9.3 복원 시간

**예상 시간:**
- Redis 로드: < 100ms
- PostgreSQL 조회: < 500ms
- 메모리 복원: < 100ms
- **Total: < 1초**

---

## 10. Implementation Roadmap (구현 로드맵)

### D70-2: ENGINE_HOOKS & STATE_STORE

1. **StateStore 모듈 생성**
   - `arbitrage/state_store.py`
   - `save_session_state()`
   - `load_session_state()`
   - `save_snapshot_to_db()`

2. **ArbitrageLiveRunner 훅 추가**
   - `_save_state_to_redis()`
   - `_restore_state_from_redis()`
   - `_save_snapshot_to_db()` (비동기)

3. **RiskGuard 훅 추가**
   - `save_state()`
   - `restore_state()`

4. **PostgreSQL 스키마 생성**
   - `db/migrations/d70_state_persistence.sql`

### D70-3: RESUME_SCENARIO_TESTS

1. **테스트 스크립트 작성**
   - `scripts/test_d70_resume.py`
   - Scenario 1~5 자동화

2. **회귀 테스트**
   - D65/D66/D67 정상 동작 확인

3. **문서 업데이트**
   - `docs/D70_REPORT.md`

---

**작성자:** Windsurf Cascade  
**검토 필요:** D70-2 구현 전 아키텍처 리뷰
