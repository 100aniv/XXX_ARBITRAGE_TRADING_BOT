#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D88-0 / D90-0 / D90-2: Entry BPS Profile

PAPER 실행 시 Entry BPS를 다양하게 생성하여 Zone별 트레이드 분산을 유도하는 프로파일.

**목표:**
- Z1~Z4 Zone에 트레이드가 분산되도록 Entry BPS 생성
- 재현 가능성(Reproducibility) 보장 (seed 기반)
- 기존 도메인 로직 변경 없이 PAPER 시나리오 입력만 조정

**Modes:**
1. **fixed**: 고정값 (기존 동작, 하나의 BPS만 사용)
2. **cycle**: Zone별 대표 BPS를 순환 (Z1 → Z2 → Z3 → Z4 → Z1 ...)
3. **random**: [min_bps, max_bps] 범위 내 균일 분포 난수 생성
4. **zone_random** (D90-0/2): Zone 가중치 기반 확률적 샘플링
   - zone_weights에 따라 Zone을 먼저 선택
   - 선택된 Zone의 boundary 내에서 균등 분포 샘플링
   - Advisory/Strict 모드별로 다른 Zone 가중치 적용 가능
   - D90-2: Zone Profile 개념 도입 (명명된 프로파일로 가중치 관리)

Author: arbitrage-lite project
Date: 2025-12-09 (D90-0), 2025-12-10 (D90-2)
"""

import random
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ZoneProfile:
    """
    Zone 가중치 프로파일 (D90-2).
    
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


# D90-2/3: Zone Profile 정의
ZONE_PROFILES: Dict[str, ZoneProfile] = {
    # D90-2: Baseline profiles
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
    
    # D90-3: Tuning candidates
    "advisory_z2_balanced": ZoneProfile(
        name="advisory_z2_balanced",
        description="Balanced Z2/Z3 profile with increased tail coverage (Z2 ≈ 42%, Z3 ≈ 33%)",
        zone_weights=(0.7, 2.5, 2.0, 0.8),
    ),
    "advisory_z23_focus": ZoneProfile(
        name="advisory_z23_focus",
        description="Z2+Z3 focused profile for mid-risk/mid-reward optimization (Z2 ≈ 50%, Z3 ≈ 39%)",
        zone_weights=(0.3, 2.8, 2.2, 0.3),
    ),
    "advisory_z2_conservative": ZoneProfile(
        name="advisory_z2_conservative",
        description="Conservative profile with broader zone distribution (Z2 ≈ 35%, all zones ≥ 17%)",
        zone_weights=(1.0, 2.0, 1.8, 1.0),
    ),
}


