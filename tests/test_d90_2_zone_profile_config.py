#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D90-2: Zone Profile Config Unit Tests

Zone Profile 추상화 및 EntryBPSProfile 통합 테스트.

Author: arbitrage-lite project
Date: 2025-12-10
"""

import pytest
from arbitrage.domain.entry_bps_profile import (
    EntryBPSProfile,
    ZoneProfile,
    ZONE_PROFILES,
)


class TestZoneProfile:
    """ZoneProfile dataclass 테스트"""
    
    def test_zone_profile_creation(self):
        """ZoneProfile 생성 테스트"""
        profile = ZoneProfile(
            name="test_profile",
            description="Test profile",
            zone_weights=(1.0, 2.0, 3.0, 4.0),
        )
        
        assert profile.name == "test_profile"
        assert profile.description == "Test profile"
        assert profile.zone_weights == (1.0, 2.0, 3.0, 4.0)
    
    def test_zone_profile_immutable(self):
        """ZoneProfile이 immutable한지 테스트"""
        profile = ZoneProfile(
            name="test",
            description="Test",
            zone_weights=(1.0, 1.0, 1.0, 1.0),
        )
        
        with pytest.raises(AttributeError):
            profile.name = "new_name"  # frozen=True이므로 수정 불가


class TestZoneProfiles:
    """ZONE_PROFILES 상수 테스트"""
    
    def test_zone_profiles_exist(self):
        """기본 프로파일이 존재하는지 테스트"""
        assert "strict_uniform" in ZONE_PROFILES
        assert "advisory_z2_focus" in ZONE_PROFILES
    
    def test_strict_uniform_profile(self):
        """strict_uniform 프로파일 검증"""
        profile = ZONE_PROFILES["strict_uniform"]
        
        assert profile.name == "strict_uniform"
        assert profile.zone_weights == (1.0, 1.0, 1.0, 1.0)
        assert "uniform" in profile.description.lower()
    
    def test_advisory_z2_focus_profile(self):
        """advisory_z2_focus 프로파일 검증"""
        profile = ZONE_PROFILES["advisory_z2_focus"]
        
        assert profile.name == "advisory_z2_focus"
        assert profile.zone_weights == (0.5, 3.0, 1.5, 0.5)
        assert "z2" in profile.description.lower()


class TestEntryBPSProfileWithZoneProfile:
    """EntryBPSProfile + Zone Profile 통합 테스트"""
    
    def test_zone_profile_name_strict_uniform(self):
        """zone_profile_name='strict_uniform' 테스트"""
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="strict_uniform",
            seed=42,
        )
        
        assert profile.zone_weights == [1.0, 1.0, 1.0, 1.0]
        assert profile.zone_profile_name == "strict_uniform"
    
    def test_zone_profile_name_advisory_z2_focus(self):
        """zone_profile_name='advisory_z2_focus' 테스트"""
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="advisory_z2_focus",
            seed=90,
        )
        
        assert profile.zone_weights == [0.5, 3.0, 1.5, 0.5]
        assert profile.zone_profile_name == "advisory_z2_focus"
    
    def test_invalid_zone_profile_name(self):
        """잘못된 zone_profile_name 테스트"""
        with pytest.raises(ValueError) as exc_info:
            EntryBPSProfile(
                mode="zone_random",
                zone_profile_name="invalid_profile",
                seed=42,
            )
        
        error_msg = str(exc_info.value)
        assert "invalid_profile" in error_msg
        assert "strict_uniform" in error_msg
        assert "advisory_z2_focus" in error_msg
    
    def test_zone_profile_priority_over_zone_weights(self):
        """zone_profile_name이 zone_weights보다 우선순위가 높은지 테스트"""
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="strict_uniform",
            zone_weights=[0.5, 3.0, 1.5, 0.5],  # 무시되어야 함
            seed=42,
        )
        
        # zone_profile_name이 우선순위가 높으므로 strict_uniform의 가중치 사용
        assert profile.zone_weights == [1.0, 1.0, 1.0, 1.0]
        assert profile.zone_profile_name == "strict_uniform"
    
    def test_backward_compatibility_zone_weights(self):
        """zone_weights 직접 지정 (backward compatibility) 테스트"""
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_weights=[0.5, 3.0, 1.5, 0.5],
            seed=90,
        )
        
        assert profile.zone_weights == [0.5, 3.0, 1.5, 0.5]
        assert profile.zone_profile_name is None
    
    def test_zone_profile_ignored_for_non_zone_random(self):
        """zone_random 모드가 아니면 zone_profile_name 무시"""
        profile = EntryBPSProfile(
            mode="random",
            zone_profile_name="advisory_z2_focus",  # 무시되어야 함
            min_bps=5.0,
            max_bps=25.0,
            seed=42,
        )
        
        assert profile.mode == "random"
        assert profile.zone_profile_name is None


class TestZoneDistribution:
    """Zone 분포 통계 테스트 (2000 샘플)"""
    
    def test_strict_uniform_distribution(self):
        """strict_uniform 프로파일의 Zone 분포 검증"""
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="strict_uniform",
            seed=42,
        )
        
        # 2000 샘플 생성
        samples = [profile.next() for _ in range(2000)]
        
        # Zone별 카운트
        zone_counts = [0, 0, 0, 0]
        for bps in samples:
            if 5.0 <= bps < 7.0:
                zone_counts[0] += 1
            elif 7.0 <= bps < 12.0:
                zone_counts[1] += 1
            elif 12.0 <= bps < 20.0:
                zone_counts[2] += 1
            elif 20.0 <= bps < 30.0:
                zone_counts[3] += 1
        
        # 각 Zone이 20~30% 범위 (균등 분포 25% ± 5%p)
        for i, count in enumerate(zone_counts):
            percentage = count / 2000 * 100
            assert 20 <= percentage <= 30, f"Zone {i+1}: {percentage:.1f}% (expected 20~30%)"
    
    def test_advisory_z2_focus_distribution(self):
        """advisory_z2_focus 프로파일의 Zone 분포 검증"""
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="advisory_z2_focus",
            seed=90,
        )
        
        # 2000 샘플 생성
        samples = [profile.next() for _ in range(2000)]
        
        # Zone별 카운트
        zone_counts = [0, 0, 0, 0]
        for bps in samples:
            if 5.0 <= bps < 7.0:
                zone_counts[0] += 1
            elif 7.0 <= bps < 12.0:
                zone_counts[1] += 1
            elif 12.0 <= bps < 20.0:
                zone_counts[2] += 1
            elif 20.0 <= bps < 30.0:
                zone_counts[3] += 1
        
        # Z2가 40~60% 범위 (예상 54.5% ± 10%p)
        z2_percentage = zone_counts[1] / 2000 * 100
        assert 40 <= z2_percentage <= 60, f"Z2: {z2_percentage:.1f}% (expected 40~60%)"
        
        # Z1, Z4는 5~15% 범위
        z1_percentage = zone_counts[0] / 2000 * 100
        z4_percentage = zone_counts[3] / 2000 * 100
        assert 5 <= z1_percentage <= 15, f"Z1: {z1_percentage:.1f}% (expected 5~15%)"
        assert 5 <= z4_percentage <= 15, f"Z4: {z4_percentage:.1f}% (expected 5~15%)"


class TestReproducibility:
    """재현성 테스트"""
    
    def test_same_seed_same_results(self):
        """같은 seed로 생성한 프로파일은 같은 결과를 생성"""
        profile1 = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="advisory_z2_focus",
            seed=90,
        )
        
        profile2 = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="advisory_z2_focus",
            seed=90,
        )
        
        samples1 = [profile1.next() for _ in range(100)]
        samples2 = [profile2.next() for _ in range(100)]
        
        assert samples1 == samples2
    
    def test_reset_reproducibility(self):
        """reset() 후 같은 결과 생성"""
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="strict_uniform",
            seed=42,
        )
        
        samples1 = [profile.next() for _ in range(50)]
        profile.reset()
        samples2 = [profile.next() for _ in range(50)]
        
        assert samples1 == samples2
