# D90-2: Zone Profile Config & Short Validation - Design Document

**작성일:** 2025-12-10  
**목적:** Zone Profile 개념 도입으로 zone_random 모드의 가중치 설정을 구조화하고, 20m A/B 검증으로 효과성 재확인

---

## 0. 배경 요약

### D88~D90-1 흐름 (1페이지 요약)

**D88-0/1/2: Entry BPS Diversification**
- 목표: Zone별 트레이드 분산 유도
- random 모드 도입 (5.0~25.0 bps 균일 분포)
- 문제: Zone 분포가 Entry BPS 범위에 의해 결정됨
- D88-2 결과: ΔP(Z2) = 2.2%p (목표 ≥3%p 미달)

**D89-0: Zone Preference 시도 및 실패**
- Zone Preference 가중치를 1.05 → 3.00으로 증가
- 예상: Advisory Z2 45~55%, ΔP(Z2) 20~25%p
- 실제: Advisory Z2 27.8%, Strict Z2 25.6% (D88-2와 동일, 0% 변화)
- **근본 원인:** Entry BPS가 Zone을 먼저 결정 → Zone Preference 무효화

**D90-0: zone_random 모드 도입**
- 핵심 아이디어: Entry BPS 생성 단계에서 Zone 가중치 직접 반영
- 2단계 샘플링:
  1. Zone 선택 (가중치 기반 확률 분포)
  2. 선택된 Zone의 boundary 내에서 균등 샘플링
- Advisory: zone_weights = [0.5, 3.0, 1.5, 0.5] (Z2-heavy)
- Strict: zone_weights = [1.0, 1.0, 1.0, 1.0] (균등)
- 30m A/B 결과: ΔP(Z2) = 22.8%p (목표 ≥5%p의 4.6배 달성)

**D90-1: 3h LONGRUN Validation**
- 샘플 사이즈 6배 증가 (180 → 1,079 trades)
- 3h A/B 결과: ΔP(Z2) = 27.2%p (목표 ≥15%p의 1.8배 달성)
- Advisory Z2: 51.5% (예상 54.5%, 차이 -3.0%p)
- Strict Z2: 24.3% (예상 25%, 차이 -0.7%p)
- **결론:** Zone Exposure 조정 레이어 구조적 확보, 장기 안정성 입증

### D90-2 필요성

**현재 문제 (AS-IS):**
1. **하드코딩:** zone_weights가 코드에 직접 입력됨
2. **프로파일 부재:** "실험용" vs "본선용" 구분 없음
3. **재사용성 부족:** 다른 러너/TopN에서 동일 설정 재사용 어려움
4. **설정 변경 불편:** 가중치 변경 시 코드 수정 필요

**TO-BE 목표:**
1. **Zone Profile 추상화:** 명명된 프로파일로 zone_weights 관리
2. **SSOT (Single Source of Truth):** 프로파일 정의를 한 곳에서 관리
3. **CLI/설정 연동:** 프로파일 이름으로 선택 가능
4. **확장성:** 향후 TopN/Universe/YAML 외부화 대비

---

## 1. 요구사항

### 1.1 Functional Requirements

**FR1: ZoneProfile 추상화**
- 프로파일 이름, 설명, zone_weights를 하나의 단위로 정의
- 예: "strict_uniform", "advisory_z2_focus", "balanced"

**FR2: 기본 프로파일 정의**
- **strict_uniform:** 균등 분포 [1.0, 1.0, 1.0, 1.0]
  - 용도: Strict 모드 기본값, 베이스라인
- **advisory_z2_focus:** Z2-heavy [0.5, 3.0, 1.5, 0.5]
  - 용도: Advisory 모드 기본값, D90-0/1에서 사용한 설정 재현

**FR3: CLI 연동**
- `--entry-bps-zone-profile <profile_name>` 옵션 추가
- 기본값 로직:
  - Strict 실행: 자동으로 `strict_uniform`
  - Advisory 실행: 자동으로 `advisory_z2_focus`
  - 명시적 지정 시 해당 프로파일 사용

**FR4: 입력 검증**
- 잘못된 profile_name → 명확한 예외 + 사용 가능한 프로파일 목록 출력
- zone_weights 길이/양수 검증 (기존 EntryBPSProfile 검증 유지)

### 1.2 Non-Functional Requirements

**NFR1: DO-NOT-TOUCH**
- Calibration JSON 구조 변경 금지
- FillModel 코어 로직 변경 금지
- 기존 D90-0/1 결과 재현 가능해야 함

**NFR2: Backward Compatibility**
- 기존 테스트 전부 PASS (특히 D90-0 unit test)
- D90-1 설정을 새 구조로 재현 가능

