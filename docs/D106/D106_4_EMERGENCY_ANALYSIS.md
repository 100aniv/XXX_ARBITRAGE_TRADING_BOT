# D106-4 긴급 분석: 3회 연속 실패

**일시:** 2025-12-28 16:07  
**상태:** ❌ **BLOCKED (설계 결함)**

---

## 실패 내역

### 1차 실패: BTC (보유 중)
- **문제:** `get_safe_test_symbol()` 필터링 실패
- **수정:** `held_symbols` 로직 강화 (KRW 제외 + threshold 0.00000001)
- **결과:** ✅ 수정 완료

### 2차 실패: ETH
- **선택:** KRW-ETH (보유 없음 확인)
- **매수 시도:** 0.00221742 ETH @ 4,509,750 KRW (total: 10K)
- **에러:** 400 Bad Request
- **추정 원인:** Upbit ETH volume 소수점 제약 (0.001 단위?)

### 3차 실패: SOL
- **선택:** KRW-SOL (보유 없음 확인)
- **매수 시도:** 0.07883948 SOL @ 190,260 KRW (total: 15K)
- **에러:** 400 Bad Request
- **추정 원인:** Upbit SOL volume 소수점 제약 또는 최소 단위 미달

---

## 근본 원인 분석

### A. 설계 결함: LIMIT 주문으로 시장가 흉내
**현재 구현:**
```python
# 시장가 매수 (Upbit: LIMIT 주문, ask*1.05로 즉시 체결)
buy_price = int(best_ask * 1.05)  # 5% 프리미엄
buy_qty_target = order_krw / buy_price
buy_qty = round(buy_qty_target, 8)

buy_order = exchange_a.create_order(
    symbol=symbol,
    side=OrderSide.BUY,
    qty=buy_qty,
    price=buy_price,
    order_type=OrderType.LIMIT,  # ❌ LIMIT으로 시장가 흉내
)
```

**문제점:**
1. **volume 소수점 제약:** Upbit은 코인별로 volume 소수점 자리수가 다름
2. **최소 단위:** ETH 0.001, SOL 0.1 등 코인별 상이
3. **400 에러:** 소수점 제약 위반 시 Upbit API 거부

**올바른 방법 (Upbit 문서 기준):**
```python
# 시장가 매수: ord_type=market, price=매수금액(KRW)
params = {
    "market": "KRW-BTC",
    "side": "bid",
    "price": "15000",  # 매수 금액 (KRW)
    "ord_type": "market",
}

# 시장가 매도: ord_type=market, volume=매도수량
params = {
    "market": "KRW-BTC",
    "side": "ask",
    "volume": "0.001",  # 매도 수량
    "ord_type": "market",
}
```

### B. 자금 부족
**현재 잔고:**
- Upbit KRW: 32,048 KRW
- 주문 금액: 15,000 KRW
- 수수료: ~150 KRW (1%)
- **여유:** 17K KRW (2회 왕복 가능, 안전 여유 부족)

### C. 심볼 선택 실패
**보유 심볼:** BTC, DOGE, XYM, ETHW, ETHF  
**시도 심볼:** BTC (보유), ETH (400), SOL (400)  
**문제:** 대부분의 메이저 코인 보유 또는 400 에러

---

## 해결 방안

### Option 1: Upbit Adapter 수정 (근본 해결)
**범위:** D106-4 범위 초과 (D108 or D109로 분리)

**변경점:**
1. `arbitrage/exchanges/upbit_spot.py` 수정
2. `create_order()` MARKET 타입 지원 강화
3. 시장가 매수: `price`에 KRW 금액 전달
4. 시장가 매도: `volume`에 수량 전달

**장점:** 근본 해결, 향후 안정성  
**단점:** 범위 초과, 기존 테스트 영향 가능성

### Option 2: 잔고 충전 + 재시도 (임시 회피)
**조건:**
- 잔고 50,000 KRW 이상 충전
- 주문 금액 20,000 KRW (안전 여유 확보)
- XRP (volume 정수 단위) 또는 DOGE (이미 보유) 사용

**장점:** 빠른 실행  
**단점:** 근본 문제 미해결

### Option 3: D106-4 재설계 (권장)
**범위:** 현재 작업에 포함

**변경점:**
1. **Upbit MARKET 주문 사용** (adapter 최소 수정)
2. **매수:** `price` 파라미터에 KRW 금액 전달
3. **매도:** `volume` 파라미터에 수량 전달
4. **volume 계산 제거** (Upbit이 자동 계산)

**구현:**
```python
# 매수: 15,000 KRW 어치 시장가 매수
buy_order = exchange_a.create_order(
    symbol=symbol,
    side=OrderSide.BUY,
    qty=0,  # MARKET 매수 시 무시
    price=order_krw,  # KRW 금액
    order_type=OrderType.MARKET,
)

# 매도: 전량 시장가 매도
sell_order = exchange_a.create_order(
    symbol=symbol,
    side=OrderSide.SELL,
    qty=buy_filled_qty,  # 매수 체결 수량
    price=None,  # MARKET 매도 시 무시
    order_type=OrderType.MARKET,
)
```

**장점:** 근본 해결, D106-4 범위 내  
**단점:** Upbit adapter 수정 필요 (최소한)

---

## 권장 조치

### Immediate (긴급)
1. **D106-4 중단** (3회 실패, 설계 결함 확인)
2. **Upbit adapter 확인** (`create_order` MARKET 타입 지원 여부)
3. **Option 3 선택** (재설계 + adapter 최소 수정)

### Next Steps (D106-4.1)
1. `arbitrage/exchanges/upbit_spot.py` 수정
   - MARKET 매수: `price` 파라미터를 KRW 금액으로 해석
   - MARKET 매도: `price` 파라미터 무시
2. `run_d106_4_live_smoke.py` 수정
   - LIMIT 주문 로직 제거
   - MARKET 주문 로직 추가
3. 테스트 실행 (잔고 30K+ 필요)

### Alternative (잔고 부족 시)
- **D106-4 연기** → D109 (Upbit MARKET 지원) 먼저 진행
- **D106-4.1 축소:** Flatten만 남기고 LIVE Smoke 제외

---

## Evidence
- Flatten 성공: `logs/evidence/flatten_upbit_20251228_160254`
- D106-4 실패 3회:
  1. `logs/evidence/d106_4_live_smoke_20251228_160316`
  2. `logs/evidence/d106_4_live_smoke_20251228_160638`
  3. `logs/evidence/d106_4_live_smoke_20251228_160722`

---

## 결론

**D106-4는 현재 상태로는 실행 불가능.**

**이유:**
1. Upbit LIMIT 주문의 volume 소수점 제약
2. 잔고 부족 (32K KRW, 안전 여유 미달)
3. 설계 결함 (LIMIT으로 시장가 흉내)

**권장:**
- **Option 3 선택** (D106-4.1 재설계 + Upbit adapter 최소 수정)
- 또는 **D106-4 연기** + D109 (Upbit MARKET 지원) 우선

**작성:** 2025-12-28 16:10  
**담당:** Windsurf Cascade
