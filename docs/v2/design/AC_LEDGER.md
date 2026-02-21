generated_at: 2026-02-20T09:00:00Z
updated_at: 2026-02-20
sources: D_ROADMAP.md, docs/v2/ROADMAP_V2.md, logs/evidence/, docs/v2/SSOT_RULES.md
rules: evidence-driven done (gate3 + artifacts), status=OPEN/DONE/LOST_EVIDENCE, V2-only (D200+/D_ALPHA)
queue_policy: SEQUENTIAL_QUEUE — Alpha(TURN5) 최우선. Refactoring은 Alpha 직후 강제 배치. D200 미만 레거시 제외. 컨트롤러는 최상단 첫 번째 OPEN 티켓을 자동 포인팅.
legacy_policy: D200 미만은 이 장부에 포함하지 않음. 원본은 docs/archive/AC_LEDGER_BACKUP_20260220.md 에 동결 보존.
| AC_ID | TITLE | STAGE | STATUS | CANONICAL_EVIDENCE | LAST_COMMIT | DUP_GROUP_KEY | NOTES |
|---|---|---|---|---|---|---|---|
| D_ALPHA-0::AC-1 | universe(top=100) 로딩 시 universe_size=100 아티팩트 기록 | D_ALPHA | DONE | logs/evidence/d_alpha_0_universe_truth_*/edge_survey_report.json | 5b482ef | — | tests/test_d_alpha_0_universe_truth.py |
| D_ALPHA-0::AC-2 | survey 실행 중 unique symbols >= 80 (20분) 증명 | D_ALPHA | DONE | logs/evidence/d205_18_2d_smoke_20260221_0606 | c9b4835 | — | REAL survey 증거 필요 |
| D_ALPHA-0::AC-3 | symbols_top=100인데 10개만 들어가는 경로 제거/수정 | D_ALPHA | DONE | logs/evidence/d205_18_2d_smoke_20260221_0607 | f6ca81f | — | 런타임 검증 미해결 |
| D_ALPHA-0::AC-4 | 테스트 보장 (TopN 로딩/샘플링/기록) | D_ALPHA | DONE | tests/test_d_alpha_0_universe_truth.py | 5b482ef | — | — |
| D_ALPHA-1::AC-1 | fee 모델 maker/taker 조합 지원 (리베이트 포함) | D_ALPHA | DONE | tests/test_d_alpha_1_maker_pivot.py | 5b482ef | — | — |
| D_ALPHA-1::AC-2 | maker-taker net_edge_bps 계산 아티팩트 | D_ALPHA | DONE | logs/evidence/d_alpha_0_1_survey_maker_20min/ | 5b482ef | — | — |
| D_ALPHA-1::AC-3 | REAL survey 체결확률 모델 적용 net_edge_bps 산출 | D_ALPHA | DONE | logs/evidence/d_alpha_0_1_survey_maker_20min/ | 5b482ef | — | positive_net_edge_pct=0% |
| D_ALPHA-1::AC-4 | 돈 로직 변경은 엔진(core/domain)에만 존재 | D_ALPHA | DONE | arbitrage/domain + arbitrage/v2/core/opportunity | 5b482ef | — | — |
| D_ALPHA-1U::AC-1 | Universe metadata 기록 + coverage_ratio 산출 | D_ALPHA | DONE | logs/evidence/d_alpha_1u_survey_off_20260131_233706/ | UNKNOWN | — | — |
| D_ALPHA-1U::AC-2 | Redis 연결 실패 시 SystemExit(1) fail-fast | D_ALPHA | DONE | logs/evidence/d205_18_2d_smoke_20260221_0627 | b424819 | — | — |
| D_ALPHA-1U::AC-3 | engine_report.json에 redis_ok 상태 포함 | D_ALPHA | OPEN | NONE | UNKNOWN | — | — |
| D_ALPHA-1U::AC-4 | OBI 데이터 수집 (obi_score, depth_imbalance) | D_ALPHA | OPEN | NONE | UNKNOWN | — | — |
| D_ALPHA-1U::AC-5 | Top100 unique_symbols_evaluated >= 95 | D_ALPHA | OPEN | NONE | UNKNOWN | — | — |
| D_ALPHA-1U::AC-6 | DB strict 모드 db_inserts_ok > 0 검증 | D_ALPHA | OPEN | NONE | UNKNOWN | — | — |
| D_ALPHA-1U::AC-7 | 20분 Survey 완료 (winrate < 100%) | D_ALPHA | OPEN | NONE | UNKNOWN | — | — |
| D_ALPHA-1U-FIX-2::AC-1 | latency_ms 증가 시 latency_total만 증가 | D_ALPHA | DONE | logs/evidence/d_alpha_1u_survey_off_20260131_233706/ | UNKNOWN | — | — |
| D_ALPHA-1U-FIX-2-1::AC-1 | adverse slippage 주입 손실 케이스 발생 | D_ALPHA | DONE | logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/ | UNKNOWN | — | — |
| D_ALPHA-1U-FIX-2-1::AC-2 | fill 실패 시 reject_count KPI 기록 | D_ALPHA | OPEN | NONE | UNKNOWN | — | — |
| D_ALPHA-1U-FIX-2-1::AC-3 | 20m Survey losses >= 1 & winrate < 100% | D_ALPHA | OPEN | NONE | UNKNOWN | — | — |
| D_ALPHA-1U-FIX-2-1::AC-4 | latency_cost vs latency_total 단위 분리 | D_ALPHA | OPEN | NONE | UNKNOWN | — | — |
| D_ALPHA-1U-FIX-2-1::AC-5 | Evidence Minimum Set + FACT_CHECK | D_ALPHA | OPEN | NONE | UNKNOWN | — | — |
| D_ALPHA-2::AC-1 | OBI 동적 임계치 엔진 내장 | D_ALPHA | OPEN | NONE | UNKNOWN | — | — |
| D_ALPHA-3::AC-1 | inventory_penalty / quote_skew 엔진 내장 | D_ALPHA | OPEN | NONE | UNKNOWN | — | — |
| D_ALPHA-3::AC-2 | inventory 상태 KPI/아티팩트 기록 | D_ALPHA | OPEN | NONE | UNKNOWN | — | — |
| D_ALPHA-3::AC-3 | RiskGuard 연계 동작 | D_ALPHA | OPEN | NONE | UNKNOWN | — | — |
| D_ALPHA-PIPELINE-0::AC-1 | Canonical entrypoint 실행 스크립트 | D_ALPHA | OPEN | NONE | UNKNOWN | — | scripts/run_alpha_pipeline.py |
| D_ALPHA-PIPELINE-0::AC-2 | Gate 3단 PASS | D_ALPHA | DONE | logs/evidence/20260209_105148_gate_doctor_66a6d64/ | 66a6d64 | — | — |
| D_ALPHA-PIPELINE-0::AC-3 | DocOps Gate ExitCode=0 | D_ALPHA | DONE | logs/evidence/dalpha_pipeline_0_docops_20260209_112924/ | 66a6d64 | — | — |
| D_ALPHA-PIPELINE-0::AC-4 | V2 Boundary PASS | D_ALPHA | DONE | logs/evidence/dalpha_pipeline_0_boundary_20260209_105950/ | 66a6d64 | — | — |
| D_ALPHA-PIPELINE-0::AC-5 | 20m Survey TIME_REACHED 증거 | D_ALPHA | DONE | logs/evidence/dalpha_pipeline_0_survey_20260209_110022/ | 66a6d64 | — | — |
| D_ALPHA-PIPELINE-0::AC-6 | 파이프라인 요약 산출물 | D_ALPHA | OPEN | NONE | UNKNOWN | — | entrypoint 연결 필요 |
| D206-0::AC-1 | Reality Scan (DOPING/SKIP/WARN 탐지) | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-0::AC-2 | Standard Engine Artifact 정의 | D206 | OPEN | NONE | UNKNOWN | — | engine_report.json 스키마 |
| D206-0::AC-3 | PreflightChecker 재작성 | D206 | OPEN | NONE | UNKNOWN | — | Runner 참조 제거 |
| D206-0::AC-4 | Runner Diet (230줄, Zero-Logic) | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-0::AC-5 | Zero-Skip 강제 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-0::AC-6 | WARN=FAIL 강제 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-1::AC-1 | 도메인 모델 임포트 완료 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-1::AC-2 | OrderBookSnapshot 통합 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-1::AC-3 | ArbitrageOpportunity dataclass 통합 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-1::AC-4 | ArbitrageTrade 전환 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-1::AC-5 | ArbRoute 통합 (D206-2 이동) | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-1::AC-6 | Doctor Gate PASS 17/17 tests | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-2::AC-1 | detect_opportunity() V1 100% 재현 | D206 | OPEN | NONE | UNKNOWN | — | 6/6 parity |
| D206-2::AC-2 | on_snapshot() 완전 이식 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-2::AC-3 | FeeModel 통합 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-2::AC-4 | MarketSpec 통합 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-2::AC-5 | V1 vs V2 parity < 1e-8 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-2::AC-6 | 회귀 테스트 PASS | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-2-1::AC-1 | take_profit_bps/stop_loss_bps Exit Rules | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-2-1::AC-2 | PnL Precision Decimal 18자리 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-2-1::AC-3 | spread_reversal 재현 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-2-1::AC-4 | HFT Alpha Hook Ready | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-2-1::AC-5 | Parity 8/8 PASS | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-2-1::AC-6 | Doctor/Fast/Regression 28/28 PASS | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-3::AC-1 | config.yml 14개 필수 키 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-3::AC-2 | 필수 키 누락 시 RuntimeError | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-3::AC-3 | Exit Rules 4키 정식화 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-3::AC-4 | Entry Thresholds 필수화 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-3::AC-5 | Decimal 정밀도 강제 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-3::AC-6 | config_fingerprint 기록 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-3::AC-7 | Config 스키마 검증 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-3::AC-8 | 회귀 테스트 100% PASS | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-4::AC-1 | OrderIntent -> PaperExecutor 호출 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-4::AC-2 | OrderResult 처리 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-4::AC-3 | Fill DB 기록 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-4::AC-4 | Trade DB 기록 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-4::AC-5 | Engine cycle 통합 테스트 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-4::AC-6 | Gate 100% PASS | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-4-1::AC-1 | Decimal-Perfect 변환 | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-4-1::AC-2 | DB Ledger insert_order/insert_fill | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-4-1::AC-3 | WARN=FAIL | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-4-1::AC-4 | SKIP=FAIL 74/74 PASS | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-4-1::AC-5 | Gate Doctor/Fast 100% PASS | D206 | OPEN | NONE | UNKNOWN | — | — |
| D206-4-1::AC-6 | DocOps PASS | D206 | OPEN | NONE | UNKNOWN | — | — |
| D207-1::AC-1 | Real MarketData 실행 증거 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1::AC-2 | MockAdapter Slippage 모델 검증 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1::AC-3 | Latency 모델 주입 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1::AC-4 | Partial Fill 모델 주입 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1::AC-5 | BASELINE 20분 실행 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1::AC-6 | net_pnl > 0 (Realistic friction) | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1::AC-7 | KPI 비교 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-2::AC-1 | REAL baseline FX 기록 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-2::AC-2 | FX staleness > 60s 시 reject | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-2::AC-3 | Evidence 링크 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-3::AC-1 | fees_total=0 시 MODEL_ANOMALY | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-3::AC-2 | winrate >= 95% 시 MODEL_ANOMALY | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-3::AC-3 | trades_per_minute > 20 시 MODEL_ANOMALY | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-3::AC-4 | WARN/SKIP/ERROR = 즉시 FAIL | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-4::AC-1 | expected_inserts = trades * 5 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-4::AC-2 | config fingerprint 직렬화 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-4::AC-3 | inserts_ok == expected_inserts | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-5::AC-0 | 아키텍처 경계 고정 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-5::AC-1 | StopReason Single Truth Chain | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-5::AC-2 | stop_reason 3개 아티팩트 동기 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-5::AC-3 | MODEL_ANOMALY exit_code=1 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-1-5::AC-4 | db_integrity.enabled 필드 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-2::AC-1 | LONGRUN 3600초 exit_code=0 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-2::AC-2 | Heartbeat max_gap <= 65초 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-2::AC-3 | wallclock_drift_pct +/- 5% | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-2::AC-4 | KPI reject_total 정합성 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-2::AC-5 | Evidence 9개 파일 non-empty | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-2::AC-6 | WARN=FAIL 0 warnings/errors | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-3::AC-1 | 승률 임계치 win_rate < 1.0 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-3::AC-2 | win_rate=1.0 시 ExitCode=1 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-3::AC-3 | DIAGNOSIS.md 시장 vs 로직 분석 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-3::AC-4 | is_optimistic_warning 플래그 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-3::AC-5 | 승률 100% 테스트 FAIL 확인 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-3::AC-6 | OPS_PROTOCOL.md 갱신 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-3::AC-7 | deterministic drift 탐지 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-3::AC-8 | edge_distribution.json 저장 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-3::AC-9 | Trade Starvation kill-switch | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-4::AC-1 | 튜닝 대상 파라미터 정의 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-4::AC-2 | 목적 함수 정의 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-4::AC-3 | Bayesian 튜너 50회 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-4::AC-4 | Thin Wrapper 격리 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-4::AC-5 | 결과 산출물 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-4::AC-6 | Baseline +15% 개선 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-5::AC-1 | symbols 비어있음 시 Exit 1 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-5::AC-2 | REAL tick 0 시 Exit 1 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-5::AC-3 | run_meta 기록 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-5::AC-4 | edge_analysis_summary.json | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-5::AC-5 | Gate 3단 + DocOps PASS | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-5::AC-6 | REAL baseline 20분 증거 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-5-1::AC-1 | edge_distribution 분석 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-5-1::AC-2 | drift double-count 제거 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-5-1::AC-3 | REAL 20분 baseline | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-5-1::AC-4 | Gate + DocOps + Git | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-6::AC-1 | round_robin + max_symbols_per_tick | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-6::AC-2 | INVALID_UNIVERSE 가드 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-6::AC-3 | edge_survey_report.json 스키마 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-6::AC-4 | stop_reason Truth Chain | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-6::AC-5 | REAL 20분 survey 증거 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-6::AC-6 | Gate 3단 PASS | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-7::AC-1 | Survey Mode CLI | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-7::AC-2 | edge_survey_report.json 확장 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-7::AC-3 | 테스트 커버리지 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-7::AC-4 | Gate 3단 PASS | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-7::AC-5 | REAL survey 2회 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D207-7::AC-6 | DocOps ExitCode=0 | D207 | OPEN | NONE | UNKNOWN | — | — |
| D208::AC-1 | MockAdapter -> ExecutionBridge 리네이밍 | D208 | OPEN | NONE | UNKNOWN | — | — |
| D208::AC-2 | Unified Engine Interface 정리 | D208 | OPEN | NONE | UNKNOWN | — | — |
| D208::AC-3 | V1 Purge 후보 목록화 | D208 | OPEN | NONE | UNKNOWN | — | — |
| D208-SLIM-1::AC-1 | V1 미사용 모듈 legacy_archive/ 이동 | D208 | OPEN | NONE | UNKNOWN | — | — |
| D208-SLIM-1::AC-2 | 이동 리스트 문서화 | D208 | OPEN | NONE | UNKNOWN | — | — |
| D208-SLIM-1::AC-3 | V2 참조 무결성 검증 | D208 | OPEN | NONE | UNKNOWN | — | — |
| D208-SLIM-1::AC-4 | Gate 3단 PASS (이동 후) | D208 | OPEN | NONE | UNKNOWN | — | — |
| D208-SLIM-2::AC-1 | legacy test 물리 이동 | D208 | OPEN | NONE | UNKNOWN | — | docs/archive/legacy_tests/ |
| D208-SLIM-2::AC-2 | conftest.py legacy marker 제거 | D208 | OPEN | NONE | UNKNOWN | — | — |
| D208-SLIM-2::AC-3 | Gate 532+ tests 유지 확인 | D208 | OPEN | NONE | UNKNOWN | — | — |
| D208-SLIM-3::AC-1 | cleanup_storage.py 강화 | D208 | OPEN | NONE | UNKNOWN | — | preview/apply |
| D208-SLIM-3::AC-2 | Docker image prune 자동화 | D208 | OPEN | NONE | UNKNOWN | — | — |
| D208-SLIM-3::AC-3 | justfile clean_all 갱신 | D208 | OPEN | NONE | UNKNOWN | — | — |
| D209-1::AC-1 | 429 Rate Limit 자동 throttling | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-1::AC-2 | Timeout 재시도 로직 | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-1::AC-3 | Reject 원인 분석 | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-1::AC-4 | Partial Fill 처리 | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-1::AC-5 | 실패 시나리오 테스트 | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-1::AC-6 | OPS_PROTOCOL.md 갱신 | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-2::AC-1 | Position Limit max_position_usd | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-2::AC-2 | Loss Cutoff max_drawdown | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-2::AC-3 | Kill-Switch RiskGuard.stop() | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-2::AC-4 | 리스크 메트릭 KPI 기록 | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-2::AC-5 | 테스트 케이스 | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-2::AC-6 | RISK_GUARD.md 작성 | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-3::AC-1 | Wallclock 이중 검증 | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-3::AC-2 | Heartbeat 60초 간격 강제 | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-3::AC-3 | watch_summary.json 자동 생성 | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-3::AC-4 | ExitCode 체계 (0/1) | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-3::AC-5 | stop_reason 체계 | D209 | OPEN | NONE | UNKNOWN | — | — |
| D209-3::AC-6 | 예외 핸들러 일원화 | D209 | OPEN | NONE | UNKNOWN | — | — |
| D210-1::AC-1 | LIVE 아키텍처 문서 | D210 | OPEN | NONE | UNKNOWN | — | — |
| D210-1::AC-2 | Allowlist 정의 | D210 | OPEN | NONE | UNKNOWN | — | — |
| D210-1::AC-3 | Evidence 규격 | D210 | OPEN | NONE | UNKNOWN | — | — |
| D210-1::AC-4 | DONE 판정 기준 | D210 | OPEN | NONE | UNKNOWN | — | — |
| D210-1::AC-5 | 리스크 경고 | D210 | OPEN | NONE | UNKNOWN | — | — |
| D210-1::AC-6 | 문서 검토 | D210 | OPEN | NONE | UNKNOWN | — | — |
| D210-2::AC-1 | 잠금 메커니즘 | D210 | OPEN | NONE | UNKNOWN | — | — |
| D210-2::AC-2 | ExitCode 강제 | D210 | OPEN | NONE | UNKNOWN | — | — |
| D210-2::AC-3 | Evidence 검증 | D210 | OPEN | NONE | UNKNOWN | — | — |
| D210-2::AC-4 | Gate 스크립트 설계 | D210 | OPEN | NONE | UNKNOWN | — | — |
| D210-2::AC-5 | 테스트 케이스 | D210 | OPEN | NONE | UNKNOWN | — | — |
| D210-2::AC-6 | LIVE_GATE_DESIGN.md | D210 | OPEN | NONE | UNKNOWN | — | — |
| D211-1::AC-1 | 과거 데이터 수집 (1개월+) | D211 | OPEN | NONE | UNKNOWN | — | — |
| D211-2::AC-1 | Replay Engine 구현 | D211 | OPEN | NONE | UNKNOWN | — | — |
| D211-3::AC-1 | Bayesian Optimizer 통합 | D211 | OPEN | NONE | UNKNOWN | — | — |
| D211-4::AC-1 | Walk-Forward Validation | D211 | OPEN | NONE | UNKNOWN | — | — |
| D212-1::AC-1 | Multi-Symbol 동시 실행 | D212 | OPEN | NONE | UNKNOWN | — | — |
| D000-3::AC-1 | DOCOPS_TOKEN_POLICY.md + allowlist | D000 | OPEN | NONE | UNKNOWN | — | [META] |
| D000-3::AC-2 | DocOps 토큰 스캔 스크립트 | D000 | OPEN | NONE | UNKNOWN | — | [META] |
| D000-3::AC-3 | Strict SSOT 토큰 0건 | D000 | OPEN | NONE | UNKNOWN | — | [META] |
