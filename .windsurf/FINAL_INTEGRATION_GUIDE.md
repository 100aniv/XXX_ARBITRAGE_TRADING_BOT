# 최종 SSOT 자동화 체계 (완벽한 구조)

## 📋 개요

이 문서는 `@[D_PROMPT_TEMPLATE.md]`와 `@[D_TEST_TEMPLATE.md]`를 기반으로 구축된 **완벽한 SSOT 자동화 체계**입니다.

**핵심 특징**:
- ✅ 두 템플릿 명확히 구분 (일반 작업 vs 테스트)
- ✅ 모든 파일에 템플릿 참조 (@[D_PROMPT_TEMPLATE.md], @[D_TEST_TEMPLATE.md])
- ✅ 워크플로우 분리 (일반/테스트)
- ✅ 규칙 확장 (WORKSPACE_RULES_EXTENSION.md)
- ✅ 선택적 실행 (스모크 테스트는 필요할 때만)

---

## 🎯 4층 구조

### 1층: 메모리 (자동 로드)
프롬프트 헤더에 따라 자동으로 로드됩니다.

#### 메모리 1: 일반 작업 (ID: 60ece762-d516-49a7-8346-36eb6117ab02)
```
[Windsurf PROMPT] Dxxx-y <단계명>
```
→ 9단계 작업 플로우 자동 로드

#### 메모리 2: 테스트 (ID: 01225f05-4b15-4d40-860f-cccf78364472)
```
[Windsurf TEST PROMPT] Dxxx-y TEST / VALIDATION
```
→ 6단계 테스트 플로우 자동 로드

### 2층: 템플릿 파일 (참조)
모든 세부사항은 이 파일들을 우선 참조하세요.

#### @[D_PROMPT_TEMPLATE.md] (일반 작업)
- 9단계 플로우 상세 설명
- SSOT 강제 규칙
- DocOps Gate
- V1/V2 Boundary Guard
- Closeout Summary 양식

#### @[D_TEST_TEMPLATE.md] (테스트)
- 6단계 테스트 플로우 상세 설명
- 테스트 절대 원칙
- FAIL 처리 규칙
- Evidence 패키징

### 3층: 워크플로우 (실행 절차)
각 단계별 구체적 실행 절차를 명시합니다.

#### /WORK_PROMPT_FLOW (일반 작업)
- 9단계 플로우
- 각 단계별 @[D_PROMPT_TEMPLATE.md] 참조 링크
- 필수/선택 사항 명시

#### /TEST_PROMPT_FLOW (테스트)
- 6단계 테스트 플로우
- 각 단계별 @[D_TEST_TEMPLATE.md] 참조 링크
- 필수/선택 사항 명시

### 4층: 규칙 (강제 사항)
프로젝트 전역 강제 규칙입니다.

#### arbitrage-workspace-rule.md (기존)
- SSOT 단일화
- scan-first → reuse-first
- Gate 통과 전 상태 선언 금지
- 0번 부트스트랩 필수

#### WORKSPACE_RULES_EXTENSION.md (신규)
- 프롬프트 템플릿 분리 규칙
- 일반 작업 / 테스트 구분
- SSOT DocOps Gate
- V1/V2 Boundary Guard

---

## 🚀 사용 방법

### 일반 작업 시작

#### 1) 프롬프트 헤더 작성
```
[Windsurf PROMPT] Dxxx-y <단계명>

모델: Claude Thinking (3 credits)

범위(Scope):
이번 턴에서 수정 허용 파일/모듈 경계

DONE 정의:
SSOT 기준(로드맵 + 증거 + Gate + 커밋)을 모두 충족한 경우에만 DONE 선언 가능
```

#### 2) 자동 로드 확인
- 메모리 1 자동 로드 (60ece762-d516-49a7-8346-36eb6117ab02)
- 규칙 자동 로드 (arbitrage-workspace-rule.md)

#### 3) 참조 파일 확인
- @[D_PROMPT_TEMPLATE.md] (전제 규칙, 9단계 플로우)
- /WORK_PROMPT_FLOW (워크플로우)

#### 4) Step 0~8 순차 진행
- Step 0: 부트스트랩
- Step 1~8: 순차 진행
- Step 9: Closeout Summary (자동 생성)

### 테스트 작업 시작

#### 1) 프롬프트 헤더 작성
```
[Windsurf TEST PROMPT] Dxxx-y TEST / VALIDATION

모델: Claude Thinking (3 credits)

DONE 정의:
- 모든 테스트 단계 PASS
- Evidence + Metrics + Logs 확보
- D_ROADMAP 업데이트
- Git commit + push
```

#### 2) 자동 로드 확인
- 메모리 2 자동 로드 (01225f05-4b15-4d40-860f-cccf78364472)
- 규칙 자동 로드 (arbitrage-workspace-rule.md)

#### 3) 참조 파일 확인
- @[D_TEST_TEMPLATE.md] (테스트 절대 원칙, 6단계 플로우)
- /TEST_PROMPT_FLOW (워크플로우)

#### 4) 필수/선택 단계 실행
- **필수**: Step 0, Step 1, Step 2
- **선택**: Step 3, Step 4, Step 5 (필요할 때만)

---

## 📁 파일 구조