**NFR3: 확장성**
- 향후 TopN/Universe에서 재사용 가능한 구조
- YAML 외부화 시 쉽게 마이그레이션 가능

---

## 2. 설계 안 비교

### 2.1 A안: EntryBPSProfile 내부 정의

**구조:**
```python
# arbitrage/domain/entry_bps_profile.py

@dataclass(frozen=True)
class ZoneProfile:
    name: str
    description: str
    zone_weights: Tuple[float, float, float, float]

ZONE_PROFILES: Dict[str, ZoneProfile] = {
    "strict_uniform": ZoneProfile(
        name="strict_uniform",
        description="Uniform zone distribution for strict mode (Z1~Z4 ≈ 25%)",
        zone_weights=(1.0, 1.0, 1.0, 1.0),
    ),
    "advisory_z2_focus": ZoneProfile(
        name="advisory_z2_focus",
        description="Z2-focused profile matching D90-1 calibration",
        zone_weights=(0.5, 3.0, 1.5, 0.5),
    ),
}

class EntryBPSProfile:
    def __init__(
        self,
        mode: Literal["fixed", "cycle", "random", "zone_random"] = "fixed",
        zone_profile_name: Optional[str] = None,
        ...
    ):
        if self.mode == "zone_random":
            if zone_profile_name:
                profile = ZONE_PROFILES.get(zone_profile_name)
                if not profile:
                    raise ValueError(
                        f"Unknown zone_profile_name: {zone_profile_name}. "
                        f"Available: {list(ZONE_PROFILES.keys())}"
                    )
                self.zone_weights = list(profile.zone_weights)
            else:
                # 기본값: 균등 가중치
                self.zone_weights = [1.0, 1.0, 1.0, 1.0]
```

**장점:**
- 단일 파일에서 모든 것 관리 (간단)
- Import 경로 변경 없음
- 기존 코드와 자연스럽게 통합

**단점:**
- entry_bps_profile.py가 비대해질 수 있음
- 프로파일 정의와 로직이 같은 파일에 혼재

### 2.2 B안: 별도 모듈 분리

**구조:**
```python
# arbitrage/domain/zone_profiles.py (신규)

@dataclass(frozen=True)
class ZoneProfile:
    name: str
    description: str
    zone_weights: Tuple[float, float, float, float]

ZONE_PROFILES: Dict[str, ZoneProfile] = {
    "strict_uniform": ZoneProfile(...),
    "advisory_z2_focus": ZoneProfile(...),
}

def get_zone_profile(name: str) -> ZoneProfile:
    """프로파일 조회 + 검증"""
    profile = ZONE_PROFILES.get(name)
    if not profile:
        raise ValueError(
            f"Unknown zone profile: {name}. "
            f"Available: {list(ZONE_PROFILES.keys())}"
        )
    return profile

# arbitrage/domain/entry_bps_profile.py

from arbitrage.domain.zone_profiles import get_zone_profile

class EntryBPSProfile:
    def __init__(
        self,
        mode: Literal["fixed", "cycle", "random", "zone_random"] = "fixed",
        zone_profile_name: Optional[str] = None,
        ...
    ):
        if self.mode == "zone_random" and zone_profile_name:
            profile = get_zone_profile(zone_profile_name)
            self.zone_weights = list(profile.zone_weights)
```

**장점:**
- 관심사 분리 (프로파일 정의 vs 로직)
- 향후 YAML 외부화 시 zone_profiles.py만 수정
- TopN/Universe에서 import하기 쉬움

**단점:**
- 파일 1개 추가
- Import 경로 추가

### 2.3 최종 선택: **A안 (EntryBPSProfile 내부 정의)**

**선택 이유:**
1. **단순성:** D90-2는 "구조화" 단계이지 "대규모 확장" 단계가 아님
2. **최소 변경:** 기존 entry_bps_profile.py만 수정, 새 파일 생성 불필요
3. **점진적 진화:** 향후 D90-4 YAML 외부화 시 zone_profiles.py로 분리 가능
4. **테스트 용이성:** 단일 파일에서 프로파일 정의 + 로직 테스트 가능

**구현 방침:**
- `ZoneProfile` dataclass 추가
- `ZONE_PROFILES` dict 상수 정의
- `EntryBPSProfile.__init__`에 `zone_profile_name` 파라미터 추가
- 잘못된 profile_name → 명확한 예외 + 사용 가능한 목록 출력

---

## 3. 상세 설계

### 3.1 ZoneProfile 구조

