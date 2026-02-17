# XXX 차익거래 트레이딩 봇 V2

**업비트–바이낸스 간 암호화폐 차익거래 자동화 시스템 (V2 Engine-Centric 아키텍처)**

**현재 상태:** D_ALPHA-2 진행 중 (2026-02-17) | TURN5 완료 | D209-3 계획 중

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
- **Alpha Engine Track**: Maker Pivot + OBI Filter + Inventory Risk Management 진행 중

### 네이밍 규칙 (D205-15-2)
- **프로젝트 시즌**: V1/V2 (예: `arbitrage/v2/`, `docs/v2/`, "V2 Engine-Centric")
- **거래 시장 타입**: MarketType.SPOT / MarketType.FUTURES
- **구분 목적**: "V1/V2"는 프로젝트 세대, "SPOT/FUTURES"는 거래 시장 구분
- **URL 경로**: `/api/v3` (Spot), `/fapi/v1` (Futures)은 구현 디테일로만 취급

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
| **4** | **Data (DB)** | [`db/schema/v2_schema.sql`](db/schema/v2_schema.sql) | PostgreSQL 스키마 |
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
│   │   │   ├── orchestrator.py     # PaperOrchestrator (메인 루프)
│   │   │   ├── opportunity_source.py # 기회 탐지 + OBI 계산
│   │   │   ├── monitor.py          # 실행 모니터링 + 증거 수집
│   │   │   ├── runtime_factory.py  # 런타임 구성 (DB/Redis/Config)
│   │   │   ├── engine_report.py    # 실행 리포트 생성
│   │   │   └── config.py           # V2 설정 로더
│   │   ├── domain/                  # 도메인 로직
│   │   │   ├── pnl_calculator.py   # PnL 계산 (SSOT)
│   │   │   ├── fee_model.py        # 수수료 모델 (메이커/테이커)
│   │   │   ├── execution_quality.py # 실행 품질 모델
│   │   │   └── topn_provider.py    # TopN 심볼 제공
│   │   ├── adapters/                # 거래소 어댑터
│   │   │   ├── mock_adapter.py     # Mock (테스트용)
│   │   │   ├── upbit_adapter.py    # 업비트 구현
│   │   │   └── binance_adapter.py  # 바이낸스 구현
│   │   ├── tools/                   # 엔진 소유 도구 (비즈니스 로직)
│   │   │   ├── topn_stress.py      # TopN 스트레스 측정
│   │   │   ├── d205_10_1_sweep.py  # Threshold Sensitivity Sweep
│   │   │   └── profit_proof_matrix.py # D206-1 수익성 증명
│   │   ├── harness/                 # 테스트 하네스 (thin wrapper)
│   │   │   ├── paper_runner.py     # Paper 실행 CLI
│   │   │   ├── topn_stress.py      # TopN 스트레스 하네스
│   │   │   └── smoke_runner.py     # Smoke 테스트 자동화
│   │   └── execution_quality/       # 실행 품질 모델
│   │       └── model_v1.py         # SimpleExecutionQualityModel
│   └── (V1 legacy 코드...)         # V1 레거시 (참조용)
├── config/
│   └── v2/                          # ⭐ V2 설정 SSOT
│       └── config.yml               # Runtime 설정
├── docs/
│   ├── D_ROADMAP.md                 # ⭐ 프로젝트 로드맵 SSOT
│   ├── v2/                          # V2 문서 공간
│   │   ├── SSOT_RULES.md           # V2 개발 규칙 (헌법)
│   │   ├── OPS_PROTOCOL.md         # 운영 프로토콜 (Invariants)
│   │   ├── V2_ARCHITECTURE.md      # 설계 계약
│   │   ├── design/                 # 설계 문서
│   │   │   ├── ENGINE_CENTRIC_PURGE_AUDIT.md
│   │   │   ├── WELDING_AUDIT.md
│   │   │   ├── SSOT_MAP.md
│   │   │   ├── EVIDENCE_FORMAT.md
│   │   │   ├── REDIS_KEYSPACE.md
│   │   │   ├── INFRA_REUSE_INVENTORY.md
│   │   │   ├── V2_MIGRATION_STRATEGY.md
│   │   │   ├── READING_CHECKLIST.md
│   │   │   └── LIVE_ARCHITECTURE.md (계획)
│   │   └── reports/                # D별 실행 리포트
│   │       ├── D205/
│   │       ├── D206/
│   │       ├── D207/
│   │       ├── D_ALPHA/
│   │       └── ...
│   └── v1/                          # V1 레거시 문서
├── scripts/                         # CLI 스크립트 (thin wrapper)
│   ├── run_d205_8_topn_stress.py
│   ├── run_d205_10_1_sweep.py
│   ├── run_d206_1_profit_proof_matrix.py
│   ├── check_engine_centricity.py  # Guard: 엔진 중심성 검증
│   ├── check_no_duplicate_pnl.py   # Guard: PnL 중복 금지
│   ├── check_v2_boundary.py        # Guard: V2 경계 검증
│   ├── check_ssot_docs.py          # Guard: SSOT 문서 검증
│   └── run_gate_with_evidence.py   # Gate 통합 실행
├── tests/                           # 단위 테스트
│   ├── test_d205_8_topn_stress.py
│   ├── test_d_alpha_*.py
│   ├── test_d206_1_profit_proof_matrix.py
│   └── ...
├── logs/evidence/                   # 실행 증거 저장소
│   ├── 20260217_gate_doctor_*/
│   ├── 20260217_gate_fast_*/
│   ├── 20260217_gate_regression_*/
│   ├── d_alpha_2_fastlane_20m_*/
│   └── ...
├── infra/
│   └── docker-compose.yml           # ⭐ 인프라 SSOT
├── .env.v2.example                  # Secrets 템플릿
├── .gitignore                       # Git 무시 규칙
└── README.md                        # 현재 문서

