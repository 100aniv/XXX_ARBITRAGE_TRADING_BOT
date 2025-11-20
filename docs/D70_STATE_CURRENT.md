# D70 – STATE_PERSISTENCE & RECOVERY: Current State Analysis

**작성일:** 2025-11-20  
**상태:** D70-1 (설계 & 영향도 분석)  
**목적:** 현재 시스템의 상태 관리 구조를 파악하고 영속화/복원 설계의 기반 마련

---

## 1. State Inventory (상태 목록)

### 1.1 세션 상태 (Session State)

**위치:** `ArbitrageLiveRunner` (in-memory)

```python
# arbitrage/live_runner.py
self._start_time = time.time()
self._loop_count = 0
self._session_stop_requested = False
self._paper_campaign_id = None  # Paper 캠페인 ID
```

**특징:**
- 모두 메모리에만 존재
- 재시작 시 초기화됨
- Redis/DB 저장 없음

**SSOT:** `ArbitrageLiveRunner`

---

### 1.2 포지션/트레이드 상태 (Position/Trade State)

#### 1.2.1 활성 주문 (Active Orders)

**위치:** `ArbitrageLiveRunner._active_orders` (in-memory)

```python
self._active_orders: Dict[str, Dict[str, Any]] = {}
# Key: trade.open_timestamp
# Value: {
#     "trade": ArbitrageTrade,
#     "order_a": Order,
#     "order_b": Order
# }
```

**특징:**
- 메모리에만 존재
- 거래 종료 시 삭제됨
- Redis/DB 저장 없음

#### 1.2.2 포지션 추적

**위치:**
- `PaperExecutor.positions` (in-memory, Paper 모드)
- `PortfolioState.positions` (in-memory)
- `PortfolioState.per_symbol_positions` (in-memory, 멀티심볼)

```python
# arbitrage/execution/executor.py
self.positions: Dict[str, Position] = {}  # {position_id: Position}

# arbitrage/types.py
@dataclass
class PortfolioState:
    positions: Dict[str, Position] = field(default_factory=dict)
    per_symbol_positions: Dict[str, Dict[str, Position]] = field(default_factory=dict)
```

**특징:**
- 메모리에만 존재
- `StateManager`를 통해 Redis 저장 가능 (현재 사용 안 함)
- 재시작 시 복원 불가

#### 1.2.3 트레이드 메트릭

**위치:** `ArbitrageLiveRunner` (in-memory)

```python
self._total_trades_opened = 0
self._total_trades_closed = 0
self._total_winning_trades = 0
self._total_pnl_usd = 0.0

# D67: 멀티심볼 포트폴리오
self._per_symbol_pnl: Dict[str, float] = {}
self._per_symbol_trades_opened: Dict[str, int] = {}
self._per_symbol_trades_closed: Dict[str, int] = {}
self._per_symbol_winning_trades: Dict[str, int] = {}
self._portfolio_initial_capital = 10000.0
self._portfolio_equity = 10000.0
```

**특징:**
- 메모리에만 존재
- 세션 종료 시 소실
- Redis/DB 저장 없음

**SSOT:** `ArbitrageLiveRunner`

---

### 1.3 리스크/가드 상태 (Risk/Guard State)

**위치:** `RiskGuard` (in-memory)

```python
# arbitrage/live_runner.py
class RiskGuard:
    def __init__(self, risk_limits: RiskLimits):
        self.session_start_time = time.time()
        self.daily_loss_usd = 0.0
        
        # D58: Multi-Symbol state tracking
        self.per_symbol_loss: Dict[str, float] = {}
        self.per_symbol_trades_rejected: Dict[str, int] = {}
        self.per_symbol_trades_allowed: Dict[str, int] = {}
        
        # D60: Multi-Symbol Capital & Position Limits
        self.per_symbol_limits: Dict[str, SymbolRiskLimits] = {}
        self.per_symbol_capital_used: Dict[str, float] = {}
        self.per_symbol_position_count: Dict[str, int] = {}
```

**특징:**
- 모두 메모리에만 존재
- 일일 손실 누적 (`daily_loss_usd`)은 재시작 시 리셋됨
- 심볼별 리스크 상태 추적
- Redis/DB 저장 없음

**SSOT:** `RiskGuard`

---

### 1.4 Paper 모드 상태 (Paper Mode State)

**위치:** `ArbitrageLiveRunner` (in-memory)

```python
# D64/D65: Paper 모드 Exit 신호 생성
self._position_open_times: Dict[int, float] = {}  # {trade_id: open_time}
self._last_price_injection_time = 0.0
self._paper_exit_trigger_interval = 10.0  # 10초 후 Exit 신호
```

**특징:**
- Paper 모드 전용
- 포지션 열린 시간 추적하여 Exit 신호 생성
- 메모리에만 존재

