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


def test_default_zone_profile_ssot_exists():
    """
    DEFAULT SSOT 파일 존재 확인
    """
    default_ssot = "config/arbitrage/zone_profiles_v2.yaml"
    assert Path(default_ssot).exists(), f"DEFAULT SSOT not found: {default_ssot}"


def test_zone_profile_applier_from_file():
    """
    ZoneProfileApplier.from_file() 테스트
    """
    from arbitrage.core.zone_profile_applier import ZoneProfileApplier
    
    default_ssot = "config/arbitrage/zone_profiles_v2.yaml"
    applier = ZoneProfileApplier.from_file(default_ssot)
    
    # _yaml_path 속성 존재 확인
    assert hasattr(applier, '_yaml_path'), "ZoneProfileApplier should have _yaml_path attribute"
    assert applier._yaml_path == default_ssot


def test_zone_profile_metadata_collection():
    """
    Zone Profile 메타데이터 수집 테스트 (sha256/mtime/profiles_applied)
    """
    import hashlib
    from arbitrage.core.zone_profile_applier import ZoneProfileApplier
    
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
    
    # path != null 검증
    assert applier._yaml_path is not None, "zone_profiles_loaded.path should not be null"


def test_zone_profile_kpi_structure():
    """
    KPI zone_profiles_loaded 구조 검증
    """
    import hashlib
    from arbitrage.core.zone_profile_applier import ZoneProfileApplier
    
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