⭐ = V2 SSOT (Single Source of Truth)
```

---

## 📚 SSOT 문서 (반드시 읽기)

V2 개발 시 참조할 SSOT 문서:

### 필수 SSOT (7종)

| # | 도메인 | SSOT 파일 | 역할 |
|---|--------|-----------|------|
| **1** | **프로세스** | [`D_ROADMAP.md`](D_ROADMAP.md) | 전체 로드맵 (D200~D210+) |
| **2** | **개발 규칙** | [`docs/v2/SSOT_RULES.md`](docs/v2/SSOT_RULES.md) | V2 강제 규칙 (Gate, 경로, 금지 사항) |
| **3** | **아키텍처** | [`docs/v2/V2_ARCHITECTURE.md`](docs/v2/V2_ARCHITECTURE.md) | Engine-Centric 설계 계약 |
| **4** | **런타임 설정** | [`config/v2/config.yml`](config/v2/config.yml) | 거래소/전략/안전 설정 |
| **5** | **Secrets** | [`.env.v2.example`](.env.v2.example) → `.env.v2` | API Keys (gitignore) |
| **6** | **인프라** | [`infra/docker-compose.yml`](infra/docker-compose.yml) | Docker 서비스 정의 |
| **7** | **증거 포맷** | [`docs/v2/design/EVIDENCE_FORMAT.md`](docs/v2/design/EVIDENCE_FORMAT.md) | 실행 증거 저장 포맷 |

### 추가 SSOT (V2 특화)

| 도메인 | SSOT 파일 | 역할 |
|--------|-----------|------|
| **운영 프로토콜** | [`docs/v2/OPS_PROTOCOL.md`](docs/v2/OPS_PROTOCOL.md) | Invariants, ExitCode, Graceful Shutdown |
| **PnL 계산** | [`arbitrage/v2/domain/pnl_calculator.py`](arbitrage/v2/domain/pnl_calculator.py) | PnL 계산 SSOT (friction, net edge) |
| **SSOT 맵** | [`docs/v2/design/SSOT_MAP.md`](docs/v2/design/SSOT_MAP.md) | 전체 SSOT 목록 및 규칙 |
| **인프라 재사용** | [`docs/v2/design/INFRA_REUSE_INVENTORY.md`](docs/v2/design/INFRA_REUSE_INVENTORY.md) | V1 인프라 재사용 전략 |
| **마이그레이션** | [`docs/v2/design/V2_MIGRATION_STRATEGY.md`](docs/v2/design/V2_MIGRATION_STRATEGY.md) | V1→V2 마이그레이션 계획 |
| **Redis 키스페이스** | [`docs/v2/design/REDIS_KEYSPACE.md`](docs/v2/design/REDIS_KEYSPACE.md) | Redis 키 네이밍 규칙 |

**중요:** SSOT는 도메인당 1개만 존재. 분기/중복 절대 금지.

---

## 🎯 V2 핵심 개념

### 1. Engine-Centric 아키텍처

```
OrderIntent (Semantic Layer)
    ↓
