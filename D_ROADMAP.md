# D_ROADMAP.md — SSOT Slim Index

**Project:** XXX_ARBITRAGE_TRADING_BOT V2 (Engine-Centric Architecture)
**Version:** 3.0 (Slim Index)
**Date:** 2026-02-20
**Model:** Windsurf Cascade (최상급 Reasoning)

> **이 파일은 유일한 SSOT 엔트리포인트입니다.**
> 상세 레일은 docs/v2/ROADMAP_V2.md, 레거시 전문은 docs/archive/ROADMAP_LEGACY_FULL_20260220.md 참조.

---

## SSOT 선언

| 순위 | 문서 | 역할 |
|---|---|---|
| 1 | docs/v2/SSOT_RULES.md | 헌법 (최상위, 모든 규칙의 근원) |
| 2 | **D_ROADMAP.md (이 파일)** | Process SSOT (목표/상태/포인터) |
| 3 | docs/v2/ROADMAP_V2.md | V2 운영 레일 (D200+ 전용, 상세 AC) |
| 4 | docs/v2/design/AC_LEDGER.md | 공장 큐 (컨트롤러가 읽는 순차 대기열) |
| 5 | docs/v2/V2_ARCHITECTURE.md | 아키텍처 계약 |
| 6 | docs/archive/ROADMAP_LEGACY_FULL_20260220.md | 레거시 동결 보존 (7962줄, 수정 금지) |

---

## 우선순위 정렬 규칙 (강제)

1. **Alpha(TURN5 수익 로직)** = 레일 최상단. 돈 버는 로직이 모든 것에 우선.
2. **Engine Core(D206)** = 수익 파이프라인 직결.
3. **Validation(D207)** = 수익 로직 신뢰성 확보.
4. **Refactoring & Slimming(D208)** = Alpha 완료 직후 강제 배치 (디스크 폭증 방지).
5. **Risk Guards(D209)** = 운영 안전장치.
6. **HFT/Live/Commercial(D210~D215)** = 상용화.
7. **Operations TO-BE(D216~D221)** = 배포/관측/장애 대응/키 관리/비용 상한/RUNBOOK.

---

## 레거시 격리 원칙

- **D200 미만(D82~D106):** 운영 레일에서 완전 제거. docs/archive/ 에 동결 보존.
- **레거시 테스트:** 수정 금지. 게이트 방해 시 docs/archive/legacy_tests/ 로 물리 이동.
- **레거시 코드:** 삭제 금지. legacy_archive/ 로 격리 후 문서화.
- **컨트롤러 필터:** D200 미만 AC_ID는 공장 큐에서 자동 제외 (controller.py _is_v2_alpha_ticket).

---

## 공장 입력(큐) 단일 정의

```
[큐 파일]  docs/v2/design/AC_LEDGER.md
[파서]     ops/factory/controller.py::parse_ledger_rows()
[선택 규칙] ops/factory/controller.py::pick_safe_open_ticket()
           - AC_LEDGER.md의 첫 번째 OPEN 행을 순차 포인팅
           - D200 미만 / 레거시 STAGE는 자동 SKIP (_is_v2_alpha_ticket)
           - D_ALPHA / ALPHA 키워드 포함 시 허용
[출력]     logs/autopilot/plan.json (FactoryPlan 스키마)
[실행]     ops/factory_supervisor.py -> worker (Docker container)
[포인터]   plan.json.ticket_id = "SAFE::{첫 OPEN AC_ID}"
```

---

## 현재 진행 포인터

| 항목 | 값 |
|---|---|
| **현재 위치** | D_ALPHA-1U-FIX-2-1::AC-3 (20m Survey losses >= 1 & winrate < 100%) |
| **다음 3개 AC** | D_ALPHA-1U-FIX-2::AC-3, D_ALPHA-1U-FIX-2::AC-4, D_ALPHA-1U-FIX-2::AC-5 |
| **최근 Gate PASS** | 2026-02-20 logs/evidence/20260220_081159_gate_regression_10a8a54 |
| **브랜치** | feature/v2-factory-hard-reset |
| **공장 상태** | OPERATIONAL (just factory_run PASS) |