```
c:\work\XXX_ARBITRAGE_TRADING_BOT\
├── D_PROMPT_TEMPLATE.md (기존 - 일반 작업 전문)
├── D_TEST_TEMPLATE.md (기존 - 테스트 전문)
└── .windsurf/
    ├── FINAL_INTEGRATION_GUIDE.md (신규 - 이 파일)
    ├── WORKSPACE_RULES_EXTENSION.md (신규 - 규칙 확장)
    ├── rules/
    │   └── arbitrage-workspace-rule.md (기존 - 규칙)
    └── workflows/
        ├── WORK_PROMPT_FLOW.md (신규 - 일반 작업 플로우)
        ├── TEST_PROMPT_FLOW.md (신규 - 테스트 플로우)
        └── (기존 8개 워크플로우 - 참고용)
```

---

## ✅ 체크리스트

### 일반 작업 시작 전
- [ ] 프롬프트 헤더: `[Windsurf PROMPT] Dxxx-y <단계명>`
- [ ] 범위(Scope) 명확히 선언
- [ ] @[D_PROMPT_TEMPLATE.md] 참조 확인
- [ ] /WORK_PROMPT_FLOW 참조 확인
- [ ] 메모리 1 자동 로드 확인
- [ ] Step 0 부트스트랩 실행
- [ ] Step 1~8 순차 진행
- [ ] Step 9 Closeout Summary 작성
- [ ] Git commit + push 완료

### 테스트 작업 시작 전
- [ ] 프롬프트 헤더: `[Windsurf TEST PROMPT] Dxxx-y TEST / VALIDATION`
- [ ] @[D_TEST_TEMPLATE.md] 참조 확인
- [ ] /TEST_PROMPT_FLOW 참조 확인
- [ ] 메모리 2 자동 로드 확인
- [ ] Step 0 인프라 부트스트랩 실행
- [ ] Step 1 Fast Gate 실행 (필수)
- [ ] Step 2 Core Regression 실행 (필수)
- [ ] Step 3~5 선택적 실행 (필요할 때만)
- [ ] Evidence 패키징
- [ ] D_ROADMAP 업데이트
- [ ] Git commit + push 완료

---

## 🔑 핵심 원칙

### SSOT 원칙
- **SSOT = D_ROADMAP.md 단 1개**
- 목표, AC, 증거 요구사항 절대 삭제 금지
- 코드/테스트/문서가 ROADMAP과 충돌하면 항상 ROADMAP 우선

### 템플릿 분리
- **일반 작업**: @[D_PROMPT_TEMPLATE.md] 참조
- **테스트**: @[D_TEST_TEMPLATE.md] 참조
- 두 템플릿은 **구분해서 사용**

### 선택적 실행
- 스모크 테스트는 **항상 하는 것이 아님**
- 필요할 때만 Step 3~5 실행
- 각 템플릿 파일에서 상세 확인

### Gate 3단 강제
- Doctor / Fast / Regression
- 100% PASS 전 DONE 선언 금지

### 증거 기반 DONE
- Evidence 없으면 PASS 주장 금지
- AC + Evidence 일치 시에만 COMPLETED 선언

---

## 📞 문제 해결

### 메모리가 로드되지 않는 경우
- 프롬프트 헤더 확인
- 메모리 ID 확인: 60ece762-d516-49a7-8346-36eb6117ab02 (일반) / 01225f05-4b15-4d40-860f-cccf78364472 (테스트)
- 수동 로드: `@memory:60ece762-d516-49a7-8346-36eb6117ab02`

### 워크플로우가 실행되지 않는 경우
- 워크플로우 파일 존재 확인: `/WORK_PROMPT_FLOW`, `/TEST_PROMPT_FLOW`
- 워크플로우 문법 확인

### 규칙이 적용되지 않는 경우
- 규칙 파일 확인: `.windsurf/rules/arbitrage-workspace-rule.md`
- 확장 규칙 확인: `.windsurf/WORKSPACE_RULES_EXTENSION.md`

---

## 🎓 학습 경로

1. **@[D_PROMPT_TEMPLATE.md]** 읽기 (일반 작업 전문)
2. **@[D_TEST_TEMPLATE.md]** 읽기 (테스트 전문)
3. **/WORK_PROMPT_FLOW** 또는 **/TEST_PROMPT_FLOW** 참조
4. 프롬프트 헤더 선택 및 작업 시작

---

## 📊 최종 요약

| 항목 | 일반 작업 | 테스트 |
|------|---------|--------|
| 프롬프트 헤더 | `[Windsurf PROMPT]` | `[Windsurf TEST PROMPT]` |
| 템플릿 | @[D_PROMPT_TEMPLATE.md] | @[D_TEST_TEMPLATE.md] |
| 메모리 ID | 60ece762-d516-49a7-8346-36eb6117ab02 | 01225f05-4b15-4d40-860f-cccf78364472 |
| 워크플로우 | /WORK_PROMPT_FLOW | /TEST_PROMPT_FLOW |
| 단계 수 | 9단계 (Step 0~8) | 6단계 (Step 0~5) |
| 필수 단계 | 모두 | Step 0, 1, 2 |
| 선택 단계 | 없음 | Step 3, 4, 5 |

---

**생성일**: 2026-01-03  
**버전**: 3.0 (완벽한 구조 - 템플릿 분리 + 워크플로우 분리 + 규칙 확장)  
**상태**: ✅ 완전 자동화 체계 구축 완료
