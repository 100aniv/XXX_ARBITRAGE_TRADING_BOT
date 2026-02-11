# -*- coding: utf-8 -*-
"""
D98-4: Live Key Guard 단위 테스트
=================================

LiveKeyGuard 모듈의 핵심 기능 단위 테스트.

Test Coverage:
--------------
1. detect_live_key() - 키 감지 로직
2. validate_live_keys() - 키 검증 로직
3. is_live_mode_allowed() - LIVE 모드 허용 여부
4. 다양한 환경/키 조합 시나리오

Test Philosophy:
----------------
- Fail-Closed: 의심스러운 키는 차단
- False Positive 허용 (안전 우선)
- False Negative 방지 (LIVE 키 놓치지 않음)
"""

import os
import pytest
from unittest.mock import patch

from arbitrage.config.live_key_guard import (
    RuntimeEnv,
    LiveKeyError,
    detect_live_key,
    validate_live_keys,
    is_live_mode_allowed,
    get_live_key_guard_status,
)


@pytest.fixture(autouse=True)
def _clear_skip_live_key_guard(monkeypatch):
    monkeypatch.delenv("SKIP_LIVE_KEY_GUARD", raising=False)


class TestDetectLiveKey:
    """detect_live_key() 함수 테스트"""
    
    def test_empty_key_returns_false(self):
        """빈 키는 Mock 모드로 간주 (안전)"""
        assert detect_live_key("UPBIT_ACCESS_KEY", "", RuntimeEnv.PAPER) is False
        assert detect_live_key("UPBIT_ACCESS_KEY", None, RuntimeEnv.PAPER) is False
    
    def test_test_pattern_keys_are_safe(self):
        """테스트 패턴 키는 안전으로 판단"""
        safe_keys = [
            "your_upbit_access_key_here",
            "test_key_123",
            "mock_api_key",
            "example_key",
            "dummy_secret",
            "fake_api_key_xyz",
            "sample_key_abc",
            "placeholder_key",
        ]
        
        for key in safe_keys:
            assert detect_live_key("UPBIT_ACCESS_KEY", key, RuntimeEnv.PAPER) is False
    
    def test_real_key_pattern_in_paper_mode_detected(self):
        """Paper 모드에서 실제 키 패턴 감지"""
        # 실제 키처럼 보이는 값 (영숫자 혼합, 20자 이상)
        suspicious_key = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        assert detect_live_key("UPBIT_ACCESS_KEY", suspicious_key, RuntimeEnv.PAPER) is True
    
    def test_real_key_pattern_in_local_dev_detected(self):
        """Local_dev 모드에서 실제 키 패턴 감지"""
        suspicious_key = "abc123def456ghi789jkl012mno345"
        assert detect_live_key("BINANCE_API_KEY", suspicious_key, RuntimeEnv.LOCAL_DEV) is True
    
    def test_real_key_in_live_mode_not_flagged(self):
        """Live 모드에서는 실제 키도 감지 안 함 (허용)"""
        real_key = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        # Live 모드에서는 detect_live_key가 False 반환 (검증 통과)
        # 하지만 현재 구현에서는 env != LIVE일 때만 체크하므로,
        # LIVE 모드에서는 이 함수가 True를 반환해도 validate_live_keys에서 허용됨
        assert detect_live_key("UPBIT_ACCESS_KEY", real_key, RuntimeEnv.LIVE) is False
    
    def test_short_key_not_flagged(self):
        """짧은 키는 실제 키가 아닌 것으로 간주"""
        short_key = "abc123"  # 20자 미만
        assert detect_live_key("UPBIT_ACCESS_KEY", short_key, RuntimeEnv.PAPER) is False


