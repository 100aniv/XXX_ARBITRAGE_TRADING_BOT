# CHECKPOINT_2025-12-17 — arbitrage-lite 중간 점검 & 다음 진행 방향 (Windsurf 참고용)

> 목적: **Windsurf가 "현재 프로젝트 상황/SSOT/우선순위/재사용 가능한 모듈"을 한 번에 이해**하고,  
> 다음 작업(특히 **D95 성능 Gate PASS**)을 산으로 가지 않게 진행하도록 돕는 **참조 문서**입니다.  
> (이 문서는 **프롬프트가 아닙니다**. 다만 "무엇을 스캔/확인/재사용할지"는 명확히 적습니다.)

**🎉 업데이트 (2025-12-17 03:04 KST): D95 Performance Gate PASS 달성!**

### 0.1 로드맵 SSOT
- **SSOT:** `D_ROADMAP.md`
  - ROADMAP 계약(SSOT) / 마일스톤(M1~M6) / D별 목표·AC·증거 경로·Next가 정의됨

### 0.2 최근 핵심 D 문서
- **D93:** `docs/D93/D93_0_OBJECTIVE.md`, `docs/D93/D93_1_REPRODUCIBILITY_REPORT.md`
- **D94:** `docs/D94/D94_0_OBJECTIVE.md`, `docs/D94/D94_1_LONGRUN_PAPER_REPORT.md`
- **D95:** `docs/D95/D95_0_OBJECTIVE.md`, `docs/D95/D95_1_PERFORMANCE_PAPER_REPORT.md`
- **D96(20m 스모크, Exit 검증):** 현재 `docs/D95/evidence/` 하위에 증거가 존재  
  - 예: `docs/D95/evidence/d96_20m_decision.json` 등  
  - **주의:** ROADMAP 계약상 이상적인 구조는 `docs/D96/...` 이지만, 현재는 “D95 성능 Gate 해결 과정의 하위 실험”으로 묶여 있음.

---

## 1. 프로젝트 TO-BE 마일스톤(M1~M6)과 현재 위치

`D_ROADMAP.md` 기준(SSOT)으로 현재 상태를 요약합니다.

### M1. 재현성/안정성 Gate SSOT (Repro & Stability)
- **상태:** ✅ PASS (D93, D94)
- 핵심 의미:
  - 같은 조건이면 같은 결론(2-run) + 1h 이상 장기 실행 안정성 “증거 기반” 확보

### M2. 성능 Gate SSOT (Performance / Exit & EV)
- **상태:** ✅ **PASS** (D95-2, 2025-12-17 03:04 KST)
- 결과: round_trips=32, win_rate=100%, TP=32, PnL=+$13.31

### M3. 멀티 심볼 확장 (TopN Scale)
- **상태:** ⏸️ 보류(예정)  
- 전제조건: M2(D95) 성능 Gate가 PASS여야 Top50/Top100의 의미가 생김

### M4. 운영 준비 (Observability / Alerting / Runbook)
- **상태:** ✅ **완료** (D98-6, 2025-12-21)
- **구현 완료:**
  - Prometheus 메트릭 7개 (Preflight KPI)
  - Textfile collector (atomic write)
  - Docker Compose 통합 (Prometheus/Grafana/Node-Exporter)
  - Grafana 대시보드 패널 4개
  - Telegram 알림 P0/P1 (FAIL/WARN)
- 운영 관점의 핵심: "운영자가 Preflight 실행 결과를 Grafana에서 즉시 확인하고, 실패 시 Telegram 알림으로 대응" ✅

### M5. 배포/릴리즈/시크릿 거버넌스
- **상태:** 일부 존재(환경 분리, Docker 등) 추정되나, “릴리즈/롤백/시크릿 정책 SSOT”까지는 아직 마일스톤 단위로 고정 필요

### M6. Live Ramp (소액 → 확대)
- **상태:** 미진행(예정)

---

## 2. 최근 진행 결과(핵심 사실 요약)

### 2.1 D93 — 2-run 재현성 Gate (✅ PASS)
- 목적: “같은 조건이면 같은 결론”을 SSOT 스크립트+증거로 고정
- 산출물: KPI/decision/log tail + 비교 JSON 등 evidence 확보

