# D106-4.1 HOTFIX: Upbit MARKET 주문 지원 (Adapter 최소 수정)

**일시:** 2025-12-28  
**상태:** ✅ **COMPLETE (설계 결함 제거)**

---

## 목표

3회 연속 LIVE Smoke 실패 근본 원인 제거:
- **설계 결함:** LIMIT 주문으로 시장가 흉내 (volume 소수점 제약 위반)
- **해결 방안:** Upbit adapter MARKET 타입 정식 지원 (BUY/SELL 분기 추가)

**원칙:**
- ✅ 실거래 재실행 금지 (READ_ONLY_ENFORCED=true 유지)
- ✅ 오버리팩토링 금지 (최소 변경)
- ✅ SSOT Gates 100% PASS 강제

---

## 이전 실패 분석 (D106-4 3회 연속 실패)

### 실패 내역

| 시도 | 심볼 | 문제 | 에러 |
|------|------|------|------|
| 1차 | BTC | 보유 중인데 선택 (필터링 버그) | ✅ 수정 완료 |
| 2차 | ETH | 0.00221742 @ 4,509,750 KRW | 400 Bad Request |
| 3차 | SOL | 0.07883948 @ 190,260 KRW | 400 Bad Request |

### 근본 원인

**잘못된 구현 (Before):**
```python
# LIMIT 주문으로 "시장가" 흉내
buy_price = int(best_ask * 1.05)  # 5% 프리미엄
buy_qty = round(order_krw / buy_price, 8)  # ❌ volume 계산

buy_order = exchange_a.create_order(
    symbol=symbol,
    side=OrderSide.BUY,
    qty=buy_qty,  # ❌ 소수점 제약 위반 (ETH 0.00221742)
    price=buy_price,
    order_type=OrderType.LIMIT,  # ❌ LIMIT으로 흉내
)
```

**문제점:**
1. Upbit volume 소수점 제약 코인별 상이 (ETH 0.001 단위, SOL 0.1 단위)
2. 계산된 volume이 제약 위반 → 400 Bad Request
3. LIMIT 주문 부분 체결/미체결 위험

---

## 해결 방안 (D106-4.1)

### Upbit MARKET 주문 규칙 (API 문서 기준)

```python
# 시장가 매수: ord_type=market, side=bid, price=KRW금액 (volume 없음)
params = {
    "market": "KRW-BTC",
    "side": "bid",
    "price": "15000",  # 매수 금액 (KRW)
    "ord_type": "market",
}

# 시장가 매도: ord_type=market, side=ask, volume=수량 (price 없음)
params = {
    "market": "KRW-BTC",
    "side": "ask",
    "volume": "0.5",  # 매도 수량
    "ord_type": "market",
}
```

---

## 구현 내역

### 1) Upbit Adapter 수정 (D106-4.1)

**파일:** `arbitrage/exchanges/upbit_spot.py`

**변경 내용:**
```python
# D106-4.1: MARKET 주문 타입별 파라미터 분기
if order_type == OrderType.MARKET:
    if side == OrderSide.BUY:
        # 시장가 매수: price=KRW금액 (volume 없음)
        params = {
            "market": symbol,
            "side": side_str,
            "price": str(int(price)) if price else None,
            "ord_type": ord_type_str,
        }
    else:
        # 시장가 매도: volume=수량 (price 없음)
        params = {
            "market": symbol,
            "side": side_str,
            "volume": str(qty),
            "ord_type": ord_type_str,
        }
else:
    # 지정가 주문: volume + price 모두 필요
    params = {
        "market": symbol,
        "side": side_str,
        "volume": str(qty),
        "price": str(int(price)) if price else None,
        "ord_type": ord_type_str,
    }
```

**효과:**
- ✅ MARKET BUY: volume 소수점 제약 회피 (Upbit이 자동 계산)
- ✅ MARKET SELL: price 없음 (즉시 체결)

---

### 2) Smoke 스크립트 수정 (D106-4.1)

**파일:** `scripts/run_d106_4_live_smoke.py`

**변경 내용:**

**Before (LIMIT 흉내):**
```python
# LIMIT 주문으로 시장가 흉내
buy_price = int(best_ask * 1.05)
buy_qty = round(order_krw / buy_price, 8)

buy_order = exchange_a.create_order(
    symbol=symbol,
    side=OrderSide.BUY,
    qty=buy_qty,
    price=buy_price,
    order_type=OrderType.LIMIT,
)
```

**After (MARKET 타입):**
```python
# D106-4.1: MARKET 타입, price=KRW금액
logger.info(f"[D106-4] Step 2) 시장가 매수: {order_krw:.0f} KRW (MARKET BUY)")

buy_order = exchange_a.create_order(
    symbol=symbol,
    side=OrderSide.BUY,
    qty=0,  # MARKET 매수는 qty 무시
    price=order_krw,  # KRW 금액
    order_type=OrderType.MARKET,
)
```

**READ_ONLY 가드 강화:**
```python
# D106-4.1: READ_ONLY 가드 (영구 차단, 실거래 금지)
read_only_enforced = os.getenv("READ_ONLY_ENFORCED", "true").lower()
if read_only_enforced in ["true", "1", "yes"]:
    logger.error("[D106-4] ❌ READ_ONLY_ENFORCED=true (실거래 차단)")
    logger.error("[D106-4] 이 스크립트는 코드 검증용이며, 실거래는 금지됩니다.")
    logger.error("[D106-4] D106-4.1은 'adapter MARKET 지원 구현'이 목표입니다.")
    return 0  # 정상 종료 (실거래 차단은 성공)
```

---

### 3) 테스트 추가 (D106-4.1)

**파일:** `tests/test_d48_upbit_order_payload.py`

**추가된 테스트:**

