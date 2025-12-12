# Docs & Config Deduplication Plan

**Date:** 2025-12-12 15:33 KST  
**Status:** 📋 PLAN ONLY (이번 턴에서는 실행 금지, 기능 검증 PASS 후만 실행)

---

## 🎯 목적

중복/백업 파일을 정리하여 SSOT(Single Source of Truth) 원칙 확립

---

## 📋 정리 대상 인벤토리

### 1. Zone Profile YAML 백업 파일 (5개)
| File | Size | Last Modified | Action |
|------|------|---------------|--------|
| `zone_profiles_v2.yaml` | 6282 | 2025-12-12 02:09 | ✅ **KEEP (SSOT)** |
| `zone_profiles_v2_new.yaml` | 5862 | 2025-12-12 01:40 | ❌ DELETE |
| `zone_profiles_v2_backup.yaml` | 5769 | 2025-12-12 01:40 | ❌ DELETE |
| `zone_profiles_v2_backup2.yaml` | 5769 | 2025-12-12 01:40 | ❌ DELETE |
| `zone_profiles_v2_original_backup.yaml` | 5769 | 2025-12-12 01:40 | ❌ DELETE |
| `zone_profiles.yaml` (v1) | 4971 | 2025-12-12 01:40 | ⏸️ KEEP (Fallback 용도) |

**Location:** `config/arbitrage/`

**Risk:** LOW (Git history로 복구 가능)

---

### 2. D92-1 문서 중복 (4개)
| Document | Purpose | Action |
|----------|---------|--------|
| `D92_1_FIX_FINAL_STATUS.md` | D92-1 최종 상태 | ✅ KEEP |
| `D92_1_FIX_ROOT_CAUSE.md` | 로깅 문제 분석 | 🔀 MERGE → FINAL_STATUS |
| `D92_1_FIX_VERIFICATION_REPORT.md` | 검증 리포트 | 🔀 MERGE → FINAL_STATUS |
| `D92_1_FIX_COMPLETION_REPORT.md` | 완료 리포트 | 🔀 MERGE → FINAL_STATUS |

**Result:** 4개 → 1개 통합 (`D92_1_FINAL_REPORT.md`)

**Risk:** MEDIUM (문서 내용 유실 가능성)

---

### 3. Config 폴더 구조 (4개 폴더)
| Folder | Purpose | Action |
|--------|---------|--------|
| `config/` | 메인 설정 (YAML, secrets) | ✅ KEEP |
| `configs/` | PAPER/Live 프로파일 | ✅ KEEP (분리 유지) |
| `arbitrage/config/` | 코드 설정 모듈 (settings.py) | ✅ KEEP |
| `tests/config/` | 테스트 전용 설정 | ✅ KEEP |

**Result:** 현재 구조 유지 (용도별 분리)

**Risk:** HIGH (경로 변경 시 런타임 에러)

---

## 🛠️ Migration 단계 (3-Step)

### Phase 1: 백업 파일 정리 (Safe)
**조건:** D92-2 검증 PASS (trade > 0 확인 후)

```powershell
# Step 1.1: 백업 파일 삭제
git rm config/arbitrage/zone_profiles_v2_new.yaml
git rm config/arbitrage/zone_profiles_v2_backup.yaml
git rm config/arbitrage/zone_profiles_v2_backup2.yaml
git rm config/arbitrage/zone_profiles_v2_original_backup.yaml

# Step 1.2: Commit
git commit -m "[CLEANUP] Remove zone profile backup files (Git history available)"
```

**Expected Result:**
- `config/arbitrage/`에 `zone_profiles_v2.yaml` (SSOT)와 `zone_profiles.yaml` (v1 fallback)만 남음
- Git history로 백업 복구 가능

**Rollback:** `git revert <commit_hash>`

---

### Phase 2: D92-1 문서 통합 (Moderate Risk)
**조건:** Phase 1 완료 + D92-2 문서 작성 완료

```powershell
# Step 2.1: D92_1_FINAL_REPORT.md 생성 (4개 문서 통합)
# (수동 작업: 핵심 내용만 추출하여 통합)

# Step 2.2: 기존 문서 삭제
git rm docs/D92_1_FIX_ROOT_CAUSE.md
git rm docs/D92_1_FIX_VERIFICATION_REPORT.md
git rm docs/D92_1_FIX_COMPLETION_REPORT.md

# Step 2.3: D92_1_FINAL_STATUS.md → D92_1_FINAL_REPORT.md 이름 변경
git mv docs/D92_1_FIX_FINAL_STATUS.md docs/D92_1_FINAL_REPORT.md

# Step 2.4: Commit
git commit -m "[DOCS] Consolidate D92-1 documents (4 → 1)"
```

