#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92-1: TopN Multi-Symbol LONGRUN Tests

TopN 멀티 심볼 1h LONGRUN Runner의 구조 및 Zone Profile 매핑 검증.

Author: arbitrage-lite project
Date: 2025-12-12 (D92-1)
"""

import json
import sys
from pathlib import Path

import pytest

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_d92_1_topn_longrun import (
    BEST_PROFILES,
    get_topn_symbols_mock,
    parse_zone_distribution,
)
from arbitrage.config.zone_profiles_loader_v2 import (
    load_zone_profiles_v2_with_fallback,
    select_profile_for_symbol,
    get_zone_boundaries_for_symbol,
)


class TestD92_1_TopNLongrun:
    """D92-1 TopN LONGRUN 테스트"""
    
    def test_best_profiles_defined(self):
        """D91-3 Best Profile이 5개 핵심 심볼에 대해 정의되어 있는지 확인"""
        required_symbols = ["BTC", "ETH", "XRP", "SOL", "DOGE"]
        
        for symbol in required_symbols:
            assert symbol in BEST_PROFILES, f"Missing Best Profile for {symbol}"
            
            profile_def = BEST_PROFILES[symbol]
            assert "mode" in profile_def, f"Missing 'mode' for {symbol}"
            assert "profile" in profile_def, f"Missing 'profile' for {symbol}"
            assert profile_def["mode"] in ["advisory", "strict"], f"Invalid mode for {symbol}"
    
    def test_topn_symbols_mock_returns_correct_count(self):
        """TopN Mock이 요청한 개수만큼 심볼을 반환하는지 확인"""
        for top_n in [5, 10, 15]:
            symbols = get_topn_symbols_mock(top_n)
            assert len(symbols) == top_n, f"Expected {top_n} symbols, got {len(symbols)}"
    
    def test_topn_symbols_includes_core_symbols(self):
        """TopN Mock이 5개 핵심 심볼을 포함하는지 확인"""
        core_symbols = ["BTC", "ETH", "XRP", "SOL", "DOGE"]
        
        symbols = get_topn_symbols_mock(10)
        
        for symbol in core_symbols:
            assert symbol in symbols, f"Core symbol {symbol} not in TopN"
    
    def test_zone_profile_mapping_for_core_symbols(self):
        """핵심 5개 심볼에 대해 Zone Profile 매핑이 정상 작동하는지 확인"""
        v2_data = load_zone_profiles_v2_with_fallback()
        profiles = v2_data["profiles"]
        symbol_mappings = v2_data["symbol_mappings"]
        
        core_symbols = ["BTC", "ETH", "XRP", "SOL", "DOGE"]
        market = "upbit"
        
        for symbol in core_symbols:
            # Best Profile 정의 가져오기
            best = BEST_PROFILES[symbol]
            mode = best["mode"]
            expected_profile_name = best["profile"]
            
            # v2 로더로 프로파일 선택
            profile = select_profile_for_symbol(
                symbol=symbol,
                market=market,
                mode=mode,
                profiles=profiles,
                symbol_mappings=symbol_mappings
            )
            
            assert profile is not None, f"Profile not found for {symbol}"
            assert profile.name == expected_profile_name, \
                f"Profile mismatch for {symbol}: expected {expected_profile_name}, got {profile.name}"
    
    def test_zone_boundaries_for_core_symbols(self):
        """핵심 5개 심볼에 대해 Zone Boundaries가 정의되어 있는지 확인"""
        v2_data = load_zone_profiles_v2_with_fallback()
        symbol_mappings = v2_data["symbol_mappings"]
        
        core_symbols = ["BTC", "ETH", "XRP", "SOL", "DOGE"]
        market = "upbit"
        
        for symbol in core_symbols:
            boundaries = get_zone_boundaries_for_symbol(
                symbol=symbol,
                market=market,
                symbol_mappings=symbol_mappings
            )
            
            assert boundaries is not None, f"Zone boundaries not found for {symbol}"
            assert len(boundaries) == 4, f"Expected 4 zones for {symbol}, got {len(boundaries)}"
            
            # Zone boundaries 검증 (오름차순, 겹치지 않음)
            for i in range(len(boundaries)):
                mn, mx = boundaries[i]
                assert mn < mx, f"Invalid zone {i} for {symbol}: {mn} >= {mx}"
                
                if i > 0:
                    prev_max = boundaries[i-1][1]
                    assert mn == prev_max, \
                        f"Zone gap for {symbol}: Zone{i-1} ends at {prev_max}, Zone{i} starts at {mn}"
    
    def test_tier1_symbols_have_tier1_profiles(self):
        """Tier1 심볼(BTC/ETH)이 Tier1 프로파일을 사용하는지 확인"""
        tier1_symbols = ["BTC", "ETH"]
        expected_profile = "advisory_z2_focus"
        
        for symbol in tier1_symbols:
            best = BEST_PROFILES[symbol]
            assert best["profile"] == expected_profile, \
                f"Tier1 symbol {symbol} should use {expected_profile}, got {best['profile']}"
    
    def test_tier2_symbols_have_tier2_profiles(self):
        """Tier2 심볼(XRP/SOL)이 Tier2 프로파일을 사용하는지 확인"""
        tier2_symbols = {
            "XRP": "advisory_z2_focus",  # D91-3 Best
            "SOL": "advisory_z3_focus",  # D91-3 Best
        }
        
        for symbol, expected_profile in tier2_symbols.items():
            best = BEST_PROFILES[symbol]
            assert best["profile"] == expected_profile, \
                f"Tier2 symbol {symbol} should use {expected_profile}, got {best['profile']}"
    
    def test_tier3_symbols_have_tier3_profiles(self):
        """Tier3 심볼(DOGE)이 Tier3 프로파일을 사용하는지 확인"""
        symbol = "DOGE"
        expected_profile = "advisory_z2_balanced"  # D91-3 Best
        
        best = BEST_PROFILES[symbol]
        assert best["profile"] == expected_profile, \
            f"Tier3 symbol {symbol} should use {expected_profile}, got {best['profile']}"
    
    def test_parse_zone_distribution_empty_file(self):
        """Zone 분포 파싱: 파일이 없을 때 빈 결과 반환"""
        fake_path = Path("nonexistent_file.jsonl")
        calib_path = Path("logs/d86-1/calibration_20251207_123906.json")
        
        result = parse_zone_distribution(fake_path, calib_path)
        
        assert result["total_buys"] == 0
        assert result["zone_counts"] == [0, 0, 0, 0]
        assert result["zone_percentages"] == [0.0, 0.0, 0.0, 0.0]
    
    def test_all_profiles_exist_in_v2_yaml(self):
        """D92-1에서 사용하는 모든 프로파일이 v2 YAML에 정의되어 있는지 확인"""
        v2_data = load_zone_profiles_v2_with_fallback()
        profiles = v2_data["profiles"]
        
        required_profiles = set()
        for symbol, best in BEST_PROFILES.items():
            required_profiles.add(best["profile"])
        
        for profile_name in required_profiles:
            assert profile_name in profiles, \
                f"Profile {profile_name} not found in v2 YAML"
    
    def test_symbol_mappings_exist_for_core_symbols(self):
        """핵심 5개 심볼이 v2 YAML symbol_mappings에 정의되어 있는지 확인"""
        v2_data = load_zone_profiles_v2_with_fallback()
        symbol_mappings = v2_data["symbol_mappings"]
        
        core_symbols = ["BTC", "ETH", "XRP", "SOL", "DOGE"]
        
        for symbol in core_symbols:
            assert symbol in symbol_mappings, \
                f"Symbol {symbol} not found in v2 YAML symbol_mappings"
            
            mapping = symbol_mappings[symbol]
            assert "default_profiles" in mapping, \
                f"Missing default_profiles for {symbol}"
            assert "zone_boundaries" in mapping, \
                f"Missing zone_boundaries for {symbol}"
            assert "liquidity_tier" in mapping, \
                f"Missing liquidity_tier for {symbol}"


class TestD92_1_Integration:
    """D92-1 통합 테스트 (Dry-run 기반)"""
    
    def test_dry_run_execution(self):
        """Dry-run 모드로 실행 시 에러 없이 완료되는지 확인"""
        from scripts.run_d92_1_topn_longrun import run_topn_longrun
        
        calibration_path = Path("logs/d86-1/calibration_20251207_123906.json")
        
        result = run_topn_longrun(
            top_n=5,
            duration_minutes=60,
            mode="advisory",
            calibration_path=calibration_path,
            market="upbit",
            dry_run=True,
        )
        
        assert result["status"] == "dry_run"
        assert "run_id" in result
        assert "symbols" in result
        assert len(result["symbols"]) == 5
        assert "symbol_profile_map" in result
        
        # 핵심 5개 심볼 포함 확인
        core_symbols = ["BTC", "ETH", "XRP", "SOL", "DOGE"]
        for symbol in core_symbols:
            assert symbol in result["symbols"]
    
    def test_dry_run_profile_mapping(self):
        """Dry-run에서 심볼별 프로파일 매핑이 올바른지 확인"""
        from scripts.run_d92_1_topn_longrun import run_topn_longrun
        
        calibration_path = Path("logs/d86-1/calibration_20251207_123906.json")
        
        result = run_topn_longrun(
            top_n=5,
            duration_minutes=60,
            mode="advisory",
            calibration_path=calibration_path,
            market="upbit",
            dry_run=True,
        )
        
        assert result["status"] == "dry_run"
        
        symbol_profile_map = result["symbol_profile_map"]
        
        # 각 심볼에 대한 프로파일 매핑 검증
        for symbol in ["BTC", "ETH", "XRP", "SOL", "DOGE"]:
            assert symbol in symbol_profile_map, f"Symbol {symbol} not in profile map"
            
            profile_info = symbol_profile_map[symbol]
            assert "profile_name" in profile_info
            assert "profile_weights" in profile_info
            assert "zone_boundaries" in profile_info
            assert "mode" in profile_info
            
            # Best Profile과 일치 확인
            expected_profile = BEST_PROFILES[symbol]["profile"]
            assert profile_info["profile_name"] == expected_profile, \
                f"Profile mismatch for {symbol}: expected {expected_profile}, got {profile_info['profile_name']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
