# D80-3: Trade-level Spread & Liquidity Logging 설계

**상태:** 🚧 **IN PROGRESS**  
**날짜:** 2025-12-04  
**작성자:** arbitrage-lite project

---

## 1. 배경 & 목적

### 1.1 왜 D80-3가 필요한가?

**D80-2에서 드러난 핵심 GAP:**

D80-2 분석 결과, D77-0-RM-EXT 1시간 Top20/Top50 실행에서:
- ✅ **엔진/인프라 레벨:** GO (1,650+ round trips, 안정적 메모리/CPU)
- ⚠️ **실제 시장 엣지:** 추가 검증 필요

**데이터 레벨 한계:**
1. **Trade-level 스프레드 데이터 부재**
   - 현재: 전체 PnL, round trips 수만 집계
   - 문제: 각 거래의 실제 스프레드가 몇 bps였는지 알 수 없음
   
2. **호가 잔량 정보 부재**
   - 현재: PAPER 모드에서 호가창 상태를 로깅하지 않음
   - 문제: 대량 거래 시 실제 체결 가능성을 평가할 수 없음

3. **체결 가격 상세 부재**
   - 현재: 진입/퇴출 시 예상 가격만 사용
   - 문제: 실제 슬리피지, 부분 체결 상황을 시뮬레이션할 수 없음

4. **Win Rate 100%의 구조적 원인 검증 불가**
   - 현재: "100% = 구조적 결과"라는 해석만 가능
   - 필요: Trade-level에서 "왜 100%인지" 데이터로 증명

### 1.2 D80-3의 목표

**"각 거래의 스프레드/유동성/체결 정보를 로깅하여, Win Rate 100% 및 $200k/h PnL의 현실성을 데이터 레벨에서 검증할 수 있게 만든다"**

**구체적 목표:**
1. Trade-level 로그 스키마 정의 (스프레드, 호가, 체결 정보)
2. 엔진에 최소 침습 방식으로 로깅 훅 추가
3. JSONL 파일 기반 저장 (향후 PostgreSQL 확장 가능)
4. 3~6분 스모크 테스트로 검증

---

## 2. AS-IS 정리

### 2.1 현재 D77-0 / D80-2 기준 데이터 구조

**집계 레벨 KPI (현재 존재):**
```json
{
  "session_id": "d77-0-top_20-20251204001337",
  "round_trips_completed": 1659,
  "total_pnl_usd": 207375.00,
  "win_rate_pct": 100.0,
  "loop_latency_p99_ms": 0.12,
  "memory_usage_mb": 150,
  "cpu_usage_pct": 35
}
```

**없는 것 (Trade-level):**
- 각 round trip의 개별 스프레드
- 진입/퇴출 시점의 호가 스냅샷
- 체결 가격 (실제 또는 시뮬레이션)
- 거래 수량 대비 호가 잔량 비율

### 2.2 기존 코드 흐름 (D77-0 PAPER 모드)

```
TopNArbitrageRunner
    ↓
arbitrage/execution/executor.py (ExecutionResult)
    ↓
run_d77_0_topn_arbitrage_paper.py (metrics 집계)
    ↓
logs/d77-0-rm-ext/.../1h_top20_kpi.json (KPI 저장)
```

**기존 메트릭 수집:**
- `CrossExchangeMetrics`: RiskGuard 결정, Executor 결과 기록
- `run_d77_0_topn_arbitrage_paper.py`: Round trips, PnL, Win Rate 집계
- `ExecutionResult`: 거래 실행 결과 (symbol, trade_id, status, pnl)

**재사용 가능한 부분:**
- `ExecutionResult` 구조체 (trade_id, status, pnl)
- `CrossExchangeMetrics` 훅 패턴
- `run_d77_0_topn_arbitrage_paper.py`의 메트릭 집계 루프

---

## 3. TO-BE 아키텍처

### 3.1 Trade-level Logging Layer 위치

```
TopNArbitrageRunner
    ↓
arbitrage/execution/executor.py (ExecutionResult 생성)
    ↓
[NEW] arbitrage/logging/trade_logger.py
    ├─> TradeLogEntry (dataclass) - 스프레드/호가/체결 정보
    ├─> TradeLogger (interface) - 로깅 인터페이스
    └─> FileTradeLogger (implementation) - JSONL 파일 기반
    ↓
logs/d80-3/trades/{run_id}/trade_log.jsonl
```

**설계 원칙:**
1. **최소 침습:** 기존 executor/메트릭 코드는 최대한 건드리지 않음
2. **훅 기반:** Round trip 종료 시점에 훅만 추가
3. **확장 가능:** 향후 D80-4 (Fill Model), D81-x (Market Impact)에서 재사용 가능

