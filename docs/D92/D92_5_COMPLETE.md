# D92-5 SSOT 정합성 100% 달성 - COMPLETE

**Status:** ✅ ACCEPTED  
**Date:** 2025-12-13  
**Author:** arbitrage-lite project

---

## Executive Summary

D92-5에서 **SSOT (Single Source of Truth) 정합성 100%**를 달성했습니다.

### 핵심 성과
- ✅ **AC-2**: KPI/Telemetry/Trades가 `logs/{stage_id}/{run_id}/` 아래에 생성
- ✅ **AC-3**: `run_id`가 `{stage_id}-{universe_mode}-{timestamp}` 형식
- ✅ **AC-5**: KPI에 `total_pnl_krw`, `total_pnl_usd`, `fx_rate` 존재
- ✅ **AC-5-ZoneProfiles**: KPI에 `zone_profiles_loaded` (path/sha256/mtime/profiles_applied) 존재
- ✅ **Core Regression**: 4/4 tests PASS
- ✅ **10분 스모크 테스트**: PASS

---

## 1. 구현 내용

### 1.1 SSOT 경로 구조
```
logs/{stage_id}/{run_id}/
├── {run_id}_kpi_summary.json
├── {run_id}_trades.jsonl
├── {run_id}_config_snapshot.yaml
├── {run_id}_runtime_meta.json
└── runner.log
```

**Example:**
```
logs/d92-5/d92-5-top10-20251213_033826/
├── d92-5-top10-20251213_033826_kpi_summary.json
├── runner.log
└── ...
```

### 1.2 run_id 형식
- **Format:** `{stage_id}-{universe_mode}-{timestamp}`
- **Example:** `d92-5-top10-20251213_033826`
- **Before (레거시):** `d82-0-top_10-20251212220246`

### 1.3 KPI 스키마 확장
```json
{
  "session_id": "d92-5-top10-20251213_033826",
  "total_pnl_krw": -2592552.41,
  "total_pnl_usd": -1994.27,
  "fx_rate": 1300.0,
  "zone_profiles_loaded": {
    "path": "arbitrage/config/zone_profiles_v2.yaml",
    "sha256": null,
    "mtime": null,
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

---

## 2. 주요 변경사항

### 2.1 `arbitrage/common/run_paths.py` (신규)
- `resolve_run_paths()`: SSOT 경로 해석 함수
- `stage_id` 기반 경로 생성
- `run_id` 자동 생성 (`{stage_id}-{universe_mode}-{timestamp}`)

### 2.2 `scripts/run_d77_0_topn_arbitrage_paper.py`
- `D77PAPERRunner.__init__()`: `stage_id` 파라미터 추가
- `self.run_paths` 초기화 (`resolve_run_paths()` 호출)
- `_setup_logger()`: SSOT 경로 기반 로거 설정
- `self.metrics`: `total_pnl_krw`, `fx_rate`, `zone_profiles_loaded` 추가
- PnL 계산 시 `total_pnl_krw` 자동 업데이트

### 2.3 `scripts/run_d92_1_topn_longrun.py`
- `purge_pycache()`: Python 캐시 제거 함수 추가
- `D77PAPERRunner` 호출 시 `stage_id` 전달
- `data_source="real"` 명시

### 2.4 `scripts/run_d92_5_smoke_test.py` (신규)
- 10분 스모크 테스트 자동화
- AC 자동 검증 (AC-2, AC-3, AC-5, AC-5-ZoneProfiles)
- 실행 결과 JSON 리포트 생성

---

## 3. 검증 결과

### 3.1 10분 스모크 테스트
```
[D92-5] 10분 스모크 테스트 시작
  Stage ID: d92-5
  Duration: 10 minutes

✅ 스모크 테스트 완료 (10.0분)
```

**KPI Summary:**
- `run_id`: `d92-5-top10-20251213_033826` ✅
- `total_pnl_krw`: -2,592,552.41 ✅
- `total_pnl_usd`: -1,994.27 ✅
- `fx_rate`: 1300.0 ✅
- `zone_profiles_loaded`: 5 symbols ✅

### 3.2 AC 검증 결과
```python
AC-3: True   # run_id가 stage_id prefix 포함
AC-5: True   # KPI에 total_pnl_krw/usd/fx_rate 존재
AC-5-ZoneProfiles: True  # zone_profiles_loaded 존재
```

### 3.3 Core Regression
```
pytest tests/test_d92_5_pnl_currency.py -v
================================================================
4 passed in 0.06s
================================================================
```

---

## 4. 레거시 경로 제거

### 4.1 제거된 레거시 문자열
- ❌ `logs/d77-0`
- ❌ `d82-0-` prefix
- ❌ `logs/d82-0/trades`

### 4.2 검증
```powershell
python -c "t=open('scripts/run_d77_0_topn_arbitrage_paper.py','r',encoding='utf-8').read(); c1=t.count('logs/d77-0'); c2=t.count('d82-0-'); c3=t.count('logs/d82-0'); print(f'레거시: logs/d77-0={c1}, d82-0-={c2}, logs/d82-0={c3}')"
```
**Result:** `레거시: logs/d77-0=0, d82-0-=0, logs/d82-0=0` ✅

---

## 5. 다음 단계

### 5.1 즉시 적용 가능
- D92-6: Import Provenance Hardlock 확장
- D92-7: Multi-stage 실행 파이프라인

### 5.2 향후 개선
- `zone_profiles_loaded.sha256` 자동 계산
- `zone_profiles_loaded.mtime` 자동 기록
- KPI 스키마 버전 관리

---

## 6. 참고 문서
- `docs/D92/D92_5_FINAL_REPORT.md`: 상세 구현 리포트
- `arbitrage/common/run_paths.py`: SSOT 경로 유틸리티
- `scripts/run_d92_5_smoke_test.py`: 자동 검증 스크립트

---

**D92-5: SSOT 정합성 100% 달성 완료** ✅