---

## Phase 요약 (V2 레일)

### Phase 1: Alpha Engine (수익 로직 최우선)

| Step | Goal | DONE/TOTAL | Status |
|---|---|---|---|
| D_ALPHA-0 | Universe Truth | 4/4 | DONE |
| D_ALPHA-1 | Maker Pivot MVP | 4/4 | DONE |
| D_ALPHA-1U | Universe Unblock & Persistence | 7/7 | DONE |
| D_ALPHA-1U-FIX-2 | Latency Cost Decomposition | 1/5 | PARTIAL |
| D_ALPHA-1U-FIX-2-1 | Winrate 현실화 | 2/5 | PARTIAL |
| D_ALPHA-2 | Dynamic OBI Threshold | 0/1 | OPEN |
| D_ALPHA-3 | Inventory Management | 0/3 | OPEN |
| D_ALPHA-PIPELINE-0 | One-Command Pipeline | 4/6 | PARTIAL |

### Phase 2: Engine Core (수익 파이프라인)

| Step | Goal | DONE/TOTAL | Status |
|---|---|---|---|
| D206-0 | Engine Foundation | 0/6 | OPEN |
| D206-1 | Domain Model Integration | 0/6 | OPEN |
| D206-2 | detect_opportunity() 이식 | 0/6 | OPEN |
| D206-2-1 | Exit Rules & PnL Precision | 0/6 | OPEN |
| D206-3 | Config SSOT | 0/8 | OPEN |
| D206-4 | Order Pipeline | 0/6 | OPEN |
| D206-4-1 | Decimal-Perfect & DB Ledger | 0/6 | OPEN |

### Phase 3: Validation & Stability

| Step | Goal | DONE/TOTAL | Status |
|---|---|---|---|
| D207-1 | REAL Baseline 20분 | 0/7 | OPEN |
| D207-1-2 | Dynamic FX Intelligence | 0/3 | OPEN |
| D207-1-3 | Active Failure Detection | 0/4 | OPEN |
| D207-1-4 | 5x Ledger Rule | 0/3 | OPEN |
| D207-1-5 | Gate Wiring | 0/5 | OPEN |
| D207-2 | LONGRUN 60분 | 0/6 | OPEN |
| D207-3 | Edge Distribution | 0/9 | OPEN |
| D207-4 | Bayesian Tuning | 0/6 | OPEN |
| D207-5 | Run Validation Guards | 0/6 | OPEN |
| D207-5-1 | Edge Distribution Analysis | 0/4 | OPEN |
| D207-6 | Multi-Symbol Survey | 0/6 | OPEN |
| D207-7 | Edge Survey Extended | 0/6 | OPEN |

### Phase 4: Refactoring & Infrastructure Slimming (Alpha 직후 강제)

| Step | Goal | DONE/TOTAL | Status |
|---|---|---|---|
| D208 | Adapter Rename & V1 Purge 계획 | 0/3 | OPEN |
| D208-SLIM-1 | Legacy Code Isolation | 0/4 | OPEN |
| D208-SLIM-2 | Test Cleanup | 0/3 | OPEN |
| D208-SLIM-3 | Disk & Docker Cleanup | 0/3 | OPEN |

### Phase 5: Risk & Operational Guards

| Step | Goal | DONE/TOTAL | Status |
|---|---|---|---|
| D209-1 | Failure Mode Handling | 0/6 | OPEN |
| D209-2 | Risk Guard | 0/6 | OPEN |
| D209-3 | Wallclock & Heartbeat | 0/6 | OPEN |

### Phase 6: HFT & Commercial Readiness

| Step | Goal | Status |
|---|---|---|
| D210-1 | HFT Alpha Model (OBI + A-S) | OPEN |
| D210-2 | LIVE Safety Seal | OPEN |
| D210-3 | LIVE Seal Verification | OPEN |
| D210-4 | Alpha Benchmark | OPEN |
| D211 | Backtesting/Replay Engine | OPEN |
| D212 | Multi-Symbol 동시 실행 | OPEN |
| D213 | HFT Latency Optimization | OPEN |
| D214 | Admin UI/UX Dashboard | OPEN |
| D215 | ML-based Parameter Optimization | OPEN |