```python
from dataclasses import dataclass
from typing import Tuple

@dataclass(frozen=True)
class ZoneProfile:
    """
    Zone 가중치 프로파일.
    
    zone_random 모드에서 사용할 Zone 가중치를 명명된 프로파일로 정의.
    
    Attributes:
        name: 프로파일 이름 (예: "strict_uniform", "advisory_z2_focus")
        description: 프로파일 설명
        zone_weights: Zone 가중치 (Z1, Z2, Z3, Z4 순서)
    
    Examples:
        >>> strict = ZoneProfile(
        ...     name="strict_uniform",
        ...     description="Uniform zone distribution",
        ...     zone_weights=(1.0, 1.0, 1.0, 1.0),
        ... )
        >>> strict.zone_weights
        (1.0, 1.0, 1.0, 1.0)
    """
    name: str
    description: str
    zone_weights: Tuple[float, float, float, float]
```

### 3.2 기본 프로파일 정의

```python
ZONE_PROFILES: Dict[str, ZoneProfile] = {
    "strict_uniform": ZoneProfile(
        name="strict_uniform",
        description="Uniform zone distribution for strict mode (Z1~Z4 ≈ 25%)",
        zone_weights=(1.0, 1.0, 1.0, 1.0),
    ),
    "advisory_z2_focus": ZoneProfile(
        name="advisory_z2_focus",
        description="Z2-focused profile matching D90-0/1 calibration (Z2 ≈ 50%+)",
        zone_weights=(0.5, 3.0, 1.5, 0.5),
    ),
    # 향후 추가 가능:
    # "balanced": ZoneProfile(
    #     name="balanced",
    #     description="Balanced distribution with slight Z2 preference",
    #     zone_weights=(1.0, 1.5, 1.2, 1.0),
    # ),
}
```

### 3.3 EntryBPSProfile 수정

**변경 사항:**
1. `zone_profile_name: Optional[str]` 파라미터 추가
2. `zone_random` 모드일 때 profile_name → zone_weights 조회
3. 잘못된 profile_name → 명확한 예외

**코드:**
```python
class EntryBPSProfile:
    def __init__(
        self,
        mode: Literal["fixed", "cycle", "random", "zone_random"] = "fixed",
        min_bps: float = 10.0,
        max_bps: float = 10.0,
        seed: int = 42,
        zone_boundaries: Optional[List[tuple]] = None,
        zone_weights: Optional[Sequence[float]] = None,  # 기존 파라미터 유지 (backward compat)
        zone_profile_name: Optional[str] = None,  # 신규 파라미터
    ):
        self.mode = mode
        self.min_bps = min_bps
        self.max_bps = max_bps
        self.seed = seed
        
        # Zone 경계값 (기본값: D86 Calibration 기준)
        if zone_boundaries is None:
            self.zone_boundaries = [
                (5.0, 7.0),    # Z1
                (7.0, 12.0),   # Z2
                (12.0, 20.0),  # Z3
                (20.0, 30.0),  # Z4
            ]
        else:
            self.zone_boundaries = zone_boundaries
        
        # Zone 가중치 결정 (우선순위: zone_profile_name > zone_weights > 기본값)
        if self.mode == "zone_random":
            if zone_profile_name:
                # 프로파일 이름으로 조회
                profile = ZONE_PROFILES.get(zone_profile_name)
                if not profile:
                    available = list(ZONE_PROFILES.keys())
                    raise ValueError(
                        f"Unknown zone_profile_name: '{zone_profile_name}'. "
                        f"Available profiles: {available}"
                    )
                self.zone_weights = list(profile.zone_weights)
                self.zone_profile_name = zone_profile_name
            elif zone_weights is not None:
                # 직접 가중치 지정 (backward compatibility)
                self.zone_weights = list(zone_weights)
                self.zone_profile_name = None
            else:
                # 기본값: 균등 가중치
                self.zone_weights = [1.0] * len(self.zone_boundaries)
                self.zone_profile_name = None
        else:
            # zone_random 모드가 아니면 무시
            self.zone_weights = [1.0] * len(self.zone_boundaries)
            self.zone_profile_name = None
        
        # ... (기존 코드 유지)
```

### 3.4 Runner 스크립트 수정

**scripts/run_d84_2_calibrated_fill_paper.py 변경:**

