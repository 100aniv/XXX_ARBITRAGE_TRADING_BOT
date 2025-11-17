# -*- coding: utf-8 -*-
"""
D62: Multi-Symbol Long-run Campaign Runner - Tests

멀티심볼 롱런 캠페인 러너의 기본 기능 검증.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import yaml

# 테스트용 임시 설정 생성
@pytest.fixture
def temp_config():
    """임시 설정 파일 생성"""
    config = {
        "initial_balance": 100000.0,
        "exchange_a": "upbit",
        "exchange_b": "binance",
        "max_notional_per_trade": 5000.0,
        "max_daily_loss": 10000.0,
        "max_open_trades": 1,
        "symbol_capital_limit": 5000.0,
        "symbol_max_positions": 2,
        "symbol_max_concurrent_trades": 1,
        "symbol_max_daily_loss": 5000.0,
        "data_source": "rest",
        "mode": "paper",
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        return f.name


class TestMultiSymbolLongrunRunner:
    """멀티심볼 롱런 러너 테스트"""
    
    def test_runner_initialization(self, temp_config):
        """러너 초기화"""
        from scripts.run_multisymbol_longrun import MultiSymbolLongrunRunner
        
        runner = MultiSymbolLongrunRunner(
            config_path=temp_config,
            symbols=["KRW-BTC", "KRW-ETH"],
            scenario="S0",
            duration_minutes=1,
        )
        
        assert runner is not None
        assert runner.symbols == ["KRW-BTC", "KRW-ETH"]
        assert runner.scenario == "S0"
        assert runner.duration_minutes == 1
    
    def test_runner_loads_config(self, temp_config):
        """설정 파일 로드"""
        from scripts.run_multisymbol_longrun import MultiSymbolLongrunRunner
        
        runner = MultiSymbolLongrunRunner(
            config_path=temp_config,
            symbols=["KRW-BTC"],
            scenario="S0",
            duration_minutes=1,
        )
        
        assert runner.config is not None
        assert runner.config["initial_balance"] == 100000.0
        assert runner.config["mode"] == "paper"
    
    def test_runner_creates_log_directory(self, temp_config):
        """로그 디렉토리 생성"""
        from scripts.run_multisymbol_longrun import MultiSymbolLongrunRunner
        
        runner = MultiSymbolLongrunRunner(
            config_path=temp_config,
            symbols=["KRW-BTC"],
            scenario="S0",
            duration_minutes=1,
        )
        
        assert runner.log_dir.exists()
        assert runner.log_file is not None
    
    def test_runner_cleanup_environment(self, temp_config):
        """환경 초기화"""
        from scripts.run_multisymbol_longrun import MultiSymbolLongrunRunner
        
        runner = MultiSymbolLongrunRunner(
            config_path=temp_config,
            symbols=["KRW-BTC"],
            scenario="S0",
            duration_minutes=1,
        )
        
        # cleanup_environment는 부작용이 있으므로 mock 사용
        with patch('subprocess.run'):
            runner.cleanup_environment()
    
    def test_runner_scenario_s0(self, temp_config):
        """S0 시나리오 (3분)"""
        from scripts.run_multisymbol_longrun import MultiSymbolLongrunRunner
        
        runner = MultiSymbolLongrunRunner(
            config_path=temp_config,
            symbols=["KRW-BTC", "KRW-ETH"],
            scenario="S0",
            duration_minutes=3,
        )
        
        assert runner.duration_seconds == 180
    
    def test_runner_scenario_s1(self, temp_config):
        """S1 시나리오 (1시간)"""
        from scripts.run_multisymbol_longrun import MultiSymbolLongrunRunner
        
        runner = MultiSymbolLongrunRunner(
            config_path=temp_config,
            symbols=["KRW-BTC", "KRW-ETH"],
            scenario="S1",
            duration_minutes=60,
        )
        
        assert runner.duration_seconds == 3600
    
    def test_runner_scenario_s2(self, temp_config):
        """S2 시나리오 (6시간)"""
        from scripts.run_multisymbol_longrun import MultiSymbolLongrunRunner
        
        runner = MultiSymbolLongrunRunner(
            config_path=temp_config,
            symbols=["KRW-BTC", "KRW-ETH", "BTCUSDT"],
            scenario="S2",
            duration_minutes=360,
        )
        
        assert runner.duration_seconds == 21600
        assert len(runner.symbols) == 3
    
    def test_runner_scenario_s3(self, temp_config):
        """S3 시나리오 (12시간)"""
        from scripts.run_multisymbol_longrun import MultiSymbolLongrunRunner
        
        runner = MultiSymbolLongrunRunner(
            config_path=temp_config,
            symbols=["KRW-BTC", "KRW-ETH", "BTCUSDT", "ETHUSDT"],
            scenario="S3",
            duration_minutes=720,
        )
        
        assert runner.duration_seconds == 43200
        assert len(runner.symbols) == 4
    
    def test_runner_multiple_symbols(self, temp_config):
        """여러 심볼 처리"""
        from scripts.run_multisymbol_longrun import MultiSymbolLongrunRunner
        
        symbols = ["KRW-BTC", "KRW-ETH", "BTCUSDT"]
        runner = MultiSymbolLongrunRunner(
            config_path=temp_config,
            symbols=symbols,
            scenario="S2",
            duration_minutes=10,
        )
        
        assert runner.symbols == symbols
        assert len(runner.symbols) == 3
    
    def test_runner_backward_compatible_single_symbol(self, temp_config):
        """단일 심볼 호환성"""
        from scripts.run_multisymbol_longrun import MultiSymbolLongrunRunner
        
        runner = MultiSymbolLongrunRunner(
            config_path=temp_config,
            symbols=["KRW-BTC"],
            scenario="S1",
            duration_minutes=60,
        )
        
        assert len(runner.symbols) == 1
        assert runner.symbols[0] == "KRW-BTC"
    
    def test_runner_timestamp_in_log_file(self, temp_config):
        """로그 파일에 타임스탬프 포함"""
        from scripts.run_multisymbol_longrun import MultiSymbolLongrunRunner
        
        runner = MultiSymbolLongrunRunner(
            config_path=temp_config,
            symbols=["KRW-BTC"],
            scenario="S0",
            duration_minutes=1,
        )
        
        log_filename = runner.log_file.name
        assert "d62_longrun" in log_filename
        assert "S0" in log_filename
        assert runner.timestamp in log_filename
    
    def test_runner_uses_rest_data_source(self, temp_config):
        """REST 데이터 소스 강제"""
        from scripts.run_multisymbol_longrun import MultiSymbolLongrunRunner
        
        runner = MultiSymbolLongrunRunner(
            config_path=temp_config,
            symbols=["KRW-BTC"],
            scenario="S0",
            duration_minutes=1,
        )
        
        assert runner.config["data_source"] == "rest"
    
    def test_runner_paper_mode(self, temp_config):
        """Paper 모드 설정"""
        from scripts.run_multisymbol_longrun import MultiSymbolLongrunRunner
        
        runner = MultiSymbolLongrunRunner(
            config_path=temp_config,
            symbols=["KRW-BTC"],
            scenario="S0",
            duration_minutes=1,
        )
        
        assert runner.config["mode"] == "paper"
