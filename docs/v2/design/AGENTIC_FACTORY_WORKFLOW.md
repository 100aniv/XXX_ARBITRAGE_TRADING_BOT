# Agentic Factory Workflow (SSOT)

**Version:** 1.0
**Effective Date:** 2026-02-18
**Status:** ENFORCED

---

## 1. 목적 / 철학

### 왜 "공장형(Agentic)" 워크플로우인가

수동 프롬프트 → 수동 검증 → 수동 커밋 루프는 **사람이 병목**이다.
공장형 워크플로우는 이 루프를 자동화하되, **SSOT 헌법을 깨지 않는 범위에서만** 자율 실행한다.

### 3대 SSOT 기둥

| 기둥 | 파일 | 역할 |
|---|---|---|
| **헌법** | `docs/v2/SSOT_RULES.md` | 개발/운영/검증 규칙의 유일한 법전 |
| **로드맵** | `D_ROADMAP.md` | 상태/목표/AC의 유일한 원천 (상태 DB) |
| **큐** | `docs/v2/design/AC_LEDGER.md` | AC 단위 작업 큐 (OPEN/DONE 추적) |

**불변 원칙:**
- SSOT_RULES 위반 = 즉시 FAIL + Revert
- D_ROADMAP 외 상태 저장소 = 금지
- AC 삭제 = 금지 (추가만 허용)

---

## 2. 4-Layer 격리 구조

```
┌─────────────────────────────────────────────────┐
│  Layer 4: Auditor (판정 전용, 코드 수정 금지)     │
│  GPT-5.2-Reasoning / Claude Opus               │
├─────────────────────────────────────────────────┤
│  Layer 3: Controller (Windsurf / 로컬 IDE)       │
│  티켓 선택 → plan.json → Worker 호출 → 증거 수집 │
├─────────────────────────────────────────────────┤
│  Layer 2: Worker (Docker 컨테이너 / CLI)         │
│  Claude Code CLI / Aider → 구현 + 테스트 실행    │
├─────────────────────────────────────────────────┤
│  Layer 1: Engine (arbitrage/v2/**)               │
│  핵심 수익 로직 (수정 권한: Worker만, Gate 통과 후)│
└─────────────────────────────────────────────────┘
```

### 왜 격리하는가

- **Layer 1 (Engine):** 돈 버는 코어. 무분별한 수정 = 수익 파괴. Gate 통과 없이 변경 금지.
- **Layer 2 (Worker):** 격리된 컨테이너에서 실행. 호스트 파일시스템/네트워크 직접 접근 차단. 실패해도 호스트 오염 없음.
- **Layer 3 (Controller):** 전체 오케스트레이션. 어떤 티켓을 누구에게 줄지 결정. 증거 수집/검증 책임.
- **Layer 4 (Auditor):** 코드를 읽기만 함. "이 변경이 SSOT를 위반하는가?" 판정만 수행. 수정 권한 없음.

### 격리 경계 규칙

| 경계 | 허용 | 금지 |
|---|---|---|
| Worker → Engine | PR/패치 제출 (Gate 통과 후 merge) | 직접 push to main |
| Worker → Host FS | 마운트된 작업 디렉토리만 | 호스트 시스템 파일 |
| Controller → Worker | plan.json 전달 + result.json 수신 | Worker 내부 로직 직접 조작 |
| Auditor → 전체 | 읽기 전용 접근 | 코드/문서/설정 수정 |

---

## 3. 역할 분리

### 3-1. Controller (결정자)

**담당:** Windsurf (Claude Sonnet 4 Thinking)

**책임:**
- D_ROADMAP에서 IN_PROGRESS 티켓 선택
- AC_LEDGER에서 OPEN AC 우선순위 결정
- Worker에게 plan.json 전달
- Worker result.json 수신 → 증거 검증
- Gate 실행 (just gate / just docops)
- SSOT 문서 업데이트 (D_ROADMAP, AC_LEDGER)
- Git commit + push

