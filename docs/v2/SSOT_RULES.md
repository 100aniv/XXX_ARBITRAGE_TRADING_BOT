# V2 SSOT Rules — Core (헌법)

**Version:** 2.2 (Slim, 20260221)
**Archive:** docs/v2/archive/SSOT_RULES_FULL_20260221.md (원본 100% 동결)
**Appendix:** docs/v2/appendix/SSOT_RULES_APPENDIX_1.md (Section F~N 상세)
**Status:** ENFORCED

> **충돌 해결(conflict_resolution):** SSOT_RULES.md > D_ROADMAP.md > OPS_PROTOCOL.md > V2_ARCHITECTURE.md
> 문서 간 충돌 시 이 순서로 우선 적용. D_ROADMAP.md는 상태/목표/AC의 유일 원천.

---

## ALPHA FAST LANE (D_ALPHA-*)

- **NO-ASK:** 사용자를 멈춰 세우는 질문(승인 UI/스코프/선택지) 금지
- **AUTO-SCOPE:** 스코프는 D_ROADMAP IN_PROGRESS + git diff로 자동 확정
- **DEFAULT ACTION:** 스코프 밖 대량 변경 감지 시 "문서/리포트만 커밋 + 나머지 stash"가 기본값
- **NET-READ PRE-AUTH:** ticker/orderbook/market data read는 사전 승인
- **ALPHA 증거 최소셋:** kpi.json + manifest.json + edge_survey_report.json만 있으면 "Done(Alpha)" 인정

---

## 핵심 원칙

### 1. SSOT는 D_ROADMAP.md 단 1개 (ssot_single_source)
- ❌ **금지:** D_ROADMAP_V2.md, D_ROADMAP_V3.md 같은 SSOT 분기
- ✅ **허용:** D_ROADMAP.md 내부에서 V2 섹션으로 관리

### 1-1. D 번호 의미는 불변 (immutable_semantics)
- ❌ **금지:** 기존 D 번호의 의미를 다른 작업으로 변경, AC를 다른 D로 이동하여 스코프 축소
- ✅ **허용:** 추가 작업은 브랜치(branching_only, Dxxx-y-z)로만 확장
- ✅ **허용 (신규):** REBASELOG가 있는 경우 D 번호 재배치/재정의

**브랜치 네이밍:** `Dxxx-y-z` (xxx=메인 D번호, y=브랜치번호, z=서브브랜치)

### 1-2. Sovereign AI Execution (자율 집도권)
- `arbitrage/v2/**` 및 `tests/**`에 대해 사전 승인된 무제한 수정/생성 권한
- Zero-Stop Policy: 환경 이슈 발생 시 묻지 말고 즉시 해결 후 완주

### 1-3. Task ID Resolution & RERUN Policy
- Task ID는 D_ROADMAP.md의 IN PROGRESS 섹션에서 1개 확정
- COMPLETED 재사용 금지, 재실행은 `RERUN`으로 표시

### 2. Report 파일명 규칙
- **메인 D:** `docs/v2/reports/Dxxx/Dxxx_REPORT.md`
- **브랜치 D:** `docs/v2/reports/Dxxx/Dxxx-y_REPORT.md`
- **필수 섹션:** Goal, AC, Implementation, Gate Result, Evidence, PASS/FAIL

**SSOT 우선순위:**
1. D_ROADMAP.md (상태/목표/AC의 유일 원천)
2. docs/v2/reports/Dxxx/Dxxx-y_REPORT.md (검증 결과 공식 문서)
3. logs/evidence/Dxxx-y_*/ (실행 증거)

### 3. 문서 경로 규칙
- V2 신규 문서: `docs/v2/` 아래에만 작성
- V1 레거시: `docs/` 아래 Read-only (수정 금지)
- Evidence: `logs/evidence/`에만 저장 (docs/v2/evidence/ 금지)

---

## 강제 금지 사항

1. **파괴적 이동/삭제 금지** — arbitrage/ 전체 리팩토링, 대량 파일 이동 금지
2. **오버리팩토링 금지** — Engine 중심 플로우 뼈대만 최소 구현
3. **스크립트 중심 실험 폐기** — run_d108_*.py 같은 일회성 스크립트 금지

