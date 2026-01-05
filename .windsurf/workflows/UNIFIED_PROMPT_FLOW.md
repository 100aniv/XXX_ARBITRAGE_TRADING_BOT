---
description: 통합 프롬프트 플로우 (SSOT_RULES 기반, 11 Steps)
---

# 통합 프롬프트 플로우 (UNIFIED_PROMPT_FLOW)

**Version:** 2.0 (SSOT 2-기둥 구조 기반)  
**Effective Date:** 2026-01-05  
**Status:** ENFORCED

---

## 핵심 원칙 (SSOT 2-기둥)

### 기둥 1: D_ROADMAP.md (상태 데이터베이스)
- "우리는 지금 어디에 있고, 목표가 무엇이며, 어떤 AC를 완료했는가?"
- 수정이 극도로 제한된 계약서
- 충돌 시 D_ROADMAP이 모든 다른 문서를 우선함

### 기둥 2: docs/v2/SSOT_RULES.md (운영 헌법 + SOP)
- "작업은 어떤 순서로 하고, 테스트는 무엇을 하며, 문서는 어떻게 검증하는가?"
- 모든 방법론이 집대성된 유일한 법전
- 프롬프트 템플릿 + 테스트 템플릿 + DocOps 검증 포함

---

## 프롬프트 헤더 (필수)

```
[Windsurf PROMPT] Dxxx-y <단계명>

모델: Claude Thinking (3 credits)

범위(Scope):
이번 턴에서 수정 허용 파일/모듈 경계

DONE 정의:
SSOT 기준(로드맵 + 증거 + Gate + 커밋)을 모두 충족한 경우에만 DONE 선언 가능
```

---

## 11단계 통합 작업 플로우

### Step 0: 부트스트랩 (강제, SSOT 문서 정독 포함)

**0-A. 환경 초기화**
- 작업 시작 증거 폴더 생성: `logs/evidence/Dxxx-y_<timestamp>/`
- Git 브랜치 / 워킹트리 고정
- 캐시 / 중복 프로세스 / 런타임 오염 제거
- 인프라 전제 확인 (필요한 단계일 때만)

**0-B. SSOT 문서 강제 정독 (정해진 순서)**
1. `D_ROADMAP.md` (현재 D 단계 목표 + AC + 증거 요구사항)
2. `docs/v2/SSOT_RULES.md` (개발 규칙 + 프롬프트 템플릿)
3. `docs/v2/SSOT_MAP.md` (도메인별 SSOT 위치)
4. `docs/v2/design/**` (해당 단계 관련 설계 문서)
5. 직전 단계 `docs/v2/reports/Dxxx/*` (컨텍스트)

**0-C. 메모리 로드**
- `/LOAD_SSOT_RULES` 명령으로 SSOT_RULES 템플릿 자동 로드
- 프롬프트 템플릿 + 테스트 템플릿 + DocOps 검증 로드

### Step 1: Repo Scan (재사용 목록)

**목표:** 새로 만들지 말고 이미 있는 것을 연결

**산출물:** `SCAN_REUSE_SUMMARY.md`
- 재사용 가능 모듈 3~7개
- 각 모듈별 1줄 이유 (왜 재사용하는가)

### Step 2: Plan (이번 턴 작업 계획)

**목표:** AC를 코드 / 테스트 / 증거로 어떻게 충족할지만 기술

**분량:** 5~12줄
- AC 1~3개 → 코드 구현 방식
- 테스트 전략 (유닛 → Gate)
- 증거 수집 방식 (KPI / 로그 / 메트릭)

### Step 3: Implement (엔진 중심)

**원칙:**
- `arbitrage/v2/**` 알맹이 구현
- `scripts/**` CLI 파라미터 파싱 + 엔진 호출만
- 하위 호환 / 스키마 변경 시 optional 필드로 확장

**Scan-First → Reuse-First 강제:**
- 기존 모듈 확장/리팩토링/얇은 어댑터만 허용
- 새 파일/새 모듈 생성 시 "왜 기존 것을 못 쓰는지" 보고서에 명시

### Step 4: Tests (유닛 → Gate)

**테스트 전략:**
- 변경 범위 유닛 테스트 작성
- Gate 3단 순차 실행 (Doctor → Fast → Regression)
- 하나라도 FAIL 시 즉시 중단 → 수정 → 재실행

**Gate 실행:**
```bash
# Doctor Gate (테스트 수집)
just doctor
# pytest --collect-only 성공

# Fast Gate (핵심 테스트)
just fast
# 핵심 테스트 100% PASS

# Regression Gate (베이스라인)
just regression
# 베이스라인 테스트 100% PASS
```

### Step 5: Smoke / Reality Check

**의미:** "안 죽는다"가 아니라 돈 버는 구조가 수치로 증명되는지

**필수 검증:**
- edge → exec_cost → net_edge 수치 존재
- 0 trades 발생 시 DecisionTrace로 차단 원인 수치화
- Negative Evidence 원칙: 실패 / 이상 수치 발생 시 숨기지 말고 `FAIL_ANALYSIS.md`에 기록

**모든 결과는 evidence로 고정**

