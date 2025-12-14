# D92-7-2 CONTEXT SCAN

**Date**: 2025-12-14  
**Objective**: Zero Trades 원인 분해 + REAL PAPER env/zone SSOT 확정

---

## 1. ROOT SCAN 결과

### 1.1 기존 모듈/경로 재사용 가능 항목

**✅ Settings 로드 (SSOT 확정됨)**
- **위치**: `arbitrage/config/settings.py` → `Settings` 클래스
- **로딩 메서드**: `Settings.from_env()` (ARBITRAGE_ENV 기반)
- **env 파일 로딩 규칙**:
  - ARBITRAGE_ENV=paper → `.env.paper` 로드
  - ARBITRAGE_ENV=live → `.env.live` 로드
  - ARBITRAGE_ENV=local_dev → `.env.local_dev` 로드
- **API 키 필드**: `upbit_access_key`, `upbit_secret_key`, `binance_api_key`, `binance_api_secret`

**✅ Zone Profile Applier (재사용 가능)**
- **위치**: `arbitrage/core/zone_profile_applier.py` → `ZoneProfileApplier` 클래스
- **로딩 메서드**:
  - `ZoneProfileApplier.from_json(json_str)` (JSON 문자열)
  - `ZoneProfileApplier.from_file(file_path)` (YAML 파일)
- **기능**:
  - 심볼별 Zone Profile 매핑
  - Entry threshold 계산 (`_compute_thresholds`)
  - Zone boundaries, weights 적용
  - Profile 적용 여부 로깅

**✅ Zone Profiles v2 YAML**
- **표준 경로**: `config/arbitrage/zone_profiles_v2.yaml`
- **백업 경로**:
  - `config/arbitrage/zone_profiles_v2_new.yaml`
  - `config/arbitrage/zone_profiles_v2_original_backup.yaml`
- **구조**:
  ```yaml
  profiles:
    advisory_z2_focus:
      name: "Advisory Z2 Focus"
      weights: [0.5, 3.0, 1.5, 0.5]
      mode: "advisory"
  symbol_mappings:
    BTC: "advisory_z2_focus"
    ETH: "advisory_z2_focus"
  ```

**✅ run_d77_0_topn_arbitrage_paper.py (Zone Profile 적용 경로)**
- **Lines 1113-1121**: Zone Profile Applier 초기화
  - `--symbol-profiles-json` (JSON 문자열)
  - `--zone-profile-file` (YAML 파일 경로)
  - 둘 다 없으면 → `zone_profile_applier = None` (기본 threshold 사용)

**✅ .env.paper (API 키 이미 설정됨)**
- UPBIT_ACCESS_KEY: 설정됨
- UPBIT_SECRET_KEY: 설정됨
- BINANCE_API_KEY: 설정됨
- BINANCE_API_SECRET: 설정됨

**✅ .gitignore (env 파일 보호 이미 완료)**
- `.env`, `.env.local_dev`, `.env.paper`, `.env.live` 모두 제외
- `!.env.*.example` 예외 처리로 example 파일은 허용

---

## 2. D92-7 Zero Trades 원인 추정

### 2.1 증거 기반 분석

**D92-7 KPI 결과**:
```json
{
  "total_trades": 0,
  "round_trips_completed": 0,
  "zone_profiles_loaded": {
    "path": null,
    "sha256": null,
    "mtime": null,
    "profiles_applied": {}
  }
}
```

**D92-5 KPI 결과 (동일 증상)**:
```json
{
  "total_trades": 0,
  "zone_profiles_loaded": {
    "path": "arbitrage\\config\\zone_profiles_v2.yaml",
    "profiles_applied": {
      "BTC": "advisory_z2_focus",
      "ETH": "advisory_z2_focus",
      "XRP": "advisory_z2_focus",
      "SOL": "advisory_z3_focus",
      "DOGE": "advisory_z2_balanced"
    }
  }
}
```