**금지:**
- 직접 코드 구현 (Worker 역할 침범)
- Gate 스킵 또는 우회
- 증거 없이 DONE 선언

### 3-2. Worker (실행자)

**담당:** Claude Code CLI (기본) / Aider (보조)

**실행 환경:** Docker 컨테이너 (WSL2 기반)

**책임:**
- plan.json 수신 → 코드 구현
- 유닛 테스트 작성 + 실행
- result.json + evidence 디렉토리 생성
- Gate 3단 로컬 실행 (Doctor/Fast/Regression)

**금지:**
- D_ROADMAP / SSOT_RULES 수정
- 스코프 밖 파일 변경
- Gate FAIL 상태에서 result.json에 "PASS" 기록

**Worker 컨테이너 제약:**
```yaml
# docker-compose.factory.yml (향후 구현)
services:
  worker:
    volumes:
      - ./arbitrage:/workspace/arbitrage
      - ./tests:/workspace/tests
      - ./scripts:/workspace/scripts:ro
      - ./logs/evidence:/workspace/logs/evidence
    network_mode: "none"  # 네트워크 격리 (기본)
    # NET-READ 필요시: network_mode: "bridge" + 읽기전용 프록시
```

### 3-3. Auditor (감사자)

**담당:** GPT-5.2-Reasoning / Claude Opus (고비용, 필요시만)

**책임:**
- Worker 산출물 코드 리뷰 (SSOT 위반 탐지)
- Gate 결과 교차 검증
- "이 변경이 수익 로직을 훼손하는가?" 판정
- 판정 결과를 audit_report.json으로 기록

**금지:**
- 코드/문서/설정 수정 (읽기 전용)
- Gate 실행 (Controller 역할)
- 티켓 선택/우선순위 변경 (Controller 역할)

**Auditor 호출 조건 (비용 절감):**
- 일반 티켓: Auditor 생략 (Controller가 Gate로 충분)
- 고위험 티켓: Engine 코어 수정, PnL 계산 변경, 새 도메인 모듈 추가
- Escalation: Worker가 2회 연속 Gate FAIL

---

## 4. PDCA 루프 + 산출물 규칙

### 4-1. PDCA 사이클

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  PLAN    │ ──→ │   DO     │ ──→ │  CHECK   │ ──→ │  ADJUST  │
│Controller│     │  Worker  │     │Controller│     │Controller│
│plan.json │     │result.json│    │Gate+Audit│     │ 문서갱신  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
      ↑                                                  │
      └──────────────── 다음 티켓 ←──────────────────────┘
