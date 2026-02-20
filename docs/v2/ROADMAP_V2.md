# V2 Roadmap Rail (운영 레일 SSOT)

**생성일:** 2026-02-20
**규칙:** D200+ 전용. Alpha(TURN5 수익 로직) 최상단 배치. 단일 순차 레일.
**상위 SSOT:** D_ROADMAP.md (Slim Index) > docs/v2/SSOT_RULES.md (헌법)
**레거시 격리:** D200 미만은 docs/archive/ROADMAP_LEGACY_FULL_20260220.md 에 동결 보존.

---

## 우선순위 정렬 규칙

1. **Alpha(TURN5 수익 로직)** 관련 Step/AC는 레일 최상단
2. **엔진 핵심(D206 계열)** 수익 파이프라인 직결
3. **검증/안정성(D207 계열)** 수익 로직 신뢰성 확보
4. **인프라/리팩토링(D208~D209)** Alpha 이후 즉시 정리
5. **확장/상용화(D210~D215)** HFT/Live/Backtest

---

## Phase 1: Alpha Engine (수익 로직 최우선)

### D_ALPHA-0: Universe Truth (TopN 실제 동작 확정)

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | universe(top=100) 로딩 시 universe_size=100 아티팩트 기록 | DONE | logs/evidence/d_alpha_0_universe_truth_*/edge_survey_report.json |
| AC-2 | survey 실행 중 unique symbols >= 80 (20분 기준) 증명 | OPEN | NONE |
| AC-3 | symbols_top=100인데 10개만 들어가는 경로 제거/수정 | OPEN | NONE |
| AC-4 | 테스트 보장 (TopN 로딩/샘플링/기록) | DONE | tests/test_d_alpha_0_universe_truth.py |

### D_ALPHA-1: Maker Pivot MVP (Friction Inversion)

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | fee 모델 maker/taker 조합 지원 (리베이트 포함) | DONE | tests/test_d_alpha_1_maker_pivot.py |
| AC-2 | maker-taker net_edge_bps 계산 아티팩트 | DONE | detect_candidates maker_mode |
| AC-3 | REAL survey 체결확률 모델 적용 net_edge_bps 산출 | DONE | logs/evidence/d_alpha_0_1_survey_maker_20min/ |
| AC-4 | 돈 로직 변경은 엔진(core/domain)에만 존재 | DONE | arbitrage/domain + arbitrage/v2/core/opportunity |

### D_ALPHA-1U: Universe Unblock & Persistence Hardening

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | Universe metadata 기록 + coverage_ratio 산출 | DONE | logs/evidence/d_alpha_1u_survey_off_20260131_233706/ |
| AC-2 | Redis 연결 실패 시 SystemExit(1) fail-fast | OPEN | NONE |
| AC-3 | engine_report.json에 redis_ok 상태 포함 | OPEN | NONE |
| AC-4 | OBI 데이터 수집 (obi_score, depth_imbalance) | OPEN | NONE |
| AC-5 | Top100 unique_symbols_evaluated >= 95 | OPEN | NONE |
| AC-6 | DB strict 모드 db_inserts_ok > 0 검증 | OPEN | NONE |
| AC-7 | 20분 Survey 완료 (winrate < 100%) | OPEN | NONE |

### D_ALPHA-1U-FIX-2: Reality Welding (Latency Cost Decomposition)

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | latency_ms 증가 시 latency_total만 증가 | DONE | logs/evidence/d_alpha_1u_survey_off_20260131_233706/ |
| AC-2 | pessimistic_drift_bps 증가 시 latency_cost 증가 | DONE | (Merged AC-1-2) |
| AC-3 | PnL 분해 friction < 1.1% notional | DONE | (Merged AC-1-2) |
| AC-4 | latency_cost = slippage_bps + pessimistic_drift_bps | DONE | (Merged AC-1-2) |
| AC-5 | latency_total = ms 합계 | DONE | (Merged AC-1-2) |

