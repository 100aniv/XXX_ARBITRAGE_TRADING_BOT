"""
Config Validators Tests
"""

import pytest
from config.loader import load_config
from config.validators import (
    validate_spread_profitability,
    validate_risk_constraints,
    validate_session_config,
    validate_all
)
from config.base import (
    ArbitrageConfig,
    TradingConfig,
    RiskConfig,
    SessionConfig,
    ConfigError
)


class TestSpreadProfitabilityValidator:
    """스프레드 수익성 검증 테스트"""
    
    def test_valid_spread(self):
        """정상적인 스프레드"""
        config = load_config(env='development')
        
        # Should not raise
        assert validate_spread_profitability(config) is True
    
    def test_invalid_spread_too_low(self):
        """스프레드가 너무 낮음 - TradingConfig.__post_init__ validation"""
        config = load_config(env='development')
        
        # D99-18 P17: TradingConfig.__post_init__가 이미 올바른 validation을 수행
        # copy() 시 __post_init__가 트리거되어 ValueError 발생
        with pytest.raises(ValueError, match="min_spread_bps.*must be >"):
            config.copy(update={
                'trading': config.trading.copy(update={'min_spread_bps': 10.0})
            })


class TestRiskConstraintsValidator:
    """리스크 제약 조건 검증 테스트"""
    
    def test_valid_risk_constraints(self):
        """정상적인 리스크 설정"""
        config = load_config(env='development')
        
        assert validate_risk_constraints(config) is True
    
    def test_invalid_daily_loss_too_low(self):
        """일일 손실이 거래당 손실보다 작음 - RiskConfig.__post_init__ validation"""
        config = load_config(env='development')
        
        # D99-18 P17: RiskConfig.__post_init__가 이미 올바른 validation을 수행
        # copy() 시 __post_init__가 트리거되어 ValueError 발생
        with pytest.raises(ValueError, match="max_daily_loss.*must be >="):
            config.copy(update={
                'risk': config.risk.copy(update={
                    'max_notional_per_trade': 10000.0,
                    'max_daily_loss': 5000.0
                })
            })


class TestSessionConfigValidator:
    """세션 설정 검증 테스트"""
    
    def test_valid_session_config_paper_paper(self):
        """유효한 조합: paper mode + paper data"""
        config = load_config(env='development')
        
        assert validate_session_config(config) is True
    
    def test_valid_session_config_paper_ws(self):
        """유효한 조합: paper mode + ws data"""
        config = load_config(env='staging')
        
        assert validate_session_config(config) is True
    
    def test_invalid_session_config_live_paper(self):
        """무효한 조합: live mode + paper data"""
        config = load_config(env='development')
        
        invalid_config = config.copy(update={
            'session': config.session.copy(update={
                'mode': 'live',
                'data_source': 'paper'  # live mode에서는 paper data 불가
            })
        })
        
        with pytest.raises(ConfigError, match="Invalid combination"):
            validate_session_config(invalid_config)


class TestValidateAll:
    """전체 validator 통합 테스트"""
    
    def test_validate_all_development(self):
        """Development config 전체 검증"""
        config = load_config(env='development')
        
        # Should pass all validators
        assert validate_all(config) is True
    
    def test_validate_all_staging(self):
        """Staging config 전체 검증"""
        config = load_config(env='staging')
        
        assert validate_all(config) is True
    
    def test_validate_all_production(self, monkeypatch):
        """Production config 전체 검증 (Paper mode)"""
        # D99-16 P15: production config 로드 시 필요한 env 설정
        monkeypatch.setenv('POSTGRES_PASSWORD', 'unit_test_postgres_password_validators_12345')
        monkeypatch.setenv('UPBIT_ACCESS_KEY', 'unit_test_upbit_access_key_validators_67890')
        monkeypatch.setenv('UPBIT_SECRET_KEY', 'unit_test_upbit_secret_key_validators_abcde')
        monkeypatch.setenv('BINANCE_API_KEY', 'unit_test_binance_api_key_validators_fghij')
        monkeypatch.setenv('BINANCE_SECRET_KEY', 'unit_test_binance_secret_key_validators_klmno')
        
        config = load_config(env='production')
        
        # Production paper mode 전체 검증
        assert validate_all(config) is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