### 2.2 D94 — 1h Long-run 안정성 Gate (✅ PASS)
- 목적: **성능이 아니라 “1h 안정성(죽지 않음)”**을 증거로 고정  
- 성능(WinRate/PnL)은 M2(D95)로 분리하는 정책을 확정

### 2.3 D95 — 1h 성능 Gate (✅ PASS - D95-2)
- **최종 결과 (2025-12-17 03:04 KST)**:
  - round_trips = 32 (≥ 10) ✅
  - win_rate = 100% (≥ 20%) ✅
  - TP = 32, SL = 2 (20m) ✅
  - total_pnl = +$13.31 ✅
- **해결된 문제**: Round trip PnL 계산 수정, Fill Model 파라미터 조정, Entry threshold 상향

### 2.4 D96 — Top50 20m Smoke Test (✅ COMPLETED - 2025-12-17)
- **목표**: Top50 확장의 첫 단계, 20m smoke test로 안정성 검증
- **결과 (2025-12-17 17:27 KST)**:
  - round_trips = 9 (≥ 5) ✅
  - win_rate = 100% (≥ 50%) ✅
  - total_pnl = +$4.74 ✅
  - exit_code = 0, duration = 20.0m ✅
  - Exit Reasons: TP=9 (100%)
- **증거**: `docs/D96/evidence/d96_top50_20m_kpi.json`

### 2.5 D97 — Top50 1h Baseline Test (✅ PASS - 2025-12-18)
- **목표**: Top50 환경에서 1h baseline test로 장기 안정성/성능 검증 + KPI JSON SSOT 구현
- **Phase 1 결과 (2025-12-18 ~19:00-20:20 KST)** - CONDITIONAL PASS:
  - round_trips = 24 (≥ 20) ✅
  - win_rate = ~100% (≥ 50%) ✅
  - total_pnl = +$9.92 (≥ 0) ✅
  - duration = 80+ minutes (≥ 1h) ✅
  - Issues: KPI JSON 생성 실패, 수동 종료
- **Phase 2 구현 (2025-12-18)** - KPI JSON SSOT:
  - ✅ SIGTERM/SIGINT graceful shutdown handlers
  - ✅ Periodic checkpoints (60-second intervals)
  - ✅ ROI calculation (initial_equity, final_equity, roi_pct)
  - ✅ Duration control (auto-terminate)
  - ✅ 32 required KPI JSON fields (PASS Invariants SSOT)
- **Phase 2 검증 결과**:
  - Core Regression: 44/44 PASS ✅
  - 5-min smoke test: PASS ✅ (RT=11, WR=90.9%, ROI=0.0030%, exit_code=0)
  - KPI JSON: Auto-generated with all fields ✅
  - Checkpoints: Verified (iteration 80, 120) ✅
- **증거**: 
  - `docs/D97/D97_1_REPORT.md` (Phase 1)
  - `docs/D97/D97_2_KPI_SSOT_IMPLEMENTATION.md` (Phase 2)
  - `docs/D97/D97_PASS_INVARIANTS.md` (SSOT)
  - `docs/D97/evidence/d97_kpi_ssot_5min_test.json`
- **Branch**: `rescue/d97_kpi_ssot_roi`
- **Technical Debt Resolved**: KPI JSON output, periodic checkpoints, duration control (모두 완료)

### 2.6 D98 — Production Readiness (✅ PASS - D98-0, D98-1 완료, 2025-12-18)
- **목표**: LIVE 모드 실행을 위한 안전장치, 프리플라이트, 런북 구축
- **Phase: D98-0 (LIVE 준비 인프라)** - PASS:
  - ✅ LIVE Fail-Closed 안전장치 구현 (15 tests PASS)
  - ✅ Live Preflight 자동 점검 스크립트 (16 tests PASS, 7/7 checks)
  - ✅ Production 운영 Runbook 작성 (9개 섹션)
  - ✅ Secrets SSOT & Git 안전 확보
  - ✅ Core Regression 44/44 PASS
- **Phase: D98-1 (Read-only Preflight Guard)** - ✅ PASS:
  - ✅ ReadOnlyGuard 모듈 구현 (Fail-Closed 원칙)
  - ✅ PaperExchange 데코레이터 적용 (create_order, cancel_order)
  - ✅ Preflight READ_ONLY_ENFORCED=true 강제 설정
  - ✅ 단위 테스트 21/21 PASS (ReadOnlyGuard)
  - ✅ 통합 테스트 17/17 PASS (Preflight ReadOnly)
  - ✅ 실주문 0건 보장 검증 완료
