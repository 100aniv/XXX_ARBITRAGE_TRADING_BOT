# D98-4 AS-IS 스캔: Live Key 로딩 진입점 분석

**날짜**: 2025-12-19  
**목표**: LIVE API Key 로딩/사용 가능한 모든 진입점 식별  
**스캔 범위**: 전체 코드베이스 (scripts, arbitrage, tests, config)

---

## 1. 핵심 발견 사항 (Executive Summary)

### 1.1 키 로딩 진입점 (Primary Entry Points)
| 위치 | 파일 | 메서드/함수 | 위험도 |
|------|------|-------------|--------|
| **Settings Layer** | `arbitrage/config/settings.py` | `Settings.from_env()` | 🔴 HIGH |
| **Live API Init** | `arbitrage/upbit_live.py` | `UpbitLiveAPI.__init__()` | 🔴 HIGH |
| **Live API Init** | `arbitrage/binance_live.py` | `BinanceLiveAPI.__init__()` | 🔴 HIGH |
| **Scripts** | `scripts/*.py` (다수) | `os.getenv()` 직접 호출 | 🟡 MEDIUM |

### 1.2 환경 파일 목록
- `.env.live.example` - Live 키 템플릿 (실제 키 아님)
- `.env.paper` - Paper 키 (실제 API 호출용, 제한된 권한)
- `.env.local_dev` - Local 개발 키 (Mock/Test)

### 1.3 키 패턴 분석
```bash
# Upbit 키 패턴 (예상)
UPBIT_ACCESS_KEY=your_upbit_access_key_here  # 실제: 영숫자 문자열
UPBIT_SECRET_KEY=your_upbit_secret_key_here  # 실제: 영숫자 문자열

# Binance 키 패턴 (예상)
BINANCE_API_KEY=your_binance_api_key_here    # 실제: 영숫자 문자열
BINANCE_API_SECRET=your_binance_api_secret_here  # 실제: 영숫자 문자열
```

**한계**: 키 패턴 검증은 exchange-specific하며, 실제 키 형식을 알아야 정확한 검증 가능.

---

## 2. 키 로딩 진입점 상세 분석

### 2.1 Settings Layer (가장 중요)

#### `arbitrage/config/settings.py::Settings.from_env()`

**코드 위치**: Lines 283-288
```python
# Upbit (use secrets provider)
upbit_access_key = get_value("UPBIT_ACCESS_KEY")
upbit_secret_key = get_value("UPBIT_SECRET_KEY")

# Binance (use secrets provider)
binance_api_key = get_value("BINANCE_API_KEY")
binance_api_secret = get_value("BINANCE_API_SECRET")
```

**특징**:
- `get_value()` 헬퍼 함수 사용 (secrets_provider 또는 os.getenv fallback)
- 환경 변수 `ARBITRAGE_ENV`로 환경 분기 (local_dev/paper/live)
- D78-2 Secrets Provider 지원 (선택적)

**현재 Guard**: ❌ 없음

**위험 시나리오**:
1. 개발자가 `.env.paper`에서 작업 중 실수로 `.env.live` 키를 복사
2. `ARBITRAGE_ENV=paper`지만 LIVE 키가 로드되어 실제 주문 가능
3. 테스트 실행 시 LIVE 키가 환경변수에 남아있어 우발적 사용

---

### 2.2 Live API Initialization

#### `arbitrage/upbit_live.py::UpbitLiveAPI.__init__()`

**코드 위치**: Lines 41-51
```python
def __init__(self, config: Dict[str, Any]):
    api_key = config.get("api_key", "")
    mock_mode = not api_key
    super().__init__(config, mock_mode=mock_mode)
    
    self.api_key = api_key
    self.api_secret = config.get("api_secret", "")
    self.rest_url = config.get("rest_url", "https://api.upbit.com")
```

**특징**:
- `config` dict에서 키 직접 수신
- `api_key` 없으면 `mock_mode=True` 자동 설정
- Settings에서 키를 받아 여기로 전달됨