### 3.2 통합 지점

**기존 코드 수정 최소화:**
- `run_d77_0_topn_arbitrage_paper.py`에서:
  - Round trip 종료 시점 (line 315-320 부근)에 `TradeLogger` 호출 추가
  - 기존 메트릭 집계 로직은 그대로 유지

**새로 추가할 모듈:**
- `arbitrage/logging/trade_logger.py` (신규 모듈)
- `scripts/analyze_d80_3_trade_logs.py` (분석 스크립트, 선택적)

---

## 4. 로그 스키마 정의

### 4.1 TradeLogEntry 구조

```python
@dataclass
class TradeLogEntry:
    """
    Trade-level 로그 엔트리
    
    각 round trip (또는 개별 레그)마다 하나씩 생성.
    D80-4, D81-x에서 슬리피지/Market Impact 분석에 활용.
    """
    
    # 기본 식별 정보
    timestamp: str                    # ISO 8601 format
    session_id: str                   # D77 run session ID
    trade_id: str                     # 고유 거래 ID
    universe_mode: str                # "TOP_20", "TOP_50", etc.
    symbol: str                       # "BTC/USDT", "ETH/KRW", etc.
    route_type: str                   # "cross_exchange", "triangular", etc.
    
    # 진입 정보 (Entry)
    entry_exchange_long: str          # 롱 포지션 거래소 (예: "upbit")
    entry_exchange_short: str         # 숏 포지션 거래소 (예: "binance")
    entry_timestamp: str              # 진입 시각
    entry_bid_upbit: float            # 진입 시 Upbit bid 가격
    entry_ask_upbit: float            # 진입 시 Upbit ask 가격
    entry_bid_binance: float          # 진입 시 Binance bid 가격
    entry_ask_binance: float          # 진입 시 Binance ask 가격
    entry_spread_bps: float           # 진입 시 스프레드 (basis points)
    entry_bid_volume_upbit: float     # 진입 시 Upbit bid 호가 잔량
    entry_ask_volume_binance: float   # 진입 시 Binance ask 호가 잔량
    
    # 퇴출 정보 (Exit)
    exit_timestamp: str               # 퇴출 시각
    exit_bid_upbit: float
    exit_ask_upbit: float
    exit_bid_binance: float
    exit_ask_binance: float
    exit_spread_bps: float
    exit_bid_volume_upbit: float
    exit_ask_volume_binance: float
    
    # 체결 정보
    order_quantity: float             # 주문 수량 (BTC, ETH 등)
    filled_quantity: float            # 실제 체결 수량 (현재 PAPER는 100%)
    fill_price_upbit: float           # Upbit 체결 가격 (PAPER: ask or bid)
    fill_price_binance: float         # Binance 체결 가격
    
    # 비용 정보
    fee_upbit_bps: float              # Upbit 수수료 (bps, 추정치)
    fee_binance_bps: float            # Binance 수수료 (bps, 추정치)
    estimated_slippage_bps: float     # 추정 슬리피지 (현재는 0, D80-4에서 모델링)
    
    # PnL 정보
    gross_pnl_usd: float              # 총 PnL (수수료 전)
    net_pnl_usd: float                # 순 PnL (수수료 후)
    trade_result: str                 # "win", "loss", "breakeven"
    
    # 메타 정보
    execution_latency_ms: float       # 진입→퇴출 소요 시간 (ms)
    risk_check_passed: bool           # RiskGuard 통과 여부
    notes: str                        # 추가 메모 (선택적)
```

### 4.2 JSON 포맷 예시

```json
{
  "timestamp": "2025-12-04T00:15:23.456Z",
  "session_id": "d77-0-top_20-20251204001337",
  "trade_id": "rt_001",
  "universe_mode": "TOP_20",
  "symbol": "BTC/USDT",
  "route_type": "cross_exchange",
  "entry_exchange_long": "upbit",
  "entry_exchange_short": "binance",
  "entry_timestamp": "2025-12-04T00:15:20.123Z",
  "entry_bid_upbit": 45000.5,
  "entry_ask_upbit": 45010.2,
  "entry_bid_binance": 44980.1,
  "entry_ask_binance": 44990.3,
  "entry_spread_bps": 45,
  "entry_bid_volume_upbit": 2.5,
  "entry_ask_volume_binance": 3.2,
  "exit_timestamp": "2025-12-04T00:15:23.456Z",
  "exit_bid_upbit": 45005.0,
  "exit_ask_upbit": 45015.0,
  "exit_bid_binance": 44985.0,
  "exit_ask_binance": 44995.0,
  "exit_spread_bps": 44,
  "exit_bid_volume_upbit": 2.3,
  "exit_ask_volume_binance": 3.0,
  "order_quantity": 0.1,
  "filled_quantity": 0.1,
  "fill_price_upbit": 45010.2,
  "fill_price_binance": 44990.3,
  "fee_upbit_bps": 5,
  "fee_binance_bps": 4,
  "estimated_slippage_bps": 0,
  "gross_pnl_usd": 19.90,
  "net_pnl_usd": 18.92,
  "trade_result": "win",
  "execution_latency_ms": 3333.0,
  "risk_check_passed": true,
  "notes": ""
}
```

