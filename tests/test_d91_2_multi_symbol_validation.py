#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D91-2: Multi-Symbol Zone Distribution Validation Tests

D91-2 Runner 및 심볼별 Zone Profile 선택 로직 검증.

Author: arbitrage-lite project
Date: 2025-12-11 (D91-2)
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from arbitrage.config.zone_profiles_loader_v2 import (
    load_zone_profiles_v2_with_fallback,
    select_profile_for_symbol,
    get_zone_boundaries_for_symbol,
)


class TestD91_2_SymbolProfileSelection:
    """심볼별 Zone Profile 선택 로직 테스트."""
    
    def test_btc_strict_selects_strict_uniform(self):
        """BTC (Upbit, strict) → strict_uniform 선택 확인."""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        profile = select_profile_for_symbol(
            symbol="BTC",
            market="upbit",
            mode="strict",
            profiles=v2_data["profiles"],
            symbol_mappings=v2_data["symbol_mappings"]
        )
        
        assert profile.name == "strict_uniform"
        assert profile.zone_weights == (1.0, 1.0, 1.0, 1.0)
    
    def test_btc_advisory_selects_advisory_z2_focus(self):
        """BTC (Upbit, advisory) → advisory_z2_focus 선택 확인."""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        profile = select_profile_for_symbol(
            symbol="BTC",
            market="upbit",
            mode="advisory",
            profiles=v2_data["profiles"],
            symbol_mappings=v2_data["symbol_mappings"]
        )
        
        assert profile.name == "advisory_z2_focus"
        assert profile.zone_weights == (0.5, 3.0, 1.5, 0.5)
    
    def test_xrp_strict_selects_strict_uniform_light(self):
        """XRP (Upbit, strict) → strict_uniform_light 선택 확인."""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        profile = select_profile_for_symbol(
            symbol="XRP",
            market="upbit",
            mode="strict",
            profiles=v2_data["profiles"],
            symbol_mappings=v2_data["symbol_mappings"]
        )
        
        assert profile.name == "strict_uniform_light"
        assert profile.zone_weights == (1.2, 1.0, 1.0, 0.5)
    
    def test_xrp_advisory_selects_advisory_z2_focus(self):
        """XRP (Upbit, advisory) → advisory_z2_focus 선택 확인 (D91-1 정의)."""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        profile = select_profile_for_symbol(
            symbol="XRP",
            market="upbit",
            mode="advisory",
            profiles=v2_data["profiles"],
            symbol_mappings=v2_data["symbol_mappings"]
        )
        
        # D91-1에서 XRP advisory는 advisory_z2_focus로 정의됨
        assert profile.name == "advisory_z2_focus"


class TestD91_2_ZoneBoundaries:
    """심볼별 Zone Boundaries 테스트."""
    
    def test_btc_zone_boundaries_tier1(self):
        """BTC Zone Boundaries (Tier1 기본값)."""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        boundaries = get_zone_boundaries_for_symbol(
            symbol="BTC",
            market="upbit",
            symbol_mappings=v2_data["symbol_mappings"]
        )
        
        expected = [
            (5.0, 7.0),
            (7.0, 12.0),
            (12.0, 20.0),
            (20.0, 25.0)
        ]
        
        assert boundaries == expected
    
    def test_xrp_zone_boundaries_tier2_expanded(self):
        """XRP Zone Boundaries (Tier2 확대)."""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        boundaries = get_zone_boundaries_for_symbol(
            symbol="XRP",
            market="upbit",
            symbol_mappings=v2_data["symbol_mappings"]
        )
        
        expected = [
            (5.0, 8.0),
            (8.0, 15.0),
            (15.0, 25.0),
            (25.0, 30.0)
        ]
        
        assert boundaries == expected


class TestD91_2_BackwardCompatibility:
    """D91-2와 D90/D91-1 하위 호환성 테스트."""
    
    def test_v2_loader_returns_v2_source(self):
        """v2 YAML 존재 시 source='v2' 반환."""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        # v2 파일이 존재하면 source는 'v2'여야 함
        assert v2_data["source"] in ["v2", "v1", "fallback"]
        
        # v2 파일이 실제로 있으므로 v2여야 함
        assert v2_data["source"] == "v2"
    
    def test_all_required_profiles_exist(self):
        """필수 프로파일 4개 존재 확인."""
        v2_data = load_zone_profiles_v2_with_fallback()
        profiles = v2_data["profiles"]
        
        required = [
            "strict_uniform",
            "advisory_z2_focus",
            "strict_uniform_light",
            "advisory_z3_focus"
        ]
        
        for profile_name in required:
            assert profile_name in profiles
    
    def test_d90_baseline_profiles_accessible(self):
        """D90 프로덕션 baseline 프로파일 접근 가능."""
        v2_data = load_zone_profiles_v2_with_fallback()
        profiles = v2_data["profiles"]
        
        # D90-5에서 승인된 프로덕션 baseline
        assert "strict_uniform" in profiles
        assert "advisory_z2_focus" in profiles
        
        # 가중치 확인
        assert profiles["strict_uniform"].zone_weights == (1.0, 1.0, 1.0, 1.0)
        assert profiles["advisory_z2_focus"].zone_weights == (0.5, 3.0, 1.5, 0.5)


class TestD91_2_Integration:
    """D91-2 통합 테스트 (Runner 로직 검증)."""
    
    def test_symbol_profile_market_consistency(self):
        """심볼/마켓/모드 조합이 일관성 있게 동작하는지 확인."""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        # BTC/ETH는 동일한 Tier1 전략 사용
        btc_profile = select_profile_for_symbol(
            symbol="BTC",
            market="upbit",
            mode="strict",
            profiles=v2_data["profiles"],
            symbol_mappings=v2_data["symbol_mappings"]
        )
        
        eth_profile = select_profile_for_symbol(
            symbol="ETH",
            market="upbit",
            mode="strict",
            profiles=v2_data["profiles"],
            symbol_mappings=v2_data["symbol_mappings"]
        )
        
        assert btc_profile.name == eth_profile.name == "strict_uniform"
    
    def test_tier_differentiation(self):
        """Tier1과 Tier2가 다른 프로파일을 사용하는지 확인."""
        v2_data = load_zone_profiles_v2_with_fallback()
        
        # Tier1 (BTC)
        tier1_profile = select_profile_for_symbol(
            symbol="BTC",
            market="upbit",
            mode="strict",
            profiles=v2_data["profiles"],
            symbol_mappings=v2_data["symbol_mappings"]
        )
        
        # Tier2 (XRP)
        tier2_profile = select_profile_for_symbol(
            symbol="XRP",
            market="upbit",
            mode="strict",
            profiles=v2_data["profiles"],
            symbol_mappings=v2_data["symbol_mappings"]
        )
        
        # Tier2는 Z4 가중치가 축소된 프로파일 사용
        assert tier1_profile.name == "strict_uniform"
        assert tier2_profile.name == "strict_uniform_light"
        
        # Z4 가중치 비교 (Tier1: 1.0, Tier2: 0.5)
        assert tier1_profile.zone_weights[3] == 1.0
        assert tier2_profile.zone_weights[3] == 0.5


def test_summary():
    """테스트 요약 출력."""
    print("\n" + "="*60)
    print("D91-2 Multi-Symbol Validation Tests Summary")
    print("="*60)
    print("1. Symbol Profile Selection: 4 tests")
    print("2. Zone Boundaries: 2 tests")
    print("3. Backward Compatibility: 3 tests")
    print("4. Integration: 2 tests")
    print("="*60)
    print("Total: 11 tests")
    print("="*60)