---

## Scan-First → Reuse-First (강제)

1. **(Scan-First)** 구현 전 repo 검색으로 기존 모듈 확인 (rg/grep)
2. **(Reuse-First)** 기존 모듈이 있으면 새 파일/모듈 생성 금지, 확장만 허용
3. **(No Duplicate)** 동일 목적의 v2_* / new_* / experimental_* 중복 모듈 생성 금지
4. **(Exception)** 새 모듈이 필요하면 "왜 기존 것을 못 쓰는지" 보고서에 명시

---

## "돈버는 알고리즘 우선" 원칙

- **D205-4~9:** Profit Loop (측정/튜닝/검증) 필수
- **D205-10~12:** 돈버는 알고리즘 최적화 필수
- **Phase 2 (D206~D209):** Core Path 필수
- **LIVE 진입:** D209 완료 후 즉시 가능 (Phase 3 완료 여부 무관)

**Profit Loop 강제 규칙:**
- D206 진입 조건: D205-12 PASS 필수
- LIVE 진입 조건: D209 PASS 필수
- Record/Replay 없으면 D205-7 (Parameter Sweep) 진입 금지
- winrate 0% 또는 100% → PASS 아님, 계약/측정 검증 단계로 강제 이동

---

## 검증 규칙 (GATE 통과 필수)

### Gate 3단 (evidence_based_done)
모든 V2 작업은 아래 GATE를 100% PASS해야 커밋 가능:
1. **Doctor Gate:** `pytest --collect-only` 성공
2. **Fast Gate:** 핵심 테스트 100% PASS
3. **Regression Gate:** 베이스라인 테스트 100% PASS

### DONE 조건 (전부 만족 필수)
- DocOps Gate: ExitCode=0
- pytest: ExitCode=0 AND SKIP=0
- D_ROADMAP: 상태/AC/증거/커밋 정확히 일치
- Evidence: logs/evidence/에 manifest.json 포함 최소셋 존재

### DocOps Always-On (커밋 전 필수)
```bash
python scripts/check_ssot_docs.py          # Gate A: ExitCode=0 필수
python scripts/check_docops_tokens.py ...  # Gate B: 토큰 정책
git status && git diff --stat              # Gate C: 범위 확인
```

---

## Section B: AC 이동 프로토콜 (강제)

- AC는 절대 삭제하지 않음
- 이동 시 원본: `~~내용~~ [MOVED_TO: <목적지 D> / <날짜> / <커밋> / <사유>]`
- 이동 시 목적지: `[ ] AC-N: 내용 [FROM: <원본 D> AC-<번호>]`

---

## Section C: Work Prompt Step 0~9 (강제)

