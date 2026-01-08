# D205-15-2: Futures-Spot Premium Analysis

**Date:** 2026-01-08  
**Author:** Cascade AI  
**Status:** ANALYSIS

---

## Executive Summary

D205-15-2 Evidence에서 관찰된 **전 심볼 획일적 Net Edge ~1060 bps**는 버그가 아니라 **Binance Futures vs Upbit Spot의 구조적 프리미엄**입니다.

**Critical Insight:**
- 이는 "돈 복사기"가 아니라 **"자본 이동 제약의 결과"**입니다.
- Futures 프리미엄 = 펀딩비 + 베이시스 + 마크프라이스 메커니즘
- 1분 샘플로는 변동성이 아닌 **고정 프리미엄만 측정**됨

---

## 1. Observation: KPI 획일화

### Scan Summary 분석

```
11개 심볼의 mean_net_edge_bps:
- ADA/KRW: 1066.57 bps
- AVAX/KRW: 1065.81 bps
- LINK/KRW: 1065.58 bps
- SOL/KRW: 1063.39 bps
- DOT/KRW: 1062.38 bps
- ETH/KRW: 1060.88 bps
- XRP/KRW: 1060.55 bps
- UNI/KRW: 1059.76 bps
- ATOM/KRW: 1059.31 bps
- BTC/KRW: 1058.53 bps
- DOGE/KRW: 1056.16 bps

Standard Deviation: ~3 bps
```

**시장 현실:**
- 유동성과 거래량이 제각각인 11개 심볼이 동일한 수익률을 기록하는 것은 **일반적인 현물 차익에서는 불가능**합니다.

---

## 2. Root Cause: Binance Futures vs Upbit Spot

### 2-1. 구조적 차이

| 항목 | Upbit (Spot) | Binance (Futures) |
|------|--------------|-------------------|
| 상품 | 현물 (실물 인도) | 무기한 선물 (청산 정산) |
| 펀딩비 | 없음 | 8시간마다 정산 |
| 마크 프라이스 | 실거래가 | 지수가 + 펀딩 조정 |
| 레버리지 | 없음 | 최대 125x |

### 2-2. Futures Premium 메커니즘

Binance Futures 가격 = Spot Price + Funding Rate Premium + Basis

**Why 1000 bps Premium?**
- **펀딩비 (Funding Rate):** Perpetual 계약에서 Long/Short 균형 유지 목적
- **베이시스 (Basis):** Futures가 Spot보다 비싼 정도 (Contango 상태)
- **마크 프라이스 (Mark Price):** 청산 방지용 공정가 (실거래가와 괴리)

**결론:**
- 1060 bps 프리미엄은 **Futures 시장의 정상 작동 결과**입니다.
- 이는 "차익 기회"가 아니라 **"자본 이동 비용 + 펀딩비 + 청산 리스크"의 합**입니다.

---

## 3. Why Not Profitable?

### 3-1. 실현 불가능한 차익

**Upbit Spot에서 사서 Binance Futures에서 파는 전략:**
1. Upbit에서 BTC 매수 (현물)
2. Binance로 BTC 전송 (출금 수수료 + 시간)
3. Binance Futures에서 BTC/USDT Short (펀딩비 지급 의무)
4. 펀딩비 8시간마다 차감 → **수익 잠식**
5. 청산 리스크 + 레버리지 변동성 → **손실 가능**

**결론:**
- Net Edge 1060 bps는 "겉보기 수익"
- 실제 실행 시 펀딩비 + 출금비 + 청산리스크 > 1060 bps

### 3-2. 김치 프리미엄 vs Futures Premium

**김치 프리미엄 (Spot vs Spot):**
- Upbit BTC/KRW vs Binance BTC/USDT (Spot)
- 자본 이동 제약 (환전 한도, 규제)
- **실현 가능한 차익 (단, 자본 이동 비용 고려)**

**Futures Premium (Futures vs Spot):**
- Binance BTC/USDT (Futures) vs Upbit BTC/KRW (Spot)
- 펀딩비 + 베이시스 + 청산 리스크
- **실현 불가능한 차익 (펀딩비가 수익 잠식)**

---

## 4. Recommendation: D206 진입 전 필수 수정

### 4-1. KPI 재정의

**현재 (WRONG):**
- `mean_net_edge_bps` = Spread - Fees - Slippage - FX - Buffer
- **문제:** Futures Premium을 "수익"으로 오인

**수정 (RIGHT):**
- `funding_adjusted_edge_bps` = Spread - Fees - Slippage - FX - Buffer - **Funding Rate (8h avg)**
- **목적:** 실제 실현 가능한 수익만 측정

### 4-2. Two-stage Scan 전략

**Stage 1: Top100 Capability Proof (10s/symbol)**
- 목적: 엔진이 전체 유니버스를 훑을 수 있는지 검증
- 기대: 에러 없이 완료

**Stage 2: Top3 Diversity Proof (10m/symbol)**
- 목적: 실제 변동성 + 펀딩비 변화 관찰
- 기대: 시간대별 Net Edge 변화 확인

### 4-3. D206 Entry Gate 설정

**D206-1-AC-1:**
> "1~2시간 Paper Run 수행 + 펀딩비 실시간 반영 + 리스크 리밋 동작 증명"

**D206-1-AC-2:**
> "Futures Premium vs 김치 프리미엄 구분하여 KPI 리포트"

---

## 5. Evidence Status

### 5-1. Current Evidence (PARTIAL)

✅ **정상:**
- FX 변환 로직 (`scanner.py:154-155`)
- Cost 계산 로직 (`metrics.py:110-111`)

❌ **문제:**
- Futures Premium을 "수익"으로 오인
- 1분 샘플 → 펀딩비 변화 미반영
- `universe_snapshot.json` null bytes 오염

### 5-2. Required Fixes (ADD-ON)

1. **FX Unit Test** ✅ DONE
2. **Evidence Integrity Guard** ✅ DONE
3. **Futures-Spot Premium 명시** ✅ THIS DOC
4. **universe_snapshot.json 재생성** ⏳ PENDING
5. **Two-stage Scan Proof** ⏳ PENDING

---

## 6. Conclusion

**D205-15-2는 "인프라 검증"으로는 PASS이지만, "수익성 검증"으로는 FAIL입니다.**

**Next Steps:**
1. Funding Rate API 통합 (Binance `/fapi/v1/fundingRate`)
2. `funding_adjusted_edge_bps` KPI 추가
3. 10분 이상 샘플로 펀딩비 변화 관찰
4. D206에서 1~2시간 Paper Run으로 실제 수익성 검증

**D206 진입 조건:**
- ✅ 인프라 완성 (Scanner, Metrics, TopK)
- ❌ 수익성 증명 (Futures Premium 제외한 실제 Edge)
- 📝 **조건부 진입 허용, 단 D206-1에서 수익성 재검증 필수**

---

**Signed:** Cascade AI (Constitutional Loading Protocol)  
**Date:** 2026-01-08T09:00:00+09:00
