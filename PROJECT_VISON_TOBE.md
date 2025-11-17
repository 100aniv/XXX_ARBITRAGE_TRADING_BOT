아래 내용 그대로 새 md 파일로 저장해서 “최종 TO-BE/비전 문서”로 쓰면 돼.
(예: docs/PROJECT_VISION_TOBE.md 이런 식으로.)

⸻

🧭 Arbitrage-Lite 프로젝트 최종 목표 & TO-BE 아키텍처

0. 한 줄 정의

“Upbit 현물 – Binance 선물 간 단일 차익거래(Arbitrage)를 중심으로,
백테스트·튜닝·실거래까지 하나의 엔진/하나의 코드베이스로 돌릴 수 있는,
로컬 Docker 기반 ‘개인용 프로급 아비트라지 시스템’

⸻

1. 최종 목표 (PRODUCT TO-BE)

1.1 사용자 관점 목표

사용자인 나는(개인 트레이더, 비개발자 기준):
	•	설치 & 실행:
	•	로컬 PC에서 Docker Desktop 한 번 띄우고,
	•	docker compose up -d 정도만으로 전체 시스템 기동
	•	UI:
	•	브라우저에서 접속 (예: http://localhost:8080)
	•	현재 상태를 한눈에 본다:
	•	현재 포지션 (Upbit/Binance 양쪽)
	•	실시간 스프레드, 기회 발생 로그
	•	오늘/전체 PnL, MDD, 승률
	•	최근 트레이드 리스트
	•	모드 전환:
	•	백테스트 모드: 기존 CSV/시세 데이터로 전략 성능 검증
	•	페이퍼(모의) 모드: 실시간 시세 + 가짜 주문(실거래 없음)
	•	라이브 모드: 실제 계정 API로 주문 실행
	•	위 3가지 모드를 UI에서 토글/설정 파일로 명확하게 전환
	•	안전장치:
	•	기본값은 항상 Paper 모드
	•	Live 모드는 사전에:
	•	live_enabled: true + 2중 확인 (설정 + UI)
	•	1일 손실 한도 / 트레이드당 최대 금액 / 레버리지 상한 등 리스크 가드 필수
	•	튜닝:
	•	“튜닝 세션 실행” 버튼/CLI로
	•	파라미터 그리드/범위를 설정하고
	•	자동으로 여러 조합을 백테스트
	•	상위 결과를 정리해서 보여줌 (PnL, MDD, 승률 등)

요약:
“로컬 Docker + 웹 UI 하나로, 백테스트→튜닝→페이퍼→라이브까지 끊김 없이 이어지는 개인용 프로 시스템”

⸻

2. 최종 아키텍처 개요 (SYSTEM TO-BE)

2.1 레이어 구조 (큰 틀)

[ UI / Dashboard ]
       ↓
[ API / Orchestrator Layer ]
       ↓
[ Trading Engine Layer ]
       ↓
[ Exchange Adapter Layer ]
       ↓
[ External Exchanges (Upbit, Binance ...) ]

[Offline Sidecar: Backtest / Tuning / K8s Pipeline]

	•	UI / Dashboard
	•	Web UI (예: React/Vue + 간단한 API 연동)
	•	실시간 상태, 로그, PnL, 트레이드 내역 표시
	•	API / Orchestrator Layer
	•	REST/gRPC/간단한 FastAPI 등
	•	“엔진 시작/중지”, “모드 변경”, “튜닝 세션 실행” 등의 제어 엔드포인트
	•	Trading Engine Layer
	•	현재 D37 ArbitrageEngine + Backtest + Tuning 로직이 있는 코어
	•	백테스트/페이퍼/라이브 모드 공통 엔진
	•	Exchange Adapter Layer
	•	D42에서 만든 BaseExchange + PaperExchange + UpbitSpotExchange + BinanceFuturesExchange
	•	실제 시세/주문은 여기서만 외부 API와 통신
	•	Offline Sidecar: 튜닝 & K8s
	•	D29~D41 K8s 기반 튜닝 파이프라인/세션 플래너/집계기
	•	“라이브 엔진과 분리된, 오프라인 튜닝 환경”

⸻

3. 엔진 코어 구조 TO-BE

3.1 단일 엔진 철학
	•	하나의 Arbitrage Engine:
	•	Backtest, Paper, Live 모두 같은 코드 경로 사용
	•	모드 차이는:
	•	데이터 소스 (CSV vs 실시간 WebSocket/REST)
	•	주문 실행 대상 (PaperExchange vs 실제 거래소 어댑터)
	•	코어 모듈은 DO-NOT-TOUCH 영역으로 고정:
	•	arbitrage_core.py
	•	arbitrage_backtest.py
	•	arbitrage_tuning.py
	•	변경/확장은 구성(config) / 어댑터 / 외부 레이어에서만 처리

3.2 엔진 데이터 흐름

OrderBookSnapshot 스트림
        ↓
ArbitrageEngine.detect_opportunity()
        ↓
ArbitrageOpportunity (기회)
        ↓
ArbitrageEngine.on_snapshot()
        ↓
ArbitrageTrade (개설/종료 이벤트)
        ↓
Execution Layer (Paper 또는 Live Exchange)
        ↓
포지션 / PnL / 로그 / 메트릭

	•	입력:
OrderBookSnapshot (현재 Upbit A, Binance B의 bid/ask)
	•	로직:
	•	스프레드 계산 (bps)
	•	수수료, 슬리피지 반영 → net edge
	•	조건 충족 시 새 포지션 개설 / 기존 포지션 종료
	•	출력:
	•	ArbitrageTrade 이벤트 + 상태 (open/closed, PnL, side, size 등)

3.3 모드 구분 (Backtest / Paper / Live)
	•	Backtest
	•	입력: CSV/저장된 시세
	•	실행: ArbitrageBacktester
	•	주문 실행: “가상 포지션” (Exchange 계층 사용 X)
	•	Paper
	•	입력: 실시간 시세 (실제 API or 스트림)
	•	주문 실행: PaperExchange (메모리 내 잔고/포지션)
	•	목적: 라이브 환경 리허설
	•	Live
	•	입력: 실시간 시세
	•	주문 실행: 실제 Upbit/Binance 어댑터
	•	반드시:
	•	손실 제한
	•	최대 포지션 크기
	•	최대 일간 트레이드 수 등 가드 적용

⸻

4. Exchange Adapter Layer TO-BE

4.1 BaseExchange 추상화
	•	공통 메서드:
	•	get_orderbook(symbol)
	•	get_balance()
	•	create_order(...)
	•	cancel_order(order_id)
	•	get_open_positions()
	•	get_order_status(order_id)
	•	구현체:
	•	PaperExchange
	•	UpbitSpotExchange
	•	BinanceFuturesExchange
	•	(미래) BybitFuturesExchange, OKXFuturesExchange 등 추가 가능

4.2 PaperExchange 역할
	•	완전한 모의 거래 엔진:
	•	내부에:
	•	잔고 dict
	•	오더북 시뮬레이션
	•	포지션/오더 상태 관리
	•	실거래 없이도:
	•	엔진 + 전략 + 리스크 로직 검증 가능
	•	테스트/개발/디버깅의 기본 모드

4.3 Live Exchange들의 원칙
	•	UpbitSpotExchange
	•	KRW 마켓 위주 (예: BTC/KRW)
	•	REST 기반 시세/주문
	•	API 제한/쿨다운 로직 포함 (rate limit)
	•	BinanceFuturesExchange
	•	USDT-M 선물
	•	롱/숏 via 선물 포지션
	•	레버리지 설정, 포지션 사이즈 계산 지원
	•	모든 실거래 어댑터는:
	•	API Key는 환경변수/비밀설정에서만 읽기
	•	테스트에서는 무조건 mock 사용
	•	live_enabled: false 를 기본값으로, 명시적 opt-in 필요

⸻

5. 튜닝 & K8s 파이프라인 위치 (D29~D41)

5.1 역할
	•	라이브 엔진과는 분리된, 오프라인/분산 튜닝 인프라
	•	목표:
	•	파라미터(스프레드 임계값, 슬리피지, 수수료 가정, 최대 포지션 등)를 자동 탐색
	•	여러 조합을 그리드/랜덤으로 돌린 뒤
	•	상위 성능 설정 후보를 뽑아낸다

5.2 주요 컴포넌트
	•	D37: ArbitrageEngine + ArbitrageBacktester (이미 구현 완료)
	•	D38: ArbitrageTuningRunner (단일 튜닝 job)
	•	D39: TuningSessionPlanner + TuningResultsAggregator
	•	D36, D41: K8s 기반 파이프라인/세션 디스트리뷰티드 러너

5.3 최종 TO-BE 관점
	•	“일반 사용” (MR WHITE 현재 목표):
	•	로컬 PC + Docker + Paper/Live만 써도 충분
	•	K8s 튜닝은 선택 사항(Advanced) 으로 남겨둠
	•	“확장/고급 사용”:
	•	클라우드 K8s 클러스터에 D29~D41 전체 파이프라인 올림
	•	밤새 수백 개 파라미터 조합 튜닝
	•	결과를 로컬 UI에서 조회하고, 상위 설정을 선택 적용

⸻

6. UI/UX & 모니터링 TO-BE

6.1 Web Dashboard
	•	구성 예시:

[Frontend]  React / Next.js / Vue 중 택1
      ↓ REST/WebSocket
[Backend API]  FastAPI or Flask
      ↓
[Core Engine / Runner] (Python)
      ↓
[DB/Storage]  SQLite or PostgreSQL (선택)

	•	페이지:
	•	Overview
	•	현재 모드 (Backtest/Paper/Live)
	•	Upbit/Binance 각각 잔고/포지션
	•	오늘 PnL / 누적 PnL / MDD / 승률
	•	Trade Log
	•	거래 리스트, 체결 시간, 가격, PnL
	•	필터: 날짜, 심볼, 전략
	•	Strategy & Risk Settings
	•	min_spread_bps, max_position_usd, stop_loss, take_profit 등
	•	UI에서 변경 → config 파일 또는 DB 반영
	•	Tuning
	•	튜닝 세션 목록
	•	각 세션에 대한 상위 파라미터 조합 / 메트릭
	•	System
	•	로그 뷰어 (엔진 로그)
	•	Docker/프로세스 상태 (healthy/unhealthy)

6.2 Observability (Grafana/Prometheus)
	•	Docker Compose에 포함:
	•	prometheus, grafana, 간단한 exporter
	•	Export 메트릭:
	•	현재 오픈 포지션 수
	•	초당 스냅샷 처리 수
	•	최근 1h/24h PnL
	•	API 에러/타임아웃 카운터
	•	Grafana 대시보드:
	•	엔진 성능/안정성 관점 시각화
	•	이 부분은 과거에 설계했다가 흐름상 사라졌으므로,
최종 TO-BE에서는 다시 포함 (단, “Advanced/옵션” 레이어로 명시)

⸻

7. 확장성 방향 (미래 옵션)

7.1 거래소 확장
	•	현재 기본:
	•	Upbit Spot + Binance Futures
	•	TO-BE:
	•	같은 BaseExchange 인터페이스 기반으로:
	•	Bybit, OKX, Bitget, MEXC 등 추가
	•	새로운 거래소를 추가해도:
	•	ArbitrageEngine과 상호작용하는 인터페이스는 동일
	•	“교체/조합 가능”

7.2 전략 확장
	•	현재 목표:
	•	2-leg Spot-Futures Arbitrage
	•	Upbit Spot ↔ Binance Futures
	•	이후 가능한 확장:
	•	Funding Rate Arbitrage
	•	선물 펀딩비 차이 활용
	•	Multi-Exchange Spread Arbitrage
	•	Binance vs Bybit vs OKX 등
	•	Triangular Arbitrage (동일 거래소 내부 3쌍)
	•	Statistical Arbitrage (pair trading 등)
	•	구조 원칙:
	•	전략을 Strategy 인터페이스로 추상화
	•	ArbitrageEngine이 다수의 Strategy를 동시에 관리 가능
	•	단, 지금 1차 목표는 “단일 Spot-Futures Arbitrage” 완성이 우선

⸻

8. 안전/보안/운영 원칙
	1.	기본 모드는 항상 Paper
	•	라이브는 명시적 두 번 이상 켜야 함 (config + UI)
	2.	API 키는 코드에 절대 하드코딩 금지
	•	.env 또는 OS 환경변수로만 관리
	3.	리스크 가드 필수
	•	트레이드당 최대 금액
	•	일간 손실 한도
	•	레버리지 상한
	•	연속 손실 횟수 제한 등
	4.	테스트는 항상 mock 기반
	•	실거래 (HTTP 요청) 날리는 테스트는 금지
	5.	코어 엔진 모듈은 DO-NOT-TOUCH
	•	동작 검증 후에는 리팩토링 금지, 필요 시 새 전략/레이어로 감쌈
	6.	Config-driven 구조 유지
	•	수치/상수는 YAML/JSON 설정으로 뺀다
	•	코드에는 로직만 남기기

⸻

9. 개발/작업 방식 철학 (GPT/Windsurf 사용 규칙)
	1.	문서 → 설계 → 코드 순서 강제
	•	새 단계(D43, D44 …) 시작 전:
	•	반드시 md 문서에 설계/목표/산출물 정의
	•	Windsurf/GPT에게도 “먼저 설계 md 작성 → 그걸 기준으로 코드 작성” 프롬프트 사용
	2.	기존 구조 재파괴 금지
	•	이미 통과된 D단계 모듈은 되도록 수정 금지
	•	수정 필요 시:
	•	영향 범위 분석
	•	테스트/문서 먼저 업데이트
	3.	테스트 우선
	•	“테스트 없이 엔진만 수정” 금지
	•	새로운 기능은 항상:
	•	테스트 파일 추가
	•	기존 회귀 테스트까지 돌려서 0 failure 확인
	4.	AI 도구에게 명확한 역할 분리
	•	Windsurf: 구체적 코드/리팩토링/테스트 구현
	•	GPT(이 채팅):
	•	전체 구조 설계
	•	규칙/철학 정리
	•	TO-BE 검증
	•	프롬프트/명령어 생성
	5.	정기적인 방향성 체크
	•	큰 단계(DX) 마다:
	•	“지금 TO-BE와 맞게 가고 있는지?”를 이 문서를 기준으로 재검토
	•	산으로 가면, 여기 문서에 맞춰 코스 수정

⸻

10. 결론: 현재 위치 & 최종 TO-BE
	•	이미 확보한 것들 (Done)
	•	D37: ArbitrageEngine + Backtest Skeleton
	•	D38: 단일 튜닝 Job Runner
	•	D39: 세션 플래너 + 결과 집계
	•	D29~D36, D41: K8s 기반 튜닝 파이프라인 (Advanced 인프라)
	•	D42: Exchange Adapter Layer (Base + Paper + Upbit/Binance 뼈대)
	•	앞으로 남은 핵심 (단일 아비트라지 완성 기준)
	1.	엔진 ↔ Exchange ↔ RiskManager 완전 통합 (Live 모드 최소 MVP)
	2.	실시간 시세 공급 레이어 (Upbit/Binance) – 안정적인 snapshot feed
	3.	Web UI 최소 버전 (상태/로그/PnL 보기 + 모드 전환)
	4.	Docker Compose로 전체 묶기
	5.	Paper 모드 장시간(예: 1~2주) 테스트로 안정성 검증
	6.	Live 모드 제한된 규모로 시범 운용

이 문서는 **프로젝트의 “최종 그림”과 “브레이크 포인트(완성 기준)”**을 고정하기 위한 기준점이다.
앞으로 GPT/Windsurf에 새로운 일을 시킬 때는,
항상 이 TO-BE를 기준으로 “지금 하는 작업이 어디에 속하는지”를 먼저 정하고 진행하면 된다.