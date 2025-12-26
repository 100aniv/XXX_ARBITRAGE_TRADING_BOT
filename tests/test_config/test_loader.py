"""
Config Loader Tests
"""

import os
import pytest
from config.loader import load_config, get_current_env
from config.base import ArbitrageConfig, ConfigError


class TestConfigLoader:
    """Config loader 테스트"""
    
    def test_get_current_env_default(self):
        """환경변수 없을 때 development 기본값"""
        # ENV 변수 제거
        old_env = os.environ.pop('ENV', None)
        old_arb_env = os.environ.pop('ARBITRAGE_ENV', None)
        
        try:
            env = get_current_env()
            assert env == 'development'
        finally:
            if old_env:
                os.environ['ENV'] = old_env
            if old_arb_env:
                os.environ['ARBITRAGE_ENV'] = old_arb_env
    
    def test_get_current_env_from_ENV(self):
        """ENV 환경변수에서 환경 감지"""
        old_env = os.environ.get('ENV')
        
        try:
            os.environ['ENV'] = 'staging'
            env = get_current_env()
            assert env == 'staging'
        finally:
            if old_env:
                os.environ['ENV'] = old_env
            else:
                os.environ.pop('ENV', None)
    
    def test_get_current_env_from_ARBITRAGE_ENV(self):
        """ARBITRAGE_ENV 환경변수에서 환경 감지"""
        old_env = os.environ.pop('ENV', None)
        old_arb_env = os.environ.get('ARBITRAGE_ENV')
        
        try:
            os.environ['ARBITRAGE_ENV'] = 'production'
            env = get_current_env()
            assert env == 'production'
        finally:
            if old_env:
                os.environ['ENV'] = old_env
            if old_arb_env:
                os.environ['ARBITRAGE_ENV'] = old_arb_env
            else:
                os.environ.pop('ARBITRAGE_ENV', None)
    
    def test_load_config_development(self):
        """Development config 로드"""
        config = load_config(env='development')
        
        assert isinstance(config, ArbitrageConfig)
        assert config.env == 'development'
        assert config.session.mode == 'paper'
        assert config.monitoring.log_level == 'DEBUG'
        assert config.risk.max_notional_per_trade == 5000.0
    
    def test_load_config_staging(self):
        """Staging config 로드"""
        config = load_config(env='staging')
        
        assert isinstance(config, ArbitrageConfig)
        assert config.env == 'staging'
        assert config.session.mode == 'paper'
        assert config.session.data_source == 'ws'
        assert config.monitoring.log_level == 'INFO'
    
    def test_load_config_production(self, monkeypatch):
        """Production 설정 로드"""
        # D99-17 P16: production config 로드 시 필요한 env 설정
        monkeypatch.setenv('POSTGRES_PASSWORD', 'unit_test_postgres_password_loader_12345')
        monkeypatch.setenv('UPBIT_ACCESS_KEY', 'unit_test_upbit_access_key_loader_67890')
        monkeypatch.setenv('UPBIT_SECRET_KEY', 'unit_test_upbit_secret_key_loader_abcde')
        monkeypatch.setenv('BINANCE_API_KEY', 'unit_test_binance_api_key_loader_fghij')
        monkeypatch.setenv('BINANCE_SECRET_KEY', 'unit_test_binance_secret_key_loader_klmno')
        
        config = load_config(env='production')
        
        assert isinstance(config, ArbitrageConfig)
        assert config.env == 'production'
        assert config.monitoring.log_level == 'WARNING'
        assert config.risk.max_notional_per_trade == 5000.0  # 보수적
    
    def test_load_config_auto_detect(self):
        """환경 자동 감지 로드"""
        old_env = os.environ.get('ENV')
        
        try:
            os.environ['ENV'] = 'development'
            config = load_config()
            assert config.env == 'development'
        finally:
            if old_env:
                os.environ['ENV'] = old_env
            else:
                os.environ.pop('ENV', None)
    
    def test_config_immutability(self):
        """Config는 immutable해야 함"""
        config = load_config(env='development')
        
        with pytest.raises(Exception):  # Pydantic frozen model error
            config.env = 'production'  # type: ignore
    
    def test_config_to_legacy_conversion(self):
        """Legacy config로 변환"""
        config = load_config(env='development')
        
        legacy_config = config.to_legacy_config()
        
        assert legacy_config.min_spread_bps == config.trading.min_spread_bps
        assert legacy_config.max_position_usd == config.risk.max_notional_per_trade
    
    def test_config_to_live_config_conversion(self):
        """LiveConfig로 변환"""
        config = load_config(env='development')
        
        live_config = config.to_live_config()
        
        assert live_config.mode == config.session.mode
        assert live_config.loop_interval_ms == config.session.loop_interval_ms
    
    def test_config_to_risk_limits_conversion(self):
        """RiskLimits로 변환"""
        config = load_config(env='development')
        
        risk_limits = config.to_risk_limits()
        
        assert risk_limits.max_notional_per_trade == config.risk.max_notional_per_trade
        assert risk_limits.max_daily_loss == config.risk.max_daily_loss


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