**Expected Result:**
- D92-1 관련 문서가 `D92_1_FINAL_REPORT.md` 1개로 통합
- 핵심 내용: 구조 변경, Zone Profile 적용, 로깅 해결, 검증 결과

**Rollback:** `git revert <commit_hash>` (통합 전 문서는 Git history에 보존)

---

### Phase 3: Config 폴더 리팩토링 (High Risk, 장기 과제)
**조건:** D92-X 시리즈 완료 + 별도 세션

**목표:**
- `config/` → Runtime 설정 (YAML, secrets, base.py)
- `configs/` → Profile 프리셋 (paper/, live/, d17_scenarios/, d23_tuning/)
- `arbitrage/config/` → 코드 설정 모듈 (settings.py, loaders)

**Risk:** HIGH (import 경로, 런타임 참조 경로 전면 변경)

**Action:** 이번 턴 스킵, D93+ 에서 별도 설계 필요

---

## 📊 정리 원칙 (SSOT)

### Zone Profile
- **SSOT:** `config/arbitrage/zone_profiles_v2.yaml`
- **Fallback:** `config/arbitrage/zone_profiles.yaml` (v1)
- **Backup:** Git history (로컬 백업 불필요)

### D 문서
- **SSOT:** 각 D 번호당 `D[XX]_FINAL_REPORT.md` 1개
- **중복:** 같은 D 번호의 여러 문서 → 통합
- **Naming:** `D[XX]_FINAL_REPORT.md` (일관성)

### Config 폴더
- **SSOT:** TBD (Phase 3에서 결정)
- **현재:** 용도별 분리 유지 (정리 금지)

---

## ✅ Acceptance Criteria

### Phase 1 (백업 파일 정리)
1. ✅ D92-2 검증 PASS (trade > 0)
2. ✅ `zone_profiles_v2.yaml` 정상 동작 확인
3. ✅ Git history에 백업 파일 보존 확인

### Phase 2 (D92-1 문서 통합)
1. ✅ `D92_1_FINAL_REPORT.md`에 4개 문서 핵심 내용 포함
2. ✅ 통합 문서 리뷰 완료
3. ✅ Git history에 원본 문서 보존 확인

### Phase 3 (Config 리팩토링)
1. ⏳ 별도 설계 문서 작성
2. ⏳ Import 경로 전수 조사
3. ⏳ 테스트 커버리지 100%

---

## 🚨 주의사항

### 절대 금지 (이번 턴)
1. ❌ Config 폴더 병합/이동
2. ❌ 백업 파일 삭제 (D92-2 검증 전)
3. ❌ 문서 통합 (D92-2 문서 작성 전)

### 허용 (다음 턴)
1. ✅ Phase 1 실행 (D92-2 PASS 후)
2. ✅ Phase 2 실행 (Phase 1 완료 후)
3. ⏸️ Phase 3 설계 (별도 세션)

---

## 📝 실행 체크리스트

### Before Phase 1
- [ ] D92-2 검증 PASS (trade > 0)
- [ ] `zone_profiles_v2.yaml` 최종 버전 확정
- [ ] Git working directory 클린 (커밋 완료)

### Before Phase 2
- [ ] Phase 1 완료 및 검증
- [ ] D92-2 문서 작성 완료
- [ ] `D92_1_FINAL_REPORT.md` 초안 작성

### Before Phase 3
- [ ] Phase 2 완료 및 검증
- [ ] Config 리팩토링 설계 문서 완성
- [ ] 테스트 커버리지 확보

---

## 🎯 Expected Outcome

### After Phase 1
```
config/arbitrage/
  ├── zone_profiles_v2.yaml  (SSOT, Active)
  └── zone_profiles.yaml      (v1 Fallback)
```

### After Phase 2
```
docs/
  ├── D92_1_FINAL_REPORT.md  (통합, 1개)
  └── D92_2_CALIBRATION_REPORT.md
```

### After Phase 3
```
config/           (Runtime 설정)
configs/          (Profile 프리셋)
arbitrage/config/ (코드 모듈)
tests/config/     (테스트 격리)
```

---

## 📌 Summary

**이번 턴 (D92-2):**
- ✅ 정리 계획 수립 (이 문서)
- ❌ 실행 금지 (기능 검증 최우선)

**다음 턴 (D92-3+):**
- ✅ Phase 1 실행 (백업 파일 정리)
- ✅ Phase 2 실행 (문서 통합)
- ⏸️ Phase 3 설계 (Config 리팩토링)

**Commit 전략:**
- 기능 커밋 (D92-2) ≠ 정리 커밋 (D92-3+)
- 각 Phase별 독립 커밋
- Rollback 가능하도록 작은 단위로 분리
