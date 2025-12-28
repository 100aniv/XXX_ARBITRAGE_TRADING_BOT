"""
V2 Config Validation Tests

config/v2/config.yml의 스키마 검증 및 필수 키 확인
"""

import pytest
from pathlib import Path
from arbitrage.v2.core.config import load_config, V2Config


def test_config_file_exists():
    """config.yml 파일 존재 확인"""
    config_path = Path("config/v2/config.yml")
    assert config_path.exists(), "config/v2/config.yml 파일이 존재해야 함"


def test_config_loads_successfully():
    """config.yml 로드 성공 확인"""
    config = load_config("config/v2/config.yml")
    assert isinstance(config, V2Config), "V2Config 객체로 로드되어야 함"


def test_config_exchanges_required():
    """거래소 설정 필수 키 확인"""
    config = load_config("config/v2/config.yml")
    
    # Upbit 설정
    assert "upbit" in config.exchanges, "upbit 거래소 설정 필요"
    upbit = config.exchanges["upbit"]
    assert upbit.enabled is True, "upbit 활성화 필요"
    assert upbit.taker_fee_bps >= 0, "taker_fee_bps는 0 이상"
    assert upbit.min_order_krw > 0, "min_order_krw는 양수"
    
    # Binance 설정
    assert "binance" in config.exchanges, "binance 거래소 설정 필요"
    binance = config.exchanges["binance"]
    assert binance.enabled is True, "binance 활성화 필요"
    assert binance.taker_fee_bps >= 0, "taker_fee_bps는 0 이상"
    assert binance.min_notional_usdt > 0, "min_notional_usdt는 양수"


def test_config_universe_required():
    """Universe 설정 필수 키 확인"""
    config = load_config("config/v2/config.yml")
    
    assert config.universe.symbols_top_n > 0, "symbols_top_n은 양수"
    assert config.universe.symbols_top_n <= 100, "symbols_top_n은 100 이하"
    assert isinstance(config.universe.allowlist, list), "allowlist는 리스트"
    assert isinstance(config.universe.denylist, list), "denylist는 리스트"


def test_config_strategy_required():
    """Strategy 설정 필수 키 확인 (하드코딩 제거)"""
    config = load_config("config/v2/config.yml")
    
    # Threshold (fee/slippage/buffer 포함)
    assert config.strategy.threshold_bps > 0, "threshold_bps는 양수"
    assert config.strategy.slippage_bps >= 0, "slippage_bps는 0 이상"
    assert config.strategy.buffer_bps >= 0, "buffer_bps는 0 이상"
    
    # Order size policy
    assert config.strategy.order_size_policy in ["fixed", "dynamic"], \
        "order_size_policy는 fixed 또는 dynamic"
    assert config.strategy.order_size_usd > 0, "order_size_usd는 양수"


def test_config_safety_guardrails():
    """Safety 가드레일 필수 키 확인"""
    config = load_config("config/v2/config.yml")
    
    # 손실 한도
    assert config.safety.max_daily_loss_usd > 0, "max_daily_loss_usd는 양수"
    assert config.safety.max_position_usd > 0, "max_position_usd는 양수"
    
    # Cooldown
    assert config.safety.cooldown_after_loss_seconds >= 0, \
        "cooldown_after_loss_seconds는 0 이상"
    
    # Emergency stop
    assert isinstance(config.safety.emergency_stop_enabled, bool), \
        "emergency_stop_enabled는 bool"


def test_config_execution_limits():
    """Execution 설정 한도 확인"""
    config = load_config("config/v2/config.yml")
    
    # Cycle interval
    assert config.execution.cycle_interval_seconds > 0, \
        "cycle_interval_seconds는 양수"
    assert config.execution.cycle_interval_seconds <= 60, \
        "cycle_interval_seconds는 60초 이하 권장"
    
    # Max concurrent orders
    assert config.execution.max_concurrent_orders > 0, \
        "max_concurrent_orders는 양수"
    assert config.execution.max_concurrent_orders <= 10, \
        "max_concurrent_orders는 10 이하 권장"
    
    # Dry run
    assert isinstance(config.execution.dry_run, bool), "dry_run은 bool"


def test_config_break_even_spread_calculation():
    """Break-even spread 계산 공식 검증"""
    config = load_config("config/v2/config.yml")
    
    # Break-even spread 계산
    break_even = config.get_break_even_spread_bps("upbit", "binance")
    
    # 예상: Upbit 5 + Binance 4 + slippage 10*2 + buffer 5 = 34 bps
    # (실제 config.yml 값에 따라 다를 수 있음)
    assert break_even > 0, "break_even_spread는 양수"
    assert break_even < 100, "break_even_spread는 100 bps 미만 권장"


def test_config_db_settings():
    """Database 설정 확인"""
    config = load_config("config/v2/config.yml")
    
    assert config.database.host, "DB host 필요"
    assert config.database.port > 0, "DB port는 양수"
    assert config.database.database, "DB name 필요"
    assert config.database.pool_size > 0, "pool_size는 양수"


def test_config_cache_settings():
    """Cache (Redis) 설정 확인"""
    config = load_config("config/v2/config.yml")
    
    assert config.cache.host, "Redis host 필요"
    assert config.cache.port > 0, "Redis port는 양수"
    assert config.cache.db >= 0, "Redis db는 0 이상"
    assert config.cache.ttl_seconds > 0, "TTL은 양수"


def test_config_no_secrets():
    """config.yml에 Secrets 포함 금지 검증"""
    config_path = Path("config/v2/config.yml")
    config_text = config_path.read_text(encoding="utf-8")
    
    # API Key가 포함되어서는 안 됨
    forbidden_patterns = [
        "UPBIT_ACCESS_KEY",
        "UPBIT_SECRET_KEY",
        "BINANCE_API_KEY",
        "BINANCE_SECRET_KEY",
        "api_key:",
        "secret_key:",
    ]
    
    for pattern in forbidden_patterns:
        assert pattern not in config_text, \
            f"config.yml에 '{pattern}' 같은 Secrets 포함 금지"


def test_config_meta_version():
    """Meta 정보 (버전) 확인"""
    config = load_config("config/v2/config.yml")
    
    assert config.meta.version, "version 필요"
    assert config.meta.name, "config name 필요"
    assert "v2" in config.meta.version.lower() or \
           "v2" in config.meta.name.lower(), \
           "V2 config임을 명시해야 함"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