ExchangeAdapter (Implementation Layer)
    ↓
PaperOrchestrator (Main Loop)
    ├─ OpportunitySource (기회 탐지 + OBI 계산)
    ├─ PaperExecutionAdapter (모의 실행)
    ├─ Monitor (실행 모니터링 + 증거 수집)
    └─ EngineReport (실행 리포트 생성)
    ↓
거래소 API (READ_ONLY 기본)
```

**핵심 원칙:**
- **비즈니스 로직**: `arbitrage/v2/core/`, `arbitrage/v2/domain/`, `arbitrage/v2/tools/`에만 존재
- **Harness/Scripts**: CLI wiring만 담당 (thin wrapper)
- **역방향 import 금지**: core/domain이 harness/scripts를 import하지 않음

### 2. MARKET 주문 규약

- **MARKET BUY**: `quote_amount` 사용 (예: 5000 KRW)
- **MARKET SELL**: `base_qty` 사용 (예: 0.001 BTC)
- **검증**: OrderIntent.validate()로 강제
- **Price 접근 금지**: OrderIntent.price/quantity 직접 접근 금지 (quote_amount/base_qty/limit_price 사용)

### 3. READ_ONLY 원칙

- 모든 Adapter는 `read_only=True` 기본값
- 실거래는 D210+ (LIVE 설계 완료) 이후 재검토
- Smoke/Paper/Backtest는 Mock 또는 READ_ONLY 모드만
- **LIVE 진입 봉인**: D210-3 완료 전까지 order_submit() 실행 불가

### 4. Alpha Engine Track (수익 로직 중심)

**목표:** "시장에 기회가 없다"가 아니라, **현재 마찰 모델을 역전시키는 알파**를 주입해 **Positive net edge 샘플을 실제로 만들어낸다**.

**진행 상황:**
- ✅ **D_ALPHA-1**: Maker Pivot MVP (메이커/리베이트 기반 손익모델)
- ✅ **D_ALPHA-1U**: Universe Unblock & Persistence Hardening (Top100 완전 로드)
- ✅ **D_ALPHA-1U-FIX-2**: Reality Welding (Latency Cost Decomposition)
- 🔄 **D_ALPHA-2**: OBI Filter & Ranking (Order Book Imbalance 기반 진입 신호)

**핵심 지표:**
- `positive_net_edge_pct`: 수익 가능 기회 비율 (목표: ≥ 5%)
- `obi_score`: Order Book Imbalance 점수 (0~1, 높을수록 유리)
- `winrate_pct`: 거래 승률 (목표: ≥ 50%, 현재 0~92%)
- `net_pnl`: 순손익 (목표: > 0)

---

## 🛠️ 개발 워크플로우

### Step 0: Bootstrap (SSOT 정독)

1. **D_ROADMAP.md** 읽기 - 현재 D 섹션 목표/AC/증거 경로 확인
2. **docs/v2/SSOT_RULES.md** 읽기 - 개발 규칙, Gate 템플릿, DocOps 강제 규칙
3. **docs/v2/design/** 최소 2개 문서 읽기 - 관련 설계 문서 정독
4. **READING_CHECKLIST.md** 업데이트 - 읽은 문서 목록 + 1줄 요약 기록

### Step 1: 코드 작성 전

1. **SSOT 확인**: `docs/v2/SSOT_RULES.md` 읽기
2. **아키텍처 계약**: `docs/v2/V2_ARCHITECTURE.md` 인터페이스 확인
3. **로드맵 확인**: `docs/D_ROADMAP.md`에서 현재 D 섹션 AC 확인
4. **스코프 선언**: "이번 턴 수정 대상 파일/경로" 명시

### Step 2: 코드 작성

```python
# 올바른 import (V2)
from arbitrage.v2.core import OrderIntent, OrderSide, OrderType
from arbitrage.v2.adapters import UpbitAdapter
from arbitrage.v2.domain import pnl_calculator  # PnL SSOT