class TestValidateLiveKeys:
    """validate_live_keys() 함수 테스트"""
    
    def test_live_mode_with_live_enabled_allows_all_keys(self):
        """LIVE 모드 + LIVE_ENABLED=true → 모든 키 허용"""
        # 실제 키처럼 보이는 값도 허용
        validate_live_keys(
            env=RuntimeEnv.LIVE,
            live_enabled=True,
            upbit_access_key="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            binance_api_key="x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6",
        )
        # 예외 발생 안 하면 성공
    
    def test_paper_mode_with_test_keys_allowed(self):
        """Paper 모드 + 테스트 키 → 허용"""
        validate_live_keys(
            env=RuntimeEnv.PAPER,
            live_enabled=False,
            upbit_access_key="test_upbit_key",
            binance_api_key="mock_binance_key",
        )
        # 예외 발생 안 하면 성공
    
    def test_paper_mode_with_live_key_blocked(self):
        """Paper 모드 + LIVE 키 → 차단"""
        with pytest.raises(LiveKeyError) as exc_info:
            validate_live_keys(
                env=RuntimeEnv.PAPER,
                live_enabled=False,
                upbit_access_key="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",  # 실제 키 패턴
            )
        
        assert "LIVE UPBIT_ACCESS_KEY 감지" in str(exc_info.value)
        assert "Paper/테스트 환경에서는 테스트 키" in str(exc_info.value)
    
    def test_local_dev_with_live_key_blocked(self):
        """Local_dev 모드 + LIVE 키 → 차단"""
        with pytest.raises(LiveKeyError) as exc_info:
            validate_live_keys(
                env=RuntimeEnv.LOCAL_DEV,
                live_enabled=False,
                binance_api_key="x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6",  # 실제 키 패턴
            )
        
        assert "LIVE BINANCE_API_KEY 감지" in str(exc_info.value)
    
    def test_live_enabled_true_but_env_not_live_blocked(self):
        """LIVE_ENABLED=true 이지만 env != live → 차단"""
        with pytest.raises(LiveKeyError) as exc_info:
            validate_live_keys(
                env=RuntimeEnv.PAPER,
                live_enabled=True,  # LIVE 활성화
                upbit_access_key="test_key",
            )
        
        assert "환경 불일치" in str(exc_info.value)
        assert "LIVE_ENABLED=true" in str(exc_info.value)
        assert "ARBITRAGE_ENV=paper" in str(exc_info.value)
    
    def test_empty_keys_allowed_in_all_envs(self):
        """빈 키는 모든 환경에서 허용 (Mock 모드)"""
        for env in [RuntimeEnv.LOCAL_DEV, RuntimeEnv.PAPER, RuntimeEnv.LIVE]:
            validate_live_keys(
                env=env,
                live_enabled=False,
                upbit_access_key=None,
                binance_api_key="",
            )
            # 예외 발생 안 하면 성공
    
    def test_multiple_keys_one_suspicious_all_blocked(self):
        """여러 키 중 하나라도 의심스러우면 전체 차단"""
        with pytest.raises(LiveKeyError):
            validate_live_keys(
                env=RuntimeEnv.PAPER,
                live_enabled=False,
                upbit_access_key="test_key",  # 안전
                binance_api_key="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",  # 의심
            )


class TestIsLiveModeAllowed:
    """is_live_mode_allowed() 함수 테스트"""
    
    @patch.dict(os.environ, {"LIVE_ENABLED": "true", "ARBITRAGE_ENV": "live"})
    def test_live_mode_allowed_when_both_flags_set(self):
        """LIVE_ENABLED=true + ARBITRAGE_ENV=live → True"""
        assert is_live_mode_allowed() is True
    
    @patch.dict(os.environ, {"LIVE_ENABLED": "false", "ARBITRAGE_ENV": "live"})
    def test_live_mode_not_allowed_when_live_enabled_false(self):
        """LIVE_ENABLED=false → False (env=live여도)"""
        assert is_live_mode_allowed() is False
    
    @patch.dict(os.environ, {"LIVE_ENABLED": "true", "ARBITRAGE_ENV": "paper"})
    def test_live_mode_not_allowed_when_env_not_live(self):
        """ARBITRAGE_ENV != live → False (LIVE_ENABLED=true여도)"""
        assert is_live_mode_allowed() is False
    
    @patch.dict(os.environ, {}, clear=True)
    def test_live_mode_not_allowed_by_default(self):
        """환경변수 없으면 기본값 False (Fail-Closed)"""
        assert is_live_mode_allowed() is False
    
    @patch.dict(os.environ, {"LIVE_ENABLED": "1", "ARBITRAGE_ENV": "live"})
    def test_live_enabled_accepts_1_as_true(self):
        """LIVE_ENABLED=1도 true로 인식"""
        assert is_live_mode_allowed() is True
    
    @patch.dict(os.environ, {"LIVE_ENABLED": "yes", "ARBITRAGE_ENV": "live"})
    def test_live_enabled_accepts_yes_as_true(self):
        """LIVE_ENABLED=yes도 true로 인식"""
        assert is_live_mode_allowed() is True


class TestGetLiveKeyGuardStatus:
    """get_live_key_guard_status() 함수 테스트"""
    
    @patch.dict(os.environ, {"ARBITRAGE_ENV": "paper", "LIVE_ENABLED": "false"})
    def test_guard_status_returns_correct_info(self):
        """Guard 상태 정보 반환 확인"""
        status = get_live_key_guard_status()
        
        assert status["arbitrage_env"] == "paper"
        assert status["live_enabled"] == "false"
        assert status["live_mode_allowed"] is False
        assert status["guard_version"] == "D98-4"