### Phase 7: Operations & Production Readiness (TO-BE)

| Step | Goal | Status |
|---|---|---|
| D216 | Deployment & Release Pipeline | OPEN |
| D217 | Observability (로그/메트릭/알림) | OPEN |
| D218 | Incident Response & Rollback | OPEN |
| D219 | Secret & Key Management | OPEN |
| D220 | Cost & Budget Control | OPEN |
| D221 | Operations RUNBOOK Master | OPEN |

### Phase META: Governance

| Step | Goal | Status |
|---|---|---|
| D000-3 | DocOps Token Policy | OPEN |

---

## SSOT 불변 규칙 (축약 - 전문: docs/v2/SSOT_RULES.md)

1. **D_ROADMAP.md 단 1개** (유일한 원천, 분기 금지)
2. **D번호 의미 불변** (확장은 Dxxx-y-z 브랜치만)
3. **AC 삭제 금지** (추가만 허용, 이관 시 MOVED_TO/FROM 표기)
4. **COMPLETED 단계 합치기 금지** (새 D/브랜치만)
5. **Evidence 없으면 DONE 주장 금지** (Gate 3단 + 실행 증거 필수)
6. **Gate 회피 금지** (워딩 꼼수, 파일 삭제, 인간 판정 금지)
7. **레거시 테스트 수정 금지** (이동만 허용)
8. **3점 리더/임시 마커 금지**


---

## conflict_resolution (SSOT 충돌 해결 원칙)

**판정 우선순위 (변경 금지):**
1. `docs/v2/SSOT_RULES.md` — 헌법, 최상위. 모든 충돌 시 SSOT_RULES 채택.
2. `D_ROADMAP.md` — Process SSOT. D번호 의미/상태/AC/증거 경로 정의.
3. `docs/v2/design/SSOT_MAP.md` — 도메인별 SSOT 위치 명시.
4. `docs/v2/V2_ARCHITECTURE.md` — 아키텍처 계약.
5. runtime(config/artifacts) — 실행 증거 + Gate 결과.

**충돌 해결 규칙:**
- 같은 레벨 문서 간 conflict 발생 시: 최신 증거(evidence) + Gate 결과 우선.
- 하위 문서가 상위 SSOT와 다른 정의를 사용하면 하위 문서를 상위에 맞춤.
- 운영 중 긴급 변경은 D_ROADMAP/AC_LEDGER에 반영 후 증거 첨부 필수.
- conflict 발견 시 조치: SSOT_RULES 확인 → D_ROADMAP 동기화 → check_ssot_docs.py ExitCode=0 확인.

---

## D번호 의미 (Immutable Semantics)

| 범위 | 의미 | 상태 |
|---|---|---|
| D82~D106 | V1 레거시 (L2, Fill, Perf, Live 등) | ARCHIVED |
| D200~D204 | V2 Foundation / Adapter / MarketData / Opportunity / Paper | ARCHIVED |
| D205 | User Facing Reporting + 다수 서브스텝 | ARCHIVED |
| D206 | Engine Core (Domain Model, detect, Config, Order) | OPEN |
| D207 | Validation & Stability (Baseline, FX, Failure, Tuning) | OPEN |
| D208 | Refactoring (Adapter Rename, V1 Purge, Slimming) | OPEN |
| D209 | Risk Guards (Failure Mode, Risk Guard, Wallclock) | OPEN |
| D210~D215 | HFT & Commercial Readiness | OPEN |
| D216~D221 | Operations TO-BE (배포/관측/장애/키관리/비용/RUNBOOK) | OPEN |
| D_ALPHA-0~3 | Alpha Engine Track (수익 로직) | PARTIAL/OPEN |
| D_ALPHA-PIPELINE-0 | One-Command Pipeline | PARTIAL |
| D000-3 | META/Governance (DocOps Token Policy) | OPEN |

