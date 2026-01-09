"""
D205-15-5: UniverseConfig SSOT 검증 테스트

UniverseConfig가 core/config.py에만 존재하고,
universe/builder.py는 UniverseBuilderConfig를 사용하는지 검증.
"""

import pytest


def test_universe_config_ssot():
    """
    UniverseConfig (core/config.py)와 UniverseBuilderConfig (universe/builder.py)가
    명확히 분리되어 있는지 검증.
    """
    from arbitrage.v2.core.config import UniverseConfig
    from arbitrage.v2.universe import UniverseBuilderConfig, UniverseMode
    
    # UniverseConfig (core/config.py)
    core_config = UniverseConfig(
        symbols_top_n=50,
        allowlist=["BTC/KRW", "ETH/KRW"],
        denylist=["DOGE/KRW"]
    )
    
    assert core_config.symbols_top_n == 50
    assert "BTC/KRW" in core_config.allowlist
    assert "DOGE/KRW" in core_config.denylist
    
    # UniverseBuilderConfig (universe/builder.py)
    builder_config = UniverseBuilderConfig(
        mode=UniverseMode.TOPN,
        topn_count=100,
        data_source="real"
    )
    
    assert builder_config.mode == UniverseMode.TOPN
    assert builder_config.topn_count == 100
    assert builder_config.data_source == "real"


def test_universe_config_types_are_different():
    """
    UniverseConfig와 UniverseBuilderConfig는 다른 타입이어야 함.
    """
    from arbitrage.v2.core.config import UniverseConfig
    from arbitrage.v2.universe import UniverseBuilderConfig
    
    assert UniverseConfig != UniverseBuilderConfig
    
    # 속성 차이 확인
    core_attrs = set(UniverseConfig.__annotations__.keys())
    builder_attrs = set(UniverseBuilderConfig.__annotations__.keys())
    
    # core/config.py UniverseConfig는 symbols_top_n를 가짐
    assert "symbols_top_n" in core_attrs
    assert "symbols_top_n" not in builder_attrs
    
    # universe/builder.py UniverseBuilderConfig는 mode를 가짐
    assert "mode" in builder_attrs
    assert "mode" not in core_attrs


def test_no_universe_config_in_builder_module():
    """
    universe/builder.py 모듈에 UniverseConfig (이름 그대로)가 존재하지 않는지 검증.
    
    D205-15-5 이전에는 universe/builder.py에도 UniverseConfig가 있었으나,
    SSOT 위반으로 UniverseBuilderConfig로 rename되었음.
    """
    # UniverseBuilderConfig는 정상 import
    from arbitrage.v2.universe import UniverseBuilderConfig
    assert UniverseBuilderConfig is not None
    
    # universe 모듈에서 UniverseConfig를 import하려고 하면 실패해야 함
    with pytest.raises(ImportError):
        from arbitrage.v2.universe import UniverseConfig
