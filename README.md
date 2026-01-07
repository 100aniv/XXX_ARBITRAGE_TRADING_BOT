# XXX 차익거래 트레이딩 봇 V2

**업비트–바이낸스 간 암호화폐 차익거래 자동화 시스템 (V2 Engine-Centric 아키텍처)**

---

## 📋 프로젝트 소개

이 프로젝트는 업비트(현물)와 바이낸스(선물) 간 가격 차이를 이용한 **차익거래 자동화 봇**입니다.

### 핵심 특징

- **V2 Engine-Centric 아키텍처**: OrderIntent → Adapter → Engine 표준 플로우
- **Binance Futures 기본**: USDT-M Futures API 사용 (Spot은 파이프라인 검증용)
- **READ_ONLY 기본**: 실거래 영구 차단, Mock/Paper 모드 우선
- **SSOT 강제**: 단일 진실 공급원 원칙 (중복/분기 금지)
- **Gate 검증**: doctor/fast/regression 100% PASS 필수
- **인프라 재사용**: Docker/PostgreSQL/Redis/Prometheus/Grafana 즉시 활용

---

## 🚀 빠른 시작 (Quickstart)

### 1. 환경 설정

**Python 3.13.11 설치 확인:**
```powershell
python --version  # 3.13.11 권장
```

**가상환경 생성 및 활성화:**
```powershell
cd c:\work\XXX_ARBITRAGE_TRADING_BOT
python -m venv abt_bot_env
.\abt_bot_env\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Gate 검증 (개발 시작 전 필수)

**Doctor Gate (테스트 수집 확인):**
```powershell
.\abt_bot_env\Scripts\python.exe -m pytest --collect-only -q
```

**Fast Gate (핵심 테스트):**
```powershell
.\abt_bot_env\Scripts\python.exe -m pytest tests/test_d48_upbit_order_payload.py -v
```

**Regression Gate (전체 회귀 테스트):**
```powershell
.\abt_bot_env\Scripts\python.exe -m pytest tests/test_d98_preflight.py -v
```

### 3. V2 Smoke Harness 실행

**V2 엔진 검증 (READ_ONLY 모드):**
```powershell
.\abt_bot_env\Scripts\python.exe -m arbitrage.v2.harness.smoke_runner
```

**출력 예시:**
```
[V2 Smoke] ✅ Mock MARKET BUY: mock-abc123
[V2 Smoke] ✅ Mock MARKET SELL: mock-def456
[V2 Smoke] ✅ Upbit MARKET BUY payload: {'market': 'KRW-BTC', 'side': 'buy', ...}
[V2 Smoke] ✅ SMOKE TEST PASSED
```

---

## 📚 SSOT 문서 (Single Source of Truth)

**V2는 SSOT 원칙을 강제합니다. 모든 도메인은 단 1개의 SSOT를 가집니다.**

### 필수 SSOT 7종

| # | 도메인 | SSOT 파일 | 역할 |
|---|--------|-----------|------|
| **1** | **Process** | [`D_ROADMAP.md`](D_ROADMAP.md) | 프로젝트 로드맵, D 단계 정의 |
| **2** | **Runtime Config** | [`config/v2/config.yml`](config/v2/config.yml) | 거래소/전략/안전 설정 |
| **3** | **Secrets** | [`.env.v2.example`](.env.v2.example) | API Keys 템플릿 (실제: `.env.v2`) |
| **4** | **Data (DB)** | [`db/migrations/v2_schema.sql`](db/migrations/v2_schema.sql) | PostgreSQL 스키마 |
| **5** | **Cache/Locks (Redis)** | [`docs/v2/design/REDIS_KEYSPACE.md`](docs/v2/design/REDIS_KEYSPACE.md) | Redis 키 네이밍 규칙 |
| **6** | **Monitoring** | [`monitoring/prometheus/prometheus.v2.yml`](monitoring/prometheus/prometheus.v2.yml) | Prometheus/Grafana 설정 |
| **7** | **Evidence** | [`docs/v2/design/EVIDENCE_FORMAT.md`](docs/v2/design/EVIDENCE_FORMAT.md) | 실행 증거 저장 포맷 |

### 추가 SSOT (V2 특화)

| 도메인 | SSOT 파일 | 역할 |
|--------|-----------|------|
| **Rulebook** | [`docs/v2/SSOT_RULES.md`](docs/v2/SSOT_RULES.md) | V2 개발 강제 규칙 |
| **Architecture** | [`docs/v2/V2_ARCHITECTURE.md`](docs/v2/V2_ARCHITECTURE.md) | Engine-Centric 설계 계약 |
| **Infra Reuse** | [`docs/v2/design/INFRA_REUSE_INVENTORY.md`](docs/v2/design/INFRA_REUSE_INVENTORY.md) | V1 인프라 재사용 전략 |
| **Migration** | [`docs/v2/design/V2_MIGRATION_STRATEGY.md`](docs/v2/design/V2_MIGRATION_STRATEGY.md) | V1→V2 마이그레이션 계획 |
| **SSOT Map** | [`docs/v2/design/SSOT_MAP.md`](docs/v2/design/SSOT_MAP.md) | 전체 SSOT 목록 및 규칙 |

**⚠️ 금지 사항:**
- ❌ SSOT 분기 (예: `config_v2_prod.yml`, `D_ROADMAP_V2.md`)
- ❌ 환경별 설정 파일 중복 (환경 변수로 오버라이드)
- ❌ Secrets 커밋 (`.env.v2`는 gitignore 필수)

---

## 📂 프로젝트 구조 (V2 기준)

```
XXX_ARBITRAGE_TRADING_BOT/
├── arbitrage/
│   ├── v2/                          # ⭐ V2 코어 (Engine-Centric)
│   │   ├── core/                    # 핵심 컴포넌트
│   │   │   ├── order_intent.py     # OrderIntent, OrderSide, OrderType
│   │   │   ├── adapter.py          # ExchangeAdapter 인터페이스
│   │   │   ├── engine.py           # ArbitrageEngine (오케스트레이터)
│   │   │   └── config.py           # V2 설정 로더 (신규 생성 예정)
│   │   ├── adapters/                # 거래소 어댑터
│   │   │   ├── mock_adapter.py     # Mock (테스트용)
│   │   │   ├── upbit_adapter.py    # 업비트 구현
│   │   │   └── binance_adapter.py  # 바이낸스 (생성 예정)
│   │   └── harness/                 # 테스트 하네스
│   │       └── smoke_runner.py     # Smoke 테스트 자동화
│   └── (V1 legacy 코드...)         # V1 레거시 (참조용)
├── config/
│   └── v2/                          # ⭐ V2 설정 SSOT
│       └── config.yml               # Runtime 설정 (생성 예정)
├── docs/
│   ├── D_ROADMAP.md                 # ⭐ 프로젝트 로드맵 SSOT
│   ├── v2/                          # V2 문서 공간
│   │   ├── SSOT_RULES.md           # V2 개발 규칙
│   │   ├── V2_ARCHITECTURE.md      # 설계 계약
│   │   └── design/                 # 설계 문서
│   │       ├── INFRA_REUSE_INVENTORY.md
│   │       ├── SSOT_MAP.md
│   │       └── V2_MIGRATION_STRATEGY.md
│   └── v1/                          # V1 레거시 문서
├── infra/
│   └── docker-compose.yml           # ⭐ 인프라 SSOT
├── .env.v2.example                  # Secrets 템플릿 (생성 예정)
└── README.md                        # 현재 문서

