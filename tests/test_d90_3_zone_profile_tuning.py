#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D90-3: Zone Profile Tuning v1 - Unit Tests

신규 Zone Profile 검증 및 Sweep 스크립트 핵심 함수 테스트.

Author: arbitrage-lite project
Date: 2025-12-10
"""

import pytest
from arbitrage.domain.entry_bps_profile import (
    EntryBPSProfile,
    ZoneProfile,
    ZONE_PROFILES,
)


class TestD90_3NewProfiles:
    """D90-3 신규 Zone Profile 검증"""
    
    def test_new_profiles_exist(self):
        """신규 프로파일이 ZONE_PROFILES에 존재하는지 검증"""
        assert "advisory_z2_balanced" in ZONE_PROFILES
        assert "advisory_z23_focus" in ZONE_PROFILES
        assert "advisory_z2_conservative" in ZONE_PROFILES
    
    def test_advisory_z2_balanced_profile(self):
        """advisory_z2_balanced 프로파일 검증"""
        profile = ZONE_PROFILES["advisory_z2_balanced"]
        
        assert profile.name == "advisory_z2_balanced"
        assert profile.zone_weights == (0.7, 2.5, 2.0, 0.8)
        assert "balanced" in profile.description.lower() or "z2" in profile.description.lower()
    
    def test_advisory_z23_focus_profile(self):
        """advisory_z23_focus 프로파일 검증"""
        profile = ZONE_PROFILES["advisory_z23_focus"]
        
        assert profile.name == "advisory_z23_focus"
        assert profile.zone_weights == (0.3, 2.8, 2.2, 0.3)
        assert "z2" in profile.description.lower() or "z3" in profile.description.lower()
    
    def test_advisory_z2_conservative_profile(self):
        """advisory_z2_conservative 프로파일 검증"""
        profile = ZONE_PROFILES["advisory_z2_conservative"]
        
        assert profile.name == "advisory_z2_conservative"
        assert profile.zone_weights == (1.0, 2.0, 1.8, 1.0)
        assert "conservative" in profile.description.lower()
    
    def test_all_profiles_have_positive_weights(self):
        """모든 프로파일의 가중치가 양수인지 검증"""
        for profile_name, profile in ZONE_PROFILES.items():
            for i, weight in enumerate(profile.zone_weights):
                assert weight > 0, f"{profile_name} Zone {i+1} weight must be positive, got {weight}"
    
    def test_all_profiles_have_nonzero_sum(self):
        """모든 프로파일의 가중치 합이 0보다 큰지 검증"""
        for profile_name, profile in ZONE_PROFILES.items():
            total = sum(profile.zone_weights)
            assert total > 0, f"{profile_name} total weight must be > 0, got {total}"
    
    def test_baseline_profiles_unchanged(self):
        """D90-2 Baseline 프로파일이 변경되지 않았는지 검증"""
        # strict_uniform
        strict = ZONE_PROFILES["strict_uniform"]
        assert strict.zone_weights == (1.0, 1.0, 1.0, 1.0)
        
        # advisory_z2_focus
        advisory = ZONE_PROFILES["advisory_z2_focus"]
        assert advisory.zone_weights == (0.5, 3.0, 1.5, 0.5)


class TestD90_3ProfileIntegration:
    """D90-3 프로파일과 EntryBPSProfile 통합 테스트"""
    
    def test_advisory_z2_balanced_integration(self):
        """advisory_z2_balanced 프로파일 통합 테스트"""
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="advisory_z2_balanced",
            seed=42,
        )
        
        assert profile.zone_weights == [0.7, 2.5, 2.0, 0.8]
        assert profile.zone_profile_name == "advisory_z2_balanced"
    
    def test_advisory_z23_focus_integration(self):
        """advisory_z23_focus 프로파일 통합 테스트"""
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="advisory_z23_focus",
            seed=90,
        )
        
        assert profile.zone_weights == [0.3, 2.8, 2.2, 0.3]
        assert profile.zone_profile_name == "advisory_z23_focus"
    
    def test_advisory_z2_conservative_integration(self):
        """advisory_z2_conservative 프로파일 통합 테스트"""
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="advisory_z2_conservative",
            seed=100,
        )
        
        assert profile.zone_weights == [1.0, 2.0, 1.8, 1.0]
        assert profile.zone_profile_name == "advisory_z2_conservative"


class TestD90_3ZoneDistributionEstimate:
    """D90-3 프로파일의 예상 Zone 분포 검증 (통계적)"""
    
    def test_advisory_z2_balanced_distribution(self):
        """advisory_z2_balanced 프로파일의 Zone 분포 검증"""
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="advisory_z2_balanced",
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
        
        # 예상 분포: [0.7, 2.5, 2.0, 0.8] / 6.0 = [11.7%, 41.7%, 33.3%, 13.3%]
        z1_pct = zone_counts[0] / 2000 * 100
        z2_pct = zone_counts[1] / 2000 * 100
        z3_pct = zone_counts[2] / 2000 * 100
        z4_pct = zone_counts[3] / 2000 * 100
        
        # 범위 검증 (±10%p)
        assert 5 <= z1_pct <= 20, f"Z1: {z1_pct:.1f}% (expected 11.7% ± 10%p)"
        assert 35 <= z2_pct <= 50, f"Z2: {z2_pct:.1f}% (expected 41.7% ± 10%p)"
        assert 25 <= z3_pct <= 45, f"Z3: {z3_pct:.1f}% (expected 33.3% ± 10%p)"
        assert 5 <= z4_pct <= 20, f"Z4: {z4_pct:.1f}% (expected 13.3% ± 10%p)"
    
    def test_advisory_z23_focus_distribution(self):
        """advisory_z23_focus 프로파일의 Zone 분포 검증"""
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="advisory_z23_focus",
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
        
        # 예상 분포: [0.3, 2.8, 2.2, 0.3] / 5.6 = [5.4%, 50.0%, 39.3%, 5.4%]
        z1_pct = zone_counts[0] / 2000 * 100
        z2_pct = zone_counts[1] / 2000 * 100
        z3_pct = zone_counts[2] / 2000 * 100
        z4_pct = zone_counts[3] / 2000 * 100
        
        # 범위 검증 (±10%p)
        assert 0 <= z1_pct <= 15, f"Z1: {z1_pct:.1f}% (expected 5.4% ± 10%p)"
        assert 40 <= z2_pct <= 60, f"Z2: {z2_pct:.1f}% (expected 50.0% ± 10%p)"
        assert 30 <= z3_pct <= 50, f"Z3: {z3_pct:.1f}% (expected 39.3% ± 10%p)"
        assert 0 <= z4_pct <= 15, f"Z4: {z4_pct:.1f}% (expected 5.4% ± 10%p)"
    
    def test_advisory_z2_conservative_distribution(self):
        """advisory_z2_conservative 프로파일의 Zone 분포 검증"""
        profile = EntryBPSProfile(
            mode="zone_random",
            zone_profile_name="advisory_z2_conservative",
            seed=100,
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
        
        # 예상 분포: [1.0, 2.0, 1.8, 1.0] / 5.8 = [17.2%, 34.5%, 31.0%, 17.2%]
        z1_pct = zone_counts[0] / 2000 * 100
        z2_pct = zone_counts[1] / 2000 * 100
        z3_pct = zone_counts[2] / 2000 * 100
        z4_pct = zone_counts[3] / 2000 * 100
        
        # 범위 검증 (±10%p)
        assert 10 <= z1_pct <= 25, f"Z1: {z1_pct:.1f}% (expected 17.2% ± 10%p)"
        assert 25 <= z2_pct <= 45, f"Z2: {z2_pct:.1f}% (expected 34.5% ± 10%p)"
        assert 20 <= z3_pct <= 40, f"Z3: {z3_pct:.1f}% (expected 31.0% ± 10%p)"
        assert 10 <= z4_pct <= 25, f"Z4: {z4_pct:.1f}% (expected 17.2% ± 10%p)"


class TestD90_3SweepAggregation:
    """D90-3 Sweep 스크립트의 집계 함수 테스트"""
    
    def test_aggregate_results_basic(self):
        """기본 집계 함수 테스트"""
        from scripts.run_d90_3_zone_profile_sweep import aggregate_results
        
        # 샘플 결과
        results = [
            {
                'profile_name': 'test_profile',
                'mode': 'advisory',
                'run_idx': 1,
                'success': True,
                'kpi': {'total_pnl_usd': 5.0, 'entry_trades': 120, 'actual_duration_seconds': 1200.0},
                'zone_distribution': {'zone_percentages': [10.0, 50.0, 30.0, 10.0]},
            },
            {
                'profile_name': 'test_profile',
                'mode': 'advisory',
                'run_idx': 2,
                'success': True,
                'kpi': {'total_pnl_usd': 6.0, 'entry_trades': 120, 'actual_duration_seconds': 1200.5},
                'zone_distribution': {'zone_percentages': [12.0, 48.0, 32.0, 8.0]},
            },
        ]
        
        aggregated = aggregate_results(results)
        
        # 검증
        assert 'test_profile_advisory' in aggregated
        data = aggregated['test_profile_advisory']
        
        assert data['profile_name'] == 'test_profile'
        assert data['mode'] == 'advisory'
        assert data['run_count'] == 2
        assert data['pnl']['mean'] == 5.5
        assert data['zone_percentages']['z2']['mean'] == 49.0
    
    def test_aggregate_results_empty(self):
        """빈 결과 집계 테스트"""
        from scripts.run_d90_3_zone_profile_sweep import aggregate_results
        
        results = []
        aggregated = aggregate_results(results)
        
        assert aggregated == {}
    
    def test_aggregate_results_failed_runs(self):
        """실패한 실행 제외 테스트"""
        from scripts.run_d90_3_zone_profile_sweep import aggregate_results
        
        results = [
            {
                'profile_name': 'test_profile',
                'mode': 'advisory',
                'run_idx': 1,
                'success': False,
                'error': 'Test error',
            },
            {
                'profile_name': 'test_profile',
                'mode': 'advisory',
                'run_idx': 2,
                'success': True,
                'kpi': {'total_pnl_usd': 5.0, 'entry_trades': 120, 'actual_duration_seconds': 1200.0},
                'zone_distribution': {'zone_percentages': [10.0, 50.0, 30.0, 10.0]},
            },
        ]
        
        aggregated = aggregate_results(results)
        
        # 성공한 실행만 집계
        assert 'test_profile_advisory' in aggregated
        data = aggregated['test_profile_advisory']
        assert data['run_count'] == 1