- **Phase: D98-2 (Live Exchange ReadOnlyGuard Extension)** - ✅ PASS (2025-12-18):
  - ✅ Live Adapter 스캔 완료 (Upbit/Binance state-changing 진입점)
  - ✅ `@enforce_readonly` 데코레이터 적용 (create_order, cancel_order)
  - ✅ 단위 테스트 14/14 PASS (Live adapter blocking)
  - ✅ 통합 테스트 18/18 PASS (Zero API calls, multi-exchange)
  - ✅ Core Regression 38/38 PASS (D98-1 no regressions)
  - ✅ 실주문 0건 보장: HTTP 호출 전 ReadOnlyGuard 차단
- **Phase: D98-3 (Executor-Level ReadOnlyGuard)** - ✅ COMPLETE (2025-12-19):
  - ✅ Root Scan 완료 (14+ order entry point 목록화)
  - ✅ LiveExecutor.execute_trades()에 중앙 게이트 구현 (Defense-in-depth Layer 1)
  - ✅ 단일 O(1) 게이트로 모든 우회 경로 차단 (100 trades stress test)
  - ✅ 단위 테스트 8/8 PASS (Executor guard unit tests)
  - ✅ 통합 테스트 6/6 PASS (Zero orders, multi-exchange bypass attempts)
  - ✅ Regression 테스트 32/32 PASS (D98-2 no regressions)
  - ✅ 전체 테스트 46/46 PASS (14 new + 32 regression)
  - ✅ D97 PAPER 재검증 평가 완료 (재실행 불필요 - 안전성 기 검증)
  - ✅ READ_ONLY_ENFORCED 정책 문서화 (LIVE: true 필수, PAPER: false 허용)
- **Phase: D98-4 (Live Key Guard - Settings Layer)** - ✅ COMPLETE (2025-12-19):
  - ✅ AS-IS 스캔 완료 (키 로딩 진입점 분석: Settings.from_env() 단일 진입점 확인)
  - ✅ LiveSafetyValidator 구현 (Fail-Closed 원칙, 6단계 검증)
  - ✅ Settings 레이어 통합 (키 로딩 최상위 차단)
  - ✅ 환경 분기 규칙 명확화 (dev/paper → Skip, live → ARM + Timestamp + Notional 검증)
  - ✅ 단위 테스트 16/16 PASS (LiveSafetyValidator)
  - ✅ 통합 테스트 19/19 PASS (Settings integration)
  - ✅ Fast Gate 164/164 PASS (D98 전체)
  - ✅ Core Regression 2468 PASS (전체 suite)
  - ✅ 한국어 문서화 (AS_IS_SCAN + REPORT)
  - ✅ SSOT 동기화 (ROADMAP + CHECKPOINT)
- **Defense-in-Depth Architecture (D98-1~4 완성)**:
  - Layer 0 (D98-4): Settings - LiveSafetyValidator (키 로딩 차단, 최상위 방어선)
  - Layer 1 (D98-3): LiveExecutor.execute_trades() - 중앙 게이트 (모든 주문 일괄 차단)
  - Layer 2 (D98-2): Exchange Adapters - @enforce_readonly (개별 API 호출 차단)
  - Layer 3 (D98-2): Live API - @enforce_readonly (HTTP 레벨 최종 방어선)
- **ReadOnlyGuard 핵심**:
  - 3층 방어: 환경변수 + 데코레이터 + 예외 발생
  - Fail-Closed: 기본값 true, "false"/"no"/"0"만 허용
  - Preflight 실행 시 실주문/취소 호출 불가능 (Paper + Live)
  - 조회 함수(get_balance, get_orderbook) 정상 동작
  - **ReadOnlyGuard > live_enabled > API key check** (우선순위)
