# D000-2: [META] check_ssot_docs.py ExitCode=0 강제 + Gate 회피 금지 + D000 번호 체계 명문화

**Run ID:** d000_2_closeout_20260105_190053  
**Date:** 2026-01-05  
**Branch:** rescue/d000_2_closeout  
**Status:** 🔄 IN PROGRESS (AC 3/11)

---

## 1. 목표 / 문제 정의

### 1-1. 왜 D000-2 CLOSEOUT이 필요했는가?

**직전 커밋 (3a36d88)의 문제:**
- **Gate 회피:** 파일명 패턴 위반 파일을 삭제(1599 lines)하여 check_ssot_docs.py 통과
- **추적성 훼손:** 유효한 D205 Report 6개 파일이 삭제되어 git history로만 접근 가능
- **SSOT 자기모순:** AC-9 (D000-2_REPORT.md) PENDING 상태인데 "DONE (AC 8/10)" 표기
- **워딩 꼼수:** "T*DO", "T.DO" 같은 변형으로 탐지 우회 시도

**근본 원인:**
- SSOT_RULES에 "Gate 회피 금지" 규칙이 명시되지 않음
- D000 번호 체계가 "메타 작업"임을 명확히 표시하지 않아 혼란 유발
- "규칙 준수"를 "통과 게임"으로 착각하는 패턴 재발

**위험성:**
- 이 패턴은 V1 인프라 덕지덕지와 동일한 실패 경로
- SSOT는 형식만 갖추고 검증 역할을 못함
- 나중에 더 큰 폭탄으로 돌아옴 (추적성 상실, 증거 손실)

### 1-2. D000-2 CLOSEOUT 목표

1. **Gate 회피 금지 규칙 명문화:** SSOT_RULES Section J 추가
2. **D000 META 번호 체계 명문화:** SSOT_RULES Section K + D_ROADMAP META RAIL 격리
3. **삭제된 파일 복구:** 6개 Report 파일 복구 + 규칙 준수 rename
4. **진짜 ExitCode=0 달성:** 꼼수 없이 물리적 증거 확보
5. **재발 방지 메커니즘:** Evidence 기반 검증 + EVASION_AUDIT.md 강제

---

## 2. 변경 요약

### 2-1. SSOT_RULES.md 패치

#### Section J: Gate 회피 금지 (Lines 1001-1033)

**금지 행위:**
1. **워딩 꼼수로 탐지 회피** (T*DO, T.DO, FIX.ME 등)
2. **파일 삭제로 규칙 회피** (Report/증거 삭제)
3. **ExitCode=0 아닌 상태에서 DONE 선언** (데이터 조작)

**위반 시 조치:**
- Gate 회피 발견 → 즉시 FAIL + 작업 Revert
- 삭제된 유효 기록 → 복구 + rename 강제
- 데이터 조작 → 프로젝트 중단 (CTO 경고)

**검증 방법:**
- `git show <commit> --stat`: 삭제 라인 수 확인
- 삭제 1000줄 이상 → 회피 의심, 복구 검토 필수
- Evidence 폴더에 "EVASION_AUDIT.md" 작성 강제

#### Section K: D000 META/Governance 번호 체계 (Lines 1036-1071)

**D000 정의:**
- **용도:** 규칙/DocOps/레일 정비 전용 (SSOT Infrastructure)
- **금지:** 실거래/엔진/알고리즘 개발
- **구분:** D000은 프로세스, D200+는 제품/기능

**네이밍 규칙:**
1. D000 제목에 [META] 태그 강제
2. D_ROADMAP에서 META RAIL 섹션 격리
3. 브랜치명도 meta 표시 (예: `rescue/d000_2_meta_closeout`)

**AC 요구사항:**
- D000-x는 check_ssot_docs.py ExitCode=0 필수
- Report에 "왜 META 작업이 필요했는지" 명시
- 완료 후 즉시 D200+ 복귀

### 2-2. D_ROADMAP.md 구조 정리

**META RAIL 섹션 추가 (Lines 2396-2405):**
```markdown
### 🏛️ META RAIL: D000 (SSOT Infrastructure - 규칙/프로세스 레일 정비 전용)

**원칙:**
- D000은 META/Governance 전용 (규칙/DocOps/레일 정비)
- 실거래/엔진/알고리즘 개발 금지
- 제목에 [META] 태그 강제
- check_ssot_docs.py ExitCode=0 필수
- 완료 후 즉시 실제 개발 라인(D200+)으로 복귀
```