**D92-4 KPI 결과 (거래 발생)**:
```json
{
  "total_trades": 6,
  "round_trips_completed": 3,
  "zone_profiles_loaded": {
    "path": "arbitrage\\config\\zone_profiles_v2.yaml",
    "profiles_applied": {...}
  }
}
```

### 2.2 원인 분해 (가설 → 검증)

| 가설 | D92-7 증거 | D92-5 증거 | D92-4 증거 | 결론 |
|---|---|---|---|---|
| **H1: API 키 미설정** | Warning: UPBIT_ACCESS_KEY not set | 동일 | N/A | ❌ **오진**: .env.paper에 키 설정됨 확인 |
| **H2: Zone Profile 미적용** | path=null, profiles_applied={} | path!=null, profiles_applied!=null | path!=null, profiles_applied!=null | ⚠️ **D92-7만 해당** |
| **H3: Entry Threshold 과도** | 계측 없음 | 계측 없음 | threshold_bps=5.0 (sweeps) | ⚠️ **가능성 있음** |
| **H4: 시장 데이터 미수신** | 계측 없음 | 계측 없음 | N/A | ⚠️ **계측 필요** |
| **H5: 진입 신호 발생 0회** | 계측 없음 | 계측 없음 | N/A | ⚠️ **계측 필요** |

**핵심 발견**:
1. D92-7은 `--zone-profile-file` 인자 없이 실행 → zone profile 미적용
2. D92-5는 zone profile이 적용되었으나 여전히 trades=0 → threshold 또는 시장데이터 문제
3. **API 키 미설정은 오진**: .env.paper에 키가 이미 존재함

---

## 3. 필요한 수정 사항 (최소 개입)

### 3.1 D1: ENV/SECRET SSOT 확정

**✅ 이미 완료된 항목**:
- `.env.paper` 존재 및 API 키 설정됨
- `.gitignore`에 env 파일 보호 규칙 존재

**🔧 필요한 작업**:
1. ENV 로딩 fail-fast 로직 추가 (REAL PAPER 모드에서 ARBITRAGE_ENV!=paper면 즉시 종료)
2. `docs/SETUP/SECRETS_AND_ENV.md` 생성 (키 발급/주입 방법 문서화)
3. `.env.paper.example` / `.env.live.example` 존재 확인 (이미 존재함 확인됨)

### 3.2 D2: ZoneProfile/Threshold 강제 적용

**🔧 필요한 작업**:
1. run_d77_0에 `--zone-profile-file` 기본값 추가:
   - 기본값: `config/arbitrage/zone_profiles_v2.yaml`
   - REAL PAPER 모드에서는 zone profile 필수 로드로 강제
2. KPI에 zone profile 메타데이터 기록 보장:
   - path, sha256, mtime
   - profiles_applied (심볼별)
   - entry_threshold_bps (최종값)

### 3.3 D3: ZeroTrades RootCause 계측

**🔧 필요한 작업**:
1. 시장데이터 수신 계측:
   - Top-of-book 갱신 카운트 (최근 N초)
   - Orderbook 갱신 카운트
2. 진입 신호 발생 계측:
   - Spread > threshold 카운트
   - Entry signal 발생 횟수
3. 포지션 진입 시도/거절 사유:
   - RiskGuard triggers
   - Inventory limit
4. KPI에 추가:
   - `market_data_updates_count`
   - `entry_signals_count`
   - `entry_attempts_count`
   - `entry_rejections` (사유별)

---

## 4. 기존 스크립트 재사용 계획

### 4.1 run_d77_0_topn_arbitrage_paper.py 수정

**수정 위치**: Lines 1113-1121 (Zone Profile 초기화)

**변경 전**:
```python
zone_profile_applier = None
if args.symbol_profiles_json:
    zone_profile_applier = ZoneProfileApplier.from_json(args.symbol_profiles_json)
elif args.zone_profile_file:
    zone_profile_applier = ZoneProfileApplier.from_file(args.zone_profile_file)
else:
    logger.warning("[D92-1-FIX] No Zone Profiles provided - using default entry thresholds")
```

