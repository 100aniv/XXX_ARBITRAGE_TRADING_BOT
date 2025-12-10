#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D90-4: Zone Profile YAML Externalization - Unit Tests

YAML 기반 Zone Profile 로더 및 하위 호환성 테스트.

**테스트 범위:**
1. YAML 로드 정상 동작
2. Fallback 동작 (YAML 없음/실패 시)
3. 프로파일 검증 (weights 길이/타입/음수 체크)
4. 하위 호환성 (ZONE_PROFILES dict-like 접근)
5. 기존 D90-0~3 테스트와 동일한 결과

Author: arbitrage-lite project
Date: 2025-12-10 (D90-4)
"""

import pytest
from pathlib import Path
from arbitrage.domain.entry_bps_profile import (
    ZoneProfile,
    ZONE_PROFILES,
    load_zone_profiles,
    get_zone_profile,
)
from arbitrage.config.zone_profiles_loader import (
    load_zone_profiles_from_yaml,
    load_zone_profiles_with_fallback,
    validate_profile_data,
    ZoneProfileLoadError,
    get_zone_profiles_yaml_path,
)


class TestZoneProfileYAMLLoad:
    """YAML 파일 로드 테스트."""
    
    def test_yaml_file_exists(self):
        """YAML 파일이 존재하는지 확인."""
        yaml_path = get_zone_profiles_yaml_path()
        assert yaml_path.exists(), f"Zone profiles YAML not found: {yaml_path}"
    
    def test_load_from_yaml_success(self):
        """YAML에서 프로파일 로드 성공."""
        profiles = load_zone_profiles_from_yaml()
        
        # 최소 프로파일 확인
        assert "strict_uniform" in profiles
        assert "advisory_z2_focus" in profiles
        
        # 프로파일 타입 확인
        for name, profile in profiles.items():
            assert isinstance(profile, ZoneProfile)
            assert profile.name == name
            assert len(profile.zone_weights) == 4
    
    def test_load_strict_uniform_weights(self):
        """strict_uniform 프로파일 가중치 확인."""
        profiles = load_zone_profiles_from_yaml()
        profile = profiles["strict_uniform"]
        
        assert profile.zone_weights == (1.0, 1.0, 1.0, 1.0)
        assert "uniform" in profile.description.lower()
    
    def test_load_advisory_z2_focus_weights(self):
        """advisory_z2_focus 프로파일 가중치 확인."""
        profiles = load_zone_profiles_from_yaml()
        profile = profiles["advisory_z2_focus"]
        
        assert profile.zone_weights == (0.5, 3.0, 1.5, 0.5)
        assert "z2" in profile.description.lower()
    
    def test_load_all_d90_3_profiles(self):
        """D90-3에서 사용한 모든 프로파일 로드 확인."""
        profiles = load_zone_profiles_from_yaml()
        
        # D90-3 Sweep에 사용된 프로파일
        d90_3_profiles = [
            "advisory_z2_focus",
            "advisory_z2_balanced",
            "advisory_z23_focus",
            "advisory_z2_conservative",
        ]
        
        for name in d90_3_profiles:
            assert name in profiles, f"D90-3 profile '{name}' missing in YAML"
            assert len(profiles[name].zone_weights) == 4


class TestZoneProfileValidation:
    """프로파일 데이터 검증 테스트."""
    
    def test_validate_valid_profile(self):
        """유효한 프로파일 검증 통과."""
        data = {
            "description": "Test profile",
            "weights": [1.0, 2.0, 3.0, 4.0],
        }
        
        # 예외 없이 통과해야 함
        validate_profile_data("test", data)
    
    def test_validate_missing_weights(self):
        """weights 필드 없음 → 예외."""
        data = {"description": "Test profile"}
        
        with pytest.raises(ZoneProfileLoadError, match="missing 'weights'"):
            validate_profile_data("test", data)
    
    def test_validate_wrong_length_weights(self):
        """weights 길이 4가 아님 → 예외."""
        data = {
            "description": "Test profile",
            "weights": [1.0, 2.0, 3.0],  # 길이 3
        }
        
        with pytest.raises(ZoneProfileLoadError, match="exactly 4 elements"):
            validate_profile_data("test", data)
    
    def test_validate_negative_weights(self):
        """weights에 음수 포함 → 예외."""
        data = {
            "description": "Test profile",
            "weights": [1.0, -2.0, 3.0, 4.0],
        }
        
        with pytest.raises(ZoneProfileLoadError, match="non-negative"):
            validate_profile_data("test", data)
    
    def test_validate_zero_sum_weights(self):
        """weights 합이 0 → 예외."""
        data = {
            "description": "Test profile",
            "weights": [0.0, 0.0, 0.0, 0.0],
        }
        
        with pytest.raises(ZoneProfileLoadError, match="sum cannot be zero"):
            validate_profile_data("test", data)
    
    def test_validate_non_numeric_weights(self):
        """weights에 비숫자 포함 → 예외."""
        data = {
            "description": "Test profile",
            "weights": [1.0, "invalid", 3.0, 4.0],
        }
        
        with pytest.raises(ZoneProfileLoadError, match="must be numeric"):
            validate_profile_data("test", data)


class TestZoneProfileFallback:
    """Fallback 동작 테스트."""
    
    def test_fallback_on_missing_file(self):
        """YAML 파일 없음 → Fallback으로 최소 프로파일 로드."""
        # 존재하지 않는 파일 경로
        fake_path = Path("/nonexistent/zone_profiles.yaml")
        
        profiles = load_zone_profiles_with_fallback(yaml_path=fake_path)
        
        # Fallback은 최소 2개 프로파일 보장
        assert "strict_uniform" in profiles
        assert "advisory_z2_focus" in profiles
        assert len(profiles) >= 2
    
    def test_fallback_profiles_valid(self):
        """Fallback 프로파일이 유효한지 확인."""
        fake_path = Path("/nonexistent/zone_profiles.yaml")
        profiles = load_zone_profiles_with_fallback(yaml_path=fake_path)
        
        # strict_uniform
        assert profiles["strict_uniform"].zone_weights == (1.0, 1.0, 1.0, 1.0)
        
        # advisory_z2_focus
        assert profiles["advisory_z2_focus"].zone_weights == (0.5, 3.0, 1.5, 0.5)


class TestBackwardCompatibility:
    """하위 호환성 테스트 (기존 ZONE_PROFILES dict-like 접근)."""
    
    def test_zone_profiles_getitem(self):
        """ZONE_PROFILES['name'] 접근."""
        profile = ZONE_PROFILES["strict_uniform"]
        
        assert isinstance(profile, ZoneProfile)
        assert profile.name == "strict_uniform"
        assert profile.zone_weights == (1.0, 1.0, 1.0, 1.0)
    
    def test_zone_profiles_contains(self):
        """'name' in ZONE_PROFILES 동작."""
        assert "strict_uniform" in ZONE_PROFILES
        assert "advisory_z2_focus" in ZONE_PROFILES
        assert "nonexistent_profile" not in ZONE_PROFILES
    
    def test_zone_profiles_keys(self):
        """ZONE_PROFILES.keys() 동작."""
        keys = list(ZONE_PROFILES.keys())
        
        assert "strict_uniform" in keys
        assert "advisory_z2_focus" in keys
    
    def test_zone_profiles_values(self):
        """ZONE_PROFILES.values() 동작."""
        values = list(ZONE_PROFILES.values())
        
        assert all(isinstance(v, ZoneProfile) for v in values)
        assert any(v.name == "strict_uniform" for v in values)
    
    def test_zone_profiles_items(self):
        """ZONE_PROFILES.items() 동작."""
        items = list(ZONE_PROFILES.items())
        
        assert all(isinstance(name, str) and isinstance(profile, ZoneProfile) for name, profile in items)
        assert any(name == "strict_uniform" for name, _ in items)
    
    def test_zone_profiles_get(self):
        """ZONE_PROFILES.get() 동작."""
        profile = ZONE_PROFILES.get("strict_uniform")
        assert profile is not None
        assert profile.name == "strict_uniform"
        
        # 없는 프로파일
        none_profile = ZONE_PROFILES.get("nonexistent", None)
        assert none_profile is None


class TestLoadZoneProfilesFunction:
    """load_zone_profiles() 함수 테스트."""
    
    def test_load_zone_profiles_caching(self):
        """load_zone_profiles()가 캐싱 동작하는지 확인."""
        profiles1 = load_zone_profiles()
        profiles2 = load_zone_profiles()
        
        # 같은 객체 참조 (캐싱)
        assert profiles1 is profiles2
    
    def test_load_zone_profiles_force_reload(self):
        """force_reload=True 시 재로드 확인."""
        profiles1 = load_zone_profiles()
        profiles2 = load_zone_profiles(force_reload=True)
        
        # 내용은 같지만 새로 로드된 객체
        assert profiles1.keys() == profiles2.keys()
        # 객체 참조는 다를 수 있음 (재로드)
    
    def test_get_zone_profile_function(self):
        """get_zone_profile() 함수 동작."""
        profile = get_zone_profile("advisory_z2_focus")
        
        assert isinstance(profile, ZoneProfile)
        assert profile.name == "advisory_z2_focus"
        assert profile.zone_weights == (0.5, 3.0, 1.5, 0.5)
    
    def test_get_zone_profile_not_found(self):
        """존재하지 않는 프로파일 → KeyError."""
        with pytest.raises(KeyError, match="not found"):
            get_zone_profile("nonexistent_profile")


class TestD90Compatibility:
    """D90-0~3 테스트와의 호환성 확인."""
    
    def test_d90_0_zone_random_compatibility(self):
        """D90-0 zone_random 모드와 호환성."""
        from arbitrage.domain.entry_bps_profile import EntryBPSProfile
        
        # zone_random 모드 + YAML 기반 프로파일
        profile = EntryBPSProfile(
            mode="zone_random",
            min_bps=5.0,
            max_bps=25.0,
            zone_boundaries=[(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 25.0)],
            zone_profile_name="strict_uniform",
            seed=42,
        )
        
        # next() 호출 가능해야 함
        bps_values = [profile.next() for _ in range(100)]
        assert all(5.0 <= bps <= 25.0 for bps in bps_values)
    
    def test_d90_2_zone_profile_config_compatibility(self):
        """D90-2 Zone Profile Config와 호환성."""
        # YAML에서 로드한 프로파일이 기존 코드와 동일한 가중치를 가져야 함
        profiles = load_zone_profiles()
        
        # D90-2 기본 프로파일
        assert profiles["strict_uniform"].zone_weights == (1.0, 1.0, 1.0, 1.0)
        assert profiles["advisory_z2_focus"].zone_weights == (0.5, 3.0, 1.5, 0.5)
    
    def test_d90_3_zone_profile_tuning_compatibility(self):
        """D90-3 Zone Profile Tuning과 호환성."""
        profiles = load_zone_profiles()
        
        # D90-3 Sweep에 사용된 프로파일 가중치 확인
        assert profiles["advisory_z2_balanced"].zone_weights == (0.7, 2.5, 2.0, 0.8)
        assert profiles["advisory_z23_focus"].zone_weights == (0.3, 2.8, 2.2, 0.3)
        assert profiles["advisory_z2_conservative"].zone_weights == (1.0, 2.0, 1.8, 1.0)


# 통합 테스트
class TestIntegration:
    """통합 테스트: 전체 플로우 검증."""
    
    def test_full_flow_yaml_to_entry_bps(self):
        """YAML → EntryBPSProfile 전체 플로우."""
        from arbitrage.domain.entry_bps_profile import EntryBPSProfile
        
        # 1. YAML에서 프로파일 로드
        profile_name = "advisory_z2_focus"
        zone_profile = get_zone_profile(profile_name)
        
        # 2. EntryBPSProfile 생성
        entry_profile = EntryBPSProfile(
            mode="zone_random",
            min_bps=5.0,
            max_bps=25.0,
            zone_boundaries=[(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 25.0)],
            zone_profile_name=profile_name,
            seed=42,
        )
        
        # 3. BPS 샘플링
        bps_values = [entry_profile.next() for _ in range(1000)]
        
        # 4. 기본 검증
        assert all(5.0 <= bps <= 25.0 for bps in bps_values)
        assert len(set(bps_values)) > 10  # 다양한 값 생성
    
    def test_yaml_profile_matches_d90_2_baseline(self):
        """YAML 프로파일이 D90-2 Baseline과 정확히 일치하는지 확인."""
        profiles = load_zone_profiles()
        
        # D90-2 Validation Report의 기준값
        d90_2_baseline = {
            "strict_uniform": (1.0, 1.0, 1.0, 1.0),
            "advisory_z2_focus": (0.5, 3.0, 1.5, 0.5),
        }
        
        for name, expected_weights in d90_2_baseline.items():
            assert profiles[name].zone_weights == expected_weights, (
                f"Profile '{name}' weights mismatch!\n"
                f"Expected: {expected_weights}\n"
                f"Got: {profiles[name].zone_weights}\n"
                f"D90-4 must maintain exact same weights as D90-2 baseline."
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