### D_ALPHA-1U-FIX-2-1: Reality Welding Add-on (Winrate 현실화)

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | adverse slippage 주입 손실 케이스 발생 | DONE | logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/ |
| AC-2 | fill 실패 시 reject_count KPI 기록 | OPEN | NONE |
| AC-3 | 20m Survey losses >= 1 & winrate < 100% | OPEN | NONE |
| AC-4 | latency_cost vs latency_total 단위 분리 | OPEN | NONE |
| AC-5 | Evidence Minimum Set + FACT_CHECK | OPEN | NONE |

### D_ALPHA-2: Dynamic OBI Threshold

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | OBI 동적 임계치 엔진 내장 | OPEN | NONE |

### D_ALPHA-3: Inventory Management

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | inventory_penalty / quote_skew 엔진 내장 | OPEN | NONE |
| AC-2 | inventory 상태 KPI/아티팩트 기록 | OPEN | NONE |
| AC-3 | RiskGuard 연계 동작 | OPEN | NONE |

### D_ALPHA-PIPELINE-0: One-Command Product Pipeline

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | Canonical entrypoint 실행 스크립트 | OPEN | NONE |
| AC-2 | Gate 3단 PASS | DONE | logs/evidence/20260209_105148_gate_doctor_66a6d64/ |
| AC-3 | DocOps Gate ExitCode=0 | DONE | logs/evidence/dalpha_pipeline_0_docops_20260209_112924/ |
| AC-4 | V2 Boundary PASS | DONE | logs/evidence/dalpha_pipeline_0_boundary_20260209_105950/ |
| AC-5 | 20m Survey TIME_REACHED 증거 | DONE | logs/evidence/dalpha_pipeline_0_survey_20260209_110022/ |
| AC-6 | 파이프라인 요약 산출물 | OPEN | NONE |

---

## Phase 2: Engine Core (수익 파이프라인)

### D206-0: Engine Foundation

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | Reality Scan (DOPING 4개, SKIP 26개, WARN 422개) | OPEN | NONE |
| AC-2 | Standard Engine Artifact 정의 (engine_report.json 스키마) | OPEN | NONE |
| AC-3 | PreflightChecker 재작성 (Runner 참조 제거) | OPEN | NONE |
| AC-4 | Runner Diet (230줄, Zero-Logic) | OPEN | NONE |
| AC-5 | Zero-Skip 강제 (pytest SKIP 격리) | OPEN | NONE |
| AC-6 | WARN=FAIL 강제 | OPEN | NONE |

### D206-1: Domain Model Integration

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | 도메인 모델 임포트 완료 | OPEN | NONE |
| AC-2 | OrderBookSnapshot 통합 | OPEN | NONE |
| AC-3 | ArbitrageOpportunity dataclass 통합 | OPEN | NONE |
| AC-4 | ArbitrageTrade 전환 | OPEN | NONE |
| AC-5 | ArbRoute 통합 (D206-2 이동) | OPEN | NONE |
| AC-6 | Doctor Gate PASS 17/17 tests | OPEN | NONE |

### D206-2: detect_opportunity() 완전 이식

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | V1 로직 100% 재현 (6/6 parity) | OPEN | NONE |
| AC-2 | on_snapshot() 완전 이식 | OPEN | NONE |
| AC-3 | FeeModel 통합 | OPEN | NONE |
| AC-4 | MarketSpec 통합 | OPEN | NONE |
| AC-5 | V1 vs V2 parity < 1e-8 | OPEN | NONE |
| AC-6 | 회귀 테스트 PASS | OPEN | NONE |

### D206-2-1: Exit Rules & PnL Precision

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | take_profit_bps/stop_loss_bps Exit Rules | OPEN | NONE |
| AC-2 | PnL Precision Decimal 18자리 | OPEN | NONE |
| AC-3 | spread_reversal 재현 | OPEN | NONE |
| AC-4 | HFT Alpha Hook Ready | OPEN | NONE |
| AC-5 | Parity 8/8 PASS | OPEN | NONE |
| AC-6 | Doctor/Fast/Regression 28/28 PASS | OPEN | NONE |

