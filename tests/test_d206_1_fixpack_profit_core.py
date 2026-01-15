"""
D206-1 FIXPACK: ProfitCore SSOT 테스트

Purpose:
- ProfitCoreConfig 필수 검증
- PaperExecutor/OpportunitySource 필수 의존성 검증
- Config 로딩 검증
- WARN=FAIL 원칙 검증

Constitutional Basis:
- No Magic Numbers (하드코딩 0개)
- Config SSOT (config.yml 필수)
- WARN=FAIL (누락 시 즉시 예외)
"""

import pytest
from arbitrage.v2.core.profit_core import ProfitCore, ProfitCoreConfig, StaticTuner, TunerConfig
from arbitrage.v2.core.paper_executor import PaperExecutor
from arbitrage.v2.core.opportunity_source import MockOpportunitySource, RealOpportunitySource
from arbitrage.v2.core.config import load_config
from arbitrage.v2.domain.break_even import BreakEvenParams


class TestProfitCoreConfig:
    """ProfitCoreConfig 검증"""
    
    def test_required_fields(self):
        """필수 필드 누락 시 ValueError"""
        with pytest.raises(ValueError, match="default_price_krw must be > 0"):
            ProfitCoreConfig(default_price_krw=0, default_price_usdt=60000.0)
        
        with pytest.raises(ValueError, match="default_price_usdt must be > 0"):
            ProfitCoreConfig(default_price_krw=80000000.0, default_price_usdt=0)
    
    def test_sanity_check_validation(self):
        """Sanity check 범위 검증"""
        with pytest.raises(ValueError, match="price_sanity_max_krw must be > min"):
            ProfitCoreConfig(
                default_price_krw=80000000.0,
                default_price_usdt=60000.0,
                price_sanity_min_krw=100000000.0,
                price_sanity_max_krw=50000000.0,
            )
    
    def test_valid_config(self):
        """정상 config"""
        cfg = ProfitCoreConfig(
            default_price_krw=80000000.0,
            default_price_usdt=60000.0,
            price_sanity_min_krw=40000000.0,
            price_sanity_max_krw=200000000.0,
        )
        assert cfg.default_price_krw == 80000000.0
        assert cfg.default_price_usdt == 60000.0


class TestProfitCore:
    """ProfitCore 기능 테스트"""
    
    def test_get_default_price(self):
        """기본 가격 조회"""
        cfg = ProfitCoreConfig(default_price_krw=100000000.0, default_price_usdt=70000.0)
        core = ProfitCore(cfg)
        
        assert core.get_default_price("upbit", "BTC/KRW") == 100000000.0
        assert core.get_default_price("binance", "BTC/USDT") == 70000.0
    
    def test_check_price_sanity(self):
        """가격 sanity check"""
        cfg = ProfitCoreConfig(
            default_price_krw=80000000.0,
            default_price_usdt=60000.0,
            price_sanity_min_krw=50000000.0,
            price_sanity_max_krw=150000000.0,
        )
        core = ProfitCore(cfg)
        
        assert core.check_price_sanity("upbit", 80000000.0) is True
        assert core.check_price_sanity("upbit", 30000000.0) is False
        assert core.check_price_sanity("upbit", 200000000.0) is False


class TestPaperExecutorDependency:
    """PaperExecutor 필수 의존성 검증"""
    
    def test_profit_core_required(self):
        """profit_core=None → TypeError"""
        with pytest.raises(TypeError, match="profit_core is REQUIRED"):
            PaperExecutor(None)
    
    def test_profit_core_valid(self):
        """profit_core 정상 주입"""
        cfg = ProfitCoreConfig(default_price_krw=80000000.0, default_price_usdt=60000.0)
        core = ProfitCore(cfg)
        executor = PaperExecutor(core)
        
        assert executor.profit_core is core


class TestOpportunitySourceDependency:
    """OpportunitySource 필수 의존성 검증"""
    
    def test_mock_profit_core_required(self):
        """MockOpportunitySource: profit_core=None → TypeError"""
        # BreakEvenParams는 OpportunitySource에서 사용하지만 이 테스트에서는 None 체크만 수행
        with pytest.raises(TypeError, match="profit_core is REQUIRED"):
            MockOpportunitySource(
                fx_provider=None,
                break_even_params=None,  # 간소화
                kpi=None,
                profit_core=None,
            )
    
    def test_real_profit_core_required(self):
        """RealOpportunitySource: profit_core=None → TypeError"""
        with pytest.raises(TypeError, match="profit_core is REQUIRED"):
            RealOpportunitySource(
                upbit_provider=None,
                binance_provider=None,
                rate_limiter_upbit=None,
                rate_limiter_binance=None,
                fx_provider=None,
                break_even_params=None,  # 간소화
                kpi=None,
                profit_core=None,
            )


class TestConfigLoading:
    """Config 로딩 검증"""
    
    def test_load_config_profit_core(self):
        """config.yml → ProfitCoreConfig 로딩"""
        cfg = load_config("config/v2/config.yml")
        
        assert cfg.profit_core is not None
        assert cfg.profit_core.default_price_krw == 80000000.0
        assert cfg.profit_core.default_price_usdt == 60000.0
    
    def test_load_config_tuner(self):
        """config.yml → TunerConfig 로딩"""
        cfg = load_config("config/v2/config.yml")
        
        assert cfg.tuner is not None
        assert cfg.tuner.enabled is False
        assert cfg.tuner.tuner_type == "static"


class TestTunerIntegration:
    """Tuner 통합 테스트"""
    
    def test_static_tuner_override(self):
        """StaticTuner 파라미터 오버라이드"""
        tuner_cfg = TunerConfig(
            enabled=True,
            param_overrides={"buffer_bps": 20.0}
        )
        tuner = StaticTuner(tuner_cfg)
        
        params = tuner.suggest_params()
        assert params.get("buffer_bps") == 20.0
    
    def test_profit_core_with_tuner(self):
        """ProfitCore + Tuner 통합"""
        tuner_cfg = TunerConfig(
            enabled=True,
            param_overrides={"buffer_bps": 25.0}
        )
        tuner = StaticTuner(tuner_cfg)
        
        profit_cfg = ProfitCoreConfig(default_price_krw=80000000.0, default_price_usdt=60000.0)
        core = ProfitCore(profit_cfg, tuner)
        
        fee_model = FeeModel(FeeStructure.UPBIT_SPOT, FeeStructure.BINANCE_FUTURES)
        params = BreakEvenParams(fee_model=fee_model, buffer_bps=10.0, slippage_bps=15.0)
        
        new_params = core.apply_tuner_overrides(params)
        assert new_params.buffer_bps == 25.0
        assert new_params.slippage_bps == 15.0  # unchanged