---

## Status Truth Sync (코드 기반 상태 판정)

기존 로드맵의 COMPLETED 표시를 맹신하지 않습니다.
AC_LEDGER.md의 DONE 판정은 다음 조건을 모두 만족해야 합니다:

1. **logs/evidence/** 에 해당 AC의 물리적 증거 디렉토리 존재
2. **tests/** 에 해당 AC의 테스트가 존재하고 PASS
3. **Gate 3단 PASS** (Doctor/Fast/Regression) 증거
4. **check_ssot_docs.py ExitCode=0**

조건 미충족 시 자동으로 OPEN 또는 LOST_EVIDENCE로 하향 조정됩니다.

---

## Operator UX (결정론적 공장 제어)

| 명령 | 설명 | 구현 |
|---|---|---|
| `just factory_status` | 진행률/포인터/최근 PASS-FAIL/evidence 경로 | scripts/factory_status.py |
| `just factory_next` | 다음 AC 1개만 실행 (1 cycle) | supervisor --max-cycles 1 |
| `just factory_run` | 큐 반복 실행 (예산/가드 기준) | supervisor + Disk Guard |
| `just factory_stop` | worker 컨테이너 즉시 종료 (안전) | scripts/factory_stop.py |
| `just factory_tail` | 최신 factory 로그 + gate.log tail | bash tail |
| `just factory_dry` | DRY-RUN (PLAN/DO/CHECK 미리보기) | supervisor --dry-run |

**안전 장치:**
- **Disk Guard:** 디스크 여유 5GB 미만 시 Fail-Fast (controller.py check_disk_guard)
- **Budget Guard:** API 비용 $5/cycle 초과 시 supervisor 즉시 종료
- **Sequential Integrity:** AC_LEDGER 위에서 아래로 순차 진행 보장 (verify_sequential_integrity)
- **진행률 계산:** AC_LEDGER DONE/TOTAL 비율 (LLM 호출 없이 결정론적)

---

## 참조 링크

| 문서 | 경로 |
|---|---|
| V2 운영 레일 (상세) | [docs/v2/ROADMAP_V2.md](docs/v2/ROADMAP_V2.md) |
| 공장 큐 (AC_LEDGER) | [docs/v2/design/AC_LEDGER.md](docs/v2/design/AC_LEDGER.md) |
| SSOT 헌법 | [docs/v2/SSOT_RULES.md](docs/v2/SSOT_RULES.md) |
| V2 아키텍처 | [docs/v2/V2_ARCHITECTURE.md](docs/v2/V2_ARCHITECTURE.md) |
| 레거시 전문 (동결) | [docs/archive/ROADMAP_LEGACY_FULL_20260220.md](docs/archive/ROADMAP_LEGACY_FULL_20260220.md) |
| SSOT 맵 | [docs/v2/design/SSOT_MAP.md](docs/v2/design/SSOT_MAP.md) |
| 증거 포맷 | [docs/v2/design/EVIDENCE_FORMAT.md](docs/v2/design/EVIDENCE_FORMAT.md) |
| 네이밍 정책 | [docs/v2/design/NAMING_POLICY.md](docs/v2/design/NAMING_POLICY.md) |

---

## Git 상태

| 항목 | 값 |
|---|---|
| 브랜치 | feature/v2-factory-hard-reset |
| 최근 커밋 | 10a8a54 (factory/v2_alpha_gate) |
| 최근 Gate PASS | 2026-02-20 08:11:59 UTC |
| Push 상태 | OK (To github.com:100aniv/XXX_ARBITRAGE_TRADING_BOT.git) |

---

## REBASELOG

| 날짜 | 사유 | 커밋 |
|---|---|---|
| 2026-02-20 | Slim Index 재구성. 레거시 7962줄 -> archive 이관. V2-only 레일 신규 생성. | 7d5243f |
| 2026-02-20 | Operator UX 추가 (factory_status/stop/next/tail). Phase 7 TO-BE 운영 단계 추가. Disk Guard/Sequential Integrity 구현. | (이번 커밋) |
