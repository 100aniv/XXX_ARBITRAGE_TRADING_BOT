[MISSION]
PHASE17 V6.1 인프라 Acceptance 테스트를 완료한다.

목표는 "Budget/Portfolio 인프라가 12시간 REAL PAPER에서 안정적으로 동작하는지" 검증하는 것이다.
1시간 돌려보고 리포트 쓰고 끝내는 것이 아니다.
이번 세션의 종료 조건은 "REAL PAPER 12H 실행이 실제로 끝나고, 최종 리포트까지 작성 완료"이다.

사용자는 어떤 명령도 직접 실행하지 않는다.
Windsurf(Claude)가 모든 실행/모니터링/디버깅/리포트 생성을 직접 수행해야 한다.

────────────────────────────────
[고정 규칙 – 절대 어기지 말 것]

1) 실행·테스트는 전부 네가 직접 한다
   - 사용자가 PowerShell/Git/pytest/스크립트를 "직접" 실행하게 시키지 말 것.
   - "이 명령을 사용자가 실행해라" / "이제 사용자가 확인해라" 같은 문장 금지.
   - Windsurf 터미널에서 네가 직접 명령을 실행하고, 로그를 읽고, 문제를 찾고, 수정하고, 다시 실행한다.

2) REAL PAPER 12H 끝날 때까지 "완료"라고 말하지 않는다
   - 5분 / 10분 / 30분 / 60분 중간 체크포인트에서
     "완벽 성공" / "PHASE17 완료" 같은 표현 절대 금지.
   - 이 세션의 "성공" 정의는 오직 하나:
     → REAL PAPER 12H 실행이 끝까지 돌고,
        Acceptance 기준을 충족하고,
        최종 리포트(MD)가 생성된 상태.

3) 기존 엔진 구조와 모듈을 최우선으로 활용한다
   - run_paper.py / 기존 Engine / PortfolioManager / PositionSizer / Guard / Reporter를 우선 사용.
   - 이미 존재하는 모듈이 있는데도, 똑같은 일을 하는 새 스크립트를 추가로 만드는 것 금지.
   - Supervisor 스크립트(run_real_paper_12h_supervised.py)는
     "PHASE17 디버깅용 하네스"로 사용할 수 있으나,
     핵심 로직은 항상 Engine 기반으로 유지한다.

4) 새 파일은 정말 필요할 때만 만든다
   - 이번 세션에서 코드/스크립트 신규 파일은 0 또는 최대 1개까지만 허용(필수인 경우에만).
   - 문서(MD)는 필요한 만큼 생성 가능하지만,
     문서 구조는 docs/PHASE17/ 하위에 정리한다.

5) 프로젝트 규칙 유지
   - 단일 엔진 (backtest/paper/live 공용)
   - Guard/Portfolio/Risk/Strategy는 "DO-NOT-TOUCH 코어"로 유지
   - Redis / Postgres / FlowGuardian 네임스페이스 등 기존 규칙 준수
   - 실행 전에 항상:
     a) Docker 컨테이너(Redis/Postgres) 상태 확인
     b) trading 관련 Python 프로세스가 있다면 종료
     c) Redis 상태/네임스페이스 클린업 (이전 실행 영향 제거)
     d) 로그 백업 및 초기화

────────────────────────────────
[이번 PHASE17 Acceptance에서 보는 것]

이 세션은 "수익 튜닝"이 아니라 "인프라 안정성" PHASE다.
따라서 검증 포인트는 다음과 같다.

1) Budget SSOT / Budget Cap 동작
   - PortfolioManager._get_used_budget() 이 실제 open position들을 반영하는지
   - PositionSizer가 available_budget 기준으로 position_value를 Cap 하는지
   - Engine이 Budget Cap 결과를 그대로 사용해 진입을 수행하는지
   - "Budget Cap Applied" 로그가 충분히 나오고, Portfolio Budget BLOCK 스팸이 사라졌는지

2) Guard/Scaling/Position Tracking 상호 충돌 여부
   - Volume Guard / Exposure Guard / Cooldown / Multi-position Scaling이 서로 충돌하지 않는지
   - 특정 Guard 하나 때문에 1시간 이상 엔트리 0 상태로 고착되지 않는지
   - Position 추가/청산 이후 PortfolioManager의 used_budget/available_budget이 일관적인지

3) 장기 실행 안정성 (12H)
   - 치명적 오류 (ERROR/CRITICAL) 0건
   - 엔진/스크립트 비정상 종료 0회
   - Redis/DB/로깅 인코딩 등으로 인한 실행 중단 없음

참고로, 이번 세션에서는 승률 / PnL은 "sanity check" 수준으로만 보고,
본격적인 수익 최적화는 다음 PHASE에서 다룬다.

