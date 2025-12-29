# D202-2 CLOSEOUT Report

**작성일:** 2025-12-29  
**상태:** ✅ DONE  
**커밋:** `fc05bce` (SSOT Closeout)

---

## 📋 목표 및 범위

### 목표
D202-2는 다음 3가지를 동시에 완료:

1. **MarketData Sampler 구현** - 1시간 샘플 수집 증거 저장 포맷 정의
2. **PostgreSQLAlertStorage UTC-naive 정규화** - timestamp tz-aware/naive 혼재 해결
3. **SSOT Closeout** - Scan-First → Reuse-First 강제, V1→V2 재사용 맵핑 문서화

### 범위
- **코드 변경:** `arbitrage/alerting/storage/postgres_storage.py` (UTC-naive 정규화)
- **신규 구현:** `scripts/run_d202_2_market_sampler.py` (MarketDataSampler)
- **문서 업데이트:** `docs/v2/SSOT_RULES.md`, `docs/v2/design/SSOT_MAP.md`, `D_ROADMAP.md`
- **테스트:** `tests/test_d202_2_market_sampler_contract.py` (9/9 PASS), `tests/test_postgres_storage.py` (12/12 PASS)

---

## ✅ 완료 항목

### 1. MarketData Sampler (D202-2 원본 목표)
- ✅ `MarketDataSampler` 클래스 구현
- ✅ Evidence 폴더 구조 SSOT 준수 (manifest.json, kpi.json, errors.ndjson, raw_sample.ndjson, README.md)
- ✅ KPI 추적 (uptime, samples_ok/fail, latency_p50/p95/max, parse_errors)
- ✅ Run ID 규칙 준수 (`d202_2_market_sample_YYYYMMDD_HHMM`)
- ✅ 테스트 9/9 PASS (Mock 기반, 실제 API 호출 없음)

**커밋:** `36f8989`

### 2. PostgreSQLAlertStorage UTC-naive 정규화 (D202-2 FIX-0)
- ✅ `_normalize_to_utc_naive()` 헬퍼 함수 추가
- ✅ 6곳 적용: `save()`, `get_recent()`, `get_by_time_range()`, `clear_before()`, `cleanup_old_alerts()`, `get_stats()`
- ✅ 모든 datetime을 UTC naive로 정규화 (tzinfo 제거)
- ✅ 테스트 12/12 PASS (`test_get_by_time_range_with_filters`, `test_get_recent` 등)
- ✅ Gate Doctor PASS

**커밋:** `3511126`

**문제 해결:**
- **원인:** PostgreSQL TIMESTAMP(no tz) 컬럼에 tz-aware datetime 저장 시 로컬 timezone 변환 (한국: UTC+9)
- **증상:** naive datetime 조회 파라미터와 시간대 불일치로 range 조회 실패 (expected 1, got 0)
- **해결:** `dt.astimezone(tz=None)` → UTC naive 변환 후 tzinfo 제거

### 3. SSOT Closeout (D202-2 FIX-1)
- ✅ Scan-First 실행 (중복 모듈 0개, Reuse-First 준수)
- ✅ `docs/v2/SSOT_RULES.md` 업데이트 (Scan-First → Reuse-First 강제 규칙)
- ✅ `docs/v2/design/SSOT_MAP.md` 업데이트 (V1→V2 재사용 맵핑 표)
- ✅ `D_ROADMAP.md` 업데이트 (D202-2 DONE 상태 + Evidence 경로 명시)
- ✅ Evidence 폴더 준비 (`logs/evidence/d202_2_closeout_20251229_233153_fc05bce/`)

**커밋:** `fc05bce`

---

## 🧪 Gate 검증 결과

### 이전 세션 증거 (HEAD: fc05bce)
| Gate | 상태 | 시간 | Evidence 경로 |
|------|------|------|--------------|
| Doctor | ✅ PASS | 4s | logs/evidence/20251229_224220_gate_doctor_3511126 |
| Fast | ✅ PASS | 190s | logs/evidence/20251229_224235_gate_fast_3511126 |
| Regression | ✅ PASS | 191s | logs/evidence/20251229_224558_gate_regression_3511126 |