**SSOT:** `ArbitrageLiveRunner`

---

## 2. Storage Layer Analysis (저장 계층 분석)

### 2.1 Redis (StateManager)

**파일:** `arbitrage/state_manager.py`

**네임스페이스 구조:**
```
{namespace}:{key_prefix}:{category}:{identifier}

예시:
- default:arbitrage:prices:upbit:KRW-BTC
- default:arbitrage:signal:KRW-BTC
- default:arbitrage:orders:ORDER_123
- default:arbitrage:positions:KRW-BTC
- default:arbitrage:execution:KRW-BTC:1234567890
- default:arbitrage:metrics:live
- default:arbitrage:portfolio:state
- default:arbitrage:stats:total_trades
- default:arbitrage:heartbeat:live_runner
```

**현재 저장되는 데이터:**
1. **가격 (Prices):** 거래소별 호가 (TTL: 60초)
2. **신호 (Signals):** 아비트라지 신호 (TTL: 300초)
3. **주문 (Orders):** 주문 정보 (TTL: 86400초)
4. **포지션 (Positions):** 포지션 정보 (TTL: 86400초)
5. **실행 결과 (Executions):** 거래 실행 결과 (TTL: 86400초)
6. **메트릭 (Metrics):** 실시간 메트릭 (TTL: 300초)
7. **포트폴리오 상태 (Portfolio State):** 포트폴리오 스냅샷 (TTL: 300초)
8. **통계 (Stats):** 누적 통계
9. **하트비트 (Heartbeat):** 컴포넌트 헬스체크 (TTL: 60초)

**특징:**
- **Optional:** `StateManager`는 Redis 연결 실패 시 in-memory fallback
- **현재 사용 여부:** `ArbitrageLiveRunner`에서 직접 사용 안 함
- **TTL 기반:** 대부분의 데이터가 자동 만료됨
- **영속성 없음:** Redis 재시작 시 모든 데이터 소실

**SSOT:** `StateManager` (사용 시)

---

### 2.2 PostgreSQL (Tuning Results Only)

**파일:** `db/migrations/d68_tuning_results.sql`

**테이블:** `tuning_results` (D68 전용)

```sql
CREATE TABLE IF NOT EXISTS tuning_results (
    run_id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    param_set JSONB NOT NULL,
    total_pnl DECIMAL(20, 8) NOT NULL,
    total_trades INTEGER NOT NULL,
    -- ... 성능 메트릭
);
```

**현재 저장되는 데이터:**
- D68 파라미터 튜닝 결과만 저장
- 실시간 거래 상태는 저장 안 함

**특징:**
- **D68 전용:** 튜닝 결과 영속화
- **실시간 상태 없음:** 포지션/주문/가드 상태 저장 안 함
- **영속성:** 재시작 후에도 유지됨

---

### 2.3 In-Memory Only (현재 대부분)

**ArbitrageLiveRunner 상태:**
- 세션 메타데이터
- 활성 주문
- 트레이드 메트릭
- 포지션 추적
- Paper 모드 상태

**RiskGuard 상태:**
- 일일 손실
- 심볼별 리스크 상태

**PaperExecutor 상태:**
- 포지션
- 주문

**특징:**
- **휘발성:** 프로세스 종료 시 모두 소실
- **복원 불가:** 재시작 시 초기 상태로 시작
- **빠름:** 메모리 접근 속도

---

## 3. Mode-Specific State Handling (모드별 상태 처리)

### 3.1 Paper Mode

**상태 저장:**
- 메모리에만 존재
- `PaperExchange`가 가상 주문/체결 관리
- `_position_open_times`로 Exit 신호 생성

**재시작 시:**
- 모든 상태 초기화
- 포지션/주문 복원 불가

### 3.2 Live Mode (향후)

**현재 구현:**
- Paper와 동일하게 메모리 기반
- 실제 거래소 API 사용

**재시작 시:**
- 거래소 API로 실제 포지션 조회 가능
- 하지만 내부 상태 (PnL, 메트릭) 복원 불가

### 3.3 Backtest Mode (향후)

**현재 구현:**
- 없음

---

## 4. State Lifecycle (상태 생명주기)

### 4.1 세션 시작 (Session Start)

```python
# ArbitrageLiveRunner.__init__()
self._start_time = time.time()
self._loop_count = 0
self._total_trades_opened = 0
# ... 모든 상태 초기화
```

### 4.2 거래 실행 (Trade Execution)

```python
# 1. 신규 거래 개설
self._execute_open_trade(trade)
self._active_orders[trade.open_timestamp] = {...}
self._total_trades_opened += 1

# 2. 거래 종료
self._execute_close_trade(trade)
del self._active_orders[trade.open_timestamp]
self._total_trades_closed += 1
self._total_pnl_usd += trade.pnl_usd
```

