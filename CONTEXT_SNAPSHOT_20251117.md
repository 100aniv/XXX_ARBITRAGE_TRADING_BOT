# ==========================================================
# 0. 프로젝트 정체성 / 개념적 배경
# ==========================================================
- 프로젝트명: arbitrage-lite
- 목표: 업비트 Spot / 바이낸스 Futures 기반의 
        “단일 아비트라지 엔진” 완성 → 실거래 가능 수준.
- 추가 목적: tuning, backtest, paper, distributed session, K8s pipeline 등
- Philosophy:
    - 항상 안전 우선 (실거래 금지 기본값)
    - 모든 단계는 검증 → 테스트 → 문서 → 회귀 보장
    - 하드코딩 금지 / config-driven
    - 엔진 코어(DO-NOT-TOUCH): backtest/engine/tuning logic
    - Infra/Wrapper 레이어는 교체 가능

- 최종적으로:
    Paper 모드 → 안정 → 실거래 통합(Live Runner) → RiskGuard → UI/UX
    로 이어지는 로드맵.

# ==========================================================
# 1. 현재까지의 실행 단계
# ==========================================================
D16~D37: 엔진/백테스트/튜닝 기반  
D38: Single Tuning Runner  
D39: Session Planner + Metrics Aggregator  
D40: Local Tuning Session Runner  
D41: K8s Distributed Runner  
D42: Exchange Adapter Layer (Paper/Upbit/Binance skeleton)

→ 지금 상태: **거래소 레이어까지 탑재된 상태 (Live-ready skeleton)**  
→ 다음 단계: D43~D45 엔진–거래소 연결 & 실거래 Paper 검증

# ==========================================================
# 2. 엔진 구조
# ==========================================================
arbitrage/
 ├── arbitrage_core.py          # 핵심 엔진 DO-NOT-TOUCH
 ├── arbitrage_backtest.py      # 백테스트 엔진
 ├── arbitrage_tuning.py        # 개별 튜닝 job
 ├── tuning_session.py          # 그리드 스윕 planner
 ├── tuning_aggregate.py        # 결과 집계
 ├── tuning_session_runner.py   # Local runner (D40)
 ├── k8s_pipeline.py            # K8s tuning pipeline (D36)
 ├── k8s_tuning_session_runner.py   # K8s distributed session 실행기 (D41)
 ├── exchanges/
 │     ├── base.py              # BaseExchange 인터페이스
 │     ├── paper_exchange.py    # Paper trader (완성)
 │     ├── upbit_spot.py        # 실거래 skeleton
 │     └── binance_futures.py   # 실거래 skeleton
 └── ... (기타 infra 모듈)

엔진 핵심 DO-NOT-TOUCH 규칙:
    - ArbitrageEngine의 core 매칭/체결 로직
    - Backtest 계산식
    - TuningMetrics/TuningConfig 구조
    - Result JSON 포맷

# ==========================================================
# 3. 데이터 흐름
# ==========================================================
[백테스트]
CSV snapshots → Backtester → Result(json)

[튜닝]
TuningConfig → ArbitrageTuningRunner(D38) → JSON

[세션 스윕]
SessionConfig(D39) → Planner → JSONL job-list  
→ (로컬: D40) Subprocess  
→ (K8s: D41) Distributed job-run  
→ Aggregator → Best metrics

[실거래(향후)]
LiveConfig → ExchangeAdapter(Upbit/Binance)  
→ ArbitrageEngine → 주문 생성/조회 → RiskGuard → 실행 Loop

# ==========================================================
# 4. 개발 철학 / 규칙 (중요)
# ==========================================================
1) **전체 구조 절대 무시 금지**  
   - 새 기능은 항상 기존 흐름(D 단계)의 상위에 쌓는 방식.

2) **테스트 우선 / 회귀 보장**
   - 매 D-step에서 테스트 = 기능 정의.
   - 모든 단계 테스트 + 이전 단계 회귀 0 실패 유지 필수.

3) **Network Policy**
   - Upbit/Binance 포함: 실제 호출 금지
   - 실거래 LiveRunner는 Paper-only 상태로 구현 후,
     최종 단계에서만 실제 API 호출을 허가.

4) **설정 기반 (config-driven)**
   - 하드코딩된 값 불가
   - YAML → dataclass 변환 → 엔진 주입

5) **CLI 철학**
   - 모든 중요한 기능은 CLI 스크립트로 실행 가능해야 함.
   - run_arbitrage_backtest.py
   - run_arbitrage_tuning.py
   - run_tuning_session_local.py
   - run_tuning_session_k8s.py
   - (향후) run_arbitrage_live.py