| Step | 내용 |
|------|------|
| 0 | Bootstrap: 증거폴더 생성, Git 상태 확인, SSOT 문서 정독 (D_ROADMAP → SSOT_RULES → design/ 최소 2개) |
| 1 | Repo Scan: 재사용 모듈 3~7개 목록화 (SCAN_REUSE_SUMMARY.md) |
| 2 | Plan: AC를 코드/테스트/증거로 어떻게 충족할지 5~12줄 |
| 3 | Implement: arbitrage/v2/** 중심, Context 관리 (불필요 파일 제거) |
| 4 | Tests: 유닛 테스트 → Gate 3단 순차 실행 (하나라도 FAIL 시 즉시 중단) |
| 5 | Smoke: edge→exec_cost→net_edge 수치 존재 확인, 0 trades → DecisionTrace |
| 6 | Evidence 패키징: manifest.json + kpi.json (필수), decision_trace.json (선택) |
| 7 | 문서 업데이트: D_ROADMAP.md 상태/커밋/Gate결과/Evidence 경로 업데이트 |
| 8 | Git: `git commit -m "[Dxxx-y] <one-line summary>"` + push |
| 9 | Closeout Summary: Commit SHA, Gate Results, KPI, Evidence 경로 전부 명시 |

**Step 0 필수 정독 순서:**
1. D_ROADMAP.md
2. docs/v2/SSOT_RULES.md (본 문서)
3. docs/v2/design/SSOT_MAP.md
4. docs/v2/design/** (해당 단계 관련 최소 2개)
5. 직전 단계 docs/v2/reports/Dxxx/*

---

## Section D: Test Template (자동화/운영급)

**테스트 절대 원칙:**
- 테스트는 사람 개입 없이 자동 실행, 중간 질문 금지
- FAIL 시 즉시 중단 → 수정 → 동일 프롬프트 재실행

**Smoke 유형:**
- **Micro-Smoke (1분):** 설정/문서만 수정 시 (프로세스 시작/종료 검증)
- **Full Smoke (20분):** Engine/Adapter/Detector 코드 변경 시 (주문 ≥ 1 필수)

**Wallclock Verification (장기 실행 필수):**
- `watch_summary.json` 자동 생성 필수
- `completeness_ratio ≥ 0.95` PASS, `stop_reason = ERROR` FAIL
- 시간 기반 완료 선언 금지 — watch_summary.json 필드 인용만 허용

---

## Section E: DocOps / SSOT Audit (Always-On)

**DocOps 불변 규칙 (SSOT 핵심 4문장):**
1. SSOT는 `D_ROADMAP.md` 단 1개 (충돌 시 D_ROADMAP 채택)
2. D 번호 의미는 불변 (Immutable Semantics)
3. 확장은 브랜치(Dxxx-y-z)로만 (이동/재정의 금지)
4. DONE/COMPLETED는 Evidence 기반 (실행 증거 필수)

**check_ssot_docs.py ExitCode=0 강제:**
- ExitCode=1이면 무조건 FAIL (이유 불문)
- "스코프 내 PASS" 같은 인간 판정 금지, 물리적 증거만 인정
- 증거: `ssot_docs_check_exitcode.txt` (내용: `0`) 필수

---

## 경로 규칙

```
docs/v2/
  ├── SSOT_RULES.md          # 본 문서 (Core)
  ├── archive/               # 원본 동결 (SSOT_RULES_FULL_YYYYMMDD.md)
  ├── appendix/              # 상세 섹션 (SSOT_RULES_APPENDIX_N.md)
  ├── V2_ARCHITECTURE.md
  ├── design/
  ├── reports/
  └── templates/

logs/evidence/
  └── <run_id>/
      ├── manifest.json
      ├── gate.log
      ├── git_info.json
      └── cmd_history.txt
```

---

## 위반 시 조치

| 위반 유형 | 조치 |
|-----------|------|
| SSOT 위반 (Critical) | 새 ROADMAP 파일 즉시 삭제 |
| Gate 미통과 (Blocker) | 커밋 금지, 즉시 수정 후 재검증 |
| Gate 회피 (Data Manipulation) | 즉시 FAIL + Revert, 프로젝트 중단 경고 |
| COMPLETED 합치기 | 즉시 FAIL, 새 D/새 브랜치로 분리 |
| 3점 리더/임시 마커 | 즉시 중단, 전체 내용 명시 후 재실행 |
| ExitCode≠0 DONE 선언 | 즉시 FAIL + 작업 Revert |

---

## Closeout Summary 강제 템플릿

```markdown
# D<number> Closeout Summary
## Commit & Branch
- Commit SHA: <full_sha> (short: <short_sha>)
- Branch: <branch_name>
## Gate Results
- Doctor: <PASS/FAIL>
- Fast: <PASS/FAIL>
- Regression: <PASS/FAIL>
## Evidence
- Path: logs/evidence/<run_id>/
- Files: manifest.json, gate.log, git_info.json, cmd_history.txt
## Next Step
- D<next>: <next_task_title>
```

---

## 참고 문서

- `D_ROADMAP.md` — 프로젝트 전체 로드맵 (SSOT)
- `docs/v2/V2_ARCHITECTURE.md` — V2 아키텍처 정의
- `docs/v2/OPS_PROTOCOL.md` — 운영 절차 런북
- `docs/v2/appendix/SSOT_RULES_APPENDIX_1.md` — Section F~N 상세
- `docs/v2/archive/SSOT_RULES_FULL_20260221.md` — 원본 동결본

---

**이 규칙은 V2 개발 전반에 걸쳐 강제 적용되며, 위반 시 작업이 차단됩니다.**
