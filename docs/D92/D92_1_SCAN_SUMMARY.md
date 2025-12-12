# D92-2 Context Scan Summary

**Date:** 2025-12-12 10:20 KST  
**Purpose:** 중복/정리 대상 스캔 + Zone Profile 핵심 파일 목록화

---

## 🔍 Config 폴더 중복 현황

### 발견된 Config 폴더 (4개)
| Path | Type | 위험도 | 용도 추정 | 이번 턴 액션 |
|------|------|--------|-----------|-------------|
| `config/` | Directory | **HIGH** | 메인 설정 폴더 (zone_profiles_v2.yaml 등) | **보존** (활성 사용 중) |
| `configs/` | Directory | **HIGH** | PAPER/baseline 설정 폴더 | **보존** (run_d77_0에서 참조) |
| `arbitrage/config/` | Directory | **MEDIUM** | 코드베이스 내부 설정 모듈 | **보존** (settings.py 등) |
| `tests/config/` | Directory | **LOW** | 테스트 전용 설정 | **보존** (테스트 격리) |

**판단:** 각각 다른 용도로 사용 중, 이번 턴에서 병합/삭제 금지

---

## 📁 Zone Profile 관련 파일

### Zone Profile YAML (6개 파일)
| File | Size (Bytes) | Last Modified | 상태 | 액션 |
|------|--------------|---------------|------|------|
| `zone_profiles_v2.yaml` | (활성) | 최신 | **ACTIVE** | ✅ 사용 중 |
| `zone_profiles_v2_new.yaml` | (백업) | 이전 | BACKUP | ⏳ 다음 턴 정리 |
| `zone_profiles_v2_backup.yaml` | (백업) | 이전 | BACKUP | ⏳ 다음 턴 정리 |
| `zone_profiles_v2_backup2.yaml` | (백업) | 이전 | BACKUP | ⏳ 다음 턴 정리 |
| `zone_profiles_v2_original_backup.yaml` | (백업) | 이전 | BACKUP | ⏳ 다음 턴 정리 |
| `zone_profiles.yaml` | (v1) | Legacy | DEPRECATED | ⏳ 다음 턴 정리 |

**Location:** `config/arbitrage/zone_profiles_v2.yaml`

**Referenced by:**
- `arbitrage/config/zone_profiles_loader_v2.py`
- `tests/test_d91_1_symbol_mapping.py`
- `scripts/run_d92_1_topn_longrun.py` (간접 참조)

---

## 📄 Docs 폴더 중복 현황

### D9X 문서 현황 (D92 시리즈)
| Document | 용도 | 중복 여부 | 액션 |
|----------|------|-----------|------|
| `D92_1_FIX_FINAL_STATUS.md` | D92-1 최종 상태 | 단독 | ✅ 보존 |
| `D92_1_FIX_ROOT_CAUSE.md` | D92-1 로깅 문제 분석 | 단독 | ✅ 보존 |
| `D92_1_FIX_VERIFICATION_REPORT.md` | D92-1 검증 리포트 | 단독 | ✅ 보존 |
| `D92_1_FIX_COMPLETION_REPORT.md` | D92-1 완료 리포트 | **중복 가능성** | ⚠️ 검토 필요 |

**중복 패턴:**
- `*_FINAL_STATUS.md`, `*_COMPLETION_REPORT.md`, `*_FINAL_REPORT.md`가 유사한 내용을 담을 가능성
- D15~D36까지 각각 `FINAL_REPORT.md` + 고유 문서 패턴 반복

### 전체 D 문서 통계
- **총 43개 D 문서** (D15~D92)
- 패턴:
  - `D[XX]_FINAL_REPORT.md` (약 20개)
  - `D[XX]_IMPLEMENTATION_SUMMARY.md` (약 5개)
  - `D[XX]_[기능명].md` (나머지)

**판단:** 대부분 히스토리 문서, 삭제 위험 높음 → 이번 턴 건드리지 않음

---

## 🎯 Zone Profile 핵심 파일 (Active)

