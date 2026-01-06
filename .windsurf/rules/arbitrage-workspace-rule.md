---
trigger: always_on
---

# Arbitrage V2 Workspace Rules (SSOT 2-기둥 구조)

**Version:** 2.0 (SSOT 2-기둥 기반)  
**Effective Date:** 2026-01-05  
**Status:** ENFORCED

---

## 기둥 1: D_ROADMAP.md (상태 데이터베이스)

**역할:** "우리는 지금 어디에 있고, 목표가 무엇이며, 어떤 AC를 완료했는가?"

**성격:** 수정이 극도로 제한된 계약서

**강제 규칙:**
- ✅ D_ROADMAP.md가 유일 SSOT (다른 문서는 참조/동기화 대상)
- ❌ D_ROADMAP_V2.md, D_ROADMAP_V3.md 같은 분기 금지
- ✅ D 번호 의미 불변 (변경 금지)
- ✅ AC 추가만 허용 (삭제/축소 금지)
- ✅ 증거 경로 명시 필수 (logs/evidence/ 고정)

---

## 기둥 2: docs/v2/SSOT_RULES.md (운영 헌법 + SOP)

**역할:** "작업은 어떤 순서로 하고, 테스트는 무엇을 하며, 문서는 어떻게 검증하는가?"

**성격:** 모든 방법론이 집대성된 유일한 법전

**포함 내용:**
- 핵심 원칙 (SSOT 단일화, D 번호 불변, Report 파일명 규칙)
- 강제 금지 사항 (파괴적 이동/삭제, 오버리팩토링, 스크립트 중심 실험)
- Scan-First → Reuse-First 강제 규칙
- Profit Loop 강제 규칙 (D205-4~12 필수)
- **프롬프트 템플릿** (반복 작업 표준화)
- **테스트 템플릿** (Gate 검증 표준화)
- **DocOps 검증** (문서 일관성 검증)

---

## 참고 파일 (메인은 아니지만 반영 필수)

1. **docs/v2/V2_ARCHITECTURE.md**
   - Engine-Centric 설계 계약
   - OrderIntent, Adapter, Engine 플로우