**변경 후**:
```python
# D92-7-2: REAL PAPER에서는 zone profile 필수
if args.data_source == "real" and not args.zone_profile_file:
    args.zone_profile_file = "config/arbitrage/zone_profiles_v2.yaml"
    logger.info(f"[D92-7-2] REAL PAPER mode: Auto-loading zone profiles from {args.zone_profile_file}")

zone_profile_applier = None
if args.symbol_profiles_json:
    zone_profile_applier = ZoneProfileApplier.from_json(args.symbol_profiles_json)
elif args.zone_profile_file:
    zone_profile_applier = ZoneProfileApplier.from_file(args.zone_profile_file)
else:
    logger.warning("[D92-1-FIX] No Zone Profiles provided - using default entry thresholds")
```

### 4.2 Settings.from_env() fail-fast 추가

**수정 위치**: `arbitrage/config/settings.py` Lines 236+

**추가 내용**:
```python
@classmethod
def from_env(cls, overrides=None, secrets_provider=None, fail_fast_real_paper=False):
    """
    Args:
        fail_fast_real_paper: REAL PAPER 모드에서 env/키 검증 강제
    """
    env_val = os.getenv("ARBITRAGE_ENV", "local_dev")
    
    # D92-7-2: REAL PAPER fail-fast
    if fail_fast_real_paper and env_val != "paper":
        raise ValueError(
            f"REAL PAPER mode requires ARBITRAGE_ENV=paper, got: {env_val}. "
            f"Check .env.paper file and ARBITRAGE_ENV variable."
        )
    
    # ... 기존 로직
```

---

## 5. 실행 계획

### 5.1 10분 Gate (Zero Trades 원인 계측)

**목표**: trades=0일 때 원인 분해 가능 여부 검증

**실행 명령**:
```bash
python scripts/run_d77_0_topn_arbitrage_paper.py \
    --universe top10 \
    --duration-minutes 10 \
    --monitoring-enabled \
    --data-source real \
    --zone-profile-file config/arbitrage/zone_profiles_v2.yaml \
    --kpi-output-path logs/d92-7-2/gate-10m-kpi.json
```

**기대 결과**:
- zone_profiles_loaded.path != null
- profiles_applied에 최소 1개 심볼
- trades=0이어도 원인 계측 데이터 존재:
  - market_data_updates_count > 0
  - entry_signals_count (0 또는 양수)
  - entry_rejections (사유별)

### 5.2 1시간 REAL PAPER

**목표**: D92-6 개선 효과 검증 (Exit 분포, PnL, 비용)

**실행 명령**:
```bash
python scripts/run_d77_0_topn_arbitrage_paper.py \
    --universe top10 \
    --duration-minutes 60 \
    --monitoring-enabled \
    --data-source real \
    --zone-profile-file config/arbitrage/zone_profiles_v2.yaml \
    --kpi-output-path logs/d92-7-2/longrun-1h-kpi.json
```

**Acceptance Criteria**:
- AC-A1: TIME_LIMIT < 80% (D92-4 대비 개선)
- AC-A2: TP/SL 중 최소 하나 > 0
- AC-B1: realized_pnl, fees, slippage 리포트
- AC-B2: RT당 PnL 분포 (median/p90/p10/worst 5)
- AC-C: Kill-switch 조건 검증

---

## 6. 다음 단계 (D1~D5)

1. **D1**: ENV/SECRET SSOT 문서화 + fail-fast 로직
2. **D2**: Zone Profile 강제 적용 (run_d77_0 수정)
3. **D3**: ZeroTrades RootCause 계측 추가
4. **D4**: 10m Gate + 1h PAPER 실행/검증
5. **D5**: 문서/ROADMAP 업데이트 + Git Commit/Push

---

**ROOT SCAN 완료**. D1 단계로 진행합니다.
