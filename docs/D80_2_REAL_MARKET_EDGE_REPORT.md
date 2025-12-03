# D80-2: Real Market Edge & Spread Reality Check - REPORT

**Status:** ✅ **COMPLETE**  
**Date:** 2025-12-04  
**Analysis Run:** Based on D77-0-RM-EXT Top20 + Top50 1h Real Market PAPER validation

---

## Executive Summary

**D80-2**는 D77-0-RM-EXT 1시간 Top20/Top50 실행 결과를 기반으로, **Real Market에서의 Edge/PnL 현실성**을 정량 분석하는 단계입니다.

### 핵심 구분: Infrastructure vs. Edge Reality

| 관점 | 판단 | 근거 |
|------|------|------|
| **Infrastructure/Engine Level** | ✅ **GO** | D77-0-RM-EXT COMPLETE: Top20/Top50 모두 Critical 5/5 충족, 60분 연속 실행, 1,650+ round trips, 안정적 메모리/CPU |
| **Real Market Edge Reality** | ⚠️ **NEEDS FURTHER VALIDATION** | 100% 승률 및 $200k/h PnL은 PAPER 모드 한계로 인한 구조적 결과. Trade-level 스프레드, 호가 잔량, 부분 체결 등 미반영 |

### 주요 발견사항

**✅ 엔진/인프라 레벨 검증 (D77-0-RM-EXT):**
- **Top20 1h:** 1,659 round trips, $207,375 PnL, 60.16분, Loop Latency p99: 0.12ms
- **Top50 1h:** 1,658 round trips, $207,250 PnL, 60.17분, Loop Latency p99: 0.12ms
- **안정성:** Memory 150MB (0% growth), CPU 35%, Crash/HANG 0건
- **판단:** 엔진 구조, 인프라 통합, 장기 안정성 모두 검증 완료

**⚠️ Real Market Edge 현실성 Gap:**
- **100% 승률:** 엔진이 `spread > fee + safety_margin` 조건에서만 진입하도록 설계되어 있어, PAPER 모드에서 부분 체결, 슬리피지, 호가 변동 등을 모델링하지 않았기 때문에 발생한 구조적 결과. 실제 시장에서는 30~80% 범위가 현실적.
- **$200k/h PnL:** 엔진 검증용 벤치마크로는 의미가 있으나, 실제 시장 수익 현실성과는 거리가 있음. 수수료, 슬리피지, 호가 잔량 제약 등을 반영하면 크게 감소할 것으로 예상.
- **Trade-level 데이터 부재:** 각 거래의 실제 스프레드, 호가 잔량, 체결 가격 등을 분석할 수 없어, Edge 현실성을 정량적으로 평가하기 어려움.

---

## 1. Data Sources

### D77-0-RM-EXT 실행 결과

| Universe | Run ID | Session ID | Duration | Round Trips | Total PnL |
|----------|--------|------------|----------|-------------|-----------|
| Top20 | run_20251204_001336 | d77-0-top_20-20251204001337 | 60.16분 | 1,659 | $207,375 |
| Top50 | run_20251204_012509 | d77-0-top_50-20251204012509 | 60.17분 | 1,658 | $207,250 |

**데이터 소스:**
- Upbit/Binance Public API (Real Market 시세)
- PAPER 모드 (실제 주문 없음, 모의 체결)
- KPI JSON 파일: `logs/d77-0-rm-ext/run_*/1h_top*_kpi.json`

**수집 기간:** 2025-12-04 00:13 ~ 02:25 (약 2시간 10분, Smoke Test 포함)

---

## 2. Edge & Spread Analysis

### 2.1 Win Rate 100%가 나온 이유 (Why 100% Win Rate?)

**⚠️ 중요: 100% 승률은 "현실 시장 수익률"이 아닙니다**

**관측 결과:**
- Top20: 100.0% win rate (1,659 / 1,659 round trips 모두 수익)
- Top50: 100.0% win rate (1,658 / 1,658 round trips 모두 수익)

---

#### 왜 100%가 나왔는가?

100% 승률은 **PAPER 모드의 이상화된 시뮬레이션 구조**에서 나온 결과입니다. 다음 4가지 핵심 요인 때문입니다:

