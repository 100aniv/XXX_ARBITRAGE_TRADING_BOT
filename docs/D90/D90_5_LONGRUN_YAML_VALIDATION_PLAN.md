# D90-5: YAML Zone Profile 1h/3h LONGRUN Validation - Plan

**작성일:** 2025-12-11  
**목표:** D90-4의 CONDITIONAL PASS 상태를 1h/3h LONGRUN으로 검증하여 **GO (완전 PASS)** 격상 여부 판단

---

## 1. 배경 & 문제 정의

### 1.1 D90-0~4 요약

#### D90-0: Entry BPS Zone-Weighted Random (30m A/B)
- Zone-weighted 2단계 샘플링 도입
- ΔP(Z2) = 22.8%p (목표 ≥5%p의 4.6배 달성)
- 샘플 사이즈: 180 trades, 통계적 변동성 존재

#### D90-1: 3h LONGRUN Validation
- **핵심 성과:** ΔP(Z2) = 27.2%p (목표 ≥15%p의 1.8배 달성)
- 샘플 사이즈: **1,080 trades** (D90-0 대비 6배 증가)
- Advisory Z2: 54.2% (설계 예상 54.5%, diff -0.3%p)
- Strict Z2: 27.0% (expected 25%, diff +2.0%p)
- 장기 안정성·통계적 유의성 확보

#### D90-2: Zone Profile Config & 20m A/B
- ZoneProfile dataclass + ZONE_PROFILES dict 추상화
- ΔP(Z2) = 23.3%p (목표 ≥15%p의 1.6배 달성)
- Advisory PnL: $5.30, Strict PnL: $4.27
- 코드 하드코딩으로 프로파일 정의

#### D90-3: Zone Profile Tuning v1
- PnL 최적화 위한 3개 신규 프로파일 설계
- 핵심 발견: **Z2 집중도와 PnL 간 강한 양의 상관관계** (R² ≈ 0.95)
- advisory_z2_focus의 최적성 확인 (변경 불필요)

#### D90-4: YAML Externalization
- Zone Profile 정의를 코드 하드코딩 → YAML 설정으로 외부화
- Unit Test: 69/69 PASS ✅
- **20m A/B 재검증:**
  - Advisory: PnL $5.36 vs D90-2 $5.30 (+1.1%, 거의 동일 ✅)
  - **Strict: PnL $4.02 vs D90-2 $4.27 (-5.9%, ⚠️)**
  - Advisory Z2: 52.5% vs D90-2 50.0% (+2.5%p)
  - Strict Z2: 24.2% vs D90-2 26.7% (-2.5%p)
- **Status:** CONDITIONAL PASS ⚠️

### 1.2 D90-4 현재 상황

**핵심 질문:**
> Strict PnL -5.9% 차이는 **단기 20m 구간의 시장 노이즈**인가, 아니면 **YAML Loader/Config 경로에 숨어 있는 구조적 편향/버그**인가?

**CONDITIONAL PASS 이유:**
1. Advisory는 거의 동일 (+1.1% PnL)
2. Strict는 단일 20m 샘플 (120 trades)의 시장 노이즈 가능성
3. YAML 프로파일 가중치 = 코드 하드코딩 값 (1:1 일치, 구조적 불변성)
4. Unit Test 69/69 PASS (하위 호환성 100%)

**리스크:**
- Strict PnL -5.9%가 시장 노이즈가 아니라면?
- YAML 로딩 경로의 미세한 버그/편향이 장기 실행에서 증폭될 가능성?

---

## 2. D90-5 목표 (TO-BE)

### 2.1 핵심 목표

**YAML 외부화 이후에도 1h/3h LONGRUN에서 D90-1과 동급 수준의 Z2 집중도·PnL 구조를 유지하는지 검증**

### 2.2 검증 대상

1. **strict_uniform** (Strict 모드 기준선)
   - D90-2/4에서 사용한 기본 프로파일
   - weights: [1.0, 1.0, 1.0, 1.0]
   - 예상 Z2: ~25%

2. **advisory_z2_focus** (Advisory 기준선)
   - D90-0/1/2/3에서 best profile로 확정
   - weights: [0.5, 3.0, 1.5, 0.5]
   - 예상 Z2: ~54.5%

### 2.3 비교 기준