2. **docs/v2/design/** (설계 문서)
   - SSOT_MAP.md: 전체 SSOT 목록 및 규칙
   - EVIDENCE_FORMAT.md: 실행 증거 저장 포맷
   - NAMING_POLICY.md: 네이밍 정책
   - INFRA_REUSE_INVENTORY.md: V1 인프라 재사용 전략

3. **README.md**
   - 프로젝트 소개 및 SSOT 문서 7종 목록
   - 금지 사항 (SSOT 분기, 환경별 설정 중복)

---

## 강제 규칙 (항상 동일, 생략 금지)

### SSOT 원칙
- ✅ D_ROADMAP.md 단 1개 (유일한 원천)
- ✅ D번호 의미 불변 (확장은 브랜치 Dxxx-y-z만)
- ✅ 기존 목표 / AC / 증거 요구사항 절대 삭제 금지
- ✅ 새 문제 발견 시 "추가(additive)"만 허용 (덮어쓰기 / 축소 / 무효화 금지)

### 개발 원칙
- ✅ 돈 버는 아비트라지 로직 / 알고리즘 우선
- ✅ 엔진 중심 구조 (arbitrage/v2/**)
- ✅ scan-first → reuse-first
- ✅ 중복 / 반복 금지

### 검증 원칙
- ✅ Gate 3단 강제 (Doctor / Fast / Regression)
- ✅ 증거(Evidence) 없으면 PASS 주장 금지
- ✅ Wallclock Verification (장기/대기/모니터링 작업 필수)
- ✅ watch_summary.json 자동 생성 필수

### 운영 원칙
- ✅ 작업 종료 시 반드시 Git commit (+ push)
- ✅ 필요 시 DB / Redis / 프로세스 / 캐시 정리 강제
- ✅ 실패 시 오염 방지 (Rollback 원칙)

---

## 경로 규칙 (SSOT)

### 코드 네임스페이스

---

## 기둥 2 확장: docs/v2/SSOT_RULES.md (Section B~K 신규 추가)

### Section B: AC 이관 프로토콜 (강제)
**목적:** AC 삭제 금지, 이관 시 원본/목적지 표기 강제, SSOT 파손 방지

**규칙:**
- AC는 절대 삭제하지 않음
- AC를 다른 D로 이관할 때는 원본/목적지 모두에 표기 필수
- 원본 AC 표기: `~~내용~~ [MOVED_TO: <목적지 D> / <날짜> / <커밋> / <사유>]`
- 목적지 AC 표기: `[ ] AC-3: 내용 [FROM: <원본 D> AC-<번호>]`
- Umbrella 섹션에 "AC 이관 매핑" 서브섹션 추가 권장
- 위반 시: 원본 AC 삭제 → 즉시 FAIL, 복원 필수

### Section C: Work Prompt Template (Step 0~9)
**모든 D-step은 Step 0~9를 순차 실행해야 함**
- Step 0: Bootstrap (SSOT 문서 정독 포함)
- Step 1~9: Repo Scan → Plan → Implement → Tests → Smoke → Evidence → 문서 업데이트 → Git → Closeout

### Section D: Test Template (자동화/운영급)
**테스트 절대 원칙:**
- 테스트는 사람 개입 없이 자동 실행
- FAIL 시 즉시 중단 → 수정 → 동일 프롬프트 재실행
- Smoke 유형: Micro-Smoke (1분) vs Full Smoke (20분)
- Wallclock Verification (장기 실행 필수): watch_summary.json 자동 생성

### Section E: DocOps / SSOT Audit (Always-On)
**적용 범위:** 모든 D 단계 / 모든 커밋

**DocOps Always-On 절차 (커밋 전 필수):**
- Gate (A) SSOT 자동 검사: `python scripts/check_ssot_docs.py` (Exit code 0 필수)
- Gate (B) ripgrep 위반 탐지: cci, 이관/migrate/migration, TODO/TBD/PLACEHOLDER
- Gate (C) Pre-commit sanity: git status, git diff --stat

**DocOps 불변 규칙 (SSOT 핵심 4문장):**
1. SSOT는 D_ROADMAP.md 단 1개 (충돌 시 D_ROADMAP 채택)
2. D 번호 의미는 불변 (Immutable Semantics)
3. 확장은 브랜치(Dxxx-y-z)로만 (이관/재정의 금지)
4. DONE/COMPLETED는 Evidence 기반 (실행 증거 필수)

### Section F: Design Docs 참조 규칙 (디폴트)
**목적:** docs/v2/design 정독을 "옵션"이 아니라 "디폴트"로 강제

**규칙:**
- 모든 D-step은 docs/v2/design/ 반드시 열어 읽기
- 이번 D에 관련된 문서 최소 2개 요약 필수
- READING_CHECKLIST.md: 읽은 문서 목록 + 1줄 요약

### Section G: COMPLETED 단계 합치기 금지 (강제)
**원칙:** COMPLETED 단계에 신규 작업 추가 방지

**규칙:**
- COMPLETED 단계에 뭔가 추가하고 싶으면 무조건 새 D/새 브랜치 생성
- "단계 합치기"는 SSOT 리스크(삭제/누락/축약) 때문에 절대 금지

### Section H: 3점 리더 / 임시 마커 금지 (강제)
**원칙:** 축약 흔적 제거 (SSOT 파손 방지)

**금지 대상:**
- `...` (3점 리더, ellipsis 문자)
- `…` (ellipsis 유니코드 U+2026)
- 임시 작업 마커 (T*DO, T*D, FIX*E, X*X, H*CK 형태)
- `pending`, `later`, `작업중`, `보류중` (COMPLETED 문서에서)

### Section I: check_ssot_docs.py ExitCode=0 강제 (SSOT DocOps Gate)
**원칙:** "스코프 내 PASS" 같은 인간 판정 금지, 물리적 증거만 인정

**규칙:**
1. **ExitCode=0만 PASS:**
   - check_ssot_docs.py 실행 결과는 ExitCode=0일 때만 PASS
   - ExitCode=1이면 무조건 FAIL (이유 불문)

2. **증거 요구사항:**
   - ssot_docs_check_exitcode.txt 파일 필수 (내용: `0`)
   - ssot_docs_check_raw.txt 또는 ssot_docs_check_final.txt 필수 (전체 출력)

### Section J: Gate 회피 금지 (강제)
**원칙:** 규칙을 통과하기 위한 편법/꼼수는 SSOT를 더 빨리 망가뜨림

**금지 행위:**
1. 워딩 꼼수로 탐지 회피 (금칙어 변형, 정규식 패턴 우회)
2. 파일 삭제로 규칙 회피 (규칙 위반 파일 삭제, Report/증거 지워서 추적성 제거)
3. ExitCode=0 아닌 상태에서 DONE 선언

**위반 시 조치:**
- Gate 회피 발견 → 즉시 FAIL + 작업 Revert
- 데이터 조작 → 프로젝트 중단 (CTO 경고)

### Section K: D000 META/Governance 번호 체계 (강제)
**원칙:** D000은 META/Governance 전용, 실제 기능 개발과 혼재 금지

**D000 정의:**
- 용도: 규칙/DocOps/레일 정비 전용 (SSOT Infrastructure)
- 금지: 실거래/엔진/알고리즘 개발

**네이밍 규칙:**
1. D000 제목에 [META] 태그 강제: `D000-1: [META] SSOT Rules Unify`
2. D_ROADMAP에서 META RAIL 섹션 격리
3. 브랜치명: `rescue/d000_1_meta_ssot_rules`

**AC 요구사항:**
- D000-x 작업은 check_ssot_docs.py ExitCode=0 필수
- D000-x Report는 "왜 META 작업이 필요했는지" 명시 필수

---

## 참고 파일 (메인은 아니지만 반영 필수) - 확장

1. **docs/v2/SSOT_RULES.md** (완전 통합)
   - Section A~K 모두 포함
   - 프롬프트 템플릿, 테스트 템플릿, DocOps 검증 완전 이관

2. **docs/v2/V2_ARCHITECTURE.md**
   - Engine-Centric 설계 계약
   - OrderIntent, Adapter, Engine 플로우

3. **docs/v2/design/** (설계 문서)
   - SSOT_MAP.md: 전체 SSOT 목록 및 규칙
   - EVIDENCE_FORMAT.md: 실행 증거 저장 포맷
   - NAMING_POLICY.md: 네이밍 정책
   - INFRA_REUSE_INVENTORY.md: V1 인프라 재사용 전략
   - SSOT_DATA_ARCHITECTURE.md: Cold/Hot Path
   - SSOT_SYNC_AUDIT.md: 정합성 감사
   - CLEANUP_CANDIDATES.md: 폐기/정리 대상 추적
   - V2_MIGRATION_STRATEGY.md: V1→V2 전환 원칙

---

## 강제 규칙 (항상 동일, 생략 금지) - 확장

### SSOT 원칙
- ✅ D_ROADMAP.md 단 1개 (유일한 원천)
- ✅ D번호 의미 불변 (확장은 브랜치 Dxxx-y-z만)
- ✅ 기존 목표 / AC / 증거 요구사항 절대 삭제 금지
- ✅ 새 문제 발견 시 "추가(additive)"만 허용 (덮어쓰기 / 축소 / 무효화 금지)
- ✅ AC 이관 시 원본/목적지 모두 표기 필수 (MOVED_TO / FROM)
- ✅ COMPLETED 단계 합치기 금지 (새 D/새 브랜치만 허용)
- ✅ 3점 리더 / 임시 마커 금지 (축약 흔적 제거)

### 개발 원칙
- ✅ 돈 버는 아비트라지 로직 / 알고리즘 우선
- ✅ 엔진 중심 구조 (arbitrage/v2/**)
- ✅ scan-first → reuse-first
- ✅ 중복 / 반복 금지

### 검증 원칙
- ✅ Gate 3단 강제 (Doctor / Fast / Regression)
- ✅ 증거(Evidence) 없으면 PASS 주장 금지
- ✅ Wallclock Verification (장기/대기/모니터링 작업 필수)
- ✅ watch_summary.json 자동 생성 필수
- ✅ check_ssot_docs.py ExitCode=0 강제 (물리적 증거만)
- ✅ Gate 회피 금지 (워딩 꼼수, 파일 삭제, 인간 판정 개입 금지)

### DocOps 원칙 (신규)
- ✅ DocOps Always-On (커밋 전 필수)
- ✅ Gate (A) SSOT 자동 검사: python scripts/check_ssot_docs.py
- ✅ Gate (B) ripgrep 위반 탐지: cci, 이관/migrate/migration, TODO/TBD/PLACEHOLDER
- ✅ Gate (C) Pre-commit sanity: git status, git diff --stat
- ✅ Design Docs 정독 강제 (최소 2개, Reading Tax 필수)
- ✅ D000 META 태그 강제 ([META] 필수)

### 운영 원칙
- ✅ 작업 종료 시 반드시 Git commit (+ push)
- ✅ 필요 시 DB / Redis / 프로세스 / 캐시 정리 강제
- ✅ 실패 시 오염 방지 (Rollback 원칙)

---