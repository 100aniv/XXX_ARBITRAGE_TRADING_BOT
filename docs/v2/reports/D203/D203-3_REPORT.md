# D203-3 Report: Opportunity → OrderIntent Bridge

**작성일:** 2025-12-30 02:00 (UTC+9)  
**상태:** ✅ DONE  
**커밋:** `d77f97e`  
**BASE_SHA:** `228eef2` → `d77f97e`  
**브랜치:** rescue/d99_15_fullreg_zero_fail

---

## 📋 목표 및 범위

### D203-3: Opportunity → OrderIntent Bridge (얇은 어댑터)
`OpportunityCandidate`를 2개의 `OrderIntent`(BUY + SELL)로 변환하는 얇은 어댑터 구현.

**목표:**
- OpportunityCandidate → OrderIntent 변환 로직 SSOT화 ✅
- Direction 기반 매수/매도 거래소 자동 배정 ✅
- Unprofitable 기회 필터링 (빈 리스트 반환) ✅
- SSOT Hygiene Fix (커밋 표기, 리포트 분리) ✅

**Note:** 
- D203-1 (Break-even), D203-2 (Opportunity Detector)의 자연스러운 확장
- Engine-centric flow와 분리된 테스트 가능한 얇은 모듈
- Reuse-First 원칙 100% 준수 (OrderIntent, OpportunityCandidate, BreakEvenParams)

---

## ✅ 완료 항목

### 1. D203-3 Intent Builder 구현
**파일:** `arbitrage/v2/opportunity/intent_builder.py` (신규, 225 lines)

**함수 (SSOT):**

#### `build_candidate(...) -> Optional[OpportunityCandidate]`
- 2개 거래소 가격 → OpportunityCandidate 생성
- 내부적으로 `detect_candidates()` 호출 (재사용)
- Invalid price → None 반환

#### `candidate_to_order_intents(...) -> List[OrderIntent]`
- OpportunityCandidate → 2개 OrderIntent (BUY + SELL)
- **Policy (SSOT):**
  - `unprofitable` (edge_bps <= 0) → 빈 리스트 (주문 생성 금지)
  - `direction == NONE` → 빈 리스트
  - `direction == BUY_A_SELL_B` → [BUY(exchange_a), SELL(exchange_b)]
  - `direction == BUY_B_SELL_A` → [BUY(exchange_b), SELL(exchange_a)]
- MARKET/LIMIT 주문 타입 지원
- Limit price fallback to market price

#### `build_and_convert(...) -> List[OrderIntent]`
- `build_candidate()` + `candidate_to_order_intents()` 통합 편의 함수

**Reuse-First:**
- ✅ OrderIntent (arbitrage/v2/core/order_intent.py) - import 재사용
- ✅ OpportunityCandidate (arbitrage/v2/opportunity/detector.py) - import 재사용
- ✅ BreakEvenParams (arbitrage/v2/domain/break_even.py) - import 재사용

---

### 2. D203-3 테스트 작성
**파일:** `tests/test_d203_3_opportunity_to_order_intent.py` (신규, 383 lines)

**테스트:** 9/9 PASS (0.15s)
1. ✅ Direction BUY_A_SELL_B → BUY(upbit), SELL(binance)
2. ✅ Direction BUY_B_SELL_A → BUY(binance), SELL(upbit)
3. ✅ Unprofitable (Edge<=0) → 빈 리스트 (intent 생성 금지)
4. ✅ Direction NONE → 빈 리스트
5. ✅ MARKET order validation (BUY: quote_amount, SELL: base_qty)
6. ✅ LIMIT order validation (limit_price 필수)
7. ✅ Invalid price → None candidate → 빈 리스트
8. ✅ build_and_convert() 편의 함수
9. ✅ build_and_convert() unprofitable → 빈 리스트

---

### 3. SSOT Hygiene Fix (Step 0.5)
**목표:** D203-1/D203-2 커밋 표기 및 리포트 정리

#### 3.1 D_ROADMAP.md 수정
- D203-1 커밋: `[작업 중]` → `228eef2` ✅
- D203-2 커밋: `[작업 중]` → `228eef2` ✅
- D203-2 리포트 경로: `D203-1_REPORT.md` → `D203-2_REPORT.md` (분리) ✅
- D203-2 Note: Backtest gate는 D204-2로 이동 완료 ✅

#### 3.2 D203-1_REPORT.md 수정
- 제목: `D203-1 (+D203-2) Report` → `D203-1 Report: Break-even Threshold (SSOT)` ✅
- 커밋: `[작업 중]` → `228eef2` ✅
- D203-2 섹션 분리: `D203-2_REPORT.md` 참조로 변경 ✅

#### 3.3 D203-2_REPORT.md 생성
- D203-2 전용 리포트 작성 (Opportunity Detector v1) ✅
- D203-1과 분리하여 독립 문서화 ✅
- Tech-Debt 섹션 추가 (Spread 정의 비대칭, Direction 기반 Break-even) ✅

---

## 🧪 Gate 검증 결과

