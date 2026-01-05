# ⚠️ DEPRECATED: SSOT_DOCOPS.md

**이 파일은 DEPRECATED되었습니다.**

**통합 날짜:** 2026-01-05  
**통합 커밋:** [D000-1] SSOT Rules 헌법 통합  
**통합 위치:** `docs/v2/SSOT_RULES.md` Section E (DocOps / SSOT Audit)

---

## ❌ WARNING: 이 파일을 참조하여 작업하지 마세요

**모든 규칙은 `docs/v2/SSOT_RULES.md`로 통합되었습니다.**

이 파일을 참조하여 작업할 시 **즉시 FAIL** 처리됩니다.

---

## 통합 이유

**문제:**
- 규칙이 3개 파일에 분산 (D_PROMPT_TEMPLATE, D_TEST_TEMPLATE, SSOT_DOCOPS)
- Windsurf가 "최근에 본 것만" 따라가서 SSOT 파손 재발
- AC 누락/단계 합치기/ellipsis 사고 유발

**해결:**
- SSOT_RULES.md에 모든 규칙 통합 (Section B/C/D/E/F/G/H)
- "규칙은 SSOT_RULES만" 원칙 확립
- 규칙 단일화로 재발 방지

---

## 올바른 참조 방법

**DocOps Always-On 절차 & SSOT 자동 검사를 확인하려면:**
```
docs/v2/SSOT_RULES.md
→ Section E: DocOps / SSOT Audit (Always-On)
```

**기타 Section:**
- Section B: AC 이관 프로토콜
- Section C: Work Prompt Template (Step 0~9)
- Section D: Test Template (자동화/운영급)
- Section F: Design Docs 참조 규칙
- Section G: COMPLETED 단계 합치기 금지
- Section H: Ellipsis(...) / Placeholder 금지

---

## 아래 내용은 참조 금지 (DEPRECATED)

**이 파일의 나머지 내용은 SSOT_RULES.md로 완전 이관되었으며, 중복 방지를 위해 참조를 금지합니다.**

---

# (아래 내용은 DEPRECATED - 참조 금지)

## 1) 불변 규칙 (SSOT 핵심 4문장)

아래 4개는 **항상 D_ROADMAP 전역 규칙 섹션에 존재**해야 하며, 다른 문서들은 이를 “동일 의미”로 따라야 한다.

1) SSOT는 `D_ROADMAP.md` 단 1개 (충돌 시 D_ROADMAP 채택)  
2) D 번호 의미는 불변(Immutable Semantics)  
3) 확장은 브랜치(Dxxx-y-z)로만(이관/재정의 금지)  
4) DONE/COMPLETED는 Evidence 기반(문서 기반 완료 금지)

## 2) ALWAYS-ON 절차 (커밋 전에 무조건 수행)

### 2-1) Read & Map (작업 시작 시, 3~5분)
- `D_ROADMAP.md` 전역 규칙 섹션을 열고, 위 “핵심 4문장”이 실제로 박혀있는지 확인
- `SSOT_RULES / SSOT_MAP / V2_ARCHITECTURE`에서 **같은 의미가 문장 수준으로 존재**하는지 확인
- 금지 표현: “체인(→)”처럼 우선순위를 오해하게 만드는 표현
  - 반드시 **Hierarchy + conflict rule(충돌 시 D_ROADMAP)** 형태로 쓴다

### 2-2) Edit & Sync (편집 후)
- `D_ROADMAP.md`를 바꿨다면 같은 턴에 아래도 동기화(누락=FAIL)
  - `SSOT_RULES.md`, `SSOT_MAP.md`, `V2_ARCHITECTURE.md`, 관련 `REPORT.md`

### 2-3) DocOps Gate (커밋 직전, 자동 검증)
아래는 “요약 PASS 선언”을 원천 차단하는 **필수 자동 검증**이다.

#### (A) SSOT 자동 검사 스크립트 (필수)
```bash
python scripts/check_ssot_docs.py
```
- **Exit code 0** 아니면 즉시 중단(FAIL)
- 출력(로그)을 Evidence/리포트에 남겨야 DONE 가능

#### (B) ripgrep(잔재/오해/위반 탐지) (필수)
```bash
# 로컬/IDE 링크 잔재(cci:) 제거
rg "cci:" -n docs/v2 D_ROADMAP.md

# “이관” 표현은 사고 유발 확률이 높음 (남아있으면 원칙적으로 FAIL)
rg "이관|migrate|migration" -n docs/v2 D_ROADMAP.md

# TODO/TBD/placeholder가 COMPLETED 문서에 남아있으면 FAIL 신호
rg "TODO|TBD|PLACEHOLDER" -n docs/v2 D_ROADMAP.md
```
- 특정 D 단계(예: D205) 이슈가 있으면 **그 D 번호를 추가로 grep**해서 오라벨 잔재를 제거한다.
  - 예: `rg "D205-11" -n docs/v2 D_ROADMAP.md`

#### (C) Pre-commit sanity (필수)
```bash
git status
git diff --stat
```
- “원래 의도한 범위” 밖 파일이 섞였으면 FAIL (범위 밖 수정은 즉시 롤백)

## 3) Evidence 저장 규칙 (gitignore와 충돌할 때의 정답)

원칙: **DocOps Gate의 결과(명령 + 결과 요약)는 커밋 가능한 형태로 남겨야 한다.**

- 추천: 각 D 리포트(`docs/v2/reports/...`)에 아래를 기록
  - 실행한 명령(원문)
  - exit code
  - 핵심 결과(예: 발견 0건 / 발견 N건 + 수정 내역)
- 런타임 로그(대용량)는 gitignore여도 OK지만,
  **검증 결과 요약(텍스트)**은 리포트에 남겨야 SSOT와 궁합이 맞다.

## 4) “한 번에 끝내는” 정의 (DONE 조건에 반드시 포함)

- DocOps Gate (A/B/C) **전부 PASS**
- SSOT 4점 문서(`D_ROADMAP/SSOT_RULES/SSOT_MAP/V2_ARCHITECTURE`) 의미 동기화 완료
- 리포트에 DocOps 증거(명령 + 결과) 포함
- 그 다음에만 git commit/push

---

이 문서는 “문서 턴만” 읽는 게 아니다.  
**매 턴 커밋 전에 읽고, 매 턴 커밋 전에 돌려라.** (혈압과 크레딧 보호 장치)
