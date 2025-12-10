#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D90-4: Zone Profile YAML Loader

Zone Profile 정의를 YAML 파일에서 로드하고 ZoneProfile 인스턴스로 변환.

**목표:**
- Zone Profile 정의를 코드에서 YAML 설정으로 외부화
- 기존 D90-0~3 결과와 완전히 동일한 Zone 분포/PnL 재현
- 설정 변경 시 코드 수정 불필요

**YAML 파일:**
- 경로: config/arbitrage/zone_profiles.yaml
- 스키마: profiles → {name → {description, weights, status}}

**Fallback 전략:**
- YAML 파일 없음/로드 실패 시 기본 프로파일 2개 내장
- strict_uniform, advisory_z2_focus만 최소 보장
- 운영 환경에서는 YAML 필수 (경고 로그)

Author: arbitrage-lite project
Date: 2025-12-10 (D90-4)
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

# ZoneProfile 임포트 (순환 참조 방지를 위해 TYPE_CHECKING 사용)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from arbitrage.domain.entry_bps_profile import ZoneProfile
else:
    # 실제 런타임에서는 동적 임포트
    ZoneProfile = None

logger = logging.getLogger(__name__)


class ZoneProfileLoadError(Exception):
    """Zone Profile 로드 실패 예외."""
    pass


# Fallback 기본 프로파일 (YAML 로드 실패 시)
FALLBACK_PROFILES: Dict[str, Dict] = {
    "strict_uniform": {
        "description": "Baseline uniform profile used for strict mode (Z1~Z4 ≈ 25%)",
        "weights": [1.0, 1.0, 1.0, 1.0],
        "status": "production",
    },
    "advisory_z2_focus": {
        "description": "Production baseline advisory profile with strong Z2 emphasis",
        "weights": [0.5, 3.0, 1.5, 0.5],
        "status": "production",
    },
}


def get_zone_profiles_yaml_path() -> Path:
    """
    Zone Profile YAML 파일 경로 반환.
    
    Returns:
        YAML 파일 절대 경로
    """
    # 프로젝트 루트 기준 상대 경로
    # arbitrage/config/zone_profiles_loader.py → ../../config/arbitrage/zone_profiles.yaml
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent  # arbitrage-lite/
    yaml_path = project_root / "config" / "arbitrage" / "zone_profiles.yaml"
    return yaml_path


def validate_profile_data(name: str, data: Dict) -> None:
    """
    프로파일 데이터 검증.
    
    Args:
        name: 프로파일 이름
        data: 프로파일 데이터 dict
    
    Raises:
        ZoneProfileLoadError: 검증 실패 시
    """
    # 1. 필수 필드 확인
    if "weights" not in data:
        raise ZoneProfileLoadError(f"Profile '{name}' missing 'weights' field")
    
    # 2. weights 타입/길이 확인
    weights = data["weights"]
    if not isinstance(weights, (list, tuple)):
        raise ZoneProfileLoadError(
            f"Profile '{name}' weights must be list or tuple, got {type(weights)}"
        )
    
    if len(weights) != 4:
        raise ZoneProfileLoadError(
            f"Profile '{name}' weights must have exactly 4 elements (Z1~Z4), got {len(weights)}"
        )
    
    # 3. weights 값 확인 (모두 숫자, 비음수)
    for i, w in enumerate(weights):
        if not isinstance(w, (int, float)):
            raise ZoneProfileLoadError(
                f"Profile '{name}' weight[{i}] must be numeric, got {type(w)}"
            )
        if w < 0:
            raise ZoneProfileLoadError(
                f"Profile '{name}' weight[{i}] must be non-negative, got {w}"
            )
    
    # 4. weights 합이 0이 아닌지 확인
    if sum(weights) == 0:
        raise ZoneProfileLoadError(
            f"Profile '{name}' weights sum cannot be zero"
        )
    
    # 5. description 필드 권장 (필수는 아님)
    if "description" not in data:
        logger.warning(f"Profile '{name}' missing 'description' field (recommended)")