**D000-1, D000-2 제목에 [META] 태그 추가:**
- `D000-1: [META] SSOT Rules 헌법 통합`
- `D000-2: [META] check_ssot_docs.py ExitCode=0 강제 + Gate 회피 금지 + D000 번호 체계 명문화`

**D000-2 AC 재정의 (11개):**
- AC-1~3: SSOT_RULES, D_ROADMAP 패치
- AC-4: 삭제된 파일 복구
- AC-5: Report 작성
- AC-6~8: Gates 실행
- AC-9: Evidence 패키징
- AC-10: AC 100% 체크
- AC-11: Git commit + push

### 2-3. 삭제된 D205 Report 파일 복구 계획

**복구 대상 (6개):**

| 파일명 (삭제됨) | 복구 후 이름 | 조치 |
|----------------|-------------|------|
| D205-10-1_WAIT_HARNESS_REPORT.md | D205-10-1_REPORT.md | git show 복구 + rename |
| D205-11-1_LATENCY_PROFILING_REPORT.md | D205-11-1_REPORT.md | git show 복구 + rename |
| D205-2_REOPEN_REPORT.md | D205-2-1_REPORT.md | git show 복구 + rename |
| D205-2_REOPEN2_REPORT.md | D205-2-2_REPORT.md | git show 복구 + rename |
| D205_9_FINAL_REPORT.md | D205-9_REPORT.md | git show 복구 + rename |
| D205_9_COMPARE_PATCH.md | Evidence로 이관 | D205-9 Report에 링크 추가 |

**복구 방법:**
```powershell
# 예시: D205-10-1_WAIT_HARNESS_REPORT.md 복구
git show 3a36d88^:docs/v2/reports/D205/D205-10-1_WAIT_HARNESS_REPORT.md > temp_file.md
Move-Item temp_file.md docs/v2/reports/D205/D205-10-1_REPORT.md
```

---

## 3. DocOps 실행 커맨드 / 출력 / ExitCode 증거

### 3-1. Before 상태

**커맨드:**
```powershell
python scripts/check_ssot_docs.py
echo $LASTEXITCODE
```

**증거 파일:**
- `logs/evidence/d000_2_closeout_20260105_190053/ssot_docs_check_before.txt`
- `logs/evidence/d000_2_closeout_20260105_190053/ssot_docs_check_before_exitcode.txt`

**결과:**
```
[PASS] SSOT DocOps: PASS (0 issues)
ExitCode: 0
```

**판정:** 3a36d88 커밋 상태에서는 ExitCode=0이나, 이는 파일 삭제로 인한 "회피 PASS"

### 3-2. After 상태 (복구 후)

**커맨드:**
```powershell
python scripts/check_ssot_docs.py
echo $LASTEXITCODE
```

**증거 파일:**
- `logs/evidence/d000_2_closeout_20260105_190053/ssot_docs_check_after.txt`
- `logs/evidence/d000_2_closeout_20260105_190053/ssot_docs_check_after_exitcode.txt`

**목표:** ExitCode=0 (파일 복구 후에도 유지)

---

## 4. AC 테이블 (11개) + 사실 기반 상태

| AC | 설명 | 증거 | 상태 |
|----|------|------|------|
| AC-1 | SSOT_RULES Section J (Gate 회피 금지) 추가 | SSOT_RULES.md Lines 1001-1033 | ✅ PASS |
| AC-2 | SSOT_RULES Section K (D000 META 번호 체계) 추가 | SSOT_RULES.md Lines 1036-1071 | ✅ PASS |
| AC-3 | D_ROADMAP META RAIL 섹션 격리 + [META] 태그 추가 | D_ROADMAP.md Lines 2396-2405, 2407, 2462 | ✅ PASS |
| AC-4 | 삭제된 D205 Report 6개 파일 복구 + rename | git show + rename 실행 결과 | ⏳ PENDING |
| AC-5 | D000-2_REPORT.md 작성 | 본 파일 | 🔄 IN PROGRESS |
| AC-6 | check_ssot_docs.py ExitCode=0 | ssot_docs_check_after_exitcode.txt = 0 | ⏳ PENDING |
| AC-7 | DocOps Gate ripgrep 실행 + 증거 | ripgrep_*.txt (금지 마커 0건) | ⏳ PENDING |
| AC-8 | Doctor/Fast/Regression Gates 100% PASS | doctor.txt, fast.txt, regression.txt | ⏳ PENDING |
| AC-9 | Evidence 패키징 | manifest.json, README.md 완성 | ⏳ PENDING |
| AC-10 | D_ROADMAP AC 100% 체크 | D_ROADMAP.md 체크박스 [x] 11개 | ⏳ PENDING |
| AC-11 | Git commit + push | git commit SHA + push 로그 | ⏳ PENDING |

