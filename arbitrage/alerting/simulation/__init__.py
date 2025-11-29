"""
Incident Simulation Module for D76-4

This module provides incident simulation capabilities for testing
the alert infrastructure with realistic failure scenarios.
"""

from .incidents import (
    IncidentResult,
    simulate_redis_connection_loss,
    simulate_high_loop_latency,
    simulate_global_risk_block,
    simulate_ws_reconnect_storm,
    simulate_rate_limiter_low_remaining,
    simulate_rate_limiter_http_429,
    simulate_exchange_health_down,
    simulate_arb_universe_all_skip,
    simulate_cross_sync_high_imbalance,
    simulate_state_save_failed,
    simulate_exchange_health_frozen,
    simulate_cross_sync_high_exposure,
    get_all_incidents,
)

__all__ = [
    "IncidentResult",
    "simulate_redis_connection_loss",
    "simulate_high_loop_latency",
    "simulate_global_risk_block",
    "simulate_ws_reconnect_storm",
    "simulate_rate_limiter_low_remaining",
    "simulate_rate_limiter_http_429",
    "simulate_exchange_health_down",
    "simulate_arb_universe_all_skip",
    "simulate_cross_sync_high_imbalance",
    "simulate_state_save_failed",
    "simulate_exchange_health_frozen",
    "simulate_cross_sync_high_exposure",
    "get_all_incidents",
]
