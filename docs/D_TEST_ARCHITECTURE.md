# D_TEST_ARCHITECTURE – 테스트/캠페인 구조 정리

## 📌 개요

본 문서는 D65~D69 테스트 및 캠페인 스크립트의 구조를 정리하고,
**엔진 vs 스크립트 역할 분리**, **Config SSOT**, **재사용성**을 명시합니다.

---

## 1. 핵심 원칙

### 1.1 엔진 = 비즈니스 로직, 스크립트 = 캠페인 하네스

| 구분 | 역할 | 예시 |
|------|------|------|
| **엔진** | 거래 로직, PnL 계산, 포지션 관리, 리스크 가드 | `ArbitrageEngine`, `ArbitrageLiveRunner`, `RiskGuard` |
| **스크립트** | 시나리오 선택, 실행 시간 제어, 결과 수집, 보고서 생성 | `run_d65_campaigns.py`, `run_d68_tuning.py`, `run_d69_robustness.py` |

**금지 사항:**
- ❌ 스크립트에서 PnL/Winrate/포지션을 직접 계산
- ❌ 스크립트에 운영 설정과 다른 하드코딩 파라미터
- ❌ 엔진 우회하는 별도 계산 로직

**허용 사항:**
- ✅ 스크립트가 파라미터 조합/시나리오를 선택
- ✅ 스크립트가 실행 시간/루프 수 제어
- ✅ 스크립트가 엔진 메트릭을 수집하여 보고서 생성

### 1.2 Config SSOT (Single Source of Truth)

- 전략 파라미터: `ArbitrageConfig`
- Runner 설정: `ArbitrageLiveConfig`
- 리스크 한도: `RiskLimits`
- Robustness 시나리오: `tuning/robustness_scenarios.py`

**모든 테스트/캠페인은 이 Config들을 기반으로 실행됩니다.**

---

## 2. 공통 Paper 모드 실행 경로

**모든 스크립트(D65/D66/D67/D68/D69)가 동일한 엔진 경로를 사용합니다:**

```
1. ArbitrageConfig 생성
   └─ 전략 파라미터 (min_spread_bps, fee, slippage, position_size 등)
   
2. ArbitrageEngine 초기화
   └─ config 기반 엔진 생성
   
3. PaperExchange 생성
   └─ exchange_a (예: KRW-BTC)
   └─ exchange_b (예: BTCUSDT)
   └─ 초기 호가 설정 (OrderBookSnapshot)
   
4. ArbitrageLiveRunner 생성
   └─ engine, exchange_a, exchange_b
   └─ ArbitrageLiveConfig (mode=paper, paper_simulation_enabled=True)
   
5. runner._paper_campaign_id 설정
   └─ 캠페인 식별용 (C1, d68_tuning, d69_slippage_stress 등)
   
6. runner.run_once() 또는 runner.run_forever() 실행
   └─ build_snapshot()
   └─ process_snapshot()
   └─ execute_trades()
   
7. 메트릭 수집
   └─ runner._total_trades_opened
   └─ runner._total_trades_closed
   └─ runner._total_pnl_usd
   └─ runner._total_winning_trades
```

**중요:** 모든 PnL/Winrate/포지션 계산은 `ArbitrageLiveRunner` 내부에서 수행됩니다.

---

## 3. 스크립트별 역할 정의

### 3.1 D65 – TRADE_LIFECYCLE_HARDENING

**파일:** `scripts/run_d65_campaigns.py`

**역할:**
- C1/C2/C3 캠페인 패턴 선택
- 각 캠페인 2분간 실행
- Entry/Exit/PnL/Winrate 수집 및 검증

**엔진 경로:**
- ✅ `ArbitrageEngine` + `PaperExchange` + `ArbitrageLiveRunner`
- ✅ `runner.run_once()` 루프
- ✅ `runner._total_*` 메트릭 수집

**Config:**
- `ArbitrageConfig`: min_spread_bps=20.0, fee=10.0, slippage=5.0
- `ArbitrageLiveConfig`: paper_simulation_enabled=True, paper_spread_injection_interval=5

---

### 3.2 D66 – MULTISYMBOL_LIFECYCLE_FIX

**파일:** `scripts/run_d66_multisymbol_campaigns.py`

