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
        
        D92-4: YAML에 명시된 threshold_bps가 있으면 우선 사용
        
        Advisory 모드 (threshold_bps 없을 때):
        - Zone 가중치가 높은 Zone의 중간값을 threshold로 사용
        - 예: advisory_z2_focus → Z2(7-12 bps) 중간값 = 9.5 bps
        
        Strict 모드:
        - Zone 경계값 최소값을 threshold로 사용
        """
        for symbol, profile in self.symbol_profiles.items():
            zone_boundaries = profile["zone_boundaries"]
            zone_weights = profile["profile_weights"]
            mode = profile["mode"]
            
            # D92-4: YAML에 threshold_bps가 명시되어 있으면 우선 사용
            if "threshold_bps" in profile and profile["threshold_bps"] is not None:
                threshold_bps = profile["threshold_bps"]
                logger.info(f"[D92-4] {symbol}: Using explicit threshold_bps={threshold_bps:.2f} from YAML")
            elif mode == "advisory":
                # 가중치가 가장 높은 Zone 찾기
                max_weight_idx = zone_weights.index(max(zone_weights))
                zone_min, zone_max = zone_boundaries[max_weight_idx]
                logger.info(f"[D92-2-DEBUG] {symbol}: max_weight_idx={max_weight_idx}, zone=({zone_min}, {zone_max})")
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
    def from_file(cls, yaml_path: str) -> "ZoneProfileApplier":
        """
        D92-7-4: YAML 파일에서 Zone Profile을 로드 (정규화 + FAIL-FAST).
        
        지원 스키마:
        1. symbol_mappings: { "BTC": {threshold_bps, zone_boundaries, default_profiles, ...}, ... }
        2. symbols: { "BTC": {profile_name, profile_weights, zone_boundaries, mode, ...}, ... }
        3. symbol_profiles: (symbols와 동일)
        
        내부 정규화:
        - 모든 입력을 단일 dict 구조로 변환
        - threshold_bps 누락/None → default threshold (0.70 bps) 사용 + 카운터 기록
        - 필수 필드 검증: zone_boundaries, profile_weights 등
        
        FAIL-FAST:
        - 파싱/검증 실패 시 즉시 예외 발생 (조용히 진행 금지)
        - 에러 메시지: 어떤 심볼/필드에서 실패했는지 명확히
        
        Args:
            yaml_path: Zone Profile YAML 파일 경로
        
        Returns:
            ZoneProfileApplier 인스턴스
        
        Raises:
            FileNotFoundError: YAML 파일 없음
            ValueError: 파싱/검증 실패
        """
        import yaml
        from pathlib import Path
        
        yaml_path_obj = Path(yaml_path)
        if not yaml_path_obj.exists():
            raise FileNotFoundError(f"[D92-7-4] Zone Profile YAML not found: {yaml_path}")
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"[D92-7-4] Failed to parse YAML {yaml_path}: {e}")
        
        if not isinstance(data, dict):
            raise ValueError(f"[D92-7-4] YAML root must be dict, got {type(data)}")
        
        # D92-7-4: 스키마 정규화 (symbol_mappings → symbol_profiles)
        symbol_mappings = data.get("symbol_mappings", {})
        symbol_profiles_direct = data.get("symbols") or data.get("symbol_profiles", {})
        profiles_dict = data.get("profiles", {})
        
        symbol_profiles = {}
        fallback_threshold_count = 0
        
        if symbol_mappings:
            # symbol_mappings 구조 정규화
            for symbol, mapping in symbol_mappings.items():
                if not isinstance(mapping, dict):
                    raise ValueError(f"[D92-7-4] symbol_mappings[{symbol}] must be dict, got {type(mapping)}")
                
                # Profile 선택 (advisory 우선, 없으면 strict)
                default_profiles = mapping.get("default_profiles", {})
                profile_name = default_profiles.get("advisory") or default_profiles.get("strict") or "advisory_z2_focus"
                
                if profile_name not in profiles_dict:
                    logger.warning(f"[D92-7-4] Profile '{profile_name}' not found for {symbol}, using default weights")
                    profile_weights = [1.0, 1.0, 1.0, 1.0]
                else:
                    profile_weights = profiles_dict[profile_name].get("weights", [1.0, 1.0, 1.0, 1.0])
                
                # Zone boundaries 검증
                zone_boundaries = mapping.get("zone_boundaries")
                if not zone_boundaries:
                    raise ValueError(f"[D92-7-4] Missing zone_boundaries for symbol {symbol}")
                if not isinstance(zone_boundaries, list) or len(zone_boundaries) < 1:
                    raise ValueError(f"[D92-7-4] zone_boundaries for {symbol} must be non-empty list, got {zone_boundaries}")
                
                # threshold_bps 처리 (None/누락 → fallback)
                threshold_bps = mapping.get("threshold_bps")
                if threshold_bps is None:
                    threshold_bps = 0.70  # Default fallback threshold
                    fallback_threshold_count += 1
                    logger.info(f"[D92-7-4] {symbol}: threshold_bps=None, using fallback {threshold_bps} bps")
                
                symbol_profiles[symbol] = {
                    "profile_name": profile_name,
                    "profile_weights": profile_weights,
                    "zone_boundaries": zone_boundaries,
                    "mode": "advisory",
                    "threshold_bps": threshold_bps,
                }
        
        elif symbol_profiles_direct:
            # symbols/symbol_profiles 구조 (이미 정규화됨)
            for symbol, profile in symbol_profiles_direct.items():
                if not isinstance(profile, dict):
                    raise ValueError(f"[D92-7-4] symbols[{symbol}] must be dict, got {type(profile)}")
                
                # 필수 필드 검증
                if "zone_boundaries" not in profile:
                    raise ValueError(f"[D92-7-4] Missing zone_boundaries for symbol {symbol}")
                
                profile_weights = profile.get("profile_weights", [1.0, 1.0, 1.0, 1.0])
                threshold_bps = profile.get("threshold_bps")
                
                if threshold_bps is None:
                    threshold_bps = 0.70
                    fallback_threshold_count += 1
                    logger.info(f"[D92-7-4] {symbol}: threshold_bps=None, using fallback {threshold_bps} bps")
                
                symbol_profiles[symbol] = {
                    "profile_name": profile.get("profile_name", "default"),
                    "profile_weights": profile_weights,
                    "zone_boundaries": profile["zone_boundaries"],
                    "mode": profile.get("mode", "advisory"),
                    "threshold_bps": threshold_bps,
                }
        
        else:
            raise ValueError(f"[D92-7-4] No symbol_mappings or symbols found in {yaml_path}")
        
        if not symbol_profiles:
            raise ValueError(f"[D92-7-4] No symbols loaded from {yaml_path}")
        
        # 인스턴스 생성
        instance = cls(symbol_profiles=symbol_profiles)
        
        # D92-7-4: 메타데이터 저장
        instance._yaml_path = yaml_path
        instance._fallback_threshold_count = fallback_threshold_count
        
        logger.info(f"[D92-7-4] Zone Profile loaded: {len(symbol_profiles)} symbols, {fallback_threshold_count} fallback thresholds")
        
        return instance
