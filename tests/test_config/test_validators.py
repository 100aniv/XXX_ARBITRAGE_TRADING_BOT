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
        """스프레드가 너무 낮음"""
        config = load_config(env='development')
        
        # 스프레드를 비정상적으로 낮게 설정
        invalid_config = config.copy(update={
            'trading': config.trading.copy(update={'min_spread_bps': 10.0})  # 너무 낮음
        })
        
        with pytest.raises(ConfigError, match="Spread not profitable"):
            validate_spread_profitability(invalid_config)


class TestRiskConstraintsValidator:
    """리스크 제약 조건 검증 테스트"""
    
    def test_valid_risk_constraints(self):
        """정상적인 리스크 설정"""
        config = load_config(env='development')
        
        assert validate_risk_constraints(config) is True
    
    def test_invalid_daily_loss_too_low(self):
        """일일 손실이 거래당 손실보다 작음"""
        config = load_config(env='development')
        
        # 일일 손실을 비정상적으로 낮게 설정
        invalid_config = config.copy(update={
            'risk': config.risk.copy(update={
                'max_notional_per_trade': 10000.0,
                'max_daily_loss': 5000.0  # 거래당 손실보다 작음
            })
        })
        
        with pytest.raises(ConfigError, match="max_daily_loss.*must be >="):
            validate_risk_constraints(invalid_config)


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
    
    def test_validate_all_production(self):
        """Production config 전체 검증 (Paper mode)"""
        config = load_config(env='production')
        
        # Production paper mode는 secrets 없어도 통과
        assert validate_all(config) is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
