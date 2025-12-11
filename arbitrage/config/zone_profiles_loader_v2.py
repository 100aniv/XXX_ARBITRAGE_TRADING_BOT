#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D91-1: Zone Profile YAML v2 Loader (Symbol Mapping PoC)

YAML v2.0.0 스키마 기반 Zone Profile 로더 및 심볼별 선택 로직.

**목표:**
- symbol_mappings 섹션 도입으로 심볼별 Zone Profile 매핑 지원
- BTC/ETH/XRP (Upbit) 3개 심볼 PoC
- v1 YAML과 하위 호환성 유지 (v2 없으면 v1 Fallback)

**YAML v2 스키마:**
- profiles: 글로벌 프로파일 정의 (v1과 동일)
- symbol_mappings: 심볼별 default_profiles, zone_boundaries, liquidity_tier 등
- metadata.schema_version: "2.0.0"

**Fallback 전략:**
- v2 YAML 없음/로드 실패 → v1 로더(load_zone_profiles_with_fallback) 호출
- v1도 실패 → 내장 Fallback (strict_uniform, advisory_z2_focus)

Author: arbitrage-lite project
Date: 2025-12-11 (D91-1)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import yaml

from arbitrage.config.zone_profiles_loader import (
    ZoneProfileLoadError,
    validate_profile_data,
    load_zone_profiles_with_fallback as load_v1_with_fallback,
)

# ZoneProfile 임포트 (순환 참조 방지를 위해 TYPE_CHECKING 사용)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from arbitrage.domain.entry_bps_profile import ZoneProfile
else:
    ZoneProfile = None

logger = logging.getLogger(__name__)


def get_zone_profiles_v2_yaml_path() -> Path:
    """
    Zone Profile YAML v2 파일 경로 반환.
    
    Returns:
        YAML v2 파일 절대 경로
    """
    # 프로젝트 루트 기준 상대 경로
    # arbitrage/config/zone_profiles_loader_v2.py → ../../config/arbitrage/zone_profiles_v2.yaml
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent  # arbitrage-lite/
    yaml_path = project_root / "config" / "arbitrage" / "zone_profiles_v2.yaml"
    return yaml_path