```python
parser.add_argument(
    "--entry-bps-zone-profile",
    type=str,
    default=None,
    help="Zone profile name for zone_random mode (e.g., 'strict_uniform', 'advisory_z2_focus')",
)

# ... (파싱 후)

# Zone profile 기본값 로직
if args.entry_bps_mode == "zone_random":
    if args.entry_bps_zone_profile is None:
        # fillmodel_mode에 따라 기본값 선택
        if args.fillmodel_mode == "strict":
            zone_profile_name = "strict_uniform"
            logger.info("[D90-2] Zone profile auto-selected: strict_uniform (Strict mode default)")
        elif args.fillmodel_mode == "advisory":
            zone_profile_name = "advisory_z2_focus"
            logger.info("[D90-2] Zone profile auto-selected: advisory_z2_focus (Advisory mode default)")
        else:
            zone_profile_name = "strict_uniform"
            logger.info("[D90-2] Zone profile auto-selected: strict_uniform (fallback)")
    else:
        zone_profile_name = args.entry_bps_zone_profile
        logger.info(f"[D90-2] Zone profile specified: {zone_profile_name}")
    
    # EntryBPSProfile 생성
    entry_bps_profile = EntryBPSProfile(
        mode=args.entry_bps_mode,
        min_bps=args.entry_bps_min,
        max_bps=args.entry_bps_max,
        seed=args.entry_bps_seed,
        zone_profile_name=zone_profile_name,
    )
else:
    # zone_random 모드가 아니면 기존 로직
    entry_bps_profile = EntryBPSProfile(
        mode=args.entry_bps_mode,
        min_bps=args.entry_bps_min,
        max_bps=args.entry_bps_max,
        seed=args.entry_bps_seed,
    )
```

---

## 4. Acceptance Criteria (D90-2)

### AC1: Unit Test 전부 PASS
- 기존 D90-0 unit test (10/10 PASS) 유지
- 신규 D90-2 unit test 추가 (프로파일 조회, 검증, 분포 확인)

### AC2: 20m PAPER A/B 검증
- Strict 20m (strict_uniform) vs Advisory 20m (advisory_z2_focus)
- **ΔP(Z2) ≥ 15%p** (D90-1 기준 유지)

### AC3: SSOT 구조 정리
- 프로파일 정의가 `ZONE_PROFILES` 한 곳에서 관리됨
- 코드 내 하드코딩된 zone_weights 제거

### AC4: D90-1 재현 가능
- D90-1에서 사용한 설정을 `advisory_z2_focus` 프로파일로 재현 가능
- 동일한 seed/calibration 사용 시 동일한 결과 기대

---

## 5. 향후 확장 (D90-3+)

### D90-3: TopN Arbitrage 통합
- TopN/Universe에서 `ZONE_PROFILES` import하여 재사용
- 심볼별 독립적인 프로파일 선택 가능

### D90-4: YAML 설정 외부화
- `zone_profiles.py` 분리 (B안으로 전환)
- `config/zone_profiles.yaml` 파일로 프로파일 정의 외부화
- 런타임에 YAML 로드 → `ZONE_PROFILES` dict 생성

### D90-5: Zone Preference 조합
- zone_random (Entry BPS 레벨) + Zone Preference (Route Score 레벨) 동시 적용
- 두 레이어의 시너지 효과 검증

---

## 6. 리스크 및 완화

### R1: 기존 테스트 깨짐
- **완화:** Backward compatibility 유지 (zone_weights 파라미터 유지)
- **검증:** 전체 pytest 실행 후 PASS 확인

### R2: 프로파일 이름 오타
- **완화:** 명확한 예외 메시지 + 사용 가능한 프로파일 목록 출력
- **검증:** Unit test에서 잘못된 이름 테스트

### R3: D90-1 결과 재현 실패
- **완화:** advisory_z2_focus 프로파일 가중치를 D90-1과 정확히 일치시킴
- **검증:** 20m A/B에서 ΔP(Z2) ≥ 15%p 확인

---

## 7. 요약

**D90-2 목표:**
- Zone Profile 개념 도입으로 zone_random 모드 구조화
- 기본 프로파일 2개 정의 (strict_uniform, advisory_z2_focus)
- CLI 연동 + 기본값 로직 구현
- 20m A/B 검증으로 효과성 재확인

**최종 구조:**
- A안 선택: EntryBPSProfile 내부에 ZoneProfile + ZONE_PROFILES 정의
- Backward compatibility 100% 유지
- 향후 D90-4에서 YAML 외부화 시 쉽게 마이그레이션 가능

**Next Steps:**
1. EntryBPSProfile 수정 (ZoneProfile, ZONE_PROFILES 추가)
2. Runner 스크립트 CLI 연동
3. Unit test 작성 (test_d90_2_zone_profile_config.py)
4. 20m A/B PAPER 실행 및 검증
5. 문서/ROADMAP 업데이트 + Git 커밋

---

**작성:** Windsurf AI (D90-2 Design Phase)  
**최종 업데이트:** 2025-12-10
