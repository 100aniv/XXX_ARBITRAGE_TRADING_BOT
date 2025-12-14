# D92-7-3: Context Scan & Baseline Sync

**Date:** 2025-12-14  
**Objective:** ZoneProfile SSOT 재통합 + 10m Gate 안정화

---

## Executive Summary

**D92-7-2 문제 분석:**
1. `zone_profiles_loaded.path = null` → ZoneProfile SSOT 미적용
2. `time_limit = 100%` → TP/SL 미트리거
3. `buy_fill_ratio = 26.15%` → 매우 낮은 체결률
4. `total_pnl_usd = -$1,624` → 큰 손실

**근본 원인:**
- ZoneProfile 자동 로드 로직 부재
- Exit Strategy 파라미터가 ZoneProfile과 연결 안 됨
- Fill Model 파라미터 너무 보수적

---

## 1. ZoneProfile SSOT 경로 확인

### 1.1 SSOT 파일 존재 확인
**Primary Path:** `config/arbitrage/zone_profiles_v2.yaml` ✅ 존재

**Backup Paths:**
- `config/arbitrage/zone_profiles_v2_new.yaml` ✅ 존재
- `config/arbitrage/zone_profiles_v2_original_backup.yaml` ✅ 존재
- `config/arbitrage/zone_profiles.yaml` ✅ 존재

**SSOT 선정:** `config/arbitrage/zone_profiles_v2.yaml` (v2 = current)

### 1.2 ZoneProfile 로딩 Call Chain

**Entry Point:**
```
scripts/run_d77_0_topn_arbitrage_paper.py:main()
  └─ args.zone_profile_file (CLI 인자)
      ├─ if args.symbol_profiles_json: ZoneProfileApplier.from_json()
      ├─ elif args.zone_profile_file: ZoneProfileApplier.from_file()
      └─ else: zone_profile_applier = None  ⚠️ 문제 발생 지점
```

**ZoneProfileApplier:**
```
arbitrage/core/zone_profile_applier.py
  ├─ from_file(yaml_path) → classmethod
  ├─ has_profile(symbol) → bool
  ├─ get_entry_threshold(symbol) → float
  └─ symbol_profiles: Dict[str, Dict]
```

**D92-7-2 실패 분기:**
- `args.zone_profile_file = None` (CLI에서 미지정)
- `zone_profile_applier = None` 전달
- `D77PAPERRunner.__init__()`:
  - `if self.zone_profile_applier:` → False
  - `yaml_path = None` → KPI에 `path: null` 기록됨

**해결 방안:**
```python
# main() 함수에서 DEFAULT SSOT 자동 로드
DEFAULT_ZONE_PROFILE_SSOT = "config/arbitrage/zone_profiles_v2.yaml"

if not args.zone_profile_file and not args.symbol_profiles_json:
    if os.path.exists(DEFAULT_ZONE_PROFILE_SSOT):
        args.zone_profile_file = DEFAULT_ZONE_PROFILE_SSOT
        logger.info(f"[D92-7-3] Auto-loading DEFAULT ZONE PROFILE SSOT: {DEFAULT_ZONE_PROFILE_SSOT}")
    else:
        raise FileNotFoundError(f"[D92-7-3] DEFAULT ZONE PROFILE SSOT not found: {DEFAULT_ZONE_PROFILE_SSOT}")
```

---

## 2. Exit Strategy 연결 확인

### 2.1 ExitStrategy 초기화
**Location:** `scripts/run_d77_0_topn_arbitrage_paper.py:418-426`

```python
self.exit_strategy = ExitStrategy(
    config=ExitConfig(
        tp_threshold_pct=0.25,
        sl_threshold_pct=0.20,
        max_hold_time_seconds=180.0,
        spread_reversal_threshold_bps=-10.0,
    )
)
```

**문제:**
- ExitConfig가 하드코딩됨
- ZoneProfile의 exit 파라미터와 연결 안 됨
- Zone별 TP/SL/time_limit 차별화 불가

**ZoneProfile v2 구조 (예상):**
```yaml
symbols:
  BTC:
    entry_threshold_bps: 25.0
    tp_threshold_pct: 0.30
    sl_threshold_pct: 0.15
    max_hold_time_seconds: 120.0
  ETH:
    entry_threshold_bps: 30.0
    tp_threshold_pct: 0.35
    sl_threshold_pct: 0.20
    max_hold_time_seconds: 150.0
```

**해결 방안:**
1. ZoneProfileApplier에 `get_exit_config(symbol)` 메서드 추가
2. Position별로 symbol에 맞는 ExitConfig 적용
3. 또는 ExitStrategy를 symbol-aware하게 리팩토링

**D92-7-3 최소 수정 원칙:**
- Position 등록 시 symbol별 TP/SL을 override하는 방식 (ExitStrategy 수정 최소화)

---

## 3. Fill Model 파라미터 확인

### 3.1 Fill Model 설정
**Location:** `arbitrage/config/settings.py` (예상)

**D92-7-2 결과:**
- `avg_buy_fill_ratio = 26.15%` ⚠️ 매우 낮음
- `avg_sell_fill_ratio = 100.00%` ✅ 정상

**원인 가설:**
1. `fill_ratio_mean` 파라미터가 너무 낮게 설정 (예: 0.3)
2. Orderbook depth 모델이 너무 보수적
3. Buy side만 낮은 이유: bid side depth가 ask side보다 얕게 모델링됨

**설정 파일 확인 필요:**
- `configs/paper/topn_arb_baseline.yaml`
- `arbitrage/config/settings.py` → `fill_model` section

**조정 방향:**
- `fill_ratio_mean`: 0.3 → 0.6 (50% 목표를 위해)
- 또는 `fill_ratio_std` 감소하여 분산 줄이기

