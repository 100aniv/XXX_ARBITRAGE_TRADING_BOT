# [D201-2] Adapter Contract Tests 100% PASS

**작성일:** 2025-12-29  
**상태:** ✅ DONE  
**커밋:** (진행 중)  
**Evidence (Gate 3단):**
- Doctor: `logs/evidence/20251229_173344_gate_doctor_3b393ca/`
- Fast: `logs/evidence/20251229_175329_gate_fast_3b393ca/`
- Regression: `logs/evidence/20251229_175331_gate_regression_3b393ca/`

---

## 목표 (Goal)

Adapter 인터페이스 contract 테스트를 작성하여 MARKET BUY/SELL 규약을 엄격히 검증하고, Mock/Upbit/Binance Adapter가 동일한 V2 계약을 만족하는지 확인한다.

---

## ✅ AC (Acceptance Criteria)

| AC | 설명 | 상태 | 세부 |
|----|------|------|------|
| AC-1 | test_v2_order_intent.py (OrderIntent validation) | ✅ PASS | 14/14 PASS |
| AC-2 | test_v2_adapter_contract.py (인터페이스 contract) | ✅ PASS | 17/17 PASS |
| AC-3 | MARKET BUY: quote_amount 필수 검증 | ✅ PASS | ValueError 정상 발생 |
| AC-4 | MARKET SELL: base_qty 필수 검증 | ✅ PASS | ValueError 정상 발생 |
| AC-5 | Mock/Upbit/Binance 모두 100% PASS | ✅ PASS | 41/41 total |

---

## 📐 V2 계약 (SSOT)

### OrderIntent 계약
- **MARKET BUY:** `quote_amount` 필수 (USDT/KRW 지출액)
- **MARKET SELL:** `base_qty` 필수 (BTC/ETH 코인 수량)
- **LIMIT 주문:** `limit_price` 필수 + 위 규칙 동일

### Adapter 계약
| Adapter | MARKET BUY | MARKET SELL |
|---------|------------|-------------|
| BinanceAdapter | `quoteOrderQty` (USDT amount) | `quantity` (BTC qty) |
| UpbitAdapter | `price` (KRW amount) | `volume` (coin qty) |
| MockAdapter | 계약 검증만 (payload는 단순화) | 계약 검증만 |

---

## 🧪 테스트 결과

### test_v2_order_intent.py (14 tests)
```
TC-1: MARKET BUY requires quote_amount                    PASS
TC-2: MARKET BUY requires positive quote_amount           PASS
TC-3: MARKET BUY valid                                    PASS
TC-4: MARKET SELL requires base_qty                       PASS
TC-5: MARKET SELL requires positive base_qty              PASS
TC-6: MARKET SELL valid                                   PASS
TC-7: LIMIT BUY requires limit_price                      PASS
TC-8: LIMIT BUY requires quote_amount                     PASS
TC-9: LIMIT BUY valid                                     PASS
TC-10: LIMIT SELL requires limit_price                    PASS
TC-11: LIMIT SELL requires base_qty                       PASS
TC-12: LIMIT SELL valid                                   PASS
TC-13: __repr__ MARKET BUY format                         PASS
TC-14: __repr__ MARKET SELL format                        PASS
```
**결과:** 14/14 PASS (100%)

### test_v2_adapter_contract.py (17 tests)
```
TestBinanceAdapterContract (5 tests):
TC-1: MARKET BUY uses quoteOrderQty                       PASS
TC-2: MARKET SELL uses quantity                           PASS
TC-3: MARKET BUY missing quote_amount raises error        PASS
TC-4: MARKET SELL missing base_qty raises error           PASS
TC-5: Symbol transformation (BTC/USDT → BTCUSDT)          PASS

TestUpbitAdapterContract (5 tests):
TC-6: MARKET BUY uses price (KRW amount)                  PASS
TC-7: MARKET SELL uses volume (coin qty)                  PASS
TC-8: MARKET BUY missing quote_amount raises error        PASS
TC-9: MARKET SELL missing base_qty raises error           PASS
TC-10: Symbol transformation (BTC/KRW → KRW-BTC)          PASS

TestMockAdapterContract (3 tests):
TC-11: MockAdapter MARKET BUY accepts quote_amount        PASS
TC-12: MockAdapter MARKET SELL accepts base_qty           PASS
TC-13: MockAdapter contract violation raises error        PASS

TestAdapterContractConsistency (4 tests):
TC-14: All adapters reject invalid MARKET BUY             PASS
TC-15: All adapters reject invalid MARKET SELL            PASS
TC-16: All adapters accept valid MARKET BUY               PASS
TC-17: All adapters accept valid MARKET SELL              PASS
```
**결과:** 17/17 PASS (100%)

### 베이스라인 유지 (test_d201_1_binance_adapter.py)
```
D201-1 Binance Adapter Tests: 10/10 PASS
```

**총계:** 41/41 PASS (100%)

---

## 📊 변경 요약 (Diff Summary)

**커밋 해시:** (진행 중)

### Modified (1개)
**1. `D_ROADMAP.md`**
- 변경: D201-2 테스트 케이스 SSOT 계약 정합화 (BinanceAdapter BUY/SELL 규약 수정)
- Line 2476-2480: "BUY/SELL both use quantity" → "BUY uses quoteOrderQty, SELL uses quantity"

### Added (3개)
**1. `tests/test_v2_order_intent.py`**
- 기능: OrderIntent validation (14 tests)
- 검증: MARKET/LIMIT BUY/SELL 규약 + __repr__ 포맷

**2. `tests/test_v2_adapter_contract.py`**
- 기능: Adapter contract 검증 (17 tests)
- 검증: Binance/Upbit/Mock Adapter 계약 일관성

**3. `docs/v2/reports/D201/D201-2_REPORT.md`**
- 기능: D201-2 최종 리포트

---

## 📁 증거 (Evidence)

**Evidence 경로:** `logs/evidence/20251229_160222_gate_doctor_109407c/`

**포함 파일:**
- manifest.json ✅
- git_info.json ✅
- cmd_history.txt ✅
- gate.log ✅ (Doctor gate: 289 tests collected)

**Gate 결과 (pytest-asyncio 설치 후):**
- Doctor: ✅ PASS (289 tests collected)
- Fast: ✅ PASS (1154 passed, 37 skipped, 188s)
- Regression: ✅ PASS (2482 passed, 43 skipped, 192s)
- D201 Tests: ✅ 41/41 PASS (test_v2_order_intent 14 + test_v2_adapter_contract 17 + test_d201_1 10)

---

## 🎯 PASS/FAIL 판정

**최종 상태:** ✅ DONE

**근거:**
- AC 5개 모두 달성 ✅
- OrderIntent validation 14/14 PASS ✅
- Adapter contract 17/17 PASS ✅
- D201-1 베이스라인 유지 10/10 PASS ✅
- V2 계약 SSOT 정합화 완료 ✅
- Gate 3단 모두 PASS (Doctor/Fast/Regression) ✅
- pytest-asyncio 의존성 추가 및 Gate 환경 정합성 확보 ✅

---

## 🔗 참고

- D_ROADMAP: `D_ROADMAP.md` (D201-2 섹션)
- SSOT_MAP: `docs/v2/design/SSOT_MAP.md`
- V2 Architecture: `docs/v2/V2_ARCHITECTURE.md`
- D201-1 Report: `docs/v2/reports/D201/D201-1_REPORT.md`
