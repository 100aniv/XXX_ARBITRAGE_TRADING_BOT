# -*- coding: utf-8 -*-
"""
D90-0: Entry BPS Zone-Weighted Random - Unit Tests

zone_random 모드 구현 검증.

Test Scenarios:
1. T1: 잘못된 설정 검증 (ValueError 발생)
2. T2: seed 고정 시 재현성 검증
3. T3: Zone 분포 검증 (rough, N=10,000)

Author: arbitrage-lite project
Date: 2025-12-09
"""

import pytest
from arbitrage.domain.entry_bps_profile import EntryBPSProfile


class TestD90EntryBPSZoneRandom:
    """
    D90-0: Entry BPS Zone-Weighted Random 테스트
    """
    
    def test_t1_invalid_config_empty_zone_boundaries(self):
        """
        T1-1: zone_random 모드에서 zone_boundaries가 비어있으면 ValueError
        """
        with pytest.raises(ValueError, match="zone_boundaries must not be empty"):
            EntryBPSProfile(
                mode="zone_random",
                zone_boundaries=[],
                zone_weights=[1.0, 1.0, 1.0, 1.0],
            )
    
    def test_t1_invalid_config_weights_length_mismatch(self):
        """
        T1-2: zone_random 모드에서 zone_weights 길이가 zone_boundaries와 다르면 ValueError
        """
        with pytest.raises(ValueError, match="zone_weights length .* must match"):
            EntryBPSProfile(
                mode="zone_random",
                zone_boundaries=[(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 30.0)],
                zone_weights=[1.0, 3.0, 1.5],  # 길이 3 (zone_boundaries는 4)
            )
    
    def test_t1_invalid_config_zero_weight(self):
        """
        T1-3: zone_random 모드에서 zone_weights에 0이 있으면 ValueError
        """
        with pytest.raises(ValueError, match="zone_weights.* must be positive"):
            EntryBPSProfile(
                mode="zone_random",
                zone_boundaries=[(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 30.0)],
                zone_weights=[1.0, 0.0, 1.5, 0.5],  # zone_weights[1] = 0
            )
    
    def test_t1_invalid_config_negative_weight(self):
        """
        T1-4: zone_random 모드에서 zone_weights에 음수가 있으면 ValueError
        """
        with pytest.raises(ValueError, match="zone_weights.* must be positive"):
            EntryBPSProfile(
                mode="zone_random",
                zone_boundaries=[(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 30.0)],
                zone_weights=[1.0, -1.0, 1.5, 0.5],  # zone_weights[1] < 0
            )
    
    def test_t2_reproducibility_with_fixed_seed(self):
        """
        T2: seed 고정 시 재현성 검증
        
        같은 seed를 사용하면 같은 Entry BPS 시퀀스가 생성되어야 함.
        """
        # Arrange
        seed = 90
        zone_weights = [0.5, 3.0, 1.5, 0.5]
        
        profile1 = EntryBPSProfile(
            mode="zone_random",
            zone_weights=zone_weights,
            seed=seed,
        )
        
        profile2 = EntryBPSProfile(
            mode="zone_random",
            zone_weights=zone_weights,
            seed=seed,
        )
        
        # Act: 각 프로파일에서 100개 샘플 생성
        samples1 = [profile1.next() for _ in range(100)]
        samples2 = [profile2.next() for _ in range(100)]
        
        # Assert: 두 시퀀스가 완전히 동일해야 함
        assert samples1 == samples2, \
            f"Same seed should produce identical sequences"
    
    def test_t3_zone_distribution_rough(self):
        """
        T3: Zone 분포 검증 (rough)
        
        zone_weights = [1.0, 3.0, 1.0, 1.0]로 설정 시,
        N=10,000 샘플링 후 Z2가 약 50% (3/6) 정도 선택되어야 함.
        
        허용 오차: ±7%p
        """
        # Arrange
        zone_weights = [1.0, 3.0, 1.0, 1.0]  # 총합 = 6.0
        # 예상 확률: Z1=1/6=16.7%, Z2=3/6=50.0%, Z3=1/6=16.7%, Z4=1/6=16.7%
        
        zone_boundaries = [
            (5.0, 7.0),    # Z1
            (7.0, 12.0),   # Z2
            (12.0, 20.0),  # Z3
            (20.0, 30.0),  # Z4
        ]
        
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_boundaries=zone_boundaries,
            zone_weights=zone_weights,
            seed=42,
        )
        
        # Act: N=10,000 샘플링
        N = 10_000
        zone_counts = [0, 0, 0, 0]
        
        for _ in range(N):
            bps = profile.next()
            
            # BPS 값으로 Zone 판정
            if 5.0 <= bps < 7.0:
                zone_counts[0] += 1
            elif 7.0 <= bps < 12.0:
                zone_counts[1] += 1
            elif 12.0 <= bps < 20.0:
                zone_counts[2] += 1
            elif 20.0 <= bps < 30.0:
                zone_counts[3] += 1
        
        # Assert: Zone 비율 계산
        zone_ratios = [count / N for count in zone_counts]
        
        # 예상 비율 (허용 오차 ±7%p)
        expected_ratios = [1/6, 3/6, 1/6, 1/6]
        tolerance = 0.07  # ±7%p
        
        for i, (actual, expected) in enumerate(zip(zone_ratios, expected_ratios)):
            assert abs(actual - expected) < tolerance, \
                f"Zone {i+1} ratio {actual:.3f} deviates from expected {expected:.3f} by more than {tolerance}"
    
    def test_t4_zone_distribution_advisory_profile(self):
        """
        T4: Advisory 프로필 (Z2 3배 강화) 분포 검증
        
        zone_weights = [0.5, 3.0, 1.5, 0.5]로 설정 시,
        N=10,000 샘플링 후 Z2가 약 54.5% (3.0/5.5) 정도 선택되어야 함.
        
        허용 오차: ±7%p
        """
        # Arrange
        zone_weights = [0.5, 3.0, 1.5, 0.5]  # 총합 = 5.5
        # 예상 확률: Z1=0.5/5.5=9.1%, Z2=3.0/5.5=54.5%, Z3=1.5/5.5=27.3%, Z4=0.5/5.5=9.1%
        
        zone_boundaries = [
            (5.0, 7.0),    # Z1
            (7.0, 12.0),   # Z2
            (12.0, 20.0),  # Z3
            (20.0, 30.0),  # Z4
        ]
        
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_boundaries=zone_boundaries,
            zone_weights=zone_weights,
            seed=90,
        )
        
        # Act: N=10,000 샘플링
        N = 10_000
        zone_counts = [0, 0, 0, 0]
        
        for _ in range(N):
            bps = profile.next()
            
            # BPS 값으로 Zone 판정
            if 5.0 <= bps < 7.0:
                zone_counts[0] += 1
            elif 7.0 <= bps < 12.0:
                zone_counts[1] += 1
            elif 12.0 <= bps < 20.0:
                zone_counts[2] += 1
            elif 20.0 <= bps < 30.0:
                zone_counts[3] += 1
        
        # Assert: Zone 비율 계산
        zone_ratios = [count / N for count in zone_counts]
        
        # 예상 비율 (허용 오차 ±7%p)
        expected_ratios = [0.5/5.5, 3.0/5.5, 1.5/5.5, 0.5/5.5]
        tolerance = 0.07  # ±7%p
        
        for i, (actual, expected) in enumerate(zip(zone_ratios, expected_ratios)):
            assert abs(actual - expected) < tolerance, \
                f"Zone {i+1} ratio {actual:.3f} deviates from expected {expected:.3f} by more than {tolerance}"
    
    def test_t5_zone_distribution_strict_profile(self):
        """
        T5: Strict 프로필 (균등 가중치) 분포 검증
        
        zone_weights = [1.0, 1.0, 1.0, 1.0]로 설정 시,
        N=10,000 샘플링 후 각 Zone이 약 25% 정도 선택되어야 함.
        
        허용 오차: ±7%p
        """
        # Arrange
        zone_weights = [1.0, 1.0, 1.0, 1.0]  # 총합 = 4.0
        # 예상 확률: 각 Zone 25%
        
        zone_boundaries = [
            (5.0, 7.0),    # Z1
            (7.0, 12.0),   # Z2
            (12.0, 20.0),  # Z3
            (20.0, 30.0),  # Z4
        ]
        
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_boundaries=zone_boundaries,
            zone_weights=zone_weights,
            seed=90,
        )
        
        # Act: N=10,000 샘플링
        N = 10_000
        zone_counts = [0, 0, 0, 0]
        
        for _ in range(N):
            bps = profile.next()
            
            # BPS 값으로 Zone 판정
            if 5.0 <= bps < 7.0:
                zone_counts[0] += 1
            elif 7.0 <= bps < 12.0:
                zone_counts[1] += 1
            elif 12.0 <= bps < 20.0:
                zone_counts[2] += 1
            elif 20.0 <= bps < 30.0:
                zone_counts[3] += 1
        
        # Assert: Zone 비율 계산
        zone_ratios = [count / N for count in zone_counts]
        
        # 예상 비율 (허용 오차 ±7%p)
        expected_ratios = [0.25, 0.25, 0.25, 0.25]
        tolerance = 0.07  # ±7%p
        
        for i, (actual, expected) in enumerate(zip(zone_ratios, expected_ratios)):
            assert abs(actual - expected) < tolerance, \
                f"Zone {i+1} ratio {actual:.3f} deviates from expected {expected:.3f} by more than {tolerance}"
    
    def test_t6_reset_functionality(self):
        """
        T6: reset() 기능 검증
        
        reset() 후에는 같은 시퀀스가 다시 생성되어야 함.
        """
        # Arrange
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_weights=[0.5, 3.0, 1.5, 0.5],
            seed=90,
        )
        
        # Act: 첫 번째 시퀀스
        samples1 = [profile.next() for _ in range(100)]
        
        # Reset
        profile.reset()
        
        # 두 번째 시퀀스
        samples2 = [profile.next() for _ in range(100)]
        
        # Assert: 두 시퀀스가 동일해야 함
        assert samples1 == samples2, \
            f"reset() should regenerate the same sequence"
    
    def test_t7_backward_compatibility_with_none_weights(self):
        """
        T7: zone_weights=None일 때 균등 가중치로 동작
        
        zone_weights를 명시하지 않으면 [1.0, 1.0, 1.0, 1.0]와 동일하게 동작해야 함.
        """
        # Arrange
        profile_none = EntryBPSProfile(
            mode="zone_random",
            zone_weights=None,  # 명시하지 않음
            seed=42,
        )
        
        profile_explicit = EntryBPSProfile(
            mode="zone_random",
            zone_weights=[1.0, 1.0, 1.0, 1.0],  # 명시적으로 균등
            seed=42,
        )
        
        # Act: 각 프로파일에서 100개 샘플 생성
        samples_none = [profile_none.next() for _ in range(100)]
        samples_explicit = [profile_explicit.next() for _ in range(100)]
        
        # Assert: 두 시퀀스가 동일해야 함
        assert samples_none == samples_explicit, \
            f"zone_weights=None should be equivalent to [1.0, 1.0, 1.0, 1.0]"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