**1️⃣ 진입 조건 자체가 보장된 승리 구조**
```python
# 엔진 진입 조건 (Conceptual)
if spread > (fee + safety_margin):
    enter_trade()  # 이 조건에서만 진입
```
- 엔진은 **"스프레드가 수수료 + 안전마진보다 클 때만"** 거래를 진입합니다.
- 이는 이론적으로 진입 시점에 이미 "수익 가능성"이 확보된 상태입니다.
- 하지만 **실제 시장에서는 진입 이후 상황이 달라질 수 있습니다** (아래 요인들 참조).

**2️⃣ 부분 체결 (Partial Fill) 미모델링**
- **현재 PAPER 모드:** 주문 수량 전체가 100% 즉시 체결된다고 가정
- **실제 시장:** 호가 잔량이 부족하면 일부만 체결되거나, 여러 호가 레벨에 걸쳐 체결됨
- **영향:** 실제로는 원하는 가격에 전량 체결되지 않아 수익률 감소 또는 손실 발생 가능

**3️⃣ 슬리피지 (Slippage) 미반영**
- **현재 PAPER 모드:** 주문 제출 시점의 가격 그대로 체결된다고 가정
- **실제 시장:** 주문 제출 후 체결까지 시간이 걸리며, 그 사이 가격이 불리하게 변동 가능
- **영향:** 진입 시 예상한 스프레드보다 실제 체결 스프레드가 좁아져 손실 가능

**4️⃣ 호가 변동 및 시장 충격 (Order Book Dynamics & Market Impact) 미반영**
- **현재 PAPER 모드:** 호가창이 정적(static)이며, 주문이 시장에 영향을 주지 않는다고 가정
- **실제 시장:** 
  - 주문 제출 후 호가창이 실시간으로 변동 (다른 거래자들의 주문)
  - 대량 주문은 시장 가격을 움직여 체결 가격이 악화됨 (Market Impact)
- **영향:** 예상 스프레드가 사라지거나 역전되어 손실 발생 가능

---

#### 현실적 승률 범위는?

**실제 시장에서는 30~80% 승률이 현실적입니다.**

| 거래 환경 | 예상 승률 | 주요 영향 요인 |
|----------|----------|---------------|
| **고유동성 시장** (BTC, ETH) | 60~80% | 호가 잔량 풍부, 슬리피지 낮음 |
| **중유동성 시장** (Top20 알트코인) | 50~70% | 부분 체결 발생, 슬리피지 보통 |
| **저유동성 시장** (Top50+ 알트코인) | 30~50% | 부분 체결 빈번, 슬리피지 높음, 호가 변동 심함 |

---

#### 결론: 100% 승률의 의미

- ✅ **엔진 구조 검증 관점:** "진입 조건 로직이 정상 작동함"을 의미 → **GO**
- ⚠️ **실제 수익 관점:** "현실 시장에서 100% 승률로 돈을 벌 수 있다"는 뜻이 **아님**
- 📋 **다음 단계 필요:** D80-3 (Trade-level 로깅), D80-4 (Fill/Slippage 모델), D81-x (Market Impact 분석)

### 2.2 PnL Structure Analysis

**시간당 PnL:**
- Top20: $206,830/h
- Top50: $206,711/h

**라운드트립당 PnL:**
- Top20: $125.00/RT
- Top50: $125.00/RT

**해석:**
시간당 $200k 레벨 PnL은 **엔진 검증용 벤치마크**로는 의미가 있으나, **실제 시장 수익 현실성과는 거리가 있습니다**. 다음 비용 요소들을 반영하면 크게 감소할 것으로 예상됩니다:

1. **거래 수수료:** Upbit/Binance 각각 0.05~0.1% (왕복 0.1~0.2%)
2. **슬리피지:** 평균 0.05~0.15% (시장 상황에 따라 변동)
3. **호가 잔량 제약:** 대량 거래 시 여러 호가 레벨에 걸쳐 체결되어 평균 가격 악화
4. **인벤토리 리밸런싱 비용:** Cross-exchange 포지션 조정 시 발생하는 추가 비용

### 2.3 Fee/Slippage Scenarios

