# D90-4: Zone Profile YAML Externalization - Design

**작성일:** 2025-12-10  
**목표:** Zone Profile 정의를 코드에서 YAML 설정으로 외부화하여 코드 수정 없이 프로파일 관리 가능하도록 함

---

## 1. 배경

D90-0~3에서 `zone_random` + `ZoneProfile` + PnL 최적화를 완료했으나, 프로파일 정의가 `entry_bps_profile.py`에 하드코딩되어 있어:
- 프로파일 추가/수정 시 코드 수정 필요
- 실험적 프로파일 관리 어려움
- TopN Arbitrage 통합 시 심볼별 프로파일 설정 불가능

D90-4에서는 프로파일 정의를 `config/arbitrage/zone_profiles.yaml`로 외부화하여 이 문제를 해결한다.

---

## 2. YAML 스키마

### 파일 경로
`config/arbitrage/zone_profiles.yaml`

### 스키마 구조
```yaml
profiles:
  profile_name:
    description: "프로파일 설명"
    weights: [z1_weight, z2_weight, z3_weight, z4_weight]
    status: production|experimental|deprecated

metadata:
  schema_version: "1.0.0"
  compatible_with: [...]
  validation_status: {...}
```

### 프로파일 정의 (5개)
1. **strict_uniform** (production): 균등 분포, Strict 모드 기본값
2. **advisory_z2_focus** (production): Z2 집중, Advisory 모드 기본값
3. **advisory_z23_focus** (experimental): Z2+Z3 집중, D90-3 Runner-up
4. **advisory_z2_balanced** (deprecated): Balanced, D90-3 성능 미달
5. **advisory_z2_conservative** (deprecated): Conservative, D90-3 성능 미달

---

## 3. 로더 구현

### Zone Profile 로더
**파일:** `arbitrage/config/zone_profiles_loader.py`

**주요 함수:**
- `load_zone_profiles_from_yaml()`: YAML 파일에서 프로파일 로드
- `load_zone_profiles_with_fallback()`: YAML 로드 실패 시 기본 프로파일 2개 제공
- `validate_profile_data()`: weights 길이/타입/음수 검증
- `get_profile()`: 프로파일 이름으로 ZoneProfile 인스턴스 반환

**Fallback 전략:**
- YAML 파일 없음/로드 실패 시: `strict_uniform`, `advisory_z2_focus` 2개 내장
- 경고 로그 출력 (운영 환경에서는 YAML 필수)

---

## 4. entry_bps_profile.py 수정

### 변경 사항
1. **하드코딩 dict 제거**: `ZONE_PROFILES = {...}` 삭제
2. **Lazy loading 도입**: `load_zone_profiles()` 함수로 YAML에서 로드 (캐싱)
3. **하위 호환성 유지**: `_ZoneProfilesDict` 클래스로 dict-like 접근 지원
   - `ZONE_PROFILES['strict_uniform']` 여전히 동작
   - `'name' in ZONE_PROFILES`, `.keys()`, `.values()`, `.items()`, `.get()` 지원

### 새 함수
- `load_zone_profiles(force_reload=False)`: YAML 로드 (캐싱)
- `get_zone_profile(name)`: 프로파일 반환 (권장 방식)

---

## 5. 테스트 전략

### 신규 테스트 (28개)
**파일:** `tests/test_d90_4_zone_profile_yaml.py`

**테스트 범위:**
1. **YAML 로드**: 파일 존재, 프로파일 로드, weights 정확도
2. **검증**: weights 길이/타입/음수/합계 검증
3. **Fallback**: YAML 없음 시 기본 프로파일 제공
4. **하위 호환성**: `ZONE_PROFILES['name']`, `in`, `.keys()` 등 동작 확인
5. **D90-0~3 호환성**: zone_random 모드, 기존 프로파일 가중치 일치

### 기존 테스트 (41개)
- D90-0: 10/10 PASS
- D90-2: 15/15 PASS
- D90-3: 16/16 PASS

---

## 6. 리스크 & 완화

| 리스크 | 완화 전략 |
|--------|-----------|
| YAML 파일 없음/손상 | Fallback으로 최소 2개 프로파일 내장 |
| YAML 파싱 오류 | 명확한 에러 메시지, validate_profile_data() 검증 |
| 하위 호환성 깨짐 | _ZoneProfilesDict로 dict-like 접근 유지 |
| 성능 오버헤드 | 캐싱 (첫 로드 후 메모리 보관) |
| 프로파일 이름 오타 | KeyError with 가능한 프로파일 리스트 제공 |

---

## 7. 실행 계획

1. ✅ YAML 스키마 확정 및 파일 생성
2. ✅ Zone Profile 로더 구현
3. ✅ entry_bps_profile.py 수정 (YAML 기반 로딩)
4. ✅ 테스트 코드 작성 (28개)
5. ✅ Unit Test 전체 실행 (69/69 PASS)
6. ✅ 20m A/B 재검증 (Strict/Advisory)
7. ⏳ D90-4 Validation Report 작성
8. ⏳ D_ROADMAP.md 업데이트
9. ⏳ Git 커밋

---

## 8. Next Steps

- **D90-5** (Optional): Production 6~12h LONGRUN with YAML profiles
- **D91**: Multi-Symbol TopN Arbitrage 통합
- **D92+**: 심볼별 독립적인 Zone Profile 선택

---

**Status:** ✅ DESIGN COMPLETE  
**Next:** D90_4_VALIDATION_REPORT.md