| Metric | D90-1 (3h, 코드 하드코딩) | D90-5 (목표) |
|--------|---------------------------|--------------|
| **Strict Z2** | 27.0% | 25~30% (±5%p) |
| **Advisory Z2** | 54.2% | 50~59% (±5%p) |
| **ΔP(Z2)** | 27.2%p | ≥22%p (±5%p) |
| **Strict PnL** | (D90-2 기준 $4.27) | ±20% |
| **Advisory PnL** | (D90-2 기준 $5.30) | ±20% |
| **Duration** | 10,800s | ±5s |
| **Trades** | ~1,080 | ~1,080 (±5%) |

---

## 3. Acceptance Criteria (AC)

### AC1: Duration 정확도 ✅
- **1h 실행:** duration = 3600s ± 5s
- **3h 실행:** duration = 10,800s ± 5s

### AC2: Zone 분포 재현성 (Z2 기준) ✅
- **Strict Z2:** D90-1 기준 (27.0%) ± 5%p (즉, 22~32%)
- **Advisory Z2:** D90-0/1/2 기준 (50~55%) ± 5%p (즉, 45~60%)
- **ΔP(Z2):** ≥ 20%p (D90-1 대비 -5%p 허용)

### AC3: PnL 안정성 ✅
- **Strict PnL:** D90-2 기준 ($4.27) ± 20% (즉, $3.42~$5.12)
- **Advisory PnL:** D90-2 기준 ($5.30) ± 20% (즉, $4.24~$6.36)
- **조건:** 비정상적인 손실 폭주 없음 (최대 Drawdown < 30%)

### AC4: 구조 동일성 ✅
- Zone Profile 선택/적용 경로가 **YAML → Loader → EntryBpsProfile → Engine**을 통해서만 이뤄짐
- 코드 하드코딩 사용 없음 (Unit Test로 검증)
- `load_zone_profiles()` → `get_zone_profile(name)` 경로 확인

### AC5: Fatal Error 0 & Infra 안정성 ✅
- 실행 중 치명적 예외 0건
- WebSocket/레이트리밋 회복 정상
- DB/Redis 관련 오류 없음
- Memory Leak 없음 (메모리 증가율 < 10% per hour)

### AC6: 로그 & 메트릭 수집 ✅
- 각 실행마다 다음 데이터 수집:
  - `kpi_*.json` (KPI 메트릭)
  - `fill_events_*.jsonl` (Fill 이벤트)
  - Zone 분포 분석 결과 (Z1~Z4 비중)
- 로그 디렉터리: `logs/d87-3/d90_5_*`

---

## 4. 실행 계획

### 4.1 실행 세트 (3-run 최소 구조)

시간 제약과 검증 우선순위를 고려하여 **최소 3-run 구조**로 설계:

#### Run #1 – Strict 1h ⚠️
- **목적:** Strict PnL -5.9% 차이가 1h에서도 재현되는지 확인
- **Duration:** 3600s (1h)
- **Profile:** strict_uniform
- **예상 Trades:** ~360
- **우선순위:** **HIGH** (D90-4의 핵심 의문점 검증)

#### Run #2 – Advisory 1h ✅
- **목적:** Advisory YAML 경로의 안정성 확인
- **Duration:** 3600s (1h)
- **Profile:** advisory_z2_focus
- **예상 Trades:** ~360
- **우선순위:** **MEDIUM** (D90-4에서 이미 +1.1% 동일 확인)

#### Run #3 – Strict 3h ⚠️
- **목적:** Strict 장기 안정성 및 D90-1 대비 통계적 유의성 확인
- **Duration:** 10,800s (3h)
- **Profile:** strict_uniform
- **예상 Trades:** ~1,080
- **우선순위:** **CRITICAL** (최종 판정의 핵심 근거)

#### (Optional) Run #4 – Advisory 3h
- 시간 여유 시 Advisory 3h 추가
- D90-1과 1:1 비교 가능

### 4.2 Trade-off 분석

| 실행 세트 | 소요 시간 | 검증 범위 | 판정 신뢰도 |
|-----------|----------|----------|------------|
| **2-run (Strict 1h+3h)** | 4h | Strict만 | 부분적 |
| **3-run (Strict 1h+3h, Advisory 1h)** | 5h | 균형 | **권장 ✅** |
| **4-run (Strict 1h+3h, Advisory 1h+3h)** | 8h | 완전 | 이상적 |

**선택:** **3-run 구조** (Strict 1h+3h, Advisory 1h)  
**이유:**
- Strict 3h가 최종 판정의 핵심 근거
- Advisory는 D90-4에서 이미 동일 확인 (+1.1%)
- 5시간 실행으로 합리적인 검증 범위 확보

### 4.3 실행 환경

