#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92-7-3: ZoneProfile SSOT 단위 테스트

AC-1 검증:
- DEFAULT SSOT 자동 로드
- zone_profiles_loaded.path != null
- sha256 해시 기록
- profiles_applied 심볼별 요약
"""

import os
import pytest
from pathlib import Path
from arbitrage.core.zone_profile_applier import ZoneProfileApplier


def test_default_zone_profile_ssot_exists():
    """D92-7-4: DEFAULT SSOT 파일 존재 확인"""
    default_ssot = "config/arbitrage/zone_profiles_v2.yaml"
    yaml_path = Path(default_ssot)
    
    assert yaml_path.exists(), f"Default SSOT file not found: {default_ssot}"


def test_zone_profile_applier_from_file():
    """D92-7-4: ZoneProfileApplier.from_file() 로드 테스트"""
    default_ssot = "config/arbitrage/zone_profiles_v2.yaml"
    applier = ZoneProfileApplier.from_file(default_ssot)
    
    assert applier is not None, "Applier should not be None"
    assert len(applier.symbol_profiles) > 0, "Should have loaded symbols"
    assert hasattr(applier, '_yaml_path'), "_yaml_path attribute should exist"
    assert applier._yaml_path == default_ssot, "_yaml_path should match input path"


def test_zone_profile_symbol_mappings_normalization():
    """D92-7-4: symbol_mappings 정규화 테스트"""
    default_ssot = "config/arbitrage/zone_profiles_v2.yaml"
    applier = ZoneProfileApplier.from_file(default_ssot)
    
    # symbol_mappings에서 로드된 심볼 확인
    test_symbols = ["BTC", "ETH", "XRP", "SOL"]
    for symbol in test_symbols:
        if applier.has_profile(symbol):
            profile = applier.symbol_profiles[symbol]
            
            # 필수 필드 검증
            assert "profile_name" in profile, f"{symbol}: profile_name missing"
            assert "profile_weights" in profile, f"{symbol}: profile_weights missing"
            assert "zone_boundaries" in profile, f"{symbol}: zone_boundaries missing"
            assert "threshold_bps" in profile, f"{symbol}: threshold_bps missing"
            assert profile["threshold_bps"] is not None, f"{symbol}: threshold_bps should not be None"


def test_zone_profile_threshold_bps_fallback():
    """D92-7-4: threshold_bps=None 시 fallback 동작 확인"""
    default_ssot = "config/arbitrage/zone_profiles_v2.yaml"
    applier = ZoneProfileApplier.from_file(default_ssot)
    
    # fallback_threshold_count 확인
    assert hasattr(applier, '_fallback_threshold_count'), "_fallback_threshold_count should exist"
    
    # 모든 심볼의 threshold_bps가 None이 아닌지 확인
    for symbol, profile in applier.symbol_profiles.items():
        assert profile["threshold_bps"] is not None, f"{symbol}: threshold_bps should not be None after normalization"
        assert isinstance(profile["threshold_bps"], (int, float)), f"{symbol}: threshold_bps should be numeric"
        assert profile["threshold_bps"] > 0, f"{symbol}: threshold_bps should be positive"


def test_zone_profile_invalid_file_fail_fast():
    """D92-7-4: 잘못된 파일 입력 시 FAIL-FAST 예외"""
    with pytest.raises(FileNotFoundError):
        ZoneProfileApplier.from_file("nonexistent/path/zone_profiles.yaml")


def test_zone_profile_missing_zone_boundaries_fail_fast():
    """D92-7-4: zone_boundaries 누락 시 FAIL-FAST 예외"""
    import tempfile
    import yaml
    
    # 잘못된 YAML 생성 (zone_boundaries 누락)
    bad_data = {
        "symbol_mappings": {
            "BTC": {
                "market": "upbit",
                "default_profiles": {"advisory": "advisory_z2_focus"},
                # zone_boundaries 누락!
            }
        },
        "profiles": {
            "advisory_z2_focus": {
                "weights": [0.5, 3.0, 1.5, 0.5]
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(bad_data, f)
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="Missing zone_boundaries"):
            ZoneProfileApplier.from_file(temp_path)
    finally:
        Path(temp_path).unlink()


def test_zone_profile_metadata_collection():
    """D92-7-4: Zone Profile 메타데이터 수집 테스트"""
    import hashlib

    default_ssot = "config/arbitrage/zone_profiles_v2.yaml"
    yaml_path = Path(default_ssot)

    # SHA256 계산
    with open(yaml_path, 'rb') as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    assert len(sha256) == 64, "SHA256 should be 64 characters"

    # mtime 확인
    mtime = yaml_path.stat().st_mtime
    assert mtime > 0, "mtime should be positive"

    # ZoneProfileApplier 로드
    applier = ZoneProfileApplier.from_file(default_ssot)

    # profiles_applied 확인
    test_symbols = ["BTC", "ETH", "XRP"]
    profiles_applied = {}

    for symbol in test_symbols:
        if applier.has_profile(symbol):
            threshold = applier.get_entry_threshold(symbol)
            threshold_bps = threshold * 10000.0
            profile = applier.symbol_profiles[symbol]
            profile_name = profile["profile_name"]

            profiles_applied[symbol] = {
                "profile_name": profile_name,
                "entry_threshold_bps": round(threshold_bps, 2),
            }

    # 최소 1개 이상의 심볼이 적용되어야 함
    assert len(profiles_applied) > 0, "At least one symbol should have zone profile applied"


def test_zone_profile_kpi_structure():
    """D92-7-4: KPI zone_profiles_loaded 구조 검증"""
    import hashlib

    default_ssot = "config/arbitrage/zone_profiles_v2.yaml"
    yaml_path = Path(default_ssot)

    with open(yaml_path, 'rb') as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    mtime = yaml_path.stat().st_mtime
    applier = ZoneProfileApplier.from_file(default_ssot)

    profiles_applied = {}
    for symbol in ["BTC", "ETH"]:
        if applier.has_profile(symbol):
            threshold = applier.get_entry_threshold(symbol)
            profile = applier.symbol_profiles[symbol]
            profiles_applied[symbol] = {
                "profile_name": profile["profile_name"],
                "entry_threshold_bps": round(threshold * 10000.0, 2),
            }

    # KPI 구조
    zone_profiles_loaded = {
        "path": str(yaml_path),
        "sha256": sha256,
        "mtime": mtime,
        "profiles_applied": profiles_applied,
    }

    # 검증
    assert zone_profiles_loaded["path"] is not None, "path should not be null"
    assert zone_profiles_loaded["sha256"] is not None, "sha256 should not be null"
    assert zone_profiles_loaded["mtime"] is not None, "mtime should not be null"
    assert len(zone_profiles_loaded["profiles_applied"]) > 0, "profiles_applied should not be empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
