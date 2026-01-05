# ⚠️ DEPRECATED: D_PROMPT_TEMPLATE.md

**이 파일은 DEPRECATED되었습니다.**

**통합 날짜:** 2026-01-05  
**통합 커밋:** [D000-1] SSOT Rules 헌법 통합  
**통합 위치:** `docs/v2/SSOT_RULES.md` Section C (Work Prompt Template)

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

**Step 0~9 작업 플로우를 확인하려면:**
```
docs/v2/SSOT_RULES.md
→ Section C: Work Prompt Template (Step 0~9)
```

**기타 Section:**
- Section B: AC 이관 프로토콜
- Section D: Test Template (자동화/운영급)
- Section E: DocOps / SSOT Audit (Always-On)
- Section F: Design Docs 참조 규칙
- Section G: COMPLETED 단계 합치기 금지
- Section H: Ellipsis(...) / Placeholder 금지

---

## 아래 내용은 참조 금지 (DEPRECATED)

**이 파일의 나머지 내용은 SSOT_RULES.md로 완전 이관되었으며, 중복 방지를 위해 참조를 금지합니다.**

---

# (아래 내용은 DEPRECATED - 참조 금지)

0) 헤더 (항상 동일)

[Windsurf PROMPT] Dxxx-y <단계명>

모델: Claude Thinking (3 credits)

범위(Scope):
이번 턴에서 수정 허용 파일/모듈 경계

DONE 정의:
SSOT 기준(로드맵 + 증거 + Gate + 커밋)을
모두 충족한 경우에만 DONE 선언 가능


────────────────────────────────
1) 전제 / 강제 규칙 (항상 동일, 생략 금지)
────────────────────────────────

SSOT = D_ROADMAP.md 단 1개
→ 모든 상태, 진실, 판단의 유일한 원천
→ 목표, AC, 증거 요구 사항을 포함한 “최상위 헌법”
→ 기존 목표 / AC / 증거 요구 사항은 절대 삭제 금지
→ 새 문제 발견 시 “추가(additive)”만 허용
   (덮어쓰기 / 축소 / 무효화 금지)
→ 코드 / 테스트 / 문서 / 의사결정이
   ROADMAP과 충돌하면 항상 ROADMAP이 우선

D번호 의미 불변
→ D번호는 절대 재정의하지 않는다
→ 확장은 브랜치(Dxxx-y-z)로만 허용
→ 단계 이관 / 병합 / 재번호 금지
→ D_ROADMAP.md가 유일 SSOT

SSOT 관련 보조 문서 체계
(ROADMAP을 보조·정의·동기화하는 문서들)

- docs/v2/SSOT_RULES.md
  - SSOT 철학
  - 변경 금지 원칙
  - Closeout / Evidence 규칙의 단일 정의

- docs/v2/SSOT_MAP.md
  - ROADMAP ↔ 설계 ↔ 코드 ↔ 증거 매핑 관계

- docs/v2/SSOT_DATA_ARCHITECTURE.md
  - 데이터 / 스토리지 / 이벤트 흐름의 SSOT 정의

- docs/v2/SSOT_SYNC_AUDIT.md
  - ROADMAP 기준 문서·코드 정합성 점검 기준

- docs/v2/V2_MIGRATION_STRATEGY.md
  - V1 → V2 전환 원칙
  - 재사용 / 폐기 / 유지 기준

- docs/v2/NAMING_POLICY.md
  - 파일 / 단계 / 지표 / 키 네이밍 규칙

- docs/v2/REDIS_KEYSPACE.md
  - Redis 키 구조 SSOT

- docs/v2/INFRA_REUSE_INVENTORY.md
  - 재사용 가능한 인프라 / 모듈 목록

- docs/v2/EVIDENCE_SPEC.md
- docs/v2/EVIDENCE_FORMAT.md
  - Evidence 구조 / 필수 항목 SSOT

- docs/v2/CLEANUP_CANDIDATES.md
  - 폐기 / 정리 대상 추적 (ROADMAP 기반)