**진행률:** 3/11 (27%)

---

## 5. Evidence 폴더 경로 + manifest 요약

**경로:** `logs/evidence/d000_2_closeout_20260105_190053/`

**현재 파일 목록:**
- bootstrap_env.txt (Git 상태, 브랜치 확인)
- DOCS_READING_CHECKLIST.md (강제 정독 5개 문서)
- EVASION_AUDIT.md (3a36d88 회피 감사 결과)
- git_show_3a36d88.txt (삭제 파일 목록)
- ssot_docs_check_before.txt + ssot_docs_check_before_exitcode.txt

**완료 후 추가될 파일:**
- ssot_docs_check_after.txt + ssot_docs_check_after_exitcode.txt
- ripgrep_cci.txt, ripgrep_migrate.txt, ripgrep_markers.txt
- doctor.txt, fast.txt, regression.txt
- manifest.json, README.md

---

## 6. 남은 리스크 / 후속 작업

### 6-1. 남은 리스크

1. **파일 복구 시 충돌 가능성:**
   - 현재 파일명과 복구 파일명이 겹칠 수 있음
   - 해결: rename 전에 기존 파일 확인

2. **ExitCode=0 유지 여부:**
   - 파일 복구 후 check_ssot_docs.py가 새로운 FAIL 발견 가능
   - 해결: 복구된 파일도 규칙 준수 상태로 유지 (파일명만 수정)

3. **Gate 실행 시간:**
   - Doctor/Fast/Regression Gate 실행에 시간 소요
   - 해결: 블로킹 실행으로 결과 확보

### 6-2. 후속 작업

**즉시 (D000-2 완료 전):**
- AC-4~11 완료 (파일 복구, Gates, Evidence, Git)

**완료 후:**
- D205-11-3 작업 복귀 (check_ssot_docs.py 100% CLEAN 상태 확보)
- Gate 회피 재발 방지 메커니즘 활성화

**장기:**
- SSOT_RULES Section J, K를 모든 D-step에 강제 적용
- EVASION_AUDIT.md를 표준 Evidence 항목으로 추가

---

## 7. 재발 방지 메커니즘

### 7-1. 구조적 차단

1. **SSOT_RULES 명문화:**
   - Section J: Gate 회피 금지 (워딩 꼼수, 파일 삭제, 데이터 조작)
   - Section K: D000 META 번호 체계 (오해 방지)

2. **D_ROADMAP 구조 정리:**
   - META RAIL 섹션 격리 (D000과 D200+ 물리적 분리)
   - [META] 태그 강제 (사람과 AI 모두 명확히 인식)

3. **Evidence 강제:**
   - EVASION_AUDIT.md: 삭제 라인 1000줄 이상 시 강제 작성
   - ssot_docs_check_exitcode.txt: ExitCode 물리적 증거

### 7-2. 프로세스 강제

1. **AC 100% 규칙:**
   - AC PENDING 상태에서 DONE 선언 금지
   - "핵심 목표 달성" 같은 부분 완료 표현 금지

2. **ExitCode=0 물리적 증거:**
   - "스코프 내 PASS" 같은 인간 판정 금지
   - ssot_docs_check_exitcode.txt 파일 내용이 `0`이어야만 인정

3. **Gate 회피 감사:**
   - 삭제 라인 수 체크 (git show --stat)
   - 1000줄 이상 삭제 시 복구 검토 강제

### 7-3. CTO 경고

**즉시 FAIL 조건:**
1. ExitCode=1인데 DONE 선언 → 데이터 조작으로 간주
2. AC PENDING인데 DONE 표기 → SSOT 자기모순
3. 파일 삭제로 Gate 통과 → Gate 회피

**프로젝트 중단 조건:**
- 위 패턴이 D000-2에서도 재발하면 프로젝트 종료 (사용자 경고)

---

## 8. 결론

**현재 상태:** 🔄 IN PROGRESS (AC 3/11, 27%)

**다음 단계:**
- Step 3: 삭제된 D205 Report 6개 파일 복구 (AC-4)
- Step 4: check_ssot_docs.py ExitCode=0 달성 (AC-6)
- Step 5~9: Gates 실행, Evidence 패키징, Git commit/push

**목표:** AC 11개 전부 달성 + ExitCode=0 물리적 증거 + Gate 회피 재발 방지 장치 완비

**DONE 조건:** AC 100% + Evidence 완비 + check_ssot_docs.py ExitCode=0 (ssot_docs_check_after_exitcode.txt = 0)