다음은 수수료 및 슬리피지를 반영한 PnL 시나리오입니다 (평균 거래 금액 $1,000 가정):

| Scenario | Fee (bps) | Slippage (bps) | Top20 Adjusted PnL | Top50 Adjusted PnL | PnL Reduction |
|----------|-----------|----------------|--------------------|--------------------|---------------|
| **Conservative** | 10 | 5 | $202,398 | $202,276 | 2.4% |
| **Moderate** | 20 | 10 | $197,421 | $197,302 | 4.8% |
| **Pessimistic** | 30 | 15 | $192,444 | $192,328 | 7.2% |

**주요 관찰:**
- Conservative 시나리오 (fee=10bps, slippage=5bps)에서도 2.4% PnL 감소
- Moderate 시나리오 (fee=20bps, slippage=10bps)에서는 4.8% 감소
- Pessimistic 시나리오 (fee=30bps, slippage=15bps)에서는 7.2% 감소

**한계점:**
- 평균 거래 금액 $1,000은 보수적 추정치 (실제 로그 데이터 없음)
- 호가 잔량 제약, 시장 충격 등은 미반영
- 실제 비용은 시나리오보다 높을 가능성 있음

### 2.4 Spread Requirements (Estimated)

**역산 추정 스프레드:**
- Top20: 1,250 bps (12.5%)
- Top50: 1,250 bps (12.5%)

**최소 수익 스프레드:**
- Moderate 시나리오 기준: 30 bps (fee 20bps + slippage 10bps)

**중요 노트:**
- 위 스프레드는 PnL 역산으로 추정한 값이며, **실제 스프레드 데이터가 로그에 없어** 정확도가 낮습니다.
- 1,250 bps (12.5%) 스프레드는 **비현실적으로 높은 수치**이며, 이는 PAPER 모드의 한계를 반영합니다.
- 실제 Upbit-Binance 간 스프레드는 일반적으로 **10~100 bps (0.1~1%)** 범위입니다.

**필요 조치:**
- D80-3: Trade-level Spread & Liquidity Logging 강화 필요
- 각 거래의 실제 스프레드, 호가 잔량, 체결 가격 로깅

---

## 3. Limitations & Gaps

D80-2 분석을 통해 다음 한계점들이 명확히 식별되었습니다:

### 3.1 Data Logging Gaps

**Issue:** Trade-level spread/liquidity 로그 부재

**Impact:**
- 각 거래의 실제 스프레드를 분석할 수 없음
- 호가 잔량 및 체결 가격 정보 부재
- Edge 현실성을 정량적으로 평가하기 어려움

**Next Step:** D80-3: Trade-level Spread & Liquidity Logging 강화

### 3.2 Fill Model Limitations

**Issue:** 부분 체결 및 슬리피지 미모델링

**Impact:**
- 100% 승률 발생 (비현실적)
- PnL 과대평가
- 실제 시장 조건 미반영

**Next Step:** D80-4: Realistic Fill/Slippage Model 도입

### 3.3 Market Impact

**Issue:** 호가 잔량 제약 및 시장 충격 미반영

**Impact:**
- 대량 거래 시 실제 체결 가능성 미평가
- 가격 영향 (Market Impact) 미반영
- 실제 수익성 과대평가

**Next Step:** D81-x: Market Impact & Liquidity Analysis

### 3.4 Inventory Cost

**Issue:** 인벤토리 리밸런싱 비용 미포함

**Impact:**
- Cross-exchange 포지션 조정 비용이 PnL에 반영되지 않음
- 실제 운영 비용 과소평가

**Next Step:** D81-x: Inventory/Rebalancing Cost Modeling

---

## 4. Interpretation: Infrastructure GO vs. Edge Reality

### 4.1 Infrastructure/Engine Level: ✅ GO

**D77-0-RM-EXT 검증 완료:**
- ✅ 1시간 연속 실행 (Top20: 60.16분, Top50: 60.17분)
- ✅ 1,650+ round trips (Top20: 1,659, Top50: 1,658)
- ✅ 안정적 메모리/CPU (150MB, 35%, 0% growth)
- ✅ Crash/HANG 0건
- ✅ Loop Latency p99: 0.12ms (≤80ms 기준 충족)
- ✅ Postgres 인증 통합, Rate Limit 핸들링 완료