**역할:**
- M1/M2/M3 멀티심볼 캠페인 패턴 선택
- BTC/ETH 각각 2분간 실행
- 심볼별 독립 Entry/Exit/PnL/Winrate 수집

**엔진 경로:**
- ✅ 심볼별 `ArbitrageEngine` + `PaperExchange` + `ArbitrageLiveRunner`
- ✅ `runner.run_once_for_symbol(symbol)` 루프
- ✅ `runner._per_symbol_pnl[symbol]` 메트릭 수집

**Config:**
- 동일 (D65 기반)

---

### 3.3 D67 – MULTISYMBOL_PORTFOLIO_PNL_AGGREGATION

**파일:** `scripts/run_d67_portfolio_campaigns.py`

**역할:**
- P1/P2/P3 포트폴리오 캠페인 패턴 선택
- BTC/ETH 동시 2분간 실행
- 포트폴리오 Total PnL/Equity/Winrate 수집

**엔진 경로:**
- ✅ 심볼별 Runner + 포트폴리오 집계
- ✅ `runner._portfolio_total_pnl`, `runner._portfolio_equity` 메트릭 수집

**Config:**
- 동일 (D65/D66 기반)

---

### 3.4 D68 – PARAMETER_TUNING

**파일:** `scripts/run_d68_tuning.py`, `tuning/parameter_tuner.py`

**역할:**
- 파라미터 조합 생성 (Grid/Random Search)
- 각 조합마다 Paper 캠페인 실행 (120초)
- 결과를 PostgreSQL `tuning_results` 테이블에 저장
- 상위 N개 결과 정렬 및 보고서 생성

**엔진 경로:**
- ✅ `ParameterTuner._run_paper_campaign()`
  ```python
  def _run_paper_campaign(self, param_set: Dict[str, float]) -> Dict[str, Any]:
      # 1. PaperExchange 생성
      exchange_a, exchange_b = ...
      
      # 2. ArbitrageConfig 생성 (param_set 적용)
      engine_config = ArbitrageConfig(
          min_spread_bps=param_set.get('min_spread_bps', 30.0),
          taker_fee_a_bps=param_set.get('taker_fee_a_bps', 10.0),
          ...
      )
      engine = ArbitrageEngine(engine_config)
      
      # 3. Runner 생성 및 실행
      runner = ArbitrageLiveRunner(engine=engine, ...)
      runner.run_forever()
      
      # 4. 메트릭 수집
      return {
          'total_pnl': runner._total_pnl_usd,
          'total_entries': runner._total_trades_opened,
          ...
      }
  ```

**Config:**
- ✅ `param_set` → `ArbitrageConfig` (SSOT)
- ✅ `tuning_results` 테이블 (PostgreSQL SSOT)

**DB 연결:**
- ❗ **D68 Acceptance는 PostgreSQL 저장 필수**
- DB 연결 실패 시 테스트 FAIL

---

### 3.5 D69 – ROBUSTNESS_TEST

**파일:** `scripts/run_d69_robustness.py`, `tuning/robustness_scenarios.py`

**역할:**
- 6개 Robustness 시나리오 선택
  - SLIPPAGE_STRESS, FEE_SURGE, FLASH_CRASH, FLASH_SPIKE, NOISE_SATURATION, MULTISYMBOL_STAGGER
- 각 시나리오마다 Paper 캠페인 실행 (120초)
- 크래시, Entry/Exit, Entry 폭주, Portfolio DD 검증

**엔진 경로:**
- ✅ `setup_robustness_engine(scenario_name)`
  ```python
  def setup_robustness_engine(scenario_name: str) -> tuple:
      # 1. 기본 설정
      base_config = {
          'min_spread_bps': 20.0,
          'taker_fee_a_bps': 4.0,
          ...
      }
      
      # 2. 시나리오별 파라미터 오버라이드 (Phase 2에서 활성화)
      # if scenario_name == 'slippage_stress':
      #     base_config['slippage_bps'] = 80.0
      
      # 3. ArbitrageConfig 생성
      config = ArbitrageConfig(**base_config)
      engine = ArbitrageEngine(config)
      
      # 4. PaperExchange 생성
      exchange_a, exchange_b = ...
      
      return engine, exchange_a, exchange_b
  ```

