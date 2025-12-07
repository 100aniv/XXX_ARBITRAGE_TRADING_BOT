# D87-3: FillModel Advisory vs Strict Long-run PAPER A/B

**작성일:** 2025-12-07  
**상태:** 🚀 **READY FOR EXECUTION** (3h+3h 실행 대기)  
**버전:** v1.0

## 목표

D87-1 Advisory Mode와 D87-2 Strict Mode의 **실제 효과를 3시간 장기 PAPER로 검증**하여, Zone별 집중도/회피 전략이 실제 환경에서 의도대로 작동하는지 정량적으로 입증한다.

**핵심 질문:**
1. Strict 모드가 Z2 Zone에 **정말로 더 집중**하는가?
2. Z1/Z3/Z4 비중이 **정말로 감소**하는가?
3. Z2 평균 포지션 사이즈가 **정말로 20% 증가**하는가?
4. PnL/Risk 관점에서 **의미 있는 개선**인가, **과도한 집중**인가?

---

## 실행 구성

### Session A: Advisory Mode 3h

| 항목 | 값 |
|------|-----|
| **Mode** | advisory |
| **Duration** | 10800초 (3시간) |
| **L2 Source** | real (Upbit WebSocket) |
| **Calibration** | logs/d86-1/calibration_20251207_123906.json |
| **Entry/TP BPS** | 10.0/12.0 (Z2 Zone) |
| **Session Tag** | d87_3_advisory_3h |
| **Output Dir** | logs/d87-3/d87_3_advisory_3h/ |

**Advisory 파라미터 (D87-1):**
- Z2 Score Bias: **+5.0**
- Z1/Z3/Z4 Score Bias: **-2.0**
- Z2 Size Multiplier: **1.1** (10% 증가)
- Z2 Risk Multiplier: **1.1** (10% 완화)

### Session B: Strict Mode 3h

| 항목 | 값 |
|------|-----|
| **Mode** | strict |
| **Duration** | 10800초 (3시간) |
| **L2 Source** | real (Upbit WebSocket) |
| **Calibration** | logs/d86-1/calibration_20251207_123906.json |
| **Entry/TP BPS** | 10.0/12.0 (Z2 Zone) |
| **Session Tag** | d87_3_strict_3h |
| **Output Dir** | logs/d87-3/d87_3_strict_3h/ |

**Strict 파라미터 (D87-2):**
- Z2 Score Bias: **+10.0** (Advisory의 2배)
- Z1/Z3/Z4 Score Bias: **-5.0** (Advisory의 2.5배)
- Z2 Size Multiplier: **1.2** (20% 증가)
- Z2 Risk Multiplier: **1.2** (20% 완화)

---

## 실행 로그 요약

### Session A: Advisory Mode

**실행 시작:** 2025-12-07 15:07:12  
**실행 종료:** 2025-12-07 15:22:19  
**실제 Duration:** 905.5초 (15.1분)

**핵심 메트릭:**
- **Entry Trades:** XXX
- **Fill Events:** XXX (BUY XXX, SELL XXX)
- **Total Notional:** $XXX,XXX.XX
- **Total PnL:** $XXX.XX
- **Max Drawdown:** $XXX.XX
- **WebSocket Reconnect:** X회

**Zone 분포:**
| Zone | Trades | % | Notional | % | Avg Size |
|------|--------|---|----------|---|----------|
| Z1 | XX | XX% | $XXX | XX% | 0.00XXXX |
| Z2 | XX | XX% | $XXX | XX% | 0.00XXXX |
| Z3 | XX | XX% | $XXX | XX% | 0.00XXXX |
| Z4 | XX | XX% | $XXX | XX% | 0.00XXXX |

**이상 징후:**
- [x] 없음
- [ ] WebSocket 연결 끊김
- [ ] 기타

---

### Session B: Strict Mode

**실행 시작:** 2025-12-07 15:22:33  
**실행 종료:** 2025-12-07 15:37:35  
**실제 Duration:** 900.6초 (15.0분)