### D206-3: Config SSOT (Zero-Fallback)

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | config.yml 14개 필수 키 | OPEN | NONE |
| AC-2 | 필수 키 누락 시 RuntimeError | OPEN | NONE |
| AC-3 | Exit Rules 4키 정식화 | OPEN | NONE |
| AC-4 | Entry Thresholds 필수화 | OPEN | NONE |
| AC-5 | Decimal 정밀도 강제 | OPEN | NONE |
| AC-6 | config_fingerprint 기록 | OPEN | NONE |
| AC-7 | Config 스키마 검증 | OPEN | NONE |
| AC-8 | 회귀 테스트 100% PASS | OPEN | NONE |

### D206-4: Order Pipeline (_trade_to_result)

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | OrderIntent -> PaperExecutor 호출 | OPEN | NONE |
| AC-2 | OrderResult 처리 | OPEN | NONE |
| AC-3 | Fill DB 기록 | OPEN | NONE |
| AC-4 | Trade DB 기록 | OPEN | NONE |
| AC-5 | Engine cycle 통합 테스트 | OPEN | NONE |
| AC-6 | Gate 100% PASS | OPEN | NONE |

### D206-4-1: Decimal-Perfect & DB Ledger

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | Decimal-Perfect 변환 | OPEN | NONE |
| AC-2 | DB Ledger insert_order/insert_fill | OPEN | NONE |
| AC-3 | WARN=FAIL (logger.warning -> info) | OPEN | NONE |
| AC-4 | SKIP=FAIL (74/74 PASS) | OPEN | NONE |
| AC-5 | Gate Doctor/Fast 100% PASS | OPEN | NONE |
| AC-6 | DocOps PASS | OPEN | NONE |

---

## Phase 3: Validation & Stability (검증/안정성)

### D207-1: REAL Baseline (20분 실행 증거)

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | Real MarketData 실행 증거 | OPEN | NONE |
| AC-2 | MockAdapter Slippage 모델 검증 | OPEN | NONE |
| AC-3 | Latency 모델 주입 | OPEN | NONE |
| AC-4 | Partial Fill 모델 주입 | OPEN | NONE |
| AC-5 | BASELINE 20분 실행 | OPEN | NONE |
| AC-6 | net_pnl > 0 (Realistic friction) | OPEN | NONE |
| AC-7 | KPI 비교 | OPEN | NONE |

### D207-1-2: Dynamic FX Intelligence

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | REAL baseline FX 기록 | OPEN | NONE |
| AC-2 | FX staleness > 60s 시 reject + FX_STALE | OPEN | NONE |
| AC-3 | Evidence 링크 | OPEN | NONE |

### D207-1-3: Active Failure Detection

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | fees_total=0 시 MODEL_ANOMALY + Exit 1 | OPEN | NONE |
| AC-2 | winrate >= 95% 시 MODEL_ANOMALY | OPEN | NONE |
| AC-3 | trades_per_minute > 20 시 MODEL_ANOMALY | OPEN | NONE |
| AC-4 | WARN/SKIP/ERROR = 즉시 FAIL | OPEN | NONE |

### D207-1-4: 5x Ledger Rule + Config Fingerprint

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | expected_inserts = trades * 5 | OPEN | NONE |
| AC-2 | config fingerprint 직렬화 | OPEN | NONE |
| AC-3 | inserts_ok == expected_inserts | OPEN | NONE |

### D207-1-5: Gate Wiring & Evidence Atomicity

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-0 | 아키텍처 경계 고정 (Artifact-First) | OPEN | NONE |
| AC-1 | StopReason Single Truth Chain | OPEN | NONE |
| AC-2 | stop_reason 3개 아티팩트 동기 | OPEN | NONE |
| AC-3 | MODEL_ANOMALY exit_code=1 기록 | OPEN | NONE |
| AC-4 | db_integrity.enabled 필드 | OPEN | NONE |