| Gate | 상태 | 테스트 | 시간 | 결과 |
|------|------|--------|------|------|
| Doctor | ✅ PASS | 2521 collected (+9) | < 1s | Import/collect OK |
| Fast | ✅ PASS | 76/76 (+9) | 0.73s | V2 core tests |
| Regression | ✅ PASS | 104/104 (+9) | 0.90s | D98 + V2 combined |

**Evidence:** `logs/evidence/d203_3_20251230_0131_228eef2/gate_results.md`

**신규 테스트:**
- test_d203_3_opportunity_to_order_intent.py: 9/9 PASS (0.15s)

**누적 테스트 (D203-1 + D203-2 + D203-3):**
- D203-1: 9 tests
- D203-2: 6 tests
- D203-3: 9 tests
- **Total: 24 tests** (100% PASS)

---

## 📊 Scan-First 결과

**V2 재사용 모듈:**
| 기능 | 기존 파일 | D203-3 적용 | 재사용 방식 | 결정 |
|------|----------|------------|-----------|------|
| OrderIntent | `arbitrage/v2/core/order_intent.py` | ✅ YES | import 재사용 | **KEEP (필수)** |
| OpportunityCandidate | `arbitrage/v2/opportunity/detector.py` | ✅ YES | import 재사용 | **KEEP (필수)** |
| BreakEvenParams | `arbitrage/v2/domain/break_even.py` | ✅ YES | import 재사용 | **KEEP (필수)** |
| Engine | `arbitrage/v2/core/engine.py` | ❌ NO | 참조만 (얇은 모듈 분리) | **REFERENCE** |
| MarketData | `arbitrage/v2/marketdata/` | ❌ NO | 필요 없음 (가격 2개 입력) | **SKIP** |

**중복 모듈:** 0개 ✅

**Evidence:** `logs/evidence/d203_3_20251230_0131_228eef2/scan_reuse_map.md`

---

## 📝 변경 파일 목록

### 신규 파일 (2개)
1. **arbitrage/v2/opportunity/intent_builder.py** - Intent bridge (225 lines)
   - `build_candidate()` - OpportunityCandidate 생성
   - `candidate_to_order_intents()` - OrderIntent 변환
   - `build_and_convert()` - 통합 편의 함수
   
2. **tests/test_d203_3_opportunity_to_order_intent.py** - 테스트 (383 lines)
   - 9개 케이스 (Direction, Unprofitable, MARKET/LIMIT, Invalid price)

### 수정 파일 (2개)
1. **D_ROADMAP.md**
   - D203-1/D203-2 커밋 표기 수정 (`228eef2`)
   - D203-2 리포트 경로 분리
   - D203-2 Note 명확화 (Backtest gate → D204-2)

2. **docs/v2/reports/D203/D203-1_REPORT.md**
   - D203-1만 포함하도록 수정 (D203-2 섹션 분리)
   - 커밋 표기 수정 (`228eef2`)
   - 신규 파일 목록 정리

### 신규 문서 (1개)
3. **docs/v2/reports/D203/D203-2_REPORT.md** - D203-2 독립 리포트 (149 lines)
   - Opportunity Detector v1 전용 문서
   - Tech-Debt 명시 (Spread 정의 비대칭, Direction 기반 Break-even)

---

## 🔍 Tech-Debt / 남은 일

**없음** - D203-3는 완전 완료.

**다음 단계:**
- D204-1: DB ledger 기록 (orders/fills/trades) "필수"
- D204-2: Paper Execution Gate (20m → 1h → 3~12h 계단식)
- D205: User Facing Reporting (PnL/DD/winrate)

---

## 📚 참조

- **SSOT:** `D_ROADMAP.md` (line 2693-2764)
- **D203-1:** `docs/v2/reports/D203/D203-1_REPORT.md`
- **D203-2:** `docs/v2/reports/D203/D203-2_REPORT.md`
- **OrderIntent:** `arbitrage/v2/core/order_intent.py`
- **OpportunityCandidate:** `arbitrage/v2/opportunity/detector.py`
- **BreakEvenParams:** `arbitrage/v2/domain/break_even.py`
- **Evidence:** `logs/evidence/d203_3_20251230_0131_228eef2/`

---

## ✅ 결론

**D203-3: 완전 완료**
- Opportunity → OrderIntent bridge 구현 ✅
- Gate 3단 100% PASS ✅
- Reuse-First 준수 (OrderIntent, OpportunityCandidate, BreakEvenParams) ✅
- SSOT Hygiene Fix 완료 (커밋 표기, 리포트 분리) ✅
- 중복 모듈 0개 ✅

**Git:**
- Commit: `d77f97e` ([D203-3] Opportunity→OrderIntent bridge + SSOT hygiene (Gate PASS))
- Push: ✅ origin/rescue/d99_15_fullreg_zero_fail
- Compare: `228eef2..d77f97e`

**누적 진행 (D203-1 + D203-2 + D203-3):**
- 신규 파일: 5개 (break_even.py, detector.py, intent_builder.py, 테스트 3개)
- 신규 테스트: 24개 (100% PASS)
- Gate 안정성: ✅ 베이스라인 회귀 0개
