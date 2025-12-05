#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D_ROADMAP.md 인코딩 수정 및 D82 블록 재작성

D_ROADMAP.md 파일의 인코딩 문제를 해결하고,
D82 섹션을 실제 결과로 업데이트합니다.
"""

import re
from pathlib import Path


def fix_d_roadmap():
    """D_ROADMAP.md 인코딩 수정 및 D82 블록 재작성"""
    
    roadmap_path = Path("D_ROADMAP.md")
    
    # 1. Read with error handling
    print("Reading D_ROADMAP.md...")
    with open(roadmap_path, "rb") as f:
        raw_bytes = f.read()
    
    # 2. Decode with replace errors
    text = raw_bytes.decode("utf-8", errors="replace")
    print(f"Decoded {len(text)} characters")
    
    # 3. Find D82 section boundaries
    # Start: "### D82-7:" or similar
    # End: "### D83" or "### D80" or similar (next major section)
    
    # Find start of D82 block
    d82_start_pattern = r"### D82-7:"
    d82_start_match = re.search(d82_start_pattern, text)
    
    if not d82_start_match:
        print("WARNING: Could not find D82 section start")
        return False
    
    d82_start_pos = d82_start_match.start()
    print(f"Found D82 start at position {d82_start_pos}")
    
    # Find end of D82 block (next ### section that's not D82)
    # Look for "### D8" or "### D79" or "---" after D82-12
    remaining_text = text[d82_start_pos:]
    
    # Find all ### headers after D82-7
    headers_after = list(re.finditer(r"\n### D\d+", remaining_text))
    
    # Filter to find first non-D82 header
    d82_end_pos_relative = None
    for header_match in headers_after:
        header_text = header_match.group()
        # Check if it's NOT a D82 header
        if not re.match(r"\n### D82-", header_text):
            d82_end_pos_relative = header_match.start()
            print(f"Found D82 end (next section): {header_text.strip()}")
            break
    
    if d82_end_pos_relative is None:
        # D82 might be at the end of file
        d82_end_pos = len(text)
        print("D82 section extends to end of file")
    else:
        d82_end_pos = d82_start_pos + d82_end_pos_relative
    
    # 4. Extract before and after D82
    before_d82 = text[:d82_start_pos]
    after_d82 = text[d82_end_pos:]
    
    # 5. Create new D82 block
    new_d82_block = """### D82-7: Edge Analysis & Threshold Recalibration (TopN + AdvancedFillModel) ✅ COMPLETE (2025-12-05)

**Status:** ✅ **COMPLETE**

**목표:** D82-6 Sweep 결과를 분석하여 이론적 Edge 모델 재계산 및 구조적으로 수익 가능한 Threshold 레인지 발견

**핵심 발견:**
- D82-6의 Entry/TP (0.3~0.7 / 1.0~2.0 bps)는 구조적으로 수익 불가능
- Effective Edge = Spread - Slippage = -1.49 ~ -0.79 bps (모두 음수)
- 평균 슬리피지 2.14 bps > Entry threshold 0.3~0.7 bps

**Threshold 재계산:**
```
min_entry_bps = ceil(p95_slippage + fee + safety_margin) = 14 bps
min_tp_bps = ceil(min_entry + p95_slippage + safety_margin) = 19 bps
```

**D82-7 Sweep 결과 (Entry 14-18, TP 19-25 bps):**
- 9/9 조합 모두 Edge > 0 (구조적 수익 가능)
- 하지만 Entry/TP 너무 높아 거래 기회 부족 (1 entry, 0 round trips)

**산출물:**
- `scripts/analyze_d82_7_edge_and_thresholds.py`
- `tests/test_d82_7_edge_analysis.py` (10/10 PASS)
- `docs/D82_7_EDGE_AND_THRESHOLD_RECALIBRATION.md`

---

### D82-8: Intermediate Threshold Long-run & Runtime Edge Monitor ✅ COMPLETE (2025-12-05)

**Status:** ✅ **COMPLETE**

**목표:** D82-6~D82-7 Gap을 메우는 Intermediate Zone (Entry 10-14, TP 12-20 bps)에서 20분 Long-run 실행

**구현:**
- Runtime Edge Monitor (Rolling Window 50 trades, Edge/PnL 실시간 추적)
- 3개 전략 조합 (Entry [10,12,14] × TP [15,18,20])
- 조합당 20분 실행 (총 60분)

**실행 결과 (60분):**
- Entry 10/TP 15: 7 entries, 6 RT, 0% WR, -$3,498 PnL
- Entry 12/TP 18: 6 entries, 6 RT, 0% WR, -$2,950 PnL
- Entry 14/TP 20: 7 entries, 6 RT, 0% WR, -$4,050 PnL

