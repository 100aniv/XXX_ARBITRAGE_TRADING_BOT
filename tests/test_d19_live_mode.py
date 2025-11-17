#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D19 Live Trading Mode Safety Validation Tests

Live Mode 안전 검증:
- Paper Mode: SimulatedExchange + 시나리오 (D17/D18)
- Shadow Live Mode: 실시간 가격 + 신호 생성 + 주문 로그만 기록
- Live Mode: 실제 Upbit/Binance 주문 발행 (엄격한 조건 충족 시에만)

Note: D20에서 ARM 시스템이 추가되었으므로, 
      Live Mode 테스트에서는 ARM 조건도 만족해야 live_enabled=True가 됨
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from arbitrage.live_trader import LiveTrader
from liveguard.risk_limits import RiskLimits
from arbitrage.types import Signal, OrderSide, ExchangeType


class TestLiveModeShadowMode:
    """Shadow Live Mode 테스트 (LIVE_MODE=false, DRY_RUN=true)"""
    
    def test_shadow_mode_when_live_mode_false(self):
        """LIVE_MODE=false일 때 Shadow Mode로 동작"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # Act
        trader = LiveTrader(
            upbit_api_key="test_key",
            upbit_secret_key="test_secret",
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            risk_limits=risk_limits,
            live_mode=False,  # Shadow Mode
            safety_mode=True,
            dry_run=True
        )
        
        # Assert
        assert trader.live_mode == False
        assert trader.live_enabled == False
        assert trader.safety_mode == True
        assert trader.dry_run == True
    
    def test_shadow_mode_when_dry_run_true(self):
        """DRY_RUN=true일 때 Shadow Mode로 동작"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # Act
        trader = LiveTrader(
            upbit_api_key="test_key",
            upbit_secret_key="test_secret",
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            risk_limits=risk_limits,
            live_mode=True,
            safety_mode=True,
            dry_run=True  # DRY_RUN=true → Shadow Mode
        )
        
        # Assert
        assert trader.live_enabled == False
    
    @pytest.mark.asyncio
    async def test_shadow_mode_logs_orders_only(self):
        """Shadow Mode에서 주문을 로그만 남기고 실행하지 않음"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        trader = LiveTrader(
            upbit_api_key="test_key",
            upbit_secret_key="test_secret",
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            risk_limits=risk_limits,
            live_mode=False,
            safety_mode=True,
            dry_run=True
        )
        
        # Mock StateManager
        trader.state_manager = Mock()
        trader.state_manager.set_order = Mock()
        
        # Act
        order = await trader._place_order(
            exchange=ExchangeType.UPBIT,
            symbol="BTC",
            side=OrderSide.BUY,
            quantity=1.0,
            price=50000000
        )
        
        # Assert
        assert order is not None
        assert order.status == "filled"
        assert order.filled_quantity == 1.0
        # Mock order 반환 (실제 거래 아님)
        assert "mock_" in order.order_id


class TestLiveModeRequirements:
    """Live Mode 진입 조건 테스트"""
    
    def test_live_mode_requires_safety_mode(self):
        """LIVE_MODE=true이지만 SAFETY_MODE=false면 Shadow Mode"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # Act
        trader = LiveTrader(
            upbit_api_key="test_key",
            upbit_secret_key="test_secret",
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            risk_limits=risk_limits,
            live_mode=True,
            safety_mode=False,  # Safety Mode 비활성화
            dry_run=False
        )
        
        # Assert
        assert trader.live_enabled == False
    
    def test_live_mode_requires_api_keys(self):
        """API 키가 없으면 Live Mode 진입 불가"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # Act
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
        assert trader.live_enabled == False
    
    def test_live_mode_requires_risk_limits(self):
        """RiskLimits가 없으면 Live Mode 진입 불가"""
        # Act
        trader = LiveTrader(
            upbit_api_key="test_key",
            upbit_secret_key="test_secret",
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            risk_limits=None,  # RiskLimits 없음
            live_mode=True,
            safety_mode=True,
            dry_run=False
        )
        
        # Assert
        assert trader.live_enabled == False
    
    def test_live_mode_requires_valid_risk_limits(self):
        """RiskLimits 값이 유효해야 Live Mode 진입 가능"""
        # Arrange
        invalid_limits = RiskLimits(
            max_position_size=0,  # 유효하지 않은 값
            max_daily_loss=500000
        )
        
        # Act & Assert - SafetyModule이 유효하지 않은 RiskLimits로 예외를 던짐
        with pytest.raises(ValueError, match="Invalid risk limits"):
            trader = LiveTrader(
                upbit_api_key="test_key",
                upbit_secret_key="test_secret",
                binance_api_key="test_key",
                binance_secret_key="test_secret",
                risk_limits=invalid_limits,
                live_mode=True,
                safety_mode=True,
                dry_run=False
            )
    
    def test_live_mode_all_conditions_satisfied(self, tmp_path):
        """모든 조건을 만족하면 Live Mode 활성화 (D20: ARM 조건 포함)"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # ARM 파일 생성 (D20)
        arm_file = tmp_path / "LIVE_ARMED"
        arm_file.write_text("armed")
        
        # Act
        with patch.dict('os.environ', {
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
                dry_run=False  # 모든 조건 만족
            )
        
        # Assert
        assert trader.live_enabled == True
        assert trader.live_mode == True
        assert trader.safety_mode == True
        assert trader.dry_run == False
        assert trader.live_armed == True


class TestLiveModeSafetyGate:
    """Live Mode 안전 게이트 테스트"""
    
    def test_circuit_breaker_blocks_live_orders(self, tmp_path):
        """회로차단기 활성화 시 Live Mode 주문 차단 (D20: ARM 조건 포함)"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # ARM 파일 생성 (D20)
        arm_file = tmp_path / "LIVE_ARMED"
        arm_file.write_text("armed")
        
        with patch.dict('os.environ', {
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
        
        # Verify Live Mode is enabled
        assert trader.live_enabled == True
        
        # Mock SafetyModule with active circuit breaker
        trader.safety.state.circuit_breaker_active = True
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="Circuit breaker is active"):
            trader._assert_live_mode_safety()
    
    def test_daily_loss_limit_blocks_live_orders(self, tmp_path):
        """일일 손실 제한 초과 시 Live Mode 주문 차단 (D20: ARM 조건 포함)"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # ARM 파일 생성 (D20)
        arm_file = tmp_path / "LIVE_ARMED"
        arm_file.write_text("armed")
        
        with patch.dict('os.environ', {
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
        
        # Verify Live Mode is enabled
        assert trader.live_enabled == True
        
        # Mock SafetyModule with exceeded daily loss
        trader.safety.state.daily_loss = 600000  # 제한(500000) 초과
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="Daily loss limit exceeded"):
            trader._assert_live_mode_safety()


class TestLiveModeMetrics:
    """Live Mode 메트릭 업데이트 테스트"""
    
    @pytest.mark.asyncio
    async def test_live_mode_updates_metrics(self):
        """Live Mode 메트릭이 StateManager에 저장됨"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        trader = LiveTrader(
            upbit_api_key="test_key",
            upbit_secret_key="test_secret",
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            risk_limits=risk_limits,
            live_mode=False,
            safety_mode=True,
            dry_run=True
        )
        
        # Mock StateManager
        trader.state_manager = Mock()
        trader.state_manager.set_metrics = Mock()
        trader.state_manager.set_heartbeat = Mock()
        
        # Act
        await trader._update_metrics()
        
        # Assert
        trader.state_manager.set_metrics.assert_called_once()
        call_args = trader.state_manager.set_metrics.call_args
        
        # 첫 번째 인자는 "live_trader"
        assert call_args[0][0] == "live_trader"
        
        # 두 번째 인자는 메트릭 딕셔너리
        metrics = call_args[0][1]
        assert "live_mode" in metrics
        assert "live_enabled" in metrics
        assert "safety_mode" in metrics
        assert "dry_run" in metrics
        assert "circuit_breaker_active" in metrics
        
        # Heartbeat도 설정됨
        trader.state_manager.set_heartbeat.assert_called_once_with("live_trader")


class TestLiveModeEnvironmentVariables:
    """Live Mode 환경 변수 테스트"""
    
    def test_live_mode_from_env_variables(self, tmp_path):
        """환경 변수에서 Live Mode 설정 읽기 (D20: ARM 조건 포함)"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # ARM 파일 생성 (D20)
        arm_file = tmp_path / "LIVE_ARMED"
        arm_file.write_text("armed")
        
        # Act - 명시적으로 파라미터를 False로 설정하여 환경 변수를 읽도록 함
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
                live_mode=False,  # 환경 변수 읽도록 False로 설정
                safety_mode=False,  # 환경 변수 읽도록 False로 설정
                dry_run=True  # 환경 변수 읽도록 True로 설정
            )
        
        # Assert
        assert trader.live_mode == True
        assert trader.safety_mode == True
        assert trader.dry_run == False
        assert trader.live_armed == True
        assert trader.live_enabled == True
    
    @patch.dict('os.environ', {'LIVE_MODE': 'false'})
    def test_shadow_mode_from_env_variables(self):
        """환경 변수에서 Shadow Mode 설정 읽기"""
        # Arrange
        risk_limits = RiskLimits(
            max_position_size=1000000,
            max_daily_loss=500000
        )
        
        # Act
        trader = LiveTrader(
            upbit_api_key="test_key",
            upbit_secret_key="test_secret",
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            risk_limits=risk_limits
        )
        
        # Assert
        assert trader.live_mode == False
        assert trader.live_enabled == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
