# D201-1: Binance Adapter v2 (MARKET Semantics)

**작성일:** 2025-12-29  
**상태:** IN_PROGRESS  
**목표:** Binance Spot MARKET 주문을 V2 OrderIntent로 명시적 지원

---

## 📋 목표 (Goal)

V2 아키텍처에서 Binance Spot MARKET 주문을 명시적으로 지원하는 BinanceAdapter를 구현한다.

**금지 사항:**
- ❌ LIMIT 주문으로 시장가를 흉내내는 설계
- ❌ Engine에서 거래소 특화 로직 처리
- ❌ OrderIntent에 거래소별 필드 추가

**원칙:**
- ✅ OrderIntent는 거래소 독립적 의미론만 표현
- ✅ Adapter가 거래소 API 변환 책임
- ✅ UpbitAdapter와 동일한 패턴 사용

---

## 🎯 MARKET Semantics (Binance Spot API)

### Binance Spot MARKET 주문 규칙

**공식 문서:** https://binance-docs.github.io/apidocs/spot/en/#new-order-trade

#### MARKET BUY (시장가 매수)
```python
# Case 1: USDT 금액으로 매수 (권장)
{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "MARKET",
    "quoteOrderQty": "100.00"  # 100 USDT로 BTC 매수
}

# Case 2: BTC 수량으로 매수 (비권장 - 가격 변동 리스크)
{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "MARKET",
    "quantity": "0.001"  # 0.001 BTC 매수 (USDT 지출액 불확실)
}
```

**V2 OrderIntent 매핑:**
```python
OrderIntent(
    exchange="binance",
    symbol="BTC/USDT",
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    quote_amount=100.00  # USDT 지출액
)
→ Binance payload: {"quoteOrderQty": "100.00"}
```

#### MARKET SELL (시장가 매도)
```python
{
    "symbol": "BTCUSDT",
    "side": "SELL",
    "type": "MARKET",
    "quantity": "0.001"  # 0.001 BTC 매도
}
```

**V2 OrderIntent 매핑:**
```python
OrderIntent(
    exchange="binance",
    symbol="BTC/USDT",
    side=OrderSide.SELL,
    order_type=OrderType.MARKET,
    base_qty=0.001  # BTC 수량
)
→ Binance payload: {"quantity": "0.001"}
```

---

## 🔧 BinanceAdapter 구현 계약

### translate_intent() 변환 규칙

| OrderIntent | Binance API Payload |
|-------------|---------------------|
| MARKET BUY + quote_amount | `type="MARKET"` + `quoteOrderQty` |
| MARKET SELL + base_qty | `type="MARKET"` + `quantity` |
| LIMIT BUY + quote_amount + limit_price | `type="LIMIT"` + `quantity` (computed) + `price` |
| LIMIT SELL + base_qty + limit_price | `type="LIMIT"` + `quantity` + `price` |

### Symbol 변환
- **V2 표준:** `BTC/USDT` (slash 구분)
- **Binance API:** `BTCUSDT` (no separator)
- **변환:** `symbol.replace("/", "")`

### 파라미터 검증
- MARKET BUY: `quote_amount > 0` (필수)
- MARKET SELL: `base_qty > 0` (필수)
- LIMIT: `limit_price > 0` (필수)

---

## 🧪 테스트 계약

### 단위 테스트 (test_d201_1_binance_adapter.py)

**TC-1: MARKET BUY 변환**
```python
intent = OrderIntent(
    exchange="binance",
    symbol="BTC/USDT",
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    quote_amount=100.00
)

payload = adapter.translate_intent(intent)

assert payload["symbol"] == "BTCUSDT"
assert payload["side"] == "BUY"
assert payload["type"] == "MARKET"
assert payload["quoteOrderQty"] == "100.00"
assert "quantity" not in payload  # quoteOrderQty 사용 시 금지
```

**TC-2: MARKET SELL 변환**
```python
intent = OrderIntent(
    exchange="binance",
    symbol="BTC/USDT",
    side=OrderSide.SELL,
    order_type=OrderType.MARKET,
    base_qty=0.001
)

payload = adapter.translate_intent(intent)

assert payload["symbol"] == "BTCUSDT"
assert payload["side"] == "SELL"
assert payload["type"] == "MARKET"
assert payload["quantity"] == "0.001"
assert "quoteOrderQty" not in payload
```

**TC-3: 금지 케이스 (LIMIT 흉내)**
```python
# ❌ LIMIT으로 시장가 흉내는 FAIL
intent = OrderIntent(
    exchange="binance",
    symbol="BTC/USDT",
    side=OrderSide.BUY,
    order_type=OrderType.LIMIT,  # MARKET이어야 함
    quote_amount=100.00,
    limit_price=99999999  # 시장가 흉내
)

payload = adapter.translate_intent(intent)
assert payload["type"] == "LIMIT"  # MARKET이 아님 → FAIL
```

---

## 📐 구현 체크리스트

- [ ] `arbitrage/v2/adapters/binance_adapter.py` 생성
- [ ] `translate_intent()` 구현 (MARKET/LIMIT 지원)
- [ ] `submit_order()` 구현 (mock mode, read_only=True)
- [ ] `parse_response()` 구현 (OrderResult 변환)
- [ ] `tests/test_d201_1_binance_adapter.py` 생성
- [ ] TC-1~TC-3 테스트 작성 및 PASS
- [ ] Doctor/Fast Gate PASS
- [ ] Evidence 생성 (gate.log 포함)

---

## 🚫 안티패턴 (명시적 금지)

### ❌ Pattern 1: LIMIT으로 시장가 흉내
```python
# 금지: 높은 가격으로 LIMIT BUY = "시장가처럼 동작"
payload = {
    "type": "LIMIT",
    "price": "99999999",  # 실제로는 시장가
    "quantity": "0.001"
}
```
**이유:** OrderType.MARKET의 의미론 위반, 디버깅 불가능

### ❌ Pattern 2: Engine에서 거래소 분기
```python
# 금지: Engine이 Binance/Upbit 구분
if exchange == "binance":
    # Binance 특화 로직
elif exchange == "upbit":
    # Upbit 특화 로직
```
**이유:** Adapter 책임 위반, 확장성 저하

### ❌ Pattern 3: OrderIntent에 거래소 필드 추가
```python
# 금지
@dataclass
class OrderIntent:
    exchange: str
    binance_quote_order_qty: Optional[float]  # ❌ 거래소 특화 필드
    upbit_price_krw: Optional[int]  # ❌ 거래소 특화 필드
```
**이유:** 거래소 독립성 위반

---

## 📊 Expected Outcomes

1. **BinanceAdapter 생성:** `arbitrage/v2/adapters/binance_adapter.py` ✅
2. **테스트 PASS:** TC-1 ~ TC-3 모두 PASS ✅
3. **Gate PASS:** doctor → fast ✅
4. **Evidence:** logs/evidence/<run_id>/ 생성 (gate.log 포함) ✅
5. **문서:** D201-1_REPORT.md + D_ROADMAP.md 업데이트 ✅

---

## 🔗 참조 (References)

- **Binance Spot API:** https://binance-docs.github.io/apidocs/spot/en/#new-order-trade
- **V2 OrderIntent:** `arbitrage/v2/core/order_intent.py`
- **V2 Adapter Interface:** `arbitrage/v2/core/adapter.py`
- **UpbitAdapter (참조):** `arbitrage/v2/adapters/upbit_adapter.py`