**핵심 발견:**
- ✅ 거래 발생 확인 (RT=6, D82-7 대비 무한대 개선)
- ❌ TP 15-20 bps는 여전히 도달 불가 (WR=0%, Timeout=100%)
- ❌ PnL 악화 (평균 -$3,500)

**종합 판단:** ⚠️ CONDITIONAL GO - TP Threshold 10-12 bps로 하향 조정 필요

**산출물:**
- `arbitrage/logging/trade_logger.py` (+220 lines)
- `scripts/run_d82_8_intermediate_threshold_longrun.py`
- `tests/test_d82_8_edge_monitor.py` (12/12 PASS)

---

### D82-9: TP 13-15 bps Fine-tuning & Real PAPER Validation ❌ NO-GO (2025-12-05)

**Status:** ❌ **NO-GO**

**목표:** TP 13-15 bps로 재조정하여 거래 활동성 및 수익성 검증

**실행 결과 (5 candidates, 10분):**
- 모든 후보 FAIL (RT=2.2 평균, WR=0%, PnL=-$1,271)
- TP Exit 0% (Timeout 100%)
- Buy Fill Ratio: 26.15% (매우 낮음)

**Root Causes:**
1. Entry/TP thresholds 2-3x higher than D77-4 baseline (~5-10 bps)
2. Minimum cost 13.28 bps exceeds all D82-9 spreads
3. All combinations have Edge < 0
4. Mock Fill Model pessimism (26% buy fill vs D77-4 likely 100%)

**산출물:**
- `docs/D82/D82-9_ANALYSIS.md` (250+ lines)
- `scripts/analyze_d82_9_kpi_deepdive.py`
- `tests/test_d82_9_tp_finetuning.py` (14/14 PASS)

**Next:** D82-10 (Edge model recalibration with D82-9 measured costs)

---

### D82-10: Recalibrated Edge Model & TP/Entry Re-selection ✅ COMPLETE (2025-12-05)

**Status:** ✅ **COMPLETE**

**목표:** D82-9 실측 비용으로 Edge 모델 재보정 및 viable candidates 선정

**D82-9 실측 비용:**
- Slippage: 2.14 bps (per trade)
- Fee: 9.0 bps (Upbit 5 + Binance 4)
- Total Roundtrip Cost: 13.28 bps

**재보정 결과:**
- D82-9 모든 조합: Edge < 0 (FAIL)
- 새 후보 8개 선정 (Entry 12-16, TP 16-18 bps)
- Top 5 candidates: Edge +0.73 ~ +3.73 bps

**Top 5 Recommended:**
1. Entry 16, TP 18: Edge +3.73 bps (highest)
2. Entry 14, TP 18: Edge +2.73 bps
3. Entry 16, TP 16: Edge +2.73 bps
4. Entry 12, TP 18: Edge +1.73 bps
5. Entry 14, TP 16: Edge +1.73 bps

**산출물:**
- `docs/D82/D82-10_RECALIBRATED_EDGE_MODEL.md`
- `scripts/recalibrate_d82_edge_model.py`
- `tests/test_d82_10_edge_recalibration.py` (8/8 PASS)
- `logs/d82-10/recalibrated_tp_entry_candidates.json` (8 candidates)

**Tests:** 8/8 PASS (100%)

---

### D82-11: TP/Entry PAPER Validation Pipeline (10m/20m/60m) ❌ NO-GO (2025-12-05)

**Status:** ❌ **NO-GO**

**목표:** D82-10 recalibrated candidates로 3-Phase validation (10m → 20m → 60m)

**Validation 결과:**
- **Phase 1 (10min, Top 3):** ❌ FAIL
  - Round Trips: 3 (target: ≥5)
  - Win Rate: 0% (target: >0%)
  - PnL: -$1,554.77 (target: ≥0)
  - TP Exits: 0% (target: >0%)
  - Timeout: 100%
- **Phase 2/3:** SKIPPED (Phase 1 failure)

**Root Causes:**
1. TP 18 bps 여전히 도달 불가 (0% TP exits, 100% timeout)
2. Entry 14-16 bps 너무 높음 (RT=3 vs D77-4의 27.6 RT/10min)
3. D82-10 Edge theory (+2.73~+3.73 bps) 실전에서 무효화
4. Fill Model issue (Buy Fill 26.15%)

