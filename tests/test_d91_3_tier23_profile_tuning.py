"""
D91-3: Tier2/3 Zone Profile Tuning Tests

Tests for XRP/SOL/DOGE symbol mappings, profile selection,
zone boundaries, validation helpers, and runner execution plans.
"""

import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arbitrage.config.zone_profiles_loader_v2 import (
    load_zone_profiles_v2_with_fallback,
    select_profile_for_symbol,
    get_zone_boundaries_for_symbol,
    validate_symbol_profile_consistency,
)
from arbitrage.domain.entry_bps_profile import ZONE_PROFILES


class TestD91_3SymbolMappingExtension:
    """D91-3: SOL/DOGE 심볼 매핑 확장 테스트"""
    
    def test_sol_symbol_mapping_loads(self):
        """SOL 심볼 매핑이 v2 YAML에서 정상 로드됨"""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        assert "SOL" in v2_data["symbol_mappings"]
        
        sol_mapping = v2_data["symbol_mappings"]["SOL"]
        assert sol_mapping["market"] == "upbit"
        assert sol_mapping["liquidity_tier"] == "tier2"
        assert sol_mapping["spread_characteristics"] == "moderate"
    
    def test_doge_symbol_mapping_loads(self):
        """DOGE 심볼 매핑이 v2 YAML에서 정상 로드됨"""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        assert "DOGE" in v2_data["symbol_mappings"]
        
        doge_mapping = v2_data["symbol_mappings"]["DOGE"]
        assert doge_mapping["market"] == "upbit"
        assert doge_mapping["liquidity_tier"] == "tier3"
        assert doge_mapping["spread_characteristics"] == "wide"
    
    def test_sol_strict_profile_selection(self):
        """SOL strict 모드 프로파일 선택"""
        v2_data = load_zone_profiles_v2_with_fallback()
        profile = select_profile_for_symbol(
            symbol="SOL", market="upbit", mode="strict",
            profiles=v2_data["profiles"], symbol_mappings=v2_data["symbol_mappings"]
        )
        
        assert profile is not None
        assert profile.name == "strict_uniform_light"
        assert len(profile.zone_weights) == 4
    
    def test_sol_advisory_profile_selection(self):
        """SOL advisory 모드 프로파일 선택"""
        v2_data = load_zone_profiles_v2_with_fallback()
        profile = select_profile_for_symbol(
            symbol="SOL", market="upbit", mode="advisory",
            profiles=v2_data["profiles"], symbol_mappings=v2_data["symbol_mappings"]
        )
        
        assert profile is not None
        assert profile.name == "advisory_z3_focus"
    
    def test_doge_strict_profile_selection(self):
        """DOGE strict 모드 프로파일 선택"""
        v2_data = load_zone_profiles_v2_with_fallback()
        profile = select_profile_for_symbol(
            symbol="DOGE", market="upbit", mode="strict",
            profiles=v2_data["profiles"], symbol_mappings=v2_data["symbol_mappings"]
        )
        
        assert profile is not None
        assert profile.name == "strict_uniform_light"
    
    def test_doge_advisory_profile_selection(self):
        """DOGE advisory 모드 프로파일 선택"""
        v2_data = load_zone_profiles_v2_with_fallback()
        profile = select_profile_for_symbol(
            symbol="DOGE", market="upbit", mode="advisory",
            profiles=v2_data["profiles"], symbol_mappings=v2_data["symbol_mappings"]
        )
        
        assert profile is not None
        assert profile.name == "advisory_z2_conservative"
    
    def test_sol_zone_boundaries(self):
        """SOL Zone boundaries가 Tier2 기준으로 확대되었는지 확인"""
        v2_data = load_zone_profiles_v2_with_fallback()
        boundaries = get_zone_boundaries_for_symbol(
            symbol="SOL", market="upbit",
            symbol_mappings=v2_data["symbol_mappings"]
        )
        
        assert boundaries is not None
        assert len(boundaries) == 4
        
        assert boundaries[0] == (5.0, 8.0)
        assert boundaries[1] == (8.0, 15.0)
        assert boundaries[2] == (15.0, 25.0)
        assert boundaries[3] == (25.0, 30.0)
    
    def test_doge_zone_boundaries(self):
        """DOGE Zone boundaries가 Tier3 기준으로 더 확대되었는지 확인"""
        v2_data = load_zone_profiles_v2_with_fallback()
        boundaries = get_zone_boundaries_for_symbol(
            symbol="DOGE", market="upbit",
            symbol_mappings=v2_data["symbol_mappings"]
        )
        
        assert boundaries is not None
        assert len(boundaries) == 4
        
        assert boundaries[0] == (5.0, 10.0)
        assert boundaries[1] == (10.0, 20.0)
        assert boundaries[2] == (20.0, 30.0)
        assert boundaries[3] == (30.0, 40.0)