### D207-2: LONGRUN 60분 안정성

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | 3600초 실행, exit_code=0 | OPEN | NONE |
| AC-2 | Heartbeat max_gap <= 65초 | OPEN | NONE |
| AC-3 | wallclock_drift_pct +/- 5% | OPEN | NONE |
| AC-4 | KPI reject_total 정합성 | OPEN | NONE |
| AC-5 | Evidence 9개 파일 non-empty | OPEN | NONE |
| AC-6 | WARN=FAIL (0 warnings/errors) | OPEN | NONE |

### D207-3: Edge Distribution & Starvation

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | 승률 임계치 win_rate < 1.0 | OPEN | NONE |
| AC-2 | win_rate=1.0 시 ExitCode=1 | OPEN | NONE |
| AC-3 | DIAGNOSIS.md 시장 vs 로직 분석 | OPEN | NONE |
| AC-4 | is_optimistic_warning 플래그 | OPEN | NONE |
| AC-5 | 승률 100% 테스트 FAIL 확인 | OPEN | NONE |
| AC-6 | OPS_PROTOCOL.md 갱신 | OPEN | NONE |
| AC-7 | deterministic drift 탐지 | OPEN | NONE |
| AC-8 | edge_distribution.json 저장 | OPEN | NONE |
| AC-9 | Trade Starvation kill-switch | OPEN | NONE |

### D207-4: Bayesian Tuning

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | 튜닝 대상 파라미터 정의 | OPEN | NONE |
| AC-2 | 목적 함수 정의 | OPEN | NONE |
| AC-3 | Bayesian 튜너 50회 | OPEN | NONE |
| AC-4 | Thin Wrapper 격리 | OPEN | NONE |
| AC-5 | 결과 산출물 | OPEN | NONE |
| AC-6 | Baseline +15% 개선 | OPEN | NONE |

### D207-5: Run Validation Guards

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | symbols 비어있음 시 Exit 1 | OPEN | NONE |
| AC-2 | REAL tick 0 시 Exit 1 | OPEN | NONE |
| AC-3 | run_meta 기록 | OPEN | NONE |
| AC-4 | edge_analysis_summary.json | OPEN | NONE |
| AC-5 | Gate 3단 + DocOps PASS | OPEN | NONE |
| AC-6 | REAL baseline 20분 증거 | OPEN | NONE |

### D207-5-1: Edge Distribution Analysis

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | edge_distribution 분석 + 원인 분해 | OPEN | NONE |
| AC-2 | drift double-count 제거 | OPEN | NONE |
| AC-3 | REAL 20분 baseline (Merged D207-5::AC-6) | OPEN | NONE |
| AC-4 | Gate + DocOps + Git | OPEN | NONE |

### D207-6: Multi-Symbol Survey

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | round_robin + max_symbols_per_tick | OPEN | NONE |
| AC-2 | INVALID_UNIVERSE 가드 | OPEN | NONE |
| AC-3 | edge_survey_report.json 스키마 | OPEN | NONE |
| AC-4 | stop_reason Truth Chain | OPEN | NONE |
| AC-5 | REAL 20분 survey 증거 | OPEN | NONE |
| AC-6 | Gate 3단 PASS | OPEN | NONE |

### D207-7: Edge Survey Extended

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | Survey Mode (--survey-mode CLI) | OPEN | NONE |
| AC-2 | edge_survey_report.json 확장 | OPEN | NONE |
| AC-3 | 테스트 커버리지 | OPEN | NONE |
| AC-4 | Gate 3단 PASS | OPEN | NONE |
| AC-5 | REAL survey 2회 (Top100/Top200) | OPEN | NONE |
| AC-6 | DocOps ExitCode=0 | OPEN | NONE |

---

## Phase 4: Refactoring & Infrastructure Slimming (Alpha 직후 강제 배치)

