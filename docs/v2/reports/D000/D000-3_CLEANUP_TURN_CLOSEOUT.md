# D000-3 Cleanup Turn Closeout

## 목적
DocOps Cleanup Finalization - 4개 핵심 산출물 완결 + Guard fail-fast 증명

## 산출물 체크리스트

### 1. AC_LEDGER ✅
**경로:** `docs/v2/design/AC_LEDGER.md`

**생성 스크립트:** `logs/autopilot/_rebase_ac_ledger.py`
- D_ROADMAP.md 스캔 → AC 추출 → Evidence 매핑 → Duplicate 탐지 → 상태 판정

**핵심 지표:**
- Total ACs: 377
- DONE (Gate3 + Artifacts): 6
- OPEN: 371
- Merged (Duplicate): 24

**Duplicate 그룹 예시:**
- D_ALPHA-1U::AC-1-2 (DONE, canonical) ← AC-2-2, AC-3-2, AC-4-2, AC-5-2 병합
- Evidence 기반 중복 제거: `EVID:logs/evidence/d_alpha_1u_survey_off_20260131_233706/`

### 2. roadmap_rebase_report ✅
**경로:** `logs/autopilot/roadmap_rebase_report.json`

**주요 섹션:**
- `done_marked`: DONE이지만 ROADMAP에 체크 누락된 항목 (0건)
- `merged`: 중복으로 병합된 AC 목록 (24건)
- `closeout_candidates`: 정리 권장 대상 (24건)
- `still_open_top`: 미완료 AC 상위 20개
- `suspicious`: 체크됐지만 증거 없는 AC (20건)

**Change Summary:**
```json
{
  "dup_group_count": 10,
  "merged_count": 24,
  "done_count": 6,
  "open_count": 371
}
```

### 3. PROFIT_LOGIC_STATUS ✅
**경로:** `docs/v2/design/PROFIT_LOGIC_STATUS.md`

**판정 기준 (3개):**
1. **partial_fill_penalty 로직:** ✅ 검증
   - 코드: `arbitrage/v2/domain/pnl_calculator.py`
   - 증거: `logs/evidence/20260215_dalpha3_pnl_weld_tail_20m/pnl_breakdown.json` (penalty=0.0, 정상)
   
2. **friction breakdown:** ✅ 검증
   - 5개 마찰 비용 항목 완전 분해 (fee/slippage/latency/spread/partial)
   - 증거: 모든 profitability matrix run의 `pnl_breakdown.json`

3. **복수 시드/유니버스:** ✅ 검증
   - D206-1: 10회 실행 (top20/top50 x 5 seeds, failed_runs=false)
   - D207-6 TURN5: net_pnl_full=22.15 > 0 (338 trades)

**판정 결과:** **Profit Logic = PASS** (2026-02-18)

### 4. Guard Fail-Fast Evidence ✅
**경로:** `docs/v2/reports/D000/D000-3_GUARD_FAILFAST_EVIDENCE.md`

**테스트 시나리오:**
1. **Welding Guard (check_no_duplicate_pnl.py)**
   - 고의 위반: `logs/autopilot/_test_guard_violation.py` (duplicate calculate_net_pnl_full)
   - 결과: ExitCode=1, FAIL 탐지
   - 원복 후: ExitCode=0, PASS

2. **Gate 강제 실행 확인**
   - `scripts/run_gate_with_evidence.py`의 `preflight_checks`
   - Preflight FAIL → Gate FAIL (즉시 중단)
   - Preflight PASS → Gate 계속 진행

3. **Engine-Centric Guard (check_engine_centricity.py)**
   - `scripts/`, `arbitrage/v2/harness/` 얇은막 강제
   - 클래스/루프/비즈니스 로직 금지
   - 역방향 import 금지

## Just Gate 가드 통합 확인

### justfile 구조
```
gate:
    @just doctor
    @just fast
    @just regression
```

### Gate 실행 플로우
```
just gate
  → doctor (run_gate_with_evidence.py doctor)
      → Preflight: check_no_duplicate_pnl.py (ExitCode 체크)
      → Preflight: check_engine_centricity.py (ExitCode 체크)
      → pytest --collect-only (Gate Doctor)
  → fast (run_gate_with_evidence.py fast)
      → Preflight 2종 (동일)
      → pytest -m "not optional_ml..." -x (Gate Fast)
  → regression (run_gate_with_evidence.py regression)
      → Preflight 2종 (동일)
      → pytest -m "not optional_ml..." (Gate Regression)
```

**강제 규칙:**
- Preflight FAIL → Gate FAIL (ExitCode=1, 즉시 중단)
- Preflight PASS → Gate 계속 진행
- Evidence 자동 생성: `logs/evidence/gate_<name>_<timestamp>_<hash>/`

## TURN5 티켓 처리 (Future Work)

**현재 상태:**
- TURN5는 historical experiment/rerun tag로만 유지 (D207-1, D207-6)
- D_ALPHA/D206/D207 티켓은 AC_LEDGER에서 OPEN 상태로 추적 중

**압축 대상 (Next D-step):**
- D_ALPHA-PIPELINE-0 (Canonical entrypoint + Gate 3단 + 20m Survey)
- D_ALPHA-2 (OBI + Dynamic Threshold)
- D_ALPHA-3 (Inventory Penalty + Quote Skew)

**나머지 티켓:**
- Factory rail로 이관 (D_ROADMAP "## Factory Rail (Backlog)" 섹션 추가 권장)

## 완료 조건 충족

### 4개 산출물 완결 ✅
1. AC_LEDGER: 377 ACs, 6 DONE, 24 merged
2. roadmap_rebase_report: JSON 구조화, suspicious/closeout 분류
3. PROFIT_LOGIC_STATUS: Profit Logic = PASS 판정
4. Guard fail-fast evidence: Welding/Engine-Centric guard 동작 증명

### Guard 통합 확인 ✅
- `just gate` 명령에 preflight 가드 2종 통합
- Fail-fast 동작 증명 완료

### 정리 턴 DONE 잠금 ✅
- 모든 산출물 증거 확보
- Gate 강제 실행 경로 확인
- Commit 준비 완료

## 날짜
- 2026-02-18 18:15 UTC+09:00
