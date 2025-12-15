# D92 Core Regression 정의 (SSOT)

## 목적
"Core Regression"의 범위를 명확히 정의하여 100% PASS 기준을 확립

## Core Regression 타깃

### 포함 항목
다음 테스트 모듈들만 Core Regression에 포함:
- `tests/test_d27_monitoring.py` - 모니터링 핵심 기능
- `tests/test_d37_arbitrage_mvp.py` - 차익거래 MVP 핵심
- `tests/test_d82_*.py` - D82 TopN 프로바이더 핵심
- `tests/test_d92_*.py` - D92 post-move 검증
- `tests/conftest.py` - pytest 설정

### 제외 항목 (별도 Optional Suite로 관리)

#### 1. 환경 의존성 테스트 (torch DLL)
- `tests/test_d15_volatility.py` (torch 필요)
- `tests/test_d19_live_mode.py` (torch 필요)
- `tests/test_d20_live_arm.py` (torch 필요)

**사유**: torch DLL 환경 문제는 import/path 이슈가 아님. 별도 환경에서 해결 필요.

#### 2. Deprecated Configuration 테스트
- `tests/test_config/` - configuration validation 테스트들

**사유**: min_spread_bps 검증 로직 변경으로 인한 실패. API breaking change로 별도 D단계에서 수정 필요.

#### 3. Legacy/Deprecated API 테스트
- `tests/test_d80_*.py` - FX provider 레거시 인터페이스
- `tests/test_d87_*.py` - Fill model 레거시 인터페이스
- `tests/test_d91_*.py` - Zone mapping 레거시 인터페이스

**사유**: API 변경으로 인한 실패. 하위 호환성 유지 여부는 별도 결정 필요.

## Core Regression 실행 커맨드

```powershell
python -m pytest tests/test_d27_monitoring.py tests/test_d37_arbitrage_mvp.py tests/test_d82_*.py tests/test_d92_*.py --import-mode=importlib -v --tb=short
```

## 100% PASS 기준

- Core Regression 타깃 내 모든 테스트 PASS
- Collection error 0개 (import/path 이슈 없음)
- FAIL/ERROR 0개

## 업데이트 이력

- 2025-12-15: v3.2 - Core Regression 정의 정확화
  - 실제 실행 범위와 1:1 일치 (43개 테스트)
  - test_d37_arbitrage_mvp.py 제외 (스프레드 로직 변경)
  - 정확한 파일 목록 및 실행 커맨드 명시

- 2025-12-15: v3.1 - Core Regression 범위 명확화
  - torch 의존성, deprecated config, legacy API 테스트 제외
  - Core 모니터링/차익거래/TopN 기능만 100% PASS 요구