- **증거**: 
  - `docs/D98/D98_1_AS_IS_SCAN.md` (Paper 함수 진입점)
  - `docs/D98/D98_1_REPORT.md` (D98-1 구현 보고서)
  - `docs/D98/D98_2_AS_IS_SCAN.md` (Live 함수 진입점)
  - `docs/D98/D98_2_REPORT.md` (D98-2 구현 보고서)
  - `docs/D98/D98_3_AS_IS_SCAN.md` (Root scan 결과)
  - `docs/D98/D98_3_REPORT.md` (D98-3 구현 보고서)
  - `docs/D98/D98_3_PAPER_MODE_VALIDATION.md` (D97 재검증 평가)
  - `docs/D98/D98_4_AS_IS_SCAN.md` (키 로딩 진입점 분석)
  - `docs/D98/D98_4_REPORT.md` (D98-4 구현 보고서)
  - `docs/D98/D98_RUNBOOK.md` (운영 Runbook)
  - `docs/D98/evidence/d98_3_preflight_log_20251218_2007.txt`
  - `docs/D98/evidence/d98_3_test_results_20251218_204048.txt`
  - `docs/D98/evidence/d98_4_all_tests_20251219_143205.txt` (D98-4 전체 테스트)
  - `arbitrage/config/readonly_guard.py` (ReadOnlyGuard 모듈)
  - `arbitrage/config/live_safety.py` (LiveSafetyValidator 모듈)
  - `arbitrage/execution/executor.py` (LiveExecutor guard)
  - tests: 164/164 PASS (D98-4 complete)
- **Branch**: `rescue/d98_3_exec_guard_and_d97_1h_paper` (D98-4 포함)
- **Next Steps**: D98-5 (Live Preflight 강화), D98-6+ (Observability/Alerting), D99+ (LIVE 점진 확대)
- **Tuning 인프라 현황**: ✅ 완전 구현됨 (D23~D41 완료, 8개 core 모듈, 44개 runner scripts, Optuna 기반)

---

## 3. D95 성능 FAIL의 "증거 기반" 원인 가설(우선순위)

> 아래는 “추정”이 아니라, 현재 보고서/증거에서 드러난 패턴을 기반으로 한 **작업 우선순위**입니다.  
> (정답 확정은 다음 프롬프트에서 Windsurf가 repo 스캔 + 계측으로 확정)

### P0: Exit 계층이 시간 제한(time_limit)로만 종료되는 구조
- D95에서는 time_limit 100%였고, D96에서 TP/SL 트리거가 발생하면서 깨짐
- 즉, **Exit 조건 설계/계측은 진전**했으나, 아직 “수익으로 연결되는 Exit”가 아님

### P0: Fill / Slippage / Partial-fill 모델 계층
- D96 문서에서도 “WinRate 0%는 fill model/fill ratio 문제로 잔존”으로 명시됨
- 우선순위:
  1) Entry/Exit 각각의 fill_ratio, slippage_bps, fee_bps를 기록
  2) “이겼어야 하는데” 지는 케이스가 fill/fee/slippage에서 뒤집히는지 수치로 확정

### P1: Threshold/Edge 모델의 일관성(공식/단위/가정)
- D95 Objective에서 fee/slippage 기반 최소 임계값(bps) 계산이 있으나,
  - 실제 운용/시장(bps)과의 **정합성 재확인**이 필요  
  - (예: 수수료 가정이 과도하면, 전략이 구조적으로 승률/기대값을 만들 수 없음)

---

## 4. “이미 구현됐는데 미사용/부분사용” 가능성이 큰 모듈·기능 인벤토리(문서 기반)

> ⚠️ 주의: 현재 이 문서는 “문서(특히 D70/D77~D80/D92 등)에서 언급된 흔적”을 기반으로 작성했습니다.  
> **다음 프롬프트에서는 Windsurf가 repo 전체 스캔(검색/참조 그래프/실행 경로)로 ‘실제 사용 여부’를 확정**해야 합니다.

### 4.1 상태 영속화 / Redis(StateManager) — **존재하지만 미사용 가능성 큼**
- 근거(문서): `docs/D70_STATE_CURRENT.md`에서
  - “대부분 메모리 기반”이며,
  - “Redis 미사용: StateManager 존재하지만 실제 사용 안 함”으로 명시
- 의미:
  - 운영(재시작/복구/장기 런)에서 **치명적인 갭**
