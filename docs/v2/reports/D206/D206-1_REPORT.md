# D206-1: V1 Domain Model Integration + Registry De-Doping Report

**상태:** IN_PROGRESS  
**시작일:** 2026-01-16  
**Baseline:** 37a399c (D206-0 completed)  
**브랜치:** rescue/d205_15_multisymbol_scan

---

## 목적

V1 도메인 모델 3종을 V2에 통합 + ComponentRegistry 약한 DOPING 제거

**주요 목표:**
1. V1 domain models (OrderBookSnapshot, ArbitrageOpportunity, ArbitrageTrade) V2에서 재사용
2. Engine dict 기반 흉내 → 타입 기반으로 전환
3. ComponentRegistryChecker 텍스트 검색 제거 → SSOT 파싱 기반으로 강화
4. HFT 알파 모델 필드 예비 (OBI, Inventory Score)
5. Commercial UI용 직렬화 메서드 (`to_ui_dict()`)

---

## Step 1: Deep Scan 결과

### A) V1 Domain Models 위치 확인

**arbitrage/arbitrage_core.py (V1 레거시):**
- Line 35-42: `OrderBookSnapshot` dataclass
  - Fields: timestamp, best_bid_a, best_ask_a, best_bid_b, best_ask_b
  - ISO 8601 timestamp 사용
  
- Line 46-54: `ArbitrageOpportunity` dataclass
  - Fields: timestamp, side, spread_bps, gross_edge_bps, net_edge_bps, notional_usd
  - Side: Literal["LONG_A_SHORT_B", "LONG_B_SHORT_A"]
  
- Line 58-73: `ArbitrageTrade` dataclass
  - Fields: open_timestamp, close_timestamp, side, entry_spread_bps, exit_spread_bps, notional_usd, pnl_usd, pnl_bps, is_open, meta, exit_reason
  - Methods: `close()`, `to_dict()`

**arbitrage/exchanges/base.py (V1 거래소 계층):**
- Line 56: `OrderBookSnapshot` dataclass (다른 정의)
  - Fields: symbol, timestamp, bids, asks, exchange
  - V1 arbitrage_core.py와 중복 정의

**arbitrage/domain/ (V1 비즈니스 계층):**
- arb_route.py (11492 bytes): ArbRoute, RouteDirection, RouteScore
- fee_model.py (3024 bytes): FeeModel, FeeStructure
- market_spec.py (3232 bytes): MarketSpec, ExchangeSpec
- risk_guard.py (20918 bytes): FourTierRiskGuard
- entry_bps_profile.py (15976 bytes): EntryBpsProfile
- exit_strategy.py (11140 bytes): ExitStrategy

### B) V2 Dict 사용 현황

**arbitrage/v2/core/engine.py:**
- Line 92: `self._open_trades: List[Dict] = []` (dict 기반 거래 추적)
- Line 93: `self._last_snapshot: Optional[Dict] = None`
- Line 137-207: `_process_snapshot(snapshot: Dict) -> List[Dict]` (dict 반환)
- Line 241-266: `_detect_opportunities(market_data: Dict) -> List[Dict]` (dict 반환)
- Line 268-323: `_detect_single_opportunity(snapshot: Dict) -> Optional[Dict]` (dict 반환)
- Line 209: `_trade_to_result(trade: Dict) -> OrderResult` (dict 입력)

**dict 사용 지점 (타입 전환 필요):**
1. Snapshot: dict → OrderBookSnapshot
2. Opportunity: dict → ArbitrageOpportunity
3. Trade: List[Dict] → List[ArbitrageTrade]
4. Result conversion: dict → ArbitrageTrade → OrderResult

### C) ComponentRegistryChecker 약한 DOPING

**arbitrage/v2/core/component_registry_checker.py:**
- Line 68-94: `check_evidence_fields()` - EVIDENCE_FORMAT.md 존재만 확인 (내용 미검증)
- Line 96-120: `check_config_keys()` - paper_runner.py 텍스트 검색 (paper_runner_content 파라미터)

**문제점:**
1. Registry가 Runner 소스 텍스트를 직접 검색 (약한 DOPING)
2. Evidence schema 파싱 없음 (존재만 확인)
3. Config keys 검증이 텍스트 기반 (YAML 파싱 없음)

**해결 방향:**
1. EVIDENCE_FORMAT.md 파싱 → engine_report.json 스키마 필드 검증
2. config.yml YAML 파싱 → 필수 키 존재 검증
3. paper_runner_content 파라미터 제거 (텍스트 검색 제거)

### D) V1 Domain vs V2 Domain 충돌

**V2 domain 모듈 (arbitrage/v2/domain/):**
- break_even.py: BreakEvenParams
- fill_model.py: FillModelConfig
- order_intent.py: OrderIntent
- pnl_calculator.py: PnLCalculator

**V1 domain 모듈 (arbitrage/domain/):**
- OrderBookSnapshot, ArbitrageOpportunity, ArbitrageTrade는 arbitrage_core.py에 정의
- domain/ 폴더는 비즈니스 로직 (ArbRoute, FeeModel, RiskGuard)

**통합 전략:**
1. V1 arbitrage_core.py의 3종 모델을 arbitrage/v2/domain/으로 이동
2. 기존 V1 import 경로 유지 (하위 호환)
3. V2는 새 경로만 사용 (arbitrage.v2.domain.*)

---

## Step 2: Domain Model Implementation Plan

### 신규 파일 (3개)
1. `arbitrage/v2/domain/orderbook.py` - OrderBookSnapshot
2. `arbitrage/v2/domain/opportunity.py` - ArbitrageOpportunity
3. `arbitrage/v2/domain/trade.py` - ArbitrageTrade, TradeFill, TradeResult

### 요구사항
**공통:**
- dataclass + type hints
- 불변성 검증 (bids/asks 정렬, 음수 금지, timestamp 존재)
- JSON serialize/deserialize (to_dict/from_dict)
- `to_ui_dict()` 메서드 (Commercial UI 대응)

**HFT Readiness (Optional 필드):**
- OrderBookSnapshot: obi_score (Order Book Imbalance), depth_imbalance
- ArbitrageOpportunity: inventory_score, alpha_signal
- ArbitrageTrade: execution_quality_score, slippage_actual_bps

---

## 다음 단계 (Step 2 Implementation)

1. OrderBookSnapshot 구현 (arbitrage/v2/domain/orderbook.py)
2. ArbitrageOpportunity 구현 (arbitrage/v2/domain/opportunity.py)
3. ArbitrageTrade 구현 (arbitrage/v2/domain/trade.py)
4. Engine wiring (dict → dataclass 전환)
5. Registry De-Doping (텍스트 검색 제거)
6. Tests (roundtrip, invalid data, serialize)
7. Gates (Doctor/Fast/Regression)
8. Evidence Packaging
9. D_ROADMAP 업데이트
10. Git commit + push

---

**작성 시각:** 2026-01-16 21:20 UTC+09:00  
**Deep Scan 완료, Step 2 Implementation 진행 예정**
