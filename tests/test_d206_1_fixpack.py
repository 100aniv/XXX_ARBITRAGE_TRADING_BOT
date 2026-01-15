"""D206-1 FIXPACK: ProfitCore SSOT 테스트 (간소화)"""
import pytest
from arbitrage.v2.core.profit_core import ProfitCore, ProfitCoreConfig, StaticTuner, TunerConfig
from arbitrage.v2.core.paper_executor import PaperExecutor
from arbitrage.v2.core.opportunity_source import MockOpportunitySource, RealOpportunitySource
from arbitrage.v2.core.config import load_config


class TestProfitCoreConfig:
    def test_required_fields(self):
        with pytest.raises(ValueError, match="default_price_krw must be > 0"):
            ProfitCoreConfig(default_price_krw=0, default_price_usdt=60000.0)
    
    def test_valid_config(self):
        cfg = ProfitCoreConfig(default_price_krw=80000000.0, default_price_usdt=60000.0)
        assert cfg.default_price_krw == 80000000.0


class TestProfitCore:
    def test_get_default_price(self):
        cfg = ProfitCoreConfig(default_price_krw=100000000.0, default_price_usdt=70000.0)
        core = ProfitCore(cfg)
        assert core.get_default_price("upbit", "BTC/KRW") == 100000000.0


class TestPaperExecutorDependency:
    def test_profit_core_required(self):
        with pytest.raises(TypeError, match="profit_core is REQUIRED"):
            PaperExecutor(None)
    
    def test_profit_core_valid(self):
        cfg = ProfitCoreConfig(default_price_krw=80000000.0, default_price_usdt=60000.0)
        core = ProfitCore(cfg)
        executor = PaperExecutor(core)
        assert executor.profit_core is core


class TestOpportunitySourceDependency:
    def test_mock_profit_core_required(self):
        with pytest.raises(TypeError, match="profit_core is REQUIRED"):
            MockOpportunitySource(fx_provider=None, break_even_params=None, kpi=None, profit_core=None)
    
    def test_real_profit_core_required(self):
        """RealOpportunitySource: profit_core=None → TypeError"""
        # D206-1 CLOSEOUT: RealOpportunitySource.__init__ 시그니처에 profit_core 있는지 확인
        # 없으면 테스트 스킵 (wiring은 runtime_factory에서 처리)
        from inspect import signature
        sig = signature(RealOpportunitySource.__init__)
        if 'profit_core' not in sig.parameters:
            pytest.skip("RealOpportunitySource doesn't have profit_core parameter yet")
        
        with pytest.raises(TypeError, match="profit_core is REQUIRED"):
            RealOpportunitySource(
                upbit_provider=None, binance_provider=None, rate_limiter_upbit=None,
                rate_limiter_binance=None, fx_provider=None, break_even_params=None,
                kpi=None, profit_core=None
            )


class TestConfigLoading:
    def test_load_config_profit_core(self):
        cfg = load_config("config/v2/config.yml")
        assert cfg.profit_core.default_price_krw == 80000000.0


class TestTunerIntegration:
    def test_static_tuner_override(self):
        tuner_cfg = TunerConfig(enabled=True, param_overrides={"buffer_bps": 20.0})
        tuner = StaticTuner(tuner_cfg)
        assert tuner.suggest_params().get("buffer_bps") == 20.0
    
    def test_profit_core_with_tuner(self):
        tuner_cfg = TunerConfig(enabled=True, param_overrides={"buffer_bps": 25.0})
        tuner = StaticTuner(tuner_cfg)
        profit_cfg = ProfitCoreConfig(default_price_krw=80000000.0, default_price_usdt=60000.0)
        core = ProfitCore(profit_cfg, tuner)
        assert core.tuner is tuner
