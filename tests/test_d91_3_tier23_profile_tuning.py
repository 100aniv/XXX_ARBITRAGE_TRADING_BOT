#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D91-3: Tier2/3 Zone Profile Tuning 테스트

v2 YAML SOL/DOGE 매핑, loader_v2 헬퍼, Runner 로직 검증.

Author: arbitrage-lite project
Date: 2025-12-11 (D91-3)
"""

import sys
from pathlib import Path

import pytest

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.config.zone_profiles_loader_v2 import (
    load_zone_profiles_v2_with_fallback,
    select_profile_for_symbol,
    get_zone_boundaries_for_symbol,
    validate_symbol_profile_consistency,
    get_zone_profiles_v2_yaml_path,
)
from arbitrage.domain.entry_bps_profile import ZONE_PROFILES


class TestD91_3SymbolMappingExtension:
    """D91-3: SOL/DOGE 심볼 매핑 확장 검증"""
    
    def test_sol_symbol_mapping_loads(self):
        """SOL 심볼 매핑이 정상 로드되는지 확인"""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        assert "symbol_mappings" in v2_data
        assert "SOL" in v2_data["symbol_mappings"]
        
        sol_mapping = v2_data["symbol_mappings"]["SOL"]
        assert sol_mapping["market"] == "upbit"
        assert sol_mapping["liquidity_tier"] == "tier2"
        assert "default_profiles" in sol_mapping
        assert "strict" in sol_mapping["default_profiles"]
        assert "advisory" in sol_mapping["default_profiles"]
    
    def test_doge_symbol_mapping_loads(self):
        """DOGE 심볼 매핑이 정상 로드되는지 확인"""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        assert "DOGE" in v2_data["symbol_mappings"]
        
        doge_mapping = v2_data["symbol_mappings"]["DOGE"]
        assert doge_mapping["market"] == "upbit"
        assert doge_mapping["liquidity_tier"] == "tier3"
        assert doge_mapping["spread_characteristics"] == "wide"
    
    def test_sol_strict_profile_selection(self):
        """SOL strict 모드 프로파일 선택"""
        profile = select_profile_for_symbol(symbol="SOL", market="upbit", mode="strict")
        
        assert profile is not None
        assert profile.name == "strict_uniform_light"
        assert len(profile.zone_weights) == 4
    
    def test_sol_advisory_profile_selection(self):
        """SOL advisory 모드 프로파일 선택"""
        profile = select_profile_for_symbol(symbol="SOL", market="upbit", mode="advisory")
        
        assert profile is not None
        assert profile.name == "advisory_z3_focus"  # D91-3 튜닝 대상
    
    def test_doge_strict_profile_selection(self):
        """DOGE strict 모드 프로파일 선택"""
        profile = select_profile_for_symbol(symbol="DOGE", market="upbit", mode="strict")
        
        assert profile is not None
        assert profile.name == "strict_uniform_light"
    
    def test_doge_advisory_profile_selection(self):
        """DOGE advisory 모드 프로파일 선택"""
        profile = select_profile_for_symbol(symbol="DOGE", market="upbit", mode="advisory")
        
        assert profile is not None
        assert profile.name == "advisory_z2_conservative"  # Tier3 보수적 전략
    
    def test_sol_zone_boundaries(self):
        """SOL Zone boundaries가 Tier2 기준으로 확대되었는지 확인"""
        boundaries = get_zone_boundaries_for_symbol(symbol="SOL", market="upbit")
        
        assert boundaries is not None
        assert len(boundaries) == 4
        
        # Tier2 기준: [5.0, 8.0], [8.0, 15.0], [15.0, 25.0], [25.0, 30.0]
        assert boundaries[0] == (5.0, 8.0)
        assert boundaries[1] == (8.0, 15.0)
        assert boundaries[2] == (15.0, 25.0)
        assert boundaries[3] == (25.0, 30.0)
    
    def test_doge_zone_boundaries(self):
        """DOGE Zone boundaries가 Tier3 기준으로 더 확대되었는지 확인"""
        boundaries = get_zone_boundaries_for_symbol(symbol="DOGE", market="upbit")
        
        assert boundaries is not None
        assert len(boundaries) == 4
        
        # Tier3 기준: [5.0, 10.0], [10.0, 20.0], [20.0, 30.0], [30.0, 40.0]
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
        """마켓 불일치 시 검증 실패"""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        is_valid, error_msg = validate_symbol_profile_consistency(
            symbol="SOL",
            market="binance",  # SOL은 upbit으로 매핑됨
            mode="strict",
            v2_data=v2_data,
            zone_profiles_dict=ZONE_PROFILES
        )
        
        assert not is_valid
        assert "market mismatch" in error_msg


class TestD91_3RunnerExecutionPlan:
    """D91-3: Runner 실행 계획 생성 로직 테스트"""
    
    def test_generate_execution_plan_single_symbol_strict(self):
        """단일 심볼 strict 모드 실행 계획"""
        from scripts.run_d91_3_tier23_profile_tuning import generate_execution_plan
        
        plan = generate_execution_plan(symbols=["XRP"], mode="strict", duration_minutes=20)
        
        assert len(plan) == 1  # XRP strict 후보 1개
        assert plan[0]["symbol"] == "XRP"
        assert plan[0]["mode"] == "strict"
        assert plan[0]["profile_name"] == "strict_uniform_light"
    
    def test_generate_execution_plan_single_symbol_advisory(self):
        """단일 심볼 advisory 모드 실행 계획"""
        from scripts.run_d91_3_tier23_profile_tuning import generate_execution_plan
        
        plan = generate_execution_plan(symbols=["XRP"], mode="advisory", duration_minutes=20)
        
        assert len(plan) == 2  # XRP advisory 후보 2개
        assert all(p["symbol"] == "XRP" for p in plan)
        assert all(p["mode"] == "advisory" for p in plan)
        
        profile_names = [p["profile_name"] for p in plan]
        assert "advisory_z2_focus" in profile_names
        assert "advisory_z3_focus" in profile_names
    
    def test_generate_execution_plan_multi_symbol_both(self):
        """다중 심볼 both 모드 실행 계획"""
        from scripts.run_d91_3_tier23_profile_tuning import generate_execution_plan
        
        plan = generate_execution_plan(symbols=["XRP", "SOL"], mode="both", duration_minutes=20)
        
        # XRP: 1 strict + 2 advisory = 3
        # SOL: 1 strict + 2 advisory = 3
        # Total: 6
        assert len(plan) == 6
        
        xrp_plans = [p for p in plan if p["symbol"] == "XRP"]
        sol_plans = [p for p in plan if p["symbol"] == "SOL"]
        
        assert len(xrp_plans) == 3
        assert len(sol_plans) == 3
    
    def test_generate_execution_plan_doge_advisory_candidates(self):
        """DOGE advisory 후보군 확인 (Tier3 보수적 전략)"""
        from scripts.run_d91_3_tier23_profile_tuning import generate_execution_plan
        
        plan = generate_execution_plan(symbols=["DOGE"], mode="advisory", duration_minutes=20)
        
        assert len(plan) == 2  # advisory_z2_conservative, advisory_z2_balanced
        
        profile_names = [p["profile_name"] for p in plan]
        assert "advisory_z2_conservative" in profile_names
        assert "advisory_z2_balanced" in profile_names


class TestD91_3BackwardCompatibility:
    """D91-3: 하위 호환성 검증 (기존 BTC/ETH/XRP 영향 없음)"""
    
    def test_btc_profile_unchanged(self):
        """BTC 프로파일 선택이 D91-2와 동일"""
        btc_strict = select_profile_for_symbol(symbol="BTC", market="upbit", mode="strict")
        btc_advisory = select_profile_for_symbol(symbol="BTC", market="upbit", mode="advisory")
        
        assert btc_strict.name == "strict_uniform"
        assert btc_advisory.name == "advisory_z2_focus"
    
    def test_eth_profile_unchanged(self):
        """ETH 프로파일 선택이 D91-2와 동일"""
        eth_strict = select_profile_for_symbol(symbol="ETH", market="upbit", mode="strict")
        eth_advisory = select_profile_for_symbol(symbol="ETH", market="upbit", mode="advisory")
        
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
        # XRP advisory는 D91-3 튜닝 대상이지만 기본값은 동일
        xrp_advisory = select_profile_for_symbol(
            symbol="XRP", market="upbit", mode="advisory",
            profiles=v2_data["profiles"], symbol_mappings=v2_data["symbol_mappings"]
        )
        assert xrp_advisory.name == "advisory_z2_focus"


class TestD91_3Integration:
    """D91-3: 통합 테스트 (v2 YAML + loader_v2 + Runner)"""
    
    def test_all_tier2_tier3_symbols_loadable(self):
        """Tier2/3 모든 심볼이 정상 로드됨"""
        v2_data = load_zone_profiles_v2_with_fallback()
        symbols = ["XRP", "SOL", "DOGE"]
        
        for symbol in symbols:
            strict_profile = select_profile_for_symbol(
                symbol=symbol, market="upbit", mode="strict",
                profiles=v2_data["profiles"], symbol_mappings=v2_data["symbol_mappings"]
            )
            advisory_profile = select_profile_for_symbol(
                symbol=symbol, market="upbit", mode="advisory",
                profiles=v2_data["profiles"], symbol_mappings=v2_data["symbol_mappings"]
            )
            
            assert strict_profile is not None, f"{symbol} strict profile not found"
            assert advisory_profile is not None, f"{symbol} advisory profile not found"
            
            # ZONE_PROFILES에 존재하는지 확인
            assert strict_profile.name in ZONE_PROFILES
            assert advisory_profile.name in ZONE_PROFILES
    
    def test_all_profiles_referenced_in_v2_exist_in_zone_profiles(self):
        """v2 YAML에서 참조하는 모든 프로파일이 ZONE_PROFILES에 존재"""
        v2_data = load_zone_profiles_v2_with_fallback()
        symbol_mappings = v2_data.get("symbol_mappings", {})
        
        for symbol, mapping in symbol_mappings.items():
            default_profiles = mapping.get("default_profiles", {})
            
            for mode, profile_name in default_profiles.items():
                assert profile_name in ZONE_PROFILES, (
                    f"Profile '{profile_name}' (referenced by {symbol} {mode}) "
                    f"not found in ZONE_PROFILES"
                )
    
    def test_runner_candidate_profiles_all_exist(self):
        """Runner 후보군의 모든 프로파일이 ZONE_PROFILES에 존재"""
        from scripts.run_d91_3_tier23_profile_tuning import SYMBOL_PROFILE_CANDIDATES
        
        for symbol, modes in SYMBOL_PROFILE_CANDIDATES.items():
            for mode, profiles in modes.items():
                for profile_name in profiles:
                    assert profile_name in ZONE_PROFILES, (
                        f"Candidate profile '{profile_name}' ({symbol} {mode}) "
                        f"not found in ZONE_PROFILES"
                    )
