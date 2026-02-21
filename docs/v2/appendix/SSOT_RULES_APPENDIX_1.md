# SSOT Rules Appendix 1 — Design Docs / Completed Rules / Governance

**출처:** docs/v2/SSOT_RULES.md (원본 동결: docs/v2/archive/SSOT_RULES_FULL_20260221.md)
**포함 섹션:** F, G, H, I, J, K, L, M, N (상세 케이스 / 운영 프로토콜 / Taxonomy)
**Core 문서:** docs/v2/SSOT_RULES.md

---

## Section F: Design Docs 참조 규칙 (디폴트)

**목적:** docs/v2/design 정독을 "옵션"이 아니라 "디폴트"로 강제

**규칙:**
- 모든 D-step은 `docs/v2/design/`를 **반드시** 열어 읽고, 이번 D에 관련된 문서 **최소 2개** 요약
- 어떤 문서가 관련인지 모르면 "목차/파일명 기반 탐색 후 선택" 규칙

**Reading Tax (읽었다는 흔적 필수):**
- `READING_CHECKLIST.md`에 읽은 문서 목록 + 1줄 요약 기록
- "이번 작업에서 무엇을 재사용하고 무엇을 가져올지" 10줄 이내 요약

**Design 문서 종류 (예시):**
- `SSOT_MAP.md` - SSOT 계층 구조
- `SSOT_DATA_ARCHITECTURE.md` - Cold/Hot Path
- `SSOT_SYNC_AUDIT.md` - 정합성 감사
- `EVIDENCE_FORMAT.md` - Evidence 구조
- `NAMING_POLICY.md` - 파일/단계/지표/키 네이밍
- `REDIS_KEYSPACE.md` - Redis 키 구조
- 기타 도메인별 설계 문서

**위반 시 조치:**
- Design 문서 정독 누락 → FAIL, READING_CHECKLIST 작성 후 재실행
- "관련 없음" 주장 → FAIL, 최소 2개 선택 후 "관련 없는 이유" 명시

---

## Section G: COMPLETED 단계 합치기 금지 (강제)

**원칙:** COMPLETED 단계에 신규 작업 추가 방지

**규칙:**
- COMPLETED 단계에 뭔가 추가하고 싶으면 무조건 **새 D/새 브랜치** 생성
- "단계 합치기"는 SSOT 리스크(삭제/누락/축약) 때문에 **절대 금지**

**예시:**
- ❌ **금지:** D205-11-2 COMPLETED에 "추가 계측" 작업 합치기
- ✅ **허용:** D205-11-3 신규 브랜치 생성 (추가 계측)

**위반 시 조치:**
- COMPLETED 단계 합치기 발견 → 즉시 FAIL, 새 D/새 브랜치로 분리

---

## Section H: 3점 리더 / 임시 마커 금지 (강제)

**원칙:** 축약 흔적 제거 (SSOT 파손 방지)

**금지 대상:**
- `...` (3점 리더, ellipsis 문자)
- `…` (ellipsis 유니코드 문자 U+2026)
- 임시 작업 마커 (T*DO, T*D, FIX*E, X*X, H*CK 형태)
- `pending`, `later`, `작업중`, `보류중` (COMPLETED 문서에서)
- **참고:** 일반 마침표 `.`는 금지 대상이 아님 (문장 종결은 정상)

**규칙:**
- 로드맵/리포트/규칙 어디에도 위 금지 대상을 남기면 FAIL
- COMPLETED 문서에 임시 마커 **절대 금지**

---

## Section I: check_ssot_docs.py ExitCode=0 강제 (SSOT DocOps Gate)

**원칙:** "스코프 내 PASS" 같은 인간 판정 금지, 물리적 증거만 인정

**규칙:**
1. **ExitCode=0만 PASS:**
   - `check_ssot_docs.py` 실행 결과는 ExitCode=0일 때만 PASS
   - ExitCode=1이면 **무조건 FAIL** (이유 불문)

2. **스코프 필터 (선택):**
   - 스코프가 필요하면 스크립트가 공식적으로 `--scope` 옵션 제공해야 함
   - 가능하면 전체 문서 정리로 ExitCode=0 우선 (스코프 옵션은 최후 수단)

3. **메인 브랜치 병합 전 타협 금지:**
   - 메인 브랜치 병합 전 모든 DocOps 실패는 **예외 없이 수정**되어야 함

**증거 요구사항:**
- `ssot_docs_check_exitcode.txt` 파일 필수 (내용: `0`)
- `ssot_docs_check_raw.txt` 또는 `ssot_docs_check_final.txt` 필수 (전체 출력)

---

## Section J: Gate 회피 금지 (강제)

**원칙:** 규칙을 통과하기 위한 편법/꼼수는 SSOT를 더 빨리 망가뜨림

**금지 행위:**
1. **워딩 꼼수로 탐지 회피:** 금칙어 변형, 정규식 패턴 우회
2. **파일 삭제로 규칙 회피:** 규칙 위반 파일 삭제, Report/증거 지워서 추적성 제거
3. **ExitCode=0 아닌 상태에서 DONE 선언:** ExitCode=1인데 "스코프 내 PASS"로 우기기