- ✅ `run_robustness_scenario()`
  ```python
  def run_robustness_scenario(scenario_name: str, duration_seconds: int) -> dict:
      # 1. Engine/Exchange 설정
      engine, exchange_a, exchange_b = setup_robustness_engine(scenario_name)
      
      # 2. Runner 생성
      runner = ArbitrageLiveRunner(...)
      runner._paper_campaign_id = f'd69_{scenario_name}'
      
      # 3. Paper 캠페인 실행
      while time.time() < end_time:
          runner.run_once()
      
      # 4. 메트릭 수집
      return {
          'entries': runner._total_trades_opened,
          'exits': runner._total_trades_closed,
          'pnl': runner._total_pnl_usd,
          ...
      }
  ```

**Config:**
- ✅ `tuning/robustness_scenarios.py` (시나리오 정의)
- ✅ `ArbitrageConfig` (시나리오별 파라미터)

**Phase 1 vs Phase 2:**
- **Phase 1 (현재):** 기본 설정으로 인프라 검증, Robustness 주입 비활성
- **Phase 2 (향후):** 극단 파라미터 주입 활성화 (slippage 80bps, fee 0.15% 등)

---

## 4. 메트릭 수집 방식

### 4.1 현재 방식 (Private 변수 직접 접근)

```python
# 모든 스크립트에서 사용
metrics = {
    'total_pnl': runner._total_pnl_usd,  # private variable
    'total_entries': runner._total_trades_opened,
    'total_exits': runner._total_trades_closed,
    'winning_trades': runner._total_winning_trades,
}
```

**장점:**
- ✅ 간단하고 직접적

**단점:**
- ❌ Runner 내부 구현에 강하게 결합
- ❌ Runner 리팩토링 시 모든 스크립트 수정 필요

### 4.2 개선 방안 (공개 메서드)

**옵션 1: `get_session_summary()` 메서드 추가**
```python
# arbitrage/live_runner.py
def get_session_summary(self) -> Dict[str, Any]:
    """세션 요약 메트릭 반환 (공개 인터페이스)"""
    return {
        'total_entries': self._total_trades_opened,
        'total_exits': self._total_trades_closed,
        'total_pnl': self._total_pnl_usd,
        'winning_trades': self._total_winning_trades,
        'winrate_pct': (
            (self._total_winning_trades / self._total_trades_closed * 100.0)
            if self._total_trades_closed > 0
            else 0.0
        ),
    }

# 스크립트에서 사용
metrics = runner.get_session_summary()
```

**옵션 2: 공통 유틸리티 함수**
```python
# arbitrage/test_utils.py (현재 구현됨)
def collect_runner_metrics(runner: ArbitrageLiveRunner) -> Dict[str, Any]:
    """Runner로부터 메트릭 수집"""
    return {
        'total_pnl': getattr(runner, '_total_pnl_usd', 0.0),
        ...
    }

# 스크립트에서 사용
from arbitrage.test_utils import collect_runner_metrics
metrics = collect_runner_metrics(runner)
```

**권장:** 옵션 1 (공개 메서드)을 장기적으로 도입, 옵션 2는 임시 해결책

---

## 5. 공통 유틸리티 (`arbitrage/test_utils.py`)

### 5.1 제공 함수

#### `create_default_paper_exchanges()`
```python
exchange_a, exchange_b = create_default_paper_exchanges(
    symbol_a="KRW-BTC",
    symbol_b="BTCUSDT",
    price_a=100000.0,
    price_b=40000.0
)
```

#### `create_paper_runner()`
```python
runner = create_paper_runner(
    engine=engine,
    symbol_a="KRW-BTC",
    symbol_b="BTCUSDT",
    campaign_id="C1",
    duration_seconds=120
)
```

#### `collect_runner_metrics()`
```python
metrics = collect_runner_metrics(runner)
# {'total_entries': 40, 'total_exits': 57, 'total_pnl': 21.52, ...}
```

### 5.2 사용 권장

**Before (중복 코드):**
```python
# 각 스크립트에서 반복
exchange_a = PaperExchange()
snapshot_a = OrderBookSnapshot(...)
exchange_a.set_orderbook("KRW-BTC", snapshot_a)
...
```

