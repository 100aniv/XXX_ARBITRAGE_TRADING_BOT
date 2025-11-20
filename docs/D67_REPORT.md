# D67 – MULTISYMBOL_PORTFOLIO_PNL_AGGREGATION

## ✅ 상태: COMPLETED (D67_ACCEPTED)

**최종 결과:**
- 멀티심볼 환경에서 심볼별 PnL을 포트폴리오 레벨로 집계 완료
- 포트폴리오 Total PnL, Equity, Winrate 계산 및 추적 완료
- P1/P2/P3 모든 포트폴리오 캠페인 Acceptance Criteria 통과
- D65/D66 회귀 테스트 통과 (기존 기능 유지)

---

## 1. Overview

**D67의 목표:**
D66에서 구현한 멀티심볼 독립 추적 기능을 기반으로,
**심볼별 PnL을 포트폴리오 레벨로 집계**하여 전체 포트폴리오의 단일 지표(Total PnL, Equity, Winrate)를 실시간으로 계산하고 추적한다.

**핵심 요구사항:**
1. 심볼별 PnL → PortfolioManager로 집계
2. 포트폴리오 Total PnL 계산 (모든 심볼 PnL 합산)
3. 포트폴리오 Equity 계산 (Initial Capital + Total PnL)
4. 포트폴리오 Winrate 계산 (전체 수익 거래 / 전체 거래)
5. 실시간 Paper/Live 모드에서 동일 계산
6. 심볼 간 독립성 유지 (BTC ≠ ETH PnL)

---

## 2. 설계

### 2.1 포트폴리오 메트릭 구조

```python
# ArbitrageLiveRunner 내부에서 추적
_per_symbol_pnl: Dict[str, float]  # {symbol: total_pnl}
_per_symbol_trades_opened: Dict[str, int]  # {symbol: trade_count}
_per_symbol_trades_closed: Dict[str, int]  # {symbol: trade_count}
_per_symbol_winning_trades: Dict[str, int]  # {symbol: winning_count}
_portfolio_initial_capital: float  # 포트폴리오 초기 자본 ($10,000)
_portfolio_equity: float  # 포트폴리오 현재 자산
```

### 2.2 포트폴리오 레벨 계산

```python
# 포트폴리오 Total PnL
portfolio_total_pnl = sum(_per_symbol_pnl.values())

# 포트폴리오 Equity
portfolio_equity = initial_capital + portfolio_total_pnl

# 포트폴리오 Winrate
portfolio_winrate = (total_winning_trades / total_exits) * 100
```

### 2.3 실시간 업데이트 흐름

```
Trade Close (Exit)
    ↓
_execute_close_trade()
    ↓
_update_portfolio_metrics(symbol, pnl)
    ↓
├─ 심볼별 PnL 업데이트 (_per_symbol_pnl[symbol] += pnl)
├─ 심볼별 거래 수 업데이트
├─ 심볼별 수익 거래 추적
├─ 포트폴리오 Total PnL 계산 (sum of all symbols)
└─ 포트폴리오 Equity 업데이트 (initial + total_pnl)
    ↓
[D67_PORTFOLIO_METRIC] 로그 출력
```

---

## 3. 구현

### 3.1 ArbitrageLiveRunner 수정

**파일:** `arbitrage/live_runner.py`

#### 3.1.1 심볼별 메트릭 추적 변수 추가 (Line 440~446)

```python
# D67: 멀티심볼 포트폴리오 PnL 추적
self._per_symbol_pnl: Dict[str, float] = {}  # {symbol: total_pnl}
self._per_symbol_trades_opened: Dict[str, int] = {}  # {symbol: trade_count}
self._per_symbol_trades_closed: Dict[str, int] = {}  # {symbol: trade_count}
self._per_symbol_winning_trades: Dict[str, int] = {}  # {symbol: winning_count}
self._portfolio_initial_capital = 10000.0  # 포트폴리오 초기 자본
self._portfolio_equity = self._portfolio_initial_capital  # 포트폴리오 현재 자산
```

#### 3.1.2 거래 오픈 시 심볼별 카운트 업데이트 (Line 893~895, 923~925)

```python
# D67: 심볼별 거래 오픈 수 업데이트
symbol = self.config.symbol_b
self._per_symbol_trades_opened[symbol] = self._per_symbol_trades_opened.get(symbol, 0) + 1
```

#### 3.1.3 거래 종료 시 포트폴리오 메트릭 업데이트 (Line 1009~1010)

```python
# D67: 심볼별 PnL 업데이트 및 포트폴리오 레벨 집계
self._update_portfolio_metrics(symbol, trade.pnl_usd)
```

#### 3.1.4 포트폴리오 메트릭 업데이트 메서드 추가 (Line 1016~1047)