class TestD91_3ProfileConsistencyValidation:
    """D91-3: 프로파일 일관성 검증 헬퍼 테스트"""
    
    def test_validate_sol_strict_consistency(self):
        """SOL strict 모드 일관성 검증"""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        is_valid, error_msg = validate_symbol_profile_consistency(
            symbol="SOL",
            market="upbit",
            mode="strict",
            v2_data=v2_data,
            zone_profiles_dict=ZONE_PROFILES
        )
        
        assert is_valid, f"Validation failed: {error_msg}"
    
    def test_validate_sol_advisory_consistency(self):
        """SOL advisory 모드 일관성 검증"""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        is_valid, error_msg = validate_symbol_profile_consistency(
            symbol="SOL",
            market="upbit",
            mode="advisory",
            v2_data=v2_data,
            zone_profiles_dict=ZONE_PROFILES
        )
        
        assert is_valid, f"Validation failed: {error_msg}"
    
    def test_validate_doge_strict_consistency(self):
        """DOGE strict 모드 일관성 검증"""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        is_valid, error_msg = validate_symbol_profile_consistency(
            symbol="DOGE",
            market="upbit",
            mode="strict",
            v2_data=v2_data,
            zone_profiles_dict=ZONE_PROFILES
        )
        
        assert is_valid, f"Validation failed: {error_msg}"
    
    def test_validate_doge_advisory_consistency(self):
        """DOGE advisory 모드 일관성 검증"""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        is_valid, error_msg = validate_symbol_profile_consistency(
            symbol="DOGE",
            market="upbit",
            mode="advisory",
            v2_data=v2_data,
            zone_profiles_dict=ZONE_PROFILES
        )
        
        assert is_valid, f"Validation failed: {error_msg}"
    
    def test_validate_invalid_symbol(self):
        """존재하지 않는 심볼에 대한 검증 실패"""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        is_valid, error_msg = validate_symbol_profile_consistency(
            symbol="INVALID",
            market="upbit",
            mode="strict",
            v2_data=v2_data,
            zone_profiles_dict=ZONE_PROFILES
        )
        
        assert not is_valid
        assert "not found in symbol_mappings" in error_msg
    
    def test_validate_market_mismatch(self):
        """마켓 불일치에 대한 검증 실패"""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        is_valid, error_msg = validate_symbol_profile_consistency(
            symbol="SOL",
            market="binance",
            mode="strict",
            v2_data=v2_data,
            zone_profiles_dict=ZONE_PROFILES
        )
        
        assert not is_valid
        assert "market mismatch" in error_msg.lower()


class TestD91_3RunnerExecutionPlan:
    """D91-3: Runner 실행 계획 생성 로직 테스트"""
    
    def test_generate_execution_plan_single_symbol_strict(self):
        """단일 심볼 strict 모드 실행 계획"""
        from scripts.run_d91_3_tier23_profile_tuning import generate_execution_plan
        
        plan = generate_execution_plan(symbols=["SOL"], mode="strict")
        
        assert len(plan) == 1
        assert plan[0]["symbol"] == "SOL"
        assert plan[0]["mode"] == "strict"
        assert plan[0]["profile_name"] == "strict_uniform_light"
    
    def test_generate_execution_plan_single_symbol_advisory(self):
        """단일 심볼 advisory 모드 실행 계획"""
        from scripts.run_d91_3_tier23_profile_tuning import generate_execution_plan
        
        plan = generate_execution_plan(symbols=["SOL"], mode="advisory")
        
        assert len(plan) >= 2
        assert all(p["symbol"] == "SOL" for p in plan)
        assert all(p["mode"] == "advisory" for p in plan)
        profile_names = [p["profile_name"] for p in plan]
        assert "advisory_z2_focus" in profile_names or "advisory_z3_focus" in profile_names
    
    def test_generate_execution_plan_multi_symbol_both(self):
        """멀티 심볼 both 모드 실행 계획"""
        from scripts.run_d91_3_tier23_profile_tuning import generate_execution_plan
        
        plan = generate_execution_plan(symbols=["XRP", "SOL"], mode="both")
        
        assert len(plan) >= 6
        symbols = [p["symbol"] for p in plan]
        assert "XRP" in symbols
        assert "SOL" in symbols
    
    def test_generate_execution_plan_doge_advisory_candidates(self):
        """DOGE advisory 후보 프로파일 확인"""
        from scripts.run_d91_3_tier23_profile_tuning import generate_execution_plan
        
        plan = generate_execution_plan(symbols=["DOGE"], mode="advisory", duration_minutes=20)
        
        profile_names = [p["profile_name"] for p in plan]
        assert "advisory_z2_conservative" in profile_names or "advisory_z2_balanced" in profile_names


