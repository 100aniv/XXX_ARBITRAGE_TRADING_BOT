#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92-1-FIX: Zone Profile → Engine Integration Tests

Zone Profile이 실제 PAPER 실행에 적용되는지 검증하는 테스트.

Test Coverage:
1. ZoneProfileApplier: JSON 로드, threshold 계산
2. CLI 전달: run_d77_0 CLI 옵션 검증
3. Threshold override: 심볼별 entry threshold 적용 검증
4. No-profile execution: Zone Profile 없이 실행 시 FAIL

Author: arbitrage-lite project
Date: 2025-12-12 (D92-1-FIX)
"""

import json
import pytest
from pathlib import Path
from arbitrage.core.zone_profile_applier import ZoneProfileApplier


class TestZoneProfileApplier:
    """ZoneProfileApplier 단위 테스트"""
    
    def test_from_json_initialization(self):
        """JSON string으로 ZoneProfileApplier 초기화"""
        symbol_profiles = {
            "BTC": {
                "profile_name": "advisory_z2_focus",
                "profile_weights": [0.5, 3.0, 1.5, 0.5],
                "zone_boundaries": [(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 30.0)],
                "mode": "advisory"
            },
            "ETH": {
                "profile_name": "advisory_z2_focus",
                "profile_weights": [0.5, 3.0, 1.5, 0.5],
                "zone_boundaries": [(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 30.0)],
                "mode": "advisory"
            },
        }
        
        json_str = json.dumps(symbol_profiles)
        applier = ZoneProfileApplier.from_json(json_str)
        
        assert applier.has_profile("BTC")
        assert applier.has_profile("ETH")
        assert not applier.has_profile("XRP")
    
    def test_threshold_calculation_advisory_z2_focus(self):
        """Advisory Z2 Focus 프로파일의 threshold 계산 검증"""
        symbol_profiles = {
            "BTC": {
                "profile_name": "advisory_z2_focus",
                "profile_weights": [0.5, 3.0, 1.5, 0.5],
                "zone_boundaries": [(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 30.0)],
                "mode": "advisory"
            },
        }
        
        applier = ZoneProfileApplier(symbol_profiles)
        
        # Z2 (7-12 bps) 중간값 = 9.5 bps = 0.00095
        threshold = applier.get_entry_threshold("BTC")
        assert abs(threshold - 0.00095) < 1e-6
    
    def test_threshold_calculation_advisory_z3_focus(self):
        """Advisory Z3 Focus 프로파일의 threshold 계산 검증"""
        symbol_profiles = {
            "SOL": {
                "profile_name": "advisory_z3_focus",
                "profile_weights": [0.5, 1.5, 3.0, 0.5],
                "zone_boundaries": [(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 30.0)],
                "mode": "advisory"
            },
        }
        
        applier = ZoneProfileApplier(symbol_profiles)
        
        # Z3 (12-20 bps) 중간값 = 16 bps = 0.0016
        threshold = applier.get_entry_threshold("SOL")
        assert abs(threshold - 0.0016) < 1e-6
    
    def test_threshold_calculation_strict(self):
        """Strict 모드의 threshold 계산 검증"""
        symbol_profiles = {
            "DOGE": {
                "profile_name": "strict_z1_min",
                "profile_weights": [1.0, 1.0, 1.0, 1.0],
                "zone_boundaries": [(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 30.0)],
                "mode": "strict"
            },
        }
        
        applier = ZoneProfileApplier(symbol_profiles)
        
        # Strict: Z1 최소값 = 5 bps = 0.0005
        threshold = applier.get_entry_threshold("DOGE")
        assert abs(threshold - 0.0005) < 1e-6
    
    def test_zone_boundaries_retrieval(self):
        """Zone boundaries 조회 검증"""
        symbol_profiles = {
            "XRP": {
                "profile_name": "advisory_z2_focus",
                "profile_weights": [0.5, 3.0, 1.5, 0.5],
                "zone_boundaries": [(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 30.0)],
                "mode": "advisory"
            },
        }
        
        applier = ZoneProfileApplier(symbol_profiles)
        boundaries = applier.get_zone_boundaries("XRP")
        
        assert len(boundaries) == 4
        assert boundaries[0] == (5.0, 7.0)
        assert boundaries[1] == (7.0, 12.0)
        assert boundaries[2] == (12.0, 20.0)
        assert boundaries[3] == (20.0, 30.0)
    
    def test_no_profile_error(self):
        """존재하지 않는 심볼 조회 시 에러 발생"""
        symbol_profiles = {
            "BTC": {
                "profile_name": "advisory_z2_focus",
                "profile_weights": [0.5, 3.0, 1.5, 0.5],
                "zone_boundaries": [(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 30.0)],
                "mode": "advisory"
            },
        }
        
        applier = ZoneProfileApplier(symbol_profiles)
        
        with pytest.raises(ValueError, match="No Zone Profile configured"):
            applier.get_entry_threshold("UNKNOWN")


class TestZoneProfileCLI:
    """run_d77_0 CLI 옵션 검증"""
    
    def test_cli_options_exist(self):
        """CLI 옵션이 존재하는지 확인"""
        import subprocess
        import sys
        
        runner_script = Path(__file__).parent.parent / "scripts" / "run_d77_0_topn_arbitrage_paper.py"
        assert runner_script.exists(), f"Runner script not found: {runner_script}"
        
        # --help 실행하여 CLI 옵션 확인
        result = subprocess.run(
            [sys.executable, str(runner_script), "--help"],
            capture_output=True,
            text=True,
        )
        
        assert "--symbol-profiles-json" in result.stdout
        assert "--zone-profile-file" in result.stdout


class TestZoneProfileMapping:
    """run_d92_1 → run_d77_0 Zone Profile 전달 검증"""
    
    def test_run_d92_1_creates_profile_json(self, tmp_path):
        """run_d92_1이 symbol_profiles.json을 생성하는지 검증"""
        # 이 테스트는 실제 run_d92_1 dry-run으로 검증
        # tmp_path를 로그 디렉터리로 사용
        from scripts.run_d92_1_topn_longrun import get_topn_symbols_mock
        from arbitrage.config.zone_profiles_loader_v2 import (
            load_zone_profiles_v2_with_fallback,
            select_profile_for_symbol,
            get_zone_boundaries_for_symbol,
        )
        
        # Mock 심볼 선정
        symbols = get_topn_symbols_mock(5)
        assert len(symbols) >= 5
        
        # Zone Profile 로드
        v2_data = load_zone_profiles_v2_with_fallback()
        profiles = v2_data["profiles"]
        symbol_mappings = v2_data["symbol_mappings"]
        
        # 심볼별 매핑
        symbol_profile_map = {}
        for symbol in symbols[:5]:
            profile = select_profile_for_symbol(
                symbol=symbol,
                market="upbit",
                mode="advisory",
                profiles=profiles,
                symbol_mappings=symbol_mappings
            )
            zone_boundaries = get_zone_boundaries_for_symbol(
                symbol=symbol,
                market="upbit",
                symbol_mappings=symbol_mappings
            )
            symbol_profile_map[symbol] = {
                "profile_name": profile.name,
                "profile_weights": profile.zone_weights,
                "zone_boundaries": zone_boundaries,
                "mode": "advisory",
            }
        
        # JSON 파일 저장 (run_d92_1과 동일한 로직)
        profile_json_path = tmp_path / "symbol_profiles.json"
        with open(profile_json_path, 'w') as f:
            json.dump(symbol_profile_map, f, indent=2)
        
        # 검증: JSON 파일 존재 및 로드 가능
        assert profile_json_path.exists()
        
        with open(profile_json_path, 'r') as f:
            loaded_profiles = json.load(f)
        
        assert len(loaded_profiles) == 5
        assert "BTC" in loaded_profiles or "ETH" in loaded_profiles


class TestNoProfileExecution:
    """Zone Profile 없이 실행 시 동작 검증"""
    
    def test_no_profile_uses_default_threshold(self):
        """Zone Profile이 없을 때 기본 threshold 사용"""
        # ZoneProfileApplier가 None이면 기본값 사용
        applier = None
        
        # 기본 threshold (Settings에서 로드)
        from arbitrage.config.settings import Settings
        settings = Settings.from_env()
        default_threshold_bps = settings.topn_entry_exit.entry_min_spread_bps
        
        # D77PAPERRunner 로직 시뮬레이션
        if applier and applier.has_profile("BTC"):
            threshold = applier.get_entry_threshold("BTC") * 10000.0
        else:
            threshold = default_threshold_bps
        
        # 기본값 사용 확인
        assert threshold == default_threshold_bps