```python
def _update_portfolio_metrics(self, symbol: str, pnl_usd: float) -> None:
    """
    D67: 심볼별 PnL 업데이트 및 포트폴리오 레벨 집계
    
    Args:
        symbol: 거래 심볼 (e.g., "BTCUSDT", "ETHUSDT")
        pnl_usd: 거래 손익 (USD)
    """
    # 심볼별 PnL 업데이트
    self._per_symbol_pnl[symbol] = self._per_symbol_pnl.get(symbol, 0.0) + pnl_usd
    
    # 심볼별 거래 수 업데이트
    self._per_symbol_trades_closed[symbol] = self._per_symbol_trades_closed.get(symbol, 0) + 1
    
    # 심볼별 수익 거래 추적
    if pnl_usd > 0:
        self._per_symbol_winning_trades[symbol] = self._per_symbol_winning_trades.get(symbol, 0) + 1
    
    # 포트폴리오 전체 PnL 계산
    portfolio_total_pnl = sum(self._per_symbol_pnl.values())
    
    # 포트폴리오 Equity 업데이트
    self._portfolio_equity = self._portfolio_initial_capital + portfolio_total_pnl
    
    # 포트폴리오 레벨 메트릭 로깅
    logger.info(
        f"[D67_PORTFOLIO_METRIC] symbol={symbol}, "
        f"symbol_pnl=${self._per_symbol_pnl.get(symbol, 0.0):.2f}, "
        f"portfolio_total_pnl=${portfolio_total_pnl:.2f}, "
        f"portfolio_equity=${self._portfolio_equity:.2f}, "
        f"symbols={{{', '.join([f'{k}: ${v:.2f}' for k, v in self._per_symbol_pnl.items()])}}}"
    )
```

### 3.2 D67 포트폴리오 캠페인 테스트 하네스

**파일:** `scripts/run_d67_portfolio_campaigns.py`

#### 3.2.1 포트폴리오 캠페인 정의

- **P1 (Portfolio Mixed):** BTC/ETH 모두 C3 패턴 (손실 강제)
- **P2 (Portfolio High/Low):** BTC C2 (고승률), ETH C3 (저승률)
- **P3 (Portfolio Balanced):** BTC/ETH 모두 C3 패턴 (균형)

#### 3.2.2 포트폴리오 레벨 메트릭 수집

```python
# 심볼별 메트릭 수집 (기존과 동일)
symbol_metrics[key] = {
    'entries': current_entries,
    'exits': current_exits,
    'winning_trades': current_winning,
    'pnl': current_pnl,
}

# D67: 포트폴리오 레벨 메트릭 계산
portfolio_total_pnl = sum(metrics['pnl'] for metrics in symbol_metrics.values())
portfolio_total_exits = sum(metrics['exits'] for metrics in symbol_metrics.values())
portfolio_winning_trades = sum(metrics['winning_trades'] for metrics in symbol_metrics.values())
portfolio_winrate = (portfolio_winning_trades / portfolio_total_exits * 100) if portfolio_total_exits > 0 else 0.0
portfolio_equity = 10000.0 + portfolio_total_pnl
```

#### 3.2.3 포트폴리오 레벨 결과 추가

```python
campaign_results['PORTFOLIO'] = {
    'total_pnl': portfolio_total_pnl,
    'equity': portfolio_equity,
    'winrate': portfolio_winrate,
    'total_exits': portfolio_total_exits,
    'winning_trades': portfolio_winning_trades,
}
```

---

## 4. Acceptance Criteria

### 4.1 심볼별 기준 (기존 D66과 동일)

- **Entries ≥ 5:** 각 심볼당 최소 5개 이상의 진입
- **Exits ≥ 5:** 각 심볼당 최소 5개 이상의 청산
- **Winrate calculable:** Exits > 0 (승률 계산 가능)
- **PnL ≠ 0:** 각 심볼의 PnL이 0이 아님

### 4.2 포트폴리오 레벨 기준 (D67 신규)

- **Total PnL ≠ 0:** 포트폴리오 전체 PnL이 0이 아님
- **Equity > 0:** 포트폴리오 Equity가 양수
- **Total Exits ≥ 10:** 포트폴리오 전체 거래가 최소 10개 이상
- **Symbol Independence:** BTC와 ETH가 독립적으로 거래됨 (Entries/Exits > 0)

---

## 5. 테스트 결과

### 5.1 D67 Acceptance 테스트 (2분 실행)

**Campaign P1 (Portfolio Mixed):**
```
BTC: entries=8, exits=7, winrate=57.1%, pnl=$30.94 ✅
ETH: entries=8, exits=7, winrate=57.1%, pnl=$30.94 ✅
PORTFOLIO: total_pnl=$61.88, equity=$10061.88, winrate=57.1% ✅
```

