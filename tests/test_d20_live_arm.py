#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D20 LIVE ARM System Tests

LIVE ARM 시스템 검증:
- ARM 파일 + ARM 토큰 기반의 2단계 무장 시스템
- Live 모드는 ARM 조건을 모두 만족할 때만 활성화
- ARM 실패 시 무조건 Shadow Live Mode로 강등
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from arbitrage.live_trader import LiveTrader
from liveguard.risk_limits import RiskLimits


class TestLiveArmingBasic:
    """LIVE ARM 기본 동작 테스트"""
    
    def test_arm_file_not_exists_arm_token_not_set(self):
        """ARM 파일 없음 + 토큰 미설정 → live_armed=False"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # Act
        with patch.dict('os.environ', {
            'LIVE_MODE': 'true',
            'SAFETY_MODE': 'true',
            'DRY_RUN': 'false',
            'LIVE_ARM_FILE': '/nonexistent/path/LIVE_ARMED',
            'LIVE_ARM_TOKEN': ''  # 토큰 미설정
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=True,
                safety_mode=True,
                dry_run=False
            )
        
        # Assert
        assert trader.live_armed == False
        assert trader.live_enabled == False
    
    def test_arm_file_exists_arm_token_not_set(self, tmp_path):
        """ARM 파일 존재 + 토큰 미설정 → live_armed=False"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # ARM 파일 생성
        arm_file = tmp_path / "LIVE_ARMED"
        arm_file.write_text("armed")
        
        # Act
        with patch.dict('os.environ', {
            'LIVE_MODE': 'true',
            'SAFETY_MODE': 'true',
            'DRY_RUN': 'false',
            'LIVE_ARM_FILE': str(arm_file),
            'LIVE_ARM_TOKEN': ''  # 토큰 미설정
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=True,
                safety_mode=True,
                dry_run=False
            )
        
        # Assert
        assert trader.live_armed == False
        assert trader.live_enabled == False
    
    def test_arm_file_not_exists_arm_token_valid(self):
        """ARM 파일 없음 + 토큰 유효 → live_armed=False"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # Act
        with patch.dict('os.environ', {
            'LIVE_MODE': 'true',
            'SAFETY_MODE': 'true',
            'DRY_RUN': 'false',
            'LIVE_ARM_FILE': '/nonexistent/path/LIVE_ARMED',
            'LIVE_ARM_TOKEN': 'I_UNDERSTAND_LIVE_RISK'  # 토큰 유효
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=True,
                safety_mode=True,
                dry_run=False
            )
        
        # Assert
        assert trader.live_armed == False
        assert trader.live_enabled == False
    
    def test_arm_file_exists_arm_token_valid(self, tmp_path):
        """ARM 파일 존재 + 토큰 유효 → live_armed=True"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # ARM 파일 생성
        arm_file = tmp_path / "LIVE_ARMED"
        arm_file.write_text("armed")
        
        # Act
        with patch.dict('os.environ', {
            'LIVE_MODE': 'true',
            'SAFETY_MODE': 'true',
            'DRY_RUN': 'false',
            'LIVE_ARM_FILE': str(arm_file),
            'LIVE_ARM_TOKEN': 'I_UNDERSTAND_LIVE_RISK'  # 토큰 유효
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=True,
                safety_mode=True,
                dry_run=False
            )
        
        # Assert
        assert trader.live_armed == True
        assert trader.live_enabled == True


class TestLiveArmingWithFlagCombinations:
    """ARM 조건과 Live 플래그 조합 테스트"""
    
    def test_live_mode_false_arm_satisfied(self, tmp_path):
        """LIVE_MODE=false인데 ARM이 되어 있는 경우 → live_enabled=False"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # ARM 파일 생성
        arm_file = tmp_path / "LIVE_ARMED"
        arm_file.write_text("armed")
        
        # Act
        with patch.dict('os.environ', {
            'LIVE_MODE': 'false',  # Live 모드 요청 안 함
            'SAFETY_MODE': 'true',
            'DRY_RUN': 'false',
            'LIVE_ARM_FILE': str(arm_file),
            'LIVE_ARM_TOKEN': 'I_UNDERSTAND_LIVE_RISK'
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=False,
                safety_mode=True,
                dry_run=False
            )
        
        # Assert
        # ARM은 True일 수 있지만, Live 모드 요청이 아니므로 live_enabled=False
        assert trader.live_armed == True
        assert trader.live_enabled == False
    
    def test_dry_run_true_arm_satisfied(self, tmp_path):
        """DRY_RUN=true인데 ARM이 되어 있는 경우 → live_enabled=False"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # ARM 파일 생성
        arm_file = tmp_path / "LIVE_ARMED"
        arm_file.write_text("armed")
        
        # Act
        with patch.dict('os.environ', {
            'LIVE_MODE': 'true',
            'SAFETY_MODE': 'true',
            'DRY_RUN': 'true',  # 드라이런 모드
            'LIVE_ARM_FILE': str(arm_file),
            'LIVE_ARM_TOKEN': 'I_UNDERSTAND_LIVE_RISK'
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=True,
                safety_mode=True,
                dry_run=True
            )
        
        # Assert
        # ARM은 True일 수 있지만, DRY_RUN=true이므로 live_enabled=False
        assert trader.live_armed == True
        assert trader.live_enabled == False
    
    def test_safety_mode_false_arm_satisfied(self, tmp_path):
        """SAFETY_MODE=false인데 ARM이 되어 있는 경우 → live_enabled=False"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # ARM 파일 생성
        arm_file = tmp_path / "LIVE_ARMED"
        arm_file.write_text("armed")
        
        # Act
        with patch.dict('os.environ', {
            'LIVE_MODE': 'true',
            'SAFETY_MODE': 'false',  # 안전 모드 비활성화
            'DRY_RUN': 'false',
            'LIVE_ARM_FILE': str(arm_file),
            'LIVE_ARM_TOKEN': 'I_UNDERSTAND_LIVE_RISK'
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=True,
                safety_mode=False,
                dry_run=False
            )
        
        # Assert
        # ARM은 True일 수 있지만, SAFETY_MODE=false이므로 live_enabled=False
        assert trader.live_armed == True
        assert trader.live_enabled == False


class TestLiveArmingTokenValidation:
    """ARM 토큰 검증 테스트"""
    
    def test_arm_token_wrong_value(self, tmp_path):
        """ARM 토큰이 잘못된 값 → live_armed=False"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # ARM 파일 생성
        arm_file = tmp_path / "LIVE_ARMED"
        arm_file.write_text("armed")
        
        # Act
        with patch.dict('os.environ', {
            'LIVE_MODE': 'true',
            'SAFETY_MODE': 'true',
            'DRY_RUN': 'false',
            'LIVE_ARM_FILE': str(arm_file),
            'LIVE_ARM_TOKEN': 'WRONG_TOKEN'  # 잘못된 토큰
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=True,
                safety_mode=True,
                dry_run=False
            )
        
        # Assert
        assert trader.live_armed == False
        assert trader.live_enabled == False
    
    def test_arm_token_case_sensitive(self, tmp_path):
        """ARM 토큰은 대소문자 구분 → live_armed=False"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # ARM 파일 생성
        arm_file = tmp_path / "LIVE_ARMED"
        arm_file.write_text("armed")
        
        # Act
        with patch.dict('os.environ', {
            'LIVE_MODE': 'true',
            'SAFETY_MODE': 'true',
            'DRY_RUN': 'false',
            'LIVE_ARM_FILE': str(arm_file),
            'LIVE_ARM_TOKEN': 'i_understand_live_risk'  # 소문자 (잘못됨)
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=True,
                safety_mode=True,
                dry_run=False
            )
        
        # Assert
        assert trader.live_armed == False
        assert trader.live_enabled == False


class TestLiveArmingDefaultValues:
    """ARM 기본값 테스트"""
    
    def test_arm_file_default_path(self):
        """ARM 파일 기본 경로: configs/LIVE_ARMED"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # Act - LIVE_ARM_FILE 환경 변수 미설정 (기본값 사용)
        with patch.dict('os.environ', {
            'LIVE_MODE': 'true',
            'SAFETY_MODE': 'true',
            'DRY_RUN': 'false',
            # LIVE_ARM_FILE 미설정 (기본값: configs/LIVE_ARMED)
            'LIVE_ARM_TOKEN': 'I_UNDERSTAND_LIVE_RISK'
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=True,
                safety_mode=True,
                dry_run=False
            )
        
        # Assert
        # 기본 경로 configs/LIVE_ARMED가 존재하지 않으므로 live_armed=False
        assert trader.live_armed == False
        assert trader.live_enabled == False
    
    def test_arm_token_default_empty(self):
        """ARM 토큰 기본값: 빈 문자열"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # Act - LIVE_ARM_TOKEN 환경 변수 미설정 (기본값: 빈 문자열)
        with patch.dict('os.environ', {
            'LIVE_MODE': 'true',
            'SAFETY_MODE': 'true',
            'DRY_RUN': 'false',
            'LIVE_ARM_FILE': '/nonexistent/path/LIVE_ARMED'
            # LIVE_ARM_TOKEN 미설정 (기본값: 빈 문자열)
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=True,
                safety_mode=True,
                dry_run=False
            )
        
        # Assert
        # 토큰이 빈 문자열이므로 live_armed=False
        assert trader.live_armed == False
        assert trader.live_enabled == False


class TestLiveArmingWithShadowMode:
    """ARM 상태와 Shadow Mode 동작 테스트"""
    
    def test_shadow_mode_when_arm_not_satisfied(self):
        """ARM이 안 되어 있으면 무조건 Shadow Mode"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # Act - Live 모드 요청이지만 ARM 미충족
        with patch.dict('os.environ', {
            'LIVE_MODE': 'true',
            'SAFETY_MODE': 'true',
            'DRY_RUN': 'false',
            'LIVE_ARM_FILE': '/nonexistent/path/LIVE_ARMED',
            'LIVE_ARM_TOKEN': ''
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=True,
                safety_mode=True,
                dry_run=False
            )
        
        # Assert
        assert trader.live_enabled == False
        # Shadow Mode 경로를 사용해야 함 (실제 주문 API 호출 안 함)


class TestLiveArmingIntegration:
    """ARM 시스템 통합 테스트"""
    
    def test_all_conditions_satisfied_with_arm(self, tmp_path):
        """모든 Live 조건 + ARM 조건 만족 → live_enabled=True"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # ARM 파일 생성
        arm_file = tmp_path / "LIVE_ARMED"
        arm_file.write_text("armed")
        
        # Act
        with patch.dict('os.environ', {
            'LIVE_MODE': 'true',
            'SAFETY_MODE': 'true',
            'DRY_RUN': 'false',
            'LIVE_ARM_FILE': str(arm_file),
            'LIVE_ARM_TOKEN': 'I_UNDERSTAND_LIVE_RISK'
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=True,
                safety_mode=True,
                dry_run=False
            )
        
        # Assert
        assert trader.live_mode == True
        assert trader.safety_mode == True
        assert trader.dry_run == False
        assert trader.live_armed == True
        assert trader.live_enabled == True
    
    def test_missing_one_condition_fails(self, tmp_path):
        """하나의 조건만 빠져도 live_enabled=False"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # ARM 파일 생성
        arm_file = tmp_path / "LIVE_ARMED"
        arm_file.write_text("armed")
        
        # Act - API 키 미설정
        with patch.dict('os.environ', {
            'LIVE_MODE': 'true',
            'SAFETY_MODE': 'true',
            'DRY_RUN': 'false',
            'LIVE_ARM_FILE': str(arm_file),
            'LIVE_ARM_TOKEN': 'I_UNDERSTAND_LIVE_RISK'
        }, clear=False):
            trader = LiveTrader(
                upbit_api_key="",  # 빈 API 키
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=risk_limits,
                live_mode=True,
                safety_mode=True,
                dry_run=False
            )
        
        # Assert
        # API 키 미설정으로 인해 live_enabled=False
        assert trader.live_enabled == False
