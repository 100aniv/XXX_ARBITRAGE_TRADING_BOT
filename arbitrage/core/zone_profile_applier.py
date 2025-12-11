#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92-1-FIX: Zone Profile Applier

Zone Profile v2 설정을 실제 PAPER 실행 엔진에 적용하는 모듈.

Purpose:
- 심볼별 Zone Profile 매핑 정보를 로드
- Entry threshold, spread guard, zone boundaries를 심볼별로 override
- Profile 적용 여부를 실시간 로깅

Author: arbitrage-lite project
Date: 2025-12-12 (D92-1-FIX)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ZoneProfileApplier:
    """
    Zone Profile v2를 PAPER 실행 엔진에 적용하는 클래스.
    
    D92-1 구조적 한계 해결:
    - run_d92_1에서 준비한 Zone Profile 설정을 run_d77_0로 전달
    - 심볼별 entry threshold, zone boundaries를 runtime에 override
    """
    
    def __init__(self, symbol_profiles: Dict[str, Dict[str, Any]]):
        """
        Args:
            symbol_profiles: 심볼별 Zone Profile 설정
                {
                    "BTC": {
                        "profile_name": "advisory_z2_focus",
                        "profile_weights": [0.5, 3.0, 1.5, 0.5],
                        "zone_boundaries": [(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 30.0)],
                        "mode": "advisory"
                    },
                    ...
                }
        """
        self.symbol_profiles = symbol_profiles
        self._symbol_thresholds: Dict[str, float] = {}
        self._symbol_zone_boundaries: Dict[str, List[tuple]] = {}
        
        # 초기화 시 threshold 계산
        self._compute_thresholds()
        
        logger.info("=" * 80)
        logger.info("[ZONE_PROFILE_APPLIER] Initialized with %d symbols", len(symbol_profiles))
        for symbol, profile in symbol_profiles.items():
            logger.info(
                "[ZONE_PROFILE_APPLIED] %s → %s (Z1=%.1f%%, Z2=%.1f%%, Z3=%.1f%%, Z4=%.1f%%, threshold=%.5f)",
                symbol,
                profile["profile_name"],
                profile["profile_weights"][0] * 10,
                profile["profile_weights"][1] * 10,
                profile["profile_weights"][2] * 10,
                profile["profile_weights"][3] * 10,
                self._symbol_thresholds.get(symbol, 0.0),
            )
        logger.info("=" * 80)
    
    def _compute_thresholds(self) -> None:
        """
        Zone Profile에서 entry threshold를 계산.
        
        Advisory 모드:
        - Zone 가중치가 높은 Zone의 중간값을 threshold로 사용
        - 예: advisory_z2_focus → Z2(7-12 bps) 중간값 = 9.5 bps
        
        Strict 모드:
        - Zone 경계값 최소값을 threshold로 사용
        """
        for symbol, profile in self.symbol_profiles.items():
            zone_boundaries = profile["zone_boundaries"]
            zone_weights = profile["profile_weights"]
            mode = profile["mode"]
            
            if mode == "advisory":
                # 가중치가 가장 높은 Zone 찾기
                max_weight_idx = zone_weights.index(max(zone_weights))
                zone_min, zone_max = zone_boundaries[max_weight_idx]
                # Zone 중간값을 threshold로 사용
                threshold_bps = (zone_min + zone_max) / 2.0
            else:  # strict
                # 첫 번째 Zone의 최소값을 threshold로 사용
                threshold_bps = zone_boundaries[0][0]
            
            # BPS를 decimal로 변환 (10 bps = 0.001 = 0.1%)
            self._symbol_thresholds[symbol] = threshold_bps / 10000.0
            self._symbol_zone_boundaries[symbol] = zone_boundaries
    
    def get_entry_threshold(self, symbol: str) -> float:
        """
        심볼별 entry threshold 조회.
        
        Args:
            symbol: 심볼 (예: "BTC")
        
        Returns:
            Entry threshold (decimal, 예: 0.00095 = 9.5 bps)
        """
        if symbol not in self._symbol_thresholds:
            raise ValueError(
                f"[ZONE_PROFILE_APPLIER] No Zone Profile configured for symbol: {symbol}. "
                f"Available symbols: {list(self._symbol_thresholds.keys())}"
            )
        return self._symbol_thresholds[symbol]
    
    def get_zone_boundaries(self, symbol: str) -> List[tuple]:
        """
        심볼별 zone boundaries 조회.
        
        Args:
            symbol: 심볼 (예: "BTC")
        
        Returns:
            Zone boundaries [(min, max), ...]
        """
        if symbol not in self._symbol_zone_boundaries:
            raise ValueError(
                f"[ZONE_PROFILE_APPLIER] No Zone boundaries for symbol: {symbol}"
            )
        return self._symbol_zone_boundaries[symbol]
    
    def has_profile(self, symbol: str) -> bool:
        """
        심볼에 Zone Profile이 설정되어 있는지 확인.
        
        Args:
            symbol: 심볼
        
        Returns:
            True if profile exists
        """
        return symbol in self.symbol_profiles
    
    @classmethod
    def from_json(cls, json_str: str) -> "ZoneProfileApplier":
        """
        JSON string에서 ZoneProfileApplier 생성.
        
        Args:
            json_str: Symbol profiles JSON
        
        Returns:
            ZoneProfileApplier instance
        """
        symbol_profiles = json.loads(json_str)
        return cls(symbol_profiles)
    
    @classmethod
    def from_file(cls, file_path: str) -> "ZoneProfileApplier":
        """
        JSON 파일에서 ZoneProfileApplier 생성.
        
        Args:
            file_path: Symbol profiles JSON 파일 경로
        
        Returns:
            ZoneProfileApplier instance
        """
        with open(file_path, 'r') as f:
            symbol_profiles = json.load(f)
        return cls(symbol_profiles)