⭐ = V2 SSOT (Single Source of Truth)
```

---

## 📚 SSOT 문서 (반드시 읽기)

V2 개발 시 참조할 SSOT 문서:

| 도메인 | SSOT 파일 | 역할 |
|--------|-----------|------|
| **프로세스** | `docs/D_ROADMAP.md` | 전체 로드맵 (D1~D206+) |
| **개발 규칙** | `docs/v2/SSOT_RULES.md` | V2 강제 규칙 (Gate, 경로, 금지 사항) |
| **아키텍처** | `docs/v2/V2_ARCHITECTURE.md` | Engine-Centric 설계 계약 |
| **런타임 설정** | `config/v2/config.yml` | 거래소/전략/안전 설정 |
| **Secrets** | `.env.v2.example` → `.env.v2` | API Keys (gitignore) |
| **인프라** | `infra/docker-compose.yml` | Docker 서비스 정의 |
| **테스트** | `pytest.ini` | pytest 설정 |

**중요:** SSOT는 도메인당 1개만 존재. 분기/중복 절대 금지.

---

## 🎯 V2 핵심 개념

### 1. Engine-Centric 플로우

```
사용자 요청
    ↓
OrderIntent (Semantic Layer)
    ↓
ExchangeAdapter (Implementation Layer)
    ↓