class TestEdgeCases:
    """엣지 케이스 테스트"""
    
    def test_case_insensitive_test_pattern_detection(self):
        """대소문자 무시 테스트 패턴 감지"""
        assert detect_live_key("KEY", "YOUR_KEY_HERE", RuntimeEnv.PAPER) is False
        assert detect_live_key("KEY", "TEST_KEY_ABC", RuntimeEnv.PAPER) is False
        assert detect_live_key("KEY", "Mock_Api_Key", RuntimeEnv.PAPER) is False
    
    def test_numeric_only_key_not_flagged(self):
        """숫자만 있는 키는 실제 키 아님"""
        numeric_key = "12345678901234567890"
        assert detect_live_key("KEY", numeric_key, RuntimeEnv.PAPER) is False
    
    def test_alpha_only_key_not_flagged(self):
        """문자만 있는 키는 실제 키 아님"""
        alpha_key = "abcdefghijklmnopqrstuvwxyz"
        assert detect_live_key("KEY", alpha_key, RuntimeEnv.PAPER) is False
    
    def test_mixed_alphanumeric_20_chars_flagged(self):
        """영숫자 혼합 20자 이상 → 의심"""
        mixed_key = "abc123def456ghi789jk"  # 정확히 20자
        assert detect_live_key("KEY", mixed_key, RuntimeEnv.PAPER) is True
    
    def test_validate_handles_all_none_keys(self):
        """모든 키가 None이어도 에러 없음"""
        validate_live_keys(
            env=RuntimeEnv.LOCAL_DEV,
            live_enabled=False,
            upbit_access_key=None,
            upbit_secret_key=None,
            binance_api_key=None,
            binance_api_secret=None,
        )


class TestDefenseInDepth:
    """Defense-in-Depth 시나리오 테스트"""
    
    def test_paper_mode_catches_accidental_live_key_copy(self):
        """시나리오: 개발자가 .env.live 키를 실수로 복사"""
        # 실제 상황 시뮬레이션
        accidentally_copied_live_key = "AbC123DeF456GhI789JkL012MnO345PqR678"
        
        with pytest.raises(LiveKeyError) as exc_info:
            validate_live_keys(
                env=RuntimeEnv.PAPER,
                live_enabled=False,
                upbit_access_key=accidentally_copied_live_key,
            )
        
        assert "허용되지 않는 환경에서 LIVE" in str(exc_info.value)
    
    def test_ci_pipeline_with_wrong_secrets_blocked(self):
        """시나리오: CI 파이프라인에서 잘못된 secrets 주입"""
        # CI에서 실수로 LIVE secrets를 paper 환경에 주입
        ci_live_secret = "github_actions_live_key_abc123def456"
        
        with pytest.raises(LiveKeyError):
            validate_live_keys(
                env=RuntimeEnv.PAPER,
                live_enabled=False,
                binance_api_key=ci_live_secret,
            )
    
    def test_local_test_with_residual_live_env_blocked(self):
        """시나리오: 로컬 테스트에서 이전 LIVE 환경변수 잔존"""
        # pytest 실행 시 환경에 LIVE 키가 남아있는 경우
        # "test" 패턴 없이 실제 키처럼 보이는 값
        residual_live_key = "previous_live_production_xyz123abc456"
        
        with pytest.raises(LiveKeyError):
            validate_live_keys(
                env=RuntimeEnv.LOCAL_DEV,
                live_enabled=False,
                upbit_access_key=residual_live_key,
            )


class TestLiveKeyErrorMessage:
    """LiveKeyError 메시지 품질 테스트"""
    
    def test_error_message_contains_actionable_guidance(self):
        """에러 메시지에 해결 방법 포함 확인"""
        with pytest.raises(LiveKeyError) as exc_info:
            validate_live_keys(
                env=RuntimeEnv.PAPER,
                live_enabled=False,
                upbit_access_key="realkey123abc456def789ghi012jkl",
            )
        
        error_msg = str(exc_info.value)
        
        # 한국어 메시지 확인
        assert "허용되지 않는 환경에서" in error_msg
        assert "LIVE" in error_msg
        assert "현재 환경" in error_msg
        assert "ARBITRAGE_ENV=live + LIVE_ENABLED=true" in error_msg
        assert "Paper/테스트 환경에서는" in error_msg
    
    def test_env_mismatch_error_has_clear_message(self):
        """환경 불일치 에러 메시지 명확성 확인"""
        with pytest.raises(LiveKeyError) as exc_info:
            validate_live_keys(
                env=RuntimeEnv.PAPER,
                live_enabled=True,  # 불일치
                upbit_access_key="test_key",
            )
        
        error_msg = str(exc_info.value)
        assert "환경 불일치" in error_msg
        assert "LIVE_ENABLED=true" in error_msg
        assert "ARBITRAGE_ENV=paper" in error_msg