────────────────────────────────
[Acceptance 기준 – 이 세션이 끝났다고 선언하려면 반드시 충족해야 하는 조건]

1) 실행 조건
   - 모드: REAL PAPER
   - Config: configs/scalping/real_paper_12h_v6_1_phase17.yml (또는 동등한 V6.1 Config)
   - Duration: 실제 약 12시간 연속 실행 (중간 재시작 시 총 실행 시간이 12H 이상이어야 함)

2) 정량 기준
   - Entry SUCCESS ≥ 100 (시장 상황이 극단적으로 조용한 경우가 아니라면)
   - Budget Cap Applied 로그 다수 존재 (Cap 0회면 실패)
   - Portfolio Budget BLOCK 비율 < 30% (초기 설계 기준, 10~20%가 이상적)
   - ERROR/CRITICAL 레벨 로그 0건
   - 엔진/프로세스 비정상 종료 0회

3) 정성 기준
   - 로그 상에서 Volume Guard, Exposure Guard, Cooldown, Budget Cap, Portfolio Check 등이
     서로 상식적인 수준에서 작동해야 하며,
     어떤 하나의 Guard 때문에 전략이 "사망 상태"로 고착되지 않아야 한다.
   - Equity 곡선이 12시간 동안 완전히 미친 듯이 붕괴되지는 않아야 한다.
     (이 PHASE에서 PnL로 합/불합격을 판단하지 않지만,
      인프라 단계에서도 완전한 붕괴는 이상 신호이므로 리포트에 기록해야 한다.)

4) 산출물
   - docs/PHASE17/PHASE17_V6_1_REAL_PAPER_12H_REPORT.md
     (필수 포함 내용:)
     - 테스트 환경 요약 (Config, 기간, 초기 Equity, 심볼 범위 등)
     - 주요 카운트:
       * Entry SUCCESS 수
       * Budget Cap Applied 수
       * Portfolio Budget BLOCK 수 및 비율
       * Guard별 BLOCK 통계 (Volume/Exposure/Cooldown 등)
       * ERROR/CRITICAL 존재 여부
     - 시간대별 체크포인트 요약 (M5, M10, M30, M60, H3, H6, H9, H12 등)
     - 간단한 Equity/Drawdown 추세 요약 (수치/표로, 그래프는 선택)
     - "PHASE17 인프라 Acceptance" 기준 충족 여부 최종 판단 (PASS / FAIL + 이유)

────────────────────────────────
[작업 단계 (네가 알아서 세부는 쪼개되, 최소 이 흐름은 지켜라)]

1) 컨텍스트 재확인 (이미 생성된 파일만 읽기)
   - execution/portfolio_manager.py
   - execution/position_sizer.py
   - execution/engine.py
   - configs/scalping/real_paper_12h_v6_1_phase17.yml
   - PHASE17 관련 보고서들 (기존 V4/V5/V6/V6.1 문서)

2) 환경 초기화
   - Docker Redis/Postgres 상태 확인
   - trading 관련 Python 프로세스 모두 종료
   - Redis 네임스페이스 / 상태 초기화
   - logs 백업 + 초기화

3) REAL PAPER 12H 실행 시작
   - 가능하면 run_real_paper_12h_supervised.py 활용
     (단, 새 하드코딩 대신 기존 설정/모듈 재사용)
   - 아니면 run_paper.py 직접 실행 + 간단한 모니터링 스크립트만 보조로 사용

4) 실행 중 모니터링 (완전 자동)
   - 5분 / 10분 / 30분 / 60분 / 3H / 6H / 9H / 12H 기준으로 상태 점검
   - 이때도 "사용자에게 확인 요청" 금지.
   - 필요한 집계/통계는 직접 스크립트를 만들어 실행하고, 그 결과를 기반으로 분석.

5) 12H 종료 후 리포트 생성
   - 위 Acceptance 기준에 따라 PASS/FAIL 판정
   - FAIL이면 원인 분석 + 다음 PHASE 제안
   - PASS면 "PHASE17 인프라 Acceptance 완료"로 문서에만 기록
     (실제 프로젝트에서 PHASE17을 마무리할지는 사용자가 결정)

────────────────────────────────
[중요 마인드셋]

- 이 세션의 목표는 "당장 수익 나는 봇"이 아니라
  "적어도 12시간 동안 망가지지 않고, 예산과 리스크를 일관성 있게 관리하는 엔진"이다.
- 중간에 30분이나 1시간 돌려보고 "완벽 성공"이라고 선언하지 말고,
  진짜 12H 장기 실행을 돌려본 후에만 Acceptance를 논할 것.
- 사용자를 QA나 오퍼레이터로 쓰지 말고,
  네가 개발자 + SRE + QA를 다 한다는 생각으로 끝까지 책임지고 진행할 것.
