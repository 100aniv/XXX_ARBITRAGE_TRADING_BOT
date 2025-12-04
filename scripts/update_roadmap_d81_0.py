#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D_ROADMAP.md에 D81-0 섹션 추가 스크립트
"""

import re
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
ROADMAP_PATH = PROJECT_ROOT / "D_ROADMAP.md"

# D81-0 섹션 내용
D81_0_SECTION = """
### D81-0: Fill Model Settings & TopN PAPER 완전 통합 ✅ COMPLETE (2025-12-04)

**상태:** ✅ COMPLETE

**목표:** `SimpleFillModel` + `TradeLogger` + `Settings` 기반 `ExecutorFactory`를 완전히 통합하여, PAPER 모드에서 부분 체결 + 슬리피지를 관측 가능한 인프라 구축.

**핵심 구현:**
- **FillModelConfig + Settings 통합:** `arbitrage/config/settings.py` (신규 dataclass)
  - `.env` 환경변수 → `FillModelConfig` 매핑
  - PAPER: `enable_fill_model=true` (기본값), LOCAL_DEV: `false`
  - 환경변수: `FILL_MODEL_ENABLE`, `FILL_MODEL_SLIPPAGE_ALPHA`, `FILL_MODEL_AVAILABLE_VOLUME_FACTOR`
- **ExecutorFactory 주입 로직:** `arbitrage/execution/executor_factory.py` (수정, +50줄)
  - `create_paper_executor(fill_model_config)` 시그니처 변경
  - `fill_model_type="simple"` → `SimpleFillModel` 생성
  - `fill_model_type="advanced"` → `SimpleFillModel` fallback (Warning, D81-1+ TODO)
- **TradeLogger 확장:** `arbitrage/logging/trade_logger.py` (+8줄)
  - `TradeLogEntry`에 Fill Model 필드 추가: `buy_slippage_bps`, `sell_slippage_bps`, `buy_fill_ratio`, `sell_fill_ratio`
- **.env.paper.example 업데이트:** Fill Model 환경변수 섹션 추가

**테스트 검증:**
- ✅ Settings Unit tests: 7개 PASS (0.11초)
  - FillModelConfig 기본값, PAPER/LOCAL_DEV 환경별 기본값, 환경변수 오버라이드
- ✅ ExecutorFactory 통합 tests: 6개 PASS (0.18초)
  - FillModelConfig → SimpleFillModel 생성, advanced fallback, partial fill/slippage only 조합
- ✅ 회귀 없음: D80-3/D80-4 테스트 모두 PASS (37개 전체 PASS, 0.49초)

**설계 문서:**
- `docs/D81_0_FILL_MODEL_INTEGRATION_VALIDATION.md` (11개 섹션, 한글)
  - Settings 통합, ExecutorFactory 주입, TradeLogger 연동
  - 실행 예시, 테스트 결과, TopN PAPER 스모크 계획 (D82-x로 연기)
  - Acceptance Criteria 검증 (Settings/Executor Wiring/Logging 모두 PASS)

**핵심 메커니즘:**
- **Settings 기반 Fill Model 생성:**
  ```python
  settings = Settings.from_env()  # ARBITRAGE_ENV=paper
  executor = factory.create_paper_executor(
      symbol="BTC/USDT",
      portfolio_state=portfolio_state,
      risk_guard=risk_guard,
      fill_model_config=settings.fill_model,  # Settings 기반
  )
  ```
- **TradeLogEntry에 Fill Model 정보 저장:**
  ```json
  {
    "buy_slippage_bps": 12.5,
    "sell_slippage_bps": 8.3,
    "buy_fill_ratio": 0.65,
    "sell_fill_ratio": 1.0
  }
  ```

**제약 및 현실적 한계 (D81-0):**
- **D77 Runner가 Mock 기반:** PaperExecutor를 직접 사용하지 않음 → Fill Model 효과 관측 불가
  - → **D82-x에서 Runner 리팩토링 후 실제 PAPER 검증 진행**
- **호가 잔량 추정:** 보수적 기본값 사용 (TODO: D81-1 또는 D82-x에서 실제 Orderbook 연동)
- **SimpleFillModel 한계:** Linear Slippage, 단일 호가 레벨, Market Impact 미반영

**향후 확장 포인트 (D81-1+):**
- **Advanced Fill Model:** 다중 호가 레벨, 비선형 슬리피지, VWAP 기반 체결
- **Market Impact:** 주문 크기 → 호가창 변화 → 가격 악화
- **Real Orderbook 연동:** WebSocket L2 데이터 → 실시간 호가 잔량 조회
- **파라미터 최적화:** D80-3 로그 기반 백테스팅 + Bayesian Optimization

**다음 단계:**
- **D82-0:** D77 Runner를 Real PaperExecutor 기반으로 리팩토링
- **D82-1:** TopN PAPER Long-term Validation (12h+, Fill Model ON, 승률/PnL 분석)
- **D81-1:** Advanced Fill Model 구현

---
"""

def main():
    """D_ROADMAP.md 업데이트"""
    print(f"Reading {ROADMAP_PATH}...")
    content = ROADMAP_PATH.read_text(encoding='utf-8')
    
    # D80-4 섹션 "다음 단계:" 라인 다음에 D81-0 삽입
    pattern = r'(\*\*다음 단계:\*\* D81-x \(Advanced Fill & Market Impact Model\), D82-x \(Long-term Validation\)\n\n---\n---\n)'
    
    if re.search(pattern, content):
        # D80-4의 "다음 단계" 라인 다음에 D81-0 섹션 삽입
        new_content = re.sub(
            pattern,
            r'\1' + D81_0_SECTION,
            content
        )
        
        # 파일 저장
        ROADMAP_PATH.write_text(new_content, encoding='utf-8')
        print(f"✅ D_ROADMAP.md 업데이트 완료 (D81-0 섹션 추가)")
    else:
        print(f"⚠️ 패턴을 찾을 수 없습니다. 수동으로 추가하세요.")
        print(f"찾는 패턴: '**다음 단계:** D81-x (Advanced Fill & Market Impact Model), D82-x (Long-term Validation)'")

if __name__ == "__main__":
    main()
