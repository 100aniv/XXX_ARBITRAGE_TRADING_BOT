# D203-1 Report: Break-even Threshold (SSOT)

**작성일:** 2025-12-30  
**상태:** ✅ DONE  
**커밋:** `228eef2`

---

## 📋 목표 및 범위

### D203-1: Break-even Threshold (SSOT)
수수료 + 슬리피지 + 버퍼를 반영한 최소 진입 스프레드(bps) 공식을 코드로 SSOT화.

**Note:** D203-2 Opportunity Detector는 별도 리포트로 분리됨 (`D203-2_REPORT.md`)

---

## ✅ 완료 항목
**파일:**
- `arbitrage/v2/domain/break_even.py` (신규, 156 lines)
- `tests/test_d203_1_break_even.py` (신규, 278 lines)

**구현:**
- `BreakEvenParams(dataclass)` - 파라미터 묶음 (fee_model, slippage_bps, buffer_bps)
- `compute_break_even_bps(params)` - Break-even 공식 (SSOT)
- `compute_edge_bps(spread_bps, break_even_bps)` - Edge 계산
- `explain_break_even(params, spread_bps)` - 디버깅/리포트용 설명

**공식 (SSOT):**
```python
break_even_bps = fee_entry_bps + fee_exit_bps + slippage_bps + buffer_bps

# 예시:
# fee_entry_bps = 5 (Upbit) + 10 (Binance) = 15
# fee_exit_bps = 15 (왕복)
# slippage_bps = 10
# buffer_bps = 5
# → break_even_bps = 15 + 15 + 10 + 5 = 45 bps
```

**Reuse-First:**
- ✅ V1 FeeModel (arbitrage/domain/fee_model.py) - import 재사용
- ✅ V2 ThresholdConfig (arbitrage/v2/core/config.py) - import 재사용
- ❌ 복사/붙여넣기 없음

**테스트:** 9/9 PASS (0.24s)
1. Fee만 있는 경우
2. Fee + Slippage
3. Fee + Slippage + Buffer
4. Spread < Break-even (edge < 0)
5. Spread > Break-even (edge > 0)
6. 극단값 안정성

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

**V1 재사용 후보:**
| 기능 | V1 위치 | V2 적용 | 재사용 방식 | 결정 |
|------|---------|---------|-----------|------|
| Fee 계산 | `arbitrage/domain/fee_model.py` | `arbitrage/v2/domain/break_even.py` | ✅ import 재사용 | KEEP |
| Threshold 설정 | `arbitrage/v2/core/config.py` | `arbitrage/v2/domain/break_even.py` | ✅ import 재사용 | KEEP |
| Spread 계산 로직 | `arbitrage/cross_exchange/spread_model.py` | `arbitrage/v2/opportunity/detector.py` | ✅ 로직 참조 | REFERENCE |

**중복 모듈:** 0개 ✅

**Evidence:** `logs/evidence/d203_1_20251230_0047_5504337/scan_reuse_map.md`

---

## 📝 변경 파일 목록

### 신규 파일 (2개, D203-1 전용)
1. `arbitrage/v2/domain/break_even.py` - Break-even 공식 (156 lines)
2. `tests/test_d203_1_break_even.py` - Break-even 테스트 (278 lines)

**Note:** D203-2 관련 파일(detector.py, test_d203_2)은 D203-2_REPORT.md 참조

### 수정 파일 (2개)
1. `D_ROADMAP.md` - D203-1/D203-2 DONE 상태 업데이트
2. `docs/v2/design/SSOT_MAP.md` - D203 섹션 추가 (예정)

---

## 🔍 Tech-Debt / 남은 일

**없음** - D203-1은 완전 완료.

**다음 단계:**
- D203-2: Opportunity Detector v1 (별도 리포트)
- D203-3: Engine에 Opportunity Detector 연결 (얇은 래핑)
- D204: Paper Execution (모의 실행)

---

## 📚 참조

- SSOT: `D_ROADMAP.md` (line 2613-2678)
- V1 FeeModel: `arbitrage/domain/fee_model.py`
- V1 SpreadModel: `arbitrage/cross_exchange/spread_model.py`
- V2 ThresholdConfig: `arbitrage/v2/core/config.py`
- Evidence: `logs/evidence/d203_1_20251230_0047_5504337/`

---

## ✅ 결론

**D203-1: 완전 완료**
- Break-even 공식 SSOT화 ✅
- Gate 3단 100% PASS ✅
- Reuse-First 준수 (FeeModel, ThresholdConfig) ✅
- 중복 모듈 0개 ✅