### Step 6: Evidence 패키징 (SSOT)

**최소 구성:**
```
logs/evidence/Dxxx-y_<timestamp>/
├── manifest.json      # 실행 메타데이터
├── kpi.json          # KPI 결과
├── gate.log          # Gate 실행 로그
├── git_info.json     # Git 상태 스냅샷
└── cmd_history.txt   # 실행 커맨드 기록
```

**필요 시 추가:**
- `decision_trace.json` (의사결정 추적)
- `latency.json` (레이턴시 분석)
- `leaderboard.json` (성능 순위)
- `best_params.json` (최적 파라미터)
- `watch_summary.json` (장기 실행 시 필수)

**README.md:**
- 재현 명령 3줄

### Step 7: 문서 업데이트 (SSOT 정합성)

**7-A. D_ROADMAP.md 반드시 업데이트**
- 상태 (DONE / IN PROGRESS)
- 커밋 SHA
- Gate 결과
- Evidence 경로
- AC (증거 기반 검증) 항목 전체 업데이트

**7-B. SSOT 문서 동기화 강제 규칙**
- `docs/v2/SSOT_MAP.md`
- `docs/v2/SSOT_DATA_ARCHITECTURE.md`
- `docs/v2/SSOT_SYNC_AUDIT.md`
- `docs/v2/design/**`
- `docs/v2/INFRA_REUSE_INVENTORY.md`
- `docs/v2/CLEANUP_CANDIDATES.md`
- 관련 `docs/v2/reports/Dxxx/*`

### Step 8: Git (강제)

```bash
git status
git diff --stat
git diff
# SSOT 스타일 커밋 메시지
git commit -m "[Dxxx] <단계명> — <핵심 변경 1줄>"
git push
```

### Step 9: Closeout Summary (출력 양식 고정)

**반드시 포함:**
- **Commit**: [Full SHA] / [Short SHA]
- **Branch**: [Branch Name]
- **Compare Patch URL**: https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/compare/<before_sha>...<after_sha>
- **Gate Results**: Doctor (PASS/FAIL) / Fast (PASS/FAIL) / Regression (PASS/FAIL)
- **KPI**: 돈 버는 구조 핵심 지표 (net_edge_after_exec, positive_rate 등)
- **Evidence**: bootstrap / main run / smoke / sweep 경로 전부 명시

### Step 10: 메모리 업데이트 (선택적)

**필요 시:**
- 새로운 패턴 / 설계 결정 메모리 저장
- 다음 작업을 위한 컨텍스트 기록

---

## 전제 / 강제 규칙 (항상 동일, 생략 금지)

### SSOT 원칙
- **SSOT = D_ROADMAP.md 단 1개** (유일한 원천)
- **D번호 의미 불변** (확장은 브랜치 Dxxx-y-z만)
- **기존 목표 / AC / 증거 요구사항 절대 삭제 금지**
- **새 문제 발견 시 "추가(additive)"만 허용** (덮어쓰기 / 축소 / 무효화 금지)

### 개발 원칙
- **돈 버는 아비트라지 로직 / 알고리즘 우선**
- **엔진 중심 구조** (`arbitrage/v2/**`)
- **scan-first → reuse-first**
- **중복 / 반복 금지**

### 검증 원칙
- **Gate 3단 강제** (Doctor / Fast / Regression)
- **증거(Evidence) 없으면 PASS 주장 금지**
- **Wallclock Verification** (장기/대기/모니터링 작업 필수)
  - `watch_summary.json` 자동 생성 필수
  - 필수 필드: started_at_utc, ended_at_utc, monotonic_elapsed_sec, completeness_ratio, stop_reason
  - 시간 기반 완료 선언 금지 (watch_summary.json에서 자동 추출만)
  - 상태 판단: stop_reason 기반 (TIME_REACHED | TRIGGER_HIT | EARLY_INFEASIBLE | ERROR | INTERRUPTED)

### 운영 원칙
- **작업 종료 시 반드시 Git commit (+ push)**
- **필요 시 DB / Redis / 프로세스 / 캐시 정리 강제**
- **실패 시 오염 방지** (Rollback 원칙)

---

## SSOT 보조 문서 체계 (참조용)

- **docs/v2/SSOT_RULES.md**: 개발 규칙 SSOT (프롬프트 템플릿 포함)
- **docs/v2/V2_ARCHITECTURE.md**: V2 아키텍처 설계
- **docs/v2/design/SSOT_MAP.md**: ROADMAP ↔ 설계 ↔ 코드 ↔ 증거 매핑
- **docs/v2/design/EVIDENCE_FORMAT.md**: Evidence 구조 / 필수 항목 SSOT
- **README.md**: 프로젝트 소개 및 SSOT 문서 7종 목록

---

## 메모리 로드 명령

사용자가 다음 작업 시 프롬프트에 포함할 명령:
```
/LOAD_SSOT_RULES
```
→ SSOT_RULES.md의 프롬프트 템플릿 + 테스트 템플릿 + DocOps 검증 자동 로드

---

**상태**: 통합 프롬프트 플로우 (11단계, SSOT 2-기둥 중심)