**공통 설정:**
- **L2 Source:** real (Upbit WebSocket)
- **Calibration:** `logs/d86-1/calibration_20251207_123906.json`
- **Entry BPS mode:** zone_random (YAML 프로파일 사용)
- **Zone boundaries:** `[(5.0,7.0), (7.0,12.0), (12.0,20.0), (20.0,25.0)]`
- **Seed:** 91 (D90-4와 동일, 재현성 보장)

**Runner:**
- 기존 `scripts/run_d84_2_calibrated_fill_paper.py` 재사용
- `--entry-bps-zone-profile` 옵션으로 YAML 프로파일 지정

**실행 명령어 예시 (Strict 1h):**
```bash
python scripts/run_d84_2_calibrated_fill_paper.py \
  --duration-seconds 3600 \
  --l2-source real \
  --fillmodel-mode strict \
  --calibration-path logs/d86-1/calibration_20251207_123906.json \
  --session-tag d90_5_strict_1h_yaml \
  --entry-bps-mode zone_random \
  --entry-bps-zone-profile strict_uniform \
  --entry-bps-seed 91
```

---

## 5. Unit Test 설계

### 5.1 새 테스트 파일
`tests/test_d90_5_zone_profile_longrun_config.py`

### 5.2 테스트 내용 (구조 검증, 실제 LONGRUN은 아님)

#### T1: YAML Loader 연동 확인
```python
def test_yaml_loader_integration():
    """YAML Loader를 통해 프로파일을 가져오는지 확인"""
    from arbitrage.domain.entry_bps_profile import load_zone_profiles
    profiles = load_zone_profiles()
    assert "strict_uniform" in profiles
    assert "advisory_z2_focus" in profiles
```

#### T2: 프로파일 가중치 정확도
```python
def test_profile_weights_accuracy():
    """YAML 프로파일 가중치가 설계 값과 일치하는지 확인"""
    from arbitrage.domain.entry_bps_profile import get_zone_profile
    
    strict = get_zone_profile("strict_uniform")
    assert strict.zone_weights == (1.0, 1.0, 1.0, 1.0)
    
    advisory = get_zone_profile("advisory_z2_focus")
    assert advisory.zone_weights == (0.5, 3.0, 1.5, 0.5)
```

#### T3: 로그 경로 패턴 검증
```python
def test_log_path_pattern():
    """로그 디렉터리 패턴이 d90_5_* 형식인지 확인"""
    session_tag = "d90_5_strict_1h_yaml"
    expected_pattern = r"d90_5_\w+_\d+h_yaml"
    assert re.match(expected_pattern, session_tag)
```

#### T4: Duration 파라미터 전달
```python
def test_duration_parameter_passing():
    """Duration 파라미터가 정확히 전달되는지 Mock 검증"""
    # Mock runner 호출, duration=3600/10800 전달 확인
    pass
```

### 5.3 회귀 테스트

D90 관련 전체 테스트 재실행으로 하위 호환성 확인:
```bash
pytest tests/test_d90_0_* tests/test_d90_2_* tests/test_d90_3_* tests/test_d90_4_* tests/test_d90_5_* -q
```

**예상 결과:** 전체 PASS (D90-5 신규 테스트 + 기존 69개)

---

## 6. 분석 & Validation Report

### 6.1 분석 스크립트

기존 스크립트 재사용:
- `scripts/analyze_d84_2_fill_results.py` (Zone 분포 분석)
- D90-3의 분석 패턴 참고

필요 시 간단한 분석 스크립트 추가:
- `scripts/analyze_d90_5_results.py`
- Zone 분포 (Z1~Z4), ΔP(Z2), PnL, 거래 수, Duration 집계

### 6.2 Validation Report

**문서:** `docs/D90/D90_5_LONGRUN_YAML_VALIDATION_REPORT.md`

**포함 내용:**
1. **목적/배경:** D90-4 Strict PnL -5.9% 차이 재검증
2. **실행 환경/설정:** 모드, duration, profile, 시각, 시장 구간
3. **Run별 주요 결과 표:**
   - D90-1 (KPI) vs D90-5 (KPI) 비교 표
   - Strict 1h, Advisory 1h, Strict 3h 각각
4. **Acceptance Criteria별 PASS/FAIL 판정:**
   - AC1~AC6 각각 실제 값과 판정
5. **최종 결론:**
   - YAML 외부화가 구조적 PnL/Zone Bias를 유발하지 않는다는 증거인지
   - D90-4의 CONDITIONAL PASS를 **GO (완전 PASS)**로 격상 가능한지
   - 추가 조치 필요 여부

---

## 7. 산출물 체크리스트