**After (유틸리티 사용):**
```python
from arbitrage.test_utils import create_default_paper_exchanges, create_paper_runner

exchange_a, exchange_b = create_default_paper_exchanges()
runner = create_paper_runner(engine, campaign_id="C1")
```

---

## 6. Acceptance Criteria 검증

### 6.1 D65~D67: Trade Lifecycle

**검증 항목:**
- ✅ Entry/Exit 정상 발생
- ✅ PnL/Winrate 계산 정상
- ✅ 심볼별 독립 추적 (D66)
- ✅ 포트폴리오 집계 (D67)

**엔진 경로 확인:**
- ✅ 모두 `ArbitrageLiveRunner` 사용
- ✅ 스크립트는 캠페인 하네스 역할만

### 6.2 D68: Parameter Tuning

**검증 항목:**
- ✅ 파라미터 조합 ≥ 3개 실행
- ✅ PostgreSQL 저장 (필수)
- ✅ 크래시 없이 정상 종료

**엔진 경로 확인:**
- ✅ `ParameterTuner._run_paper_campaign()`이 실제 Paper 엔진 사용
- ✅ `param_set` → `ArbitrageConfig` (SSOT)

### 6.3 D69: Robustness Test

**검증 항목:**
- ✅ 6개 시나리오 정상 종료
- ✅ 크래시 없음
- ✅ Entry/Exit/PnL 계산 정상

**엔진 경로 확인:**
- ✅ `run_robustness_scenario()`이 실제 Paper 엔진 사용
- ✅ 시나리오 설정 → `ArbitrageConfig` (SSOT)

---

## 7. Phase 2 개선 계획

### 7.1 D69 Robustness 주입 활성화

**현재 상태 (Phase 1):**
```python
# scripts/run_d69_robustness.py:62-70
# D69 Phase 1: 기본 설정으로 인프라 검증 (Robustness 주입 없이)
# 시나리오별 파라미터 오버라이드는 추후 추가
# if scenario_name == 'slippage_stress':
#     base_config['slippage_bps'] = 80.0  # 극단적 슬리피지
```

**Phase 2 계획:**
1. `setup_robustness_engine()`에서 시나리오별 파라미터 활성화
2. `RobustnessInjector`를 `ArbitrageLiveRunner`와 연결
3. 실제 극단 값으로 테스트 (slippage 80bps, fee 0.15%)

### 7.2 메트릭 수집 공개 메서드 추가

**현재 상태:**
- Private 변수 직접 접근 (`runner._total_pnl_usd`)

**Phase 2 계획:**
- `ArbitrageLiveRunner.get_session_summary()` 메서드 추가
- 모든 스크립트를 공개 메서드로 변경

### 7.3 공통 유틸리티 확대

**현재 상태:**
- `arbitrage/test_utils.py` (기본 함수만)

**Phase 2 계획:**
- 캠페인 패턴별 헬퍼 함수 추가
- 시나리오 검증 유틸리티 추가
- DB 저장/조회 유틸리티 추가

---

## 8. 요약

### 8.1 핵심 원칙 재확인

1. **엔진 = 비즈니스 로직, 스크립트 = 캠페인 하네스**
2. **Config = SSOT** (ArbitrageConfig, ArbitrageLiveConfig, RiskLimits)
3. **모든 테스트는 동일한 Paper 엔진 경로 사용**
4. **스크립트는 엔진 우회 금지**

### 8.2 현재 상태 (✅)

- ✅ D65~D69 모두 올바른 엔진 경로 사용
- ✅ 스크립트 역할이 명확함 (캠페인 하네스)
- ✅ Config SSOT 유지

### 8.3 개선 진행 중 (🔄)

- 🔄 공통 유틸리티 모듈 생성 (`arbitrage/test_utils.py`)
- 🔄 메트릭 수집 방식 개선 (공개 메서드)
- 🔄 D69 Robustness 주입 활성화 (Phase 2)

### 8.4 향후 계획 (📋)

- 📋 `ArbitrageLiveRunner.get_session_summary()` 메서드 추가
- 📋 D69 Phase 2: 극단 파라미터 주입 로직 통합
- 📋 캠페인 패턴별 헬퍼 함수 확대

---

**작성일:** 2025-11-20  
**작성자:** AI (Claude 4.5 Thinking)  
**버전:** 1.0