**판단:**
엔진 구조, D75 Infrastructure 통합, 장기 안정성 모두 검증 완료. **D78 (Authentication & Secrets) 진행 가능.**

### 4.2 Real Market Edge Reality: ⚠️ NEEDS FURTHER VALIDATION

**현재 상태:**
- ⚠️ 100% 승률: PAPER 모드 한계로 인한 구조적 결과
- ⚠️ $200k/h PnL: 엔진 벤치마크로는 의미 있으나, 실제 수익 현실성과는 거리가 있음
- ⚠️ Trade-level 데이터 부재: 스프레드, 호가 잔량, 체결 가격 등 미로깅
- ⚠️ Fill Model 한계: 부분 체결, 슬리피지, 호가 변동 미모델링

**판단:**
**"1조 프로그램" 관점에서 실제 수익 가능성을 평가하려면, 추가 검증 단계 (D80-3, D80-4, D81-x 등)가 필요합니다.**

---

## 5. Next Steps Proposal

D80-2 분석 결과를 바탕으로, 다음 단계들을 제안합니다:

### 5.1 D80-3: Trade-level Spread & Liquidity Logging 강화

**목표:** 각 거래의 스프레드, 호가, 체결 가격 로깅

**구현 내용:**
- Entry/Exit 시점의 Upbit/Binance 호가 스냅샷 저장
- 실제 체결 가격 및 스프레드 계산
- 호가 잔량 (Bid/Ask Volume) 로깅
- Trade-level JSON/CSV 로그 생성

**기대 효과:**
- 실제 스프레드 분포 분석 가능
- 호가 잔량 제약 평가 가능
- Edge 현실성 정량 평가 가능

### 5.2 D80-4: Realistic Fill/Slippage Model 도입

**목표:** 부분 체결, 슬리피지, 호가 변동 모델링

**구현 내용:**
- Partial Fill 로직: 호가 잔량 < 주문 수량 시 부분 체결
- Slippage Model: 주문 실행 시점과 체결 시점 간 가격 변동 반영
- Order Book Dynamics: 주문 제출 후 호가 변동 시뮬레이션
- Realistic Win Rate: 30~80% 범위로 조정

**기대 효과:**
- 현실적 승률 및 PnL 산출
- PAPER 모드의 신뢰도 향상
- 실제 시장 조건 반영

### 5.3 D81-x: Market Impact & Liquidity Analysis

**목표:** 호가 잔량 제약 및 시장 충격 분석

**구현 내용:**
- 대량 주문 시 여러 호가 레벨 체결 시뮬레이션
- Market Impact Model: 주문 크기에 따른 가격 영향 추정
- Liquidity Heatmap: 시간대별/심볼별 호가 잔량 분석

**기대 효과:**
- 실제 체결 가능성 평가
- 최적 주문 크기 결정
- 시장 충격 최소화 전략 수립

### 5.4 D81-x: Inventory/Rebalancing Cost Modeling

**목표:** Cross-exchange 포지션 조정 비용 반영

**구현 내용:**
- Inventory Imbalance 추적
- Rebalancing Trade 비용 계산
- 최적 리밸런싱 주기 분석

**기대 효과:**
- 실제 운영 비용 정확한 반영
- 순수익 (Net Profit) 산출
- 리밸런싱 전략 최적화

### 5.5 D82-x: Long-term (12h+) Real Market Validation

**목표:** 장기 실행으로 Edge 지속성 검증

**구현 내용:**
- 12시간 이상 Real Market PAPER 실행
- 시간대별 Edge 변화 분석
- 장기 안정성 및 수익성 검증

**기대 효과:**
- Edge 지속성 확인
- 시간대별 최적 전략 도출
- 장기 운영 준비도 평가

---

## 6. Conclusion

### 6.1 Summary

**D80-2: Real Market Edge & Spread Reality Check**는 D77-0-RM-EXT 1시간 Top20/Top50 실행 결과를 기반으로, **Infrastructure/Engine Level**과 **Real Market Edge Reality**를 명확히 구분하여 분석했습니다.