class TestD91_3BackwardCompatibility:
    """D91-3: 하위 호환성 검증"""
    
    def test_btc_profile_unchanged(self):
        """BTC 프로파일 선택이 D91-2와 동일"""
        v2_data = load_zone_profiles_v2_with_fallback()
        btc_strict = select_profile_for_symbol(
            symbol="BTC", market="upbit", mode="strict",
            profiles=v2_data["profiles"], symbol_mappings=v2_data["symbol_mappings"]
        )
        btc_advisory = select_profile_for_symbol(
            symbol="BTC", market="upbit", mode="advisory",
            profiles=v2_data["profiles"], symbol_mappings=v2_data["symbol_mappings"]
        )
        
        assert btc_strict.name == "strict_uniform"
        assert btc_advisory.name == "advisory_z2_focus"
    
    def test_eth_profile_unchanged(self):
        """ETH 프로파일 선택이 D91-2와 동일"""
        v2_data = load_zone_profiles_v2_with_fallback()
        eth_strict = select_profile_for_symbol(
            symbol="ETH", market="upbit", mode="strict",
            profiles=v2_data["profiles"], symbol_mappings=v2_data["symbol_mappings"]
        )
        eth_advisory = select_profile_for_symbol(
            symbol="ETH", market="upbit", mode="advisory",
            profiles=v2_data["profiles"], symbol_mappings=v2_data["symbol_mappings"]
        )
        
        assert eth_strict.name == "strict_uniform"
        assert eth_advisory.name == "advisory_z2_focus"
    
    def test_xrp_profile_unchanged(self):
        """XRP 프로파일 선택이 D91-2와 동일"""
        v2_data = load_zone_profiles_v2_with_fallback()
        xrp_strict = select_profile_for_symbol(
            symbol="XRP", market="upbit", mode="strict",
            profiles=v2_data["profiles"], symbol_mappings=v2_data["symbol_mappings"]
        )
        
        assert xrp_strict.name == "strict_uniform_light"
        xrp_advisory = select_profile_for_symbol(
            symbol="XRP", market="upbit", mode="advisory",
            profiles=v2_data["profiles"], symbol_mappings=v2_data["symbol_mappings"]
        )
        assert xrp_advisory.name == "advisory_z2_focus"


class TestD91_3Integration:
    """D91-3: 통합 테스트"""
    
    def test_all_tier2_tier3_symbols_loadable(self):
        """Tier2/3 모든 심볼이 정상 로드됨"""
        v2_data = load_zone_profiles_v2_with_fallback()
        symbols = ["XRP", "SOL", "DOGE"]
        
        for symbol in symbols:
            assert symbol in v2_data["symbol_mappings"]
            mapping = v2_data["symbol_mappings"][symbol]
            assert "market" in mapping
            assert "liquidity_tier" in mapping
            assert "zone_boundaries" in mapping
            assert "default_profiles" in mapping
    
    def test_all_profiles_referenced_in_v2_exist_in_zone_profiles(self):
        """v2 YAML에서 참조하는 모든 프로파일이 ZONE_PROFILES에 존재"""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        for symbol, mapping in v2_data["symbol_mappings"].items():
            if "default_profiles" in mapping:
                for mode, profile_name in mapping["default_profiles"].items():
                    assert profile_name in ZONE_PROFILES, \
                        f"{symbol} {mode} references {profile_name} which doesn't exist in ZONE_PROFILES"
    
    def test_runner_candidate_profiles_all_exist(self):
        """Runner에서 사용하는 후보 프로파일이 모두 존재"""
        from scripts.run_d91_3_tier23_profile_tuning import PROFILE_CANDIDATES
        
        for symbol, candidates in PROFILE_CANDIDATES.items():
            for mode, profile_list in candidates.items():
                for profile_name in profile_list:
                    assert profile_name in ZONE_PROFILES, \
                        f"Runner candidate {profile_name} for {symbol} {mode} doesn't exist in ZONE_PROFILES"