def validate_symbol_mapping_data(symbol: str, data: Dict[str, Any]) -> None:
    """
    심볼 매핑 데이터 검증.
    
    Args:
        symbol: 심볼 이름 (예: "BTC", "ETH")
        data: 심볼 매핑 데이터 dict
    
    Raises:
        ZoneProfileLoadError: 검증 실패 시
    """
    # 1. 필수 필드 확인
    required_fields = ["market", "default_profiles"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ZoneProfileLoadError(
            f"Symbol mapping '{symbol}' missing required fields: {missing}"
        )
    
    # 2. market 타입 확인
    if not isinstance(data["market"], str):
        raise ZoneProfileLoadError(
            f"Symbol mapping '{symbol}' market must be string, got {type(data['market'])}"
        )
    
    # 3. default_profiles 구조 확인
    default_profiles = data["default_profiles"]
    if not isinstance(default_profiles, dict):
        raise ZoneProfileLoadError(
            f"Symbol mapping '{symbol}' default_profiles must be dict, got {type(default_profiles)}"
        )
    
    # 4. default_profiles에 strict/advisory 키 확인
    for mode in ["strict", "advisory"]:
        if mode not in default_profiles:
            raise ZoneProfileLoadError(
                f"Symbol mapping '{symbol}' default_profiles missing '{mode}' key"
            )
        if not isinstance(default_profiles[mode], str):
            raise ZoneProfileLoadError(
                f"Symbol mapping '{symbol}' default_profiles.{mode} must be string, "
                f"got {type(default_profiles[mode])}"
            )
    
    # 5. zone_boundaries 검증 (선택적 필드)
    if "zone_boundaries" in data:
        boundaries = data["zone_boundaries"]
        if not isinstance(boundaries, list):
            raise ZoneProfileLoadError(
                f"Symbol mapping '{symbol}' zone_boundaries must be list, got {type(boundaries)}"
            )
        if len(boundaries) != 4:
            raise ZoneProfileLoadError(
                f"Symbol mapping '{symbol}' zone_boundaries must have 4 zones, got {len(boundaries)}"
            )
        for i, zone in enumerate(boundaries):
            if not isinstance(zone, list) or len(zone) != 2:
                raise ZoneProfileLoadError(
                    f"Symbol mapping '{symbol}' zone_boundaries[{i}] must be [min, max], got {zone}"
                )


def load_zone_profiles_v2_from_yaml(yaml_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    YAML v2 파일에서 Zone Profile 및 Symbol Mapping 로드.
    
    Args:
        yaml_path: YAML v2 파일 경로 (None이면 기본 경로 사용)
    
    Returns:
        {
            "profiles": {profile_name: ZoneProfile},
            "symbol_mappings": {symbol: mapping_data},
            "metadata": metadata_dict
        }
    
    Raises:
        ZoneProfileLoadError: 로드/파싱/검증 실패 시
    """
    # ZoneProfile 클래스 동적 임포트 (순환 참조 방지)
    from arbitrage.domain.entry_bps_profile import ZoneProfile as ZP
    global ZoneProfile
    ZoneProfile = ZP
    
    if yaml_path is None:
        yaml_path = get_zone_profiles_v2_yaml_path()
    
    # 1. 파일 존재 확인
    if not yaml_path.exists():
        raise ZoneProfileLoadError(
            f"Zone profiles YAML v2 not found: {yaml_path}\n"
            f"Falling back to v1 loader."
        )
    
    # 2. YAML 로드
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ZoneProfileLoadError(
            f"Failed to parse YAML v2 file {yaml_path}: {e}"
        ) from e
    except Exception as e:
        raise ZoneProfileLoadError(
            f"Failed to read YAML v2 file {yaml_path}: {e}"
        ) from e
    
    # 3. 루트 구조 확인
    if not isinstance(data, dict):
        raise ZoneProfileLoadError(
            f"YAML v2 root must be a dict, got {type(data)}"
        )
    
    if "profiles" not in data:
        raise ZoneProfileLoadError(
            f"YAML v2 missing 'profiles' section"
        )
    
    # 4. metadata 확인 (schema_version = "2.0.0")
    metadata = data.get("metadata", {})
    schema_version = metadata.get("schema_version")
    if schema_version != "2.0.0":
        logger.warning(
            f"[ZONE_PROFILES_V2] Expected schema_version '2.0.0', got '{schema_version}'. "
            f"Proceeding with caution."
        )
    
    # 5. profiles 섹션 파싱 (v1과 동일한 방식)
    profiles_data = data["profiles"]
    if not isinstance(profiles_data, dict):
        raise ZoneProfileLoadError(
            f"'profiles' section must be a dict, got {type(profiles_data)}"
        )
    
    profiles: Dict[str, ZoneProfile] = {}
    
    for name, profile_data in profiles_data.items():
        if not isinstance(profile_data, dict):
            logger.warning(
                f"Skipping profile '{name}': data must be dict, got {type(profile_data)}"
            )
            continue
        
        try:
            # v1 검증 로직 재사용
            validate_profile_data(name, profile_data)
            
            # ZoneProfile 인스턴스 생성
            weights = profile_data["weights"]
            description = profile_data.get("description", f"Zone profile: {name}")
            
            profile = ZoneProfile(
                name=name,
                description=description,
                zone_weights=tuple(weights),
            )
            
            profiles[name] = profile
            
            logger.debug(
                f"[V2] Loaded profile '{name}': weights={weights}, "
                f"status={profile_data.get('status', 'unknown')}"
            )
        
        except ZoneProfileLoadError as e:
            logger.error(f"[V2] Failed to load profile '{name}': {e}")
            raise
        except Exception as e:
            logger.error(f"[V2] Unexpected error loading profile '{name}': {e}")
            raise ZoneProfileLoadError(
                f"Failed to load profile '{name}': {e}"
            ) from e
    
    # 6. 최소 프로파일 확인 (strict_uniform, advisory_z2_focus)
    required_profiles = ["strict_uniform", "advisory_z2_focus"]
    missing = [p for p in required_profiles if p not in profiles]
    
    if missing:
        raise ZoneProfileLoadError(
            f"YAML v2 missing required profiles: {missing}\n"
            f"Production requires at least: {required_profiles}"
        )
    
    # 7. symbol_mappings 섹션 파싱 (선택적)
    symbol_mappings: Dict[str, Dict[str, Any]] = {}
    
    if "symbol_mappings" in data:
        mappings_data = data["symbol_mappings"]
        if not isinstance(mappings_data, dict):
            logger.warning(
                f"[V2] 'symbol_mappings' section must be dict, got {type(mappings_data)}. "
                f"Ignoring symbol_mappings."
            )
        else:
            for symbol, mapping_data in mappings_data.items():
                if not isinstance(mapping_data, dict):
                    logger.warning(
                        f"[V2] Skipping symbol mapping '{symbol}': data must be dict, "
                        f"got {type(mapping_data)}"
                    )
                    continue
                
                try:
                    validate_symbol_mapping_data(symbol, mapping_data)
                    symbol_mappings[symbol] = mapping_data
                    
                    logger.debug(
                        f"[V2] Loaded symbol mapping '{symbol}': "
                        f"market={mapping_data['market']}, "
                        f"profiles={mapping_data['default_profiles']}"
                    )
                
                except ZoneProfileLoadError as e:
                    logger.error(f"[V2] Failed to load symbol mapping '{symbol}': {e}")
                    raise
                except Exception as e:
                    logger.error(f"[V2] Unexpected error loading symbol mapping '{symbol}': {e}")
                    raise ZoneProfileLoadError(
                        f"Failed to load symbol mapping '{symbol}': {e}"
                    ) from e
    
    logger.info(
        f"[ZONE_PROFILES_V2] Loaded {len(profiles)} profiles and "
        f"{len(symbol_mappings)} symbol mappings from {yaml_path}"
    )
    
    return {
        "profiles": profiles,
        "symbol_mappings": symbol_mappings,
        "metadata": metadata,
    }


def load_zone_profiles_v2_with_fallback(yaml_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    YAML v2에서 Zone Profile 로드, 실패 시 v1 Fallback.
    
    Fallback 전략:
    - v2 YAML 파일 없음/로드 실패 → v1 로더 호출
    - v1도 실패 → 내장 Fallback (strict_uniform, advisory_z2_focus)
    
    Args:
        yaml_path: YAML v2 파일 경로 (None이면 기본 경로 사용)
    
    Returns:
        {
            "profiles": {profile_name: ZoneProfile},
            "symbol_mappings": {symbol: mapping_data},
            "metadata": metadata_dict,
            "source": "v2" | "v1" | "fallback"
        }
    """
    try:
        result = load_zone_profiles_v2_from_yaml(yaml_path=yaml_path)
        result["source"] = "v2"
        return result
    
    except ZoneProfileLoadError as e:
        logger.warning(
            f"[ZONE_PROFILES_V2] Failed to load from YAML v2: {e}\n"
            f"Falling back to v1 loader."
        )
        
        # Fallback to v1
        try:
            v1_profiles = load_v1_with_fallback()
            logger.info(
                f"[ZONE_PROFILES_V2] Successfully loaded {len(v1_profiles)} profiles from v1"
            )
            return {
                "profiles": v1_profiles,
                "symbol_mappings": {},  # v1에는 symbol_mappings 없음
                "metadata": {"schema_version": "1.0.0"},
                "source": "v1",
            }
        
        except Exception as e2:
            logger.error(
                f"[ZONE_PROFILES_V2] v1 fallback also failed: {e2}\n"
                f"This should not happen (v1 has built-in fallback)."
            )
            raise ZoneProfileLoadError(
                f"Both v2 and v1 loaders failed. v2 error: {e}, v1 error: {e2}"
            ) from e2


def select_profile_for_symbol(
    symbol: str,
    market: str,
    mode: Literal["strict", "advisory"],
    profiles: Dict[str, 'ZoneProfile'],
    symbol_mappings: Dict[str, Dict[str, Any]]
) -> 'ZoneProfile':
    """
    심볼/마켓/모드에 맞는 Zone Profile 선택.
    
    우선순위:
    1. symbol_mappings[symbol][market][mode] 존재 시 해당 프로파일
    2. symbol_mappings[symbol][mode] 존재하되 market 불일치 시 글로벌 기본
    3. profiles[f"{mode}_default"] 존재 시 글로벌 기본
    4. Fallback: strict → strict_uniform, advisory → advisory_z2_focus
    
    Args:
        symbol: 심볼 이름 (예: "BTC", "ETH", "XRP")
        market: 마켓 이름 (예: "upbit", "binance")
        mode: "strict" 또는 "advisory"
        profiles: 로드된 프로파일 dict
        symbol_mappings: 로드된 심볼 매핑 dict
    
    Returns:
        선택된 ZoneProfile 인스턴스
    
    Raises:
        ZoneProfileLoadError: 프로파일을 찾을 수 없을 때
    """
    # 1. 심볼별 매핑 확인
    if symbol in symbol_mappings:
        mapping = symbol_mappings[symbol]
        
        # market 일치 여부 확인
        if market == mapping.get("market"):
            profile_name = mapping.get("default_profiles", {}).get(mode)
            
            if profile_name:
                if profile_name in profiles:
                    logger.debug(
                        f"[SELECT] Symbol '{symbol}' ({market}, {mode}) → profile '{profile_name}' "
                        f"(symbol-specific mapping)"
                    )
                    return profiles[profile_name]
                else:
                    logger.warning(
                        f"[SELECT] Symbol mapping '{symbol}' references non-existent profile "
                        f"'{profile_name}'. Falling back to global default."
                    )
        else:
            logger.debug(
                f"[SELECT] Symbol '{symbol}' found in mappings but market mismatch "
                f"(requested: {market}, mapped: {mapping.get('market')}). "
                f"Falling back to global default."
            )
    
    # 2. 글로벌 기본 프로파일 확인 (예: "strict_default", "advisory_default")
    default_name = f"{mode}_default"
    if default_name in profiles:
        logger.debug(
            f"[SELECT] Symbol '{symbol}' ({market}, {mode}) → profile '{default_name}' "
            f"(global default)"
        )
        return profiles[default_name]
    
    # 3. Fallback (프로덕션 baseline)
    fallback_name = "strict_uniform" if mode == "strict" else "advisory_z2_focus"
    
    if fallback_name in profiles:
        logger.debug(
            f"[SELECT] Symbol '{symbol}' ({market}, {mode}) → profile '{fallback_name}' "
            f"(fallback baseline)"
        )
        return profiles[fallback_name]
    
    # 4. 최악의 경우 (이론상 발생하지 않아야 함)
    raise ZoneProfileLoadError(
        f"Cannot select profile for symbol '{symbol}' ({market}, {mode}). "
        f"Neither symbol mapping, global default ('{default_name}'), "
        f"nor fallback ('{fallback_name}') found in loaded profiles: {list(profiles.keys())}"
    )


def get_zone_boundaries_for_symbol(
    symbol: str,
    market: str,
    symbol_mappings: Dict[str, Dict[str, Any]],
    default_boundaries: Optional[List[Tuple[float, float]]] = None
) -> List[Tuple[float, float]]:
    """
    심볼/마켓에 맞는 Zone Boundaries 반환.
    
    Args:
        symbol: 심볼 이름 (예: "BTC", "ETH", "XRP")
        market: 마켓 이름 (예: "upbit", "binance")
        symbol_mappings: 로드된 심볼 매핑 dict
        default_boundaries: 기본 Zone Boundaries (None이면 BTC 기준값 사용)
    
    Returns:
        Zone boundaries list [(min1, max1), (min2, max2), (min3, max3), (min4, max4)]
    """
    # 기본값 설정 (BTC baseline)
    if default_boundaries is None:
        default_boundaries = [
            (5.0, 7.0),
            (7.0, 12.0),
            (12.0, 20.0),
            (20.0, 25.0)
        ]
    
    # 심볼별 매핑 확인
    if symbol in symbol_mappings:
        mapping = symbol_mappings[symbol]
        
        # market 일치 여부 확인
        if market == mapping.get("market"):
            if "zone_boundaries" in mapping:
                boundaries_data = mapping["zone_boundaries"]
                
                # [[min, max], ...] → [(min, max), ...]
                boundaries = [tuple(zone) for zone in boundaries_data]
                
                logger.debug(
                    f"[BOUNDARIES] Symbol '{symbol}' ({market}) → {boundaries} "
                    f"(symbol-specific)"
                )
                return boundaries
    
    # Fallback to default
    logger.debug(
        f"[BOUNDARIES] Symbol '{symbol}' ({market}) → {default_boundaries} "
        f"(default)"
    )
    return default_boundaries