### 1. Configuration
- **Active YAML:** `config/arbitrage/zone_profiles_v2.yaml`
- **Loader:** `arbitrage/config/zone_profiles_loader_v2.py`

### 2. Core Logic
- **Applier:** `arbitrage/core/zone_profile_applier.py`

### 3. Runner Scripts
- **D92-1 Runner:** `scripts/run_d92_1_topn_longrun.py`
- **D77-0 PAPER:** `scripts/run_d77_0_topn_arbitrage_paper.py`

### 4. Tests
- **Symbol Mapping Test:** `tests/test_d91_1_symbol_mapping.py`

---

## 🚨 중복/정리 위험도 평가

### HIGH Risk (이번 턴 절대 건드리지 말 것)
1. **config/ vs configs/** 병합
   - 이유: 활성 참조 중, 경로 변경 시 런타임 에러 발생
   - 액션: SKIP

2. **zone_profiles_v2.yaml 백업 파일들**
   - 이유: 롤백 가능성, 검증 전 삭제 위험
   - 액션: SKIP (검증 PASS 후 별도 커밋)

### MEDIUM Risk
3. **D92-1 문서 중복 (4개)**
   - 이유: 내용 유사성 불명, 하나로 통합 가능 여부 검토 필요
   - 액션: 이번 턴에서 "인벤토리+계획"만 작성

### LOW Risk
4. **tests/config/** 폴더
   - 이유: 테스트 격리, 메인 로직과 무관
   - 액션: 보존

---

## 📋 이번 턴(D92-2) 액션 결정

### ✅ 진행 가능 (기능 구현)
1. Telemetry 추가 (spread 분포 수치화)
2. Threshold 재보정 로직 구현
3. 5분 스모크 + 1h Real PAPER
4. `config/arbitrage/zone_profiles_v2.yaml` 업데이트

### ⏸️ 보류 (정리는 검증 PASS 후)
1. zone_profiles 백업 파일 삭제
2. D92-1 문서 통합
3. config/configs 병합

### 📝 문서만 작성
1. `docs/DOCS_DEDUP_PLAN.md` (이동/삭제 계획, 실행 X)
2. `docs/D92_2_CALIBRATION_REPORT.md` (결과 리포트)

---

## 🛠️ 다음 턴(D92-3 이후) 정리 계획 (초안)

### Phase 1: 백업 파일 정리
```bash
# 검증 PASS 후
git rm config/arbitrage/zone_profiles_v2_*.yaml
git rm config/arbitrage/zone_profiles.yaml  # v1 deprecated
```

### Phase 2: 문서 통합
- D92_1_FIX_*.md (4개) → D92_1_FINAL_REPORT.md (1개)로 통합
- 중복 내용 제거, 핵심만 남김

### Phase 3: Config 폴더 리팩토링 (장기)
- `config/` → 메인 설정 (YAML, JSON)
- `configs/` → 프로파일/프리셋 (paper, live 등)
- `arbitrage/config/` → 코드 설정 모듈 (settings.py)
- 명확한 네이밍 규칙 수립

---

## 📌 SSOT (Single Source of Truth) 원칙

### Zone Profile
- **SSOT:** `config/arbitrage/zone_profiles_v2.yaml`
- 백업: Git history로 충분, 로컬 백업 불필요

### D 문서
- **SSOT:** 각 D 번호당 1개 FINAL_REPORT.md
- 중복 문서는 FINAL_REPORT로 통합 or 삭제

### Config 폴더
- **SSOT:** TBD (Phase 3에서 결정)

---

## ✅ Summary

**이번 턴(D92-2) 원칙:**
1. **기능 검증 최우선** - Telemetry + Threshold 보정 + 1h PAPER
2. **정리는 PASS 후** - 백업 파일/중복 문서 삭제 금지
3. **계획만 작성** - DOCS_DEDUP_PLAN.md (실행 X)
4. **안전한 커밋** - 기능 커밋 + 문서 계획 커밋 분리

**다음 턴 정리 조건:**
- D92-2 검증 PASS (trade > 0)
- Threshold 보정 효과 확인
- Git 상태 클린
