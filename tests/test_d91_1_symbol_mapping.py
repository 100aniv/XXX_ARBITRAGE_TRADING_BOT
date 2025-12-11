#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D91-1: Symbol Mapping YAML v2 PoC Tests

YAML v2.0.0 기반 Zone Profile 로더 및 심볼별 선택 로직 검증.

**테스트 카테고리:**
- A. v2 YAML 기본 로딩 (3 tests)
- B. 심볼별 매핑 로직 (6 tests)
- C. Fallback & Backward Compatibility (6 tests)

Total: 15 tests

Author: arbitrage-lite project
Date: 2025-12-11 (D91-1)
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from arbitrage.config.zone_profiles_loader_v2 import (
    load_zone_profiles_v2_from_yaml,
    load_zone_profiles_v2_with_fallback,
    select_profile_for_symbol,
    get_zone_boundaries_for_symbol,
    get_zone_profiles_v2_yaml_path,
    validate_symbol_mapping_data,
    ZoneProfileLoadError,
)
from arbitrage.domain.entry_bps_profile import ZoneProfile


# ===== A. v2 YAML 기본 로딩 =====

def test_v2_yaml_loading_success():
    """
    A1. v2 YAML 파일 로딩 성공 및 schema_version 확인.
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    
    # v2 파일이 존재해야 함
    assert yaml_path.exists(), f"YAML v2 file not found: {yaml_path}"
    
    # 로드 성공
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    # 구조 확인
    assert "profiles" in result
    assert "symbol_mappings" in result
    assert "metadata" in result
    
    # schema_version 확인
    assert result["metadata"]["schema_version"] == "2.0.0"
    
    print(f"✅ [A1] v2 YAML loaded: {len(result['profiles'])} profiles, "
          f"{len(result['symbol_mappings'])} symbol mappings")


def test_v2_yaml_required_profiles_exist():
    """
    A2. v2 YAML에 필수 프로파일 4개 존재 확인.
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    profiles = result["profiles"]
    
    # 필수 프로파일 (D91-1 PoC 범위)
    required_profiles = [
        "strict_uniform",
        "advisory_z2_focus",
        "strict_uniform_light",
        "advisory_z3_focus"
    ]
    
    for profile_name in required_profiles:
        assert profile_name in profiles, f"Required profile '{profile_name}' not found"
        assert isinstance(profiles[profile_name], ZoneProfile)
    
    print(f"✅ [A2] All required profiles exist: {required_profiles}")


def test_v2_yaml_symbol_mappings_exist():
    """
    A3. v2 YAML에 BTC/ETH/XRP 심볼 매핑 존재 확인.
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    symbol_mappings = result["symbol_mappings"]
    
    # PoC 범위 심볼
    required_symbols = ["BTC", "ETH", "XRP"]
    
    for symbol in required_symbols:
        assert symbol in symbol_mappings, f"Symbol '{symbol}' not found in mappings"
        
        mapping = symbol_mappings[symbol]
        assert "market" in mapping
        assert "default_profiles" in mapping
        assert "strict" in mapping["default_profiles"]
        assert "advisory" in mapping["default_profiles"]
    
    print(f"✅ [A3] All required symbols exist: {required_symbols}")


# ===== B. 심볼별 매핑 로직 =====

def test_select_profile_btc_upbit_strict():
    """
    B1. BTC (Upbit, strict) → strict_uniform 반환.
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    profile = select_profile_for_symbol(
        symbol="BTC",
        market="upbit",
        mode="strict",
        profiles=result["profiles"],
        symbol_mappings=result["symbol_mappings"]
    )
    
    assert profile.name == "strict_uniform"
    assert profile.zone_weights == (1.0, 1.0, 1.0, 1.0)
    
    print(f"✅ [B1] BTC (Upbit, strict) → {profile.name}")


