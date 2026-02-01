# D_ROADMAP.md 업데이트 블록 (붙여넣기용)

**위치:** D_ROADMAP.md의 D_ALPHA 섹션 (D_ALPHA-1 다음)

---

```markdown
#### D_ALPHA-1U: Universe Unblock & Persistence Hardening (Commercial Master)

**상태:** PARTIAL COMPLETION (2026-01-31 / commit 0e699b5 / CRITICAL BLOCKER 발견)  
**목적:** Top100 Universe 로딩 강제, Redis/DB persistence 검증, OBI 데이터 수집, RunWatcher 100% winrate guard 검증.

**Acceptance Criteria:**
- [x] AC-1: Universe metadata (requested/loaded/evaluated) 기록 및 coverage_ratio/universe_symbols_hash 산출. *(arbitrage/v2/core/monitor.py, tests/test_d_alpha_0_universe_truth.py)*
- [x] AC-2: Redis 연결 실패 시 SystemExit(1) fail-fast 로직. *(arbitrage/v2/core/runtime_factory.py, arbitrage/v2/core/feature_guard.py)*
- [x] AC-3: engine_report.json에 redis_ok 상태 포함. *(arbitrage/v2/core/engine_report.py)*
- [x] AC-4: OBI (Order Book Imbalance) 데이터 수집 (obi_score, depth_imbalance). *(arbitrage/v2/core/opportunity_source.py)*
- [ ] AC-5: Top100 요청 시 unique_symbols_evaluated ≥ 95 (REAL survey 20분). *(BLOCKER: 42개만 로드됨, Universe Loader 수정 필요)*
- [ ] AC-6: DB strict 모드에서 db_inserts_ok > 0 검증. *(BLOCKER: db_mode=optional로 실행, 환경 변수 미설정)*
- [ ] AC-7: 20분 Survey 완료 (winrate < 100%). *(BLOCKER: RunWatcher가 100% winrate 탐지하여 6분 13초에 조기 종료)*

**Evidence 경로:**
- Maker OFF Survey (조기 종료): `logs/evidence/d_alpha_1u_survey_off_20260131_233706/`
- Gate Doctor: `logs/evidence/20260131_153906_gate_doctor_0e699b5/`
- Gate Fast: `logs/evidence/20260131_154117_gate_fast_0e699b5/`
- Gate Regression: `logs/evidence/20260131_154513_gate_regression_0e699b5/`
- 보고서: `docs/v2/reports/D_ALPHA/D_ALPHA-1U_REPORT.md`

**핵심 발견 (CRITICAL BLOCKERS):**
1. **Universe Loader:** Top100 요청 → 42개만 로드 (Binance API 400 에러 + 공통 심볼 부족)
2. **Paper Execution:** 100% winrate (22 trades, 0 losses) → RunWatcher FAIL_WINRATE_100
3. **DB Persistence:** db_inserts_ok=0 (db_mode=optional, 환경 변수 미설정)

**다음 액션 (Required for COMPLETION):**
- **D_ALPHA-1U-FIX-1:** Universe Loader 수정 (Top100 → ≥95 로드)
- **D_ALPHA-1U-FIX-2:** Paper Execution 현실성 강화 (winrate < 100%, losses ≥ 1)
- **D_ALPHA-1U-FIX-3:** DB Persistence 검증 (db_mode=strict + 환경 변수)

**의존성:**
- Depends on: D_ALPHA-1 (Maker Pivot MVP)
- Blocks: D_ALPHA-2 (OBI Filter & Ranking)
- Related: D207-3 (RunWatcher 100% winrate guard - 정상 동작 확인)

**Git 상태:**
- Branch: rescue/d207_6_multi_symbol_alpha_survey
- Commit: 0e699b5f15564ae61a2c4dbd5cdedfefa973bfe9
- Gate Results: Doctor/Fast/Regression 100% PASS

---
```

**붙여넣기 위치:** D_ROADMAP.md 라인 6838 (D_ALPHA-1 섹션 다음)

**주의사항:**
1. D_ALPHA-2 섹션은 **절대 수정하지 않습니다** (기존 정의 유지).
2. D_ALPHA-1U는 "추가(additive)" 방식으로 삽입됩니다.
3. AC-5/6/7은 미완료 상태로 표시하여 후속 작업(D_ALPHA-1U-FIX-1/2/3) 필요성을 명시합니다.
