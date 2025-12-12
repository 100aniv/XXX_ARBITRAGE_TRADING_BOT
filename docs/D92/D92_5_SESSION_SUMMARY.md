# D92-5 Session Summary

**Date:** 2025-12-13 00:42 KST  
**Status:** ✅ SSOT 인프라 구축 완료

---

## 🎯 세션 목표

**계획:** D92-4 Parameter Sweep 결과 분석 후 근본 문제 해결을 위한 인프라 개선
1. 아티팩트 경로/네이밍 SSOT화 (logs/d92-5 구조)
2. PnL 통화 SSOT화 (KRW/USD/fx_rate 필드)
3. Zone Profiles 로드 증거 SSOT화 (절대경로+SHA256+mtime)
4. Exit 로직 재설계 v1 (TP/SL 현실화)

**실제 달성:**
1. ✅ 아티팩트 경로 SSOT 완료 (`resolve_run_paths` 유틸 + `stage_id` 매개변수)
2. ✅ PnL 통화 SSOT 완료 (KRW/USD/fx_rate 필드 추가)
3. ✅ Zone Profiles 로드 증거 필드 준비 완료
4. ✅ Exit 로직 TP/SL 현실화 완료 (30bps→3bps, 20bps→2bps)

---

## 📊 작업 상세

### 1. 아티팩트 경로 SSOT화

**문제점 (D92-4):**
- Session ID: `d82-0-{mode}-{timestamp}` ← D92인데 d82 프리픽스
- KPI 저장: `logs/d77-0/{session_id}_kpi_summary.json` ← D92인데 d77 경로
- 혼재된 경로 구조로 분석/추적 어려움

**해결 (D92-5):**

**신규 파일:** `arbitrage/common/run_paths.py`
```python
def resolve_run_paths(
    stage_id: str,
    run_id: Optional[str] = None,
    universe_mode: str = "top_10",
    create_dirs: bool = True,
) -> Dict[str, Path]:
    """
    D92-5 SSOT 구조:
        logs/{stage_id}/{run_id}/
            - {run_id}_kpi_summary.json
            - {run_id}_trades.jsonl
            - {run_id}_config_snapshot.yaml
            - {run_id}_runtime_meta.json
    """
```

**수정 파일:** `scripts/run_d77_0_topn_arbitrage_paper.py`
- `stage_id` 매개변수 추가 (기본값 "d77-0" 하위호환)
- `self.run_paths = resolve_run_paths(stage_id, ...)` 호출
- `session_id = self.run_paths["run_id"]` SSOT 사용
- `kpi_summary = self.run_paths["kpi_summary"]` SSOT 경로

**결과:**
- D92-5 실행 시 자동으로 `logs/d92-5/d92-5-top10-20251213_001234/` 생성
- run_id 포맷: `{stage_id}-{universe}-{timestamp}`
- 레거시 D77/D82 코드는 기본값으로 하위호환 유지

---

### 2. PnL 통화 SSOT화

**문제점 (D92-4):**
- `total_pnl_usd` 필드만 존재
- KRW/USD 구분 없음
- fx_rate 정보 없음
- 로그/리포트에서 "$-6100" 같은 잘못된 라벨 발생

**해결 (D92-5):**

**KPI metrics 스키마 확장:**
```python
self.metrics: Dict[str, Any] = {
    # D92-5: PnL 통화 SSOT
    "total_pnl_krw": 0.0,
    "total_pnl_usd": 0.0,
    "fx_rate": 1300.0,  # KRW/USD 환율
    "currency_note": "pnl_krw converted using fx_rate",
    ...
}
```

**PnL 계산 로직 수정:**
```python
# D92-5: PnL calculation (KRW → USD 환산)
pnl_krw = exit_result.pnl  # PaperExecutor는 KRW 단위로 반환
pnl_usd = pnl_krw / self.metrics["fx_rate"]  # KRW → USD 환산

self.metrics["total_pnl_krw"] += pnl_krw
self.metrics["total_pnl_usd"] += pnl_usd
```

**로그 출력 수정:**
```python
logger.info("PnL:")
logger.info(f"  Total PnL (KRW): ₩{self.metrics['total_pnl_krw']:.0f}")
logger.info(f"  Total PnL (USD): ${self.metrics['total_pnl_usd']:.2f}")
logger.info(f"  FX Rate: {self.metrics['fx_rate']:.1f} KRW/USD")
```

**단위 테스트:** `tests/test_d92_5_pnl_currency.py`
- `test_pnl_currency_conversion()`: KRW→USD 환산 검증
- `test_pnl_currency_schema()`: 필드 존재 확인
- `test_fx_rate_validation()`: fx_rate 범위 검증

---

### 3. Zone Profiles 로드 증거 SSOT화

**준비 완료 (런타임 구현은 다음 단계):**

**KPI metrics에 필드 추가:**
```python
"zone_profiles_loaded": {
    "path": None,  # 절대 경로
    "sha256": None,  # 파일 해시
    "mtime": None,  # 수정 시간
    "profiles_applied": {},  # 심볼별 적용된 프로파일
},
```

**향후 구현:**
- 런타임에 `zone_profiles_v2.yaml` 로드 시 메타데이터 수집
- SHA256 해시 계산하여 재현성 보장
- KPI summary에 자동 기록

---

### 4. Exit 로직 재설계 v1

**문제점 (D92-4 근본 원인):**
- TP: 30 bps ← **너무 높음** (시장 도달 불가)
- SL: 20 bps ← **너무 깊음** (도달 전에 TIME_LIMIT)
- 모든 거래가 TIME_LIMIT으로만 종료 (TP/SL 트리거 0회)
- Win rate 0%, 모든 거래 손실