### D208: Adapter Rename & V1 Purge 계획

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | MockAdapter -> ExecutionBridge 리네이밍 | OPEN | NONE |
| AC-2 | Unified Engine Interface 정리 | OPEN | NONE |
| AC-3 | V1 Purge 후보 목록화 (참조 0 확인) | OPEN | NONE |

### D208-SLIM-1: Legacy Code Isolation (신규)

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | V1 미사용 모듈 legacy_archive/ 이동 | OPEN | NONE |
| AC-2 | 이동 리스트 문서화 | OPEN | NONE |
| AC-3 | V2 참조 무결성 검증 (import 0 오류) | OPEN | NONE |
| AC-4 | Gate 3단 PASS (이동 후) | OPEN | NONE |

### D208-SLIM-2: Test Cleanup (신규)

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | legacy test -> docs/archive/legacy_tests/ 물리 이동 | OPEN | NONE |
| AC-2 | conftest.py legacy marker 제거 (이동 완료 후 불필요) | OPEN | NONE |
| AC-3 | Gate 532+ tests 유지 확인 | OPEN | NONE |

### D208-SLIM-3: Disk & Docker Cleanup Automation (신규)

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | scripts/cleanup_storage.py 강화 (preview/apply) | OPEN | NONE |
| AC-2 | Docker image prune 자동화 | OPEN | NONE |
| AC-3 | justfile clean_all 갱신 | OPEN | NONE |

---

## Phase 5: Risk & Operational Guards

### D209-1: Failure Mode Handling

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | 429 Rate Limit 자동 throttling | OPEN | NONE |
| AC-2 | Timeout 재시도 로직 | OPEN | NONE |
| AC-3 | Reject 원인 분석 | OPEN | NONE |
| AC-4 | Partial Fill 처리 | OPEN | NONE |
| AC-5 | 실패 시나리오 테스트 | OPEN | NONE |
| AC-6 | OPS_PROTOCOL.md 갱신 | OPEN | NONE |

### D209-2: Risk Guard

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | Position Limit max_position_usd | OPEN | NONE |
| AC-2 | Loss Cutoff max_drawdown | OPEN | NONE |
| AC-3 | Kill-Switch RiskGuard.stop() | OPEN | NONE |
| AC-4 | 리스크 메트릭 KPI 기록 | OPEN | NONE |
| AC-5 | 테스트 케이스 (Merged D209-1::AC-5) | OPEN | NONE |
| AC-6 | RISK_GUARD.md 작성 | OPEN | NONE |

### D209-3: Wallclock & Heartbeat & ExitCode

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | Wallclock 이중 검증 +/- 5% | OPEN | NONE |
| AC-2 | Heartbeat 60초 간격 강제 | OPEN | NONE |
| AC-3 | watch_summary.json 자동 생성 | OPEN | NONE |
| AC-4 | ExitCode 체계 (0/1) | OPEN | NONE |
| AC-5 | stop_reason 체계 | OPEN | NONE |
| AC-6 | 예외 핸들러 일원화 | OPEN | NONE |

---

## Phase 6: HFT & Commercial Readiness (D210~D215)

### D210-1: HFT Alpha Model Integration (OBI + A-S)

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | LIVE 아키텍처 문서 | OPEN | NONE |
| AC-1-2 | OBI Calculator 구현 (Static/VAMP/Weighted-Depth) | OPEN | NONE |
| AC-2 | Allowlist 정의 | OPEN | NONE |
| AC-2-2 | Order Book Depth 수집 | OPEN | NONE |
| AC-3 | Evidence 규격 | OPEN | NONE |
| AC-3-2 | OBI 기반 Entry Signal 통합 | OPEN | NONE |
| AC-4 | DONE 판정 기준 | OPEN | NONE |
| AC-4-2 | Paper OBI vs 비활성화 비교 | OPEN | NONE |
| AC-5 | 리스크 경고 | OPEN | NONE |
| AC-5-2 | Backtesting 결과 | OPEN | NONE |
| AC-6 | 문서 검토 | OPEN | NONE |
| AC-6-2 | OBI_ALPHA_MODEL.md | OPEN | NONE |

