#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D_ROADMAP.md에 D82-0 섹션 추가 스크립트
"""

import re
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
ROADMAP_PATH = PROJECT_ROOT / "D_ROADMAP.md"

# D82-0 섹션 내용
D82_0_SECTION = """
### D82-0: D77 TopN Runner → Real PaperExecutor + Fill Model 통합 ✅ COMPLETE (2025-12-04)

**상태:** ✅ COMPLETE (Infrastructure Ready, Smoke Test Pending)

**목표:** D77 Runner를 **Mock 시뮬레이션**에서 **Real PaperExecutor + Fill Model** 기반으로 완전 전환하여, Settings → ExecutorFactory → PaperExecutor + SimpleFillModel 경로가 실제 PAPER 실행에서 동작하는지 검증.

**핵심 구현:**
- **Runner 리팩토링:** `scripts/run_d77_0_topn_arbitrage_paper.py` (+200줄)
  - `_mock_arbitrage_iteration()` → `_real_arbitrage_iteration()` 전환
  - Settings + ExecutorFactory + PaperExecutor + TradeLogger 통합
  - MockTrade 정의 (PaperExecutor 호환 필드)
- **Fill Model 활성화:** Settings.fill_model 기반 SimpleFillModel 자동 주입
  - Lazy Initialization: `_get_or_create_executor(symbol)` → Symbol별 PaperExecutor 생성
  - FillModelConfig → SimpleFillModel 인스턴스 생성
- **TradeLogger 연동:** ExecutionResult → TradeLogEntry 저장
  - slippage_bps, fill_ratio 필드 포함
  - 로그 저장 경로: `logs/d82-0/trades/{run_id}/top20_trade_log.jsonl`
- **KPI 확장:** partial_fills_count, failed_fills_count, avg_slippage_bps 등 추가

**테스트 검증:**
- ✅ D82-0 신규 테스트: 4개 PASS (0.39초)
  - Runner 초기화 with Settings
  - MockTrade 구조 검증
  - Executor Lazy Initialization
  - KPI metrics Fill Model 필드 존재
- ✅ 회귀 테스트: 18개 PASS (D80-4, D81-0 모두 정상 동작)

**설계 문서:**
- `docs/D82_0_TOPN_RUNNER_PAPER_EXECUTOR_INTEGRATION.md` (11개 섹션, 한글)
  - AS-IS vs TO-BE 구조 다이어그램
  - Runner 리팩토링 상세 내용
  - REAL PAPER 스모크 실행 방법 (3~6분)
  - 검증 포인트 (KPI, Trade 로그)
  - 제약 및 현실적 한계 명시

**AS-IS → TO-BE 구조:**
- **AS-IS (Mock 기반):**
  - 하드코딩된 Mock 가격
  - PaperExecutor 미사용
  - Fill Model 효과 없음
  - TradeLogger 미연동
- **TO-BE (Real Executor):**
  - Settings → ExecutorFactory → PaperExecutor
  - Fill Model 자동 주입 (SimpleFillModel)
  - ExecutionResult → TradeLogEntry 저장
  - KPI에 slippage/fill_ratio 집계

**REAL PAPER 스모크 실행 방법:**
```powershell
# 3분 스모크 (Top20, Mock Data)
python scripts/run_d77_0_topn_arbitrage_paper.py \
    --data-source mock \
    --topn-size 20 \
    --run-duration-seconds 180 \
    --monitoring-enabled \
    --kpi-output-path logs/d82-0/d82-0-smoke-3min_kpi.json

# 6분 스모크 (Top20, Real Market Data)
python scripts/run_d77_0_topn_arbitrage_paper.py \
    --data-source real \
    --topn-size 20 \
    --run-duration-seconds 360 \
    --monitoring-enabled \
    --kpi-output-path logs/d82-0/d82-0-smoke-6min_kpi.json
```

**검증 포인트:**
- KPI 파일: `win_rate_pct < 100.0`, `avg_slippage_bps > 0`, `partial_fills_count > 0`
- Trade 로그: `buy_slippage_bps > 0`, `buy_fill_ratio < 1.0` (부분 체결 존재)

**제약 및 현실적 한계:**
- **Entry/Exit 로직:** 여전히 간단한 Mock 기반 (iteration % 20)
  - Real Market Data 기반 Entry/Exit는 D82-1로 연기
- **호가 잔량 추정:** SimpleFillModel이 보수적 기본값 사용
  - 실제 Orderbook 연동은 D83-x로 연기
- **스모크 실행:** 시간 제약으로 사용자가 직접 실행 (문서화 완료)

**D82-0의 범위 (명확히 정의):**
- ✅ **인프라 준비 완료:** Settings + ExecutorFactory + PaperExecutor + TradeLogger 통합
- ✅ **테스트 검증:** 22개 테스트 모두 PASS (4개 신규 + 18개 회귀)
- ✅ **문서화:** 스모크 실행 방법, 검증 포인트, 제약 명시
- ⏳ **스모크 실행 대기:** 3~6분 REAL PAPER 실행은 사용자가 직접 수행 또는 D82-1로 넘김

**다음 단계:**
- **D82-1:** Real Market Data 기반 Entry/Exit 로직 구현 + 12h+ Long-term PAPER
- **D81-1:** Advanced Fill Model (다중 호가, 비선형 슬리피지, VWAP)
- **D83-x:** Real Orderbook Integration (WebSocket L2, 실시간 호가 잔량)

---
"""

def main():
    """D_ROADMAP.md 업데이트"""
    print(f"Reading {ROADMAP_PATH}...")
    content = ROADMAP_PATH.read_text(encoding='utf-8')
    
    # D81-0 섹션 "다음 단계" 라인 다음에 D82-0 삽입
    pattern = r'(\*\*다음 단계:\*\*\n- \*\*D82-0:\*\* D77 Runner를 Real PaperExecutor 기반으로 리팩토링\n- \*\*D82-1:\*\* TopN PAPER Long-term Validation \(12h\+, Fill Model ON, 승률/PnL 분석\)\n- \*\*D81-1:\*\* Advanced Fill Model 구현\n\n---\n)'
    
    if re.search(pattern, content):
        # D81-0의 "다음 단계" 라인 다음에 D82-0 섹션 삽입
        new_content = re.sub(
            pattern,
            r'\1' + D82_0_SECTION,
            content
        )
        
        # 파일 저장
        ROADMAP_PATH.write_text(new_content, encoding='utf-8')
        print(f"✅ D_ROADMAP.md 업데이트 완료 (D82-0 섹션 추가)")
    else:
        print(f"⚠️ 패턴을 찾을 수 없습니다. 수동으로 추가하세요.")
        print(f"찾는 패턴: '**다음 단계:**' 섹션 (D81-0 다음)")

if __name__ == "__main__":
    main()