### 4.3 세션 종료 (Session End)

```python
# ArbitrageLiveRunner.run_forever()
# 정상 종료 시:
logger.info("[D43_LIVE] Session completed")
# 모든 메모리 상태 소실
```

### 4.4 비정상 종료 (Abnormal Termination)

**현재 동작:**
- 프로세스 강제 종료 시 모든 상태 소실
- 복원 메커니즘 없음
- 다음 시작 시 완전 초기화

---

## 5. SSOT (Single Source of Truth) 분석

| 상태 카테고리 | 현재 SSOT | 저장 위치 | 영속성 |
|--------------|----------|----------|--------|
| 세션 메타데이터 | `ArbitrageLiveRunner` | Memory | ❌ |
| 활성 주문 | `ArbitrageLiveRunner._active_orders` | Memory | ❌ |
| 포지션 | `PaperExecutor.positions` | Memory | ❌ |
| 트레이드 메트릭 | `ArbitrageLiveRunner` | Memory | ❌ |
| 리스크 가드 상태 | `RiskGuard` | Memory | ❌ |
| Paper 모드 상태 | `ArbitrageLiveRunner` | Memory | ❌ |
| 튜닝 결과 | `ParameterTuner` | PostgreSQL | ✅ |
| 가격/신호 (Optional) | `StateManager` | Redis (TTL) | ⚠️ |

**결론:**
- **대부분 메모리 기반:** 재시작 시 복원 불가
- **영속성 없음:** PostgreSQL은 D68 튜닝 결과만 저장
- **Redis 미사용:** `StateManager` 존재하지만 실제 사용 안 함

---

## 6. Critical Gaps (핵심 갭)

### 6.1 재시작 시 상태 복원 불가

**문제:**
- 엔진 크래시 후 재시작 시 모든 상태 소실
- 활성 포지션 정보 없음
- 누적 PnL/메트릭 초기화

**영향:**
- 운영 중 재시작 불가
- 포지션 열린 상태에서 크래시 시 수동 복구 필요

### 6.2 일일 손실 추적 리셋

**문제:**
- `RiskGuard.daily_loss_usd`가 메모리에만 존재
- 재시작 시 0으로 리셋

**영향:**
- 일일 손실 한도 체크 무효화
- 재시작 후 추가 손실 발생 가능

### 6.3 멀티심볼 포트폴리오 상태 소실

**문제:**
- `_per_symbol_pnl`, `_per_symbol_trades_*` 메모리 기반
- 재시작 시 심볼별 통계 소실

**영향:**
- 포트폴리오 레벨 리스크 관리 불가
- 심볼별 성과 추적 단절

### 6.4 Paper 모드 Exit 신호 생성 중단

**문제:**
- `_position_open_times` 소실
- 재시작 후 Exit 신호 생성 불가

**영향:**
- Paper 테스트 중단 시 재시작 불가
- 포지션 청산 로직 테스트 불가

---

## 7. Recommendations for D70-2 (D70-2 권장 사항)

### 7.1 우선순위 1: 핵심 상태 영속화

**저장 대상:**
1. 활성 포지션 (`_active_orders`)
2. 트레이드 메트릭 (`_total_*`, `_per_symbol_*`)
3. 리스크 가드 상태 (`daily_loss_usd`, `per_symbol_loss`)
4. 세션 메타데이터 (`_start_time`, `_paper_campaign_id`)

**저장 위치:**
- **Redis:** 실시간 상태 (TTL 없음 또는 긴 TTL)
- **PostgreSQL:** 세션 스냅샷 (영속성)

### 7.2 우선순위 2: 복원 로직 구현

**필요 기능:**
1. `ArbitrageLiveRunner.restore_from_state()`
2. `RiskGuard.restore_from_state()`
3. `PaperExecutor.restore_positions()`

### 7.3 우선순위 3: 모드별 전략

**CLEAN_RESET:**
- 기존 동작 유지
- Redis/DB 상태 정리 후 시작

**RESUME_FROM_STATE:**
- Redis/DB에서 상태 읽기
- 일관성 검증
- 복원 후 계속 실행

---

## 8. Next Steps (다음 단계)

1. **D70_STATE_PERSISTENCE_DESIGN.md** 작성
   - CLEAN_RESET vs RESUME_FROM_STATE 설계
   - Redis/PostgreSQL 스키마 정의
   - 상태 생명주기 설계

2. **D70_STATE_IMPACT_ANALYSIS.md** 작성
   - 모듈별 변경 사항 분석
   - 잠재적 리스크 식별
   - 구현 우선순위 정의

3. **D70-2: 구현 단계**
   - StateStore 모듈 생성
   - 복원 로직 구현
   - 테스트 시나리오 실행

---

**작성자:** Windsurf Cascade  
**검토 필요:** D70-2 구현 전 아키텍처 리뷰