**산출물:**
- `docs/D82/D82-11_VALIDATION_REPORT.md` (500+ lines)
- `scripts/run_d82_11_validation_pipeline.py` (master pipeline, 716 lines)
- `scripts/run_d82_11_smoke_test.py`
- `tests/test_d82_11_validation_pipeline.py` (16/16 PASS)
- `logs/d82-11/d82_11_validation_report.json`

**Tests:** 16/16 PASS + D82-9/10 regression (38/38 total)

**Final Decision:** ❌ NO-GO → D82-12 (Lowered TP/Entry to D77-4 baseline)

---

### D82-12: Lowered TP/Entry Re-baseline (D77-4 Quick Win) ❌ NO-GO (2025-12-06)

**Status:** ❌ **NO-GO** (Full Validation Complete)

**목표:** D77-4 검증된 낮은 threshold (Entry/TP 5-10 bps)로 회귀하여 성능 재현 시도

**Parameter Grid:**
- Entry: [5.0, 7.0, 10.0] bps
- TP: [7.0, 10.0, 12.0] bps
- Valid combinations: 6 (TP > Entry only)
- Edge range: -7.28 ~ -2.28 bps (all negative per D82-10 cost model)

**Hypothesis:** D82-10 cost model 과대 추정, 낮은 TP가 더 자주 도달할 것

**Validation 실행 (2025-12-06 00:40-01:10, 30분):**
- **Phase 1 (10min, Top 3):** ❌ FAIL
  - E10.0/TP12.0: RT=3, WR=0%, TP=0%, Timeout=100%, PnL=-$1,785.85
  - E7.0/TP12.0: RT=3, WR=0%, TP=0%, Timeout=100%, PnL=-$1,780.47
  - E5.0/TP12.0: RT=3, WR=0%, TP=0%, Timeout=100%, PnL=-$1,971.21
  - **All candidates FAIL** (RT < 5, WR = 0%)
- **Phase 2/3:** SKIPPED (Phase 1 failure)

**D77-4 vs D82-12 비교:**
- D77-4 (60min): 1,656 RT, 100% WR, +$8,263.82 PnL
- D82-12 (10min): 3 RT, 0% WR, -$5,537.53 PnL
- **99.8% 성능 저하 (동일한 Threshold인데도 불구하고)**

**핵심 발견:**
1. **Threshold 조정으로는 해결 불가** (D82-11 → D82-12 변화 없음)
2. **TP 12 bps도 0% 도달** (낮춰도 Timeout 100%)
3. **D77-4 재현 완전 실패** (1,656 RT → 3 RT)
4. **Fill Model 이상 징후** (Fill Ratio 0 보고, KPI 계산 문제 의심)

**Root Causes:**
- Fill Model (Buy Fill 26%) 과조정
- L2 Orderbook 부재 (L1만으로는 Fill 판단 불가)
- 시장 조건 변화 (변동성 감소)

**산출물:**
- `docs/D82/D82-12_LOWERED_THRESHOLD_REBASELINE.md`
- `docs/D82/D82-12_VALIDATION_REPORT.md` (실제 결과 반영)
- `scripts/generate_d82_12_lowered_tp_entry_candidates.py`
- `tests/test_d82_12_lowered_threshold_candidates.py` (14/14 PASS)
- `logs/d82-12/lowered_tp_entry_candidates.json` (6 candidates)
- `logs/d82-11/d82_11_summary_600.json` (Phase 1 KPI)
- `logs/d82-11/d82_11_validation_report.json` (Final report)

**Tests:** 14/14 PASS (D82-12) + 52/52 PASS (Total regression D82-9/10/11/12)

**Final Decision:** ❌ **NO-GO** → 근본적 Infrastructure 개선 필요

**Next Steps (Priority):**
1. **D84-x: Fill Model 개선** (우선순위 1) - Buy Fill 26% → 50%+ 달성
2. **D83-x: L2 Orderbook 통합** (우선순위 2) - WebSocket L2 Stream 구축
3. **D82-13: D77-4 조건 재현 실험** - 당시 코드/설정으로 차이점 분석

---

"""
    
    # 6. Combine all parts
    new_text = before_d82 + new_d82_block + after_d82
    
    # 7. Write back as clean UTF-8
    print("Writing updated D_ROADMAP.md...")
    with open(roadmap_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_text)
    
    print(f"✅ D_ROADMAP.md updated successfully")
    print(f"   - Before D82: {len(before_d82)} chars")
    print(f"   - D82 block: {len(new_d82_block)} chars")
    print(f"   - After D82: {len(after_d82)} chars")
    print(f"   - Total: {len(new_text)} chars")
    
    return True


if __name__ == "__main__":
    success = fix_d_roadmap()
    exit(0 if success else 1)