**현재 Guard**: ❌ 없음 (키 검증 없음)

---

#### `arbitrage/binance_live.py::BinanceLiveAPI.__init__()`

**코드 위치**: Lines 41-51
```python
def __init__(self, config: Dict[str, Any]):
    api_key = config.get("api_key", "")
    mock_mode = not api_key
    super().__init__(config, mock_mode=mock_mode)
    
    self.api_key = api_key
    self.api_secret = config.get("api_secret", "")
    self.rest_url = config.get("rest_url", "https://api.binance.com")
```

**특징**: Upbit와 동일 패턴

**현재 Guard**: ❌ 없음 (키 검증 없음)

---

### 2.3 Scripts 직접 키 로딩

#### `scripts/check_required_secrets.py`

**코드 위치**: Lines 53-56
```python
upbit_key = os.getenv("UPBIT_ACCESS_KEY")
upbit_secret = os.getenv("UPBIT_SECRET_KEY")
binance_key = os.getenv("BINANCE_API_KEY")
binance_secret = os.getenv("BINANCE_API_SECRET")
```

**용도**: Preflight 체크 (키 존재 여부만 확인)

**위험도**: 🟡 MEDIUM (읽기 전용, 하지만 키 검증 없음)

---

#### `scripts/run_gate_10m_ssot.py`, `scripts/run_gate_10m_ssot_v3_2.py`

**코드 위치**: Lines 48-49
```python
has_upbit = bool(os.getenv("UPBIT_ACCESS_KEY") and os.getenv("UPBIT_SECRET_KEY"))
has_binance = bool(os.getenv("BINANCE_API_KEY") and os.getenv("BINANCE_API_SECRET"))
```

**용도**: Runner 스크립트 (키 존재 확인 후 실행)

**위험도**: 🟡 MEDIUM (읽기 전용, 하지만 키 검증 없음)

---

### 2.4 Exchange Adapter Initialization

#### `arbitrage/exchanges/upbit_spot.py`, `arbitrage/exchanges/binance_futures.py`

**특징**:
- D98-2에서 `@enforce_readonly` 데코레이터로 `create_order`, `cancel_order` 보호
- 하지만 **키 로딩 시점**에는 guard 없음

**현재 Guard**: ✅ 주문 실행 레벨만 보호 (D98-2)

---

## 3. 환경 분기 규칙 (AS-IS)

### 3.1 현재 환경 분류

| 환경 | `ARBITRAGE_ENV` | 용도 | 키 요구사항 |
|------|-----------------|------|-------------|
| **local_dev** | `local_dev` | 로컬 개발 (Mock) | ❌ 불필요 (Mock keys) |
| **paper** | `paper` | Paper Trading | ✅ 실제 키 필요 (읽기 전용) |
| **live** | `live` | Live Trading | 🔴 실제 키 필요 (거래 권한) |

### 3.2 현재 키 로딩 로직

**`arbitrage/config/settings.py::from_env()` (Lines 268-273)**:
```python
# Environment
env_str = get_value("ARBITRAGE_ENV", "local_dev").lower()
try:
    env = RuntimeEnv(env_str)
except ValueError:
    print(f"Warning: Invalid ARBITRAGE_ENV '{env_str}', defaulting to local_dev")
    env = RuntimeEnv.LOCAL_DEV
```

**문제점**:
- 환경 변수만으로 분기, **키의 실제 용도는 검증 안 함**
- `ARBITRAGE_ENV=paper`여도 LIVE 키 로드 가능
- `ARBITRAGE_ENV=live` + 테스트 실행 = 실수로 LIVE 키 사용 가능

---

## 4. 우회 경로 분석 (Bypass Scenarios)

### 4.1 시나리오 1: 환경 변수 오염

**상황**:
```bash
# 개발자가 .env.live를 실수로 로드
export ARBITRAGE_ENV=paper
export UPBIT_ACCESS_KEY=<LIVE_KEY>  # 실수로 LIVE 키
export UPBIT_SECRET_KEY=<LIVE_SECRET>
```