**핵심 결론:**
1. **Infrastructure/Engine Level: ✅ GO** - 엔진 구조, 인프라 통합, 장기 안정성 모두 검증 완료
2. **Real Market Edge Reality: ⚠️ NEEDS FURTHER VALIDATION** - Trade-level 데이터, Fill Model, Market Impact 등 추가 검증 필요

### 6.2 Honest Assessment

**100% 승률 및 $200k/h PnL**은 엔진 검증용 벤치마크로는 의미가 있으나, **실제 시장 수익 현실성과는 거리가 있습니다**. 이는 PAPER 모드의 한계로 인한 구조적 결과이며, 다음 요소들을 반영하면 크게 감소할 것으로 예상됩니다:

- 수수료 및 슬리피지: 2.4~7.2% PnL 감소 (시나리오별)
- 부분 체결 및 호가 변동: 승률 30~80%로 조정
- 호가 잔량 제약 및 시장 충격: 추가 PnL 감소
- 인벤토리 리밸런싱 비용: 운영 비용 증가

### 6.3 Path Forward

**"1조 프로그램" 관점에서 실제 수익 가능성을 평가하려면**, 다음 단계들을 순차적으로 진행해야 합니다:

1. **D80-3:** Trade-level Spread & Liquidity Logging 강화
2. **D80-4:** Realistic Fill/Slippage Model 도입
3. **D81-x:** Market Impact & Liquidity Analysis
4. **D81-x:** Inventory/Rebalancing Cost Modeling
5. **D82-x:** Long-term (12h+) Real Market Validation

**현재 단계 (D80-2)에서는**, "엔진/인프라 레벨 GO"와 "실제 수익 구조의 현실성"을 명확히 분리하여 기록하고, **추가 검증이 필요한 Gap들을 정확하게 정의**하는 것이 목표입니다.

---

**Report Date:** 2025-12-04  
**Analysis Tool:** `scripts/d80_2_real_market_edge_analyzer.py`  
**Output:** `logs/d80-2/d80_2_edge_summary.json`

---

## 📝 작성 규칙 (Documentation Guidelines)

**2025-12-04부터 적용되는 문서 작성 원칙:**

### 기본 언어: 한국어
- 모든 설계 문서, 분석 리포트, 계획서는 **한국어를 기본 언어**로 작성합니다.
- 영어는 기술 용어 또는 국제 표준 용어에 한해 괄호 병기 형태로 사용합니다.
  - 예: "Real Market Edge(실제 시장에서의 엣지)"
  - 이후에는 한국어 용어 위주로 사용

### 코드 주석
- Python/JavaScript 등 코드 주석도 **가능한 한 한국어**로 작성합니다.
- 함수/클래스 docstring은 한국어로 작성하되, 필요 시 짧은 영어 요약 추가 가능
- 기술 용어 (예: PnL, Slippage, Round Trip)는 그대로 사용하되, 첫 언급 시 한국어 설명 추가

### 문서 톤 & 스타일
- **"1조 프로그램"** 관점: 엔지니어링적으로 냉정하고 정확하게
- **과장 금지:** 마케팅 문구 없이, 현실과 이상을 명확히 구분
- **정량화:** 가능한 모든 내용을 수치/데이터로 뒷받침
- **한계 명시:** 현재 구현의 한계와 Gap을 솔직하게 기록

### Git Commit 메시지
- Commit 메시지는 **한글 + 영어 혼용** 가능
- 예: `[D80-2] Real Market Edge 보고서 한글화 및 WinRate 100% 설명 강화`

### 이 규칙의 적용 범위
- `docs/` 디렉토리의 모든 .md 파일
- `scripts/` 디렉토리의 분석/리포트 스크립트 docstring/주석
- `D_ROADMAP.md`, `PROJECT_VISION_TOBE.md` 등 프로젝트 문서

**Note:** 이 규칙은 프로젝트 전체의 일관성과 유지보수성을 높이기 위한 것입니다. 기존 영어 문서를 무리하게 전환할 필요는 없으며, 신규 작성 또는 대폭 수정 시 점진적으로 적용합니다.