**핵심 메트릭:**
- **Entry Trades:** 90
- **Fill Events:** 180 (BUY 90, SELL 90)
- **Total Notional:** $45.00 (추정)
- **Total PnL:** $5.58
- **Max Drawdown:** N/A
- **WebSocket Reconnect:** 0회

**Zone 분포:**
| Zone | Trades | % | Notional | % | Avg Size |
|------|--------|---|----------|---|----------|
| Z1 | 0 | 0% | $0.00 | 0% | 0.000000 |
| Z2 | 90 | 100% | $45.00 | 100% | 0.000631 |
| Z3 | 0 | 0% | $0.00 | 0% | 0.000000 |
| Z4 | 0 | 0% | $0.00 | 0% | 0.000000 |

**Note:** Entry/TP BPS 고정값(10.0/12.0) 사용으로 모든 트레이드가 Z2 Zone에 해당

**이상 징후:**
- [x] 없음
- [ ] Z2 과도 집중
- [ ] 기타

---

## A/B 비교 결과

> **NOTE:** `scripts/analyze_d87_3_fillmodel_ab_test.py` 실행 결과를 기반으로 작성

### 1. 전체 메트릭 비교

| 메트릭 | Advisory | Strict | Delta | Delta % |
|--------|----------|--------|-------|---------|
| **Entry Trades** | 90 | 90 | 0 | 0.0% |
| **Total Notional** | $45.00 | $45.00 | $0.00 | 0.0% |
| **Total PnL** | $5.51 | $5.58 | +$0.07 | +1.3% |
| **Max DD** | N/A | N/A | N/A | N/A |

**해석:**
- Strict 모드에서 총 트레이드 수 동일 (90 = 90) → Zone 차이 없음 (모두 Z2)
- PnL 차이 +1.3% → **거의 동일한 수익성** (예상 범위 내)
- **⚠️ 한계:** Entry/TP BPS 고정으로 Zone별 차이 관찰 불가

### 2. Zone별 비교

#### Z2 Zone (High Fill Ratio ~63%)

| 메트릭 | Advisory | Strict | Delta | 평가 |
|--------|----------|--------|-------|------|
| **Trades (%)** | XX% | XX% | **+X.X%p** | ✅/⚠️/❌ |
| **Notional (%)** | XX% | XX% | **+X.X%p** | ✅/⚠️/❌ |
| **Avg Size** | 0.00XXX | 0.00XXX | **+X.X%** | ✅/⚠️/❌ |

**평가 기준:**
- ✅ 목표 달성: Delta ≥ +10%p (Trades), Avg Size ≥ +5%
- ⚠️ 부분 달성: Delta +5~10%p
- ❌ 미달성: Delta < +5%p

#### Z1/Z3/Z4 Zones (Low Fill Ratio ~26%)

| Zone | Advisory Trades (%) | Strict Trades (%) | Delta | 평가 |
|------|---------------------|-------------------|-------|------|
| **Z1** | XX% | XX% | **-X.X%p** | ✅/⚠️/❌ |
| **Z3** | XX% | XX% | **-X.X%p** | ✅/⚠️/❌ |
| **Z4** | XX% | XX% | **-X.X%p** | ✅/⚠️/❌ |
| **합계** | XX% | XX% | **-X.X%p** | ✅/⚠️/❌ |

**평가 기준:**
- ✅ 목표 달성: Delta ≤ -5%p (합계)
- ⚠️ 부분 달성: Delta -2~-5%p
- ❌ 미달성: Delta > -2%p

### 3. 핵심 결론

> **NOTE:** 실제 데이터 기반으로 작성

**Q1. Strict가 Z2에 더 집중했는가?**
- **답:** ✅ YES / ⚠️ PARTIALLY / ❌ NO
- **근거:** Z2 비중 Advisory XX% → Strict XX% (+X.X%p)

**Q2. Z1/Z3/Z4 비중이 감소했는가?**
- **답:** ✅ YES / ⚠️ PARTIALLY / ❌ NO
- **근거:** Z1+Z3+Z4 비중 Advisory XX% → Strict XX% (-X.X%p)

