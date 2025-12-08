#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D88-0: Entry BPS Profile 유닛 테스트

Entry BPS Profile의 fixed/cycle/random 모드 동작을 검증한다.
"""

import pytest
from arbitrage.domain.entry_bps_profile import EntryBPSProfile


class TestEntryBPSProfile:
    """Entry BPS Profile 테스트"""
    
    def test_fixed_mode_returns_same_value(self):
        """Fixed 모드: 항상 같은 값 반환"""
        profile = EntryBPSProfile(mode="fixed", min_bps=10.0, max_bps=10.0)
        
        # 100번 호출해도 항상 10.0
        values = [profile.next() for _ in range(100)]
        assert all(v == 10.0 for v in values), "Fixed 모드는 항상 같은 값을 반환해야 함"
    
    def test_cycle_mode_repeats_zone_values(self):
        """Cycle 모드: Zone별 대표 BPS를 순환"""
        profile = EntryBPSProfile(
            mode="cycle",
            min_bps=5.0,
            max_bps=25.0,
            zone_boundaries=[
                (5.0, 7.0),    # Z1, 중간값 6.0
                (7.0, 12.0),   # Z2, 중간값 9.5
                (12.0, 20.0),  # Z3, 중간값 16.0
                (20.0, 30.0),  # Z4, 중간값 25.0
            ]
        )
        
        # 첫 사이클 (Z1 → Z2 → Z3 → Z4)
        v1 = profile.next()
        v2 = profile.next()
        v3 = profile.next()
        v4 = profile.next()
        
        assert v1 == 6.0, "Z1 중간값"
        assert v2 == 9.5, "Z2 중간값"
        assert v3 == 16.0, "Z3 중간값"
        assert v4 == 25.0, "Z4 중간값"
        
        # 두 번째 사이클 (반복)
        v5 = profile.next()
        v6 = profile.next()
        assert v5 == 6.0, "Z1 중간값 (반복)"
        assert v6 == 9.5, "Z2 중간값 (반복)"
    
    def test_random_mode_within_range(self):
        """Random 모드: 범위 내 난수 생성"""
        profile = EntryBPSProfile(mode="random", min_bps=5.0, max_bps=25.0, seed=42)
        
        # 100개 샘플 생성
        values = [profile.next() for _ in range(100)]
        
        # 모든 값이 범위 내
        assert all(5.0 <= v <= 25.0 for v in values), "Random 모드는 범위 내 값을 생성해야 함"
        
        # 값들이 다양함 (적어도 10개 이상의 unique 값)
        unique_values = set(values)
        assert len(unique_values) >= 10, "Random 모드는 다양한 값을 생성해야 함"
    
    def test_random_mode_reproducibility(self):
        """Random 모드: 같은 seed로 동일한 시퀀스 생성"""
        profile1 = EntryBPSProfile(mode="random", min_bps=5.0, max_bps=25.0, seed=42)
        profile2 = EntryBPSProfile(mode="random", min_bps=5.0, max_bps=25.0, seed=42)
        
        # 같은 seed로 100개 생성
        values1 = [profile1.next() for _ in range(100)]
        values2 = [profile2.next() for _ in range(100)]
        
        assert values1 == values2, "같은 seed는 동일한 시퀀스를 생성해야 함"
    
    def test_random_mode_different_seeds(self):
        """Random 모드: 다른 seed로 다른 시퀀스 생성"""
        profile1 = EntryBPSProfile(mode="random", min_bps=5.0, max_bps=25.0, seed=42)
        profile2 = EntryBPSProfile(mode="random", min_bps=5.0, max_bps=25.0, seed=123)
        
        # 다른 seed로 100개 생성
        values1 = [profile1.next() for _ in range(100)]
        values2 = [profile2.next() for _ in range(100)]
        
        assert values1 != values2, "다른 seed는 다른 시퀀스를 생성해야 함"
    
    def test_reset_restores_initial_state(self):
        """Reset: 초기 상태로 복원"""
        profile = EntryBPSProfile(mode="random", min_bps=5.0, max_bps=25.0, seed=42)
        
        # 첫 10개 값
        values1 = [profile.next() for _ in range(10)]
        
        # Reset 후 다시 10개 값
        profile.reset()
        values2 = [profile.next() for _ in range(10)]
        
        assert values1 == values2, "Reset 후 동일한 시퀀스를 생성해야 함"
    
    def test_zone_boundaries_validation(self):
        """Zone Boundaries: 검증"""
        # 유효한 경계
        profile = EntryBPSProfile(
            mode="fixed",
            min_bps=10.0,
            max_bps=10.0,
            zone_boundaries=[(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 30.0)]
        )
        assert profile is not None
        
        # 잘못된 경계 (min >= max)
        with pytest.raises(ValueError):
            EntryBPSProfile(
                mode="fixed",
                min_bps=10.0,
                max_bps=10.0,
                zone_boundaries=[(7.0, 5.0)]  # 잘못된 순서
            )
    
    def test_invalid_mode_raises_error(self):
        """Invalid Mode: 에러 발생"""
        with pytest.raises(ValueError):
            EntryBPSProfile(mode="invalid", min_bps=10.0, max_bps=10.0)
    
    def test_min_max_validation(self):
        """Min/Max 검증"""
        # min > max
        with pytest.raises(ValueError):
            EntryBPSProfile(mode="fixed", min_bps=20.0, max_bps=10.0)
        
        # 음수
        with pytest.raises(ValueError):
            EntryBPSProfile(mode="fixed", min_bps=-5.0, max_bps=10.0)
    
    def test_cycle_mode_zone_coverage(self):
        """Cycle 모드: 모든 Zone을 커버"""
        profile = EntryBPSProfile(
            mode="cycle",
            min_bps=5.0,
            max_bps=25.0,
            zone_boundaries=[
                (5.0, 7.0),    # Z1
                (7.0, 12.0),   # Z2
                (12.0, 20.0),  # Z3
                (20.0, 30.0),  # Z4
            ]
        )
        
        # 4개 Zone을 순환하므로 8개 호출 시 각 Zone이 2번씩 나타남
        values = [profile.next() for _ in range(8)]
        
        # Zone 중간값
        z1_mid = 6.0
        z2_mid = 9.5
        z3_mid = 16.0
        z4_mid = 25.0
        
        # 각 Zone이 2번씩 나타나는지 확인
        assert values.count(z1_mid) == 2, "Z1이 2번 나타나야 함"
        assert values.count(z2_mid) == 2, "Z2가 2번 나타나야 함"
        assert values.count(z3_mid) == 2, "Z3이 2번 나타나야 함"
        assert values.count(z4_mid) == 2, "Z4가 2번 나타나야 함"
    
    def test_random_mode_zone_distribution(self):
        """Random 모드: Zone별 분포 검증 (샘플링)"""
        profile = EntryBPSProfile(
            mode="random",
            min_bps=5.0,
            max_bps=30.0,
            seed=42,
            zone_boundaries=[
                (5.0, 7.0),    # Z1
                (7.0, 12.0),   # Z2
                (12.0, 20.0),  # Z3
                (20.0, 30.0),  # Z4
            ]
        )
        
        # 1000개 샘플 생성
        values = [profile.next() for _ in range(1000)]
        
        # 각 Zone에 속하는 샘플 수
        z1_count = sum(1 for v in values if 5.0 <= v < 7.0)
        z2_count = sum(1 for v in values if 7.0 <= v < 12.0)
        z3_count = sum(1 for v in values if 12.0 <= v < 20.0)
        z4_count = sum(1 for v in values if 20.0 <= v < 30.0)
        
        # 모든 Zone에 최소 1개 이상의 샘플이 존재해야 함
        assert z1_count > 0, "Z1에 샘플이 없음"
        assert z2_count > 0, "Z2에 샘플이 없음"
        assert z3_count > 0, "Z3에 샘플이 없음"
        assert z4_count > 0, "Z4에 샘플이 없음"
        
        # 각 Zone이 전체의 5% 이상을 차지해야 함 (균일 분포 검증)
        total = z1_count + z2_count + z3_count + z4_count
        assert z1_count / total >= 0.05, f"Z1 비율이 너무 낮음: {z1_count/total:.2%}"
        assert z2_count / total >= 0.05, f"Z2 비율이 너무 낮음: {z2_count/total:.2%}"
        assert z3_count / total >= 0.05, f"Z3 비율이 너무 낮음: {z3_count/total:.2%}"
        assert z4_count / total >= 0.05, f"Z4 비율이 너무 낮음: {z4_count/total:.2%}"