# 금지된 import (V1 직접 사용 금지)
# from arbitrage.live_runner import ...  # ❌ 금지

# 금지된 패턴 (역방향 import)
# from arbitrage.v2.harness import ...  # ❌ core/domain에서 금지
```

**Engine-Centric 원칙:**
- 비즈니스 로직은 `arbitrage/v2/core/`, `arbitrage/v2/domain/`, `arbitrage/v2/tools/`에만
- Harness/Scripts는 CLI wiring만 (thin wrapper)
- PnL 계산은 `arbitrage/v2/domain/pnl_calculator.py`에만 (중복 금지)

### Step 3: 테스트 작성

```powershell
# V2 테스트 작성
tests/test_d_alpha_*.py
tests/test_d206_*.py

# 실행
pytest tests/test_d_alpha_*.py -v
```

### Step 4: Guard 검증 (커밋 전 필수)

```powershell
# 엔진 중심성 검증
python scripts/check_engine_centricity.py

# PnL 중복 금지 검증
python scripts/check_no_duplicate_pnl.py

# V2 경계 검증
python scripts/check_v2_boundary.py

# SSOT 문서 검증
python scripts/check_ssot_docs.py
```

### Step 5: Gate 검증 (커밋 전 필수)

```powershell
# 순서대로 실행, 하나라도 FAIL 시 커밋 금지
python -m pytest --collect-only         # Doctor
python -m pytest tests/test_d205_*.py -v  # Fast
python -m pytest tests/test_d98_*.py -v   # Regression

# 또는 통합 실행
python scripts/run_gate_with_evidence.py
```

### Step 6: Smoke 테스트 (변경 범위에 따라)

```powershell
# Micro-Smoke (1분, 경미 변경)
python -m arbitrage.v2.harness.smoke_runner

# Full Smoke (20분, 트레이딩 루프 변경)
python scripts/run_d205_8_topn_stress.py --duration 20
```

### Step 7: 문서 업데이트

1. **D_ROADMAP.md** - AC 체크, 증거 경로 기록
2. **docs/v2/reports/Dxxx/Dxxx_REPORT.md** - 실행 결과 기록
3. **READING_CHECKLIST.md** - 읽은 문서 목록 업데이트

### Step 8: DocOps 검증 (커밋 직전 필수)

```powershell
# Gate (A) SSOT 자동 검사
python scripts/check_ssot_docs.py  # ExitCode=0 필수

# Gate (B) ripgrep 위반 탐지
rg "cci:" -n docs/v2 D_ROADMAP.md
rg "이관|migrate|migration" -n docs/v2 D_ROADMAP.md
rg "TODO|TBD|PLACEHOLDER" -n docs/v2 D_ROADMAP.md

# Gate (C) Pre-commit sanity
git status
git diff --stat
```

### Step 9: 커밋 & 푸시

```powershell
# 스코프 내 파일만 스테이징
git add -p  # 대화형 스테이징

# SSOT 스타일 커밋 메시지
git commit -m "[Dxxx-y] <단계명> — <핵심 변경 1줄>

(선택) 상세 설명 (2~3줄)"

# 푸시
git push origin <branch>

# Compare URL 생성
# https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/compare/<before_sha>...<after_sha>
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

## 📊 현재 상태 (2026-02-17 기준)

### ✅ 완료 (TURN5 완료)

**Phase 1: V2 Foundation (D200-D205)**
- ✅ D200: V2 Kickoff + SSOT 문서 3종
- ✅ D201: Adapter Contract Tests + Upbit/Binance 구현
- ✅ D202: MarketData REST/WS 통합 + Alert Storage
- ✅ D203: Opportunity Detector + Fee 모델 + Execution Quality
- ✅ D204: Paper Execution (20m/1h/3h) + PnL 분해
- ✅ D205: PnL 리포트 + Grafana 대시보드 + TopN Stress + Threshold Sweep

**Phase 2: Stability & Verification (D206-D207)**
- ✅ D206: Profitability Proof Matrix (민감도 분석, 수익성 증명)
- ✅ D207: Multi-Symbol Alpha Survey (Top100/Top200 실제 서베이)