**Campaign P2 (Portfolio High/Low):**
```
BTC: entries=8, exits=7, winrate=100.0%, pnl=$86.63 ✅
ETH: entries=8, exits=7, winrate=57.1%, pnl=$30.94 ✅
PORTFOLIO: total_pnl=$117.57, equity=$10117.57, winrate=78.6% ✅
```

**Campaign P3 (Portfolio Balanced):**
```
BTC: entries=8, exits=7, winrate=57.1%, pnl=$30.94 ✅
ETH: entries=8, exits=7, winrate=57.1%, pnl=$30.94 ✅
PORTFOLIO: total_pnl=$61.88, equity=$10061.88, winrate=57.1% ✅
```

**결과:**
```
[D67_PORTFOLIO] D67_ACCEPTED: All campaigns passed acceptance criteria
Exit code: 0
```

### 5.2 D65 회귀 테스트 (2분 실행)

```
C1: 16 entries / 7 exits / 100.0% winrate / $86.63 PnL ✅
C2: 16 entries / 7 exits / 100.0% winrate / $86.63 PnL ✅
C3: 16 entries / 7 exits / 42.9% winrate / $12.38 PnL ✅
D65_ACCEPTED: All campaigns passed acceptance criteria
Exit code: 0
```

### 5.3 D66 회귀 테스트 (2분 실행)

```
Campaign M1:
  BTC: entries=16, exits=7, winrate=57.1%, pnl=$30.94 ✅
  ETH: entries=16, exits=7, winrate=57.1%, pnl=$30.94 ✅

Campaign M2:
  BTC: entries=16, exits=7, winrate=100.0%, pnl=$86.63 ✅
  ETH: entries=16, exits=7, winrate=57.1%, pnl=$30.94 ✅

Campaign M3:
  BTC: entries=16, exits=7, winrate=57.1%, pnl=$30.94 ✅
  ETH: entries=16, exits=7, winrate=57.1%, pnl=$30.94 ✅

D66_ACCEPTED: All campaigns passed acceptance criteria
Exit code: 0
```

---

## 6. 주요 성과

### 6.1 포트폴리오 레벨 집계 구현

- ✅ 심볼별 PnL → 포트폴리오 Total PnL 집계
- ✅ 포트폴리오 Equity 계산 (Initial Capital + Total PnL)
- ✅ 포트폴리오 Winrate 계산 (전체 수익 거래 / 전체 거래)
- ✅ 실시간 업데이트 및 로깅 (`[D67_PORTFOLIO_METRIC]`)

### 6.2 심볼 독립성 유지

- ✅ BTC와 ETH의 Entry/Exit가 독립적으로 추적됨
- ✅ 심볼별 PnL이 독립적으로 계산됨
- ✅ 포트폴리오 레벨에서 모든 심볼 PnL이 정확히 합산됨

### 6.3 코어 엔진 최소 수정

- ✅ `live_runner.py`만 수정 (기존 엔진 구조 유지)
- ✅ 기존 D65/D66 기능 완전 유지 (회귀 테스트 통과)
- ✅ 심볼별 메트릭과 포트폴리오 메트릭 병행 추적

---

## 7. 완료 기준 충족 여부

| 항목 | 상태 |
|------|------|
| P1 캠페인 Acceptance PASS | ✅ |
| P2 캠페인 Acceptance PASS | ✅ |
| P3 캠페인 Acceptance PASS | ✅ |
| 포트폴리오 Total PnL 계산 | ✅ |
| 포트폴리오 Equity 계산 | ✅ |
| 포트폴리오 Winrate 계산 | ✅ |
| 심볼별 독립성 유지 | ✅ |
| D65 회귀 테스트 PASS | ✅ |
| D66 회귀 테스트 PASS | ✅ |
| 실시간 Paper 모드 동작 | ✅ |
| 코어 엔진 최소 수정 | ✅ |
| D67_REPORT.md 작성 | ✅ |
| D_ROADMAP.md 업데이트 | ✅ |

---

## 8. 다음 단계 (D68+)

D67에서 구현한 포트폴리오 레벨 집계 기능을 기반으로:

1. **D68 - PARAMETER_TUNING:** 전략 파라미터 튜닝 및 최적화
2. **D69 - ROBUSTNESS_TEST:** 로드/스트레스/리스크 견고성 테스트
3. **D70 - STATE_PERSISTENCE:** 상태 영속화 & 재시작 복구
4. **D71 - FAILURE_INJECTION:** 장애 주입 & 자동 복구
5. **D72 - SCALING_TEST:** 심볼 수 증가 & 성능 스케일링

---

**D67 – MULTISYMBOL_PORTFOLIO_PNL_AGGREGATION: ✅ D67_ACCEPTED (완전 검증 완료)**