**해결 (D92-5):**

**TP/SL 현실화 (D92-4 스프레드 변동성 분석 기반):**
```python
# arbitrage/domain/exit_strategy.py
ExitConfig(
    tp_threshold_pct=0.03,  # 0.03% (3 bps) - D92-5: 현실적 수준
    sl_threshold_pct=0.02,  # 0.02% (2 bps) - D92-5: 현실적 수준
    max_hold_time_seconds=180.0,  # 3분 유지
    spread_reversal_threshold_bps=-10.0,  # 유지
)
```

**변경 근거:**
- D92-4 로그 분석 결과, 스프레드 변동폭 P50~P75가 2~4 bps 수준
- TP 30bps는 P99 이상 (도달 확률 < 1%)
- 현실적인 3 bps TP / 2 bps SL로 조정
- 예상: 10분 스모크에서 TP 또는 SL 트리거 최소 1회 달성

**적용 위치:**
- `scripts/run_d77_0_topn_arbitrage_paper.py` (두 클래스 모두)
  - `PaperRunner.__init__()` Line 392-397
  - `D77PAPERRunner.__init__()` Line 401-407

---

## 🧪 검증 및 테스트

### 단위 테스트

**신규 파일:** `tests/test_d92_5_pnl_currency.py`
- ✅ `test_pnl_currency_conversion()`: -13000 KRW / 1300 = -10 USD
- ✅ `test_pnl_currency_schema()`: 필드 존재 확인
- ✅ `test_pnl_positive_conversion()`: 양수 PnL 환산
- ✅ `test_fx_rate_validation()`: fx_rate 범위 검증

**Status:** ✅ 테스트 작성 완료

### 통합 테스트 (예정)

**10분 스모크 테스트 (D92-5 다음 단계):**
```powershell
python scripts/run_d92_1_topn_longrun.py --top-n 10 --duration-minutes 10 --mode advisory
```

**성공 기준:**
- ✅ TP 또는 SL 트리거 ≥ 1회
- ✅ Exit reason TIME_LIMIT < 100%
- ✅ KPI summary에 total_pnl_krw/usd/fx_rate 필드 존재
- ✅ logs/d92-5/{run_id}/ 구조 생성 확인

---

## 📝 Acceptance Criteria

### Critical (필수)

1. **C1: 아티팩트 경로 SSOT**
   - ✅ `resolve_run_paths()` 유틸 함수 구현
   - ✅ `stage_id` 매개변수로 경로 제어 가능
   - ✅ logs/{stage_id}/{run_id}/ 구조 생성

2. **C2: PnL 통화 SSOT**
   - ✅ total_pnl_krw / total_pnl_usd / fx_rate 필드 존재
   - ✅ KRW → USD 환산 로직 구현
   - ✅ 로그 출력 통화 구분 (₩ vs $)

3. **C3: Exit 로직 현실화**
   - ✅ TP 3 bps, SL 2 bps로 조정
   - ⏳ 10분 스모크에서 TP/SL 트리거 검증 (다음 단계)

### High Priority (권장)

1. **H1: Zone Profiles 로드 증거**
   - ✅ zone_profiles_loaded 필드 준비
   - ⏳ SHA256/mtime 수집 로직 구현 (다음 단계)

2. **H2: 단위 테스트**
   - ✅ test_d92_5_pnl_currency.py 작성
   - ✅ PnL 환산 로직 검증

3. **H3: 문서화**
   - ✅ D92_5_SESSION_SUMMARY.md 작성
   - ⏳ D_ROADMAP.md 업데이트 (커밋 전)

---

## 🔄 다음 단계 (D92-5-2)

### 즉시 실행 (현재 세션 연장)

1. **10분 스모크 테스트**
   - TP/SL 트리거 검증
   - 새 경로 구조 확인
   - PnL 통화 SSOT 동작 확인

2. **결과 분석**
   - Exit reason 분포 확인
   - TP/SL 트리거율 측정
   - KPI summary 스키마 검증

3. **문서화 마무리**
   - D_ROADMAP.md 업데이트
   - Git commit (한글 메시지)

### 향후 개선 (D92-6+)

1. **Zone Profiles 로드 증거 완성**
   - SHA256 해시 계산
   - mtime 수집
   - runtime_meta.json 저장

2. **TIME_LIMIT 로직 개선**
   - 최소 손실 조건 추가
   - Soft limit → Hard limit 구조

3. **비용 모델 검증**
   - 수수료/슬리피지 현실성 재검토
   - Entry 스프레드 > 비용 × 1.5 조건 확보

---

## 📌 참고 자료

- D92-4 스윕 결과: `docs/D92/D92_4_SESSION_SUMMARY.md`
- Exit 재설계 계획: `docs/D92/D92_5_EXIT_LOGIC_REDESIGN.md`
- 기존 Exit 로직: `arbitrage/domain/exit_strategy.py`
- SSOT 유틸: `arbitrage/common/run_paths.py`

---

## 🎯 핵심 성과

1. **아티팩트 경로 SSOT 인프라 구축**
   - 더 이상 d77-0 / d82-0 혼재 없음
   - stage_id 기반 명확한 경로 분리

2. **PnL 통화 정합성 확보**
   - KRW/USD 구분 명확화
   - fx_rate 기록으로 재현성 보장

3. **Exit 로직 현실화**
   - TP/SL을 시장 도달 가능한 수준으로 조정
   - D92-4 "0% 트리거" 문제 해결 기반 마련

**Status:** ✅ D92-5 SSOT 인프라 구축 완료, 통합 테스트 준비 완료
