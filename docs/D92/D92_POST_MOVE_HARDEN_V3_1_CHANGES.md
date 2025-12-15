# D92 POST-MOVE-HARDEN v3.1: 변경 파일 목록

**브랜치**: `rescue/d92_post_move_v3_1_gate_evidence_fix`  
**작성일**: 2025-12-15

---

## 신규 파일 (Added)

### 1. 재발 방지 스크립트
- **`scripts/check_docs_layout.py`**
  - 문서 경로 린트 스크립트
  - 규칙: D_ROADMAP.md는 루트에만, D92 보고서는 docs/D92/ 이하에만
  - Raw URL: (커밋 후 생성)

- **`scripts/check_shadowing_packages.py`**
  - 패키지 shadowing 검사 스크립트
  - tests/ 디렉토리가 루트 패키지를 shadowing하는지 검증
  - Raw URL: (커밋 후 생성)

- **`scripts/run_gate_10m_ssot.py`**
  - Gate 10분 테스트 SSOT 래퍼
  - 600초+exit0+KPI JSON 생성 강제
  - Raw URL: (커밋 후 생성)

### 2. 문서
- **`docs/D92/D92_POST_MOVE_HARDEN_V3_1_REPORT.md`**
  - v3.1 완료 보고서
  - Raw URL: (커밋 후 생성)

- **`docs/D92/D92_POST_MOVE_HARDEN_V3_1_CHANGES.md`**
  - 본 파일
  - Raw URL: (커밋 후 생성)

- **`docs/D92/D92_CORE_REGRESSION_DEFINITION.md`**
  - Core Regression 정의 SSOT
  - 44개 테스트 범위 명확화
  - Raw URL: (커밋 후 생성)

### 3. 로그 디렉토리
- **`logs/d92/v3_1/`**
  - env_checker.log
  - fast_gate.log
  - core_regression_final.log
  - gate_10m_manual.log
  - (gitignored, 로컬 증거용)

### 4. 이동된 문서 (docs/ → docs/D92/)
- **`docs/D92/D92_1_FIX_COMPLETION_REPORT.md`** (이동)
- **`docs/D92/D92_1_FIX_FINAL_STATUS.md`** (이동)
- **`docs/D92/D92_1_FIX_ROOT_CAUSE.md`** (이동)
- **`docs/D92/D92_1_FIX_VERIFICATION_REPORT.md`** (이동)

---

## 수정 파일 (Modified)

### 1. arbitrage/monitoring/__init__.py
**변경 내용**: StateManager export 추가

**수정 전**:
```python
from arbitrage.monitoring.status_monitors import (
    LiveStatusMonitor,
    TuningStatusMonitor,
    LiveStatusSnapshot,
    TuningStatusSnapshot
)
```

**수정 후**:
```python
from arbitrage.monitoring.status_monitors import (
    LiveStatusMonitor,
    TuningStatusMonitor,
    LiveStatusSnapshot,
    TuningStatusSnapshot,
    StateManager  # 추가
)
```

**사유**: test_d27_monitoring.py에서 `patch('arbitrage.monitoring.StateManager')` 실패 해결

**Raw URL**: (커밋 후 생성)

### 2. D_ROADMAP.md
**변경 내용**: D92 v3.1 항목 추가

**추가 내용**:
- Gate 10분 테스트 SSOT화 (600초+exit0+KPI 강제)
- pytest/import 불변식 재발 방지 장치 (shadowing 검사)
- 문서 경로 규칙 고정 (린트 스크립트)
- Core Regression 정의 SSOT (44개 테스트)

**Raw URL**: (커밋 후 생성)

---

## Git 변경 통계 (예상)

```
Added:
- scripts/check_docs_layout.py
- scripts/check_shadowing_packages.py
- scripts/run_gate_10m_ssot.py
- docs/D92/D92_POST_MOVE_HARDEN_V3_1_REPORT.md
- docs/D92/D92_POST_MOVE_HARDEN_V3_1_CHANGES.md
- docs/D92/D92_CORE_REGRESSION_DEFINITION.md

Modified:
- arbitrage/monitoring/__init__.py
- D_ROADMAP.md

Renamed/Moved:
- docs/D92_1_FIX_COMPLETION_REPORT.md → docs/D92/D92_1_FIX_COMPLETION_REPORT.md
- docs/D92_1_FIX_FINAL_STATUS.md → docs/D92/D92_1_FIX_FINAL_STATUS.md
- docs/D92_1_FIX_ROOT_CAUSE.md → docs/D92/D92_1_FIX_ROOT_CAUSE.md
- docs/D92_1_FIX_VERIFICATION_REPORT.md → docs/D92/D92_1_FIX_VERIFICATION_REPORT.md
```

---

## 커밋 정보

**브랜치**: `rescue/d92_post_move_v3_1_gate_evidence_fix`  
**커밋 SHA**: (커밋 후 생성)  
**PR 링크**: (푸시 후 생성)  
**Compare 링크**: (푸시 후 생성)

---

## Raw URL 목록 (커밋 후 업데이트)

형식: `https://raw.githubusercontent.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/<SHA>/<path>`

### 신규 파일
1. scripts/check_docs_layout.py
2. scripts/check_shadowing_packages.py
3. scripts/run_gate_10m_ssot.py
4. docs/D92/D92_POST_MOVE_HARDEN_V3_1_REPORT.md
5. docs/D92/D92_POST_MOVE_HARDEN_V3_1_CHANGES.md
6. docs/D92/D92_CORE_REGRESSION_DEFINITION.md

### 수정 파일
1. arbitrage/monitoring/__init__.py
2. D_ROADMAP.md

(커밋 SHA 생성 후 위 목록에 실제 URL 추가 예정)
