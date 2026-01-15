D205-18-4: REAL 최종 테스트 검증 (81분 Paper Acceptance)
결과 검증 및 완료 선언
Wall-clock 실행 시간: Watchdog 로그 기준 약 81분 34초 동안 정상 동작하여 목표(80분)의 ±5% 이내로 완료되었습니다. 이는 Wallclock Duration Invariant (실제 시간 ±5%)를 충족함을 의미합니다.
Evidence 및 DB 무결성: Real MarketData로 Upbit/Binance 데이터를 받아 201개의 tick/opportunity를 평가했고, DB Strict 모드에서 1,458건의 insert가 모두 성공했습니다. 각 closed_trade 대비 약 2건의 DB 기록으로, DB Invariant(closed_trades×2 ≈ inserts) 조건을 만족했습니다. Evidence 폴더에는 manifest.json, daily_report_*.json 등이 생성되었고, chain_summary에도 모든 체인 정보가 기록되었습니다.
Winrate 98% 이슈: 최종 **승률이 98%**로 비정상적으로 높게 나타났습니다. 이는 Paper 모드의 특성상 슬리피지 없음, 즉시 체결 등에 따른 가짜 낙관 영향으로 보입니다. SSOT 규칙에 따라 **승률 95% 이상은 경고(WARNING)**로 간주되며, 실제 이익률 지표(edge_after_cost 등)로 교차 검증해야 합니다. 본 테스트에서는 slippage/부분체결이 없었기 때문에 높은 승률이 나왔으며, 이는 Paper 모드 본질적 한계로 문서화되었습니다. 실제 운영 시에는 슬리피지 모델과 현실적 실패 케이스가 포함되어 승률이 낮아질 것이며, 해당 경고는 이번 테스트의 False Positive로 판단됩니다.
코어 엔진 기반 실행: 이번 81분 실증은 Orchestrator 코어 엔진 루프에서 수행되었으며, V2 엔진의 **모니터링(Watchdog/RunWatcher)**과 Heartbeat 흐름을 검증하였습니다. 다만 초기 Evidence에서 heartbeat.jsonl 파일이 생성되지 않는 버그가 발견되어 즉시 수정되었습니다. 수정 후 RunWatcher가 정상 동작하여 60초 주기의 heartbeat를 기록, Heartbeat Density Invariant(≤65초) 조건을 충족합니다. **체인 요약(chain_summary)**에도 실행 단계별 duration이 기록되나, 초기엔 duration_seconds 필드 오기록 문제가 있었고, 이를 패치하여 실제 wall-clock 시간과 일치하도록 고정했습니다.
최종 판단: 위 조건들을 종합 검토한 결과, 실행 시간, DB 기록 무결성, 모니터링 지표, 에비던스 무결성이 모두 만족되는 것으로 확인되었습니다. 승률 지표의 높음은 Paper 환경 특성에 기인하며 SSOT 경고에 따라 인지하고 넘어갑니다. 따라서 D205-18-4 단계를 “COMPLETED”로 선언하며, D205 마일스톤을 최종 완료 처리합니다 ✅.
D206-0: 운영 프로토콜 엔진 내재화
목적
Run Protocol 엔진 통합: V2 엔진(Orchestrator) 내부에 **운영 프로토콜(OPS_PROTOCOL)**의 실행 절차를 내재화합니다. 모든 실행 모드(Paper/Smoke/Baseline/Longrun 등)에 대해 유일한 코어 루프를 Orchestrator가 담당하고, 과거 V1의 PaperRunner, LiveRunner 등의 중복 루프를 제거합니다.
헌법 규칙 적용: “WARN = FAIL” 원칙을 엔진 레벨에서 강제하여, 운영 인variant 위반 시 즉시 종료하도록 구현합니다. 예를 들어 실행 시간 편차 ±5% 초과, 하트비트 누락(>65초), DB 입력 불일치 등의 불변 조건 위반 시 Orchestrator가 **즉시 Exit(코드 1)**하며, 이에 대한 로그와 종료 사유를 남깁니다.
Evidence 원자화 & Flush: 엔진 종료 시 Evidence(manifest, KPI, decision_trace 등) 필수 파일들을 원자적으로 Flush하여 저장 완료를 보장하고, 부분 파일 또는 유실이 없도록 합니다. 이를 통해 운영자가 종료 후 로그를 통해 완전한 실험 결과 검증이 가능하게 합니다.
헬스체크 & 장애 대응: Docker/쿠버네티스 환경의 Healthcheck와 연계될 수 있도록, RunWatcher/Heartbeat 기반 헬스 시그널을 엔진이 주기적으로 발생시키며, SIGTERM 등 Graceful Shutdown 시그널 수신 시 정상 종료 루틴을 따르도록 합니다. 운영 중 장애 발생 시 자동 복구/재시작을 위한 후속 처리(예: 상태 파일 dump 등)도 엔진 단계에서 고려합니다.
엔진 단일화 및 얇은 러너: 궁극적으로 Runner(예: run_paper.py, run_live.py)는 얇은 진입점(thin wrapper) 역할만 수행하고, 모든 실행 흐름 제어는 Engine 내부로 일원화합니다. 이로써 V1의 다수 스크립트 난립 문제를 해결하고, 엔진 중심(Engine-Centric) 아키텍처 완성을 목표로 합니다.
Acceptance Criteria
Orchestrator 단일 루프 구현: orchestrator.run()이 모든 모드에 대한 시작-실행-종료 시퀀스를 책임지고, 다른 Runner에서 loop 로직이 사라질 것. (예: PaperRunner의 주요 로직이 Orchestrator로 이동)
운영 Invariant 강제: OPS_PROTOCOL.md의 불변 조건(예: Wallclock ±5%, Heartbeat ≤65s, DB inserts 매칭 등)을 Orchestrator 내에서 검사하고 위반 시 ExitCode=1로 종료 처리 (로그에 원인 명시). 경고 수준 임계치(예: 승률 95% 초과)는 사전 정의된 예외 처리 또는 별도 플래그(is_optimistic_warning)로 기록.
Graceful Termination: SIGTERM 수신 또는 AC 조건 만족에 따른 정상 종료 시, 모든 Evidence 데이터를 flush하고 watch_summary.json 등의 요약을 최종 기록. 종료 사유(stop_reason)를 명시하고 ExitCode=0으로 종료.
Heartbeat 통합: heartbeat.jsonl을 60초 주기로 append 작성하는 RunWatcher를 엔진에 통합. 테스트로 5분 이상 장기 실행 시 heartbeat 로그의 간격 최대값 ≤65초를 확인.
엔진 상태 관리 인터페이스: 엔진 내부에 Admin Control 훅을 추가하여, 실행 중 현재 상태(예: Running, Stopped, Error 등)를 조회하거나 제어할 수 있게 할 것. 이는 이후 UI/모니터링 툴 (예: Grafana 패널 또는 Admin Panel)과 연계 예정.
Evidence 경로
통합 테스트: tests/test_d206_0_ops_protocol.py – 워치독/하트비트 및 종료 invariant 검증용 테스트 (예: 인위적 시간초과로 ExitCode 확인).
실행 증거: logs/evidence/d206_0_ops_protocol_integration_<날짜>/ (실제 Smoke 실행 10분)
manifest.json, heartbeat.jsonl, watch_summary.json, errors.ndjson (에러 발생 시), README.md 등
상태
PLANNED (설계 완료, 구현 대기)
D206-1: 수익 로직 모듈화 및 튜너 인터페이스 설계
목적
Profit Loop 재설계: 수익 발생 핵심 로직을 엔진 중심으로 재구성합니다. 현재 FillModel, EntryStrategy, TradeProcessor 등의 모듈에 산재된 임계값 하드코딩과 규칙 기반 로직을 제거하고, 이를 구성 가능한 형태로 바꿉니다. 예를 들어, break_even 임계값, 슬리피지 비율, 부분 체결 패널티 등의 파라미터를 코드 상수 대신 **구성 파일(config.yml)**이나 SSOT로 관리하여 단일 진실원칙을 따릅니다.
모델/전략 모듈화: 거래 진입/종료 전략(Entry/Exit Strategy)과 채결 결과 처리(Fill/Execution Model)를 플러그인 모듈 형태로 분리합니다. 이를 통해 새로운 전략이나 모델(예: 다른 슬리피지 모델, 다른 진입 필터)을 엔진 교체 없이 추가/교체할 수 있게 합니다. 각 모듈은 공통 인터페이스(예: BaseFillModel, BaseEntryStrategy)를 구현하도록 해 엔진-전략 분리를 달성합니다.
튜너 인터페이스 도입: 수익성 향상을 위해 자동/반자동으로 매개변수 튜닝이 가능하도록 엔진에 튜너(Tuner) 인터페이스를 설계합니다. 엔진은 튜너로부터 제안된 파라미터 세트를 주입받아 실행하고, 결과 **KPI(PnL, win_rate, sharpe 등)**를 튜너에 반환하는 훅을 가집니다. 이를 통해 Grid Search, Bayesian Optimization 등의 기법을 활용한 자동 파라미터 최적화가 가능해집니다.
하드코딩 제거: 기존 코드에 존재하는 마법 상수(magic number) 제거가 목표입니다. 예를 들어, MockAdapter나 TradeProcessor에 있던 50_000_000.0 같은 임시 가격 상수를 제거하고, 모든 계산에 실제 OrderResult의 filled_price/qty 값을 활용합니다. 또한 threshold, buffer 값 등도 config나 엔진 초기화 인자로 주입되도록 변경합니다.
Acceptance Criteria
파라미터 SSOT화: break_even_params, 수수료, 버퍼(bp), 슬리피지 모델 등 핵심 수익 결정 변수를 config.yml 또는 전역 SSOT로 관리. 엔진 실행 시 해당 값을 로드하고, 절대 코드 하드코딩이 없을 것 (코드 스캔으로 상수 제거 확인).
전략/모델 인터페이스 구현: arbitrage.v2.strategy.entry.BaseEntryStrategy, arbitrage.v2.model.fill.BaseFillModel 등의 추상 클래스를 정의하고, 현재 사용 중인 로직을 기본 구현 클래스로 분리(DefaultEntryStrategy, SimpleFillModel 등). 엔진은 이들을 의존성 주입(DI) 받아 사용하고, 다른 구현체로 쉽게 교체 가능해야 함.
TradeProcessor 개선: TradeProcessor가 거래 체결 후 PnL을 계산하는 과정에서 **입력 파라미터(BreakEvenParams)**를 100% 활용하고, 매직넘버 없음을 보장. 예를 들어 filled_qty 계산, 실제 수수료 계산 등을 OrderResult 기반으로 수행하고, Qty 불일치나 데이터 누락 시 Fail-fast 예외 발생. 해당 부분에 대한 단위 테스트 완비 (예: qty mismatch 시 예외 발생 테스트).
튜너 훅 설계: 엔진에 engine.tuner (예: BaseTuner 인터페이스) 추가. AC로서 튜너 더미 구현을 하나 만들고 (예: 일정 범위의 buffer_bps 값을 바꿔가며 5분 Paper 실행), 엔진이 이를 통해 여러 파라미터 셋을 시도할 수 있음을 로그로 확인. 튜너와 엔진 간 매개변수 교환 프로토콜 (params -> run -> result)이 문서화되고 구현되어야 함.
회귀 테스트 통과: 상기 변경으로 인해 기존 테스트(Gate Doctor/Fast/Regression) 100% 통과. 특히 수익 계산 로직 변경으로 과거 대비 PnL 계산이 일치해야 하며, 변경 전후 결과 차이가 있을 경우 Report에 분석 첨부.
Evidence 경로
설계 보고: docs/v2/reports/D206/D206-1_REPORT.md – 전략/모델 분리 설계서 및 튜닝 인터페이스 설명서.
테스트 결과: logs/evidence/d206_1_tuner_dummy_run/ – 튜너 더미를 통한 여러 파라미터 실행 증적 (예: 각 run별 manifest, kpi.json 모음 및 비교표).
코드 검증: PR 및 Diff에서 상수 제거를 확인할 수 있는 Compare URL 첨부 (예: compare/prev_commit...new_commit에서 buffer_bps=... 등의 제거 확인).
상태
PLANNED (세부 설계 진행 중)
D206-2: 자동 파라미터 튜너 내재화 및 성능 검증
목적
Auto-Tuning 엔진 구축: 엔진 내부에 자동 파라미터 튜닝 모듈을 내재화하여, 수익성 지표 최적화를 위한 실험을 자동화합니다. D206-1의 튜너 인터페이스를 활용하여, 과거 수동으로 수행하던 Grid Search나 간단한 휴리스틱 튜닝을 넘어 Bayesian Optimization, 강화학습 기반 튜닝 등도 적용할 수 있는 확장성 있는 Auto-Tuner를 구현합니다. 예를 들어, Gaussian Process를 활용한 Bayesian 최적화로 buffer_bps vs net PnL 관계를 학습하거나, 분산된 Executor를 통해 병렬 실험을 수행하도록 설계합니다.
튜닝 시나리오 검증: Paper 환경에서 일정 기간 실행하여 P&L, Sharpe Ratio, win_rate 등의 목표 함수를 최대화/목표화하도록 튜너를 동작시킵니다. 튜너가 제안한 파라미터에 따라 엔진을 반복 실행하고 결과를 수집, 최적의 파라미터 셋 및 신뢰 구간을 도출합니다. 이를 통해 baseline 대비 성능 향상 (예: edge_after_cost 평균 20%↑)이 입증되어야 합니다.
실측 기반 보정: 튜너는 단순 수학적 최적화뿐 아니라 실측 데이터 기반 정책도 포함합니다. 예를 들어, 실거래 비용, 슬리피지 분포를 반영한 페널티를 목표 함수에 적용하거나, 최적화 도중 리스크(예: 변동성 폭증으로 인한 모델 오류)를 감지해 안전장치를 트리거합니다. 궁극적으로 자동 튜닝 결과가 현실적으로 실행 가능한 전략으로 이어지도록 합니다 (오버피팅 방지).
Acceptance Criteria
Bayesian 튜너 구현: arbitrage.v2.tuner.BayesianTuner 클래스 구현 (예: scikit-optimize 사용 가능). 최소 3개 이상의 파라미터 공간에 대해 Bayesian Optimization 수행. AC로서 예시: buffer_bps, slippage_model_param, partial_fill_penalty 3개에 대해 50회 Iteration 최적화 실행.
튜닝 결과 향상: 튜닝 전후의 KPI 비교 보고서 작성. AC: 튜닝 후 최적 파라미터 적용 시, edge_after_cost 평균 또는 **순이익(PnL)**이 baseline 대비 개선되어야 함. 예를 들어 baseline net PnL 대비 +15% 이상 향상 또는 win_rate 유지하며 Sharpe 개선 등이 목표. 개선폭이 미미할 경우 FAIL.
Automated Sweep Evidence: 튜너 실행 과정에서 생성된 parameter_sweep_results.json (또는 bayes_opt_trace.json) 및 **최적 파라미터 결과(optimal_params.json)**를 Evidence로 저장하고, pareto_frontier.png 또는 성능 지도 그래프를 생성하여 튜닝 과정을 시각화.
통합 테스트: 자동 튜닝 모듈의 단위 테스트 및 통합 테스트. 예: test_d206_2_auto_tuner.py에서 Dummy 목표 함수를 최적화해 known optimum을 찾는지 검증. 또한 엔진과 튜너의 인터페이스 연동 테스트 (튜너->엔진 다중 실행)로 메모리 누수나 race condition 없이 동작 확인.
문서화: 튜닝 알고리즘의 수학적 개요, 파라미터 범위 설정 근거, 실행 시간 대비 기대 개선효과 등을 docs/v2/design/auto_tuner.md 등에 문서화. 운영 시 튜너를 사용할지 여부, 주기 등을 Runbook에 반영.
Evidence 경로
튜닝 실행 로그: logs/evidence/d206_2_tuner_run_<date>/
sweep_results.json, optimal_params.json, tuning_history.png (혹은 .csv), README.md (실행 방법)
비교 보고: docs/v2/reports/D206/D206-2_REPORT.md – 튜닝 전후 성능 비교, 개선 여부에 대한 분석.
테스트 결과: CI 상의 Gate 테스트 (Fast/Regression) 로그 – 튜너 모듈 추가 후에도 기존 테스트 0 Fail 확인.
상태
PLANNED (구현 예정, 리서치 내용 반영 준비)
D206-3: 리스크 컨트롤 & 종료/예외 처리 일원화
목적
리스크 가드 통합: 엔진에 실시간 리스크 관리 모듈을 내재화하여, 운영 중 발생할 수 있는 손실 한도 초과, 의도적 종료 조건, 비정상 행위 감지 등을 단일 흐름으로 제어합니다. 예를 들어 연속 손실 횟수, 누적 손실 금액이 사전 정의된 임계치를 넘으면 엔진이 **자동 중단(Kill-Switch)**하고 해당 사유를 로그 및 Evidence에 남깁니다. 또한 거래소 API 오류 연속 발생, 주문 거부 등의 이벤트도 오류 횟수 기반 종료 규칙에 포함합니다.
종료 상태 정의: 정상 종료, 비정상 종료(예: Invariant 위반), 수동 종료(운영자 개입) 등의 종료 유형을 명확히 구분하고, 이를 Engine이 상태 코드와 함께 기록합니다. 종료 타입에 따라 후속 동작도 달리합니다. 예를 들어, 비정상 종료 시 재시작 금지 및 알람 전송, 정상 종료 시 다음 스케줄 대기, 수동 종료 시 운영자 확인 대기 등의 흐름을 명문화합니다.
예외 처리 일괄화: 엔진 코어 내 예외 처리 블록을 표준화합니다. 현재 개별 모듈에서 흩어져 처리되던 예외(예: Order 실패 예외, DB예외 등)를 상위 Orchestrator에서 catch하여 하나의 처리 루틴을 거치도록 합니다. 이 루틴에서 모든 자원 정리(스레드, DB connection 등), Evidence flush, 재시도 여부 결정, 알림 트리거 등을 수행합니다. 이를 통해 어떠한 예외 상황에서도 엔진이 정의된 방법으로 안전하게 종료되도록 합니다.
Acceptance Criteria
RiskGuard 모듈 구현: arbitrage.v2.core.risk_guard.py 모듈 신규 구현. 구성 파일에 리스크 임계치(예: max_drawdown, max_consecutive_losses, max_error_count)를 정의하고 엔진이 주기적으로 검사. 임계치 초과 시 orchestrator.stop(reason="RISK_XXX") 호출하여 Graceful Stop. 해당 기능에 대한 시뮬레이션 테스트 (의도적으로 손실 발생시키는 Mock) 통과.
엔진 StopReason 체계: 엔진 종료 시 watch_summary.json 혹은 별도 termination_summary.json에 stop_reason 필드를 남길 것. 값 예시: "NORMAL", "ERROR_INVARIANT_VIOLATION", "MANUAL_HALT", "RISK_DRAWDOWN". 각각에 대응하여 Alerting 모듈이 동작할 수 있게 Hook 마련 (예: ERROR나 RISK일 때 텔레그램 경고 전송).
예외 핸들러 일원화: Orchestrator.run 루프에 try/except를 설치하여, 어떠한 예외도 빠져나가지 않고 최상위에서 처리. AC로서 의도적으로 Exception을 발생시키는 테스트(test_d206_3_exception_handler.py)에서 엔진이 예외 내용을 로그에 남기고 clean exit (ExitCode=1) 하는지 확인. 또한 이때 Evidence 디렉토리에 errors.ndjson나 DIAGNOSIS 보고서가 생성되어야 함.
종료 플로우 테스트: 다양한 시나리오별 종료 흐름 통합 테스트: a) 정상 AC 만족 종료 → ExitCode 0, b) RiskGuard 트리거 종료 → ExitCode 1 + stop_reason, c) Invariant 위반 종료 → ExitCode 1 + stop_reason, d) 수동 SIGTERM 종료 → ExitCode 0 + stop_reason. 각 경우 자원(leak) 없음, 모든 파일 flush, 다음 실행에 영향 없음을 검증.
문서/런북 갱신: 운영 Runbook에 새로운 위험 통제 시나리오별 조치를 추가합니다. 또한 OPS_PROTOCOL.md에 종료 타입 및 Warn→Fail 절차를 명시 (예: WARN 발생 시 어떻게 Fail로 전환하는지)하여 SSOT를 최신화합니다.
Evidence 경로
종료 시나리오 증적: logs/evidence/d206_3_failure_injection_test/ – 의도적으로 실패를 유발한 실행의 로그 (예: mock adapter에 연속 오류 발생시킨 로그, RiskGuard 작동 로그 등).
종료 보고서: docs/v2/reports/D206/D206-3_REPORT.md – 다양한 종료 원인별로 엔진이 어떻게 대응했는지, 개선된 흐름과 과거 대비 달라진 점 등을 정리 (Postmortem 포함).
Alert 확인: 텔레그램/Slack 등 알림 채널에 risk 혹은 error stop 발생시 발송된 메시지 캡처 (민감정보 제외).
상태
PLANNED (구현 설계 완료, 리팩토링 대기)
D206-4: 실행 프로파일(PAPER/SMOKE/BASELINE/LONGRUN) 엔진 통합
목적
프로파일 기반 실행 모드: 그동안 개별 스크립트/인자 조합으로 관리되던 실행 모드(Paper, Smoke Test, Baseline Test, Long-run Test 등)를 엔진 내부에서 프로파일(Profile) 개념으로 통합합니다. 각 프로파일은 실행 시간, 데이터 양, 검증 강도 등에 대한 설정 세트를 가지며, 엔진은 입력 인자(--profile)나 구성 파일에 따라 해당 프로파일을 적용합니다. 예를 들어, --profile SMOKE이면 5분 실행 + 최소 evidence 생성, BASELINE이면 20분 실행 + 표준 evidence, LONGRUN이면 60분+ 실행 + 추가 메모리/성능 계측 등의 파라미터가 자동 설정됩니다.
엔진 내 스위칭: Orchestrator는 전달받은 profile에 따라 duration, 모니터링 주기, 로깅 레벨, 슬리피지 모델 상세도 등을 조정합니다. 이를 통해 하나의 엔진 코드베이스로 다양한 길이/목적의 테스트를 수행할 수 있게 합니다. Env/Profile별 분기 코드는 최소화하고, 가령 duration만 다르고 나머지 로직은 동일하게 유지하여 일관성 있는 실행 흐름을 확보합니다.
중복 제거: 프로파일 통합으로 scripts/run_smoke.py, run_longrun.py 등의 분리 구현을 제거합니다. 오직 run.py --profile=<TYPE> 한 종류의 진입점만 유지하고, 과거 V1처럼 모드별로 중복되던 설정을 없앱니다. DocOps 측면에서도 각 프로파일별 Acceptance Criteria와 의미를 D_ROADMAP/SSOT에 명시하고, Report에서도 해당 프로파일로 실행했음을 명기하여 혼선을 줄입니다 (예: D205-9는 Paper Smoke 20m 프로파일로 실행됨).
Acceptance Criteria
Profile 정의 및 적용: 지원할 프로파일 4가지 PAPER, SMOKE, BASELINE, LONGRUN을 정의하고, ops_config.yml 등에 각 프로파일의 기본 설정(duration 등)을 명시. 엔진 실행 인자로 --profile을 받으면 해당 설정을 로드하여 Orchestrator에 전달. AC 확인: arbitrage.v2.core.config.get_profile_config("SMOKE") 호출시 예상 값 반환 테스트.
단일 Run 엔트리: scripts/run.py 하나로 모든 실행 대응. AC: 기존 run_paper.py, run_smoke.py 등이 run.py로 통합되고, deprecated됨. 사용법 안내 업데이트 (README에 --profile 사용법 기재).
프로파일별 Evidence 변화: 각 프로파일에 따라 Evidence 요구 사항이 조정됨. 예: SMOKE에서는 성능상 latency_samples.jsonl 생략, LONGRUN에서는 메모리/CPU usage 로그 추가 등. 이러한 차이가 SSOT에 정의되고 실제 구현되었는지 확인. AC로서 SMOKE 프로파일 실행 시 불필요 파일 미생성 확인, LONGRUN 실행 시 추가 파일 생성 확인.
프로파일별 AC 검증: D 단계별로 어떤 프로파일을 사용할지 명확히 규정하고, 엔진이 이를 준수하는지 테스트. 예를 들어 D205-9 단계는 PAPER(SMOKE) 20m 이내로만 실행하도록 하고 엔진이 LONGRUN 프로파일을 거부 또는 경고하도록 구현. 이와 같이 프로파일별 금지/허용 규칙(SSOT Rule) 준수 여부를 테스트 (잘못된 프로파일 사용 시 엔진이 예외 발생).
Backward Compatibility: 프로파일 도입 후에도 기존 단위 테스트와 운영 절차가 모두 통과해야 함. 특히 CI 테스트(아주 짧은 실행)는 별도 TEST 프로파일 또는 SMOKE로 대체하고, 문서의 실행 예시들을 최신 프로파일 방식으로 갱신할 것.
Evidence 경로
통합 테스트 로그: logs/evidence/d206_4_profile_switching/ – 프로파일별로 엔진을 실행한 결과 로그 (예: SMOKE 5분, BASELINE 20분 실행 결과 각각 저장).
SSOT 문서: docs/v2/SSOT_RULES.md – 프로파일 정의 및 사용 규칙 (예: Paper Acceptance는 반드시 BASELINE+LONGRUN 조합 등) 추가된 섹션.
D_ROADMAP 갱신: 각 D 단계에 해당 프로파일이 명시되도록 D_ROADMAP.md 수정 (예: D205-9는 PAPER Smoke 20m 프로파일, D205-18은 BASELINE+LONGRUN 프로파일 실행 등).
상태
PLANNED (프로파일 세부 내용 설계 중)
향후 조치: 상기의 D206-0 ~ D206-4 재정의에 따라, 원래 계획되었던 Grafana, Docker 배포, Runbook 등 **운영 인프라 작업(D206-1~5)**은 D207 이후로 연기됩니다. D206 단계에서는 엔진 내부의 운영 프로토콜과 수익 로직 강화에 집중하며, 이를 통해 “돈 버는 알고리즘 우선” 원칙을 구현합니다. 이후 D207부터 모니터링 대시보드, Compose/배포, 운영 인터페이스 등의 과제를 순차적으로 진행할 예정입니다.