**Phase 3: Alpha Engine Track (D_ALPHA)**
- ✅ D_ALPHA-0: Universe Truth (TopN 실제 동작 확정)
- ✅ D_ALPHA-1: Maker Pivot MVP (메이커/리베이트 기반 손익모델)
- ✅ D_ALPHA-1U: Universe Unblock & Persistence Hardening
- ✅ D_ALPHA-1U-FIX-1: Universe Loader (Top100 완전 로드)
- ✅ D_ALPHA-1U-FIX-2: Reality Welding (Latency Cost Decomposition)
- ✅ D_ALPHA-1U-FIX-2-1: Winrate 현실화 (손실 발생 증거)
- ✅ D_ALPHA-1U-FIX-2-2: OrderIntent Price Guard + D206-1 Stabilization

### 🔄 진행 중 (D_ALPHA-2)

**D_ALPHA-2: OBI Filter & Ranking (HFT Intelligence v1)**
- 상태: IN PROGRESS (2026-02-17)
- 목표: OBI(Order Book Imbalance)로 유리한 순간만 골라 메이커 진입 보조
- 진행: AC-2~6 완료, AC-1 진행 중 (동적 임계치 구현)
- 증거: `logs/evidence/dalpha_2_final_obi_on_20m_20260207_212559/`
- Gate: Doctor/Fast/Regression 100% PASS

### ⏳ 계획 (D208~D210)

**D208: Structural Normalization**
- ExecutionBridge 리네이밍 (MockAdapter → ExecutionBridge)
- Unified Engine Interface (Backtest/Paper/Live)
- V1 Purge 계획 (삭제 후보 리스트업)

**신 D209: 주문 라이프사이클/실패모델/리스크 가드**
- D209-1: 주문 실패 시나리오 (429/timeout/reject/partial fill)
- D209-2: 리스크 가드 통합 (position limit, loss cutoff, kill-switch)
- D209-3: Wallclock 이중 검증 + Fail-Fast 전파 (D205-10-2 유산 복구)

**신 D210: LIVE 진입 설계/게이트 (구현은 봉인)**
- D210-1: LIVE 설계 문서
- D210-2: LIVE Gate 설계
- D210-3: LIVE 봉인 검증

**D210~D215: HFT & Commercial Readiness (Phase 3)**
- Multi-Exchange Adapter (Upbit, Binance, Bybit, OKX, Bitget, Bithumb, Coinone)
- Rate Limit Manager + Exchange Health Monitor
- 4-Tier RiskGuard + WebSocket Market Stream
- Cross-Exchange Position Sync + Multi-Exchange Hedging Engine
- Spread-based Arbitrage Risk Model + Order Execution Optimizer
- Backtest Engine 확장 + Hyperparameter Tuning Cluster
- Failover & Resume + Compliance & Audit Trail
- Monitoring & Alerting Stack (Prometheus, Grafana, Telegram)

---

## 🚨 금지 사항

### ❌ 절대 금지

1. **SSOT 분기**: D_ROADMAP_V2.md, SSOT_RULES_v2.md 등 생성 금지
2. **V1 직접 import**: V2 코드에서 `from arbitrage.live_runner import ...` 금지
3. **Secrets 커밋**: .env.v2를 Git에 절대 커밋 금지
4. **파괴적 이동**: V1 코드 삭제/이동 금지 (V2와 공존)
5. **Gate 무시**: doctor/fast/regression FAIL 상태로 커밋 금지
6. **PnL 중복**: `arbitrage/v2/domain/pnl_calculator.py` 외 다른 곳에서 friction 계산 금지
7. **역방향 import**: core/domain이 harness/scripts를 import하지 않기
8. **LIVE 실행**: D210-3 완료 전까지 order_submit() 실행 금지
9. **AC 삭제**: 기존 AC를 삭제/축소하지 않기 (추가만 허용)
10. **D 번호 재정의**: D 번호의 의미를 다른 작업으로 변경하지 않기

### ⚠️ 주의 사항

- 환경 변수는 `.env.v2`에만 (config.yml에 Secrets 저장 금지)
- 새 파라미터 추가 시 `config/v2/config.yml` + dataclass 동시 수정
- 인터페이스 변경 시 `V2_ARCHITECTURE.md` 먼저 수정 후 코드 동기화
- OrderIntent.price/quantity 직접 접근 금지 (quote_amount/base_qty/limit_price 사용)
- 장기 실행(≥1h)은 watch_summary.json + heartbeat.json 이중 검증 필수
- 모든 실행은 logs/evidence/ 경로에 증거 저장 필수