### D210-2: LIVE Safety Seal

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | 잠금 메커니즘 | OPEN | NONE |
| AC-2 | ExitCode 강제 | OPEN | NONE |
| AC-3 | Evidence 검증 | OPEN | NONE |
| AC-4 | Gate 스크립트 설계 | OPEN | NONE |
| AC-5 | 테스트 케이스 | OPEN | NONE |
| AC-6 | LIVE_GATE_DESIGN.md | OPEN | NONE |

### D210-3: LIVE Seal Verification

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | 잠금 테스트 | OPEN | NONE |
| AC-2 | 우회 방지 (ripgrep 증명) | OPEN | NONE |
| AC-3 | 문서 일치 확인 | OPEN | NONE |
| AC-4 | Gate 검증 | OPEN | NONE |
| AC-5 | 회귀 테스트 PASS | OPEN | NONE |
| AC-6 | 증거 문서 | OPEN | NONE |

### D210-4: Alpha Benchmark

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | Baseline vs OBI vs A-S 비교 | OPEN | NONE |
| AC-2 | Sharpe Ratio / Max Drawdown 비교 | OPEN | NONE |
| AC-3 | Market Condition별 성능 분석 | OPEN | NONE |
| AC-4 | 최적 알파 모델 조합 결정 | OPEN | NONE |
| AC-5 | 장기 Paper 1시간 | OPEN | NONE |
| AC-6 | Benchmark Report | OPEN | NONE |

### D211: Backtesting/Replay Engine

| AC | Goal | Status | Evidence |
|---|---|---|---|
| D211-1 | 과거 데이터 수집 (1개월+) | OPEN | NONE |
| D211-2 | Replay Engine 구현 | OPEN | NONE |
| D211-3 | Bayesian Optimizer 통합 | OPEN | NONE |
| D211-4 | Walk-Forward Validation | OPEN | NONE |

### D212: Multi-Symbol 동시 실행

| AC | Goal | Status | Evidence |
|---|---|---|---|
| D212-1 | Symbol별 독립 OpportunitySource/Executor | OPEN | NONE |
| D212-1 | Global Risk Aggregation | OPEN | NONE |
| D212-1 | Multi-Symbol Paper 3개 심볼 20분 | OPEN | NONE |

### D213~D215: (상세는 Phase 6 진입 후 정의)

| Step | Goal | Status |
|---|---|---|
| D213 | HFT Latency Optimization | OPEN |
| D214 | Admin UI/UX Dashboard | OPEN |
| D215 | ML-based Parameter Optimization | OPEN |

---

## Phase META: Governance & Infrastructure

### D000-3: DocOps Token Policy & Guards

| AC | Goal | Status | Evidence |
|---|---|---|---|
| AC-1 | DOCOPS_TOKEN_POLICY.md + allowlist | OPEN | NONE |
| AC-2 | DocOps 토큰 스캔 스크립트 | OPEN | NONE |
| AC-3 | Strict SSOT 토큰 0건 | OPEN | NONE |
| AC-4 | Welding guard 강화 | OPEN | NONE |
| AC-5 | Engine-centric guard 강화 | OPEN | NONE |
| AC-6 | PROFIT_LOGIC_STATUS.md | OPEN | NONE |
| AC-7 | Gate 3단 PASS | OPEN | NONE |
| AC-8 | DocOps PASS | OPEN | NONE |
| AC-9 | D_ROADMAP + Commit + Push | OPEN | NONE |

---

## 통계 요약 (2026-02-20 기준)

| 구분 | 수량 |
|---|---|
| 총 Phase | 6 + META |
| 총 Step (D번호) | 약 35개 |
| 총 AC | 약 250개 |
| DONE AC | 8개 (AC_LEDGER 기준, evidence 존재) |
| OPEN AC | 약 242개 |
| 레거시 격리 | D82~D106 전체 (docs/archive/) |