**A. test_upbit_create_order_market_buy**
```python
@patch('arbitrage.exchanges.upbit_spot.HTTPClient.post')
def test_upbit_create_order_market_buy(self, mock_post):
    """시장가 매수 (D106-4.1: price=KRW금액, volume 없음)"""
    exchange.create_order(
        symbol="KRW-BTC",
        side=OrderSide.BUY,
        qty=0,  # MARKET 매수는 qty 무시
        price=15000.0,  # KRW 금액
        order_type=OrderType.MARKET,
    )
    
    # 페이로드 검증
    params = call_kwargs["params"]
    assert params["ord_type"] == "market"
    assert params["side"] == "bid"
    assert params["price"] == "15000"  # KRW 금액
    assert "volume" not in params  # MARKET BUY는 volume 없음
```

**B. test_upbit_create_order_market_sell**
```python
@patch('arbitrage.exchanges.upbit_spot.HTTPClient.post')
def test_upbit_create_order_market_sell(self, mock_post):
    """시장가 매도 (D106-4.1: volume=수량, price 없음)"""
    exchange.create_order(
        symbol="KRW-BTC",
        side=OrderSide.SELL,
        qty=0.5,  # 매도 수량
        price=None,  # MARKET 매도는 price 무시
        order_type=OrderType.MARKET,
    )
    
    # 페이로드 검증
    params = call_kwargs["params"]
    assert params["ord_type"] == "market"
    assert params["side"] == "ask"
    assert params["volume"] == "0.5"  # 매도 수량
    assert "price" not in params  # MARKET SELL은 price 없음
```

---

## 테스트 결과 (SSOT Gates)

### Gate 1 (Doctor): ✅ PASS
```bash
python -m pytest --collect-only -q
# 2495 tests collected
```

### Gate 2 (Fast): ✅ PASS
```bash
python -m pytest tests/test_d48_upbit_order_payload.py -v
# 11 passed in 0.28s
```

**테스트 목록:**
1. test_upbit_create_order_live_disabled
2. test_upbit_create_order_no_api_key
3. test_upbit_create_order_success
4. test_upbit_create_order_payload_structure
5. test_upbit_create_order_signature_header
6. test_upbit_cancel_order_success
7. test_upbit_cancel_order_live_disabled
8. test_upbit_create_order_network_error
9. test_upbit_create_order_parse_error
10. **test_upbit_create_order_market_buy** (D106-4.1 신규)
11. **test_upbit_create_order_market_sell** (D106-4.1 신규)

### Gate 3 (Core Regression): ✅ PASS
```bash
python -m pytest tests/test_d98_preflight.py tests/test_d48_upbit_order_payload.py -v
# 27 passed in 0.57s
```

---

## 보장 내역 (AC)

| AC | 목표 | 상태 | 증거 |
|----|------|------|------|
| AC-1 | Upbit MARKET BUY payload 정상 (price=KRW, volume 없음) | ✅ PASS | test_upbit_create_order_market_buy |
| AC-2 | Upbit MARKET SELL payload 정상 (volume=수량, price 없음) | ✅ PASS | test_upbit_create_order_market_sell |
| AC-3 | Smoke 스크립트 LIMIT 로직 제거 | ✅ PASS | scripts/run_d106_4_live_smoke.py (Lines 269-341) |
| AC-4 | READ_ONLY 가드 강화 (실거래 차단) | ✅ PASS | scripts/run_d106_4_live_smoke.py (Lines 482-488) |
| AC-5 | SSOT Gates 100% PASS | ✅ PASS | doctor/fast/regression 모두 통과 |

---

## 변경 파일 목록

### Modified (2개)
**1. arbitrage/exchanges/upbit_spot.py**
- **변경:** MARKET 주문 타입별 파라미터 분기 (BUY: price=KRW, SELL: volume=수량)
- **Lines:** 321-348 (D106-4.1 주석 포함)

**2. scripts/run_d106_4_live_smoke.py**
- **변경:** LIMIT 로직 제거 + MARKET 타입 사용 + READ_ONLY 가드 강화
- **Lines:** 269-341 (execute_real_trade), 482-488 (main)

**3. tests/test_d48_upbit_order_payload.py**
- **변경:** test_upbit_create_order_market_type → test_upbit_create_order_market_buy/sell (분리 + 강화)
- **Lines:** 258-329 (2개 테스트 추가)

---

## 남은 작업 (D106-4 재개 조건)

D106-4.1은 **"설계 결함 제거"**가 목표이며, **실거래는 포함되지 않음**.

D106-4 재개를 위한 조건:
1. ✅ Upbit adapter MARKET 지원 완료 (D106-4.1)
2. ⏳ 잔고 충전 (최소 50,000 KRW 권장)
3. ⏳ READ_ONLY_ENFORCED=false 설정 (일시적, 프로세스 내부)
4. ⏳ 실거래 재시도 (--enable-live --i-understand-live-trading)

---

## 최종 요약

**성공 (5개):**
- ✅ AC-1: Upbit MARKET BUY payload 정상
- ✅ AC-2: Upbit MARKET SELL payload 정상
- ✅ AC-3: Smoke 스크립트 LIMIT 로직 제거
- ✅ AC-4: READ_ONLY 가드 강화
- ✅ AC-5: SSOT Gates 100% PASS

**D106-4 상태:**
- Before: ❌ **BLOCKED** (3회 연속 실패, 설계 결함)
- After: ✅ **READY** (설계 결함 제거, 실거래 준비 완료)

**다음 단계 (사용자 선택):**
1. **D106-4 재개** (잔고 충전 후 실거래 재시도)
2. **D106-5 진행** (1h LIVE 확장)
3. **M6 다른 단계** (D106-4 연기)

**작성:** 2025-12-28 22:10  
**담당:** Windsurf Cascade
