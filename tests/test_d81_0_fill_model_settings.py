# -*- coding: utf-8 -*-
"""
D81-0: FillModelConfig + Settings 통합 테스트

목적:
    .env 환경변수 → FillModelConfig 매핑이 정상 동작하는지 검증.

Author: arbitrage-lite project
Date: 2025-12-04
"""

import os
import pytest
from unittest.mock import patch

from arbitrage.config.settings import Settings, FillModelConfig, RuntimeEnv


class TestFillModelSettings:
    """FillModelConfig + Settings 통합 테스트"""
    
    def test_fill_model_config_default_values(self):
        """
        테스트 1: FillModelConfig 기본값 확인
        
        기대 결과:
            - enable_fill_model=True
            - enable_partial_fill=True
            - enable_slippage=True
            - slippage_alpha=0.0001
            - fill_model_type="simple"
            - available_volume_factor=2.0
        """
        config = FillModelConfig()
        
        assert config.enable_fill_model is True
        assert config.enable_partial_fill is True
        assert config.enable_slippage is True
        assert config.slippage_alpha == 0.0001
        assert config.fill_model_type == "simple"
        assert config.available_volume_factor == 2.0
    
    def test_settings_paper_env_fill_model_enabled_by_default(self):
        """
        테스트 2: PAPER 환경에서 Fill Model 기본 활성화
        
        조건:
            - ARBITRAGE_ENV=paper
            - Fill Model 환경변수 없음
        
        기대 결과:
            - fill_model.enable_fill_model=True (PAPER 기본값)
        """
        with patch.dict(os.environ, {
            "ARBITRAGE_ENV": "paper",
            "UPBIT_ACCESS_KEY": "test_upbit_key",
            "UPBIT_SECRET_KEY": "test_upbit_secret",
            "TELEGRAM_BOT_TOKEN": "test_telegram_token",
            "TELEGRAM_CHAT_ID": "test_chat_id",
        }, clear=True):
            settings = Settings.from_env()
            
            assert settings.env == RuntimeEnv.PAPER
            assert settings.fill_model.enable_fill_model is True
            assert settings.fill_model.enable_partial_fill is True
            assert settings.fill_model.enable_slippage is True
            assert settings.fill_model.slippage_alpha == 0.0001
    
    def test_settings_local_dev_fill_model_disabled_by_default(self):
        """
        테스트 3: LOCAL_DEV 환경에서 Fill Model 기본 비활성화
        
        조건:
            - ARBITRAGE_ENV=local_dev
            - Fill Model 환경변수 없음
        
        기대 결과:
            - fill_model.enable_fill_model=False (LOCAL_DEV 기본값)
        """
        with patch.dict(os.environ, {
            "ARBITRAGE_ENV": "local_dev",
        }, clear=True):
            settings = Settings.from_env()
            
            assert settings.env == RuntimeEnv.LOCAL_DEV
            assert settings.fill_model.enable_fill_model is False
    
    def test_settings_fill_model_env_vars_override(self):
        """
        테스트 4: 환경변수로 Fill Model 설정 오버라이드
        
        조건:
            - FILL_MODEL_ENABLE=true
            - FILL_MODEL_SLIPPAGE_ALPHA=0.0005
            - FILL_MODEL_AVAILABLE_VOLUME_FACTOR=3.0
        
        기대 결과:
            - 환경변수 값이 정상 반영됨
        """
        with patch.dict(os.environ, {
            "ARBITRAGE_ENV": "local_dev",
            "FILL_MODEL_ENABLE": "true",
            "FILL_MODEL_PARTIAL_ENABLE": "false",
            "FILL_MODEL_SLIPPAGE_ENABLE": "true",
            "FILL_MODEL_SLIPPAGE_ALPHA": "0.0005",
            "FILL_MODEL_TYPE": "advanced",
            "FILL_MODEL_AVAILABLE_VOLUME_FACTOR": "3.0",
        }, clear=True):
            settings = Settings.from_env()
            
            assert settings.fill_model.enable_fill_model is True
            assert settings.fill_model.enable_partial_fill is False
            assert settings.fill_model.enable_slippage is True
            assert settings.fill_model.slippage_alpha == 0.0005
            assert settings.fill_model.fill_model_type == "advanced"
            assert settings.fill_model.available_volume_factor == 3.0
    
    def test_settings_fill_model_disabled_explicitly(self):
        """
        테스트 5: 명시적으로 Fill Model 비활성화
        
        조건:
            - ARBITRAGE_ENV=paper
            - FILL_MODEL_ENABLE=false
        
        기대 결과:
            - fill_model.enable_fill_model=False (환경변수 우선)
        """
        with patch.dict(os.environ, {
            "ARBITRAGE_ENV": "paper",
            "FILL_MODEL_ENABLE": "false",
            "UPBIT_ACCESS_KEY": "test_upbit_key",
            "UPBIT_SECRET_KEY": "test_upbit_secret",
            "TELEGRAM_BOT_TOKEN": "test_telegram_token",
            "TELEGRAM_CHAT_ID": "test_chat_id",
        }, clear=True):
            settings = Settings.from_env()
            
            assert settings.env == RuntimeEnv.PAPER
            assert settings.fill_model.enable_fill_model is False
    
    def test_settings_fill_model_conservative_defaults(self):
        """
        테스트 6: 보수적 기본값 확인
        
        조건:
            - 환경변수 없음
        
        기대 결과:
            - slippage_alpha: 0.0001 (보수적)
            - available_volume_factor: 2.0 (보수적)
        """
        with patch.dict(os.environ, {
            "ARBITRAGE_ENV": "paper",
            "UPBIT_ACCESS_KEY": "test_upbit_key",
            "UPBIT_SECRET_KEY": "test_upbit_secret",
            "TELEGRAM_BOT_TOKEN": "test_telegram_token",
            "TELEGRAM_CHAT_ID": "test_chat_id",
        }, clear=True):
            settings = Settings.from_env()
            
            # 보수적 기본값 확인
            assert settings.fill_model.slippage_alpha == 0.0001  # 0.01% per unit
            assert settings.fill_model.available_volume_factor == 2.0  # Conservative
    
    def test_settings_fill_model_type_validation(self):
        """
        테스트 7: Fill Model Type 검증 (simple/advanced)
        
        조건:
            - FILL_MODEL_TYPE=simple 또는 advanced
        
        기대 결과:
            - fill_model_type 값이 정상 반영됨
        """
        # Test "simple"
        with patch.dict(os.environ, {
            "ARBITRAGE_ENV": "paper",
            "FILL_MODEL_TYPE": "simple",
            "UPBIT_ACCESS_KEY": "test_upbit_key",
            "UPBIT_SECRET_KEY": "test_upbit_secret",
            "TELEGRAM_BOT_TOKEN": "test_telegram_token",
            "TELEGRAM_CHAT_ID": "test_chat_id",
        }, clear=True):
            settings = Settings.from_env()
            assert settings.fill_model.fill_model_type == "simple"
        
        # Test "advanced"
        with patch.dict(os.environ, {
            "ARBITRAGE_ENV": "paper",
            "FILL_MODEL_TYPE": "advanced",
            "UPBIT_ACCESS_KEY": "test_upbit_key",
            "UPBIT_SECRET_KEY": "test_upbit_secret",
            "TELEGRAM_BOT_TOKEN": "test_telegram_token",
            "TELEGRAM_CHAT_ID": "test_chat_id",
        }, clear=True):
            settings = Settings.from_env()
            assert settings.fill_model.fill_model_type == "advanced"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
