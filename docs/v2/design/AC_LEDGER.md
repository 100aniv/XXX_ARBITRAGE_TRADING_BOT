generated_at: 2026-02-18T09:08:58Z
sources: c:\work\XXX_ARBITRAGE_TRADING_BOT\D_ROADMAP.md, c:\work\XXX_ARBITRAGE_TRADING_BOT\logs\evidence, c:\work\XXX_ARBITRAGE_TRADING_BOT\docs\v2\reports, c:\work\XXX_ARBITRAGE_TRADING_BOT\docs\v2\SSOT_RULES.md
rules: evidence-driven done (gate3 + artifacts), dup handling (evidence/title/intent), status=OPEN/DONE
| AC_ID | TITLE | STAGE | STATUS | CANONICAL_EVIDENCE | LAST_COMMIT | DUP_GROUP_KEY | NOTES |
|---|---|---|---|---|---|---|---|
| D_ALPHA-0::AC-1 | universe(top=100)가 로딩되면 **universe_size=100**이 아티팩트에 기록된다. *(tests/test_d_alpha_0_universe_truth.py)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:universetopuniversesizeteststestdalphauniversetruthpy | canonical evidence missing |
| D_ALPHA-0::AC-2 | survey 실행 중 “실제 평가된 unique symbols 수”가 **>=80**(20분 기준)임을 증명한다. *(Top100 REAL survey docops_followup_D_ALPHA_0_01: 20분 REAL survey 증거 필요)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:surveyuniquesymbolstoprealsurveydocopsfollowupdalpharealsurvey | canonical evidence missing; canonical evidence missing |
| D_ALPHA-0::AC-3 | `symbols_top=100`인데 `symbols`가 10개만 들어가는 경로가 있으면 제거/수정한다. *(runtime validation docops_followup_D_ALPHA_0_02: 런타임 검증 미해결)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:symbolstopsymbolsruntimevalidationdocopsfollowupdalpha | canonical evidence missing; canonical evidence missing |
| D_ALPHA-0::AC-4 | 테스트로 보장한다(TopN 로딩/샘플링/기록). *(tests/test_d_alpha_0_universe_truth.py)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:topnteststestdalphauniversetruthpy | canonical evidence missing |
| D_ALPHA-1::AC-1 | fee 모델이 maker/taker 조합을 지원(리베이트 포함 가능). *(arbitrage/domain/fee_model.py, tests/test_d_alpha_1_maker_pivot.py)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:feemakertakerarbitragedomainfeemodelpyteststestdalphamakerpivotpy | canonical evidence missing; canonical evidence missing |
| D_ALPHA-1::AC-2 | 동일 데이터에서 **maker-taker net_edge_bps**를 계산하여 아티팩트로 남긴다. *(detect_candidates maker_mode + fill_probability.py + tests/test_d_alpha_1_maker_pivot.py)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:makertakernetedgebpsdetectcandidatesmakermodefillprobabilitypyteststestdalphamakerpivotpy | canonical evidence missing; canonical evidence missing |
| D_ALPHA-1::AC-3 | REAL survey 실행 시 **체결 확률 모델(Fill Probability)**이 적용된 net_edge_bps를 산출한다. *(maker_mode ON/OFF 각 20분 실행, positive_net_edge_pct = 0% - 현재 시장 조건)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:realsurveyfillprobabilitynetedgebpsmakermodeonoffpositivenetedgepct | canonical evidence missing; canonical evidence missing |
| D_ALPHA-1::AC-4 | 돈 로직 변경은 엔진(core/domain)에만 존재한다(하네스 오염 금지). *(Changes confined to arbitrage/domain + arbitrage/v2/core/opportunity, harness CLI wiring only)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:coredomainchangesconfinedtoarbitragedomainarbitragevcoreopportunityharnesscliwiringonly | canonical evidence missing |
| D_ALPHA-1U::AC-1 | Universe metadata (requested/loaded/evaluated) 기록 및 coverage_ratio/universe_symbols_hash 산출. *(arbitrage/v2/core/monitor.py, tests/test_d_alpha_0_universe_truth.py)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:universemetadatarequestedloadedevaluatedcoverageratiouniversesymbolshasharbitragevcoremonitorpyteststestdalphauniversetruthpy | canonical evidence missing |
| D_ALPHA-1U::AC-1-2 | latency_ms 증가 → latency_total만 증가, latency_cost 불변 (단위 테스트 검증) | D_ALPHA | DONE | logs/evidence/d_alpha_1u_survey_off_20260131_233706/ | UNKNOWN | EVID:logs/evidence/d_alpha_1u_survey_off_20260131_233706/ | — |
| D_ALPHA-1U::AC-1-3 | adverse slippage 확률(>=10%) 주입으로 동일 입력에서 손실 케이스 발생 가능(결정론 seed 증거 포함). | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:adverseslippageseed | canonical evidence missing; canonical evidence missing |
| D_ALPHA-1U::AC-1-4 | `PaperOrchestrator`에서 `OrderIntent.price`/`quantity` 직접 접근 제거, quote notional 유도 경로(`quote_amount/base_qty/limit_price/ref_price`)로 교체. | D_ALPHA | DONE | logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/ | UNKNOWN | EVID:logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/ | — |
| D_ALPHA-1U::AC-2 | Redis 연결 실패 시 SystemExit(1) fail-fast 로직. *(arbitrage/v2/core/runtime_factory.py, arbitrage/v2/core/feature_guard.py)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:redissystemexitfailfastarbitragevcoreruntimefactorypyarbitragevcorefeatureguardpy | canonical evidence missing |
| D_ALPHA-1U::AC-2-2 | pessimistic_drift_bps 증가 → latency_cost 증가, latency_ms 불변 (단위 테스트 검증) (Merged into D_ALPHA-1U::AC-1-2) | D_ALPHA | DONE | logs/evidence/d_alpha_1u_survey_off_20260131_233706/ | UNKNOWN | EVID:logs/evidence/d_alpha_1u_survey_off_20260131_233706/ | Merged into D_ALPHA-1U::AC-1-2 (dup_key=EVID:logs/evidence/d_alpha_1u_survey_off_20260131_233706/) |
| D_ALPHA-1U::AC-2-3 | fill 실패(미체결) 발생 시 closed_trades 감소 또는 reject_count 증가가 KPI/engine_report에 기록됨. | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:fillclosedtradesrejectcountkpienginereport | canonical evidence missing |
| D_ALPHA-1U::AC-2-4 | Orchestrator loop의 모든 주요 `continue` 분기(`candidate_none`, `admin_paused`, `symbol_blacklisted`, `cooldown`, `intent_conversion_failed`, `execution_reject`)에서 cycle pacing 강제. (Merged into D_ALPHA-1U::AC-1-4) | D_ALPHA | OPEN | logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/ | UNKNOWN | EVID:logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/ | missing kpi.json; missing pnl/friction breakdown artifact; Merged into D_ALPHA-1U::AC-1-4 (dup_key=EVID:logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/) |
| D_ALPHA-1U::AC-3 | engine_report.json에 redis_ok 상태 포함. *(arbitrage/v2/core/engine_report.py)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:enginereportjsonredisokarbitragevcoreenginereportpy | canonical evidence missing |
| D_ALPHA-1U::AC-3-2 | PnL 분해 스케일 상식선 유지 (friction < 1.1% notional, 단위 테스트 검증) (Merged into D_ALPHA-1U::AC-1-2) | D_ALPHA | DONE | logs/evidence/d_alpha_1u_survey_off_20260131_233706/ | UNKNOWN | EVID:logs/evidence/d_alpha_1u_survey_off_20260131_233706/ | Merged into D_ALPHA-1U::AC-1-2 (dup_key=EVID:logs/evidence/d_alpha_1u_survey_off_20260131_233706/) |
| D_ALPHA-1U::AC-3-3 | Negative edge 일부 체결 허용으로 20m Survey에서 losses ≥ 1 & winrate < 100% 증거 확보. | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:negativeedgemsurveylosseswinrate | canonical evidence missing; canonical evidence missing |
| D_ALPHA-1U::AC-3-4 | 회귀 테스트 추가 및 PASS - `tests/test_d_alpha_1u_fix_2_reality_welding.py::test_ac4_orchestrator_quote_amount_regression_no_orderintent_price_attr`. (Merged into D_ALPHA-1U::AC-1-4) | D_ALPHA | OPEN | logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/ | UNKNOWN | EVID:logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/ | missing kpi.json; missing pnl/friction breakdown artifact; Merged into D_ALPHA-1U::AC-1-4 (dup_key=EVID:logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/) |
| D_ALPHA-1U::AC-4 | OBI (Order Book Imbalance) 데이터 수집 (obi_score, depth_imbalance). *(arbitrage/v2/core/opportunity_source.py)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:obiorderbookimbalanceobiscoredepthimbalancearbitragevcoreopportunitysourcepy | canonical evidence missing |
| D_ALPHA-1U::AC-4-2 | latency_cost = slippage_bps + pessimistic_drift_bps 기반 가격 영향 (KRW 단위) (Merged into D_ALPHA-1U::AC-1-2) | D_ALPHA | DONE | logs/evidence/d_alpha_1u_survey_off_20260131_233706/ | UNKNOWN | EVID:logs/evidence/d_alpha_1u_survey_off_20260131_233706/ | Merged into D_ALPHA-1U::AC-1-2 (dup_key=EVID:logs/evidence/d_alpha_1u_survey_off_20260131_233706/) |
| D_ALPHA-1U::AC-4-3 | latency_cost(가격 영향) vs latency_total(ms 합계) 단위 분리 유지 (FACT_CHECK_SUMMARY.txt 수치 증명). | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:latencycostvslatencytotalmsfactchecksummarytxt | canonical evidence missing; canonical evidence missing |
| D_ALPHA-1U::AC-4-4 | D206-1 proof matrix 재실행 PASS (top20/top50 x 5 seeds = 10 runs), `failed_runs=False`, `has_negative_pnl=False`, `missing_percentiles=[]`. (Merged into D_ALPHA-1U::AC-1-4) | D_ALPHA | OPEN | logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/ | UNKNOWN | EVID:logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/ | missing kpi.json; missing pnl/friction breakdown artifact; Merged into D_ALPHA-1U::AC-1-4 (dup_key=EVID:logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/) |
| D_ALPHA-1U::AC-5 | Top100 요청 시 unique_symbols_evaluated ≥ 95 (REAL survey 20분). *(FIX-1 완료: 100/100 로드, coverage_ratio=1.00, wallclock=51s)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:topuniquesymbolsevaluatedrealsurveycoverageratiowallclocks | canonical evidence missing |
| D_ALPHA-1U::AC-5-2 | latency_total = ms 합계 (시간 단위, 독립적 누적) (Merged into D_ALPHA-1U::AC-1-2) | D_ALPHA | DONE | logs/evidence/d_alpha_1u_survey_off_20260131_233706/ | UNKNOWN | EVID:logs/evidence/d_alpha_1u_survey_off_20260131_233706/ | Merged into D_ALPHA-1U::AC-1-2 (dup_key=EVID:logs/evidence/d_alpha_1u_survey_off_20260131_233706/) |
| D_ALPHA-1U::AC-5-3 | Evidence Minimum Set + FACT_CHECK_SUMMARY.txt 포함 (원자적 패키지). | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:evidenceminimumsetfactchecksummarytxt | canonical evidence missing |
| D_ALPHA-1U::AC-5-4 | runtime config 주입 경로 유지 (`runtime_factory`에서 `config_path` 우선 로드) + proof harness에서 `negative_edge_execution_probability=0.0`, `min_net_edge_bps>=40`, `edge_distribution_stride=1` 적용. (Merged into D_ALPHA-1U::AC-1-4) | D_ALPHA | OPEN | logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/ | UNKNOWN | EVID:logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/ | missing kpi.json; missing pnl/friction breakdown artifact; Merged into D_ALPHA-1U::AC-1-4 (dup_key=EVID:logs/evidence/STEP0_BOOTSTRAP_D_ALPHA_1U_FIX_2_1_20260204_102405/) |
| D_ALPHA-1U::AC-6 | DB strict 모드에서 db_inserts_ok > 0 검증. *(Evidence: logs/evidence/d_alpha_1u_closeout_20m_20260203_121456/engine_report.json, inserts_ok=20)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:dbstrictdbinsertsokevidencelogsevidencedalphaucloseoutmenginereportjsoninsertsok | canonical evidence missing |
| D_ALPHA-1U::AC-7 | 20분 Survey 완료 (winrate < 100%). *(Evidence: logs/evidence/d_alpha_1u_closeout_20m_20260203_121456/engine_report.json, winrate=0%, stop_reason=TIME_REACHED)* | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:surveywinrateevidencelogsevidencedalphaucloseoutmenginereportjsonwinratestopreasontimereached | canonical evidence missing |
| D_ALPHA-2::AC-1 | OBI 계산 표준화 및 **수익 구간 진입을 위한 동적 임계치(Dynamic Threshold)**가 엔진에 내장된다. | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:obidynamicthreshold | canonical evidence missing |
| D_ALPHA-3::AC-1 | inventory_penalty / quote_skew 파라미터가 엔진에 내장된다. | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:inventorypenaltyquoteskew | canonical evidence missing |
| D_ALPHA-3::AC-2 | inventory 상태 변화가 KPI/아티팩트로 기록된다. | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:inventorykpi | canonical evidence missing |
| D_ALPHA-3::AC-3 | RiskGuard와 충돌 없이(또는 연계하여) 동작한다. | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:riskguard | canonical evidence missing |
| D_ALPHA-PIPELINE-0::AC-1 | Canonical entrypoint 실행 스크립트 존재 및 실행 기록 (`scripts/run_alpha_pipeline.py`) | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:canonicalentrypointscriptsrunalphapipelinepy | canonical evidence missing |
| D_ALPHA-PIPELINE-0::AC-2 | Gate 3단 PASS (Doctor/Fast/Regression) | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:gatepassdoctorfastregression | canonical evidence missing |
| D_ALPHA-PIPELINE-0::AC-3 | DocOps Gate 실행 (check_ssot_docs ExitCode=0 + rg 결과 저장) | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:docopsgatecheckssotdocsexitcoderg | canonical evidence missing; canonical evidence missing |
| D_ALPHA-PIPELINE-0::AC-4 | V2 Boundary PASS | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:vboundarypass | canonical evidence missing |
| D_ALPHA-PIPELINE-0::AC-5 | 20m Survey TIME_REACHED 증거 (watch_summary/kpi/engine_report/edge_survey_report) | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:msurveytimereachedwatchsummarykpienginereportedgesurveyreport | canonical evidence missing; canonical evidence missing |
| D_ALPHA-PIPELINE-0::AC-6 | 파이프라인 요약 산출물 및 자동 레일 확인 (entrypoint 연결 필요) | D_ALPHA | OPEN | NONE | UNKNOWN | D_ALPHA:TITLE:entrypoint | canonical evidence missing |
| D206-0::AC-1 | Reality Scan - DOPING 발견 (4개), pytest SKIP 26개, logger.warning 422개 | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:realityscandopingpytestskiploggerwarning | canonical evidence missing |
| D206-0::AC-2 | Standard Engine Artifact 정의 - engine_report.json 스키마, 필수 필드 명시 | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:standardengineartifactenginereportjson | canonical evidence missing |
| D206-0::AC-3 | Gate Artifact 기반 변경 - PreflightChecker 전면 재작성 (Runner 참조 제거) | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:gateartifactpreflightcheckerrunner | canonical evidence missing |
| D206-0::AC-4 | Runner Diet - 230줄, Zero-Logic 확인 (이미 Thin Wrapper) | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:runnerdietzerologicthinwrapper | canonical evidence missing |
| D206-0::AC-5 | Zero-Skip 강제 - pytest SKIP mark 격리, filterwarnings 추가 | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:zeroskippytestskipmarkfilterwarnings | canonical evidence missing |
| D206-0::AC-6 | WARN=FAIL 강제 - WarningCounterHandler (Orchestrator), filterwarnings (pytest) | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:warnfailwarningcounterhandlerorchestratorfilterwarningspytest | canonical evidence missing |
| D206-1::AC-1 | 도메인 모델 임포트 - `arbitrage/v2/core/engine.py:15`에서 `arbitrage.v2.domain.*` 임포트 완료 | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:arbitragevcoreenginepyarbitragevdomain | canonical evidence missing |
| D206-1::AC-2 | OrderBookSnapshot 통합 - `_detect_single_opportunity()` 인자를 OrderBookSnapshot 지원 (backward compatible) | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:orderbooksnapshotdetectsingleopportunityorderbooksnapshotbackwardcompatible | canonical evidence missing |
| D206-1::AC-3 | ArbitrageOpportunity 통합 - `_detect_single_opportunity()` 반환값을 ArbitrageOpportunity dataclass로 변경 | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:arbitrageopportunitydetectsingleopportunityarbitrageopportunitydataclass | canonical evidence missing |
| D206-1::AC-4 | ArbitrageTrade 통합 - Engine 내부 `_open_trades: List[ArbitrageTrade]` 전환 완료 | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:arbitragetradeengineopentradeslistarbitragetrade | canonical evidence missing |
| D206-1::AC-5 | ArbRoute 통합 - V1 ArbRoute 의사결정 로직 (D206-2로 이동: FeeModel/MarketSpec 통합 필요) | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:arbroutevarbroutedfeemodelmarketspec | canonical evidence missing; canonical evidence missing |
| D206-1::AC-6 | 타입 안정성 검증 - Doctor Gate PASS (python -m compileall), 17/17 tests PASS | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:doctorgatepasspythonmcompilealltestspass | canonical evidence missing |
| D206-2-1::AC-1 | take_profit_bps/stop_loss_bps Exit Rules 구현 - 단위(bps) 명시, min_hold_sec 옵션 ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:takeprofitbpsstoplossbpsexitrulesbpsminholdsec | canonical evidence missing; canonical evidence missing |
| D206-2-1::AC-2 | PnL Precision 검증 - Decimal (18자리) 기반, 0.01% 오차 이내, ROUND_HALF_UP ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:pnlprecisiondecimalroundhalfup | canonical evidence missing; canonical evidence missing |
| D206-2-1::AC-3 | spread_reversal 케이스 회피 없이 재현 - V1 behavior recording, V2 policy expectation 분리 ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:spreadreversalvbehaviorrecordingvpolicyexpectation | canonical evidence missing; canonical evidence missing |
| D206-2-1::AC-4 | HFT Alpha Hook Ready - enable_alpha_exit 예비 슬롯 구현 ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:hftalphahookreadyenablealphaexit | canonical evidence missing |
| D206-2-1::AC-5 | Parity 테스트 100% PASS - 8/8 PASS, SKIP/xfail 0개 ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:paritypasspassskipxfail | canonical evidence missing |
| D206-2-1::AC-6 | Doctor/Fast/Regression 100% PASS - 28/28 tests PASS ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:doctorfastregressionpasstestspass | canonical evidence missing |
| D206-2::AC-1 | detect_opportunity() 완전 이식 - V1 로직 100% 재현 (환율, 스프레드, fee, slippage, gross/net edge) - 6/6 parity tests PASS | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:detectopportunityvfeeslippagegrossnetedgeparitytestspass | canonical evidence missing; canonical evidence missing |
| D206-2::AC-2 | on_snapshot() 완전 이식 - spread_reversal + TP/SL + PnL precision (D206-2-1에서 완성) | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:onsnapshotspreadreversaltpslpnlprecisiond | canonical evidence missing; canonical evidence missing |
| D206-2::AC-3 | FeeModel 통합 - `arbitrage/domain/fee_model.py` 직접 import, total_entry_fee_bps() 사용 | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:feemodelarbitragedomainfeemodelpyimporttotalentryfeebps | canonical evidence missing; canonical evidence missing |
| D206-2::AC-4 | MarketSpec 통합 - `arbitrage/domain/market_spec.py` 직접 import, fx_rate_a_to_b 사용 | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:marketspecarbitragedomainmarketspecpyimportfxrateatob | canonical evidence missing |
| D206-2::AC-5 | V1 parity 테스트 - V1 vs V2 detect_opportunity 100% 일치 (<1e-8 오차) | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:vparityvvsvdetectopportunitye | canonical evidence missing |
| D206-2::AC-6 | 회귀 테스트 - Doctor PASS, Fast PASS (D206-1 17/17 tests) | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:doctorpassfastpassdtests | canonical evidence missing |
| D206-3::AC-1 | **config.yml 생성** - Entry/Exit/Cost 키 전체 정의 (14개 필수 키) ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:configymlentryexitcost | canonical evidence missing |
| D206-3::AC-2 | **Zero-Fallback Enforcement** - 필수 키 누락 시 즉시 RuntimeError (기본값 금지) ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:zerofallbackenforcementruntimeerror | canonical evidence missing |
| D206-3::AC-3 | **Exit Rules 4키 정식화** - take_profit_bps, stop_loss_bps, min_hold_sec, enable_alpha_exit ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:exitrulestakeprofitbpsstoplossbpsminholdsecenablealphaexit | canonical evidence missing; canonical evidence missing |
| D206-3::AC-4 | **Entry Thresholds 필수화** - min_spread_bps, max_position_usd, max_open_trades (REQUIRED) ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:entrythresholdsminspreadbpsmaxpositionusdmaxopentradesrequired | canonical evidence missing; canonical evidence missing |
| D206-3::AC-5 | **Decimal 정밀도 강제** - config float → Decimal(18자리) 변환, 비교 연산 1LSB 오차 금지 ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:decimalconfigfloatdecimallsb | canonical evidence missing |
| D206-3::AC-6 | **Artifact Config Audit** - engine_report.json에 config_fingerprint 기록 (사후 감사) ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:artifactconfigauditenginereportjsonconfigfingerprint | canonical evidence missing |
| D206-3::AC-7 | **Config 스키마 검증** - 누락/오타 시 명확한 에러 메시지 + 예제 config 제공 ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:configconfig | canonical evidence missing |
| D206-3::AC-8 | **회귀 테스트** - Gate Doctor/Fast/Regression 100% PASS, config 누락 시 FAIL 검증 ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:gatedoctorfastregressionpassconfigfail | canonical evidence missing |
| D206-4-1::AC-1 | Decimal-Perfect - `/ 50000.0` → `/ Decimal('50000')` ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:decimalperfectdecimal | canonical evidence missing |
| D206-4-1::AC-2 | DB Ledger 기록 - `insert_order()` + `insert_fill()` 실제 호출 ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:dbledgerinsertorderinsertfill | canonical evidence missing; canonical evidence missing |
| D206-4-1::AC-3 | WARN=FAIL - `logger.warning` → `logger.info` ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:warnfailloggerwarningloggerinfo | canonical evidence missing |
| D206-4-1::AC-4 | SKIP=FAIL - 3개 SKIP 테스트 제거, 74/74 PASS ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:skipfailskippass | canonical evidence missing |
| D206-4-1::AC-5 | Gate Doctor/Fast 100% PASS (SKIP 0, WARN 0) ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:gatedoctorfastpassskipwarn | canonical evidence missing |
| D206-4-1::AC-6 | DocOps PASS (check_ssot_docs.py Exit 0) ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:docopspasscheckssotdocspyexit | canonical evidence missing; canonical evidence missing |
| D206-4::AC-1 | _trade_to_result() 구현 - OrderIntent → PaperExecutor.submit_order() 호출 ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:tradetoresultorderintentpaperexecutorsubmitorder | canonical evidence missing |
| D206-4::AC-2 | OrderResult 처리 - filled_qty/avg_price 추출 ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:orderresultfilledqtyavgprice | canonical evidence missing |
| D206-4::AC-3 | Fill 기록 - DB fills 테이블 기록 ✅ (D206-4-1 FIX) | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:filldbfillsdfix | canonical evidence missing |
| D206-4::AC-4 | Trade 기록 - DB orders 테이블 기록 ✅ (D206-4-1 FIX) | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:tradedbordersdfix | canonical evidence missing |
| D206-4::AC-5 | 파이프라인 통합 테스트 - Engine cycle 전체 플로우 검증 ✅ | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:enginecycle | canonical evidence missing |
| D206-4::AC-6 | 회귀 테스트 - Gate 100% PASS (SKIP 0) ✅ (D206-4-1 FIX → Closeout Regression 76/76) | D206 | OPEN | NONE | UNKNOWN | D206:TITLE:gatepassskipdfixcloseoutregression | canonical evidence missing |
| D207-1-2::AC-1 | REAL baseline에서 `fx_rate`, `fx_rate_source`, `fx_rate_age_sec`, `fx_rate_timestamp`, `fx_rate_degraded` 기록 ✅ | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:realbaselinefxratefxratesourcefxrateagesecfxratetimestampfxratedegraded | canonical evidence missing |
| D207-1-2::AC-2 | FX staleness(>60s) 발생 시 opportunity reject + stop_reason=`FX_STALE` + **Exit 1** ✅ | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:fxstalenesssopportunityrejectstopreasonfxstaleexit | canonical evidence missing |
| D207-1-2::AC-3 | D_ROADMAP에 Evidence 링크 + 지표 박제 ✅ | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:droadmapevidence | canonical evidence missing |
| D207-1-3::AC-1 | fees_total=0 → stop_reason=`MODEL_ANOMALY` + Exit 1 ✅ (코드: run_watcher.py:250-260, 실제: fees=18,927 KRW/184거래) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:feestotalstopreasonmodelanomalyexitrunwatcherpyfeeskrw | canonical evidence missing; canonical evidence missing |
| D207-1-3::AC-2 | winrate>=95% → stop_reason=`MODEL_ANOMALY` + Exit 1 ✅ (트리거: winrate=100% → FAIL F → Exit 1, 60초 조기 중단) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:winratestopreasonmodelanomalyexitwinratefailfexit | canonical evidence missing |
| D207-1-3::AC-3 | trades_per_minute>20 → stop_reason=`MODEL_ANOMALY` + Exit 1 ✅ (코드: run_watcher.py:262-279, 실제: 184/60s >> 20/min) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:tradesperminutestopreasonmodelanomalyexitrunwatcherpysmin | canonical evidence missing |
| D207-1-3::AC-4 | WARN/SKIP/ERROR = 즉시 FAIL (Exit 1) ✅ (코드: orchestrator.py:420-427, D207-1-5 보강: 404-418) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:warnskiperrorfailexitorchestratorpyd | canonical evidence missing |
| D207-1-4::AC-1 | expected_inserts = trades * 5 (engine_report에 공식 반영) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:expectedinsertstradesenginereport | canonical evidence missing |
| D207-1-4::AC-2 | config fingerprint가 항상 직렬화 가능(sha256:unknown fallback 포함) — 런타임 artifact로 증명 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:configfingerprintshaunknownfallbackartifact | canonical evidence missing |
| D207-1-4::AC-3 | (DB를 쓰는 모드에서) inserts_ok == expected_inserts 증명 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:dbinsertsokexpectedinserts | canonical evidence missing |
| D207-1-5::AC-0 | 아키텍처 경계 고정: Runner/Gate는 엔진 내부 객체를 참조하지 않고, 엔진이 생성한 Standard JSON Artifacts만 검증한다 (Artifact-First, Thin Wrapper) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:runnergatestandardjsonartifactsartifactfirstthinwrapper | canonical evidence missing |
| D207-1-5::AC-1 | StopReason Single Truth Chain - Orchestrator가 유일한 SSOT 소유자 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:stopreasonsingletruthchainorchestratorssot | canonical evidence missing; canonical evidence missing |
| D207-1-5::AC-2 | stop_reason이 engine_report.json, kpi.json, watch_summary.json에 동일하게 기록됨 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:stopreasonenginereportjsonkpijsonwatchsummaryjson | canonical evidence missing |
| D207-1-5::AC-3 | MODEL_ANOMALY 트리거 시 exit_code=1 + stop_reason="MODEL_ANOMALY" 기록됨 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:modelanomalyexitcodestopreasonmodelanomaly | canonical evidence missing |
| D207-1-5::AC-4 | db_integrity.enabled 필드 추가 (D207-1-4 보완) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:dbintegrityenabledd | canonical evidence missing |
| D207-1::AC-1 | Real MarketData (실행 증거 + 엔진 아티팩트로 입증) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:realmarketdata | canonical evidence missing |
| D207-1::AC-2 | MockAdapter Slippage 모델 (D205-17/18 재사용, 실측 대비 검증) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:mockadapterslippaged | canonical evidence missing; canonical evidence missing |
| D207-1::AC-3 | Latency 모델 (지수분포/꼬리 포함) 주입 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:latency | canonical evidence missing; canonical evidence missing |
| D207-1::AC-4 | Partial Fill 모델 주입 (deterministic Anti-Dice) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:partialfilldeterministicantidice | canonical evidence missing; canonical evidence missing |
| D207-1::AC-5 | BASELINE 20분 실행 (Evidence로 입증) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:baselineevidence | canonical evidence missing |
| D207-1::AC-6 | net_pnl > 0 (Realistic friction 포함) ✅ PASS | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:netpnlrealisticfrictionpass | canonical evidence missing; canonical evidence missing |
| D207-1::AC-7 | KPI 비교 (baseline vs 이전 실행 vs 파라미터) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:kpibaselinevsvs | canonical evidence missing |
| D207-2::AC-1 | LONGRUN 60분 - 3600.24초 실행, exit_code=0 ✅ PASS | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:longrunexitcodepass | canonical evidence missing |
| D207-2::AC-2 | Heartbeat 정합성 - max_gap=60.02초 ≤65초 ✅ PASS | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:heartbeatmaxgappass | canonical evidence missing |
| D207-2::AC-3 | Wallclock 정합성 - wallclock_drift_pct=0.0% (±5% 이내) ✅ PASS | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:wallclockwallclockdriftpctpass | canonical evidence missing |
| D207-2::AC-4 | KPI 정합성 - reject_total=15774 = sum(reject_reasons) ✅ PASS | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:kpirejecttotalsumrejectreasonspass | canonical evidence missing |
| D207-2::AC-5 | Evidence 완전성 - 9개 파일 생성, 모두 non-empty ✅ PASS | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:evidencenonemptypass | canonical evidence missing |
| D207-2::AC-6 | WARN=FAIL - warning_count=0, error_count=0 ✅ PASS | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:warnfailwarningcounterrorcountpass | canonical evidence missing |
| D207-3::AC-1 | 승률 임계치 - kpi_summary.json win_rate < 1.0 (100% 금지) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:kpisummaryjsonwinrate | canonical evidence missing |
| D207-3::AC-2 | 승률 100% 감지 - win_rate = 1.0 발견 시 ExitCode=1, stop_reason="WIN_RATE_100_SUSPICIOUS" | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:winrateexitcodestopreasonwinratesuspicious | canonical evidence missing |
| D207-3::AC-3 | DIAGNOSIS.md 시장 vs 로직 분석 - 실패 원인 분석 (시장 기회 부족 vs 로직 오류), Mock 데이터 사용 여부 검증, 거래 패턴 분석 (D205-9 기준 재사용) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:diagnosismdvsvsmockd | canonical evidence missing |
| D207-3::AC-4 | 예외 처리 - OPS_PROTOCOL.md에 승률 95% 초과 시 is_optimistic_warning 플래그 기록 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:opsprotocolmdisoptimisticwarning | canonical evidence missing |
| D207-3::AC-5 | 테스트 케이스 - 의도적으로 승률 100% 만드는 테스트, FAIL 확인 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:fail | canonical evidence missing |
| D207-3::AC-6 | 문서화 - OPS_PROTOCOL.md에 승률 100% 감지 시나리오 추가 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:opsprotocolmd | canonical evidence missing |
| D207-3::AC-7 | deterministic drift 탐지 반영 - net_edge_bps = edge_bps - drift, config 주입 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:deterministicdriftnetedgebpsedgebpsdriftconfig | canonical evidence missing; canonical evidence missing |
| D207-3::AC-8 | edge_distribution.json 저장 및 manifest 포함 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:edgedistributionjsonmanifest | canonical evidence missing; canonical evidence missing |
| D207-3::AC-9 | Trade Starvation kill-switch - 20분 경과 후 opp>=100 & intents=0이면 ExitCode=1 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:tradestarvationkillswitchoppintentsexitcode | canonical evidence missing |
| D207-4::AC-1 | 튜닝 대상 파라미터 정의 - min_spread_bps(20~50), take_profit_bps(10~100), stop_loss_bps(10~100), close_on_spread_reversal(bool) 범위 정의 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:minspreadbpstakeprofitbpsstoplossbpscloseonspreadreversalbool | canonical evidence missing; canonical evidence missing |
| D207-4::AC-2 | 목적 함수 정의 - net_pnl (주), drawdown (제약), trade_count (최소 10회), stability (표준편차) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:netpnldrawdowntradecountstability | canonical evidence missing; canonical evidence missing |
| D207-4::AC-3 | Bayesian 튜너 구현 - 50회 Iteration, Optuna or scikit-optimize 재사용 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:bayesianiterationoptunaorscikitoptimize | canonical evidence missing |
| D207-4::AC-4 | 튜닝 러너는 Thin Wrapper - 엔진 로직 오염 금지, arbitrage/v2/tuning/ 격리 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:thinwrapperarbitragevtuning | canonical evidence missing |
| D207-4::AC-5 | 결과 산출물 - tuned_config.yml, leaderboard.json (Top 10), tuning_report.md, evidence | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:tunedconfigymlleaderboardjsontoptuningreportmdevidence | canonical evidence missing |
| D207-4::AC-6 | 튜닝 결과 향상 검증 - Baseline 대비 +15% 이상 순이익 개선 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:baseline | canonical evidence missing |
| D207-5-1::AC-1 | edge_distribution 분석 + 원인 분해 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:edgedistribution | canonical evidence missing; canonical evidence missing |
| D207-5-1::AC-2 | drift double-count 제거 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:driftdoublecount | canonical evidence missing |
| D207-5-1::AC-3 | REAL 20분 baseline 증거 확보 (Merged into D207-5::AC-6) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:realbaselinemergedintodac | canonical evidence missing |
| D207-5-1::AC-4 | Gate + DocOps + Git | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:gatedocopsgit | canonical evidence missing; canonical evidence missing |
| D207-5::AC-1 | symbols 비어있음 → Exit 1 (INVALID_RUN_SYMBOLS_EMPTY) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:symbolsexitinvalidrunsymbolsempty | canonical evidence missing |
| D207-5::AC-2 | REAL tick 0 → Exit 1 (INVALID_RUN_REAL_TICKS_ZERO) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:realtickexitinvalidrunrealtickszero | canonical evidence missing |
| D207-5::AC-3 | run_meta 기록 (config_path, symbols, cli_args, git_sha, branch, run_id) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:runmetaconfigpathsymbolscliargsgitshabranchrunid | canonical evidence missing |
| D207-5::AC-4 | edge_analysis_summary.json 생성 + manifest 포함 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:edgeanalysissummaryjsonmanifest | canonical evidence missing; canonical evidence missing |
| D207-5::AC-5 | Gate 3단 + DocOps PASS | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:gatedocopspass | canonical evidence missing; canonical evidence missing |
| D207-5::AC-6 | REAL baseline 20분 실행 증거 확보 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:realbaseline | canonical evidence missing |
| D207-6::AC-1 | round_robin + max_symbols_per_tick 샘플링 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:roundrobinmaxsymbolspertick | canonical evidence missing |
| D207-6::AC-2 | INVALID_UNIVERSE 가드 (symbols empty/REAL tick 0) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:invaliduniversesymbolsemptyrealtick | canonical evidence missing |
| D207-6::AC-3 | edge_survey_report.json 스키마 + sampling_policy 기록 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:edgesurveyreportjsonsamplingpolicy | canonical evidence missing; canonical evidence missing |
| D207-6::AC-4 | stop_reason Truth Chain (TIME_REACHED) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:stopreasontruthchaintimereached | canonical evidence missing |
| D207-6::AC-5 | REAL 20분 survey 증거 | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:realsurvey | canonical evidence missing |
| D207-6::AC-6 | Gate 3단 PASS | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:gatepass | canonical evidence missing |
| D207-7::AC-1 | Survey Mode 구현 (--survey-mode CLI flag, profitable=False reject 기록) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:surveymodesurveymodecliflagprofitablefalsereject | canonical evidence missing; canonical evidence missing |
| D207-7::AC-2 | edge_survey_report.json 스키마 확장 (reject_total, reject_by_reason, tail_stats) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:edgesurveyreportjsonrejecttotalrejectbyreasontailstats | canonical evidence missing; canonical evidence missing |
| D207-7::AC-3 | 테스트 커버리지 (test_d207_7_edge_survey_extended.py) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:testdedgesurveyextendedpy | canonical evidence missing; canonical evidence missing |
| D207-7::AC-4 | Gate 3단 PASS (Doctor/Fast/Regression) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:gatepassdoctorfastregression | canonical evidence missing |
| D207-7::AC-5 | REAL survey 2회 실행 (Top100/Top200) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:realsurveytoptop | canonical evidence missing |
| D207-7::AC-6 | DocOps 검증 (check_ssot_docs.py ExitCode=0) | D207 | OPEN | NONE | UNKNOWN | D207:TITLE:docopscheckssotdocspyexitcode | canonical evidence missing; canonical evidence missing |
| D208::AC-1 | ExecutionBridge 리네이밍 - MockAdapter → ExecutionBridge (alias 유지, 행동변경 0) | D208 | OPEN | NONE | UNKNOWN | D208:TITLE:executionbridgemockadapterexecutionbridgealias | canonical evidence missing; canonical evidence missing |
| D208::AC-2 | Unified Engine Interface - Backtest/Paper/Live 동일 Engine + 교체 가능한 Adapter 구조 정리 | D208 | OPEN | NONE | UNKNOWN | D208:TITLE:unifiedengineinterfacebacktestpaperliveengineadapter | canonical evidence missing |
| D208::AC-3 | V1 Purge 계획 - 삭제 후보 목록화 + 참조 0 확인 (실제 삭제는 D209+ 범위) | D208 | OPEN | NONE | UNKNOWN | D208:TITLE:vpurged | canonical evidence missing |
| AUTO-OTHER::AC-1 | Prometheus 메트릭 6개 이상 노출 (7개 구현) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:prometheus | canonical evidence missing |
| AUTO-OTHER::AC-1-2 | Real open positions lookup (CrossExchangePositionManager 사용) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:realopenpositionslookupcrossexchangepositionmanager | canonical evidence missing |
| AUTO-OTHER::AC-2 | Docker Compose Prometheus/Grafana 통합 (3개 서비스 추가) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:dockercomposeprometheusgrafana | canonical evidence missing |
| AUTO-OTHER::AC-2-2 | Policy application (FAIL + Telegram P0) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:policyapplicationfailtelegramp | canonical evidence missing |
| AUTO-OTHER::AC-3 | Grafana 패널 4개 이상 구현 (Last Success, Duration P95, Check Breakdown, Latency) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:grafanalastsuccessdurationpcheckbreakdownlatency | canonical evidence missing; canonical evidence missing |
| AUTO-OTHER::AC-3-2 | Evidence saving (5 files) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencesavingfiles | canonical evidence missing |
| AUTO-OTHER::AC-4 | Preflight 결과가 Evidence에 저장 (.json + .prom) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:preflightevidencejsonprom | canonical evidence missing |
| AUTO-OTHER::AC-4-2 | Core Regression 44/44 PASS | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:coreregressionpass | canonical evidence missing |
| AUTO-OTHER::AC-5 | Telegram 알림 P0/P1 실제 발송 (P1 테스트 성공) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:telegramppp | canonical evidence missing |
| AUTO-OTHER::AC-5-2 | 문서 동기화 (D_ROADMAP, D98_7_REPORT, CHECKPOINT) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:droadmapdreportcheckpoint | canonical evidence missing |
| AUTO-OTHER::AC-6 | D98 테스트 100% PASS (12/12 PASS) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:dpasspass | canonical evidence missing |
| AUTO-OTHER::AC-6-2 | Git commit + push | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gitcommitpush | canonical evidence missing |
| AUTO-OTHER::AC-7 | 문서/커밋 한국어 작성 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:문서/커밋 한국어 작성 | canonical evidence missing |
| AUTO-OTHER::AC-8 | SSOT 동기화 (ROADMAP + CHECKPOINT) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:ssotroadmapcheckpoint | canonical evidence missing; canonical evidence missing |
| D000-3::AC-1 | DOCOPS_TOKEN_POLICY.md + allowlist 설정 추가 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:docopstokenpolicymdallowlist | canonical evidence missing; canonical evidence missing |
| D000-3::AC-2 | DocOps 토큰 스캔 스크립트 + justfile 연동 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:docopsjustfile | canonical evidence missing; canonical evidence missing |
| D000-3::AC-3 | Strict SSOT 문서 토큰 0건 유지 (SSOT_RULES/SSOT_MAP/V2_ARCHITECTURE) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:strictssotssotrulesssotmapvarchitecture | canonical evidence missing; canonical evidence missing |
| D000-3::AC-4 | Welding guard 강화 (pnl_calculator 단일 진실성) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:weldingguardpnlcalculator | canonical evidence missing; canonical evidence missing |
| D000-3::AC-5 | Engine-centric guard에 harness 얇은막 강제 추가 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:enginecentricguardharness | canonical evidence missing |
| D000-3::AC-6 | PROFIT_LOGIC_STATUS.md 작성 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:profitlogicstatusmd | canonical evidence missing; canonical evidence missing |
| D000-3::AC-7 | Gate Doctor/Fast/Regression PASS | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatedoctorfastregressionpass | canonical evidence missing |
| D000-3::AC-8 | DocOps PASS (check_ssot_docs + token policy scan) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:docopspasscheckssotdocstokenpolicyscan | canonical evidence missing; canonical evidence missing |
| D000-3::AC-9 | D_ROADMAP 업데이트 + Commit + Push | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:droadmapcommitpush | canonical evidence missing |
| D205-12-2::AC-1 | Engine.run() 메서드 구현 (유일한 루프, duration_minutes 파라미터) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:enginerundurationminutes | canonical evidence missing |
| D205-12-2::AC-2 | EngineState enum 정의 (RUNNING/PAUSED/STOPPED/PANIC) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:enginestateenumrunningpausedstoppedpanic | canonical evidence missing |
| D205-12-2::AC-3 | AdminControl 훅 통합 (should_process_tick → tick skip) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:admincontrolshouldprocessticktickskip | canonical evidence missing |
| D205-12-2::AC-4 | AdminControl 훅 통합 (is_symbol_blacklisted → symbol skip) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:admincontrolissymbolblacklistedsymbolskip | canonical evidence missing |
| D205-12-2::AC-8 | Doctor/Fast Gate PASS ✅ (Regression은 차기) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:doctorfastgatepassregression | canonical evidence missing |
| D205-12-2::AC-9 | Evidence 패키징 (scan_report, manifest, gate 결과) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencescanreportmanifestgate | canonical evidence missing |
| D205-12::AC-1 | ControlState enum 정의 (RUNNING/PAUSED/STOPPING/PANIC/EMERGENCY_CLOSE) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:controlstateenumrunningpausedstoppingpanicemergencyclose | canonical evidence missing |
| D205-12::AC-2 | CommandHandler 구현 (start/stop/panic/blacklist/close 명령 처리) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:commandhandlerstartstoppanicblacklistclose | canonical evidence missing |
| D205-12::AC-3 | Start/Stop 명령 → 5초 내 상태 변경 검증 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:startstop | canonical evidence missing |
| D205-12::AC-4 | Panic 명령 → 5초 내 중단 + 포지션 초기화 검증 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:panic | canonical evidence missing |
| D205-12::AC-5 | Symbol blacklist → 즉시 거래 중단 검증 (decision trace) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:symbolblacklistdecisiontrace | canonical evidence missing |
| D205-12::AC-6 | Emergency close → 10초 내 청산 검증 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:emergencyclose | canonical evidence missing |
| D205-12::AC-7 | Admin 명령 audit log (누가/언제/무엇을/결과) NDJSON 형식 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:adminauditlogndjson | canonical evidence missing |
| D205-12::AC-8 | 모든 제어 기능 유닛 테스트 (15개 테스트, 100% PASS) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:pass | canonical evidence missing |
| D205-13::AC-1 | config.yml에 mode 필드 추가 (paper/live/replay SSOT) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:configymlmodepaperlivereplayssot | canonical evidence missing; canonical evidence missing |
| D205-13::AC-2 | V2Config에 mode 필드 파싱 및 validation ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:vconfigmodevalidation | canonical evidence missing |
| D205-13::AC-3 | PaperRunner.run()에서 while 루프 제거 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:paperrunnerrunwhile | canonical evidence missing |
| D205-13::AC-4 | Engine.run() 호출로 전환 (fetch_tick_data/process_tick 콜백) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:enginerunfetchtickdataprocesstick | canonical evidence missing |
| D205-13::AC-5 | 증명 테스트 4개 추가 및 PASS ✅ (Merged into D205-12::AC-8) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:passmergedintodac | canonical evidence missing |
| D205-14-1::AC-1 | AutoTuner 실행 완료 (144 조합, 13.05초) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:autotuner | canonical evidence missing |
| D205-14-1::AC-2 | leaderboard.json 생성 (Top 10 조합) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:leaderboardjsontop | canonical evidence missing |
| D205-14-1::AC-3 | best_params.json 생성 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:bestparamsjson | canonical evidence missing |
| D205-14-1::AC-4 | SSOT_RULES.md 보강 (Reuse Exception Protocol + Smoke 규칙) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:ssotrulesmdreuseexceptionprotocolsmoke | canonical evidence missing; canonical evidence missing |
| D205-14-1::AC-5 | TuningConfig 추가 (config.py 누락 수정) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:tuningconfigconfigpy | canonical evidence missing |
| D205-14-1::AC-6 | Gate 3단 PASS (Doctor/Fast/Regression) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatepassdoctorfastregression | canonical evidence missing |
| D205-14-1::AC-7 | Evidence 패키징 (kpi.json, manifest.json, README.md) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencekpijsonmanifestjsonreadmemd | canonical evidence missing |
| D205-14-2::AC-1 | 입력 데이터 200줄 확보 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:입력 데이터 200줄 확보 ✅ | canonical evidence missing |
| D205-14-2::AC-2 | AutoTuner 실행 완료 (144 조합, 200 ticks) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:autotunerticks | canonical evidence missing |
| D205-14-2::AC-3 | leaderboard.json 형식 검증 테스트 추가 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:leaderboardjson | canonical evidence missing |
| D205-14-2::AC-4 | Gate 3단 PASS (Doctor/Fast/Regression) ✅ (Merged into D205-14-1::AC-6) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatepassdoctorfastregressionmergedintodac | canonical evidence missing |
| D205-14-2::AC-5 | D_ROADMAP 임시 토큰 제거 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:droadmap | canonical evidence missing |
| D205-14-2::AC-6 | Evidence 패키징 (kpi.json, README.md) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencekpijsonreadmemd | canonical evidence missing |
| D205-14-3::AC-1 | 실제 시장 데이터 1000+ ticks 기록 ✅ (1050 ticks) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:ticksticks | canonical evidence missing |
| D205-14-3::AC-2 | 유니크 비율 >= 50% ✅ (100%, 1050/1050) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:유니크 비율 >= 50% ✅ (100%, 1050/1050) | canonical evidence missing |
| D205-14-3::AC-4 | Gate 3단 PASS (Doctor/Fast/Regression) ✅ (Merged into D205-14-1::AC-6) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatepassdoctorfastregressionmergedintodac | canonical evidence missing; Merged into D205-14-2::AC-4 (dup_key=OTHER:TITLE:gatepassdoctorfastregressionmergedintodac) |
| D205-14-3::AC-5 | Evidence 패키징 (README + kpi/stats) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencereadmekpistats | canonical evidence missing |
| D205-14-3::AC-6 | D_ROADMAP 임시 토큰 제거 + D205-14-3 추가 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:droadmapd | canonical evidence missing |
| D205-14-3::AC-7 | Git commit + push ✅ (Merged into AUTO-OTHER::AC-6-2) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gitcommitpushmergedintoautootherac | canonical evidence missing |
| D205-14-4::AC-1 | Upbit orderbook best bid/ask 수집 ✅ (get_orderbook() 호출 추가) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:upbitorderbookbestbidaskgetorderbook | canonical evidence missing |
| D205-14-4::AC-2 | Binance bookTicker best bid/ask 수집 ✅ (이미 구현됨) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:binancebooktickerbestbidask | canonical evidence missing |
| D205-14-4::AC-3 | MarketTick schema bid/ask 현실값 기록 ✅ (1038 ticks) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:markettickschemabidaskticks | canonical evidence missing |
| D205-14-4::AC-4 | market_stats.json spread_bps median > 0 ✅ (0.3 bps, D205-14-3의 0 bps 해결) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:marketstatsjsonspreadbpsmedianbpsdbps | canonical evidence missing; canonical evidence missing |
| D205-14-4::AC-6 | Gate 3단 PASS ✅ (Doctor/Fast 16 tests/Regression 2 tests) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatepassdoctorfasttestsregressiontests | canonical evidence missing |
| D205-14-4::AC-7 | Evidence 패키징 ✅ (README + manifest + kpi + stats + leaderboard) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencereadmemanifestkpistatsleaderboard | canonical evidence missing |
| D205-14-4::AC-8 | D_ROADMAP PARTIAL 업데이트 ✅ (this commit) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:droadmappartialthiscommit | canonical evidence missing; canonical evidence missing |
| D205-14-4::AC-9 | Git commit + push ✅ (this commit) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gitcommitpushthiscommit | canonical evidence missing |
| D205-14-5::AC-1 | Upbit REST provider에서 **bid_size/ask_size 기록** ✅ (0.242~0.195 BTC) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:upbitrestproviderbidsizeasksizebtc | canonical evidence missing |
| D205-14-5::AC-10 | D_ROADMAP PARTIAL 업데이트 + Git commit + push ✅ (this commit) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:droadmappartialgitcommitpushthiscommit | canonical evidence missing; canonical evidence missing |
| D205-14-5::AC-2 | Binance REST provider에서 **bid_size/ask_size 기록** ✅ (2.241~9.458 BTC) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:binancerestproviderbidsizeasksizebtc | canonical evidence missing |
| D205-14-5::AC-3 | Ticker schema에 **bid_size/ask_size 필드 추가** ✅ (optional, backward compatible) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:tickerschemabidsizeasksizeoptionalbackwardcompatible | canonical evidence missing |
| D205-14-5::AC-4 | Recorder에서 MarketTick에 size 기록 시 **None 검증 가드** ✅ (skip if None) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:recordermarketticksizenoneskipifnone | canonical evidence missing |
| D205-14-5::AC-5 | 10분 recording 재실행 → market.ndjson 샘플 5줄에서 **size None 0건** ✅ (289 ticks) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:recordingmarketndjsonsizenoneticks | canonical evidence missing |
| D205-14-5::AC-6 | market_stats.json에 **size_none_count** 필드 추가 ✅ (0건, README에 기록) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:marketstatsjsonsizenonecountreadme | canonical evidence missing |
| D205-14-5::AC-8 | Gate 3단 PASS ✅ (Doctor/Fast 6 tests 0.17s/Regression 6 tests 0.13s) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatepassdoctorfasttestssregressiontestss | canonical evidence missing |
| D205-14-5::AC-9 | Evidence 패키징 ✅ (manifest + leaderboard + decisions + README) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencemanifestleaderboarddecisionsreadme | canonical evidence missing |
| D205-14-6::AC-1 | BinanceRestProvider market_type="futures" 기본 전환 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:binancerestprovidermarkettypefutures | canonical evidence missing |
| D205-14-6::AC-2 | README/ROADMAP "Futures 기본" 문장 정렬 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:readmeroadmapfutures | canonical evidence missing |
| D205-14-6::AC-3 | ReplayRunner notional 파라미터화 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:replayrunnernotional | canonical evidence missing |
| D205-14-6::AC-4 | config.yml tuning.notional 추가 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:configymltuningnotional | canonical evidence missing |
| D205-14-6::AC-5 | ParameterSweep params.json 저장 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:parametersweepparamsjson | canonical evidence missing |
| D205-14-6::AC-6 | Gate 3단 PASS (Doctor/Fast/Regression) ✅ (Merged into D205-14-1::AC-6) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatepassdoctorfastregressionmergedintodac | canonical evidence missing; Merged into D205-14-2::AC-4 (dup_key=OTHER:TITLE:gatepassdoctorfastregressionmergedintodac) |
| D205-14-6::AC-7 | AutoTuner 재실행 → leaderboard Top10 mean_net_edge_bps unique >= 2 ❌ (unique=1, 시장 현실 제약) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:autotunerleaderboardtopmeannetedgebpsuniqueunique | canonical evidence missing; canonical evidence missing |
| D205-14-6::AC-8 | Evidence 패키징 (manifest/kpi/leaderboard/params.json/README) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencemanifestkpileaderboardparamsjsonreadme | canonical evidence missing |
| D205-14-6::AC-9 | D_ROADMAP 업데이트 + Git commit + push ⏳ (방향성 재검토 후 진행) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:droadmapgitcommitpush | canonical evidence missing |
| D205-14::AC-1 | Config SSOT - config.yml에 tuning.param_ranges 정의 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:configssotconfigymltuningparamranges | canonical evidence missing; canonical evidence missing |
| D205-14::AC-2 | Tuning Runner - AutoTuner 클래스 구현 (sweep.py 재사용) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:tuningrunnerautotunersweeppy | canonical evidence missing |
| D205-14::AC-3 | Dry-run - 단일 파라미터 조합 평가 성공 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:dryrun | canonical evidence missing |
| D205-14::AC-4 | Result Storage - leaderboard.json, best_params.json 생성 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:resultstorageleaderboardjsonbestparamsjson | canonical evidence missing |
| D205-14::AC-5 | CLI - scripts/run_d205_14_autotune.py 실행 가능 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:cliscriptsrundautotunepy | canonical evidence missing |
| D205-14::AC-6 | Evidence - manifest.json + README.md 재현 패키지 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencemanifestjsonreadmemd | canonical evidence missing |
| D205-15-2::AC-1 | Naming Purge 완료 (README.md, D_ROADMAP.md 숫자 라벨 제거) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:namingpurgereadmemddroadmapmd | canonical evidence missing |
| D205-15-2::AC-11 | D_ROADMAP 최종 업데이트 + Commit + Push ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:droadmapcommitpush | canonical evidence missing; Merged into D000-3::AC-9 (dup_key=OTHER:TITLE:droadmapcommitpush) |
| D205-15-2::AC-2 | Universe Builder 모듈 추가 (arbitrage/v2/universe/builder.py) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:universebuilderarbitragevuniversebuilderpy | canonical evidence missing |
| D205-15-2::AC-3 | config.yml universe 설정 (mode: static | topn, topn_count: 100) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:configymluniversemodestatictopntopncount | canonical evidence missing |
| D205-15-2::AC-5 | Evidence Run 완료 (12 symbols, 11 valid, TopK=3) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencerunsymbolsvalidtopk | canonical evidence missing |
| D205-15-2::AC-7 | leaderboard.json (ADA/AVAX/LINK 오토튠 완료) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:leaderboardjsonadaavaxlink | canonical evidence missing |
| D205-15-2::AC-8 | Gate 3단 PASS (Doctor/Fast 2379 passed) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatepassdoctorfastpassed | canonical evidence missing |
| D205-15-2::AC-9 | Evidence 패키징 (FINAL_REPORT.md + cost_breakdown.json) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencefinalreportmdcostbreakdownjson | canonical evidence missing |
| D205-15-3::AC-1 | Directional/Executable spread KPI 추가 (`executable_spread_bps`) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:directionalexecutablespreadkpiexecutablespreadbps | canonical evidence missing; canonical evidence missing |
| D205-15-3::AC-2 | `tradeable_rate` KPI 추가 (executable > 0인 비율) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:tradeableratekpiexecutable | canonical evidence missing |
| D205-15-3::AC-3 | Funding Rate Provider 모듈 추가 (`arbitrage/v2/funding/provider.py`) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:fundingrateproviderarbitragevfundingproviderpy | canonical evidence missing |
| D205-15-3::AC-4 | `funding_adjusted_edge_bps` KPI 계산 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:fundingadjustededgebpskpi | canonical evidence missing; canonical evidence missing |
| D205-15-3::AC-5 | evidence_guard.py 강화 (atomic write: temp → fsync → rename) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidenceguardpyatomicwritetempfsyncrename | canonical evidence missing |
| D205-15-3::AC-6 | KPI 비교 Evidence 완료 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:kpievidence | canonical evidence missing |
| D205-15-3::AC-7 | Gate 3단 PASS (Doctor/Fast/Regression) ✅ (Merged into D205-14-1::AC-6) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatepassdoctorfastregressionmergedintodac | canonical evidence missing; Merged into D205-14-2::AC-4 (dup_key=OTHER:TITLE:gatepassdoctorfastregressionmergedintodac) |
| D205-15-3::AC-8 | D_ROADMAP 업데이트 + Commit + Push ✅ (Merged into D205-15-2::AC-11) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:droadmapcommitpushmergedintodac | canonical evidence missing |
| D205-15-4::AC-1 | LiveFxProvider 구현 (crypto-implied 방식) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:livefxprovidercryptoimplied | canonical evidence missing |
| D205-15-4::AC-2 | config/v2/config.yml에 fx 섹션 추가 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:configvconfigymlfx | canonical evidence missing |
| D205-15-4::AC-3 | validate_fx_provider_for_mode LIVE 차단 테스트 ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:validatefxproviderformodelive | canonical evidence missing |
| D205-15-4::AC-4 | Evidence에 FX 메타 기록 (fx_rate, fx_source, fx_timestamp, degraded) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencefxfxratefxsourcefxtimestampdegraded | canonical evidence missing |
| D205-15-4::AC-5 | 상수 후보 탐지 및 config 반영 (ADD-ON #2) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:configaddon | canonical evidence missing |
| D205-15-4::AC-6 | 중복 모듈 탐지 및 통합 (ADD-ON #3) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:addon | canonical evidence missing |
| D205-15-4::AC-7 | D205 Audit Briefing 반영 완료 (ADD-ON #1) ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:dauditbriefingaddon | canonical evidence missing |
| D205-15-4::AC-8 | Gate 3단 PASS (Doctor/Fast/Regression) + DocOps PASS ✅ | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatepassdoctorfastregressiondocopspass | canonical evidence missing; canonical evidence missing |
| D205-15-4::AC-9 | D_ROADMAP 업데이트 + Commit + Push ✅ (Merged into D205-15-2::AC-11) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:droadmapcommitpushmergedintodac | canonical evidence missing; Merged into D205-15-3::AC-8 (dup_key=OTHER:TITLE:droadmapcommitpushmergedintodac) |
| D205-15-5::AC-1 | UniverseConfig SSOT 통합 (core/config.py 유일) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:universeconfigssotcoreconfigpy | canonical evidence missing; canonical evidence missing |
| D205-15-5::AC-2 | 테스트 Shadowing 검증 완료 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:shadowing | canonical evidence missing |
| D205-15-5::AC-3 | 6h Paper Run 하네스 구현 **[D205-15-5b HOTFIX 완료]** | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:hpaperrundbhotfix | canonical evidence missing |
| D205-15-5::AC-4 | Evidence 무결성 보장 **[D205-15-5b HOTFIX 완료]** | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencedbhotfix | canonical evidence missing |
| D205-15-5::AC-5 | 10분 Smoke Paper Run **[에이전트 직접 실행 완료]** | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:smokepaperrun | canonical evidence missing |
| D205-15-5::AC-6 | 10분 Smoke Run 4회 완료 + 근본 원인 분석 **[D205-15-5c/d 디버깅 완료]** | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:smokerundcd | canonical evidence missing |
| D205-15-5::AC-7 | Gate 3단 PASS (Doctor/Fast/Regression) + DocOps PASS (Merged into D205-15-4::AC-8) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatepassdoctorfastregressiondocopspassmergedintodac | canonical evidence missing; canonical evidence missing |
| D205-15-5::AC-8 | D_ROADMAP 업데이트 + Commit + Push (Merged into D205-15-2::AC-11) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:droadmapcommitpushmergedintodac | canonical evidence missing; Merged into D205-15-3::AC-8 (dup_key=OTHER:TITLE:droadmapcommitpushmergedintodac) |
| D205-15-6::AC-1 | RunWatcher 구현 (arbitrage/v2/core/run_watcher.py) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:runwatcherarbitragevcorerunwatcherpy | canonical evidence missing |
| D205-15-6::AC-2 | Evidence Decomposition | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidencedecomposition | canonical evidence missing |
| D205-15-6::AC-3 | Config SSOT화 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:configssot | canonical evidence missing; canonical evidence missing |
| D205-15-6::AC-4 | "시장 vs 로직" 판정 자동화 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:vs | canonical evidence missing |
| D205-15-6::AC-5 | 10분 Smoke 테스트 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:smoke | canonical evidence missing |
| D205-15-6::AC-6 | Gate 3단 PASS (Doctor/Fast/Regression) + DocOps PASS (Merged into D205-15-4::AC-8) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatepassdoctorfastregressiondocopspassmergedintodac | canonical evidence missing; canonical evidence missing; Merged into D205-15-5::AC-7 (dup_key=OTHER:TITLE:gatepassdoctorfastregressiondocopspassmergedintodac) |
| D205-15-6::AC-7 | D_ROADMAP 업데이트 + Commit + Push (Merged into D205-15-2::AC-11) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:droadmapcommitpushmergedintodac | canonical evidence missing; Merged into D205-15-3::AC-8 (dup_key=OTHER:TITLE:droadmapcommitpushmergedintodac) |
| D205-15-6::AC-8 | Closeout Summary (Compare Patch URL 포함) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:closeoutsummarycomparepatchurl | canonical evidence missing |
| D205-15::AC-1 | 멀티심볼 universe 10+ 심볼 (Upbit × Binance 교집합) ✅ SYMBOL_UNIVERSE 12개 정의 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:universeupbitbinancesymboluniverse | canonical evidence missing |
| D205-15::AC-10 | D_ROADMAP 업데이트 + Git commit + push (Merged into D205-14-6::AC-9) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:droadmapgitcommitpushmergedintodac | canonical evidence missing |
| D205-15::AC-2 | 심볼별 10분+ Futures recording 완료 (Evidence Run 필요) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:futuresrecordingevidencerun | canonical evidence missing |
| D205-15::AC-3 | scan_summary.json 생성 (심볼별 spread/edge/positive_rate) ✅ 코드 구현 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:scansummaryjsonspreadedgepositiverate | canonical evidence missing; canonical evidence missing |
| D205-15::AC-4 | TopK(3개) 선정 + 선정 근거 문서화 ✅ Fix-4 적용 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:topk | canonical evidence missing |
| D205-15::AC-5 | TopK별 AutoTune leaderboard 생성 (Evidence Run 필요) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:topkautotuneleaderboardevidencerun | canonical evidence missing |
| D205-15::AC-6 | 최소 1개 심볼에서 mean_net_edge_bps unique >= 2 달성 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:meannetedgebpsunique | canonical evidence missing; canonical evidence missing |
| D205-15::AC-7 | cost_breakdown.json (수수료/슬리피지/환산 분해) ✅ Fix-3 적용 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:costbreakdownjson | canonical evidence missing |
| D205-15::AC-8 | Gate 3단 PASS (Doctor/Fast/Regression) ✅ 2026-01-08 (Merged into D205-14-1::AC-6) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatepassdoctorfastregressionmergedintodac | canonical evidence missing; Merged into D205-14-2::AC-4 (dup_key=OTHER:TITLE:gatepassdoctorfastregressionmergedintodac) |
| D205-15::AC-9 | Evidence 패키징 (Evidence Run 필요) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:evidenceevidencerun | canonical evidence missing |
| D209-1::AC-1 | 429 Rate Limit - throttling 자동 활성화, manual pause 가능 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:ratelimitthrottlingmanualpause | canonical evidence missing |
| D209-1::AC-2 | Timeout - 재시도 로직, timeout 임계치 설정 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:timeouttimeout | canonical evidence missing |
| D209-1::AC-3 | Reject - 주문 거부 시 원인 분석 (insufficient balance, invalid symbol 등) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:rejectinsufficientbalanceinvalidsymbol | canonical evidence missing |
| D209-1::AC-4 | Partial Fill - 부분 체결 시 Fill 기록, 잔여 주문 처리 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:partialfillfill | canonical evidence missing; canonical evidence missing |
| D209-1::AC-5 | 실패 시나리오 테스트 - 각 실패 타입별 테스트 케이스, ExitCode 전파 확인 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:exitcode | canonical evidence missing |
| D209-1::AC-6 | 문서화 - OPS_PROTOCOL.md #8 Failure Modes 갱신 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:opsprotocolmdfailuremodes | canonical evidence missing |
| D209-2::AC-1 | Position Limit - max_position_usd 임계치, 초과 시 신규 주문 차단 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:positionlimitmaxpositionusd | canonical evidence missing |
| D209-2::AC-2 | Loss Cutoff - max_drawdown, max_consecutive_losses 임계치, 초과 시 ExitCode=1 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:losscutoffmaxdrawdownmaxconsecutivelossesexitcode | canonical evidence missing |
| D209-2::AC-3 | Kill-Switch - RiskGuard.stop(reason="RISK_XXX") 호출 시 Graceful Stop | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:killswitchriskguardstopreasonriskxxxgracefulstop | canonical evidence missing |
| D209-2::AC-4 | 리스크 메트릭 - kpi_summary.json에 position_risk, drawdown, consecutive_losses 기록 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:kpisummaryjsonpositionriskdrawdownconsecutivelosses | canonical evidence missing |
| D209-2::AC-5 | 테스트 케이스 - 각 리스크 임계치 초과 시나리오 테스트, ExitCode=1 확인 (Merged into D209-1::AC-5) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:exitcodemergedintodac | canonical evidence missing |
| D209-2::AC-6 | 문서화 - docs/v2/design/RISK_GUARD.md 작성 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:docsvdesignriskguardmd | canonical evidence missing |
| D209-3::AC-1 | Wallclock 이중 검증 - monotonic_elapsed_sec vs 실제 시간 **±5% 이내 검증**, 초과 시 ExitCode=1 (D205-10-2 재사용) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:wallclockmonotonicelapsedsecvsexitcoded | canonical evidence missing |
| D209-3::AC-2 | Heartbeat 정합성 - heartbeat.json 60초 간격 강제, 최대 65초 (OPS Invariant) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:heartbeatheartbeatjsonopsinvariant | canonical evidence missing |
| D209-3::AC-3 | watch_summary.json 자동 생성 - 모든 종료 경로(정상/예외/Ctrl+C)에서 필수 생성, completeness_ratio ≥ 0.95 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:watchsummaryjsonctrlccompletenessratio | canonical evidence missing |
| D209-3::AC-4 | ExitCode 체계 - 정상 종료=0, 비정상 종료=1, 모든 예외 catch | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:exitcodecatch | canonical evidence missing |
| D209-3::AC-5 | stop_reason 체계 - watch_summary.json에 stop_reason 필드 ("TIME_REACHED", "EARLY_INFEASIBLE", "ERROR", "INTERRUPTED") | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:stopreasonwatchsummaryjsonstopreasontimereachedearlyinfeasibleerrorinterrupted | canonical evidence missing |
| D209-3::AC-6 | 예외 핸들러 일원화 + Fail-Fast 전파 - Orchestrator.run() 최상위 try/except, clean exit, 하위 모듈 예외 즉시 전파 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:failfastorchestratorruntryexceptcleanexit | canonical evidence missing |
| D210-1::AC-1 | LIVE 아키텍처 - `docs/v2/design/LIVE_ARCHITECTURE.md` 작성 (order_submit 실제 호출 시나리오) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:livedocsvdesignlivearchitecturemdordersubmit | canonical evidence missing |
| D210-1::AC-1-2 | OBI Calculator 구현 - `arbitrage/v2/alpha/obi_calculator.py` 신규 생성, Static OBI / VAMP / Weighted-Depth 3종 계산 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:obicalculatorarbitragevalphaobicalculatorpystaticobivampweighteddepth | canonical evidence missing |
| D210-1::AC-2 | Allowlist 정의 - LIVE 진입 허용 조건 명시 (D209 완료, 수익성 증명, Gate 100% PASS) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:allowlistlivedgatepass | canonical evidence missing |
| D210-1::AC-2-2 | Order Book Depth 수집 - Binance/Upbit WebSocket에서 Depth 데이터 수집 (최소 Level 5), `arbitrage/v2/marketdata/ws/` 확장 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:orderbookdepthbinanceupbitwebsocketdepthlevelarbitragevmarketdataws | canonical evidence missing |
| D210-1::AC-3 | 증거 규격 - LIVE 실행 시 요구되는 Evidence 파일 목록 (manifest, kpi_summary, trade_log 등) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:liveevidencemanifestkpisummarytradelog | canonical evidence missing |
| D210-1::AC-3-2 | OBI 기반 Entry Signal 통합 - OpportunitySource에 OBI 조건 추가 (Spread > threshold AND OBI > 0.2), Hybrid Entry 로직 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:obientrysignalopportunitysourceobispreadthresholdandobihybridentry | canonical evidence missing; canonical evidence missing |
| D210-1::AC-4 | DONE 판정 기준 - LIVE 단계 DONE 조건 명시 (실거래 20분, net_pnl > 0, 0 실패) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:donelivedonenetpnl | canonical evidence missing; canonical evidence missing |
| D210-1::AC-4-2 | Paper 실행 검증 - OBI 활성화 vs 비활성화 20분 Paper 실행, net_pnl 비교 (최소 +10% 개선) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:paperobivspapernetpnl | canonical evidence missing; canonical evidence missing |
| D210-1::AC-5 | 리스크 경고 - LIVE 리스크 시나리오 명시 (자금 손실, API 제한, 거래소 정책 변경 등) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:liveapi | canonical evidence missing |
| D210-1::AC-5-2 | Backtesting 결과 - 20시간 히스토리 데이터 백테스트, Return per Trade 비교 (OBI 활성화 시 +15% 이상) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:backtestingreturnpertradeobi | canonical evidence missing |
| D210-1::AC-6 | 문서 검토 - LIVE_ARCHITECTURE.md에 대한 CTO/리드 검토 필수 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:livearchitecturemdcto | canonical evidence missing |
| D210-1::AC-6-2 | 문서화 - `docs/v2/design/OBI_ALPHA_MODEL.md` 작성, 수학적 근거 + 실험 결과 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:docsvdesignobialphamodelmd | canonical evidence missing |
| D210-2::AC-1 | 잠금 메커니즘 - LiveAdapter.submit_order()에 allowlist 검사, 허가 없으면 ExitCode=1 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:liveadaptersubmitorderallowlistexitcode | canonical evidence missing |
| D210-2::AC-1-2 | Reservation Price 계산 - | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:reservationprice | canonical evidence missing |
| D210-2::AC-2 | ExitCode 강제 - LIVE 미허가 진입 시 ExitCode=1, stop_reason="LIVE_NOT_ALLOWED" | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:exitcodeliveexitcodestopreasonlivenotallowed | canonical evidence missing |
| D210-2::AC-2-2 | Optimal Spread 계산 - δ = γ  σ  (T - t) + 2/γ  ln(1 + γ/κ) 구현, Volatility + Liquidity 반영 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:optimalspreadttlnvolatilityliquidity | canonical evidence missing; canonical evidence missing |
| D210-2::AC-3 | 증거 검증 - LIVE 실행 시 Evidence 파일 검증 규칙 (필수 필드, 스키마 일치) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:liveevidence | canonical evidence missing |
| D210-2::AC-3-2 | Inventory Tracker 구현 - rbitrage/v2/core/inventory_tracker.py 신규, 현재 포지션 실시간 추적 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:inventorytrackerrbitragevcoreinventorytrackerpy | canonical evidence missing |
| D210-2::AC-4 | Gate 스크립트 설계 - `scripts/check_live_gate.py` 설계 (실제 구현은 별도 D-step) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatescriptschecklivegatepydstep | canonical evidence missing |
| D210-2::AC-4-2 | Volatility Estimator 구현 - Rolling Window (60분) 기반 σ 계산 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:volatilityestimatorrollingwindow | canonical evidence missing |
| D210-2::AC-5 | 테스트 케이스 설계 - LIVE 잠금 테스트 시나리오 명시 (미허가 진입 FAIL 확인) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:livefail | canonical evidence missing |
| D210-2::AC-5-2 | Paper 실행 검증 - A-S 모델 활성화 Paper 20분 실행, Inventory Risk 제어 확인 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:paperaspaperinventoryrisk | canonical evidence missing |
| D210-2::AC-6 | 문서화 - `docs/v2/LIVE_GATE_DESIGN.md` 작성 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:docsvlivegatedesignmd | canonical evidence missing |
| D210-2::AC-6-2 | 문서화 - docs/v2/design/AVELLANEDA_STOIKOV_MODEL.md 작성 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:docsvdesignavellanedastoikovmodelmd | canonical evidence missing |
| D210-3::AC-1 | 잠금 테스트 - LiveAdapter.submit_order() 호출 시 ExitCode=1 확인 (allowlist 미등록 상태) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:liveadaptersubmitorderexitcodeallowlist | canonical evidence missing |
| D210-3::AC-1-2 | Position Imbalance 모니터링 - q (Inventory deviation) 실시간 계산 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:positionimbalanceqinventorydeviation | canonical evidence missing |
| D210-3::AC-2 | 우회 방지 - LiveAdapter 이외의 실거래 경로 0개 증명 (ripgrep 검색) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:liveadapterripgrep | canonical evidence missing |
| D210-3::AC-2-2 | Risk-adjusted Spread 적용 - Reservation Price 기반 주문 생성 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:riskadjustedspreadreservationprice | canonical evidence missing; canonical evidence missing |
| D210-3::AC-3 | 문서 일치 - LIVE_GATE_DESIGN.md와 실제 잠금 동작 일치 확인 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:livegatedesignmd | canonical evidence missing |
| D210-3::AC-3-2 | Max Inventory 임계치 - max_inventory_usd 초과 시 신규 주문 차단 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:maxinventorymaxinventoryusd | canonical evidence missing |
| D210-3::AC-4 | Gate 검증 - check_live_gate.py 실행 시 LIVE 미허가 상태 FAIL 확인 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatechecklivegatepylivefail | canonical evidence missing |
| D210-3::AC-4-2 | Inventory Decay 시뮬레이션 - 포지션 청산 시나리오 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:inventorydecay | canonical evidence missing |
| D210-3::AC-5 | 회귀 테스트 - Gate Doctor/Fast/Regression 100% PASS (LIVE 잠금 유지) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:gatedoctorfastregressionpasslive | canonical evidence missing |
| D210-3::AC-5-2 | Paper 실행 검증 - Max Inventory 임계치 테스트 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:papermaxinventory | canonical evidence missing |
| D210-3::AC-6 | 증거 문서 - `docs/v2/reports/D210/D210-3_LIVE_SEAL_VERIFICATION.md` 작성 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:docsvreportsddlivesealverificationmd | canonical evidence missing |
| D210-3::AC-6-2 | 문서화 - docs/v2/design/INVENTORY_RISK_MANAGEMENT.md | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:docsvdesigninventoryriskmanagementmd | canonical evidence missing |
| D210-4::AC-1 | Baseline vs OBI vs A-S 수익성 비교 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:baselinevsobivsas | canonical evidence missing |
| D210-4::AC-2 | Sharpe Ratio, Max Drawdown 비교 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:sharperatiomaxdrawdown | canonical evidence missing |
| D210-4::AC-3 | Market Condition별 성능 분석 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:marketcondition | canonical evidence missing |
| D210-4::AC-4 | 최적 알파 모델 조합 결정 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:최적 알파 모델 조합 결정 | canonical evidence missing |
| D210-4::AC-5 | 장기 Paper 실행 (1시간) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:paper | canonical evidence missing |
| D210-4::AC-6 | 문서화 - Benchmark Report | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:benchmarkreport | canonical evidence missing |
| D211-1::AC-1 | 과거 데이터 수집 스크립트 - 최소 1개월 (720시간) 히스토리 데이터 수집 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:과거 데이터 수집 스크립트 - 최소 1개월 (720시간) 히스토리 데이터 수집 | canonical evidence missing |
| D211-1::AC-2 | 데이터 정규화 - 통일 스키마, Parquet 또는 PostgreSQL 저장 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:parquetpostgresql | canonical evidence missing |
| D211-1::AC-3 | 데이터 품질 검증 - 누락 < 1%, 중복 제거, 이상치 탐지 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:데이터 품질 검증 - 누락 < 1%, 중복 제거, 이상치 탐지 | canonical evidence missing |
| D211-1::AC-4 | 데이터 저장소 구현 - rbitrage/v2/data/historical_storage.py | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:rbitragevdatahistoricalstoragepy | canonical evidence missing |
| D211-1::AC-5 | 데이터 메타데이터 - manifest.json 기록 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:manifestjson | canonical evidence missing |
| D211-1::AC-6 | 문서화 - docs/v2/design/HISTORICAL_DATA_SPEC.md | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:docsvdesignhistoricaldataspecmd | canonical evidence missing |
| D211-2::AC-1 | Replay MarketDataProvider - 히스토리 데이터 순차 재생 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:replaymarketdataprovider | canonical evidence missing |
| D211-2::AC-2 | Simulated Execution - Slippage/Latency/Partial Fill 모델 적용 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:simulatedexecutionslippagelatencypartialfill | canonical evidence missing; canonical evidence missing |
| D211-2::AC-3 | Orchestrator Replay 모드 - mode='replay' 추가 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:orchestratorreplaymodereplay | canonical evidence missing |
| D211-2::AC-4 | Backtesting 결과 저장 - manifest.json, kpi_summary.json, trades.jsonl | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:backtestingmanifestjsonkpisummaryjsontradesjsonl | canonical evidence missing |
| D211-2::AC-5 | Backtesting 검증 - 20시간 데이터 백테스트 실행 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:backtesting | canonical evidence missing |
| D211-2::AC-6 | 문서화 - docs/v2/design/BACKTESTING_ENGINE.md | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:docsvdesignbacktestingenginemd | canonical evidence missing |
| D211-3::AC-1 | Bayesian Optimizer 통합 - 50~100회 Iteration | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:bayesianoptimizeriteration | canonical evidence missing |
| D211-3::AC-2 | Objective Function 정의 - Sharpe Ratio 최대화 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:objectivefunctionsharperatio | canonical evidence missing |
| D211-3::AC-3 | Pareto Frontier 시각화 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:paretofrontier | canonical evidence missing |
| D211-3::AC-4 | 최적 파라미터 자동 추출 - optimal_params.json | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:optimalparamsjson | canonical evidence missing |
| D211-3::AC-5 | Parameter Sweep 검증 - Out-of-Sample 백테스트 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:parametersweepoutofsample | canonical evidence missing |
| D211-3::AC-6 | 문서화 - Sweep Report | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:sweepreport | canonical evidence missing |
| D211-4::AC-1 | Train/Test Period 분할 - 60%/40% 분할 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:traintestperiod | canonical evidence missing |
| D211-4::AC-2 | Train Period 최적화 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:trainperiod | canonical evidence missing |
| D211-4::AC-3 | Test Period Out-of-Sample 검증 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:testperiodoutofsample | canonical evidence missing |
| D211-4::AC-4 | Overfitting 감지 - 차이 < 10% 확인 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:overfitting | canonical evidence missing |
| D211-4::AC-5 | Walk-Forward 실행 - Rolling Window | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:walkforwardrollingwindow | canonical evidence missing |
| D211-4::AC-6 | 문서화 - Walk-Forward Report | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:walkforwardreport | canonical evidence missing |
| D212-1::AC-1 | Symbol별 독립 OpportunitySource | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:symbolopportunitysource | canonical evidence missing |
| D212-1::AC-2 | Symbol별 독립 Executor | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:symbolexecutor | canonical evidence missing |
| D212-1::AC-3 | Global Risk Aggregation | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:globalriskaggregation | canonical evidence missing |
| D212-1::AC-4 | Symbol별 KPI 분리 저장 | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:symbolkpi | canonical evidence missing |
| D212-1::AC-5 | Multi-Symbol Paper 실행 (3개 심볼 20분) | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:multisymbolpaper | canonical evidence missing |
| D212-1::AC-6 | 문서화 - Multi-Symbol Architecture | OTHER | OPEN | NONE | UNKNOWN | OTHER:TITLE:multisymbolarchitecture | canonical evidence missing |