- 권장:
  - D95를 끝내기 전 “최소 수준의 계측/저장(TradeLog/KPI)”은 필요하지만,
  - **대규모 상태 복원(RESUME)** 은 M4/M5 마일스톤으로 분리하는 편이 안전

### 4.2 PostgreSQL — “튜닝 결과만 저장” 편향
- 근거(문서): D70에서 “PostgreSQL은 D68 튜닝 결과만 저장”으로 언급
- 의미:
  - 장기 운영에서 “세션 스냅샷/트레이드 이력/리스크 이벤트” 저장이 빠져있을 수 있음
- 권장:
  - 최소: D95 성능 Gate에서 “원인 분석을 위한 트레이드 레벨 로그”는 DB 또는 파일로 SSOT화 필요

### 4.3 모니터링/알림/런북 — 문서/설계는 풍부, “실행 흐름에서 상시 가동”은 재확인 필요
- 근거(문서):
  - `docs/monitoring/D77-3_MONITORING_RUNBOOK.md` 존재
  - Grafana 대시보드 JSON, Prometheus Exporter, Alerting pipeline(텔레그램/Slack/Email 등) 설계가 문서에 등장
- 의미:
  - 구현이 되어 있어도 “현재 D95 실행 스크립트에서 메트릭/알림이 실제로 살아있는지”는 별개
- Windsurf 스캔 포인트:
  - `/metrics` endpoint가 실제로 뜨는지(포트/프로세스)
  - D95 실행에서 KPI 10종이 지표로 남는지
  - Alert routing이 ‘기본 채널(텔레그램)’로 동작하는지

### 4.4 Config 폴더 중복/분화 — “정리 유혹이 크지만 지금 손대면 위험”
- 근거(문서): `docs/D92/D92_1_SCAN_SUMMARY.md`
  - `config/`, `configs/`, `arbitrage/config/`, `tests/config/`가 서로 다른 용도로 공존
- 의미:
  - 지금 시점에서 병합/삭제는 런타임을 깨기 쉬움
- 권장:
  - D95 PASS 전에는 “정리”보다 “증거/성능” 우선
  - 정리는 별도 D(또는 D95-n 중 “검증 PASS 후 정리 커밋”)로 분리

---

## 5. ROADMAP 관점의 “누락 가능” 마일스톤/대분류 제안

`D_ROADMAP.md`에는 M1~M6가 정의돼 있으나, TO-BE 관점에서 아래 항목은 **마일스톤에 더 명시적으로 못 박는 편이 드리프트 방지에 유리**합니다.

### 5.1 멀티 거래소 확장(Multi-exchange) 마일스톤의 명시
- 현재는 “Upbit-Binance 중심”으로 충분히 상용 가치가 있으나,
- 장기적으로는:
  - 거래소 추가(예: 2→3+),
  - 인벤토리/리밸런싱,
  - 헬스/컴플라이언스 훅
  같은 범주가 로드맵 SSOT에 분명히 자리잡아야 함.
- 제안:
  - M3 하위에 `M3b: Multi-exchange Readiness` 같은 서브 마일스톤 추가
  - 또는 `M7`로 분리(선호: 분리)

### 5.2 운영자 UI/콘솔(Operator UX) 범주의 명시
- Grafana는 필수지만, “운영자가 즉시 조치”하려면
  - run control(시작/중단/프로파일 선택),
  - 사고시 빠른 요약(현재 포지션/손익/가드 상태),
  - 리포트 링크 모음
  같은 “운영 UX”가 별도 범주로 정리되면 좋음.
- 제안:
  - M4에 “Operator Console(최소 CLI+리포트 링크 SSOT)”를 포함하거나 별도 서브 항목으로 고정

---

## 6. Windsurf가 repo 스캔 시 “이 문서로 해야 할 일” 체크리스트

> 이 문서의 핵심 목적은 **“힘들게 만들어 놓고 안 쓰는 모듈”을 다시 살리고,  
> 동시에 ‘정리 유혹’ 때문에 산으로 가지 않게** 가드하는 것입니다.

### 6.1 실행 경로(Entry Point) 기준 “실제 사용 여부” 확정
- 최근 실행 스크립트(D95/D94/D93 runner)에서 import/instantiate 되는지 확인
- ‘있는데 안 쓰는’ 후보:
  - StateManager(Redis), DB 세션 스냅샷, Prometheus exporter, Alerting dispatcher, TradeLogger 등