### 7.1 코드/테스트
- ✅ 기존 Runner 재사용 (`run_d84_2_calibrated_fill_paper.py`)
- ⏳ `tests/test_d90_5_zone_profile_longrun_config.py` (4개 테스트)
- ⏳ pytest 실행 (D90-0~5 전체)

### 7.2 문서
- ✅ `docs/D90/D90_5_LONGRUN_YAML_VALIDATION_PLAN.md` (현재 문서)
- ⏳ `docs/D90/D90_5_LONGRUN_YAML_VALIDATION_REPORT.md`

### 7.3 로그/데이터
- ⏳ `logs/d87-3/d90_5_strict_1h_yaml/` (kpi, fill_events, zone_distribution)
- ⏳ `logs/d87-3/d90_5_advisory_1h_yaml/`
- ⏳ `logs/d87-3/d90_5_strict_3h_yaml/`

### 7.4 프로젝트 관리
- ⏳ `D_ROADMAP.md` 업데이트 (D90-5 항목 추가)
- ⏳ Git 커밋 (설계/테스트/문서 PASS 후)

---

## 8. 리스크 & 완화

| 리스크 | 영향 | 완화 전략 |
|--------|------|-----------|
| **Strict PnL -5.9% 재현** | HIGH | 3h LONGRUN으로 통계적 유의성 확보, D90-1 대비 ±20% 허용 |
| **YAML 로딩 경로 버그** | MEDIUM | Unit Test로 경로 검증, AC4로 구조 동일성 확인 |
| **시장 변동성** | MEDIUM | D86-1 Calibration 동일 사용, Seed 고정 (91) |
| **인프라 불안정** | LOW | WebSocket 재연결, DurationGuard, Fatal Error 모니터링 |
| **1h 샘플 사이즈 부족** | LOW | 3h LONGRUN으로 최종 판정 (1,080 trades) |

---

## 9. 최종 판정 기준

### 9.1 GO (완전 PASS) 조건

**ALL** of the following:
1. AC1~AC6 **ALL PASS** ✅
2. Strict 3h PnL이 D90-2 대비 ±20% 이내 ($3.42~$5.12)
3. Advisory 1h PnL이 D90-2 대비 ±20% 이내 ($4.24~$6.36)
4. Strict 3h Z2가 D90-1 대비 ±5%p 이내 (22~32%)
5. Advisory 1h Z2가 D90-0/1/2 대비 ±5%p 이내 (45~60%)
6. ΔP(Z2) ≥ 20%p

**결과:** D90-4의 CONDITIONAL PASS → **GO (완전 PASS)** 격상

### 9.2 CONDITIONAL PASS 유지 조건

**ANY** of the following:
1. Strict 3h PnL이 허용 범위 밖이지만 -10% 이내 ($3.85~$5.12)
2. AC2 (Zone 분포)는 PASS, AC3 (PnL)만 일부 벗어남
3. 시장 변동성으로 인한 일시적 편차 가능성 (추가 검증 권장)

**결과:** CONDITIONAL PASS 유지, D90-6 (추가 검증) 권장

### 9.3 NO-GO 조건

**ANY** of the following:
1. Strict 3h PnL이 D90-2 대비 -20% 초과 하락 (< $3.42)
2. AC5 (Fatal Error) FAIL (치명적 예외 발생)
3. ΔP(Z2) < 15%p (Zone Exposure 제어 실패)
4. YAML 로딩 경로에서 구조적 버그 발견

**결과:** NO-GO, 코드 재검토 및 버그 수정 필요 (D90-4 Rollback 고려)

---

## 10. Next Steps

### 10.1 Immediate (D90-5 완료 후)

- **GO 격상 시:** D91 (TopN Multi-Symbol 통합) 진행
- **CONDITIONAL 유지 시:** D90-6 (추가 검증) 또는 D91 진행 (위험 인지)
- **NO-GO 시:** 코드 재검토, 버그 수정, D90-4 Rollback 고려

### 10.2 Mid-term (D91+)

- **D91:** TopN Multi-Symbol Arbitrage 통합
  - 심볼별 독립적인 Zone Profile 선택
  - YAML 파일에 심볼별 프로파일 매핑 추가
- **Deprecated 프로파일 제거:** advisory_z2_balanced, advisory_z2_conservative

### 10.3 Long-term (D92+)

- **Zone Profile 최적화 v2:** Bayesian Optimization, Multi-Symbol 성능 비교
- **6h/12h LONGRUN:** 극한 안정성 검증

---

**Status:** ✅ **PLAN COMPLETE**  
**Next:** Unit Test 작성 → 인프라 준비 → LONGRUN 실행