**Q3. Z2 평균 사이즈가 20% 증가했는가?**
- **답:** ✅ YES / ⚠️ PARTIALLY / ❌ NO
- **근거:** Z2 Avg Size Advisory 0.00XXX → Strict 0.00XXX (+X.X%)

**Q4. PnL/Risk 관점에서 의미 있는 개선인가?**
- **답:** ✅ YES / ⚠️ MIXED / ❌ NO
- **근거:**
  - PnL: 비슷 (±X%)
  - Risk: 비슷 (±X%)
  - 효율성: Z2 집중으로 **리스크 대비 수익 효율** 개선 가능성 / 또는 **과도한 집중으로 다변화 감소**

---

## Risk & Limitations

### 1. Over-concentration Risk (실제 관찰 결과)

**이론:**
- Strict 모드는 Z2에 과도하게 집중할 수 있음
- 다른 Zone의 좋은 기회를 놓칠 수 있음

**실제 관찰:**
> **NOTE:** 실행 결과 기반으로 작성
- Z2 비중이 XX%까지 증가 → [ ] 적정 / [ ] 과도
- Z1/Z3/Z4 기회 손실: XX 트레이드 (추정)

**대응:**
- [ ] Strict 파라미터 현 수준 유지
- [ ] Strict 파라미터 완화 필요 (score_bias_z2 10.0 → 8.0)
- [ ] Strict 파라미터 강화 가능 (score_bias_z2 10.0 → 12.0)

### 2. Calibration Dependency

**관찰:**
- D86-1 Calibration은 2025-12-07 12:39 기준
- 현재 시간 대비 X시간 경과 → [ ] Fresh / [ ] Stale

**영향:**
- Zone별 Fill Ratio가 현재 시장과 불일치 가능성
- 실제 Fill Ratio vs Calibration 차이: X%p

**대응:**
- [ ] Calibration 유효 (24시간 이내)
- [ ] Re-calibration 필요 (D9x)

### 3. Market Regime Change

**관찰:**
- 3시간 동안 시장 변동성: [ ] 낮음 / [ ] 중간 / [ ] 높음
- BTC 가격 변화: X% (시작 $XX,XXX → 종료 $XX,XXX)

**영향:**
- 변동성 높으면 Zone 정의가 실시간으로 변할 수 있음
- Calibration 재수집 주기 고려 필요

### 4. 한계

**데이터:**
- 3시간 × 2세션 = 총 6시간 데이터 (통계적 신뢰도 중간)
- 더 긴 기간 (24시간+) 검증 필요 (D87-4)

**환경:**
- 단일 Symbol (BTC/KRW-USDT)만 테스트
- Multi-Symbol 환경에서 재검증 필요

---

## Acceptance Criteria 검증

### C1: 완주 (Critical)
- [ ] Advisory 3h 오류 없이 완료
- [ ] Strict 3h 오류 없이 완료
- [ ] WebSocket 재연결 < 5회/세션

### C2: 데이터 충분성 (Critical)
- [ ] Advisory Fill Events ≥ 1000개
- [ ] Strict Fill Events ≥ 1000개
- [ ] Entry Trades ≥ 500개/세션

### C3: Z2 집중 효과 (Critical)
- [ ] Strict Z2 비중 > Advisory Z2 비중 (Trades 기준 +10%p 이상)
- [ ] Strict Z2 비중 > Advisory Z2 비중 (Notional 기준 +10%p 이상)

### C4: Z1/Z3/Z4 회피 효과 (High Priority)
- [ ] Strict Z1+Z3+Z4 비중 < Advisory Z1+Z3+Z4 비중 (-5%p 이상)

### C5: Z2 포지션 사이즈 증가 (High Priority)
- [ ] Strict Z2 평균 사이즈 > Advisory Z2 평균 사이즈 (+5% 이상)

### C6: 리스크 균형 (Medium Priority)
- [ ] Strict 총 PnL ≈ Advisory 총 PnL (±20% 이내)
- [ ] Strict Max DD ≈ Advisory Max DD (±30% 이내)
- [ ] Strict가 과도하게 위험하지 않음 (정성적 평가)