6) **K8s 규칙**
   - kubectl 직접 호출 금지
   - client wrapper mock 기반
   - JobSpecBuilder로 manifest 생성

7) **Paper-first / Live later**
   - PaperExchange → 엔진 동작 완전 검증
   - Upbit/Binance는 skeleton만 유지 후 후반 통합

8) **안전 정책**
   - live_enabled: false 기본값
   - 실거래는 마지막 단계에서 명시적 enable 필요
   - API key는 환경변수 기반

# ==========================================================
# 5. D42 Exchange Adapter Layer 요약
# ==========================================================
구조:
exchanges/
 ├── base.py          # 필수 인터페이스
 ├── exceptions.py
 ├── paper_exchange.py
 ├── upbit_spot.py    # 실제 구현 skeleton
 └── binance_futures.py

핵심 메서드:
    get_orderbook(symbol)
    get_balance()
    create_order()
    cancel_order()
    get_order_status()
    get_open_positions()

특징:
    - 공통 인터페이스(Easy to scale)
    - PaperExchange: 완전 구현
    - Upbit/Binance: 실거래 로직 미구현 (stub 구조)
    - live_enabled 플래그로 안전성 확보

# ==========================================================
# 6. 현재까지의 테스트 체계
# ==========================================================
- D16~D42 전체 테스트 수: 약 550+
- 모든 D 단계 테스트 100% 통과
- K8s runner, tuning pipeline, session planner까지 모두 검증
- Exchange layer도 mock 기반으로 52개 테스트 통과

테스트 목적:
    - 모든 레이어가 서로 맞물리는지 확인
    - 엔진 회귀 방지
    - K8s/Paper/Backtest 간 기능 불일치 제거

# ==========================================================
# 7. 전체 로드맵 (확정 버전)
# ==========================================================
(이미 수행)
D16~D30: 엔진/백테스트 기반  
D31~D36: K8s tuning pipeline  
D37: Arbitrage MVP  
D38: single tuning job runner  
D39: session planner & aggregator  
D40: local runner  
D41: K8s distributed runner  
D42: exchange adapter layer

(남은 단계: 핵심 실사용 로드맵)
D43: LiveConfig + LiveRunner 설계  
D44: RiskGuard (per-trade, daily loss limit)  
D45: LiveRunner ↔ ExchangeAdapter 실제 통합  
D46: Paper 모드 장시간 스트레스 테스트  
D47: Logging/Monitoring Layer (파일, Slack optional)  
D48: Metrics Dashboard (시각화: Grafana-lite or local UI)  
D49: Minimal UI/UX (Python+FastAPI+simple dashboard)  
D50: 실거래 단계로의 migration 준비  
      - API 키/시크릿 관리  
      - 슬리피지, 오더 실패 재시도  
      - 안전 제동장치  
D51: Final QA / Packaging  
D52: Final Release

# ==========================================================
# 8. 최종 구조 철학 (TO-BE)
# ==========================================================
엔진 = 불변  
Infra = 교체 가능  
거래소 = 추상화  
실행 파이프라인 = config-driven  
Risk = 구조적으로 제어  
UI/UX = 엔진을 건드리지 않고 위에서 보기만 한다  
배포 = 로컬 Docker Desktop 기준  
클라우드/K8s는 선택적

# ==========================================================
# 9. 개발할 때의 절대 금지사항
# ==========================================================
- 엔진 로직 직접 수정 금지 (except explicit phase)
- API 키 하드코딩 금지
- K8s에 kubectl shell 호출 금지
- 출력 조작 금지 (debugging용 로그 외)
- 테스트 생략 금지
- D 단계 건너뛰기 금지
- 실거래 호출 금지 (final phase까지 NO)

# ==========================================================
# 10. 새 채팅에서 이어가기 위한 최소 요구
# ==========================================================
새 채팅에서는 다음을 포함해 질문/요청하면 된다:

"arbitrage-lite 프로젝트의 Context Snapshot을 불러온다.
현재 단계는 D42까지 완료되었으며,
다음 단계는 D43 Live Runner 설계이다.
이 문맥 전체를 기반으로 이어서 작업을 진행하라."

이렇게 하면:
- 전체 엔진 구조
- DO-NOT-TOUCH 규칙
- K8s/Paper 백엔드 철학
- Exchange adapter skeleton
- Tuning pipeline 흐름
- 앞으로의 로드맵

까지 **모두 즉시 복원**된다.

# ==========================================================
# END OF CONTEXT SNAPSHOT
# ==========================================================