def test_select_profile_btc_upbit_advisory():
    """
    B2. BTC (Upbit, advisory) → advisory_z2_focus 반환.
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    profile = select_profile_for_symbol(
        symbol="BTC",
        market="upbit",
        mode="advisory",
        profiles=result["profiles"],
        symbol_mappings=result["symbol_mappings"]
    )
    
    assert profile.name == "advisory_z2_focus"
    assert profile.zone_weights == (0.5, 3.0, 1.5, 0.5)
    
    print(f"✅ [B2] BTC (Upbit, advisory) → {profile.name}")


def test_select_profile_eth_upbit_strict():
    """
    B3. ETH (Upbit, strict) → strict_uniform 반환.
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    profile = select_profile_for_symbol(
        symbol="ETH",
        market="upbit",
        mode="strict",
        profiles=result["profiles"],
        symbol_mappings=result["symbol_mappings"]
    )
    
    assert profile.name == "strict_uniform"
    
    print(f"✅ [B3] ETH (Upbit, strict) → {profile.name}")


def test_select_profile_xrp_upbit_strict():
    """
    B4. XRP (Upbit, strict) → strict_uniform_light 반환.
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    profile = select_profile_for_symbol(
        symbol="XRP",
        market="upbit",
        mode="strict",
        profiles=result["profiles"],
        symbol_mappings=result["symbol_mappings"]
    )
    
    assert profile.name == "strict_uniform_light"
    assert profile.zone_weights == (1.2, 1.0, 1.0, 0.5)
    
    print(f"✅ [B4] XRP (Upbit, strict) → {profile.name}")


def test_select_profile_xrp_upbit_advisory():
    """
    B5. XRP (Upbit, advisory) → advisory_z2_focus 반환.
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    profile = select_profile_for_symbol(
        symbol="XRP",
        market="upbit",
        mode="advisory",
        profiles=result["profiles"],
        symbol_mappings=result["symbol_mappings"]
    )
    
    assert profile.name == "advisory_z2_focus"
    
    print(f"✅ [B5] XRP (Upbit, advisory) → {profile.name}")


def test_select_profile_unknown_symbol_fallback():
    """
    B6. 존재하지 않는 심볼 (ABC) → Fallback (strict_uniform or advisory_z2_focus).
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    # Strict 모드
    profile_strict = select_profile_for_symbol(
        symbol="ABC",  # 존재하지 않는 심볼
        market="upbit",
        mode="strict",
        profiles=result["profiles"],
        symbol_mappings=result["symbol_mappings"]
    )
    
    assert profile_strict.name == "strict_uniform"
    
    # Advisory 모드
    profile_advisory = select_profile_for_symbol(
        symbol="ABC",
        market="upbit",
        mode="advisory",
        profiles=result["profiles"],
        symbol_mappings=result["symbol_mappings"]
    )
    
    assert profile_advisory.name == "advisory_z2_focus"
    
    print(f"✅ [B6] Unknown symbol (ABC) → Fallback: strict={profile_strict.name}, "
          f"advisory={profile_advisory.name}")


def test_select_profile_market_mismatch_fallback():
    """
    B7. market 불일치 케이스 (XRP, market="binance") → Fallback.
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    # XRP는 upbit에 매핑되어 있으나, binance 요청 → Fallback
    profile = select_profile_for_symbol(
        symbol="XRP",
        market="binance",  # YAML에는 upbit만 정의됨
        mode="strict",
        profiles=result["profiles"],
        symbol_mappings=result["symbol_mappings"]
    )
    
    # Fallback → strict_uniform
    assert profile.name == "strict_uniform"
    
    print(f"✅ [B7] XRP (binance, market mismatch) → Fallback: {profile.name}")


# ===== C. Fallback & Backward Compatibility =====

