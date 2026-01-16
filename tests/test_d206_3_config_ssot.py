"""
D206-3: Config SSOT Zero-Fallback Tests

Test suite for config.yml loading and validation.
Enforces Zero-Fallback principle: missing required keys must raise RuntimeError.
"""

import pytest
import tempfile
import os
from pathlib import Path
from arbitrage.v2.core.engine import EngineConfig


class TestConfigSSOT:
    """D206-3: Config SSOT validation tests"""
    
    def test_config_file_missing(self):
        """Zero-Fallback: Missing config.yml must raise RuntimeError"""
        with pytest.raises(RuntimeError, match="config.yml not found"):
            EngineConfig.from_config_file("nonexistent_config.yml")
    
    def test_config_all_required_keys_present(self, tmp_path):
        """PASS: All required keys present in config.yml"""
        config_path = tmp_path / "config.yml"
        config_content = """
min_spread_bps: 30.0
max_position_usd: 1000.0
max_open_trades: 1
taker_fee_a_bps: 10.0
taker_fee_b_bps: 10.0
slippage_bps: 5.0
exchange_a_to_b_rate: 1.0
"""
        config_path.write_text(config_content)
        
        config = EngineConfig.from_config_file(str(config_path))
        
        assert config.min_spread_bps == 30.0
        assert config.max_position_usd == 1000.0
        assert config.max_open_trades == 1
        assert config.taker_fee_a_bps == 10.0
        assert config.taker_fee_b_bps == 10.0
        assert config.slippage_bps == 5.0
        assert config.exchange_a_to_b_rate == 1.0
    
    def test_config_missing_entry_threshold(self, tmp_path):
        """Zero-Fallback: Missing min_spread_bps must raise RuntimeError"""
        config_path = tmp_path / "config.yml"
        config_content = """
max_position_usd: 1000.0
max_open_trades: 1
taker_fee_a_bps: 10.0
taker_fee_b_bps: 10.0
slippage_bps: 5.0
exchange_a_to_b_rate: 1.0
"""
        config_path.write_text(config_content)
        
        with pytest.raises(RuntimeError, match="Missing required config keys.*min_spread_bps"):
            EngineConfig.from_config_file(str(config_path))
    
    def test_config_missing_cost_key(self, tmp_path):
        """Zero-Fallback: Missing taker_fee_a_bps must raise RuntimeError"""
        config_path = tmp_path / "config.yml"
        config_content = """
min_spread_bps: 30.0
max_position_usd: 1000.0
max_open_trades: 1
taker_fee_b_bps: 10.0
slippage_bps: 5.0
exchange_a_to_b_rate: 1.0
"""
        config_path.write_text(config_content)
        
        with pytest.raises(RuntimeError, match="Missing required config keys.*taker_fee_a_bps"):
            EngineConfig.from_config_file(str(config_path))
    
    def test_config_missing_multiple_keys(self, tmp_path):
        """Zero-Fallback: Missing multiple keys must raise RuntimeError with all missing keys"""
        config_path = tmp_path / "config.yml"
        config_content = """
max_position_usd: 1000.0
taker_fee_b_bps: 10.0
"""
        config_path.write_text(config_content)
        
        with pytest.raises(RuntimeError, match="Missing required config keys"):
            EngineConfig.from_config_file(str(config_path))
    
    def test_config_exit_rules_optional(self, tmp_path):
        """Exit Rules (TP/SL) are optional - can be null or absent"""
        config_path = tmp_path / "config.yml"
        config_content = """
min_spread_bps: 30.0
max_position_usd: 1000.0
max_open_trades: 1
taker_fee_a_bps: 10.0
taker_fee_b_bps: 10.0
slippage_bps: 5.0
exchange_a_to_b_rate: 1.0
take_profit_bps: null
stop_loss_bps: 50.0
"""
        config_path.write_text(config_content)
        
        config = EngineConfig.from_config_file(str(config_path))
        
        assert config.take_profit_bps is None  # null in YAML
        assert config.stop_loss_bps == 50.0
        assert config.min_hold_sec == 0.0  # default
        assert config.close_on_spread_reversal is True  # default
        assert config.enable_alpha_exit is False  # default
    
    def test_config_kwargs_override(self, tmp_path):
        """kwargs passed to from_config_file should override config.yml"""
        config_path = tmp_path / "config.yml"
        config_content = """
min_spread_bps: 30.0
max_position_usd: 1000.0
max_open_trades: 1
taker_fee_a_bps: 10.0
taker_fee_b_bps: 10.0
slippage_bps: 5.0
exchange_a_to_b_rate: 1.0
"""
        config_path.write_text(config_content)
        
        # Override max_position_usd via kwargs
        config = EngineConfig.from_config_file(str(config_path), max_position_usd=2000.0)
        
        assert config.max_position_usd == 2000.0  # overridden
        assert config.min_spread_bps == 30.0  # from config.yml
    
    def test_config_real_config_yml_loads(self):
        """Real config.yml in repo root should load without errors"""
        repo_root = Path(__file__).parent.parent
        config_path = repo_root / "config.yml"
        
        if not config_path.exists():
            pytest.skip("config.yml not found in repo root")
        
        config = EngineConfig.from_config_file(str(config_path))
        
        # Verify all required keys are present
        assert config.min_spread_bps > 0
        assert config.max_position_usd > 0
        assert config.max_open_trades >= 1
        assert config.taker_fee_a_bps >= 0
        assert config.taker_fee_b_bps >= 0
        assert config.slippage_bps >= 0
        assert config.exchange_a_to_b_rate > 0


class TestConfigIntegration:
    """D206-3: Integration tests with ArbitrageEngine"""
    
    def test_engine_from_config_file(self, tmp_path):
        """ArbitrageEngine can be initialized from config.yml"""
        config_path = tmp_path / "config.yml"
        config_content = """
min_spread_bps: 30.0
max_position_usd: 1000.0
max_open_trades: 1
taker_fee_a_bps: 10.0
taker_fee_b_bps: 10.0
slippage_bps: 5.0
exchange_a_to_b_rate: 1.0
enable_execution: false
"""
        config_path.write_text(config_content)
        
        from arbitrage.v2.core.engine import ArbitrageEngine
        
        config = EngineConfig.from_config_file(str(config_path))
        engine = ArbitrageEngine(config)
        
        assert engine.config.min_spread_bps == 30.0
        assert engine._total_cost_bps == 25.0  # 10 + 10 + 5
        assert engine._exchange_a_to_b_rate == 1.0
    
    def test_engine_exit_rules_from_config(self, tmp_path):
        """Engine respects Exit Rules from config.yml"""
        config_path = tmp_path / "config.yml"
        config_content = """
min_spread_bps: 30.0
max_position_usd: 1000.0
max_open_trades: 1
taker_fee_a_bps: 10.0
taker_fee_b_bps: 10.0
slippage_bps: 5.0
exchange_a_to_b_rate: 1.0
take_profit_bps: 100.0
stop_loss_bps: 50.0
min_hold_sec: 60.0
close_on_spread_reversal: false
"""
        config_path.write_text(config_content)
        
        from arbitrage.v2.core.engine import ArbitrageEngine
        
        config = EngineConfig.from_config_file(str(config_path))
        engine = ArbitrageEngine(config)
        
        assert engine.config.take_profit_bps == 100.0
        assert engine.config.stop_loss_bps == 50.0
        assert engine.config.min_hold_sec == 60.0
        assert engine.config.close_on_spread_reversal is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
