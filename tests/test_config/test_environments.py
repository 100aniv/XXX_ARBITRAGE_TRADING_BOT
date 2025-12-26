"""
Environment-specific Config Tests
"""

import pytest
from config.environments import DevelopmentConfig, StagingConfig, ProductionConfig
from config.base import ArbitrageConfig


class TestDevelopmentConfig:
    """Development 환경 설정 테스트"""
    
    def test_development_config_structure(self):
        """Development config 기본 구조"""
        config = DevelopmentConfig()
        
        assert isinstance(config, ArbitrageConfig)
        assert config.env == 'development'
        assert config.session.mode == 'paper'
        assert config.monitoring.log_level == 'DEBUG'
    
    def test_development_no_secrets_required(self):
        """Development는 secrets 불필요"""
        config = DevelopmentConfig()
        
        # API keys는 None이어도 됨 (Paper mode)
        assert config.exchange.upbit_access_key is None
        assert config.exchange.binance_api_key is None
    
    def test_development_low_risk(self):
        """Development는 낮은 리스크 한도"""
        config = DevelopmentConfig()
        
        assert config.risk.max_notional_per_trade == 5000.0
        assert config.risk.max_open_trades == 1


class TestStagingConfig:
    """Staging 환경 설정 테스트"""
    
    def test_staging_config_structure(self):
        """Staging config 기본 구조"""
        config = StagingConfig()
        
        assert isinstance(config, ArbitrageConfig)
        assert config.env == 'staging'
        assert config.session.mode == 'paper'
        assert config.session.data_source == 'ws'  # 실제 WS
        assert config.monitoring.log_level == 'INFO'
    
    def test_staging_multi_symbol(self):
        """Staging는 멀티 심볼 테스트"""
        config = StagingConfig()
        
        assert len(config.symbols) >= 2
        assert 'KRW-BTC' in config.symbols
    
    def test_staging_medium_risk(self):
        """Staging는 중간 리스크 한도"""
        config = StagingConfig()
        
        assert config.risk.max_notional_per_trade == 10000.0
        assert config.risk.max_open_trades == 2


class TestProductionConfig:
    """Production 환경 설정 테스트"""
    
    def test_production_config_structure(self):
        """Production config 기본 구조"""
        config = ProductionConfig()
        
        assert isinstance(config, ArbitrageConfig)
        assert config.env == 'production'
        assert config.session.data_source == 'ws'
        assert config.monitoring.log_level == 'WARNING'
    
    def test_production_conservative_risk(self):
        """Production는 보수적인 리스크 한도"""
        config = ProductionConfig()
        
        assert config.risk.max_notional_per_trade == 5000.0
        assert config.risk.max_open_trades == 1
        assert config.risk.max_daily_trades == 50  # 낮음
    
    def test_production_secrets_placeholders(self, monkeypatch):
        """Production은 환경변수 placeholder 사용
        
        D99-20: Test self-isolation
        - 이전 테스트(PAPER mode)가 UPBIT/BINANCE 키를 실제값으로 설정
        - 이 테스트는 placeholder 형식(${...})을 검증해야 하므로
        - 테스트 시작 시 오염된 키를 명시적으로 삭제
        """
        # D99-20: Clean env vars that might be set by previous tests
        # (PAPER mode tests set these to actual values)
        cleanup_keys = [
            "UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY",
            "BINANCE_API_KEY", "BINANCE_API_SECRET", "BINANCE_SECRET_KEY",
            "REDIS_HOST", "REDIS_PASSWORD",
            "POSTGRES_HOST", "POSTGRES_USER", "POSTGRES_PASSWORD",
        ]
        for key in cleanup_keys:
            monkeypatch.delenv(key, raising=False)
        
        config = ProductionConfig()
        
        # 환경변수 placeholder 형식
        assert config.exchange.upbit_access_key.startswith('${')
        assert config.database.postgres_password.startswith('${')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
