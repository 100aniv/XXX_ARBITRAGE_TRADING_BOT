# READING_CHECKLIST

**Date:** 2026-02-01

## Step 0 Reading (D205-10-1-1 THINWRAP)

- D_ROADMAP.md — 확인: D205-10 브랜치/AC 상태와 문서/증거 요구사항 재확인.
- docs/v2/SSOT_RULES.md — 확인: Gate 3단, DocOps, Report 규칙 재확인.
- docs/v2/design/SSOT_MAP.md — 확인: SSOT 계층 및 Evidence SSOT 위치 재확인.
- docs/v2/design/EVIDENCE_FORMAT.md — 확인: evidence 필수 산출물 및 watch_summary 규칙 재확인.
- docs/v2/V2_ARCHITECTURE.md — 확인: Thin Wrapper/One True Loop 원칙 재확인.

## Step 0 Reading (D207-5)

- D_ROADMAP.md — Confirmed D207/D208 sections and dependencies; D208-0 currently present and requires REBASELOG-based change.
- docs/v2/SSOT_RULES.md — Verified SSOT priority, Gate requirements, and REBASELOG allowance for D-number rebase.
- docs/v2/design/SSOT_MAP.md — Confirmed SSOT layering and D-number immutability rules.
- docs/v2/design/EVIDENCE_FORMAT.md — Confirmed evidence structure and engine_report.json artifact requirements.
- docs/v2/reports/D207/D207-4_CTO_AUDIT_REPORT.md — Reviewed prior audit context and baseline evidence references.

## Step 0 Reading (D207-6)

- D_ROADMAP.md — 확인: D207 섹션 구조와 신규 D207-6 추가 위치 정합성 점검.
- docs/v2/SSOT_RULES.md — 확인: Gate 3단, DocOps, 증거 기준 순서 재확인.
- docs/v2/design/SSOT_MAP.md — 확인: SSOT 계층과 D 번호 불변 규칙 재확인.
- docs/v2/design/EVIDENCE_FORMAT.md — 확인: edge_survey_report.json 증거 포함 규칙 재확인.

## Step 0 Reading (D_ALPHA-0/1)

- D_ROADMAP.md — 확인: D_ALPHA-0/1 AC와 증거 경로, 실행 요구사항 재확인.
- docs/v2/SSOT_RULES.md — 확인: Gate 3단, DocOps, Report 규칙 재확인.
- docs/v2/design/SSOT_MAP.md — 확인: Config SSOT와 Evidence SSOT 위치 매핑 재확인.
- docs/v2/design/EVIDENCE_FORMAT.md — 확인: evidence 산출물 필수 목록 및 gate.log 요구사항 재확인.

## Step 0 Reading (D_ALPHA-2)

- D_ROADMAP.md — 확인: D_ALPHA-2 목표/AC/의존성 및 D_ALPHA-3 종속성 재확인.
- docs/v2/design/SSOT_MAP.md — 확인: SSOT 계층 및 Evidence SSOT 위치 재확인.
- docs/v2/design/EVIDENCE_FORMAT.md — 확인: edge_survey_report.json 및 evidence 필수 산출물 규칙 재확인.

## Step 0 Reading (D_ALPHA-1U)

- D_ROADMAP.md — 확인: D_ALPHA-0/1/2 정의와 D_ALPHA-1U 삽입 위치 정합성 점검.
- docs/v2/SSOT_RULES.md — 확인: D 번호 불변, Gate 3단, DocOps 규칙 준수.
- docs/v2/design/SSOT_MAP.md — 확인: Evidence/Config/Redis/DB SSOT 위치 재확인.
- docs/v2/design/EVIDENCE_FORMAT.md — 확인: evidence 필수 산출물 및 engine_report.json 규칙 재확인.
- docs/v2/design/SSOT_DATA_ARCHITECTURE.md — 확인: DB/Redis 모두 Required 원칙 재확인.
- docs/v2/design/REDIS_KEYSPACE.md — 확인: Redis key prefix/TTL 규칙 재확인.
- docs/v2/V2_ARCHITECTURE.md — 확인: Engine-Centric/Infra Parity 원칙 재확인.
- docs/v2/design/CONFIG_SCHEMA.md — 확인: config 키/Zero-Fallback/Decimal 규칙 재확인.
- docs/v2/design/V2_COMPONENT_REGISTRY.json — 확인: ops_critical/required 컴포넌트 기준 재확인.
- docs/v2/design/SSOT_SYNC_AUDIT.md — 확인: Redis/DB Required 문구 정합성 재확인.
- docs/v2/design/INFRA_REUSE_INVENTORY.md — 확인: V1/V2 재사용 정책 재확인.
- docs/v2/design/CLEANUP_CANDIDATES.md — 확인: 즉시 삭제 금지 원칙 재확인.

## Step 0 Reading (D_ALPHA-1U-FIX)

- D_ROADMAP.md — 확인: D_ALPHA-1U 추가 블록과 D_ALPHA-2 수정 금지 규칙 재확인.
- docs/v2/SSOT_RULES.md — 확인: Gate 3단 강제, DocOps, Report 규칙 재확인.
- docs/v2/design/SSOT_MAP.md — 확인: SSOT 계층 및 Evidence/Config 위치 재확인.
- docs/v2/design/EVIDENCE_FORMAT.md — 확인: engine_report.json 및 evidence 필수 산출물 규칙 재확인.
- docs/v2/V2_ARCHITECTURE.md — 확인: Engine-Centric, Infra Parity 원칙 재확인.
- docs/v2/design/D201-1_BINANCE_MARKET_SEMANTICS.md — 확인: Binance 심볼/마켓 의미론 재확인.

## Step 0 Reading (D_ALPHA-1U-FIX-2)

- D_ROADMAP.md — 확인: D_ALPHA-1U 남은 FIX-2/3 상태와 선기입 필요성 재확인.
- docs/v2/SSOT_RULES.md — 확인: Roadmap-first, Gate 3단, WARN=FAIL 원칙 재확인.
- docs/v2/OPS_PROTOCOL.md — 확인: Invariant(heartbeat≤65s, DB=closed_trades*3±2, Evidence Minimum Set) 재확인.
- docs/v2/design/SSOT_MAP.md — 확인: SSOT 계층/증거 위치/Config 우선순위 재확인.
- docs/v2/design/EVIDENCE_FORMAT.md — 확인: Evidence Minimum Set 및 Atomic Flush 규칙 재확인.
- docs/v2/design/V2_ARCHITECTURE.md — 확인: Engine-Centric + Adapter 계약 재확인.
- docs/v2/design/CONFIG_SCHEMA.md — 확인: Zero-Fallback + Decimal 규칙 재확인.