---

## 5. 저장 구조

### 5.1 파일 경로 규칙

```
logs/d80-3/
  ├─ trades/
  │   ├─ run_20251204_001336/
  │   │   ├─ top20_trade_log.jsonl      # Top20 실행 로그
  │   │   └─ metadata.json               # Run 메타데이터
  │   └─ run_20251204_012509/
  │       ├─ top50_trade_log.jsonl      # Top50 실행 로그
  │       └─ metadata.json
  └─ analysis/                           # 분석 결과 (향후)
      └─ summary_20251204.json
```

### 5.2 JSONL 포맷

- **파일 형식:** `.jsonl` (JSON Lines)
- **각 줄:** 하나의 `TradeLogEntry` JSON 객체
- **장점:**
  - 스트리밍 쓰기 가능 (메모리 효율적)
  - 파싱 쉬움 (line-by-line)
  - 압축 가능 (gzip)

### 5.3 Metadata 파일

```json
{
  "run_id": "run_20251204_001336",
  "session_id": "d77-0-top_20-20251204001337",
  "universe_mode": "TOP_20",
  "start_time": "2025-12-04T00:13:36Z",
  "end_time": "2025-12-04T01:13:38Z",
  "duration_seconds": 3602,
  "total_trades_logged": 1659,
  "log_file": "top20_trade_log.jsonl",
  "version": "D80-3"
}
```

### 5.4 향후 PostgreSQL 확장

**테이블 스키마 (예정):**
```sql
CREATE TABLE d80_trade_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    trade_id VARCHAR(255) NOT NULL UNIQUE,
    symbol VARCHAR(50) NOT NULL,
    entry_spread_bps NUMERIC(10,2),
    exit_spread_bps NUMERIC(10,2),
    gross_pnl_usd NUMERIC(12,2),
    net_pnl_usd NUMERIC(12,2),
    trade_result VARCHAR(20),
    -- ... 기타 필드
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_session_id ON d80_trade_logs(session_id);
CREATE INDEX idx_timestamp ON d80_trade_logs(timestamp);
```

**현재 단계에서는:**
- 테이블 정의만 문서화
- 실제 구현은 D80-5 이후로 미룸

---

## 6. 구현 계획

### 6.1 새로 만들 모듈

**`arbitrage/logging/trade_logger.py`** (신규)

```python
# arbitrage/logging/trade_logger.py
"""
D80-3: Trade-level Logging Module

Trade-level 스프레드/유동성/체결 정보를 로깅하는 모듈.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
import json
from datetime import datetime


@dataclass
class TradeLogEntry:
    """Trade-level 로그 엔트리 (스키마는 위 섹션 4.1 참조)"""
    # ... (전체 필드 정의)
    pass


class TradeLogger:
    """
    Trade-level 로깅 인터페이스
    
    책임:
    - TradeLogEntry를 JSONL 파일로 저장
    - Run별 / Universe별 로그 파일 분리
    """
    
    def __init__(self, base_dir: Path, run_id: str, universe_mode: str):
        """
        Args:
            base_dir: 로그 베이스 디렉토리 (예: logs/d80-3/trades)
            run_id: 실행 ID (예: run_20251204_001336)
            universe_mode: Universe 모드 (예: TOP_20)
        """
        self.base_dir = base_dir
        self.run_id = run_id
        self.universe_mode = universe_mode
        self.log_file = self._init_log_file()
    
    def _init_log_file(self) -> Path:
        """로그 파일 초기화"""
        # logs/d80-3/trades/{run_id}/top20_trade_log.jsonl
        run_dir = self.base_dir / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        universe_label = self.universe_mode.lower().replace("_", "")
        log_file = run_dir / f"{universe_label}_trade_log.jsonl"
        return log_file
    
    def log_trade(self, entry: TradeLogEntry) -> None:
        """
        Trade 로그 기록
        
        Args:
            entry: TradeLogEntry 객체
        """
        with open(self.log_file, "a", encoding="utf-8") as f:
            json.dump(asdict(entry), f, ensure_ascii=False)
            f.write("\n")
    
    def save_metadata(self, metadata: dict) -> None:
        """
        Run 메타데이터 저장
        
        Args:
            metadata: 메타데이터 딕셔너리
        """
        metadata_file = self.log_file.parent / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
```