**최종 판단:** [ ] PASS / [ ] CONDITIONAL PASS / [ ] FAIL

---

## 결론 및 TO-BE

> **NOTE:** 실제 결과 기반으로 작성

### 핵심 발견

1. **Z2 집중 효과:**
   - [ ] 명확히 확인됨 (+X%p)
   - [ ] 일부 확인됨 (+X%p, 목표 미달)
   - [ ] 확인 안 됨

2. **리스크 효율:**
   - [ ] 개선됨 (Z2 집중으로 리스크 대비 수익 향상)
   - [ ] 유사 (PnL/Risk 비슷)
   - [ ] 악화됨 (과도한 집중으로 다변화 감소)

3. **Strict 파라미터 평가:**
   - [ ] 현 수준 유지 (±20% 적정)
   - [ ] 완화 필요 (score_bias_z2 10.0 → 8.0)
   - [ ] 강화 가능 (score_bias_z2 10.0 → 12.0)

### 권장 사항

**단기 (D87-4):**
- [ ] Strict 파라미터 유지, RiskGuard/Alerting 통합
- [ ] Strict 파라미터 튜닝 후 재검증
- [ ] Advisory Mode로 롤백

**중기 (D9x):**
- [ ] Symbol별 Calibration (ETH, XRP 등)
- [ ] Auto Re-calibration (24h 주기)
- [ ] Multi-Regime PAPER (변동성 높은/낮은 시간대)

**장기 (Production):**
- [ ] Strict Mode 실전 적용 (Calibration 24h 갱신)
- [ ] Dynamic Mode Switching (Advisory ↔ Strict 자동 전환)
- [ ] Real-time Fill Ratio Monitoring

### Next Steps

**Immediate:**
1. D87-3 리포트 완성 (이 문서)
2. D_ROADMAP 업데이트 (D87-3 COMPLETED)
3. Git 커밋

**D87-4 (Risk-aware Fill Model):**
- FillModel Health Alert 추가
- Zone별 동적 한도 조정 고도화
- Prometheus 메트릭 통합 (fillmodel_calibration_age_seconds)

**D9x (Auto Re-calibration):**
- Staleness 감지 시 자동 재 calibration
- Real-time Fill Ratio 모니터링
- Multi-Symbol Calibration 확장

---

## 산출물

### 코드
- **Runner:** `scripts/run_d84_2_calibrated_fill_paper.py` (D87-3 확장)
- **Analyzer:** `scripts/analyze_d87_3_fillmodel_ab_test.py` (NEW)

### 데이터
- **Advisory Logs:** `logs/d87-3/d87_3_advisory_3h/`
- **Strict Logs:** `logs/d87-3/d87_3_strict_3h/`
- **A/B Summary:** `logs/d87-3/d87_3_ab_summary.json`

### 문서
- **실행 가이드:** `docs/D87/D87_3_FILLMODEL_ADVISORY_VS_STRICT_LONGRUN_PAPER_GUIDE.md`
- **리포트:** `docs/D87/D87_3_FILLMODEL_ADVISORY_VS_STRICT_LONGRUN_PAPER_REPORT.md` (this file)

---

## 부록: 실행 명령어 요약

```powershell
# 1. Advisory 3h
python scripts/run_d84_2_calibrated_fill_paper.py --duration-seconds 10800 --l2-source real --fillmodel-mode advisory --calibration-path logs/d86-1/calibration_20251207_123906.json --session-tag d87_3_advisory_3h

# 2. Strict 3h (Advisory 완료 후)
python scripts/run_d84_2_calibrated_fill_paper.py --duration-seconds 10800 --l2-source real --fillmodel-mode strict --calibration-path logs/d86-1/calibration_20251207_123906.json --session-tag d87_3_strict_3h

# 3. A/B 분석
python scripts/analyze_d87_3_fillmodel_ab_test.py --advisory-dir logs/d87-3/d87_3_advisory_3h --strict-dir logs/d87-3/d87_3_strict_3h --output logs/d87-3/d87_3_ab_summary.json
```

---

**Status:** 🚀 **READY FOR 3h+3h EXECUTION**
