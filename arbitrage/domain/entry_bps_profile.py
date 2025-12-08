#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D88-0: Entry BPS Profile

PAPER 실행 시 Entry BPS를 다양하게 생성하여 Zone별 트레이드 분산을 유도하는 프로파일.

**목표:**
- Z1~Z4 Zone에 트레이드가 분산되도록 Entry BPS 생성
- 재현 가능성(Reproducibility) 보장 (seed 기반)
- 기존 도메인 로직 변경 없이 PAPER 시나리오 입력만 조정

**Modes:**
1. **fixed**: 고정값 (기존 동작, 하나의 BPS만 사용)
2. **cycle**: Zone별 대표 BPS를 순환 (Z1 → Z2 → Z3 → Z4 → Z1 ...)
3. **random**: [min_bps, max_bps] 범위 내 균일 분포 난수 생성

Author: arbitrage-lite project
Date: 2025-12-09
"""

import random
from typing import List, Literal, Optional


class EntryBPSProfile:
    """
    Entry BPS 생성 프로파일.
    
    PAPER 실행 시 Zone별 트레이드 분산을 위해 다양한 Entry BPS를 생성한다.
    
    Args:
        mode: 생성 모드 ("fixed", "cycle", "random")
        min_bps: 최소 BPS (기본값 10.0)
        max_bps: 최대 BPS (기본값 10.0)
        seed: 난수 생성 seed (재현성 보장, 기본값 42)
        zone_boundaries: Zone 경계값 (옵션, 없으면 기본값 사용)
            예: [(5, 7), (7, 12), (12, 20), (20, 30)]
    
    Attributes:
        mode: 생성 모드
        min_bps: 최소 BPS
        max_bps: 최대 BPS
        seed: 난수 생성 seed
        zone_boundaries: Zone 경계값 리스트 [(min, max), ...]
        _cycle_index: cycle 모드용 인덱스
        _rng: random.Random 인스턴스 (독립적인 난수 생성기)
    
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
    """
    
    def __init__(
        self,
        mode: Literal["fixed", "cycle", "random"] = "fixed",
        min_bps: float = 10.0,
        max_bps: float = 10.0,
        seed: int = 42,
        zone_boundaries: Optional[List[tuple]] = None,
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
        
        # Cycle 모드용 인덱스
        self._cycle_index = 0
        
        # Random 모드용 독립 난수 생성기
        self._rng = random.Random(seed)
        
        # 입력 검증
        self._validate()
    
    def _validate(self):
        """입력 파라미터 검증."""
        if self.mode not in ["fixed", "cycle", "random"]:
            raise ValueError(f"Invalid mode: {self.mode}. Must be 'fixed', 'cycle', or 'random'.")
        
        if self.min_bps < 0 or self.max_bps < 0:
            raise ValueError(f"min_bps and max_bps must be non-negative: min={self.min_bps}, max={self.max_bps}")
        
        if self.min_bps > self.max_bps:
            raise ValueError(f"min_bps must be <= max_bps: min={self.min_bps}, max={self.max_bps}")
        
        if not self.zone_boundaries:
            raise ValueError("zone_boundaries must not be empty")
        
        for i, (zmin, zmax) in enumerate(self.zone_boundaries):
            if zmin >= zmax:
                raise ValueError(f"Zone {i} has invalid boundaries: min={zmin}, max={zmax}")
    
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
    
    def reset(self):
        """
        프로파일 상태를 초기화한다.
        
        - cycle 모드: 인덱스를 0으로 리셋
        - random 모드: 난수 생성기를 재초기화
        """
        self._cycle_index = 0
        self._rng = random.Random(self.seed)
    
    def __repr__(self):
        return (
            f"EntryBPSProfile(mode={self.mode!r}, min_bps={self.min_bps}, "
            f"max_bps={self.max_bps}, seed={self.seed})"
        )