```

### 4-2. 산출물 규칙

#### plan.json (Controller → Worker)

```json
{
  "ticket_id": "D_ALPHA-PIPELINE-0",
  "ac_ids": ["AC-1-1", "AC-1-2"],
  "scope": {
    "modify": ["arbitrage/v2/core/orchestrator.py", "tests/test_orchestrator.py"],
    "readonly": ["arbitrage/v2/domain/pnl_calculator.py"],
    "forbidden": ["D_ROADMAP.md", "docs/v2/SSOT_RULES.md"]
  },
  "done_criteria": "Gate 3단 PASS + kpi.json 존재 + net_pnl_full > 0",
  "timeout_minutes": 30,
  "model_budget": "standard"
}
```

#### result.json (Worker → Controller)

```json
{
  "ticket_id": "D_ALPHA-PIPELINE-0",
  "status": "PASS",
  "gate_results": {
    "doctor": "PASS",
    "fast": "PASS",
    "regression": "PASS"
  },
  "evidence_path": "logs/evidence/d_alpha_pipeline0_20260218_2100/",
  "files_changed": ["arbitrage/v2/core/orchestrator.py"],
  "kpi_summary": {
    "net_pnl_full": 15.32,
    "closed_trades": 245,
    "partial_fill_penalty": 0.0
  },
  "duration_seconds": 847,
  "model_used": "claude-code-cli",
  "cost_estimate_usd": 0.12
}
```

#### evidence 디렉토리 (SSOT)

```
logs/evidence/<run_id>/
├── manifest.json      # 필수: 실행 메타데이터
├── kpi.json           # 필수: 핵심 성과 지표
├── gate.log           # 필수: Gate 실행 로그
├── git_info.json      # 필수: 커밋/브랜치 정보
├── cmd_history.txt    # 필수: 실행 명령 기록
├── pnl_breakdown.json # 수익 관련 티켓 시 필수
└── README.md          # 재현 명령 3줄
```

---

## 5. Guard / Fail-Fast 정책

### 5-1. Guard 목록

| Guard | 스크립트 | 역할 | FAIL 시 |
|---|---|---|---|
| **Welding** | `scripts/check_no_duplicate_pnl.py` | PnL/friction 계산 단일화 강제 | ExitCode=1, Gate 즉시 중단 |
| **Engine-Centric** | `scripts/check_engine_centricity.py` | scripts/harness 얇은막 강제 | ExitCode=1, Gate 즉시 중단 |
| **DocOps Token** | `scripts/check_docops_tokens.py` | 금칙어 탐지 (strict/allowlist) | ExitCode=1, 커밋 금지 |
| **SSOT Docs** | `scripts/check_ssot_docs.py` | SSOT 문서 정합성 | ExitCode=1, 커밋 금지 |

### 5-2. Gate 실행 흐름

```
just gate
  → just doctor
      → run_gate_with_evidence.py doctor
          → Preflight: check_no_duplicate_pnl.py (FAIL → 즉시 중단)
          → Preflight: check_engine_centricity.py (FAIL → 즉시 중단)
          → pytest --collect-only (구문/임포트 검증)
  → just fast
      → (동일 Preflight) → pytest -m "not optional_ml..." -x
  → just regression
      → (동일 Preflight) → pytest -m "not optional_ml..."
```

### 5-3. Fail-Fast 원칙

- **Preflight FAIL → Gate 전체 FAIL** (후속 테스트 실행하지 않음)
- **Gate FAIL → Worker 결과 거부** (result.json status를 "FAIL"로 강제)
- **2회 연속 FAIL → Escalation** (Auditor 호출 또는 사람 개입)
- **증거:** `docs/v2/reports/D000/D000-3-2_REPORT.md`에 재현 기록

### 5-4. Kill Switch (안전 장치)

- **Budget Cap:** 1회 PDCA 사이클 비용 상한 (기본: $1.00)
- **Time Cap:** Worker 실행 시간 상한 (기본: 30분)
- **Retry Cap:** 동일 티켓 최대 재시도 횟수 (기본: 3회)
- **초과 시:** Controller가 티켓을 "BLOCKED"로 마킹, 사람 에스컬레이션

---

## 6. 모델/도구 조합 표

### 6-1. 역할별 권장 모델

| 역할 | 기본 모델 | 대체 모델 | 비용 배수 | 용도 |
|---|---|---|---|---|
| **Controller** | Claude Sonnet 4 (Thinking) | - | 3x | 문서/정리/오케스트레이션 |
| **Worker (구현)** | Claude Code CLI | Aider (보조) | 1x | 코드 구현 + 테스트 |
| **Worker (소수술)** | Codex (High) | - | 1x | 단일 파일 버그픽스 |
| **Auditor** | GPT-5.2-Reasoning | Claude Opus 4.5 | 5~8x | 고위험 판정 |
| **Windsurf 소작업** | Codex (Free) | - | 0x | 단순 편집/포맷 |

### 6-2. 비용 기준 (1x = Codex High 기준)

| 모델 | 배수 | 월 예산 가이드 |
|---|---|---|
| Codex High | 1x | 무제한 (기본) |
| Claude Sonnet 4 Thinking | 3x | Controller 전용 |
| Claude Opus 4.5 Thinking | 5x | Auditor 전용 |
| GPT-5.2 Reasoning | 8x | Escalation 전용 |

---

## 7. 비용 원칙

### 7-1. 비용 Gate (언제 비싼 모델을 쓰는가)

```
티켓 난이도 판정:
  LOW  (문서/포맷/단순 버그)  → Codex Free/High
  MED  (기능 구현/테스트)     → Claude Code CLI
  HIGH (Engine 코어 수정)     → Claude Code CLI + Auditor 리뷰
  CRIT (PnL 계산/수익 로직)   → Claude Code CLI + Opus/GPT-5.2 Auditor