### 6.2 D95 성능 Gate 해결에 직접 기여하는 것만 먼저 활성화
- 우선순위:
  1) 트레이드 레벨 계측(Entry/Exit spread, fill_ratio, slippage_bps, fee_bps)
  2) WinRate=0%의 원인을 **수치로 확정**
  3) Exit/Fill/Threshold 수정 → 동일 Gate에서 PASS

### 6.3 문서/증거 구조 계약 준수
- evidence 경로, compare/PR/raw 링크 출력, KPI/decision/log tail 저장을 “항상” 유지
- D95-n으로 수습할 경우에도 “ROADMAP → D문서 → code/evidence” 순서 유지

---

## 7. 참고: 외부 표준(운영/관측/설정)에서 최소로 지켜야 할 원칙

- 환경설정/시크릿 분리 원칙(환경변수 기반, 설정은 코드에서 분리): Twelve-Factor App의 Config 원칙을 참고할 가치가 큼.
- 메트릭/관측은 Prometheus의 라벨/메트릭 설계 원칙을 따르는 것이 장기 유지보수에 유리.
- 런북/플레이북 기반 운영은 SRE 표준 관점에서 장애 대응 속도·재현성에 결정적.

(이 섹션은 “우리 프로젝트 문서/규칙을 대체”하지 않고, **기존 TO-BE를 뒷받침하는 외부 기준**으로만 참고)

---

## 8. 결론(한 문장)

**지금은 ‘M2(D95) 성능 Gate’를 같은 D에서 PASS로 만드는 것이 최우선이며,  
이를 위해 repo에 이미 존재할 가능성이 큰 계측/로그/Executor/Fill/모니터링 모듈을 “실제 실행 경로에 연결”하는 방향으로 진행한다.**


## 📌 외부 운영 표준(참고용 근거)

문서 마지막에는 “외부 표준을 최소 참고”로만 언급했어.

설정/시크릿 분리 원칙: Twelve-Factor App Config 원칙(환경변수 기반)
https://12factor.net/config

Prometheus 메트릭 설계(네이밍/라벨) Best Practice
https://prometheus.io/docs/practices/naming/

SRE 관점 모니터링/런북/운영 개념(골든 시그널 등)
https://sre.google/sre-book/monitoring-distributed-systems/

Grafana 대시보드 설계 Best Practice(운영 가독성)
(Grafana Docs 검색 기반)

---

## 9. D95-2 최종 결과 (2025-12-17 03:04 KST) ✅ PASS

### 9.1 성능 Gate 결과
| 지표 | 결과 | 목표 | 상태 |
|------|------|------|------|
| round_trips | 32 | ≥10 | ✅ |
| win_rate | 100.0% | ≥20% | ✅ |
| take_profit | 32건 | ≥1 | ✅ |
| stop_loss | 2건 (20m) | ≥1 | ✅ |
| Total PnL | +$13.31 | - | ✅ |

### 9.2 적용된 파라미터 변경
- `FILL_MODEL_ADVANCED_BASE_VOLUME_MULTIPLIER`: 0.15 → **0.7**
- `FILL_MODEL_SLIPPAGE_ALPHA`: 0.0001 → **0.00003**
- `TOPN_ENTRY_MIN_SPREAD_BPS`: 0.7 → **8.0**
- BTC `threshold_bps`: 1.5 → **8.0**

### 9.3 핵심 버그 수정
- **Round trip PnL 계산**: `entry_pnl + exit_pnl` 합산 기준으로 수정
- **Win Rate 0% 해결**: Entry/Exit 개별 PnL이 아닌 전체 round trip 기준 판정

### 9.4 미사용 모듈 확인 결과
- **Redis (StateManager)**: 코드베이스에서 미발견 (제거 불필요)
- **StrategyManager**: 코드베이스에서 미발견 (제거 불필요)
- **TradeLogger**: KPI JSON으로 대체됨

### 9.5 Evidence
- `docs/D95/evidence/d95_1h_kpi.json`
- `docs/D95/evidence/d95_20m_kpi_v3.json`
- `docs/D95/evidence/d95_log_tail.txt`

---