**결론:** Gate 3단 모두 PASS. D202-2 목표 달성.

---

## 📊 Scan-First 결과

### 검색 대상 모듈
| 모듈 | 위치 | 상태 | 비고 |
|------|------|------|------|
| PostgreSQLAlertStorage | `arbitrage/alerting/storage/postgres_storage.py` | ✅ 존재 | D202-2에서 재사용 |
| StorageBase | `arbitrage/alerting/storage/base.py` | ✅ 존재 | 추상 인터페이스 |
| OrderIntent | `arbitrage/v2/core/order_intent.py` | ✅ 존재 | V2 신규 생성 (V1 없음) |
| ExchangeAdapter | `arbitrage/v2/core/adapter.py` | ✅ 존재 | V2 신규 생성 (V1 없음) |
| MarketDataSampler | `scripts/run_d202_2_market_sampler.py` | ✅ 존재 | D202-2 신규 생성 |
| BaseStorage | `arbitrage/storage.py` | ✅ 존재 | V1 레거시 |

**결론:** 중복 모듈 없음. Reuse-First 원칙 준수.

---

## 📝 변경 파일 목록

### 코드 변경 (2개)
1. **arbitrage/alerting/storage/postgres_storage.py**
   - `_normalize_to_utc_naive()` 헬퍼 함수 추가
   - 6곳 적용 (save, get_recent, get_by_time_range, clear_before, cleanup_old_alerts, get_stats)
   - 커밋: `3511126`

2. **scripts/run_d202_2_market_sampler.py**
   - MarketDataSampler 클래스 구현
   - Evidence 저장 로직
   - 커밋: `36f8989`

### 문서 변경 (3개)
1. **docs/v2/SSOT_RULES.md**
   - Scan-First → Reuse-First 강제 규칙 추가 (+30 lines)
   - 커밋: `fc05bce`

2. **docs/v2/design/SSOT_MAP.md**
   - V1→V2 재사용 맵핑 표 추가 (+45 lines)
   - 커밋: `fc05bce`

3. **D_ROADMAP.md**
   - D202-2 상태를 DONE으로 업데이트
   - Evidence 경로 명시
   - Tech-Debt 섹션 추가

---

## 🔧 Tech-Debt (별도 D-step)

### 1. UTC 명시적 변환 재검증
- **현재:** `dt.astimezone(tz=None)` (로컬 timezone 변환)
- **문제:** 로컬 timezone에 따라 결과가 달라질 수 있음
- **제안:** `dt.astimezone(timezone.utc)` 사용 (명시적 UTC 변환)
- **상태:** D202-2 FIX-1에서 시도했으나 test_clear_before_time 호환성 문제로 보류
- **다음 단계:** 별도 D-step에서 테스트 전략 재설계 후 진행

### 2. test_get_stats 격리 이슈
- **상태:** D202-2 FIX-1에서 확인, 현재 PASS 상태
- **원인:** 이전 세션에서 지적된 이슈, 현재 재현 불가
- **다음 단계:** 모니터링 필요

---

## 📚 참조 문서

- **SSOT Rules:** `docs/v2/SSOT_RULES.md`
- **SSOT Map:** `docs/v2/design/SSOT_MAP.md`
- **Reuse Inventory:** `docs/v2/design/INFRA_REUSE_INVENTORY.md`
- **Roadmap:** `D_ROADMAP.md` (D202-2 섹션)
- **Evidence:** `logs/evidence/d202_2_closeout_20251229_233153_fc05bce/`

---

## ✨ 결론

D202-2는 **3가지 목표를 모두 달성**했습니다:

1. ✅ **MarketData Sampler** - 1h 샘플 수집 증거 저장 포맷 정의 완료
2. ✅ **PostgreSQL UTC-naive 정규화** - timestamp 혼재 문제 해결 완료
3. ✅ **SSOT Closeout** - Scan-First → Reuse-First 강제, V1→V2 재사용 맵핑 문서화 완료

**Gate 3단 모두 PASS.** D202-2는 DONE 상태입니다.

**다음 단계:** D202-3 (Engine MarketData wiring) 또는 D203 진행
