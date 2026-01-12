XXX_ARBITRAGE_TRADING_BOT 구조 진단 및 리빌딩 로드맵
1. 현재 레포지토리 구조 (V1 vs V2)와 최근 커밋 흐름
V1 구조: 초기 버전(V1, Arbitrage-Lite)은 다수의 개별 스크립트로 동작하는 단일 전략 봇이었습니다. scripts/ 디렉토리에 run_*.py 스크립트가 65개 이상 존재하여 각 기능/실험마다 별도 실행 파일을 남발했고, 트레이딩 루프도 각 스크립트(예: run_live.py, run_paper.py 등) 내부에 중복 구현되어 있었습니다. 이러한 스크립트 난립과 중복 루프 구조로 인해 코드 일관성과 재사용성이 떨어졌습니다. V2 구조: V2에서는 기존 구조의 문제를 해결하기 위해 엔진 중심 재설계를 시작했습니다. 기존 V1 코드(base 엔진, 수집기 등)는 남겨둔 채 arbitrage/v2/에 새로운 코어 엔진 모듈들을 구축하고, 스크립트는 최소한의 얇은 래퍼(thin wrapper) 역할만 하도록 개편했습니다. 예를 들어 V2에는 ArbitrageEngine, Orchestrator, Metrics/Monitor, RunWatcher 등의 코어 컴포넌트가 추가되었고, V1의 PaperRunner 등이 담당하던 대부분의 로직을 이들로 이관했습니다. V2 단계에서 도메인 모델(fill_model.py, pnl_calculator.py), 트레이드 처리(trade_processor.py) 등 모듈이 신설되고, **자체 모니터링 RunWatcher(60초 하트비트 기반)**가 도입되는 등 주요 리팩토링이 이뤄졌습니다. 최근 커밋 흐름: D205 마일스톤을 전후로 커밋 이력을 보면 다수의 병렬 개선 작업과 핫픽스가 진행되었습니다. 예를 들어, D205-15-6a/b 등의 커밋에서는 실시간 PnL 계산 버그로 인한 **winrate 0%/100% 문제를 긴급 수정(HOTFIX)**하고, PaperRunner의 채결 가격 처리 오류를 수정하는 등 계획 외 수정이 발생했습니다. 동시에 D205-18 시리즈에서는 PaperRunner의 비대한 로직을 코어로 옮기고 Orchestrator를 도입하는 대규모 구조개편이 진행되었으며, 이후 Run 프로토콜 강화(D205-18-4R/R2) 커밋들을 통해 엔진 실행 중 이상징후 발생 시 프로세스 종료 및 증적 저장(Atomic Flush) 등의 운영 무결성 보강이 이루어졌습니다. 이러한 커밋 흐름은 로드맵상의 여러 과제가 동시다발적으로 처리되며 구조 개선과 버그 수정이 뒤섞여 진행된 모습을 보여줍니다. 그 결과 D205 이후 현재 V2 코드는 엔진/오케스트레이션 관련 핵심 모듈이 갖춰졌지만, 초기 로드맵 대비 분화된 우회 경로와 임시처리가 늘어난 상태입니다.
2. D205 이후 로드맵 분기 문제
D205 완료 시점 이후의 로드맵을 살펴보면, 계획의 분산과 과제 산재 문제가 드러납니다. 원래 V2 로드맵은 D201~D206 단계로 Upbit/Binance 커넥터 구현, 실시간 데이터 통합, 수수료/기회 탐지, PnL 리포트, 모니터링/배포 등의 순차적 과제를 정의했습니다. 그러나 D205 단계에서 내부 구조 보강과 긴급 수정 사항이 다수 발생하면서, 로드맵 진행이 비직선적으로 분기되었습니다. 예를 들어, PnL 리포트와 Grafana 대시보드 구축이라는 본래 D205 목표와 별개로, 엔진 신뢰성 강화를 위한 여러 sub-task(D205-15, D205-18 시리즈)가 동시 수행되었습니다. 이로 인해 로드맵 상의 우선순위와 작업 흐름이 복잡해졌고, 완료된 D205 시점에도 일부 계획(D201~D204 관련 기능)과 D206 선결조건 등이 미완인 채 남았습니다. 또한 SSOT(Single Source of Truth) 문서와 로드맵의 괴리도 문제로 지적됩니다. 로드맵은 원칙적으로 단일 SSOT 문서(D_ROADMAP.md)로 관리하도록 규정되었으나, D205 전후로 여러 이슈에 대응하면서 SSOT 규칙 문서, Evidence 로그, 개별 디자인 문서 등에 부분적인 계획/현황이 흩어졌습니다. 그 결과 *“로드맵이 과도하게 분기되고 산재”*되어 팀원들이 현황을 한눈에 파악하기 어려운 상황입니다. 이러한 분산을 해소하고 단일한 체계로 로드맵과 설계를 관리할 필요성이 대두되고 있습니다.
3. 스크립트 중심 구조의 한계와 엔진 중심 통합 설계 필요성
V1의 스크립트 중심 아키텍처는 유지보수성과 확장성 측면에서 큰 한계를 드러냈습니다. 각 실행 스크립트가 자체 로직과 루프를 포함하면서, 새로운 실험이나 기능 추가 시마다 별도 스크립트를 복사/수정하는 방식이 반복되었습니다. 이로 인해 코드 중복과 불일치가 누적되고, 운영 프로토콜이 스크립트마다 달라지는 문제가 생겼습니다. 실제 D206 계획 문서에서도 *“V1: 65+ 개의 run 스크립트 난립, Runner가 자체 루프 보유”*라는 문제점을 인정하고 있습니다. 엔진 중심 통합 설계는 이러한 문제의 해법으로 제시됩니다. 하나의 일원화된 메인 엔진 루프가 모든 컴포넌트를 통합 구동하고, 개별 스크립트는 엔진을 호출하는 얇은 인터페이스로 축소되어야 합니다. V2에서 진행된 Orchestrator 도입과 PaperRunner 슬림화는 이러한 방향으로의 전환 사례입니다. 구체적으로, PaperRunner 내 루프를 제거하고 Orchestrator가 주요 실행 흐름을 관장하도록 변경하여 “Engine에 유일한 루프, Runner는 얇은 막” 구조를 달성했습니다. Acceptance Criteria를 통해 보면, Orchestrator/RuntimeFactory 생성과 6개의 코어 모듈 분리, DIP(Dependency Inversion Principle) 준수 등을 완료하여 핵심 로직이 엔진(Core) 레이어로 모두 이동되었습니다. 그 결과 PaperRunner 코드는 149줄로 대폭 줄고(-88%), 14개의 로직 함수가 모두 코어로 이양되어 Runner에는 설정 및 호출만 남는 형태가 되었습니다. 엔진 중심으로 재구성하면 운영 프로토콜의 일관성이 확보됩니다. 모든 모드(백테스트, 페이퍼, 라이브)가 동일한 엔진 루틴을 따르므로 모니터링과 제어가 단일 지점에서 이루어집니다. 예컨대 Hummingbot 등의 상용 수준 오픈소스도 중앙 Clock 컴포넌트가 주기적인 틱 신호로 모든 전략 및 마켓 연결자를 구동하며 일관된 사이클을 유지합니다
. 우리 시스템도 Orchestrator/Engine을 통해 이와 유사한 중앙제어 루프를 갖추게 되었고, 이는 전략 로직 추가나 변경 시 각 스크립트를 개별 수정하는 대신 엔진 모듈만 수정하면 되는 구조로 개선되었습니다. 또한 엔진 중심 구조는 확장성과 테스트 용이성을 높입니다. 엔진 내부에서 데이터 수집→기회포착→주문생성→체결처리 흐름을 모듈화해두면, 새로운 거래소나 전략을 추가할 때 해당 모듈만 교체/확장하면 됩니다. Freqtrade 등의 봇도 데이터 수집, 처리 로직, 주문 실행을 레이어별로 모듈화하여 한 층의 수정이 다른 층에 영향없이 가능하도록 합니다
. 현재 V2의 OpportunitySource, IntentConverter, TradeProcessor 등의 구성은 이런 관심사 분리를 반영한 것으로, 향후 새로운 전략 알고리즘이나 상품을 도입할 때 엔진 구조를 유지한 채 모듈만 추가하면 되는 유연성을 제공합니다.
4. 상용 트레이딩 봇 사례의 운영 프로토콜 및 인프라 베스트 프랙틱스
운영 프로토콜: 전문 트레이딩 시스템들은 실패 허용 범위가 거의 없기 때문에 운영 절차와 프로토콜을 매우 엄격히 설계합니다. 예를 들어, Jane Street 같은 기관의 시스템은 주문 하나하나의 상태 추적과 예외 처리, 장애 발생 시 롤백/알림 체계를 갖춰 어떤 경우에도 일관된 상태 보장과 자산 보호가 이루어집니다 (예: 주문 취소 실패 시 재시도 및 포지션 정리 등). 오픈소스인 Hummingbot도 모든 주문을 내부적으로 트래킹하여 일부 API 응답 누락이나 지연이 있어도 주문 상태를 잃지 않고, 중복 주문이나 유실 주문이 없도록 설계되었습니다
. 또한 API 지연/다운 시에도 기능 저하(degrade) 모드로 안전하게 동작을 지속하거나 중단할 수 있게 합니다
. 이러한 사례들은 Fail-safe 운영 프로토콜의 중요 요소들을 시사합니다:
일관된 상태 추적: 우리 봇도 각 거래 주문과 포지션을 DB와 메모리 양쪽에 추적하고, 주문 시도에 대한 응답 실패 시 일정 재시도 횟수 후 알림 또는 프로세스 일시정지를 하도록 해야 합니다.
자동 중단 및 정리: 시스템적 오류나 비정상 패턴 감지 시 사람 개입 없이도 특정 모듈을 재시작하거나 전체 트레이딩을 안전하게 중단하는 메커니즘이 필요합니다. V2에서 도입한 RunWatcher가 그 예로, 심박 신호나 트레이드 발생 빈도를 감시하여 임계 조건에 도달하면 자체적으로 프로세스를 Fail-fast 종료시킵니다. 향후 이 부분을 더욱 발전시켜, 중요한 예외상황(예: 연속된 주문 실패, API 응답 지연 등)에도 엔진이 무한정 대기하거나 잘못된 동작을 이어가지 않고 즉시 안전 정지 및 알림을 수행하도록 해야 합니다.
Graceful Shutdown: 갑작스런 종료에도 데이터 불일치나 홀딩 자산 문제가 없도록 종료 시퀀스를 정의해야 합니다. 예를 들어 RunWatcher 신호 → Orchestrator 루프 중단 → Evidence(증거자료) 저장 → 연결된 자원 해제의 단계로 우아한 종료를 구현하는 것이 바람직합니다. 현재 커밋에서도 Orchestrator의 finally 블록에서 Atomic Evidence Flush를 수행하고, 종료 직전에 RunWatcher를 멈추는 처리가 추가되어 이러한 절차의 기초를 마련했습니다. 이를 더욱 정교화해 SIGINT/SIGTERM 시그널 핸들링까지 포함한 정식 종료 프로토콜을 수립할 필요가 있습니다.
컨테이너 배포: 최신 트레이딩 봇들은 대부분 Docker 등의 컨테이너로 배포되어 일관된 환경 재현성과 확장성을 확보합니다. Hummingbot의 공식 배포도 Docker Compose를 사용해 봇, DB, 대시보드 등을 손쉽게 올릴 수 있게 하며
, 우리 프로젝트 역시 이미 docker-compose 기반의 멀티 컨테이너 운영을 부분 도입한 상태입니다. Runbook에 따르면 arbitrage-engine, arbitrage-redis, arbitrage-postgres 3개 컨테이너를 함께 구동하여 엔진, 캐시, 영속저장소를 분리 운영 중이며, 각 컨테이너의 상태를 수시로 확인하고 있습니다
. 이는 장애 격리와 확장에 유리한 구조로서 지속 유지되어야 합니다. 나아가 Prometheus, Grafana 컨테이너까지 포함한 모니터링 스택을 붙여 실시간 메트릭 수집과 시각화를 운영환경에 통합할 계획이며, 실제 로드맵 D205 항목에 Grafana 대시보드 구축이 명시되어 있습니다. 이러한 인프라 구성은 상용 시스템 수준의 가시성과 추적성을 줄 것으로 기대됩니다. 로깅 & 모니터링: 운영 중 발생하는 이벤트와 지표를 체계적으로 로깅하고 모니터링하는 것은 상용 수준 완성도의 필수 요건입니다. Freqtrade 같은 봇은 텔레그램/웹 UI로 상태를 실시간 확인하도록 하고, Hummingbot은 각 전략 별로 PnL, 주문 상황을 주기적으로 로그에 남겨 사용자가 모니터링할 수 있게 합니다. 우리 시스템의 경우 이미 로그 기반 모니터링 절차가 수립되어 있습니다. Runbook에서는 매 시간 최근 한 시간치 로그에서 “ERROR”/“CRITICAL” 키워드를 grep해서 오류 빈도를 점검하고, 오류 횟수 기준으로 조치 기준을 안내하고 있습니다
. 또한 매일 주요 지표(분당 트레이드 수, 에러 수, 지연 시간 등)를 점검하고 이상치 발생 시 별도 시나리오를 따라 대응하도록 정의되어 있습니다
. 이처럼 체계적인 로그 점검과 지표 모니터링을 이어가는 한편, 향후에는 보다 자동화된 모니터링 고도화가 제안됩니다:
애플리케이션 레벨 헬스 체크 엔드포인트 구현 (현재 healthcheck.py로 수동 확인하는 것을, 주기적 헬스 체크 스크립트/HTTP로 노출)
.
경고/알람 시스템 강화: RunWatcher나 엔진이 비정상 종료되면 즉시 DevOps팀에 슬랙/이메일 알람을 보내고, 중요 이벤트(예: 손실 한도 초과 등)도 실시간 알림을 트리거하도록. 현재 Kubernetes 환경에서는 send_k8s_alerts.py로 경고를 전송한 전례가 있으므로
, 이를 Docker 환경에도 적용하거나 CloudWatch/Sentry 같은 도구를 도입할 수 있습니다.
대시보드: Grafana 등을 통해 주요 KPI(PnL, 승률, 지연, 에러율 등)를 실시간 대시보드화하고, 과거 추세를 누적 분석해 성능 회귀나 이상 패턴을 시각적으로 파악할 수 있게 합니다. D205에서 일부 PnL 리포트 및 Grafana 연계를 시작했으므로 이를 지속 발전시키면 됩니다.
Fail-Safe 설계: Fail-Safe란 어떠한 실패 상황에도 시스템이 안전한 방향으로 동작하거나 최소한 경고 후 정지하는 것을 의미합니다. 상용 트레이딩 시스템에서는 전형적으로 다중 안전장치를 사용합니다. 예를 들어, 주문 실행 전후로 포지션 불일치 검사, 손실 한도 체크, 외부 서비스 응답 타임아웃 설정 등이 그것입니다. 우리 엔진도 D205-18-4R2에서 이러한 Fail-Safe 원칙을 도입했습니다. 구체적으로 Warn->Fail 승격 원칙을 적용하여 이전까지 경고 수준에 그쳤던 조건(예: 실행 시간이 예상 대비 초과, 하트비트 누락 등)을 이제 즉시 Fail 처리하여 프로세스 종료하도록 했고, 종료 시 Exit Code를 상위 계층까지 전파하여 배포 스크립트나 운영자가 즉시 인지할 수 있게 했습니다. 또한 DB 데이터 무결성 검사(예: 거래 종결 건수와 DB 입력 건수의 대략적 일치 여부)도 수행해 불일치 시 Fail 처리하고, 무조건 Evidence 저장을 보장함으로써 사후 원인 분석에 필요한 데이터를 남기도록 했습니다. 향후 Fail-Safe를 더욱 강화하기 위해:
리스크 제한: 설정된 최대 포지션 규모, 일별 최대 손실 등을 엔진 차원에서 강제해 한계를 넘을 경우 자동 청산 또는 정지를 실행.
이중 확인(checks and balances): 중요 연산(예: 매수/매도 가격 결정 등)에 대해 독립적인 계산을 병행해 결과 불일치 시 경고를 내거나 사람 승인 후 진행.
테스트넷/모의주문 연동: 거래소 API의 응답 이상 여부를 확인하기 위해 정기적으로 테스트 주문(혹은 testnet)을 실행해보고 실패율을 측정, 높아지면 알고리즘 속도를 늦추거나 일시정지.
시그널 처리: 장기 운영 시 프로세스 종료나 재시작 등의 시그널 처리가 중요합니다. 예를 들어 시스템 업그레이드나 장애로 컨테이너를 내릴 때, SIGTERM을 수신한 엔진은 즉시 새로운 주문을 멈추고 진행 중인 작업을 마무리한 뒤 종료해야 합니다. 현재 Runbook에는 수동으로 docker-compose down으로 서비스를 내리는 절차가 있지만, 이를 자동화하려면 애플리케이션 레벨에서 시그널 핸들러를 구현해야 합니다. Python의 signal 모듈로 SIGINT/SIGTERM 이벤트를 잡아 Orchestrator에 안전중지 플래그를 주고 RunWatcher를 해제하는 등의 처리를 넣으면, 사람 개입 없이도 컨테이너 종료 시 안전하게 서비스를 내릴 수 있습니다. 이러한 Signal Handling은 24/7 무인 운영에 필수적인 요소입니다. 요약하면, 엔진 중심 구조 + 컨테이너 인프라를 갖춘 우리 시스템은 상용 봇들의 모범 사례와 상당 부분 궤를 같이합니다. 앞으로 남은 것은 각 요소(프로토콜, 모니터링, Fail-safe 등)를 더욱 다듬어 기술적 효율성과 무결성, 운영 편의성을 최고 수준으로 끌어올리는 것입니다.
5. Docker 컨테이너화 및 운영 환경 시뮬레이션 기능
전체 환경 컨테이너화: 현재 V2에서 Docker Compose로 엔진과 기본 인프라(데이터베이스, Redis 등)를 컨테이너화한 것은 매우 고무적입니다. 이를 한 걸음 더 나아가 운영 환경을 완전 동일하게 로컬/테스트에 재현하는 방향을 추구해야 합니다. 구체적으로:
Infra 계층 분리: 이미 분리된 DB(PostgreSQL), 캐시(Redis) 외에, 향후 Prometheus, Grafana, Adminer 등의 관리 도구도 Compose에 포함하여 개발/운영 환경의 구성이 동일하도록 합니다
. 예컨대 개발자는 로컬에서 docker-compose up만 하면 운영과 동일한 서비스들이 떠서 테스트할 수 있게 됩니다.
환경 변수 및 설정: .env.example 또는 config 파일을 통해 각 환경별 변수(API 키, 엔드포인트, 모드 등)를 관리하고, 이미지 빌드시 이를 주입받도록 합니다. 현재 .env.live.example 등이 repo에 있고 V2용 runtime config SSOT 작성이 진행 중인 것으로 보입니다. 이를 확장하여 .env.dev, .env.prod 등 환경 구분 설정과 그에 따른 config.yml 로딩 로직을 구현하면 환경 전환이 간편해집니다.
Immutable 이미지: 엔진 애플리케이션을 단일 Docker 이미지로 빌드하여 어디서나 동일 버전이 재현되게 합니다. Compose 환경에서는 애플리케이션 컨테이너를 rolling update하거나 k8s 배포도 가능하도록, Dockerfile을 최적화(캐시 활용, 경량화)하고 CI에서 이미지 태깅/푸시 파이프라인을 구축하면 좋습니다.
운영 환경 시뮬레이션: 리얼 마켓과 동일한 조건을 가상으로 재현해보는 것은 전략 검증과 회귀 테스트에 필수입니다. 이를 위해 두 가지 시뮬레이션 레벨을 고려합니다:
Paper Trading 모드: 실제 거래소에 주문을 보내지 않고, 자체 로직으로 체결을 흉내내는 모드입니다. V1에서도 run_paper.py로 제공되었고 V2에서도 PaperRunner/Orchestrator 조합으로 구현되어 있습니다. 앞으로 이 Paper 모드를 더 현실감 있게 만들 필요가 있습니다. 예를 들어 체결 가격/체결 여부를 실제 주문장 데이터 기반으로 계산하도록 개선하면, 현재는 즉시체결 가정으로 처리하는 부분을 고쳐 슬리피지나 체결 지연까지 시뮬레이션할 수 있습니다. 이를 위해 과거 주문장 스냅샷을 리플레이하거나, HFT 논문들처럼 이벤트드리븐 체결 엔진을 내장하는 방법도 검토할 수 있습니다. 또, 실제 API와 동일한 응답 형식을 주는 Mock Exchange 서버를 두고 엔진이 그 API를 대상으로 거래하도록 하면 엔진 입장에서는 진짜 거래소와 통신하지만 백엔드에서는 가상 체결이 일어나게 할 수도 있습니다 (CCXT 등의 sandbox 활용 또는 간단한 FastAPI 모킹).
백테스팅 모드: 과거 데이터로 엔진을 돌려보는 모드로, D37~D40 단계에서 구현된 arbitrage_backtest.py와 튜닝 세션들이 이에 해당합니다
. 이 백테스팅 기능을 계속 활용하되, V2 엔진과 통합하는 작업이 필요합니다. 즉, 현재 V2 ArbitrageEngine이 실시간으로 동작하지만, 이를 과거 데이터 입력으로도 동일하게 구동할 수 있게 인터페이스를 맞추는 것입니다. 예컨대 Engine에 feed_historical_data(data_stream) 메소드를 두어 실시간 수집기 대신 과거 CSV나 DB 데이터를 입력받아 돌릴 수 있게 하면, 코드 수정 없이도 백테스트가 가능한 구조가 됩니다. Freqtrade 등은 동일 엔진코드로 실시간 매매와 백테스트를 모두 수행하는데, CLI 옵션이나 config로 모드만 구분하도록 되어 있습니다. 우리도 --mode live/paper/backtest 같은 옵션으로 엔진이 입력 소스만 바꿔치기하여 돌도록 통합할 수 있습니다.
시뮬레이션 환경 검증: 컨테이너화된 시뮬레이션을 CI에 통합하면 릴리즈 전 자동검증을 달성할 수 있습니다. 예를 들어 GitHub Actions 등으로 Docker Compose up -> 백테스트 1일치 실행 -> 결과 검증까지의 시나리오를 돌려보면, 코드 변경이 기존 전략 성능이나 수익률에 미치는 영향을 바로 파악 가능합니다. 현재 SSOT_RULES에서 성능 기준선(예: VaR 계산 0.7ms 등)을 정하고 성능 저하 시 원인 분석을 요구하는 규칙이 있듯이
, CI의 백테스트 결과로 주요 지표(PnL, 승률, Max DD 등)를 산출해 이전 커밋과 비교함으로써 성능 또는 수익률의 회귀(Regressions)를 자동 탐지하는 체계를 마련할 수 있습니다. 이는 상용 금융사들이 필수적으로 하는 프리-프로덕션 검증 단계로서, “상용 그 이상의 완성도”를 추구한다면 적극 도입할 가치가 있습니다. 정리하면, 컨테이너화와 시뮬레이션은 개발에서 프로덕션까지 환경 차이를 최소화하고, 전략의 과거/가상 검증을 쉽게 해주는 수단입니다. V2에서 이미 기반을 갖췄으므로 향후 모든 구성요소의 컨테이너화와 엔진-시뮬레이션 통합을 통해 신뢰성과 개발 생산성을 더욱 끌어올려야 합니다.
6. 현재 V2 구조에서 재사용 가능한 컴포넌트 (V1 포함)
V2로의 리팩토링 과정에서 기존 V1의 유용한 구성요소들을 상당 부분 계승하거나 참조하고 있습니다. 향후 리빌딩 로드맵을 설계할 때도, 검증된 컴포넌트는 재사용하고 불완전하거나 중복된 부분만 개선하는 것이 효율적입니다. 재사용 가능/필요한 주요 컴포넌트를 정리하면:
거래소 연결 및 데이터 수집 로직: V1에서 사용했던 Collector/Exchange 모듈은 이미 실전 검증된 API 통신, 시세 변환 로직을 담고 있습니다. Arbitrage-Lite README에도 **“기존 앙상블 트레이딩 봇의 Collector/Exchange 코드 재사용”**이 명시되어 있었고
, 실제로 V2 개발 초기에 이 코드를 Thin Wrapper 형태로 붙여넣는 TODO가 존재했습니다. 현재 V2에서 Upbit/Binance 어댑터 구현을 D201 단계로 계획하고 있는데, 이때 V1 코드의 해당 부분을 구조만 맞춰 이식하면 신속히 개발할 수 있을 것입니다. 주의: V2 코드에서 V1 모듈을 직접 import하는 것은 금지되어 있습니다. 따라서 V1의 핵심 로직을 복사해와 V2 네임스페이스에 맞게 변경하되, V1 코드는 그대로 보존하는 방식(점진적 마이그레이션)을 따라야 합니다.
리스크 관리 및 포트폴리오 로직: V1(D1~D15 사이)에 이미 **정량적 리스크 관리 모듈(risk_quant.py)**과 포트폴리오 최적화 모듈(portfolio_optimizer.py), **변동성 예측 ML 모듈(volatility_model.py)**까지 구현되어 있었습니다
. 이들은 Arbitrage 단일 전략보다는 포트폴리오 전체나 멀티자산에 관련된 코드이지만, 그만큼 고도화된 기능입니다. V2 리빌딩 시 당장은 단일 전략에 집중하더라도, 장기적으로 다중 페어 혹은 멀티전략으로 확장할 여지를 고려한다면 해당 모듈들을 V2 구조에 맞게 통합하는 것이 좋습니다. 예컨대 risk_quant의 VaR, MDD 계산 함수를 V2의 Metrics에 흡수하거나, volatility_model을 사용해 실시간 변동성 추정치를 리스크 한도로 활용하는 등의 응용이 가능합니다. 이미 V1 코드로 안정성이 검증된 만큼, V2에서 재사용 시에도 큰 문제 없이 동작할 것으로 보입니다. 다만 성능 기준선을 깨지 않도록 (예: 10,000개 데이터 VaR 0.7ms
) V2 엔진에 맞게 최적화 여부는 확인해야 합니다.
테스트 시나리오와 데이터: V1에서 작성된 다양한 테스트 (tests/ 디렉토리의 D37~D40 등)와 시나리오 config 파일들(e.g., configs/d17_scenarios/*.yaml에 여러 시장 상황 정의
)은 매우 귀중한 자산입니다. 이들은 과거 버전 코드에 맞춰 작성되었지만, 시나리오 자체는 엔진 리빌딩 후에도 유효합니다. 그러므로 리빌딩 후 신규 엔진에 대해 기존 시나리오 테스트를 재활용하여 회귀검증을 수행해야 합니다. 예컨대 basic_spread_win.yaml, choppy_market.yaml 등의 케이스를 V2 엔진의 백테스트 입력으로 사용해, V1 결과와 비교함으로써 성능이 향상되었는지 혹은 문제는 없는지 확인할 수 있습니다. 테스트 코드 역시 마찬가지로, D37_arbitrage_mvp 테스트는 V2 엔진의 MVP 동작 검증에 응용될 수 있습니다
. 리빌딩 로드맵에 이 기존 테스트/시나리오 활용 계획을 포함시키면 품질을 담보하기에 용이합니다.
운영 도구 및 문서: scripts/ 아래 존재하는 유용한 운영 스크립트들도 선별적으로 V2에서 계속 사용하거나 개선할 수 있습니다. 예를 들어 k8s_alerts.py (k8s 환경 알림), k8s_monitor.py 등 쿠버네티스 관련 스クリプ트들은 Docker 환경으로 전환되면서 일부 불필요해졌지만, 서비스 헬스 체크, 이벤트 로깅 로직 등은 재사용할 수 있습니다. 또한 send_k8s_alerts.py의 로직을 일반화하여 Docker 환경에서도 쓸 수 있는 경고 발송 툴로 바꾸거나, gen_d29_k8s_jobs.py의 아이디어를 빌려 배치 작업 자동화 스크립트를 작성하는 등 응용이 가능합니다. 문서의 경우도, V1 시절 작성된 수많은 설계/레포트 문서(D-docs 시리즈)가 있습니다
. 이 중 개념 재사용이 가능한 부분(예: ZoneProfile 설계, Tuning 방법론 등)은 V2 문서에 통합하거나 레퍼런스로 남겨 지식 축적을 이어가야 합니다.
참고: V1과 V2 코드를 당분간 공존시키는 전략은 옳았습니다. 혹시 V2에 치명적 버그가 있을 때 V1 방식으로 롤백하거나 참고할 수 있기 때문입니다. 그러나 리빌딩 로드맵 완료 시점에는 V1를 완전히 대체할 계획인 만큼, 이행 기간이 끝나면 V1 코드는 폐기하도록 합니다. 그 전까지는 V1의 중요 컴포넌트들을 단계적으로 V2로 이식한 후, V1와 동일한 동작을 V2에서 달성하면 V1를 deprecated 표시하는 식으로 진행하면 무리 없을 것입니다.
7. 새로운 운영 프로토콜 정의 필요성 (SSOT_RULES와의 관계)
D205 단계에서 운영 프로토콜(런 프로토콜) 강화 작업이 이루어지며, 암묵적이던 많은 운영상의 규칙들이 코드와 SSOT 문서에 규정화되었습니다. 예를 들어 “WARN시 Fail 처리, Exit Code 엄격 전파, Evidence 무조건 기록” 등의 원칙이 SSOT_RULES.md Section N (Operational Hardening)에 추가되었고, Orchestrator.run에 그 구현이 반영되었습니다. 하지만 이러한 내용이 현재는 여러 커밋 메시지와 SSOT_RULES의 일부 섹션 등에 흩어져 있어, 전체적인 운영 프로토콜을 한눈에 이해하기 어렵습니다. 따라서 새로운 운영 프로토콜 정의서를 작성하여 운영 절차와 규칙을 일원화할 필요가 있습니다. 운영 프로토콜 정의서에 포함될 내용:
엔진 실행 단계와 조건: 예를 들어 부팅 → 프리플라이트 체크 → 메인 루프(심박 체크, DB 체크 포함) → 정상 종료 또는 비정상 중단 처리 등 엔진의 생명주기 단계를 정의하고, 각 단계에서 어떤 조건을 만족해야 넘어가는지 명시합니다. D205-18-4R2 작업에서 정의된 Wallclock 기간 오차 ±5% 이내, Heartbeat density 일정 기준 이상, DB Invariant 일치 여부 등이 이러한 조건에 해당하므로, 이러한 검증 로직을 프로토콜 문서에 “운영 중 검증 체크리스트” 형태로 포함시킵니다.
이상 상황 분류와 대응: 운영 중 발생할 수 있는 상황을 분류하고 프로토콜을 정의합니다. 예컨대 경고 (Warn)과 실패(Fail)의 기준, 일시정지 vs 완전중단 결정 로직, 자동 재시작 조건, 휴먼 인터벤션 필요 조건 등을 기술합니다. 이를테면 연속 3회 이상의 Heartbeat FAIL 발생 시 자동 재시작, DB 불일치 Fail 시 즉시 중단 및 알람 발송, API 타임아웃 5회 누적 시 전략 일시 정지 등 구체적인 룰을 정해 둘 수 있습니다. 현재 SSOT_RULES에 WARN=FAIL 원칙이나 Exit Code 전파 등이 규칙으로 추가되었지만, 보다 세밀한 시나리오별 대응은 운영 프로토콜에 위임하는 것이 적절합니다.
Fail-safe 트리거 및 후속조치: Fail-safe 기전이 발동되었을 때 어떤 후속조치를 취할지도 프로토콜에 포함합니다. 예를 들면 “프로세스 강제종료 시 반드시 Evidence 디렉토리에 로그/결과물 아카이브 후 종료”, “재시작 시 마지막 성공 시점부터 재개” 혹은 “사람 검토 전까지 재개하지 않음” 등의 방침을 결정해 둡니다. D205 커밋에서는 Atomic Evidence Flush를 통해 증거를 남기도록 했으므로, 이에 더해 자동 재기동 여부는 현재 Runbook 상 인간이 수동으로 서비스 재시작을 하는 절차가 있으나
, 장기적으로는 Supervisor나 cron을 통해 자동 재기동할지 여부까지 정책으로 정해둘 필요가 있습니다.
운영상 체크리스트와 권한: 누구(혹은 어떤 프로세스)가 어떤 권한으로 프로토콜을 실행하는지도 문서화합니다. 예컨대 일일 점검은 Operator가, 장애 대응은 On-call Engineer가 맡으며 각각 참고할 섹션을 지정하는 식입니다 (이 내용은 이미 Runbook의 Roles에 일부 나와 있습니다
). 프로토콜 문서에서는 시스템 내부 주체(예: RunWatcher, Orchestrator)와 휴먼 주체 간의 상호작용도 다룹니다.
SSOT_RULES와의 분리 여부: 원칙적으로 한 프로젝트 내 SSOT 문서는 단일해야 하므로, 현재도 SSOT_RULES.md와 D_ROADMAP.md를 분리 관리하는 것 이상은 지양하고 있습니다. SSOT_RULES.md는 시스템의 헌법과 같은 위치로, 코딩 컨벤션부터 운영 원칙까지 핵심 규칙들을 번호별로 정의해 둔 문서입니다. 여기에 운영 프로토콜 세부사항을 모두 넣으면 너무 방대해질 우려가 있습니다. 그러므로 SSOT_RULES.md에는 운영 프로토콜의 핵심 원칙만 기록하고, 상세 절차와 시나리오는 별도 문서로 분리하는 것이 합리적입니다. 예를 들어 SSOT_RULES.md에 “모든 Warn은 Fail로 간주하여 프로세스가 종료돼야 한다”, “실행 중 핵심 지표 무결성 검증 실패 시 재시작 금지” 등의 룰 조항을 추가하고, 구체적인 구현과 체크방법은 “운영 프로토콜 가이드” 문서를 작성하여 거기에 서술한 뒤 SSOT_RULES에서 해당 문서를 참조하도록 하면 됩니다. 이렇게 하면 SSOT_RULES는 불변의 원칙 중심으로 간결하게 유지되고, 프로토콜 세부사항은 경우에 따라 업데이트하기 용이한 별도 가이드로 관리할 수 있습니다. 정리하면, 새 운영 프로토콜 정의는 D205 이후 개선된 운영 방식들을 공식화하고 향후 일관되게 지킬 수 있게 해준다는 점에서 반드시 추진해야 합니다. 이는 리빌딩 로드맵의 중요한 산출물 중 하나이며, 최종적으로 Runbook(운영자 매뉴얼), SSOT_RULES(원칙 모음), Protocol Spec(절차 세부) 세 문서가 유기적으로 연결되어 상용 수준의 운영 지침 체계를 갖추게 될 것입니다.
8. D205 이후 리빌딩 로드맵 제안
위 분석을 바탕으로, D205 이후의 개발을 기술적 완성도와 운영 효율을 극대화하는 구조로 재편하기 위한 로드맵을 제안합니다. 이 로드맵은 기존 문제점 해결 → 구조개선 → 고도화 순으로 단계별 추진됩니다. ① 문제점 명확화 및 정리 (단기) – 먼저 현재 산재된 로드맵 조각들과 구조적 문제들을 명시적으로 정리합니다.
로드맵 SSOT 정비: 현 시점까지 완료된 사항과 남은 과제를 D_ROADMAP.md 한 곳에 최신 상태로 업데이트합니다 (이미 UTF-8 인코딩 복구 및 일부 정리는 완료됨
). 분기된 계획은 통합하거나 우선순위를 재조정하여, 모든 팀원이 합의된 하나의 진실된 로드맵을 참고하도록 합니다.
기존 시스템 진단 리포트: 본 분석과 유사하게, V1의 한계와 V2 진행사항, 발견된 이슈를 문서화하여 팀 내부 공유합니다. 특히 “V1 스크립트 난립”, “엔진-러너 분리 미흡”, “핫픽스로 인한 일정 지연” 등을 솔직히 짚어주고, 왜 리빌딩이 필요한지 인식 합의를 이룹니다.
SSOT_RULES 개정 준비: SSOT_RULES.md에 추가해야 할 규칙(예: Warn=Fail, Engine 중심 구조 등)을 식별하고 초안을 마련합니다. 이를 통해 이후 단계를 진행하며 규칙 위반을 방지하는 가이드로 삼습니다.
② 엔진 중심 아키텍처 완성 (중기) – D206 이전에 엔진-러너 구조전환 작업을 완료하고 핵심 엔진을 확고한 상태로 만듭니다.
엔진 단일 루프화 완료: Orchestrator+Engine 기반으로 PaperRunner, LiveRunner 등 모든 Runner의 루프를 제거하고, Runner들은 엔진 설정 및 결과 취합만 수행하게 합니다. 현재 PaperRunner는 달성되었고, LiveRunner도 유사하게 Orchestrator 또는 Engine을 활용하도록 개편합니다.
거래소 어댑터 통합: D201~D202 과제로 남은 Upbit/Binance Adapter 구현을 완료하여 V2 엔진에 실제 시세 연동 및 주문 실행 기능을 붙입니다. 이때 V1 Exchange 모듈 코드를 최대한 활용하되, V2의 OrderIntent/Adapter 인터페이스에 맞춰 리팩토링합니다. 완료되면 실제 환경에서 V2 엔진으로 한 사이클 매매가 가능해집니다.
리스크/모니터링 모듈 엔진편입: V1의 risk_quant, 포트폴리오, ML 모듈 중 즉시 활용할 부분(특히 단일 전략이라도 필요한 손실제한, 이익실현 등 리스크관리)을 Engine에 통합합니다. 또한 RunWatcher를 개선해 여러 종류의 건강검진(Heartbeat, Trade 속도, PnL 한도 등)을 수행하도록 확장합니다. 엔진 코드에는 이러한 검사결과를 반영하여 자동 Pause/Resume 기능도 고려합니다. 이 단계에서 엔진 안정화 테스트로 수 시간짜리 Paper/Llive 시뮬레이션을 돌려보고, 문제 발생 시 모두 수정해 엔진 코어를 완성시킵니다.
③ 운영 프로토콜 수립 및 문서화 (중기) – 엔진 개선과 병행하여 운영 프로토콜/환경 정비를 진행합니다.
운영 프로토콜 문서 작성: 위 7번 항목에서 논의한 새로운 운영 프로토콜 가이드 문서를 초안 작성하고, 관련 규칙을 SSOT_RULES.md에 추가합니다. 예컨대 “Heartbeat Fail 3회 시 자동중지” 등을 규칙화하고, 실제 코드 RunWatcher에도 임계값 3으로 설정합니다. 프로토콜 문서는 Runbook과 겹치지 않도록 시스템 내부 동작 위주로 서술하고, Runbook은 운영자 대응 절차 위주로 유지해 두 문서가 상호보완되게 합니다.
컨테이너/배포 파이프라인 정비: Docker 이미지 빌드와 Compose 구성을 확정짓습니다. infra/docker-compose.yml에 현재 운영 중인 서비스들을 모두 명시하고 README/Runbook에 배포 및 종료 절차를 업데이트합니다. D206 단계의 목표인 “배포 런북 완성”도 이 시점에 달성합니다. 또한 CI에 Docker 빌드 및 간단 헬스체크를 추가해 배포 신뢰성을 높입니다. 쿠버네티스 사용 가능성이 남아있다면, K8s manifest도 업데이트하고 (D29~D36 스크립트 참고), 그렇지 않다면 관련 코드는 정리합니다.
모니터링/로그 통합: Prometheus 노출용 메트릭 엔드포인트를 엔진에 구현하거나, 기존 로그를 Filebeat/Fluentd 등으로 수집해 ElasticSearch에 적재하는 등 로그/메트릭 수집 인프라를 구축합니다. 작은 팀 규모를 감안하면, Grafana의 Loki 등의 로그 대시보드나 CloudWatch와 연동도 고려할 수 있습니다. 핵심은 운영 중 발생하는 이벤트를 실시간으로 중앙 모니터링할 수 있게 만드는 것입니다. 이 작업을 통해 D205 목표였던 Grafana 대시보드 구성을 실제 완성합니다.
④ 기능 확장 및 성능 최적화 (중장기) – 엔진이 안정화되고 운영체계가 잡히면, 상용 수준 그 이상의 기능들을 추가하여 경쟁력을 높입니다.
다중 페어/전략 지원: 구조적으로 멀티페어, 멀티전략을 수용할 수 있도록 엔진을 확장합니다. 예를 들어 현재는 Upbit-바이낸스 1페어 아비트라지에 특화되어 있지만, 엔진 모듈을 일반화하여 설정 파일로 여러 심볼쌍을 등록하면 루프 내에서 각각 처리 가능하도록 만들 수 있습니다. 병렬성은 고려해서, 싱글 쓰레드 루프에 여러 페어를 넣으면 지연이 커질 수 있으므로, 멀티쓰레드 또는 비동기 방식으로 Engine 인스턴스를 심볼별 돌리는 구조도 연구합니다. 상용 봇들은 다수 전략을 동시에 구동할 수 있는 경우가 많으므로, 우리도 장차 엔진 하나로 여러 전략 플러그인 로딩이 가능하도록 설계할 수 있습니다. (물론 이는 우선순위 상 후순위로 두고, 단일 전략 완성도가 확보된 후 진행합니다.)
고급 주문 실행 및 최적화: 제인스트리트와 같은 기업은 주문 실행 최적화를 통해 수익을 극대화합니다. 우리도 향후 스마트 주문 라우팅, 슬리피지 최소화 알고리즘 등을 도입할 수 있습니다. 예를 들어 목표수량을 한 번에 주문내지 않고 분할주문 알고리즘 적용, 또는 다중 거래소 간 재원활용 최적화 (한 거래소에서 번 자금으로 다른 거래소 손실 보전 등)를 고려할 수 있습니다. 이러한 기능을 추가할 때도 엔진 구조가 정교하면 모듈 추가만으로 구현 가능할 것입니다.
성능 튜닝: 거래 빈도가 높아질 경우를 대비해 엔진 성능 튜닝을 지속합니다. Python으로 작성된 엔진은 GIL 등의 한계가 있으므로, 필요시 Cython이나 PyPy, 또는 Rust로 성능critical한 부분을 작성하는 것도 검토합니다. SSOT_RULES에 정의된 성능 기준선
을 준수하면서, 동시에 타이밍 민감한 암호화폐 시장에서 기회 포착이 늦지 않도록 최적화합니다. WebSocket 지원도 D206 이후 과제로 추가해 보다 실시간性 높은 시세 반영을 이루고, REST 폴링은 Fail-safe용 백업경로로 남깁니다
.
⑤ 문서 및 운영체계 고도화 (중장기) – 마지막으로 문서와 운영 프로세스를 다듬어, 새로 합류한 팀원이나 외부 협업자가 봤을 때도 이해하기 쉬운 상태로 만듭니다.
문서 구조 개편: 현재 docs 폴더에 D숫자별로 많게는 200여개에 달하는 문서 조각들이 있습니다. 이를 Architecture, Operation, Reference 등의 주제별로 재분류하고, 오래되어 의미 줄어든 문서는 아카이빙하거나 본문에 녹여냅니다. 예컨대 Architecture.md를 만들어 V2 전체 구조와 모듈 책임을 최신 기준으로 설명하고 (D39/40 구조 감사 내용 활용
), Operation_Runbook.md는 운영 절차를 (기존 RUNBOOK.md 보강), API_Reference.md는 외부 노출 API나 Config 스키마 등을 정리하는 식입니다. 또한 중요한 개념(예: Zone Profile, SSOT 원칙)은 별도의 Concept 설명서로 정리해 둡니다. 이러한 문서 체계를 README에서 링크로 연결해주면, 오픈소스 수준의 문서화가 구현됩니다.
SSOT 원칙 준수 자동화: 마지막으로 개발 문화 측면에서 SSOT를 강제하는 도구를 활용합니다. 이미 check_ssot_docs.py로 문서 일치 여부를 검사하고 Exit Code를 리턴하는 기능이 일부 구현되어 있고, DocOps 개념이 도입되었으므로, 이를 CI에 넣어 문서 미갱신 시 빌드 실패하도록 할 수 있습니다. 예를 들어 주요 설정값이나 규칙들은 docs 폴더의 YAML이나 JSON으로 관리하고, 코드가 변경될 때 해당 파일도 변경하도록 검증하는 것입니다. 이렇게 하면 단일 진실 소스 원칙이 지속적으로 지켜져 로드맵과 구현 간 불일치가 최소화됩니다.
以上 단계를 순차적으로 실행하면, 궁극적으로 XXX_ARBITRAGE_TRADING_BOT은 **“상용 그 이상의 완성도”**를 갖춘 구조로 진화할 것입니다. 요약하면, 기존 로드맵의 문제점(스크립트 난립, 병렬진행 혼선)을 해소하고 엔진 중심으로 구조를 재편하며, 산업계 모범사례의 운영 프로토콜을 흡수하고 컨테이너 기반 배포/모니터링 체계를 완비하는 것이 목표입니다. 이를 통해 기술적 효율성(중복 제거, 성능 최적화)과 무결성(Fail-safe, 일관성), 확장성(멀티전략, 모듈화) 및 운용 용이성(모니터링/알림, 문서화)이 조화를 이루는 트레이딩 엔진으로 발전할 것으로 기대됩니다. 향후 모든 개발과 운영 결정은 SSOT 원칙 아래 이 궁극적 목표에 부합하는 방향으로 이루어져야 함은 말할 필요도 없습니다. 이제 명확해진 청사진을 바탕으로 한 걸음씩 실천하여, 팀의 Arbitrage 봇을 한층 견고하고 프로페셔널한 시스템으로 탈바꿈시키길 제안드립니다. 참고 자료: 기존 Arbitrage-Lite 구조 및 로드맵
, V2 구조 개선 커밋 내역, 운영 Runbook 발췌
, Hummingbot/Freqtrade 아키텍처 개요
 등. (상세 출처는 본 문서 각주에 명시)
인용
D_ROADMAP.md

file://file_00000000f4b4720992c0e27ab3a9966e
9fcdb4fd976d3a8e1ae887d751d09006c7054829...5bb25a6c198d9c5a0ef42875adafced24e707744.patch.txt

file://file_0000000046487207b9fcf66a977c442a
0292b48..f04a71a.patch.txt

file://file_00000000428471faa6180fe8bc3eba02
D_ROADMAP.md

file://file_00000000f4b4720992c0e27ab3a9966e
D_ROADMAP.md

file://file_00000000d64471fdb6a3ac8280013421
D_ROADMAP.md

file://file_00000000d64471fdb6a3ac8280013421
README.md

file://file_000000000fb071fab3645f3a4edd7324
README.md

file://file_000000000fb071fab3645f3a4edd7324
9fcdb4fd976d3a8e1ae887d751d09006c7054829...5bb25a6c198d9c5a0ef42875adafced24e707744.patch.txt

file://file_0000000046487207b9fcf66a977c442a

Hummingbot Architecture - Part 1 - Hummingbot

https://hummingbot.org/blog/hummingbot-architecture---part-1/

Freqtrade: Master Crypto Auto-Trading with a Modular Bot | by JIN | . | Medium

https://medium.com/aimonks/freqtrade-master-crypto-auto-trading-with-a-modular-bot-daf8e06a0533

Hummingbot Architecture - Part 1 - Hummingbot

https://hummingbot.org/blog/hummingbot-architecture---part-1/

Hummingbot Architecture - Part 1 - Hummingbot

https://hummingbot.org/blog/hummingbot-architecture---part-1/
0292b48..f04a71a.patch.txt

file://file_00000000428471faa6180fe8bc3eba02
D_ROADMAP.md

file://file_00000000d64471fdb6a3ac8280013421

Hummingbot Docker Quickstart Guide

https://hummingbot.org/blog/hummingbot-docker-quickstart-guide/
GitHub
RUNBOOK.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/RUNBOOK.md#L68-L75
GitHub
RUNBOOK.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/RUNBOOK.md#L98-L106
GitHub
RUNBOOK.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/RUNBOOK.md#L112-L120
GitHub
RUNBOOK.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/RUNBOOK.md#L122-L129
GitHub
RUNBOOK.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/RUNBOOK.md#L82-L90
GitHub
PROJECT_STRUCTURE_D39_D40.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/PROJECT_STRUCTURE_D39_D40.md#L22-L28
GitHub
PROJECT_STRUCTURE_D39_D40.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/PROJECT_STRUCTURE_D39_D40.md#L34-L36
D_ROADMAP.md

file://file_00000000d64471fdb6a3ac8280013421
D_ROADMAP.md

file://file_00000000d64471fdb6a3ac8280013421
D_ROADMAP.md

file://file_00000000d64471fdb6a3ac8280013421
D_ROADMAP.md

file://file_00000000d64471fdb6a3ac8280013421
README.md

file://file_000000000fb071fab3645f3a4edd7324
README.md

file://file_00000000e70071fa8f94a14c56119909
README.md

file://file_000000000fb071fab3645f3a4edd7324
README.md

file://file_00000000e70071fa8f94a14c56119909
GitHub
PROJECT_STRUCTURE_D39_D40.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/PROJECT_STRUCTURE_D39_D40.md#L69-L77
GitHub
PROJECT_STRUCTURE_D39_D40.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/PROJECT_STRUCTURE_D39_D40.md#L79-L87
GitHub
ROLE.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/ROLE.md#L94-L103
GitHub
ROLE.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/ROLE.md#L108-L116
GitHub
README.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/README.md#L92-L100
README.md

file://file_00000000e70071fa8f94a14c56119909
GitHub
ROLE.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/ROLE.md#L24-L33
GitHub
ROLE.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/ROLE.md#L40-L49
GitHub
ROLE.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/ROLE.md#L94-L102
GitHub
PROJECT_STRUCTURE_D39_D40.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/PROJECT_STRUCTURE_D39_D40.md#L54-L62
GitHub
PROJECT_STRUCTURE_D39_D40.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/PROJECT_STRUCTURE_D39_D40.md#L48-L56
GitHub
PROJECT_STRUCTURE_D39_D40.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/PROJECT_STRUCTURE_D39_D40.md#L94-L101
GitHub
PROJECT_STRUCTURE_D39_D40.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/PROJECT_STRUCTURE_D39_D40.md#L37-L46
D_ROADMAP.md

file://file_00000000d64471fdb6a3ac8280013421
D_ROADMAP.md

file://file_00000000d64471fdb6a3ac8280013421
D_ROADMAP.md

file://file_00000000d64471fdb6a3ac8280013421
GitHub
RUNBOOK.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/RUNBOOK.md#L54-L62
GitHub
RUNBOOK.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/RUNBOOK.md#L38-L46
README.md

file://file_000000000fb071fab3645f3a4edd7324
GitHub
D_ROADMAP.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/D_ROADMAP.md#L9-L17
README.md

file://file_000000000fb071fab3645f3a4edd7324
GitHub
ROLE.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/docs/ROLE.md#L90-L99

Hummingbot Architecture - Part 1 - Hummingbot

https://hummingbot.org/blog/hummingbot-architecture---part-1/

Hummingbot Architecture - Part 1 - Hummingbot

https://hummingbot.org/blog/hummingbot-architecture---part-1/
D_ROADMAP.md

file://file_00000000d64471fdb6a3ac8280013421
GitHub
README.md

https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/blob/607be424f17f8637e8edb77937c403f95382e10c/README.md#L26-L35
7d1aa22..f6aced0.patch.txt

file://file_000000006e2471fa8ab2d2df2e8e2865
모든 출처
D_ROADMAP.md
9fcdb4fd...patch.txt
0292b48....patch.txt
README.md

hummingbot

medium

github
7d1aa22....patch.txt