거래소 API
```

### 2. MARKET 주문 규약

- **MARKET BUY**: `quote_amount` 사용 (예: 5000 KRW)
- **MARKET SELL**: `base_qty` 사용 (예: 0.001 BTC)
- **검증**: OrderIntent.validate()로 강제

### 3. READ_ONLY 원칙

- 모든 Adapter는 `read_only=True` 기본값
- 실거래는 D206+ 이후 재검토
- Smoke/Paper는 Mock 또는 READ_ONLY 모드만

---

## 🛠️ 개발 워크플로우

### 1. 코드 작성 전

1. **SSOT 확인**: `docs/v2/SSOT_RULES.md` 읽기
2. **아키텍처 계약**: `docs/v2/V2_ARCHITECTURE.md` 인터페이스 확인
3. **로드맵 확인**: `docs/D_ROADMAP.md`에서 현재 Phase 확인

### 2. 코드 작성

```python
# 올바른 import (V2)
from arbitrage.v2.core import OrderIntent, OrderSide, OrderType
from arbitrage.v2.adapters import UpbitAdapter

# 금지된 import (V1 직접 사용 금지)
# from arbitrage.live_runner import ...  # ❌ 금지
```

### 3. 테스트 작성

```powershell
# V2 테스트 작성
tests/test_v2_order_intent.py
tests/test_v2_upbit_adapter.py

# 실행
pytest tests/test_v2_*.py -v
```

### 4. Gate 검증 (커밋 전 필수)

```powershell
# 순서대로 실행, 하나라도 FAIL 시 커밋 금지
pytest --collect-only         # Doctor
pytest tests/test_d48_*.py    # Fast
pytest tests/test_d98_*.py    # Regression
```

### 5. 커밋 & 푸시

```powershell
git add .
git commit -m "[D20X-Y] 작업 내용"
git push origin rescue/d99_15_fullreg_zero_fail
```

---

## 🐳 인프라 실행 (Docker)

### PostgreSQL + Redis + Prometheus + Grafana 시작

```powershell
cd c:\work\XXX_ARBITRAGE_TRADING_BOT
docker-compose -f infra/docker-compose.yml up -d postgres redis prometheus grafana
```

### 서비스 확인

- **Adminer (DB 관리)**: http://localhost:8080
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

### 중지

```powershell
docker-compose -f infra/docker-compose.yml down
```

---

## 📊 현재 상태 (2025-12-29 기준)

### ✅ 완료 (D200-0)

- V2 Kickoff 완료
- SSOT 문서 3종 생성
- OrderIntent/Adapter/Engine 구현
- Smoke Harness 5/5 PASS
- Gate 100% PASS

### 🔄 진행 중 (D200-1)

- Runtime Config SSOT 생성
- .env.v2.example 템플릿 생성
- 인프라 재사용 인벤토리 확정
- README 정리

### ⏳ 계획 (D201~D206)

- D201: Adapter Contract Tests + Upbit/Binance 구현
- D202: MarketData REST/WS 통합
- D203: Opportunity Detector + Fee 모델
- D204: Paper Execution (20m/1h/3h)
- D205: PnL 리포트 + Grafana 대시보드
- D206: Ops/Deploy + 배포 런북

---

## 🚨 금지 사항

### ❌ 절대 금지

1. **SSOT 분기**: D_ROADMAP_V2.md, SSOT_RULES_v2.md 등 생성 금지
2. **V1 직접 import**: V2 코드에서 `from arbitrage.live_runner import ...` 금지
3. **Secrets 커밋**: .env.v2를 Git에 절대 커밋 금지
4. **파괴적 이동**: V1 코드 삭제/이동 금지 (V2와 공존)
5. **Gate 무시**: doctor/fast/regression FAIL 상태로 커밋 금지

### ⚠️ 주의 사항

- 환경 변수는 `.env.v2`에만 (config.yml에 Secrets 저장 금지)
- 새 파라미터 추가 시 `config/v2/config.yml` + dataclass 동시 수정
- 인터페이스 변경 시 `V2_ARCHITECTURE.md` 먼저 수정 후 코드 동기화

---

## 🔗 주요 링크

- **GitHub 저장소**: https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT
- **로드맵**: `docs/D_ROADMAP.md`
- **V2 규칙**: `docs/v2/SSOT_RULES.md`
- **V2 아키텍처**: `docs/v2/V2_ARCHITECTURE.md`
- **V1 문서**: `docs/v1/README.md`

---

## 📞 문의 & 기여

- 이슈: GitHub Issues
- 커밋 컨벤션: `[D번호] 작업 내용`
- 코드 리뷰: SSOT 규칙 준수 확인 필수

---

## 📜 라이선스

MIT License

---

**V2는 Engine-Centric, SSOT 강제, READ_ONLY 기본, Gate 100% PASS 필수.** 🚀