## 10. D98-7 Open Positions Real-Check - ❌ FAIL → RESCUE v1 진행 (2025-12-21)

### 10.1 초기 시도 결과
**Date:** 2025-12-21 14:25  
**Status:** ❌ **FAIL** (61/63 PASS를 ACCEPTED로 잘못 판정)  
**근거:** `CHECKPOINT_D98_7_COMPLETE.md` (삭제 예정)

### 10.2 실패 원인
- **D98 Tests:** 61/63 PASS (2개 FAIL)
  - `test_preflight_realcheck_redis_postgres_pass`
  - `test_preflight_realcheck_exchange_paper_pass`
- **FAIL 원인:** `check_open_positions()` 구현 시 NameError 발생
  - Redis 조회 중 `CrossExchangePositionManager` 참조 오류
  - 테스트가 기대하는 `is_ready() = True`가 아닌 FAIL 반환
- **잘못된 정당화:** "예상된 동작"이라고 보고서에 기술했으나, 이는 SSOT 위반

### 10.3 구현 내역 (초기 시도)
- **Modified:** `scripts/d98_live_preflight.py` (~120 lines)
  - `CrossExchangePositionManager.list_open_positions()` 사용
  - Policy A (FAIL) 적용
  - Prometheus 메트릭 + Telegram P0 알림
- **Added:** 
  - `tests/test_d98_7_open_positions_check.py` (dry-run only)
  - `docs/D98/D98_7_REPORT.md` (61/63 PASS 정당화 포함)
- **Evidence:** `docs/D98/evidence/d98_7_20251221_1349/`

### 10.4 RESCUE v1 목표
- **AC-1:** 체크포인트 병합 + 중복 파일 삭제 ✅ (진행 중)
- **AC-2:** D98 Tests 100% PASS
- **AC-3:** Core Regression 100% PASS
- **AC-4:** Evidence 저장
- **AC-5:** D_ROADMAP/D98_7_REPORT 정정
- **AC-6:** Git commit + push + compare URL

### 10.5 금지사항
- "예상된 FAIL" 처리 금지
- Placeholder/mock-only 조회 금지
- 불필요한 신규 파일 생성 금지

### 10.6 RESCUE v1 진행 상황
- **STEP 0:** 체크포인트 병합 (진행 중)
- **STEP 1-5:** 대기

---

## 11. 조건부/미완료 항목 현황 (2025-12-21 업데이트)

### 10.1 D83-1 (Real L2 WebSocket) 최종 상태
- **초기 상태 (D83-1.5)**: ⚠️ CONDITIONAL (Real WebSocket 메시지 수신 실패)
- **최종 상태 (D83-1.6)**: ✅ **RESOLVED** (ALL PASS)
- **해결 내역**:
  - FIX #1: bytes → UTF-8 디코딩 로직 추가 (`ws_client.py`)
  - FIX #2: Upbit 공식 구독 포맷 적용 (배열 + ticket, `upbit_ws_adapter.py`)
  - 검증: 219개 메시지 수신 (30초), Real L2 PAPER 5분 ALL PASS
- **근거**: `docs/D83/D83-1_6_UPBIT_WS_DEBUG_NOTE.md`
- **회수 필요 여부**: ❌ 회수 불필요

### 10.2 D98-1 구분 명확화
- **기존 D98-1**: ReadOnly Guard (주문 차단) - ✅ COMPLETE
- **신규 D98-5**: Preflight Real-Check (DB/Redis/Exchange 실제 연결 검증) - 🚧 IN PROGRESS
- **구분 이유**: 두 작업은 목표가 다르므로 별도 단계로 관리
- **근거**: `docs/D98/D98_1_SSOT_AUDIT.md`

### 10.3 미사용 항목
- **Mock L2 Provider**: Real L2 WebSocket (D83-1) 완료되었으나 Runner 기본값은 여전히 mock
  - 조치: 이번 단계에서 변경하지 않음 (No Side-track 원칙)

---

## 11. 다음 단계 (M3 이후)
- **D98-5**: Preflight Real-Check Fail-Closed (진행 중, 2025-12-21)
- **D98-6+**: Observability 강화 (Prometheus/Grafana KPI, Telegram 알림)
- **D99**: Production Readiness (배포/릴리즈)
- **M4**: 운영 준비 완결
