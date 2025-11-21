"""
Configuration Module for Arbitrage Trading System

This module provides a standardized, environment-aware configuration system
with validation, secrets management, and SSOT (Single Source of Truth) principles.

Usage:
    from config import load_config
    
    # Automatically loads based on ENV environment variable
    config = load_config()
    
    # Or explicitly specify environment
    config = load_config(env='production')
"""

# Lazy imports to avoid circular dependency
def __getattr__(name):
    if name == 'load_config':
        from config.loader import load_config
        return load_config
    elif name == 'get_current_env':
        from config.loader import get_current_env
        return get_current_env
    elif name in ['ArbitrageConfig', 'ExchangeConfig', 'RiskConfig', 'MonitoringConfig', 'DatabaseConfig', 'SessionConfig', 'TradingConfig']:
        from config.base import (
            ArbitrageConfig,
            ExchangeConfig,
            RiskConfig,
            MonitoringConfig,
            DatabaseConfig,
            SessionConfig,
            TradingConfig
        )
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'load_config',
    'get_current_env',
    'ArbitrageConfig',
    'ExchangeConfig',
    'RiskConfig',
    'MonitoringConfig',
    'DatabaseConfig',
    'SessionConfig',
    'TradingConfig'
]

__version__ = '1.0.0'