---

## � 성능 목표 (TO-BE Architecture)

### Phase 1: Core Infrastructure (완료)
- ✅ Multi-Exchange Adapter (Upbit, Binance)
- ✅ Rate Limit Manager (기본)
- ✅ Exchange Health Monitor (기본)
- ✅ WebSocket Market Stream (기본)

### Phase 2: Advanced Trading (진행 중)
- 🔄 ArbUniverse / ArbRoute (Top100/Top200 로드 완료)
- 🔄 Cross-Exchange Position Sync (기본)
- ⏳ Multi-Exchange Hedging Engine
- ⏳ Trade Ack Latency Monitor
- ⏳ Dynamic Symbol Selection

### Phase 3: Optimization & Analytics (계획)
- ⏳ Spread-based Arbitrage Risk Model
- ⏳ Order Execution Optimizer (TWAP/VWAP)
- ⏳ Backtest Engine 확장
- ⏳ Hyperparameter Tuning Cluster
- ⏳ Multi-Currency Support

### Phase 4: Production Operations (계획)
- ⏳ Failover & Resume
- ⏳ Compliance & Audit Trail
- ⏳ Monitoring & Alerting Stack (Prometheus, Grafana, Telegram)

### 성능 지표 (목표)
- **Loop latency**: < 25ms (avg), < 40ms (p99)
- **Throughput**: ≥ 40 iter/s
- **CPU**: < 10%, Memory: < 60MB
- **Uptime**: 99.9%+
- **Multi-symbol**: Top50+ concurrent
- **Positive net edge**: ≥ 5% (현재 0~5.61%)
- **Winrate**: ≥ 50% (현재 0~92%)

---

## �🔗 주요 링크

- **GitHub 저장소**: https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT
- **로드맵**: [`docs/D_ROADMAP.md`](D_ROADMAP.md)
- **V2 규칙**: [`docs/v2/SSOT_RULES.md`](docs/v2/SSOT_RULES.md)
- **V2 아키텍처**: [`docs/v2/V2_ARCHITECTURE.md`](docs/v2/V2_ARCHITECTURE.md)
- **운영 프로토콜**: [`docs/v2/OPS_PROTOCOL.md`](docs/v2/OPS_PROTOCOL.md)
- **설계 문서**: [`docs/v2/design/`](docs/v2/design/)
- **실행 리포트**: [`docs/v2/reports/`](docs/v2/reports/)
- **V1 문서**: [`docs/v1/README.md`](docs/v1/README.md)

---

## 📞 문의 & 기여

- **이슈**: GitHub Issues
- **커밋 컨벤션**: `[Dxxx-y] <단계명> — <핵심 변경 1줄>`
- **코드 리뷰**: SSOT 규칙 준수 확인 필수
- **문서 검증**: `python scripts/check_ssot_docs.py` (ExitCode=0 필수)

---

## 📜 라이선스

MIT License

---

## 🎯 다음 단계 (D209-3 계획)

**현재:** D_ALPHA-2 진행 중 (OBI Filter & Ranking)

**다음:**
1. **D208**: Structural Normalization (ExecutionBridge 리네이밍)
2. **신 D209-1**: 주문 실패 시나리오 (429/timeout/reject/partial fill)
3. **신 D209-2**: 리스크 가드 통합 (position limit, loss cutoff, kill-switch)
4. **신 D209-3**: Wallclock 이중 검증 + Fail-Fast 전파 ← **현재 계획 중**
5. **신 D210**: LIVE 진입 설계/게이트 (구현은 봉인)

**최종 목표:** 
- ✅ TURN5 완료 (D207 Multi-Symbol Alpha Survey)
- ✅ SSOT-consistent Alpha Engine (D_ALPHA-2 진행 중)
- ⏳ Fail-Fast + ExitCode 체계 완성 (D209-3)
- ⏳ LIVE 봉인 검증 (D210-3)
- ⏳ HFT & Commercial Readiness (D210~D215)

---

**V2는 Engine-Centric, SSOT 강제, READ_ONLY 기본, Gate 100% PASS 필수.** 🚀

**마지막 업데이트:** 2026-02-17 | **Branch:** rescue/d207_6_multi_symbol_alpha_survey