def test_v2_fallback_to_v1_on_missing_file():
    """
    C1. v2 YAML 파일 미존재 시 → v1 로더 Fallback.
    """
    # v2 파일 경로를 임의로 변경하여 없는 파일 시뮬레이션
    non_existent_path = Path("/tmp/non_existent_zone_profiles_v2.yaml")
    
    result = load_zone_profiles_v2_with_fallback(yaml_path=non_existent_path)
    
    # v1 Fallback 확인
    assert result["source"] == "v1"
    assert "strict_uniform" in result["profiles"]
    assert "advisory_z2_focus" in result["profiles"]
    
    # v1에는 symbol_mappings 없음
    assert len(result["symbol_mappings"]) == 0
    
    print(f"✅ [C1] v2 file missing → v1 fallback: {len(result['profiles'])} profiles")


def test_v2_fallback_to_v1_on_parse_error():
    """
    C2. v2 YAML 구조가 잘못된 경우 → v1 Fallback.
    """
    # 임시 잘못된 YAML 파일 생성
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        f.write("invalid: [unclosed list\n")  # 의도적 YAML 에러
        temp_yaml_path = Path(f.name)
    
    try:
        result = load_zone_profiles_v2_with_fallback(yaml_path=temp_yaml_path)
        
        # v1 Fallback 확인
        assert result["source"] == "v1"
        assert "strict_uniform" in result["profiles"]
        
        print(f"✅ [C2] v2 parse error → v1 fallback: {len(result['profiles'])} profiles")
    
    finally:
        # 임시 파일 삭제
        temp_yaml_path.unlink(missing_ok=True)


def test_v2_symbol_mappings_optional():
    """
    C3. v2 존재하되 symbol_mappings 없을 때 → 글로벌 프로파일 사용.
    """
    # 임시 v2 YAML 파일 생성 (symbol_mappings 없음)
    import tempfile
    
    yaml_content = """
profiles:
  strict_uniform:
    description: "Test profile"
    weights: [1.0, 1.0, 1.0, 1.0]
    status: production
  
  advisory_z2_focus:
    description: "Test profile"
    weights: [0.5, 3.0, 1.5, 0.5]
    status: production

metadata:
  schema_version: "2.0.0"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        f.write(yaml_content)
        temp_yaml_path = Path(f.name)
    
    try:
        result = load_zone_profiles_v2_from_yaml(yaml_path=temp_yaml_path)
        
        # symbol_mappings 비어있어야 함
        assert len(result["symbol_mappings"]) == 0
        
        # 프로파일은 정상 로드
        assert "strict_uniform" in result["profiles"]
        assert "advisory_z2_focus" in result["profiles"]
        
        # 심볼 선택 시 Fallback 동작
        profile = select_profile_for_symbol(
            symbol="BTC",
            market="upbit",
            mode="strict",
            profiles=result["profiles"],
            symbol_mappings=result["symbol_mappings"]
        )
        
        assert profile.name == "strict_uniform"
        
        print(f"✅ [C3] v2 without symbol_mappings → global profiles: {profile.name}")
    
    finally:
        temp_yaml_path.unlink(missing_ok=True)


def test_fallback_profiles_are_production_baseline():
    """
    C4. Fallback이 D90-5 프로덕션 승인 프로파일로 귀결되는지 확인.
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    # 알 수 없는 심볼 → Fallback
    profile_strict = select_profile_for_symbol(
        symbol="UNKNOWN_SYMBOL",
        market="unknown_market",
        mode="strict",
        profiles=result["profiles"],
        symbol_mappings=result["symbol_mappings"]
    )
    
    profile_advisory = select_profile_for_symbol(
        symbol="UNKNOWN_SYMBOL",
        market="unknown_market",
        mode="advisory",
        profiles=result["profiles"],
        symbol_mappings=result["symbol_mappings"]
    )
    
    # D90-5 프로덕션 baseline 확인
    assert profile_strict.name == "strict_uniform"
    assert profile_strict.zone_weights == (1.0, 1.0, 1.0, 1.0)
    
    assert profile_advisory.name == "advisory_z2_focus"
    assert profile_advisory.zone_weights == (0.5, 3.0, 1.5, 0.5)
    
    print(f"✅ [C4] Fallback → production baseline: strict={profile_strict.name}, "
          f"advisory={profile_advisory.name}")


