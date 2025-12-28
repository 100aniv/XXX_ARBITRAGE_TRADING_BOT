# V2 정리 후보 목록 (TOP30 랭킹)

**작성일:** 2025-12-29  
**목적:** 중복/유사 항목 정리 우선순위 결정 (삭제/이동 금지, 후보만 나열)

**원칙:** 이 문서는 "후보 + 근거"만 제공. 실제 삭제/이동은 별도 D 단계에서 수행.

---

## 📊 스캔 요약

**스캔 시각:** 2025-12-29 01:56:11  
**증거 경로:** `logs/evidence/v2_kickoff_scan_20251229_015611/`

**통계:**
- 총 폴더: 3556개
- 총 Python 파일: 612개
- 중복 폴더 패턴: **567개**
- 중복 Python 모듈: **50개**
- 스크립트 런처: **65개**

---

## 🗂️ TOP30 중복 폴더 패턴

### 1. `trades` (533개) - 🔴 HIGH
**위치:** `logs/d77-0/*/trades`  
**근거:** Paper 실행 로그 폴더, 대부분 오래된 실행 기록  
**제안:** 
- KEEP: 최근 7일 (2025-12-22 이후)
- ARCHIVE: 7~30일 (압축)
- DROP: 30일 이상 (삭제 후보)

### 2. `evidence` (8개) - 🟡 MEDIUM
**위치:** `docs/D93~D99/evidence`, `logs/evidence`  
**근거:** 각 D 단계별 증거 폴더 중복  
**제안:**
- KEEP: `logs/evidence` (SSOT)
- MIGRATE: `docs/Dxx/evidence` → `logs/evidence/dxx_*/` (통합)

### 3. `runs` (6개) - 🟡 MEDIUM
**위치:** `logs/d82-*/runs`  
**근거:** D82 시리즈 실행 기록  
**제안:**
- KEEP: 최신 2개 (d82-11, d82-9)
- ARCHIVE: 나머지 (압축)

### 4. `monitoring` (3개) - 🟠 LOW
**위치:** `monitoring`, `arbitrage/monitoring`, `docs/monitoring`  
**근거:** 기능/코드/문서 분리는 정상  
**제안:** KEEP (구조상 필요)

### 5~30. `d77-0-top10-*` (각 3개씩, 총 78개) - 🔴 HIGH
**위치:** `logs/d77-0/*/trades/*`, `logs/d92-2/*`  
**근거:** D77-0 실행 기록 중복 (동일 run_id가 3곳에 존재)  
**제안:**
- KEEP: `logs/d77-0/*` (원본)
- DROP: `logs/d92-2/*` (복사본)
- DROP: `*/trades/*` 하위 중복 (자동 생성 오류)

---

## 🐍 TOP30 중복 Python 모듈

### 1. `config.py` (16개) - 🔴 HIGH
**위치:**
- `arbitrage/config/base.py`
- `arbitrage/cross_exchange/config.py`
- `config/base.py`
- `config/environments/development.py`
- ... (12개 추가)

**근거:** 설정 로직 난립  
**제안:**
- SSOT: `config/v2/config.yml` + `arbitrage/v2/core/config.py`
- DEPRECATE: V1 config.py들 (레거시 마커)

### 2. `settings.py` (8개) - 🟠 MEDIUM
**위치:** `arbitrage/*/settings.py` (8곳)  
**근거:** 모듈별 설정 분산  
**제안:**
- MIGRATE: `config/v2/config.yml`로 통합
- DEPRECATE: V1 settings.py

### 3. `__init__.py` (197개) - 🟢 OK
**근거:** Python 패키지 구조상 필수  
**제안:** KEEP (정상)

### 4. `constants.py` (6개) - 🟡 MEDIUM
**위치:** `arbitrage/*/constants.py`  
**근거:** 상수 정의 분산  
**제안:**
- CONSOLIDATE: `arbitrage/v2/core/constants.py`로 통합
- DEPRECATE: V1 상수 파일

### 5. `logger.py` / `logging.py` (5개) - 🟡 MEDIUM
**위치:** `arbitrage/monitoring/logger.py` 등  
**근거:** 로깅 로직 중복  
**제안:**
- SSOT: `arbitrage/v2/core/logging.py`
- DEPRECATE: V1 로거