def load_zone_profiles_from_yaml(yaml_path: Optional[Path] = None) -> Dict[str, 'ZoneProfile']:
    """
    YAML 파일에서 Zone Profile 로드.
    
    Args:
        yaml_path: YAML 파일 경로 (None이면 기본 경로 사용)
    
    Returns:
        {profile_name: ZoneProfile} dict
    
    Raises:
        ZoneProfileLoadError: 로드/파싱/검증 실패 시
    
    Examples:
        >>> profiles = load_zone_profiles_from_yaml()
        >>> profiles['strict_uniform'].zone_weights
        (1.0, 1.0, 1.0, 1.0)
    """
    # ZoneProfile 클래스 동적 임포트 (순환 참조 방지)
    from arbitrage.domain.entry_bps_profile import ZoneProfile as ZP
    global ZoneProfile
    ZoneProfile = ZP
    
    if yaml_path is None:
        yaml_path = get_zone_profiles_yaml_path()
    
    # 1. 파일 존재 확인
    if not yaml_path.exists():
        raise ZoneProfileLoadError(
            f"Zone profiles YAML not found: {yaml_path}\n"
            f"Please create the file or check the path."
        )
    
    # 2. YAML 로드
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ZoneProfileLoadError(
            f"Failed to parse YAML file {yaml_path}: {e}"
        ) from e
    except Exception as e:
        raise ZoneProfileLoadError(
            f"Failed to read YAML file {yaml_path}: {e}"
        ) from e
    
    # 3. profiles 섹션 확인
    if not isinstance(data, dict):
        raise ZoneProfileLoadError(
            f"YAML root must be a dict, got {type(data)}"
        )
    
    if "profiles" not in data:
        raise ZoneProfileLoadError(
            f"YAML missing 'profiles' section"
        )
    
    profiles_data = data["profiles"]
    if not isinstance(profiles_data, dict):
        raise ZoneProfileLoadError(
            f"'profiles' section must be a dict, got {type(profiles_data)}"
        )
    
    # 4. 각 프로파일 파싱 및 검증
    profiles: Dict[str, ZoneProfile] = {}
    
    for name, profile_data in profiles_data.items():
        if not isinstance(profile_data, dict):
            logger.warning(
                f"Skipping profile '{name}': data must be dict, got {type(profile_data)}"
            )
            continue
        
        try:
            # 검증
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
                f"Loaded profile '{name}': weights={weights}, "
                f"status={profile_data.get('status', 'unknown')}"
            )
        
        except ZoneProfileLoadError as e:
            logger.error(f"Failed to load profile '{name}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading profile '{name}': {e}")
            raise ZoneProfileLoadError(
                f"Failed to load profile '{name}': {e}"
            ) from e
    
    # 5. 최소 프로파일 확인 (strict_uniform, advisory_z2_focus)
    required_profiles = ["strict_uniform", "advisory_z2_focus"]
    missing = [p for p in required_profiles if p not in profiles]
    
    if missing:
        raise ZoneProfileLoadError(
            f"YAML missing required profiles: {missing}\n"
            f"Production requires at least: {required_profiles}"
        )
    
    logger.info(
        f"[ZONE_PROFILES] Loaded {len(profiles)} profiles from {yaml_path}: "
        f"{list(profiles.keys())}"
    )
    
    return profiles


def load_zone_profiles_with_fallback(yaml_path: Optional[Path] = None) -> Dict[str, 'ZoneProfile']:
    """
    YAML에서 Zone Profile 로드, 실패 시 Fallback 사용.
    
    Fallback 전략:
    - YAML 파일 없음/로드 실패 시 기본 프로파일 2개 사용
    - strict_uniform, advisory_z2_focus만 최소 보장
    - 경고 로그 출력 (운영 환경에서는 YAML 필수)
    
    Args:
        yaml_path: YAML 파일 경로 (None이면 기본 경로 사용)
    
    Returns:
        {profile_name: ZoneProfile} dict (최소 2개 보장)
    
    Examples:
        >>> profiles = load_zone_profiles_with_fallback()
        >>> 'strict_uniform' in profiles
        True
        >>> 'advisory_z2_focus' in profiles
        True
    """
    # ZoneProfile 클래스 동적 임포트
    from arbitrage.domain.entry_bps_profile import ZoneProfile as ZP
    global ZoneProfile
    ZoneProfile = ZP
    
    try:
        return load_zone_profiles_from_yaml(yaml_path=yaml_path)
    
    except ZoneProfileLoadError as e:
        logger.warning(
            f"[ZONE_PROFILES] Failed to load from YAML: {e}\n"
            f"Falling back to built-in profiles (strict_uniform, advisory_z2_focus)"
        )
        
        # Fallback: 기본 프로파일 2개만 생성
        fallback_profiles: Dict[str, ZoneProfile] = {}
        
        for name, data in FALLBACK_PROFILES.items():
            profile = ZoneProfile(
                name=name,
                description=data["description"],
                zone_weights=tuple(data["weights"]),
            )
            fallback_profiles[name] = profile
        
        logger.info(
            f"[ZONE_PROFILES] Using fallback profiles: {list(fallback_profiles.keys())}"
        )
        
        return fallback_profiles


def get_profile(name: str, profiles: Optional[Dict[str, 'ZoneProfile']] = None) -> 'ZoneProfile':
    """
    프로파일 이름으로 ZoneProfile 인스턴스 반환.
    
    Args:
        name: 프로파일 이름
        profiles: 프로파일 dict (None이면 자동 로드)
    
    Returns:
        ZoneProfile 인스턴스
    
    Raises:
        KeyError: 프로파일 없음
    
    Examples:
        >>> profile = get_profile('strict_uniform')
        >>> profile.zone_weights
        (1.0, 1.0, 1.0, 1.0)
    """
    if profiles is None:
        profiles = load_zone_profiles_with_fallback()
    
    if name not in profiles:
        available = list(profiles.keys())
        raise KeyError(
            f"Zone profile '{name}' not found. "
            f"Available profiles: {available}"
        )
    
    return profiles[name]


def list_profiles(profiles: Optional[Dict[str, 'ZoneProfile']] = None) -> List[str]:
    """
    사용 가능한 프로파일 이름 목록 반환.
    
    Args:
        profiles: 프로파일 dict (None이면 자동 로드)
    
    Returns:
        프로파일 이름 리스트
    
    Examples:
        >>> list_profiles()
        ['strict_uniform', 'advisory_z2_focus', ...]
    """
    if profiles is None:
        profiles = load_zone_profiles_with_fallback()
    
    return list(profiles.keys())