**결과**: Paper 모드지만 LIVE 키가 로드됨 → 실주문 가능성

**현재 방어**: ❌ 없음

---

### 4.2 시나리오 2: 테스트 환경에서 LIVE 키 잔존

**상황**:
```bash
# 이전 LIVE 테스트 후 환경변수 미정리
pytest tests/test_live_executor.py  # LIVE 키가 환경에 남아있음
```

**결과**: 테스트가 실제 API 호출 시도 (dry_run=False인 경우)

**현재 방어**: ❌ 없음

---

### 4.3 시나리오 3: CI/CD 파이프라인 오설정

**상황**:
```yaml
# GitHub Actions에서 실수로 LIVE secrets 주입
env:
  ARBITRAGE_ENV: paper
  UPBIT_ACCESS_KEY: ${{ secrets.LIVE_UPBIT_KEY }}  # 실수
```

**결과**: CI 테스트에서 LIVE 키 사용

**현재 방어**: ❌ 없음

---

## 5. 기존 안전장치 현황

### 5.1 D98-1~3 ReadOnlyGuard (실행 레벨)

**범위**: 주문 실행 시점 차단
- D98-1: PaperExchange
- D98-2: Live Adapters (Upbit/Binance)
- D98-3: LiveExecutor

**한계**: **키 로딩 시점**에는 개입하지 않음

---

### 5.2 dry_run 플래그

**범위**: LiveExecutor
- `dry_run=True`면 로그만 출력, 실제 주문 안 함

**한계**:
- 코드 레벨 플래그 (환경 변수 아님)
- 실수로 `dry_run=False` 설정 가능

---

## 6. D98-4 구현 요구사항 도출

### 6.1 핵심 요구사항

1. **키 로딩 게이트**: `Settings.from_env()` 진입 시 환경 검증
2. **Fail-Closed**: 환경 불일치 시 즉시 예외 발생 (프로세스 종료)
3. **환경 분기 규칙**:
   - `ARBITRAGE_ENV=live` + `LIVE_ENABLED=true` → LIVE 키 허용
   - 그 외 → LIVE 키 감지 시 차단
4. **키 식별**: LIVE vs Paper 키 구분 (allowlist 또는 패턴 기반)

---

### 6.2 구현 위치

**Primary Guard**: `arbitrage/config/settings.py::from_env()` (Lines 283-288)
- 키 로딩 직전에 환경 검증
- LIVE 키 감지 시 즉시 예외 발생

**Secondary Guard** (선택적): Live API `__init__()` 메서드
- Defense-in-depth 2차 방어선

---

### 6.3 키 식별 전략

#### Option A: Allowlist 방식 (권장)
```python
# .env.paper.keys (안전한 키 목록)
SAFE_UPBIT_KEYS = ["paper_key_1", "test_key_2"]
SAFE_BINANCE_KEYS = ["paper_binance_1", "testnet_key_2"]

# Guard: 로드된 키가 allowlist에 있는지 확인
if env != RuntimeEnv.LIVE:
    if upbit_access_key not in SAFE_UPBIT_KEYS:
        raise LiveKeyError("Non-live environment에서 LIVE Upbit 키 감지")
```

**장점**: 정확함, False positive 없음  
**단점**: Allowlist 유지보수 필요

---

#### Option B: 환경변수 Prefix 방식
```bash
# Paper/Dev 키는 prefix로 구분
PAPER_UPBIT_ACCESS_KEY=paper_abc123
LIVE_UPBIT_ACCESS_KEY=live_xyz789

# Guard: LIVE_ prefix 키 감지
if env != RuntimeEnv.LIVE:
    if "LIVE_" in key_name:
        raise LiveKeyError("...")
```

**장점**: 간단함, 명확함  
**단점**: 기존 키 네이밍 변경 필요

---