class EntryBPSProfile:
    """
    Entry BPS 생성 프로파일.
    
    PAPER 실행 시 Zone별 트레이드 분산을 위해 다양한 Entry BPS를 생성한다.
    
    Args:
        mode: 생성 모드 ("fixed", "cycle", "random", "zone_random")
        min_bps: 최소 BPS (기본값 10.0)
        max_bps: 최대 BPS (기본값 10.0)
        seed: 난수 생성 seed (재현성 보장, 기본값 42)
        zone_boundaries: Zone 경계값 (옵션, 없으면 기본값 사용)
            예: [(5, 7), (7, 12), (12, 20), (20, 30)]
        zone_weights: Zone 가중치 (zone_random 모드 전용, 옵션)
            예: [0.5, 3.0, 1.5, 0.5] → Z2를 3배 더 자주 선택
            None이면 균등 가중치 [1.0, 1.0, 1.0, 1.0] 사용
    
    Attributes:
        mode: 생성 모드
        min_bps: 최소 BPS
        max_bps: 최대 BPS
        seed: 난수 생성 seed
        zone_boundaries: Zone 경계값 리스트 [(min, max), ...]
        zone_weights: Zone 가중치 (zone_random 모드 전용)
        _cycle_index: cycle 모드용 인덱스
        _rng: random.Random 인스턴스 (독립적인 난수 생성기)
        _zone_cumulative_weights: Zone 누적 가중치 (zone_random 모드 전용)
    
    Examples:
        # Fixed 모드 (기존 동작)
        >>> profile = EntryBPSProfile(mode="fixed", min_bps=10.0)
        >>> profile.next()  # 항상 10.0
        10.0
        
        # Cycle 모드 (Zone별 순환)
        >>> profile = EntryBPSProfile(mode="cycle", min_bps=5.0, max_bps=25.0)
        >>> [profile.next() for _ in range(4)]  # Z1, Z2, Z3, Z4 대표값
        [6.0, 10.0, 15.0, 22.0]
        
        # Random 모드 (균일 분포)
        >>> profile = EntryBPSProfile(mode="random", min_bps=5.0, max_bps=25.0, seed=42)
        >>> profile.next()  # 5.0~25.0 범위 난수
        18.48...
        
        # Zone Random 모드 (D90-0, Zone 가중치 기반)
        >>> profile = EntryBPSProfile(
        ...     mode="zone_random",
        ...     zone_weights=[0.5, 3.0, 1.5, 0.5],  # Z2를 3배 더 자주 선택
        ...     seed=90
        ... )
        >>> profile.next()  # Z2 zone (7.0~12.0) 내에서 샘플링될 확률 높음
        9.12...
    """
    
    def __init__(
        self,
        mode: Literal["fixed", "cycle", "random", "zone_random"] = "fixed",
        min_bps: float = 10.0,
        max_bps: float = 10.0,
        seed: int = 42,
        zone_boundaries: Optional[List[tuple]] = None,
        zone_weights: Optional[Sequence[float]] = None,
        zone_profile_name: Optional[str] = None,  # D90-2: 신규 파라미터
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
        
        # D90-2: Zone 가중치 결정 (우선순위: zone_profile_name > zone_weights > 기본값)
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
        
        # Cycle 모드용 인덱스
        self._cycle_index = 0
        
        # Random 모드용 독립 난수 생성기
        self._rng = random.Random(seed)
        
        # Zone Random 모드용 누적 가중치 (확률 분포 샘플링)
        self._zone_cumulative_weights: List[float] = []
        if self.mode == "zone_random":
            self._compute_cumulative_weights()
        
        # 입력 검증
        self._validate()
    
    def _validate(self):
        """입력 파라미터 검증."""
        if self.mode not in ["fixed", "cycle", "random", "zone_random"]:
            raise ValueError(
                f"Invalid mode: {self.mode}. "
                f"Must be 'fixed', 'cycle', 'random', or 'zone_random'."
            )
        
        if self.min_bps < 0 or self.max_bps < 0:
            raise ValueError(
                f"min_bps and max_bps must be non-negative: "
                f"min={self.min_bps}, max={self.max_bps}"
            )
        
        if self.min_bps > self.max_bps:
            raise ValueError(
                f"min_bps must be <= max_bps: "
                f"min={self.min_bps}, max={self.max_bps}"
            )
        
        if not self.zone_boundaries:
            raise ValueError("zone_boundaries must not be empty")
        
        for i, (zmin, zmax) in enumerate(self.zone_boundaries):
            if zmin >= zmax:
                raise ValueError(
                    f"Zone {i} has invalid boundaries: min={zmin}, max={zmax}"
                )
        
        # zone_random 모드 전용 검증
        if self.mode == "zone_random":
            if len(self.zone_weights) != len(self.zone_boundaries):
                raise ValueError(
                    f"zone_weights length ({len(self.zone_weights)}) "
                    f"must match zone_boundaries length ({len(self.zone_boundaries)})"
                )
            
            for i, weight in enumerate(self.zone_weights):
                if weight <= 0:
                    raise ValueError(
                        f"zone_weights[{i}] must be positive, got {weight}"
                    )
    
    def _compute_cumulative_weights(self):
        """
        Zone 가중치를 누적합으로 변환 (확률 분포 샘플링용).
        
        예: zone_weights = [0.5, 3.0, 1.5, 0.5]
            → cumulative = [0.5, 3.5, 5.0, 5.5]
            → 총합 = 5.5
        """
        self._zone_cumulative_weights = []
        cumsum = 0.0
        for weight in self.zone_weights:
            cumsum += weight
            self._zone_cumulative_weights.append(cumsum)
    
    def _sample_zone_index(self) -> int:
        """
        Zone 가중치 기반으로 Zone 인덱스를 확률적으로 샘플링.
        
        Returns:
            Zone 인덱스 (0~3 for Z1~Z4)
        """
        # [0, total_weight) 범위에서 난수 생성
        total_weight = self._zone_cumulative_weights[-1]
        rand_val = self._rng.uniform(0, total_weight)
        
        # 누적합에서 rand_val이 들어갈 구간 찾기 (binary search 가능하지만 zone 개수가 적어 linear scan)
        for idx, cumsum in enumerate(self._zone_cumulative_weights):
            if rand_val < cumsum:
                return idx
        
        # Fallback (부동소수점 오차 대비)
        return len(self._zone_cumulative_weights) - 1
    
    def next(self) -> float:
        """
        다음 Entry BPS 값을 생성한다.
        
        Returns:
            Entry BPS (float)
        """
        if self.mode == "fixed":
            return self._next_fixed()
        elif self.mode == "cycle":
            return self._next_cycle()
        elif self.mode == "random":
            return self._next_random()
        elif self.mode == "zone_random":
            return self._next_zone_random()
        else:
            raise ValueError(f"Unknown mode: {self.mode}")
    
    def _next_fixed(self) -> float:
        """Fixed 모드: 항상 같은 값 반환."""
        return self.min_bps
    
    def _next_cycle(self) -> float:
        """
        Cycle 모드: Zone별 대표 BPS를 순환.
        
        각 Zone의 중간값을 사용하여 순환한다.
        예: Z1(6.0) → Z2(9.5) → Z3(16.0) → Z4(25.0) → Z1 ...
        """
        zone_idx = self._cycle_index % len(self.zone_boundaries)
        zmin, zmax = self.zone_boundaries[zone_idx]
        
        # Zone 중간값 사용
        bps = (zmin + zmax) / 2.0
        
        self._cycle_index += 1
        return bps
    
    def _next_random(self) -> float:
        """
        Random 모드: [min_bps, max_bps] 범위 내 균일 분포 난수 생성.
        
        Returns:
            균일 분포 난수 (float)
        """
        return self._rng.uniform(self.min_bps, self.max_bps)
    
    def _next_zone_random(self) -> float:
        """
        Zone Random 모드 (D90-0): Zone 가중치 기반 확률적 샘플링.
        
        1. zone_weights 비율로 Zone 인덱스를 확률적으로 선택
        2. 선택된 Zone의 (min_bps, max_bps) 범위 내에서 균등 분포 샘플링
        
        Returns:
            Entry BPS (float)
        """
        # 1. Zone 선택 (가중치 기반 확률 분포)
        zone_idx = self._sample_zone_index()
        
        # 2. 선택된 Zone의 boundary 내에서 균등 샘플링
        zmin, zmax = self.zone_boundaries[zone_idx]
        bps = self._rng.uniform(zmin, zmax)
        
        return bps
    
    def reset(self):
        """
        프로파일 상태를 초기화한다.
        
        - cycle 모드: 인덱스를 0으로 리셋
        - random 모드: 난수 생성기를 재초기화
        - zone_random 모드: 난수 생성기 재초기화 + 누적 가중치 재계산
        """
        self._cycle_index = 0
        self._rng = random.Random(self.seed)
        if self.mode == "zone_random":
            self._compute_cumulative_weights()
    
    def __repr__(self):
        return (
            f"EntryBPSProfile(mode={self.mode!r}, min_bps={self.min_bps}, "
            f"max_bps={self.max_bps}, seed={self.seed})"
        )
