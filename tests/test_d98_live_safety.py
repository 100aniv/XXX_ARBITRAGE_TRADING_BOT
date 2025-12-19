"""
D98-0: LIVE Safety 안전장치 테스트

Fail-Closed 원칙 검증:
- 기본 케이스는 차단되어야 PASS
- 모든 조건 만족 시만 허용
"""

import os
import time
import pytest
from unittest.mock import patch, MagicMock

from arbitrage.config.live_safety import (
    LiveSafetyValidator,
    LiveSafetyError,
    check_live_mode_safety,
    is_live_mode_armed,
)


class TestLiveSafetyValidator:
    """LIVE 모드 안전 검증기 테스트"""
    
    def setup_method(self):
        """테스트 전 환경변수 정리"""
        # LIVE 관련 환경변수 제거
        for key in ["LIVE_ARM_ACK", "LIVE_ARM_AT", "LIVE_MAX_NOTIONAL_USD"]:
            os.environ.pop(key, None)
    
    def teardown_method(self):
        """테스트 후 환경변수 정리"""
        for key in ["LIVE_ARM_ACK", "LIVE_ARM_AT", "LIVE_MAX_NOTIONAL_USD"]:
            os.environ.pop(key, None)
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_paper_mode_always_allowed(self, mock_get_settings):
        """PAPER 모드는 항상 허용"""
        # Given: PAPER 모드
        mock_settings = MagicMock()
        mock_settings.env = "paper"
        mock_get_settings.return_value = mock_settings
        
        # When
        validator = LiveSafetyValidator()
        is_valid, error_message = validator.validate_live_mode()
        
        # Then
        assert is_valid is True
        assert error_message == ""
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_live_mode_blocked_by_default(self, mock_get_settings):
        """LIVE 모드는 기본적으로 차단 (Fail-Closed)"""
        # Given: LIVE 모드, 환경변수 없음
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        # When
        validator = LiveSafetyValidator()
        is_valid, error_message = validator.validate_live_mode()
        
        # Then
        assert is_valid is False
        assert "LIVE_ARM_ACK" in error_message
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_live_mode_blocked_without_ack(self, mock_get_settings):
        """LIVE 모드: ACK 없으면 차단"""
        # Given: LIVE 모드, ACK 없음
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        os.environ["LIVE_ARM_AT"] = str(int(time.time()))
        os.environ["LIVE_MAX_NOTIONAL_USD"] = "100.0"
        
        # When
        validator = LiveSafetyValidator()
        is_valid, error_message = validator.validate_live_mode()
        
        # Then
        assert is_valid is False
        assert "LIVE_ARM_ACK" in error_message
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_live_mode_blocked_with_wrong_ack(self, mock_get_settings):
        """LIVE 모드: 잘못된 ACK는 차단"""
        # Given: LIVE 모드, 잘못된 ACK
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        os.environ["LIVE_ARM_ACK"] = "wrong_value"
        os.environ["LIVE_ARM_AT"] = str(int(time.time()))
        os.environ["LIVE_MAX_NOTIONAL_USD"] = "100.0"
        
        # When
        validator = LiveSafetyValidator()
        is_valid, error_message = validator.validate_live_mode()
        
        # Then
        assert is_valid is False
        assert "LIVE_ARM_ACK" in error_message
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_live_mode_blocked_without_timestamp(self, mock_get_settings):
        """LIVE 모드: 타임스탬프 없으면 차단"""
        # Given: LIVE 모드, 타임스탬프 없음
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        os.environ["LIVE_ARM_ACK"] = "I_UNDERSTAND_LIVE_RISK"
        os.environ["LIVE_MAX_NOTIONAL_USD"] = "100.0"
        
        # When
        validator = LiveSafetyValidator()
        is_valid, error_message = validator.validate_live_mode()
        
        # Then
        assert is_valid is False
        assert "LIVE_ARM_AT" in error_message
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_live_mode_blocked_with_invalid_timestamp(self, mock_get_settings):
        """LIVE 모드: 잘못된 타임스탬프는 차단"""
        # Given: LIVE 모드, 잘못된 타임스탬프
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        os.environ["LIVE_ARM_ACK"] = "I_UNDERSTAND_LIVE_RISK"
        os.environ["LIVE_ARM_AT"] = "not_a_number"
        os.environ["LIVE_MAX_NOTIONAL_USD"] = "100.0"
        
        # When
        validator = LiveSafetyValidator()
        is_valid, error_message = validator.validate_live_mode()
        
        # Then
        assert is_valid is False
        assert "LIVE_ARM_AT" in error_message
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_live_mode_blocked_with_old_timestamp(self, mock_get_settings):
        """LIVE 모드: 10분 이상 된 타임스탬프는 차단"""
        # Given: LIVE 모드, 오래된 타임스탬프
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        old_timestamp = int(time.time()) - 700  # 11분 전
        os.environ["LIVE_ARM_ACK"] = "I_UNDERSTAND_LIVE_RISK"
        os.environ["LIVE_ARM_AT"] = str(old_timestamp)
        os.environ["LIVE_MAX_NOTIONAL_USD"] = "100.0"
        
        # When
        validator = LiveSafetyValidator()
        is_valid, error_message = validator.validate_live_mode()
        
        # Then
        assert is_valid is False
        assert "너무 오래되었습니다" in error_message
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_live_mode_blocked_without_max_notional(self, mock_get_settings):
        """LIVE 모드: MAX_NOTIONAL 없으면 차단"""
        # Given: LIVE 모드, MAX_NOTIONAL 없음
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        os.environ["LIVE_ARM_ACK"] = "I_UNDERSTAND_LIVE_RISK"
        os.environ["LIVE_ARM_AT"] = str(int(time.time()))
        
        # When
        validator = LiveSafetyValidator()
        is_valid, error_message = validator.validate_live_mode()
        
        # Then
        assert is_valid is False
        assert "LIVE_MAX_NOTIONAL_USD" in error_message
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_live_mode_blocked_with_invalid_max_notional(self, mock_get_settings):
        """LIVE 모드: 잘못된 MAX_NOTIONAL은 차단"""
        # Given: LIVE 모드, 잘못된 MAX_NOTIONAL
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        os.environ["LIVE_ARM_ACK"] = "I_UNDERSTAND_LIVE_RISK"
        os.environ["LIVE_ARM_AT"] = str(int(time.time()))
        os.environ["LIVE_MAX_NOTIONAL_USD"] = "not_a_number"
        
        # When
        validator = LiveSafetyValidator()
        is_valid, error_message = validator.validate_live_mode()
        
        # Then
        assert is_valid is False
        assert "유효한 숫자가 아닙니다" in error_message
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_live_mode_blocked_with_too_small_notional(self, mock_get_settings):
        """LIVE 모드: 너무 작은 MAX_NOTIONAL은 차단"""
        # Given: LIVE 모드, 너무 작은 MAX_NOTIONAL
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        os.environ["LIVE_ARM_ACK"] = "I_UNDERSTAND_LIVE_RISK"
        os.environ["LIVE_ARM_AT"] = str(int(time.time()))
        os.environ["LIVE_MAX_NOTIONAL_USD"] = "5.0"  # < MIN (10.0)
        
        # When
        validator = LiveSafetyValidator()
        is_valid, error_message = validator.validate_live_mode()
        
        # Then
        assert is_valid is False
        assert "너무 작습니다" in error_message
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_live_mode_blocked_with_too_large_notional(self, mock_get_settings):
        """LIVE 모드: 너무 큰 MAX_NOTIONAL은 차단"""
        # Given: LIVE 모드, 너무 큰 MAX_NOTIONAL
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        os.environ["LIVE_ARM_ACK"] = "I_UNDERSTAND_LIVE_RISK"
        os.environ["LIVE_ARM_AT"] = str(int(time.time()))
        os.environ["LIVE_MAX_NOTIONAL_USD"] = "2000.0"  # > MAX (1000.0)
        
        # When
        validator = LiveSafetyValidator()
        is_valid, error_message = validator.validate_live_mode()
        
        # Then
        assert is_valid is False
        assert "너무 큽니다" in error_message
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_live_mode_allowed_with_all_conditions(self, mock_get_settings):
        """LIVE 모드: 모든 조건 만족 시 허용"""
        # Given: LIVE 모드, 모든 조건 만족
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        os.environ["LIVE_ARM_ACK"] = "I_UNDERSTAND_LIVE_RISK"
        os.environ["LIVE_ARM_AT"] = str(int(time.time()))
        os.environ["LIVE_MAX_NOTIONAL_USD"] = "100.0"
        
        # When
        validator = LiveSafetyValidator()
        is_valid, error_message = validator.validate_live_mode()
        
        # Then
        assert is_valid is True
        assert error_message == ""
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_enforce_live_mode_safety_raises_on_fail(self, mock_get_settings):
        """enforce_live_mode_safety는 실패 시 예외 발생"""
        # Given: LIVE 모드, 조건 불만족
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        # When/Then
        validator = LiveSafetyValidator()
        with pytest.raises(LiveSafetyError):
            validator.enforce_live_mode_safety()
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_check_live_mode_safety_function(self, mock_get_settings):
        """check_live_mode_safety 함수 테스트"""
        # Given: LIVE 모드, 조건 불만족
        mock_settings = MagicMock()
        mock_settings.env = "live"
        mock_get_settings.return_value = mock_settings
        
        # When/Then
        with pytest.raises(LiveSafetyError):
            check_live_mode_safety()
    
    @patch("arbitrage.config.live_safety.get_settings")
    def test_is_live_mode_armed_function(self, mock_get_settings):
        """is_live_mode_armed 함수 테스트"""
        # Given: PAPER 모드
        mock_settings = MagicMock()
        mock_settings.env = "paper"
        mock_get_settings.return_value = mock_settings
        
        # When
        is_armed = is_live_mode_armed()
        
        # Then
        assert is_armed is True
