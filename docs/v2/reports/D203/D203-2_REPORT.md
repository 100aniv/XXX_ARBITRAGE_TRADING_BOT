# D203-2 Report: Opportunity Detector v1

**작성일:** 2025-12-30  
**상태:** ✅ DONE  
**커밋:** `228eef2`

---

## 📋 목표 및 범위

### D203-2: Opportunity Detector v1 (옵션 확장)
두 거래소 가격을 입력받아 차익거래 기회를 탐지하는 모듈.

**Note:** 
- 원래 D203-2는 "Replay/Backtest Gate" 계획이었으나, D203-1의 자연스러운 확장으로 Opportunity Detector를 먼저 구현
- Backtest Gate는 D204-2로 이동 예정

---

## ✅ 완료 항목

**파일:**
- `arbitrage/v2/opportunity/__init__.py` (신규, 4 lines)
- `arbitrage/v2/opportunity/detector.py` (신규, 154 lines)
- `tests/test_d203_2_opportunity_detector.py` (신규, 258 lines)

**구현:**
- `OpportunityCandidate(dataclass)` - 기회 후보
  - symbol, exchange_a, exchange_b
  - price_a, price_b
  - spread_bps, break_even_bps, edge_bps
  - direction (BUY_A_SELL_B, BUY_B_SELL_A, NONE)
  - profitable (edge_bps > 0)
- `detect_candidates(...)` - 단일 심볼 기회 탐지
- `detect_multi_candidates(...)` - 여러 심볼 기회 탐지 + Edge 순 정렬

**Direction 정의:**
```python
class OpportunityDirection(str, Enum):
    BUY_A_SELL_B = "buy_a_sell_b"  # A에서 사고 B에서 팔기 (A < B)
    BUY_B_SELL_A = "buy_b_sell_a"  # B에서 사고 A에서 팔기 (B < A)
    NONE = "none"  # 기회 없음
```

**Logic:**
```python
def detect_candidates(...):
    """
    1. Spread 계산 (bps)
    2. Break-even 계산 (bps)
    3. Edge 계산 (bps)
    4. Direction 판단
    5. Profitable 여부 확인
    """
```

**Reuse-First:**
- ✅ BreakEvenParams 재사용 (D203-1)
- ✅ SpreadModel 로직 참조 (V1: `spread_percent = (price_a - price_b) / price_b * 100`)

**테스트:** 6/6 PASS (0.18s)
1. 단일 기회 탐지 (profitable) - BTC spread 101 bps, edge 56 bps
2. 단일 기회 탐지 (unprofitable) - ETH spread 30 bps, edge -15 bps
3. Direction 판단 (BUY_A_SELL_B vs BUY_B_SELL_A)
4. 여러 기회 중 profitable만 필터링 (3개 → 2개)
5. Edge 순서대로 정렬 (BTC 56 bps > XRP 15 bps)
6. Invalid 가격 처리 (0 또는 음수 → None 반환)

---

## 🧪 Gate 검증 결과 (D203-1 + D203-2 통합)

| Gate | 상태 | 테스트 | 시간 | 결과 |
|------|------|--------|------|------|
| Doctor | ✅ PASS | 2512 collected | < 1s | Import/collect OK |
| Fast | ✅ PASS | 67/67 | 0.68s | V2 core tests (D203-1: 9, D203-2: 6 포함) |
| Regression | ✅ PASS | 95/95 | 0.90s | D98 + V2 combined |

**Evidence:** `logs/evidence/d203_1_20251230_0047_5504337/gate_results.md`

---

## 📊 Scan-First 결과

**V1 참조 모듈:**
| 기능 | V1 위치 | V2 적용 | 재사용 방식 | 결정 |
|------|---------|---------|-----------|------|
| Spread 계산 공식 | `arbitrage/cross_exchange/spread_model.py` | `arbitrage/v2/opportunity/detector.py` | ✅ 로직 참조 | REFERENCE |
| Break-even 파라미터 | `arbitrage/v2/domain/break_even.py` | `arbitrage/v2/opportunity/detector.py` | ✅ import 재사용 | KEEP |

**중복 모듈:** 0개 ✅

**Evidence:** `logs/evidence/d203_1_20251230_0047_5504337/scan_reuse_map.md`

---

## 📝 변경 파일 목록

### 신규 파일 (3개, D203-2 전용)
1. `arbitrage/v2/opportunity/__init__.py` - Package init (4 lines)
2. `arbitrage/v2/opportunity/detector.py` - Opportunity detector (154 lines)
3. `tests/test_d203_2_opportunity_detector.py` - Detector 테스트 (258 lines)

**Note:** D203-1 관련 파일(break_even.py, test_d203_1)은 D203-1_REPORT.md 참조

---

## 🔍 Tech-Debt / 남은 일

### ⚠️ Spread 정의 비대칭 (SSOT 문서화 필요)
**현재 구현:**
```python
spread_percent = (price_a - price_b) / price_b * 100
spread_bps = abs(spread_percent * 100)
```

**이슈:**
- 분모가 항상 `price_b`라서 A/B를 바꾸면 spread 크기가 미세하게 달라지는 비대칭 정의
- v1로는 "그럴 수 있음"이지만, SSOT 문서에 **"왜 price_b 기준인지"** 명시 필요
- 대안: mid-price 기반 `(price_a + price_b) / 2` 또는 최소값 기반 `min(price_a, price_b)`

**조치:** D203-3 또는 D204에서 SSOT 문서화 (현재는 v1 동작)

### 🔶 Direction 기반 Break-even (다음 단계)
**현재 제한:**
- Break-even이 "방향성"을 반영하지 않음
- 현실은 BUY_A_SELL_B냐 BUY_B_SELL_A냐에 따라 entry/exit exchange가 바뀌고, 수수료/슬리피지도 달라질 수 있음

**조치:** D203-3에서 Direction 기반 break-even 계산으로 확장 여부 결정

---

## 📚 참조

- SSOT: `D_ROADMAP.md` (line 2655-2678)
- D203-1: `docs/v2/reports/D203/D203-1_REPORT.md`
- V1 SpreadModel: `arbitrage/cross_exchange/spread_model.py`
- V2 BreakEvenParams: `arbitrage/v2/domain/break_even.py`
- Evidence: `logs/evidence/d203_1_20251230_0047_5504337/`

---

## ✅ 결론

**D203-2: 완전 완료**
- Opportunity Detector v1 구현 ✅
- Gate 3단 100% PASS ✅
- Reuse-First 준수 (BreakEvenParams, SpreadModel 로직) ✅
- 중복 모듈 0개 ✅

**다음 단계:**
- D203-3: Opportunity → OrderIntent 변환 (얇은 어댑터)
- D204-1: DB ledger 기록 (orders/fills/trades)
- D204-2: Paper Execution Gate (원래 D203-2 계획)