### 6~30. `adapter.py`, `executor.py`, `monitor.py` 등 (각 2~4개)
**근거:** V1/V2 공존으로 인한 자연스러운 중복  
**제안:** KEEP (V1은 레거시, V2는 신규)

---

## 🚀 TOP30 스크립트 런처

### 1. `run_d77_0_*.py` (12개) - 🔴 HIGH
**위치:** `scripts/run_d77_0_*.py`  
**예시:**
- `run_d77_0_topn_arbitrage_paper.py`
- `run_d77_0_rm_ext_full_auto.py`
- `run_d77_0_top20_paper.py`
- ... (9개 추가)

**근거:** D77-0 실험 스크립트 난립  
**제안:**
- KEEP: `run_d77_0_topn_arbitrage_paper.py` (통합 버전)
- DEPRECATE: 나머지 (레거시 마커)

### 2. `run_d82_*.py` (8개) - 🟠 MEDIUM
**위치:** `scripts/run_d82_*.py`  
**근거:** D82 시리즈 실험 스크립트  
**제안:**
- KEEP: 최신 2개 (d82-11, d82-9)
- DEPRECATE: 나머지

### 3. `run_d9*_*.py` (15개) - 🟡 MEDIUM
**위치:** `scripts/run_d9*_*.py` (D90~D99)  
**근거:** D9x 시리즈 실험 스크립트  
**제안:**
- KEEP: Gate 검증용 (d98_preflight, d99_*)
- DEPRECATE: 나머지

### 4. `run_d64_*.py`, `run_d61_*.py` 등 (각 2~3개) - 🟢 OK
**근거:** 개별 D 단계 검증용  
**제안:** KEEP (증거용)

### 5~30. 기타 `run_*.py` (각 1~2개)
**제안:**
- PATTERN: `scripts/v2/run_*.py`로 V2 스크립트 분리
- DEPRECATE: V1 스크립트는 `scripts/v1/`로 이동 (미래 작업)

---

## 📋 정리 우선순위 (추천)

### Phase 1: 즉시 정리 가능 (위험도 낮음)
1. **오래된 Paper 로그** (30일+ `trades` 폴더) → 삭제
2. **중복 evidence** (`docs/Dxx/evidence`) → `logs/evidence`로 통합
3. **중복 run_id** (`logs/d92-2/*`) → 삭제

**예상 절감:** ~500개 폴더, ~5GB 디스크

### Phase 2: 계획 후 정리 (D201+)
1. **중복 config.py** → `config/v2/config.yml` 통합
2. **중복 설정 파일** → SSOT 확정 후 DEPRECATE
3. **오래된 스크립트** → `scripts/v1/` 이동 + 레거시 마커

**예상 절감:** ~30개 모듈, ~20개 스크립트

### Phase 3: 장기 정리 (D206+)
1. **V1 코드 전체** → `arbitrage/v1/`로 격리
2. **V1 문서** → `docs/v1/` 통합
3. **V1 스크립트** → `scripts/v1/` 통합

**예상 절감:** 구조 정리, SSOT 준수

---

## 🚫 절대 삭제 금지 목록

### 1. Gate 검증 파일
- `tests/test_d98_preflight.py`
- `tests/test_d48_upbit_order_payload.py`
- Core Regression 관련 테스트

### 2. SSOT 문서
- `D_ROADMAP.md`
- `docs/v2/SSOT_RULES.md`
- `docs/v2/V2_ARCHITECTURE.md`
- `config/v2/config.yml`

### 3. 최근 실행 증거 (7일 이내)
- `logs/evidence/v2_*`
- `logs/evidence/d106_*`
- `logs/d77-0/*` (최근 2주)

### 4. 운영 중 인프라
- `infra/docker-compose.yml`
- `monitoring/prometheus/prometheus.yml`
- `.env.v2.example`

---

## 📝 다음 단계

이 문서는 **후보 목록**입니다. 실제 정리는 다음 순서로 진행:

1. **D200-1 완료 후** Phase 1 정리 검토
2. **D201 시작 전** Phase 2 계획 수립
3. **D206 완료 후** Phase 3 장기 정리

**원칙:** 한 번에 대량 삭제 금지. 단계별 검증 후 점진적 정리.