- docs/v2/design/**
  - 도메인별 설계 SSOT
    (marketdata, execution_quality, risk, replay 등)

※ 위 문서들은 ROADMAP을 “대체”하지 않으며,
   ROADMAP의 정의를 보조·구체화·검증하는 역할만 수행한다.


돈 버는 아비트라지 로직 / 알고리즘 우선
→ 인프라 확장은 후순위 (필요할 때만)

엔진 중심 구조
→ 알맹이: arbitrage/v2/**
→ scripts/run_*.py 는
   “얇은 실행막(CLI / Wiring)”만 담당

scan-first → reuse-first
→ V1 유산 모듈 / 인프라 / 테스트 자산 재사용 우선
→ 생코딩은 “기존 모듈이 없을 때만”

중복 / 반복 금지
→ 이미 확인한 것을 다시 확인하며 크레딧 소모 금지

Gate 3단 강제
→ Doctor / Fast / Regression
→ 100% PASS 전 DONE 선언 금지

증거(Evidence) 없으면 PASS 주장 금지

Wallclock Verification (장기/대기/모니터링 작업 필수)
→ 장기 실행(≥1h) / 대기 / 모니터링 / Wait Harness 포함 작업은
  watch_summary.json 자동 생성 + 필수 필드 충족 전 DONE 선언 금지
→ 필수 필드:
  - started_at_utc, ended_at_utc (ISO 8601, timezone-aware)
  - monotonic_elapsed_sec (정확한 경과 시간, SSOT)
  - planned_total_hours, samples_collected, expected_samples
  - completeness_ratio (≥0.95 권장, EARLY_INFEASIBLE 등 예외 허용)
  - stop_reason (enum: TIME_REACHED | TRIGGER_HIT | EARLY_INFEASIBLE | ERROR | INTERRUPTED)
→ 시간 기반 완료 선언 금지:
  - "3h 완료", "10h 실행" 같은 문구는 watch_summary.json에서 자동 추출한 값만 사용
  - 인간이 손으로 시간 쓰는 것 금지 (재발 방지)
→ 상태 판단은 stop_reason 기반:
  - COMPLETED: TIME_REACHED + completeness_ratio ≥ 0.95
  - PARTIAL: EARLY_INFEASIBLE (시장 제약) 또는 completeness < 0.95
  - FAILED: ERROR 또는 예상치 못한 종료

작업 종료 시 반드시 Git commit (+ push)

필요 시 DB / Redis / 프로세스 / 캐시 정리 강제

실패 시 오염 방지 (Rollback 원칙)
→ Gate 진입 전 상태가 Clean 이었다면
→ 심각한 실패 시 덕지덕지 수정 금지
→ Revert 후 재설계 고려


────────────────────────────────
2) Step 0 — 부트스트랩 (강제, 문서 정독 포함)
────────────────────────────────

0-A. 작업 시작 증거 폴더 생성
logs/evidence/STEP0_BOOTSTRAP_<timestamp>/
- bootstrap_env.txt
- bootstrap_git.txt

0-B. Git / 브랜치 / 워킹트리 고정
- git rev-parse HEAD
- git branch --show-current
- git status --porcelain

Dirty 상태면:
- 이유 기록
- 원칙적으로 Clean 상태로 정리 후 시작

0-C. 캐시 / 중복 프로세스 / 런타임 오염 제거
- __pycache__ 제거
- 관련 python 프로세스 잔존 시 종료
  (수정 반영 누락 방지)

0-D. 인프라 전제 확인 (필요한 단계일 때만)
- Postgres / Redis / Docker 상태 점검
- 필요 시 SSOT 규칙에 따른 clean reset

0-E. SSOT 문서 정독 (도메인별)
정해진 순서로 읽고, 읽었다는 흔적을 Evidence에 남긴다.

필수 정독 순서:
1. D_ROADMAP.md
2. docs/v2/SSOT_RULES.md
3. docs/v2/SSOT_MAP.md
4. docs/v2/design/** (해당 단계 관련 문서)
5. 직전 단계 docs/v2/reports/Dxxx/*

Step 0 산출물 (증거):
- READING_CHECKLIST.md
- “이번 작업에서 무엇을 재사용하고
   무엇을 가져올지” 10줄 이내 요약


────────────────────────────────
3) Step 1 — Repo Scan (재사용 목록)
────────────────────────────────

목표:
- 새로 만들지 말고 이미 있는 것을 연결

산출물:
- SCAN_REUSE_SUMMARY.md
  - 재사용 모듈 3~7개
  - 재사용 이유 (각 1줄)

새 파일이 필요한 경우:
- “왜 없는지” 근거 명시


────────────────────────────────
4) Step 2 — Plan (이번 턴 작업 계획)
────────────────────────────────

- AC를 코드 / 테스트 / 증거로
  어떻게 충족할지만 기술
- 분량: 5~12줄

산으로 갈 선택:
- 과도한 리팩토링
- 인프라 확장
→ 여기서 사전 차단


────────────────────────────────
5) Step 3 — Implement (엔진 중심)
────────────────────────────────

알맹이 구현:
- arbitrage/v2/**

scripts/**:
- CLI 파라미터 파싱
- 엔진 호출만 담당

하위 호환 / 스키마 변경 시:
- optional 필드로 확장
- manifest에 version 명시

Context 관리:
- 구현 종료 후 테스트 전
- 불필요한 로그 / 참고 파일
  컨텍스트에서 제거


────────────────────────────────
6) Step 4 — Tests (유닛 → Gate)
────────────────────────────────

- 변경 범위 유닛 테스트

Gate 3단 순차 실행:
1. Doctor
2. Fast
3. Regression

하나라도 FAIL 시:
- 즉시 중단
- 수정
- 재실행

“Fast만 충분” 같은 예외 주장 금지
(SSOT상 3단 필수)


────────────────────────────────
7) Step 5 — Smoke / Reality Check
────────────────────────────────

Smoke의 의미:
- “안 죽는다”가 아니라
- 돈 버는 구조가 수치로 증명되는지

필수 검증:
- edge → exec_cost → net_edge 수치 존재

0 trades 발생 시:
- DecisionTrace로 차단 원인 수치화

Negative Evidence 원칙:
- 실패 / 이상 수치 발생 시
- 숨기지 말고 FAIL_ANALYSIS.md에 기록

모든 결과는 evidence로 고정


────────────────────────────────
8) Step 6 — Evidence 패키징 (SSOT)
────────────────────────────────

Evidence 최소 구성:
- manifest.json
- kpi.json

(필요 시)
- decision_trace.json
- latency.json
- leaderboard.json
- best_params.json

README.md:
- 재현 명령 3줄


────────────────────────────────
9) Step 7 — 문서 업데이트 (SSOT 정합성)
────────────────────────────────

9-A. D_ROADMAP.md 반드시 업데이트
- 상태 (DONE / IN PROGRESS)
- 커밋 SHA
- Gate 결과
- Evidence 경로

AC (증거 기반 검증) 항목 전체 업데이트
- 특정 수치 고정 금지
- “모든 AC 항목이 증거 기준으로
   업데이트됨”이 명확히 드러나야 함

9-B. SSOT 문서 동기화 강제 규칙

ROADMAP이 업데이트되었고,
그 변경이 기존 설계 / 규칙 / 구조와
연관된다면 아래 문서들은
반드시 검토 대상이 된다:

- docs/v2/SSOT_MAP.md
- docs/v2/SSOT_DATA_ARCHITECTURE.md
- docs/v2/SSOT_SYNC_AUDIT.md
- docs/v2/design/**
- docs/v2/INFRA_REUSE_INVENTORY.md
- docs/v2/CLEANUP_CANDIDATES.md
- 관련 docs/v2/reports/Dxxx/*

원칙:
- 구조 / 철학 변경 없으면 억지 업데이트 금지
- 단, 낡은 정의 / 불일치 / 누락 발견 시 반드시 수정
- ROADMAP과 불일치한 문서는 기술 부채로 간주
  → PASS 불가


────────────────────────────────
10) Step 8 — Git (강제)
────────────────────────────────

- git status
- git diff --stat
- SSOT 스타일 커밋 메시지
- git push


────────────────────────────────
11) Step 9 — Closeout Summary (출력 양식 고정)
────────────────────────────────

반드시 포함:

Commit:
- [Full SHA] / [Short SHA]

Branch:
- [Branch Name]

Compare Patch URL:
https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/compare/<before_sha>...<after_sha>.patch

Gate Results:
- Doctor (PASS / FAIL)
- Fast (PASS / FAIL)
- Regression (PASS / FAIL)

KPI:
- 돈 버는 구조 핵심 지표
  (net_edge_after_exec, positive_rate 등)

Evidence:
- bootstrap
- main run
- smoke / sweep 경로 전부 명시
