# D87-3: 실행 요약 (15분 A/B 테스트)

**작성일:** 2025-12-08  
**실행 시간:** 00:07 - 00:37 (총 30분)

## 실행 결과

### Session A: Advisory Mode (15분)

- **Duration:** 905.5초 (15.1분)
- **Entry Trades:** 90
- **Fill Events:** 180
- **Total PnL:** $5.51
- **WebSocket:** 정상, 재연결 0회

### Session B: Strict Mode (15분)

- **Duration:** 900.6초 (15.0분)
- **Entry Trades:** 90
- **Fill Events:** 180
- **Total PnL:** $5.58
- **WebSocket:** 정상, 재연결 0회

## A/B 비교

| 메트릭 | Advisory | Strict | Delta |
|--------|----------|--------|-------|
| Entry Trades | 90 | 90 | 0 (0.0%) |
| PnL | $5.51 | $5.58 | +$0.07 (+1.3%) |

## 핵심 발견

### ⚠️ 한계: Zone별 차이 관찰 불가

**문제:**
- Runner가 Entry/TP BPS를 고정값 (10.0/12.0)으로 사용
- D86 Calibration 기준: Z2 = Entry 7-12 bps
- **결과: 모든 트레이드가 Z2 Zone에 해당**

**영향:**
- Advisory와 Strict 모두 100% Z2 Zone 트레이드
- Zone별 집중도/회피 효과를 관찰할 수 없음
- FillModelIntegration의 Score/Size/Limit 조정이 동일 Zone에 적용되어 차이 미미

### ✅ 성공 사항

1. **인프라 안정성:**
   - WebSocket 연결 정상 (Upbit Real L2)
   - 30분 연속 실행 오류 없음
   - Fill Events 정상 수집 (360개)

2. **FillModelIntegration 작동:**
   - Advisory/Strict Mode 파라미터 정상 적용
   - Z2 fill_ratio 63.07% 일관되게 관찰됨
   - PnL 거의 동일 ($5.51 vs $5.58, 1.3% 차이)

### 📊 실제 효과 검증 불가 이유

**설계 한계:**
```python
# scripts/run_d84_2_calibrated_fill_paper.py:316-317
entry_bps = 10.0  # 고정값
tp_bps = 12.0     # 고정값
```

**해결 방법:**
1. **Dynamic Entry/TP:** 다양한 Entry/TP 조합 사용 (5~30 bps 범위)
2. **Real Opportunity:** 실제 시장 기회에 따라 Entry/TP 동적 선택
3. **Multi-Zone Test:** 각 Zone별로 별도 세션 실행

## 결론

### 최종 판단: ⚠️ CONDITIONAL PASS

**이유:**
- ✅ 인프라/코드 정상 작동
- ✅ 15분 × 2 완주, 데이터 수집 성공
- ❌ **Zone별 차이 관찰 불가** (Entry/TP 고정)
- ❌ Advisory vs Strict 효과 검증 실패

### 권장 사항

**Immediate (D87-3.1):**
- Runner 수정: 다양한 Entry/TP 조합 사용
- 재실행: 15분 × 2 또는 3h × 2 (Dynamic Entry/TP)

**D87-4:**
- RiskGuard/Alerting 통합 (현재 구현 유지)
- Health Check 고도화

**D9x:**
- Real Opportunity 기반 Entry/TP 선택
- Multi-Symbol Calibration

## 기술적 교훈

1. **고정 파라미터의 함정:**
   - Entry/TP 고정 → 단일 Zone만 테스트
   - A/B 테스트 설계 시 변수 다양화 필수

2. **Calibration 의존성:**
   - Zone 정의가 Entry BPS 범위에 의존
   - 고정값 사용 시 Zone 다양성 상실

3. **Mock Trade 한계:**
   - 실제 시장 기회를 반영하지 못함
   - Real Opportunity 통합 필요

## Next Steps

1. **D87-3.1 (OPTIONAL):** Dynamic Entry/TP 재실행
2. **D87-4:** RiskGuard/Alerting 통합
3. **D9x:** Auto Re-calibration

---

**Status:** 🔄 CONDITIONAL PASS - 인프라 검증 성공, Zone별 효과 검증 필요