```

### 7-2. 비용 절감 규칙

1. **기본은 싸게:** Worker = Claude Code CLI (1x), Controller = Sonnet (3x)
2. **Auditor는 조건부:** 고위험 티켓 또는 2회 연속 FAIL 시에만 호출
3. **Opus/GPT-5.2는 최후 수단:** 일반 티켓에 사용 금지
4. **배치 최적화:** 동일 스코프 티켓은 묶어서 1회 Worker 호출
5. **캐시 활용:** 동일 Gate 결과는 재실행하지 않음 (evidence 해시 기반)

### 7-3. 비용 추적

- 각 result.json에 `cost_estimate_usd` 필드 필수
- 월간 집계: `logs/autopilot/cost_summary_YYYYMM.json` (향후 자동 생성)

---

## 8. 시작하기 (최소 명령 세트)

### 8-1. 현재 사용 가능한 명령

```bash
# Gate 3단 (Doctor → Fast → Regression)
just gate

# DocOps 검증 (SSOT check + 금칙어 스캔)
just docops

# Evidence 최소 세트 확인
just evidence_check

# 개별 Gate 실행
just doctor
just fast
just regression

# 개별 Guard 실행
.\abt_bot_env\Scripts\python.exe scripts\check_no_duplicate_pnl.py
.\abt_bot_env\Scripts\python.exe scripts\check_engine_centricity.py
.\abt_bot_env\Scripts\python.exe scripts\check_docops_tokens.py --config config\docops_token_allowlist.yml
```

### 8-2. 향후 추가 예정 명령 (FACTORY 가동 시)

```bash
# Factory Dry Run (1개 티켓 시뮬레이션, 실제 변경 없음)
just factory_dry

# Factory Run (자동 PDCA 1사이클)
just factory_run

# Factory Status (현재 큐/진행 상황)
just factory_status

# Auditor 호출 (수동)
just factory_audit <ticket_id>
```

### 8-3. 최소 시작 절차

```
1. git status → clean 확인
2. just gate → 3단 PASS 확인
3. just docops → SSOT 정합성 확인
4. D_ROADMAP.md → IN_PROGRESS 티켓 확인
5. AC_LEDGER.md → OPEN AC 우선순위 확인
6. plan.json 작성 → Worker 호출
7. result.json 수신 → Gate 재실행 → 증거 검증
8. SSOT 문서 갱신 → git commit + push
```

---

## 9. 참조 문서

| 문서 | 경로 | 역할 |
|---|---|---|
| SSOT 헌법 | `docs/v2/SSOT_RULES.md` | 모든 규칙의 원천 |
| 로드맵 | `D_ROADMAP.md` | 상태/목표/AC DB |
| AC 큐 | `docs/v2/design/AC_LEDGER.md` | 작업 큐 |
| Profit Logic | `docs/v2/design/PROFIT_LOGIC_STATUS.md` | 수익 로직 판정 |
| Guard Evidence | `docs/v2/reports/D000/D000-3-2_REPORT.md` | Guard 동작 증명 |
| PREP Closeout | `docs/v2/reports/D000/D000-3-1_REPORT.md` | PREP 완료 증거 |
| Evidence Format | `docs/v2/design/EVIDENCE_FORMAT.md` | 증거 구조 SSOT |
| Architecture | `docs/v2/V2_ARCHITECTURE.md` | Engine-Centric 설계 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|---|---|---|
| 2026-02-18 | 1.0 | 초판 생성 (PREP_DONE → FACTORY_SETTING 전환) |