**위반 시 조치:**
- Gate 회피 발견 → 즉시 FAIL + 작업 Revert
- 데이터 조작 → 프로젝트 중단 (CTO 경고)

---

## Section K: D000 META/Governance 번호 체계 (강제)

**원칙:** D000은 META/Governance 전용, 실제 기능 개발과 혼재 금지

**D000 정의:**
- **용도:** 규칙/DocOps/레일 정비 전용 (SSOT Infrastructure)
- **금지:** 실거래/엔진/알고리즘 개발

**네이밍 규칙:**
1. D000 제목에 [META] 태그 강제: `D000-1: [META] SSOT Rules Unify`
2. D_ROADMAP에서 META RAIL 섹션 격리
3. 브랜치명: `rescue/d000_1_meta_ssot_rules`

**AC 요구사항:**
- D000-x 작업은 check_ssot_docs.py ExitCode=0 필수
- D000-x Report는 "왜 META 작업이 필요했는지" 명시 필수

---

## Section L: API 및 버전 명칭 규칙 (강제)

**원칙:** 시즌 버전(V1/V2)과 외부 API 버전(v1/v3)의 혼동 방지

**규칙:**
- ✅ **허용:** `MarketType.SPOT`, `MarketType.FUTURES`
- ✅ **허용:** `BINANCE_SPOT_BASE_URL`, `BINANCE_FUTURES_BASE_URL`
- ✅ **허용:** URL 내부의 `/api/v3`, `/fapi/v1`은 구현 디테일로만 취급
- ❌ **금지:** 코드/설정/문서에서 "v1 API", "v3 API" 표현
- ❌ **금지:** `API_V1`, `API_V3`, `R1`, `R3` 같은 변수/상수명

**검증:**
```bash
rg "v1 API|v3 API|API_V1|API_V3|R1|R3" --type py --type md --type yaml
```

---

## Section M: Paper Acceptance REAL 강제 규칙 + Taxonomy 표준화

### Paper Acceptance (D205-18-4)
- Paper mode 실행 시 REAL 시장 데이터 강제, Mock 데이터 금지
- Winrate 정상 범위: 50~80% (95%+ WARNING, 100% FAIL)
- DB Strict Mode 필수 (`--db-mode strict`)
- Baseline (20m) + Longrun (60m) 필수

### Taxonomy 정의 (D206 Ops Protocol)
- **RunMode:** BACKTEST | PAPER | LIVE (실행 환경)
- **RunProfile:** SMOKE | BASELINE | LONGRUN | ACCEPTANCE | EXTENDED (실행 프로파일)
- **ValidationRigor:** QUICK | SSOT (검증 강도)
- **금지:** "mode"와 "profile" 혼용, "phase"를 "mode"로 혼용

### Evidence 패키징 필수
- `chain_summary.json`, `daily_report_YYYY-MM-DD.json`, `README.md`

---

## Section N: Artifact-First Gate & No Partial (D206-1 HARDENED)

### N-1: Artifact-First Gate
- Gate는 Runner가 아닌 Core 산출물(manifest.json, kpi_summary.json)을 검증
- Runner property 직접 검사 금지

### N-2: No Partial Completion
- DONE 조건: DocOps ExitCode=0 AND Registry ExitCode=0 AND pytest ExitCode=0 AND SKIP=0
- "PARTIAL", "부분 완료", "pending", "later" 표현 금지

### N-3: WARN=FAIL / SKIP=FAIL
- Registry/Preflight에서 warning > 0 → sys.exit(1)
- pytest에서 SKIP > 0 → FAIL

### Operational Hardening Core Principles
- **Wallclock Duration:** 모든 duration_seconds는 wall-clock 기준
- **Heartbeat Density:** heartbeat.jsonl 60초 간격, 65초 초과 FAIL
- **Evidence Completeness:** chain_summary/heartbeat/kpi/manifest 전부 필수
- **WARN=FAIL:** 모든 WARNING은 Exit Code 1
- **Atomic Evidence Flush:** finally 블록에서 무조건 Evidence 저장

---

## Section O: Operation Thresholds (Value Watch)

**목적:** Factory 사이클의 에이전트/모델 선택 기준을 비용 관점에서 명문화.

| Tier | 조건 | 권장 에이전트 | 권장 모델 |
|------|------|---------------|-----------|
| **CHEAP** | est_cost_usd < 0.05 | aider (OpenAI low) | gpt-4.1-mini |
| **MEDIUM** | 0.05 <= est_cost_usd < 0.50 | aider (OpenAI mid) | gpt-4.1 |
| **HEAVY** | est_cost_usd >= 0.50 OR context_risk == "danger" | claude_code (Anthropic) | claude-sonnet-4-20250514 |

**규칙:**
- context_risk가 "danger"이면 est_cost_usd와 무관하게 HEAVY로 분류
- HEAVY 분류 시 worker.py의 Context Budget Guard가 route_to_claude=True를 반환하며, 실제 claude_code로 강제 전환됨
- VALUE_WATCH 출력은 이 임계값 기준으로 현재 상태를 표시
- MAX_BUDGET_PER_SESSION = $5.00 USD (초과 시 경고)

---

*상세 원문: docs/v2/archive/SSOT_RULES_FULL_20260221.md*
