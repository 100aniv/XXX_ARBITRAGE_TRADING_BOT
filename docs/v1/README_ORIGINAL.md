# Arbitrage-Lite

**업비트–바이낸스 간 단일 전략 아비트라지 전용 봇**

## 프로젝트 개요

이 프로젝트는 업비트(현물)와 바이낸스(선물) 간 가격 스프레드를 기반으로 한 아비트라지 전략을 실행하는 **단일 전략 전용 봇**입니다.

- **목표**: 단순하고 명확한 구조로 MVP 수준의 거래/시뮬레이션 달성
- **특징**: 
  - 복잡한 플랫폼/프레임워크 구조 금지
  - 기존 앙상블 트레이딩 봇의 Collector/Exchange 로직 재사용
  - 나중에 앙상블 엔진에 전략 모듈로 포팅 가능한 최소 모듈화

## 프로젝트 구조

```
arbitrage-lite/
  README.md
  requirements.txt
  
  config/
    base.yml                  # 기본 설정 (거래소 URL, 심볼, 스프레드 임계값 등)
    secrets.example.yml       # API 키 템플릿 (실제 키는 secrets.yml에 저장, .gitignore 처리)
  
  arbitrage/
    __init__.py
    models.py                 # 데이터 모델 (Ticker, SpreadOpportunity, Position 등)
    collectors.py             # 기존 Collector/Exchange 코드 래핑 모듈
    normalizer.py             # 업비트/바이낸스 시세 공통 포맷 변환
    engine.py                 # 스프레드 계산 및 진입/청산 시그널 생성
    risk.py                   # 리스크 관리 (노출 한도, 주문 금액 제한 등)
    executor.py               # 주문 실행 인터페이스
    storage.py                # 간단한 저장 계층 (CSV/JSON 기반)
  
  scripts/
    run_collect_only.py       # 가격 수집 + 스프레드 계산만 출력 (MVP 1단계)
    run_paper.py              # 가상 체결 모드 (PHASE A-3)
    run_live.py               # 실거래 모드 (PHASE A-4)
```

## 설치 및 실행

### 1. Python 가상환경 설정

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 설정 파일 구성

1. `config/secrets.example.yml`을 `config/secrets.yml`로 복사
2. `secrets.yml`에 실제 API 키 입력
3. `config/base.yml`에서 거래 설정 조정 (심볼, 스프레드 임계값, 주문 금액 등)

**주의**: `secrets.yml`은 `.gitignore`에 등록하여 절대 커밋하지 마세요.

### 3. 실행

#### PHASE A-2 (MVP 1단계): 가격 수집 + 스프레드 계산
```bash
python scripts/run_collect_only.py
```

업비트와 바이낸스에서 현재가를 조회하고, 스프레드를 계산하여 콘솔에 출력합니다.

#### PHASE A-3 (향후): Paper Trading
```bash
python scripts/run_paper.py
```

가상 체결 모드로 실제 주문 없이 거래 시뮬레이션을 수행합니다.

#### PHASE A-4 (향후): Live Trading
```bash
python scripts/run_live.py
```

실제 API 키를 사용하여 실거래를 수행합니다. (주의: 실제 자금 사용)

## 기존 Collector 재사용 전략

이 프로젝트는 **기존 앙상블 트레이딩 봇 프로젝트의 Collector/Exchange 모듈을 재사용**합니다.

- `arbitrage/collectors.py`는 기존 프로젝트의 Collector 코드를 thin wrapper로 감싸는 역할
- HTTP 요청/서명 로직을 새로 작성하지 않고, 이미 검증된 코드를 이식
- 인터페이스와 함수 시그니처를 먼저 정의하고, "기존 프로젝트의 XXX 함수를 붙여 넣는다"는 TODO 주석으로 명확히 표시

**작업 방식:**
1. 현재는 인터페이스와 TODO만 정의
2. 나중에 기존 앙상블 프로젝트에서 Collector 관련 코드 조각을 복사/이식
3. 이식 위치와 방법은 코드 주석에 상세히 명시

## 개발 단계 (PHASE)

### PHASE A-1: 프로젝트 스캐폴딩 ✅ (현재 단계)
- 폴더 구조 생성
- venv 설정 방법 문서화
- config 스키마 설계
- 데이터 모델 설계
- 각 모듈의 책임 정의 및 TODO 작성

### PHASE A-2: Collector/Normalizer/Engine MVP
- 실제 시세 1회 조회 기능 구현
- 스프레드 계산 로직 구현
- `run_collect_only.py` 스크립트 완성

### PHASE A-3: Paper 모드
- 가상 체결 로직 추가
- Position 관리 구현
- `run_paper.py` 스크립트 완성

### PHASE A-4: Live Executor 뼈대
- 실거래 주문 실행 구조 구현
- 리스크 관리 강화
- `run_live.py` 스크립트 완성

## 주의사항

- **단일 전략 전용**: 이 프로젝트는 여러 전략을 올리는 플랫폼이 아니라, 업비트-바이낸스 아비트라지만 수행하는 전용 봇입니다.
- **최소 의존성**: 필요한 라이브러리만 사용하고, 추가 시 이유를 명시합니다.
- **명확한 구조**: 복잡한 계층 구조 없이, 얕고 명확한 구조를 유지합니다.

## TODO (향후 추가)

- [ ] WebSocket 기반 실시간 시세 수집 (현재는 REST API 폴링)
  - 필요 시 `websockets` 또는 `websocket-client` 라이브러리 추가
- [ ] SQLite/PostgreSQL 기반 저장 계층 (현재는 CSV/JSON)
- [ ] 거래 내역 시각화 대시보드
- [ ] Telegram/Discord 알림 봇 연동

## 라이선스

MIT License (또는 프로젝트에 맞는 라이선스 명시)