#### Option C: 명시적 LIVE_ENABLED 플래그 (최종 권장)
```python
# Settings에서 LIVE_ENABLED 확인
live_enabled = os.getenv("LIVE_ENABLED", "false").lower() == "true"

if live_enabled:
    # ARBITRAGE_ENV=live 검증
    if env != RuntimeEnv.LIVE:
        raise LiveKeyError("LIVE_ENABLED=true지만 ARBITRAGE_ENV != live")
else:
    # LIVE 키 사용 시도 감지 (휴리스틱)
    # 예: .env.live 파일 존재 확인, 키 길이 등
    pass
```

**장점**: 명시적, 오버라이드 가능  
**단점**: 여전히 키 식별 로직 필요

---

## 7. 테스트 시나리오 도출

### 7.1 단위 테스트

1. **Test: dev 환경에서 LIVE 키 차단**
   - `ARBITRAGE_ENV=local_dev` + LIVE 키 → `LiveKeyError`
2. **Test: paper 환경에서 LIVE 키 차단**
   - `ARBITRAGE_ENV=paper` + LIVE 키 → `LiveKeyError`
3. **Test: live 환경 + LIVE_ENABLED=true → 허용**
   - `ARBITRAGE_ENV=live` + `LIVE_ENABLED=true` + LIVE 키 → OK
4. **Test: live 환경 + LIVE_ENABLED=false → 차단**
   - `ARBITRAGE_ENV=live` + `LIVE_ENABLED=false` + LIVE 키 → `LiveKeyError`

---

### 7.2 통합 테스트

1. **Test: Settings.from_env() 호출 차단**
   - Mock 환경변수 주입 → Guard 트리거 확인
2. **Test: Live API 초기화 차단**
   - UpbitLiveAPI/BinanceLiveAPI 생성 시 Guard 작동 확인
3. **Test: Preflight 스크립트에서 키 검증**
   - `scripts/d98_live_preflight.py` 실행 시 LIVE 키 감지

---

## 8. Evidence 요구사항

### 8.1 스캔 산출물 (이 문서)
- ✅ `docs/D98/D98_4_AS_IS_SCAN.md`

### 8.2 구현 산출물 (예정)
- `arbitrage/config/live_key_guard.py` (새 모듈)
- `arbitrage/config/settings.py` (Guard 통합)

### 8.3 테스트 산출물 (예정)
- `tests/test_d98_4_live_key_guard.py` (단위 테스트)
- `tests/test_d98_4_integration_key_blocking.py` (통합 테스트)
- `docs/D98/evidence/d98_4_test_results_*.txt` (테스트 로그)

### 8.4 문서 산출물 (예정)
- `docs/D98/D98_4_REPORT.md` (구현 보고서, 한국어)
- `D_ROADMAP.md` (D98-4 상태 업데이트)
- `CHECKPOINT_2025-12-17_ARBITRAGE_LITE_MID_REVIEW.md` (체크포인트 업데이트)

---

## 9. 결론

### 9.1 핵심 발견
1. **Settings.from_env()가 단일 진입점** - 여기에 Guard 배치 필수
2. **환경 검증 없음** - `ARBITRAGE_ENV`만으로 분기, 키 실제 용도 미검증
3. **우회 가능성 다수** - 환경변수 오염, 테스트 잔존 키, CI 오설정 등

### 9.2 D98-4 구현 방향
- **Primary Guard**: `Settings.from_env()` (키 로딩 직전)
- **전략**: `LIVE_ENABLED` 명시적 플래그 + 환경 검증
- **Fail-Closed**: 불일치 시 즉시 예외 → 프로세스 종료
- **Defense-in-Depth**: D98-3 (Executor) + D98-4 (Key Loading)

### 9.3 다음 단계
1. `LiveKeyGuard` 모듈 설계 및 구현 (STEP 2)
2. 단위/통합 테스트 작성 (STEP 3)
3. Fast Gate + Regression 실행 (STEP 4)
4. 문서 동기화 (STEP 5-6)

---

**스캔 완료**: 2025-12-19  
**다음 작업**: STEP 2 - LiveKeyGuard 구현