### 6.2 기존 코드 연동 지점

**`scripts/run_d77_0_topn_arbitrage_paper.py` 수정:**

```python
# 기존 코드 (line 315-320 부근)
self.exit_strategy.unregister_position(position_id)
self.metrics["exit_trades"] += 1
self.metrics["round_trips_completed"] += 1
self.metrics["total_trades"] += 1

# [NEW] D80-3 Trade-level 로깅 훅 추가
if hasattr(self, 'trade_logger') and self.trade_logger:
    trade_entry = self._create_trade_log_entry(
        position_id, current_tick, exit_pnl
    )
    self.trade_logger.log_trade(trade_entry)
```

**`_create_trade_log_entry()` 메서드 추가:**
- 현재 `ExecutionResult` 및 시장 데이터에서 필드 추출
- `TradeLogEntry` 객체 생성
- 스프레드/호가 계산 (현재는 mock 데이터 가능, D80-4에서 실제 반영)

### 6.3 엔진 수정 원칙

**DO:**
- ✅ Round trip 종료 시점에 훅 하나만 추가
- ✅ `TradeLogger`는 optional (--enable-trade-logging 플래그)
- ✅ 기존 메트릭 집계 로직 그대로 유지

**DON'T:**
- ❌ Executor, RiskGuard, PnLTracker 핵심 로직 수정
- ❌ PAPER 모드 체결 로직 변경
- ❌ 성능 크리티컬 경로에 무거운 로깅 추가

---

## 7. 테스트 전략

### 7.1 Unit Tests

**`tests/test_d80_3_trade_logger.py` (신규):**

```python
def test_trade_logger_init():
    """TradeLogger 초기화 테스트"""
    # 로그 디렉토리 생성 확인
    pass

def test_trade_logger_log_single_trade():
    """단일 트레이드 로깅 테스트"""
    # JSONL 파일 생성 및 내용 확인
    pass

def test_trade_logger_universe_separation():
    """Universe별 로그 분리 테스트"""
    # Top20/Top50 로그 파일 분리 확인
    pass

def test_trade_log_entry_serialization():
    """TradeLogEntry JSON 직렬화 테스트"""
    # asdict() 결과가 JSON으로 변환 가능한지 확인
    pass

def test_trade_logger_invalid_data():
    """잘못된 데이터 처리 테스트"""
    # 필수 필드 누락 시 에러 처리
    pass
```

### 7.2 스모크 PAPER 실행

**실행 명령:**
```bash
# Docker 스택 기동 (Redis/Postgres/Prometheus/Grafana)
python scripts/prepare_d77_0_rm_ext_env.py

# 3분 스모크 테스트 (Trade-level 로깅 활성화)
python scripts/run_d77_0_topn_arbitrage_paper.py \
  --data-source real \
  --topn-size 20 \
  --run-duration-seconds 180 \
  --monitoring-enabled \
  --enable-trade-logging \
  --trade-log-dir logs/d80-3/trades
```

**검증 항목:**
1. **로그 파일 생성:** `logs/d80-3/trades/{run_id}/top20_trade_log.jsonl` 존재
2. **로그 개수:** 3분간 최소 10~20개 이상의 트레이드 로그
3. **필드 완전성:** 각 로그 레코드에 스프레드/호가/PnL 필드 존재
4. **기존 테스트 회귀 없음:** D77/D80-2 관련 테스트 PASS
5. **성능 영향 최소:** CPU/Memory 3분 실행 기준 ±5% 이내

### 7.3 로그 내용 검증

**샘플 검증 스크립트:**
```python
# scripts/verify_d80_3_logs.py
import json
from pathlib import Path

def verify_trade_logs(log_file: Path):
    """Trade 로그 검증"""
    with open(log_file, 'r') as f:
        trades = [json.loads(line) for line in f]
    
    print(f"Total trades: {len(trades)}")
    
    # 필수 필드 체크
    required_fields = [
        "trade_id", "symbol", "entry_spread_bps", 
        "exit_spread_bps", "gross_pnl_usd", "net_pnl_usd"
    ]
    
    for i, trade in enumerate(trades[:5]):  # 처음 5개만 샘플 체크
        print(f"\nTrade {i+1}:")
        print(f"  ID: {trade['trade_id']}")
        print(f"  Symbol: {trade['symbol']}")
        print(f"  Entry Spread: {trade['entry_spread_bps']} bps")
        print(f"  Exit Spread: {trade['exit_spread_bps']} bps")
        print(f"  Gross PnL: ${trade['gross_pnl_usd']:.2f}")
        print(f"  Net PnL: ${trade['net_pnl_usd']:.2f}")
```

