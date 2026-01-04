---
description: Workspace Rules 확장 (arbitrage-workspace-rule.md에 추가할 내용)
---

# Workspace Rules 확장

## 추가 위치
`arbitrage-workspace-rule.md` 파일의 `---trigger: always_on---` 섹션 아래에 다음 내용을 추가하세요.

---

## 프롬프트 템플릿 분리 (2가지 구분)

### 1) 일반 작업 프롬프트
**참조**: @[D_PROMPT_TEMPLATE.md]  
**헤더**: `[Windsurf PROMPT] Dxxx-y <단계명>`  
**메모리**: 60ece762-d516-49a7-8346-36eb6117ab02 (자동 로드)  
**워크플로우**: /WORK_PROMPT_FLOW  
**플로우**: 9단계 (Step 0~8)

**적용 대상**:
- 코드 구현
- 설계 작업
- 리팩토링
- 문서 작성

**필수 단계**:
- Step 0: 부트스트랩
- Step 1~8: 순차 진행
- Step 9: Closeout Summary (자동 생성)

**전제 규칙** (@[D_PROMPT_TEMPLATE.md] 참조):
- SSOT = D_ROADMAP.md 단 1개
- 목표, AC, 증거 요구사항 절대 삭제 금지
- D번호 의미 불변 (확장은 브랜치 Dxxx-y-z로만 허용)
- 돈 버는 아비트라지 로직 우선
- 엔진 중심 구조 (arbitrage/v2/** 알맹이, scripts는 CLI만)
- scan-first → reuse-first
- Gate 3단 강제 (Doctor/Fast/Regression)
- 증거(Evidence) 없으면 PASS 주장 금지
- 작업 종료 시 반드시 Git commit + push

### 2) 테스트 프롬프트
**참조**: @[D_TEST_TEMPLATE.md]  
**헤더**: `[Windsurf TEST PROMPT] Dxxx-y TEST / VALIDATION`  
**메모리**: 01225f05-4b15-4d40-860f-cccf78364472 (자동 로드)  
**워크플로우**: /TEST_PROMPT_FLOW  
**플로우**: 6단계 테스트 (Step 0~5)

**적용 대상**:
- Gate 실행 (Doctor, Fast, Regression)
- 스모크 테스트
- 성능 검증
- 회귀 테스트

**필수 단계**:
- Step 0: 인프라 부트스트랩
- Step 1: 코드 무결성 & Fast Gate
- Step 2: Core Regression

**선택 단계** (필요할 때만):
- Step 3: Smoke PAPER Test
- Step 4: Monitoring 검증
- Step 5: Extended PAPER

**테스트 절대 원칙** (@[D_TEST_TEMPLATE.md] 참조):
- 자동 실행 (사람 개입 없음)
- 중간 질문 금지
- FAIL 시 즉시 중단 → 수정 → 동일 프롬프트 재실행
- 의미 있는 지표 필수

## 중요 사항

### 두 템플릿 명확히 구분
- 일반 작업과 테스트는 **별도의 프롬프트 헤더** 사용
- 각 템플릿 파일 **전문 참조** (누락 방지)
- 메모리 자동 로드 확인

### 선택적 실행
- 스모크 테스트는 **항상 하는 것이 아님**
- 필요할 때만 Step 3~5 실행
- 각 템플릿 파일에서 상세 확인

### 워크플로우 참조
- 일반 작업: `/WORK_PROMPT_FLOW` (9단계)
- 테스트: `/TEST_PROMPT_FLOW` (6단계, 선택적)

## SSOT DocOps Gate (ALWAYS-ON)
@[D_PROMPT_TEMPLATE.md] 참조:

### 1) 자동 검사 (필수)
```bash
python scripts/check_ssot_docs.py
```

### 2) ripgrep 위반 탐지 (필수)
```bash
rg "cci:" -n docs/v2 D_ROADMAP.md
rg "이관|migrate|migration" -n docs/v2 D_ROADMAP.md
rg "TODO|TBD|PLACEHOLDER" -n docs/v2 D_ROADMAP.md
```

### 3) Evidence 기록 (필수)
위 명령/출력을 `docs/v2/reports/<Dxxx>/..._REPORT.md`에 기록

### 4) 그 다음에만 Git
```bash
git status
git diff --stat
git diff
```

## V1/V2 Boundary Guard (ALWAYS-ON / Fast Gate 연결)
@[D_PROMPT_TEMPLATE.md] 참조:

```bash
python scripts/check_v1_v2_boundary.py
```

---

**생성일**: 2026-01-03  
**상태**: arbitrage-workspace-rule.md에 추가할 확장 규칙  
**적용**: 모든 Dxxx 작업