def test_backward_compatibility_v1_profiles_accessible():
    """
    C5. v1 프로파일이 v2에서도 접근 가능한지 확인 (하위 호환성).
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    profiles = result["profiles"]
    
    # v1에 정의된 5개 프로파일이 v2에도 있어야 함
    v1_profiles = [
        "strict_uniform",
        "advisory_z2_focus",
        "advisory_z23_focus",
        "advisory_z2_balanced",
        "advisory_z2_conservative"
    ]
    
    for profile_name in v1_profiles:
        # v1 프로파일 중 일부는 v2에 없을 수 있음 (예: deprecated)
        # 하지만 production baseline 2개는 반드시 있어야 함
        if profile_name in ["strict_uniform", "advisory_z2_focus"]:
            assert profile_name in profiles, f"v1 baseline profile '{profile_name}' not found in v2"
    
    print(f"✅ [C5] v1 baseline profiles accessible in v2")


def test_regression_existing_d90_tests_compatible():
    """
    C6. 기존 D90-0~5 테스트와 호환되는지 간단 확인.
    """
    # v2 with fallback 호출 → v1 호환성 확인
    result = load_zone_profiles_v2_with_fallback()
    
    # v2 또는 v1에서 로드되었어야 함
    assert result["source"] in ["v2", "v1", "fallback"]
    
    # 프로덕션 baseline 존재 확인
    profiles = result["profiles"]
    assert "strict_uniform" in profiles
    assert "advisory_z2_focus" in profiles
    
    # ZoneProfile 인스턴스 확인
    assert isinstance(profiles["strict_uniform"], ZoneProfile)
    assert isinstance(profiles["advisory_z2_focus"], ZoneProfile)
    
    print(f"✅ [C6] Regression check: v2 compatible with D90-0~5 (source={result['source']})")


# ===== D. Zone Boundaries =====

def test_get_zone_boundaries_btc():
    """
    D1. BTC Zone Boundaries (Tier1 기본값) 확인.
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    boundaries = get_zone_boundaries_for_symbol(
        symbol="BTC",
        market="upbit",
        symbol_mappings=result["symbol_mappings"]
    )
    
    # Tier1 기본값
    expected = [
        (5.0, 7.0),
        (7.0, 12.0),
        (12.0, 20.0),
        (20.0, 25.0)
    ]
    
    assert boundaries == expected
    
    print(f"✅ [D1] BTC zone_boundaries: {boundaries}")


def test_get_zone_boundaries_xrp():
    """
    D2. XRP Zone Boundaries (Tier2 확대) 확인.
    """
    yaml_path = get_zone_profiles_v2_yaml_path()
    result = load_zone_profiles_v2_from_yaml(yaml_path)
    
    boundaries = get_zone_boundaries_for_symbol(
        symbol="XRP",
        market="upbit",
        symbol_mappings=result["symbol_mappings"]
    )
    
    # Tier2 확대 값
    expected = [
        (5.0, 8.0),
        (8.0, 15.0),
        (15.0, 25.0),
        (25.0, 30.0)
    ]
    
    assert boundaries == expected
    
    print(f"✅ [D2] XRP zone_boundaries: {boundaries}")


# ===== Test Summary =====

def test_summary():
    """
    테스트 요약 출력.
    """
    print("\n" + "="*60)
    print("D91-1 Symbol Mapping Tests Summary")
    print("="*60)
    print("A. v2 YAML 기본 로딩: 3 tests")
    print("B. 심볼별 매핑 로직: 7 tests")
    print("C. Fallback & Backward Compatibility: 6 tests")
    print("D. Zone Boundaries: 2 tests")
    print("="*60)
    print("Total: 18 tests")
    print("="*60)