---

## 4. ENV/Secrets SSOT 확인

### 4.1 .env.paper 로딩 확인
**Current Logic:**
```python
# arbitrage/config/settings.py
ARBITRAGE_ENV = os.getenv("ARBITRAGE_ENV", "local_dev")
dotenv_path = f".env.{ARBITRAGE_ENV}"
load_dotenv(dotenv_path)
```

**문제:**
- `ARBITRAGE_ENV` 환경변수가 설정 안 되면 `.env.local_dev` 로드
- `.env.paper` 로드 안 됨

**D92-7-2 수정 (settings.py):**
- `fail_fast_real_paper` 파라미터 추가됨
- 하지만 실제 ENV 강제는 run_d77_0에서 수행 안 함

**해결 방안:**
```python
# run_d77_0_topn_arbitrage_paper.py:main()
if args.data_source == "real":
    os.environ["ARBITRAGE_ENV"] = "paper"
    logger.info("[D92-7-3] REAL mode: Forcing ARBITRAGE_ENV=paper")
```

### 4.2 .gitignore 확인
**Status:** `.env*` 패턴 이미 포함됨 ✅

---

## 5. 계측 필드 현황

### 5.1 D92-7-2에서 추가된 필드
```python
"market_data_updates_count": 0,
"spread_samples_count": 0,
"entry_signals_count": 0,
"entry_attempts_count": 0,
"entry_rejections_by_reason": {...},
"exceptions_count": 0,
"last_exception_summary": None,
```

**문제:** 
- 필드는 정의되었으나, 실제 카운트 로직이 구현 안 됨
- D92-7-2에서 syntax error로 인해 롤백됨

### 5.2 D92-7-3 추가 필요 계측
**Exit Eval Counters:**
```python
"tp_eval_count": 0,
"sl_eval_count": 0,
"time_limit_eval_count": 0,
"spread_reversal_eval_count": 0,
"triggered_tp": 0,
"triggered_sl": 0,
"triggered_time_limit": 0,
"triggered_spread_reversal": 0,
```

**Fill Counters:**
```python
"buy_order_attempts": 0,
"buy_fills": 0,
"buy_partial": 0,
"buy_cancel": 0,
"sell_order_attempts": 0,
"sell_fills": 0,
"sell_partial": 0,
"sell_cancel": 0,
```

---

## 6. 테스트 파일 SSOT

### 6.1 기존 ZoneProfile 테스트
- `tests/test_d90_4_zone_profile_yaml.py` ✅
- `tests/test_d91_1_symbol_mapping.py` ✅
- `tests/test_d92_1_fix_zone_profile_integration.py` ✅

### 6.2 D92-7-3 추가 테스트
**신규 파일:** `tests/test_d92_7_3_zone_profile_ssot.py`

**테스트 항목:**
1. DEFAULT SSOT 자동 로드
2. zone_profiles_loaded.path != null
3. sha256 해시 기록
4. profiles_applied 심볼별 요약

---

## 7. D92 ROADMAP 동기화

### 7.1 현재 상태
- D92-6: PnL SSOT + Exit 정상화 ✅
- D92-7: REAL PAPER 재검증 ❌ (Zero Trades)
- D92-7-2: Zero Trades 해결 ⚠️ (새로운 문제 발견)
- D92-7-3: ZoneProfile SSOT + 10m Gate 안정화 (진행 중)

### 7.2 다음 단계
- D92-7-4: 1-Hour REAL PAPER (Gate 통과 후)
- D92-8: Threshold Sweep (ZoneProfile 기반)

---

## 8. 작업 우선순위 (D92-7-3)

### Priority 1: ZoneProfile SSOT 강제 (AC-1)
1. DEFAULT SSOT 자동 로드 로직 추가
2. KPI에 path/sha256/mtime/profiles_applied 기록 강제
3. 단위테스트 추가

### Priority 2: Exit Strategy 연결 (AC-2 해결)
1. ZoneProfileApplier에 `get_exit_config()` 추가
2. Position별 symbol-aware TP/SL 적용
3. Exit eval 카운터 구현

### Priority 3: Fill Model 조정 (AC-2 해결)
1. Fill Model 설정 파일 확인
2. `fill_ratio_mean` 조정 (0.3 → 0.6)
3. Fill 카운터 구현

### Priority 4: ENV SSOT 강제 (AC-1)
1. `data_source=real` 시 `ARBITRAGE_ENV=paper` 강제
2. 키 존재 여부 마스킹 로그

### Priority 5: Kill-switch (AC-2)
1. `total_pnl_usd <= -300` 시 즉시 중단
2. 직전 RT 상세 로그 저장

---

## 9. 파일 실존 확인

```powershell
# 문서 생성 후 확인
ls docs/D92/D92_7_3_*.md
git status docs/D92/
```

**생성 예정 문서:**
- `D92_7_3_CONTEXT_SCAN.md` ✅ (본 파일)
- `D92_7_3_ENV_SSOT.md` (STEP 1)
- `D92_7_3_GATE_10M_ANALYSIS.md` (STEP 5)
- `D92_7_3_IMPLEMENTATION_SUMMARY.md` (STEP 6)

---

## Next Steps

**STEP 1:** ENV/SECRETS SSOT 강제  
**STEP 2:** ZoneProfile SSOT 재통합 (핵심)  
**STEP 3:** Exit/Fill 계측 + 10m Gate 안정화  
**STEP 4:** Fast Gate + Core Regression  
**STEP 5:** 10m REAL PAPER Gate 실행  
**STEP 6:** ROADMAP/문서 동기화  
**STEP 7:** Git Commit + Push