---

## 8. 향후 확장 포인트

### 8.1 D80-4: Realistic Fill/Slippage Model

**D80-3 데이터 활용:**
- `entry_spread_bps`, `exit_spread_bps` → 슬리피지 모델 입력
- `entry_bid_volume_upbit`, `entry_ask_volume_binance` → 부분 체결 시뮬레이션
- `order_quantity` vs 호가 잔량 비교 → 체결 가능성 평가

### 8.2 D81-x: Market Impact & Liquidity Analysis

**D80-3 데이터 활용:**
- 호가 잔량 히트맵 생성 (시간대별, 심볼별)
- 대량 주문 시 Market Impact 추정
- 최적 주문 크기 분석

### 8.3 D82-x: Long-term Validation

**D80-3 데이터 활용:**
- 12시간+ 실행 시 스프레드 변화 추이
- Edge 지속성 분석
- 시간대별 승률/PnL 패턴

---

## 9. Acceptance Criteria

### D80-3 PASS 조건

다음을 모두 만족해야 D80-3 COMPLETE:

1. ✅ **설계 문서:** `docs/D80_3_TRADE_LEVEL_LOGGING_DESIGN.md` 존재 + 내용 충실
2. ✅ **구현:**
   - `arbitrage/logging/trade_logger.py` 모듈 생성
   - `TradeLogEntry` dataclass 정의 (30+ 필드)
   - `TradeLogger` 클래스 구현 (JSONL 쓰기)
3. ✅ **엔진 연동:**
   - `run_d77_0_topn_arbitrage_paper.py`에 훅 추가
   - `--enable-trade-logging` 플래그 지원
4. ✅ **테스트:**
   - Unit tests: 5개 이상 (모두 PASS)
   - 스모크 PAPER 실행: 3~6분, Top20
5. ✅ **로그 생성:**
   - `logs/d80-3/trades/{run_id}/top20_trade_log.jsonl` 생성
   - 10~20개 이상 트레이드 로그
   - 각 레코드에 스프레드/호가/PnL 필드 존재
6. ✅ **회귀 없음:**
   - D77/D80-2 기존 테스트 PASS
   - 성능 영향 최소 (CPU/Memory ±5% 이내)
7. ✅ **문서화:**
   - `D_ROADMAP.md`: D80-3 ✅ COMPLETE
   - Git 커밋 완료

---

## 10. 제약사항 & 한계

### 10.1 현재 단계에서 하지 않는 것

❌ **Fill Model 구현 (D80-4):**
- 현재는 PAPER 모드 그대로 (100% 체결 가정)
- 부분 체결, 슬리피지 시뮬레이션은 D80-4에서

❌ **Market Impact 모델링 (D81-x):**
- 현재는 호가 잔량만 로깅
- Market Impact 계산은 D81-x에서

❌ **FX Provider 구현 (D80-5 이후):**
- D80_3_REAL_FX_PROVIDER_DESIGN.md는 별도 단계
- 이번 단계에서는 절대 구현하지 않음

❌ **PostgreSQL 통합 (향후):**
- 현재는 JSONL 파일만
- DB 통합은 필요 시 추후 진행

### 10.2 알려진 한계

1. **Mock 데이터 가능성:**
   - PAPER 모드에서 실제 호가창 API를 호출하지 않을 경우, 호가 필드가 추정치일 수 있음
   - 향후 Real Market API 연동 시 개선

2. **로깅 오버헤드:**
   - 파일 I/O 오버헤드 존재 (JSONL append)
   - 대규모 실행 시 성능 영향 모니터링 필요

3. **스프레드 계산 단순화:**
   - 현재는 단순 bid-ask 차이
   - Multi-level order book 고려 안 함 (D81-x에서)

---

## 11. 참고 문서

- [D80-2: Real Market Edge & Spread Reality Check](D80_2_REAL_MARKET_EDGE_REPORT.md)
- [D77-0-RM-EXT: Real Market 1h+ Extended PAPER Validation](D77_0_RM_EXT_REPORT.md)
- [D79-6: Cross-Exchange Metrics Collector](../arbitrage/monitoring/cross_exchange_metrics.py)

---

**작성일:** 2025-12-04  
**버전:** 1.0  
**다음 단계:** D80-3 구현 → 테스트 → COMPLETE
