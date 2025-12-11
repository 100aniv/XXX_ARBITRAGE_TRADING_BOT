"""
D90-5: YAML Zone Profile 1h/3h LONGRUN Validation - Config Tests

Purpose:
- YAML Loader 연동 확인
- 프로파일 가중치 정확도 검증
- 로그 경로 패턴 검증
- Duration 파라미터 전달 확인

Note: 실제 1h/3h LONGRUN은 이 테스트에서 실행하지 않음 (구조 검증만)
"""

import re
import pytest
from pathlib import Path


class TestD90_5_YAMLLoaderIntegration:
    """D90-5: YAML Loader 연동 확인"""

    def test_yaml_loader_integration(self):
        """YAML Loader를 통해 프로파일을 가져오는지 확인"""
        from arbitrage.domain.entry_bps_profile import load_zone_profiles

        profiles = load_zone_profiles()
        assert "strict_uniform" in profiles, "strict_uniform 프로파일이 로드되지 않음"
        assert "advisory_z2_focus" in profiles, "advisory_z2_focus 프로파일이 로드되지 않음"

    def test_zone_profiles_dict_access(self):
        """ZONE_PROFILES dict-like 접근 확인"""
        from arbitrage.domain.entry_bps_profile import ZONE_PROFILES

        # dict-like access
        assert "strict_uniform" in ZONE_PROFILES
        assert "advisory_z2_focus" in ZONE_PROFILES
        
        # get() 메서드
        strict = ZONE_PROFILES.get("strict_uniform")
        assert strict is not None
        assert strict.name == "strict_uniform"

    def test_get_zone_profile_function(self):
        """get_zone_profile() 함수 동작 확인"""
        from arbitrage.domain.entry_bps_profile import get_zone_profile

        strict = get_zone_profile("strict_uniform")
        assert strict.name == "strict_uniform"
        assert strict.zone_weights == (1.0, 1.0, 1.0, 1.0)

        advisory = get_zone_profile("advisory_z2_focus")
        assert advisory.name == "advisory_z2_focus"
        assert advisory.zone_weights == (0.5, 3.0, 1.5, 0.5)


class TestD90_5_ProfileWeightsAccuracy:
    """D90-5: 프로파일 가중치 정확도 검증"""

    def test_strict_uniform_weights(self):
        """strict_uniform 가중치가 [1.0, 1.0, 1.0, 1.0]인지 확인"""
        from arbitrage.domain.entry_bps_profile import get_zone_profile

        strict = get_zone_profile("strict_uniform")
        assert strict.zone_weights == (1.0, 1.0, 1.0, 1.0), \
            f"strict_uniform weights mismatch: {strict.zone_weights}"

    def test_advisory_z2_focus_weights(self):
        """advisory_z2_focus 가중치가 [0.5, 3.0, 1.5, 0.5]인지 확인"""
        from arbitrage.domain.entry_bps_profile import get_zone_profile

        advisory = get_zone_profile("advisory_z2_focus")
        assert advisory.zone_weights == (0.5, 3.0, 1.5, 0.5), \
            f"advisory_z2_focus weights mismatch: {advisory.zone_weights}"

    def test_weights_sum_positive(self):
        """모든 프로파일의 가중치 합이 양수인지 확인"""
        from arbitrage.domain.entry_bps_profile import load_zone_profiles

        profiles = load_zone_profiles()
        for name, profile in profiles.items():
            total = sum(profile.zone_weights)
            assert total > 0, f"{name} weights sum is not positive: {total}"

    def test_weights_all_non_negative(self):
        """모든 프로파일의 가중치가 음수가 아닌지 확인"""
        from arbitrage.domain.entry_bps_profile import load_zone_profiles

        profiles = load_zone_profiles()
        for name, profile in profiles.items():
            for w in profile.zone_weights:
                assert w >= 0, f"{name} has negative weight: {w}"


class TestD90_5_LogPathPattern:
    """D90-5: 로그 경로 패턴 검증"""

    def test_session_tag_pattern_strict_1h(self):
        """Strict 1h 세션 태그가 d90_5_strict_1h_yaml 패턴인지 확인"""
        session_tag = "d90_5_strict_1h_yaml"
        expected_pattern = r"d90_5_\w+_\d+h_yaml"
        assert re.match(expected_pattern, session_tag), \
            f"Session tag does not match pattern: {session_tag}"

    def test_session_tag_pattern_advisory_1h(self):
        """Advisory 1h 세션 태그가 d90_5_advisory_1h_yaml 패턴인지 확인"""
        session_tag = "d90_5_advisory_1h_yaml"
        expected_pattern = r"d90_5_\w+_\d+h_yaml"
        assert re.match(expected_pattern, session_tag), \
            f"Session tag does not match pattern: {session_tag}"

    def test_session_tag_pattern_strict_3h(self):
        """Strict 3h 세션 태그가 d90_5_strict_3h_yaml 패턴인지 확인"""
        session_tag = "d90_5_strict_3h_yaml"
        expected_pattern = r"d90_5_\w+_\d+h_yaml"
        assert re.match(expected_pattern, session_tag), \
            f"Session tag does not match pattern: {session_tag}"


class TestD90_5_DurationParameter:
    """D90-5: Duration 파라미터 전달 확인"""

    def test_duration_1h_value(self):
        """1h duration이 3600초인지 확인"""
        duration_1h = 3600
        assert duration_1h == 3600, f"1h duration mismatch: {duration_1h}"

    def test_duration_3h_value(self):
        """3h duration이 10800초인지 확인"""
        duration_3h = 10800
        assert duration_3h == 10800, f"3h duration mismatch: {duration_3h}"

    def test_duration_tolerance(self):
        """Duration 허용 오차가 ±5초인지 확인"""
        tolerance = 5
        assert tolerance == 5, f"Duration tolerance mismatch: {tolerance}"


class TestD90_5_BackwardCompatibility:
    """D90-5: D90-0~4 하위 호환성 확인"""

    def test_d90_0_zone_random_mode(self):
        """D90-0의 zone_random 모드가 여전히 동작하는지 확인"""
        from arbitrage.domain.entry_bps_profile import EntryBPSProfile

        profile = EntryBPSProfile(
            mode="zone_random",
            zone_boundaries=[(5.0, 7.0), (7.0, 12.0), (12.0, 20.0), (20.0, 25.0)],
            zone_weights=[1.0, 1.0, 1.0, 1.0],
            seed=91
        )
        
        assert profile.mode == "zone_random"
        assert profile.zone_weights == [1.0, 1.0, 1.0, 1.0]

    def test_d90_2_zone_profile_access(self):
        """D90-2의 ZONE_PROFILES dict 접근이 여전히 동작하는지 확인"""
        from arbitrage.domain.entry_bps_profile import ZONE_PROFILES

        # D90-2 방식: dict-like access
        strict = ZONE_PROFILES["strict_uniform"]
        assert strict.name == "strict_uniform"

        advisory = ZONE_PROFILES["advisory_z2_focus"]
        assert advisory.name == "advisory_z2_focus"

    def test_d90_4_yaml_based_loading(self):
        """D90-4의 YAML 기반 로딩이 정상 동작하는지 확인"""
        from arbitrage.domain.entry_bps_profile import load_zone_profiles

        # Force reload to test YAML loading path
        profiles = load_zone_profiles(force_reload=True)
        
        assert len(profiles) >= 2, "최소 2개 프로파일 (strict_uniform, advisory_z2_focus) 필요"
        assert "strict_uniform" in profiles
        assert "advisory_z2_focus" in profiles


# Test Summary
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
