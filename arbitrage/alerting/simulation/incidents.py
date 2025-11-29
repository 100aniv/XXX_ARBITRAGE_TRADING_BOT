"""
Incident Simulation Functions for D76-4

This module implements 12+ realistic incident scenarios for testing
the D75/D76 alerting infrastructure.

Each incident function:
1. Simulates a specific failure/risk scenario
2. Triggers alerts via AlertManager
3. Returns an IncidentResult with verification data
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from arbitrage.alerting.manager import AlertManager
from arbitrage.alerting.models import AlertSeverity, AlertSource
from arbitrage.alerting.rule_engine import AlertDispatchPlan, Environment


@dataclass
class IncidentResult:
    """Result of an incident simulation"""
    name: str
    rule_id: str
    severity: AlertSeverity
    dispatch_plan: AlertDispatchPlan
    storage_saved: bool
    telegram_sent: bool
    slack_sent: bool
    email_sent: bool
    timestamp: datetime
    metadata: dict
    
    def to_dict(self) -> dict:
        """Convert to dictionary for reporting"""
        return {
            "name": self.name,
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "dispatch_plan": {
                "telegram": self.dispatch_plan.telegram,
                "slack": self.dispatch_plan.slack,
                "email": self.dispatch_plan.email,
                "postgres": self.dispatch_plan.postgres,
            },
            "actual_delivery": {
                "storage_saved": self.storage_saved,
                "telegram_sent": self.telegram_sent,
                "slack_sent": self.slack_sent,
                "email_sent": self.email_sent,
            },
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================================
# Incident 1: Redis Connection Loss
# ============================================================================

def simulate_redis_connection_loss(
    manager: AlertManager,
    environment: Environment = Environment.PROD,
) -> IncidentResult:
    """
    Simulate Redis connection loss
    
    Rule ID: D75.SYSTEM.REDIS_CONNECTION_LOST
    Severity: P0 (Critical)
    Expected Channels:
        - PROD: Telegram + PostgreSQL
        - DEV: Telegram + Slack + PostgreSQL
    """
    rule_id = "D75.SYSTEM.REDIS_CONNECTION_LOST"
    severity = AlertSeverity.P0
    
    success = manager.send_alert(
        severity=severity,
        source=AlertSource.SYSTEM,
        title="Redis Connection Lost",
        message="Redis connection timeout after 3 retry attempts. "
                "System state persistence unavailable. Recommend immediate investigation.",
        rule_id=rule_id,
        metadata={
            "connection_attempts": 3,
            "last_error": "ConnectionRefusedError: [Errno 111] Connection refused",
            "redis_host": "localhost:6379",
        }
    )
    
    # Get dispatch plan from rule engine
    from arbitrage.alerting.models import AlertRecord
    alert = AlertRecord(
        severity=severity,
        source=AlertSource.SYSTEM,
        title="Redis Connection Lost",
        message="Test",
    )
    dispatch_plan = manager.rule_engine.evaluate_alert(alert, rule_id, skip_throttle=True)
    
    return IncidentResult(
        name="Redis Connection Loss",
        rule_id=rule_id,
        severity=severity,
        dispatch_plan=dispatch_plan,
        storage_saved=success and dispatch_plan.postgres,
        telegram_sent=success and dispatch_plan.telegram and "telegram" in manager._notifiers,
        slack_sent=success and dispatch_plan.slack and "slack" in manager._notifiers,
        email_sent=success and dispatch_plan.email and "email" in manager._notifiers,
        timestamp=datetime.now(),
        metadata={"environment": environment.value},
    )


# ============================================================================
# Incident 2: High Loop Latency Spike
# ============================================================================

def simulate_high_loop_latency(
    manager: AlertManager,
    environment: Environment = Environment.PROD,
) -> IncidentResult:
    """
    Simulate engine loop latency spike
    
    Rule ID: D75.SYSTEM.ENGINE_LATENCY
    Severity: P1 (High)
    Expected Channels:
        - PROD: Telegram + PostgreSQL
        - DEV: Telegram + Slack + PostgreSQL
    """
    rule_id = "D75.SYSTEM.ENGINE_LATENCY"
    severity = AlertSeverity.P1
    
    success = manager.send_alert(
        severity=severity,
        source=AlertSource.SYSTEM,
        title="Engine Latency Spike Detected",
        message="Loop latency exceeded 100ms threshold for 5 consecutive iterations. "
                "Current: 125ms (avg), 180ms (max). Performance degradation detected.",
        rule_id=rule_id,
        metadata={
            "latency_avg_ms": 125.4,
            "latency_max_ms": 180.2,
            "threshold_ms": 100.0,
            "consecutive_violations": 5,
            "loop_iterations": 1250,
        }
    )
    
    from arbitrage.alerting.models import AlertRecord
    alert = AlertRecord(
        severity=severity,
        source=AlertSource.SYSTEM,
        title="Engine Latency Spike Detected",
        message="Test",
    )
    dispatch_plan = manager.rule_engine.evaluate_alert(alert, rule_id, skip_throttle=True)
    
    return IncidentResult(
        name="High Loop Latency Spike",
        rule_id=rule_id,
        severity=severity,
        dispatch_plan=dispatch_plan,
        storage_saved=success and dispatch_plan.postgres,
        telegram_sent=success and dispatch_plan.telegram and "telegram" in manager._notifiers,
        slack_sent=success and dispatch_plan.slack and "slack" in manager._notifiers,
        email_sent=success and dispatch_plan.email and "email" in manager._notifiers,
        timestamp=datetime.now(),
        metadata={"environment": environment.value},
    )


# ============================================================================
# Incident 3: RiskGuard Global Block (Daily Loss Limit)
# ============================================================================

def simulate_global_risk_block(
    manager: AlertManager,
    environment: Environment = Environment.PROD,
) -> IncidentResult:
    """
    Simulate global risk block due to daily loss limit
    
    Rule ID: D75.RISK_GUARD.GLOBAL_BLOCK
    Severity: P0 (Critical)
    Expected Channels:
        - PROD: Telegram + PostgreSQL (Never throttled!)
        - DEV: Telegram + Slack + PostgreSQL
    """
    rule_id = "D75.RISK_GUARD.GLOBAL_BLOCK"
    severity = AlertSeverity.P0
    
    success = manager.send_alert(
        severity=severity,
        source=AlertSource.RISK_GUARD,
        title="GLOBAL BLOCK - Trading HALTED",
        message="Global daily loss limit exceeded. All trading activity immediately halted. "
                "Current loss: $12,450.00 / Limit: $10,000.00. Requires manual intervention.",
        rule_id=rule_id,
        metadata={
            "current_loss_usd": 12450.00,
            "daily_loss_limit_usd": 10000.00,
            "breach_percentage": 124.5,
            "guard_tier": "GlobalGuard",
            "decision": "BLOCK",
            "reason_code": "DAILY_LOSS_LIMIT_EXCEEDED",
        }
    )
    
    from arbitrage.alerting.models import AlertRecord
    alert = AlertRecord(
        severity=severity,
        source=AlertSource.RISK_GUARD,
        title="GLOBAL BLOCK - Trading HALTED",
        message="Test",
    )
    dispatch_plan = manager.rule_engine.evaluate_alert(alert, rule_id, skip_throttle=True)
    
    return IncidentResult(
        name="Global Risk Block (Daily Loss)",
        rule_id=rule_id,
        severity=severity,
        dispatch_plan=dispatch_plan,
        storage_saved=success and dispatch_plan.postgres,
        telegram_sent=success and dispatch_plan.telegram and "telegram" in manager._notifiers,
        slack_sent=success and dispatch_plan.slack and "slack" in manager._notifiers,
        email_sent=success and dispatch_plan.email and "email" in manager._notifiers,
        timestamp=datetime.now(),
        metadata={"environment": environment.value},
    )


# ============================================================================
# Incident 4: WebSocket Reconnect Storm
# ============================================================================

def simulate_ws_reconnect_storm(
    manager: AlertManager,
    environment: Environment = Environment.PROD,
) -> IncidentResult:
    """
    Simulate WebSocket reconnection storm
    
    Rule ID: D75.SYSTEM.WS_RECONNECT_STORM
    Severity: P1 (High)
    Expected Channels:
        - PROD: Telegram + PostgreSQL
        - DEV: Telegram + Slack + PostgreSQL
    """
    rule_id = "D75.SYSTEM.WS_RECONNECT_STORM"
    severity = AlertSeverity.P1
    
    success = manager.send_alert(
        severity=severity,
        source=AlertSource.SYSTEM,
        title="WebSocket Reconnect Storm",
        message="Excessive WS reconnections detected. 15 reconnects in 5 minutes. "
                "Possible network instability or exchange-side issues.",
        rule_id=rule_id,
        metadata={
            "reconnect_count": 15,
            "time_window_minutes": 5,
            "affected_exchanges": ["Upbit", "Binance"],
            "last_disconnect_reason": "1006 Connection closed abnormally",
        }
    )
    
    from arbitrage.alerting.models import AlertRecord
    alert = AlertRecord(
        severity=severity,
        source=AlertSource.SYSTEM,
        title="WebSocket Reconnect Storm",
        message="Test",
    )
    dispatch_plan = manager.rule_engine.evaluate_alert(alert, rule_id, skip_throttle=True)
    
    return IncidentResult(
        name="WebSocket Reconnect Storm",
        rule_id=rule_id,
        severity=severity,
        dispatch_plan=dispatch_plan,
        storage_saved=success and dispatch_plan.postgres,
        telegram_sent=success and dispatch_plan.telegram and "telegram" in manager._notifiers,
        slack_sent=success and dispatch_plan.slack and "slack" in manager._notifiers,
        email_sent=success and dispatch_plan.email and "email" in manager._notifiers,
        timestamp=datetime.now(),
        metadata={"environment": environment.value},
    )


# ============================================================================
# Incident 5: RateLimiter Low Remaining
# ============================================================================

def simulate_rate_limiter_low_remaining(
    manager: AlertManager,
    environment: Environment = Environment.PROD,
) -> IncidentResult:
    """
    Simulate rate limit low remaining capacity
    
    Rule ID: D75.RATE_LIMITER.LOW_REMAINING
    Severity: P2 (Medium)
    Expected Channels:
        - PROD: PostgreSQL only (Telegram opt-in via env var)
        - DEV: Telegram + Slack + Email + PostgreSQL
    """
    rule_id = "D75.RATE_LIMITER.LOW_REMAINING"
    severity = AlertSeverity.P2
    
    success = manager.send_alert(
        severity=severity,
        source=AlertSource.RATE_LIMITER,
        title="Rate Limit Warning - Low Remaining",
        message="Upbit REST API rate limit capacity below 20%. "
                "Current: 15/100 tokens. Consider throttling non-critical requests.",
        rule_id=rule_id,
        metadata={
            "exchange": "Upbit",
            "category": "REST_API",
            "remaining": 15,
            "limit": 100,
            "remaining_pct": 15.0,
            "threshold_pct": 20.0,
        }
    )
    
    from arbitrage.alerting.models import AlertRecord
    alert = AlertRecord(
        severity=severity,
        source=AlertSource.RATE_LIMITER,
        title="Rate Limit Warning - Low Remaining",
        message="Test",
    )
    dispatch_plan = manager.rule_engine.evaluate_alert(alert, rule_id, skip_throttle=True)
    
    return IncidentResult(
        name="RateLimiter Low Remaining",
        rule_id=rule_id,
        severity=severity,
        dispatch_plan=dispatch_plan,
        storage_saved=success and dispatch_plan.postgres,
        telegram_sent=success and dispatch_plan.telegram and "telegram" in manager._notifiers,
        slack_sent=success and dispatch_plan.slack and "slack" in manager._notifiers,
        email_sent=success and dispatch_plan.email and "email" in manager._notifiers,
        timestamp=datetime.now(),
        metadata={"environment": environment.value},
    )


# ============================================================================
# Incident 6: RateLimiter HTTP 429
# ============================================================================

def simulate_rate_limiter_http_429(
    manager: AlertManager,
    environment: Environment = Environment.PROD,
) -> IncidentResult:
    """
    Simulate HTTP 429 (Too Many Requests) response
    
    Rule ID: D75.RATE_LIMITER.HTTP_429
    Severity: P1 (High)
    Expected Channels:
        - PROD: Telegram + PostgreSQL
        - DEV: Telegram + Slack + PostgreSQL
    """
    rule_id = "D75.RATE_LIMITER.HTTP_429"
    severity = AlertSeverity.P1
    
    success = manager.send_alert(
        severity=severity,
        source=AlertSource.RATE_LIMITER,
        title="HTTP 429 Received - Rate Limit Exceeded",
        message="Binance API returned HTTP 429. Request rate exceeded exchange limits. "
                "Automatic backoff applied. Retry after: 60 seconds.",
        rule_id=rule_id,
        metadata={
            "exchange": "Binance",
            "endpoint": "/api/v3/order",
            "status_code": 429,
            "retry_after_seconds": 60,
            "request_weight": 2,
        }
    )
    
    from arbitrage.alerting.models import AlertRecord
    alert = AlertRecord(
        severity=severity,
        source=AlertSource.RATE_LIMITER,
        title="HTTP 429 Received",
        message="Test",
    )
    dispatch_plan = manager.rule_engine.evaluate_alert(alert, rule_id, skip_throttle=True)
    
    return IncidentResult(
        name="RateLimiter HTTP 429",
        rule_id=rule_id,
        severity=severity,
        dispatch_plan=dispatch_plan,
        storage_saved=success and dispatch_plan.postgres,
        telegram_sent=success and dispatch_plan.telegram and "telegram" in manager._notifiers,
        slack_sent=success and dispatch_plan.slack and "slack" in manager._notifiers,
        email_sent=success and dispatch_plan.email and "email" in manager._notifiers,
        timestamp=datetime.now(),
        metadata={"environment": environment.value},
    )


# ============================================================================
# Incident 7: Exchange Health DOWN
# ============================================================================

def simulate_exchange_health_down(
    manager: AlertManager,
    environment: Environment = Environment.PROD,
) -> IncidentResult:
    """
    Simulate exchange health status transition to DOWN
    
    Rule ID: D75.HEALTH.DOWN
    Severity: P1 (High)
    Expected Channels:
        - PROD: Telegram + PostgreSQL
        - DEV: Telegram + Slack + PostgreSQL
    """
    rule_id = "D75.HEALTH.DOWN"
    severity = AlertSeverity.P1
    
    success = manager.send_alert(
        severity=severity,
        source=AlertSource.HEALTH_MONITOR,
        title="Exchange Health DOWN",
        message="Upbit health status degraded to DOWN. Consecutive failures: 5. "
                "Last error: 503 Service Unavailable. Trading suspended on this exchange.",
        rule_id=rule_id,
        metadata={
            "exchange": "Upbit",
            "previous_status": "DEGRADED",
            "current_status": "DOWN",
            "consecutive_failures": 5,
            "last_error": "503 Service Unavailable",
            "last_success_timestamp": "2025-11-23T10:45:32Z",
        }
    )
    
    from arbitrage.alerting.models import AlertRecord
    alert = AlertRecord(
        severity=severity,
        source=AlertSource.HEALTH_MONITOR,
        title="Exchange Health DOWN",
        message="Test",
    )
    dispatch_plan = manager.rule_engine.evaluate_alert(alert, rule_id, skip_throttle=True)
    
    return IncidentResult(
        name="Exchange Health DOWN",
        rule_id=rule_id,
        severity=severity,
        dispatch_plan=dispatch_plan,
        storage_saved=success and dispatch_plan.postgres,
        telegram_sent=success and dispatch_plan.telegram and "telegram" in manager._notifiers,
        slack_sent=success and dispatch_plan.slack and "slack" in manager._notifiers,
        email_sent=success and dispatch_plan.email and "email" in manager._notifiers,
        timestamp=datetime.now(),
        metadata={"environment": environment.value},
    )


# ============================================================================
# Incident 8: ArbUniverse ALL_SKIP
# ============================================================================

def simulate_arb_universe_all_skip(
    manager: AlertManager,
    environment: Environment = Environment.PROD,
) -> IncidentResult:
    """
    Simulate all arbitrage routes marked as SKIP
    
    Rule ID: D75.ARB_UNIVERSE.ALL_SKIP
    Severity: P1 (High)
    Expected Channels:
        - PROD: Telegram + PostgreSQL
        - DEV: Telegram + Slack + PostgreSQL
    """
    rule_id = "D75.ARB_UNIVERSE.ALL_SKIP"
    severity = AlertSeverity.P1
    
    success = manager.send_alert(
        severity=severity,
        source=AlertSource.ARB_UNIVERSE,
        title="All Arbitrage Routes SKIP",
        message="All 15 monitored routes returned SKIP decision. No profitable arbitrage opportunities. "
                "Possible market-wide low volatility or data feed issues.",
        rule_id=rule_id,
        metadata={
            "total_routes": 15,
            "skip_count": 15,
            "max_spread_bps": 3.2,
            "min_spread_threshold_bps": 20.0,
            "evaluation_timestamp": "2025-11-23T11:15:00Z",
        }
    )
    
    from arbitrage.alerting.models import AlertRecord
    alert = AlertRecord(
        severity=severity,
        source=AlertSource.ARB_UNIVERSE,
        title="All Arbitrage Routes SKIP",
        message="Test",
    )
    dispatch_plan = manager.rule_engine.evaluate_alert(alert, rule_id, skip_throttle=True)
    
    return IncidentResult(
        name="ArbUniverse ALL_SKIP",
        rule_id=rule_id,
        severity=severity,
        dispatch_plan=dispatch_plan,
        storage_saved=success and dispatch_plan.postgres,
        telegram_sent=success and dispatch_plan.telegram and "telegram" in manager._notifiers,
        slack_sent=success and dispatch_plan.slack and "slack" in manager._notifiers,
        email_sent=success and dispatch_plan.email and "email" in manager._notifiers,
        timestamp=datetime.now(),
        metadata={"environment": environment.value},
    )


# ============================================================================
# Incident 9: CrossSync High Imbalance
# ============================================================================

def simulate_cross_sync_high_imbalance(
    manager: AlertManager,
    environment: Environment = Environment.PROD,
) -> IncidentResult:
    """
    Simulate high inventory imbalance across exchanges
    
    Rule ID: D75.CROSS_SYNC.HIGH_IMBALANCE
    Severity: P2 (Medium)
    Expected Channels:
        - PROD: PostgreSQL only (Telegram opt-in)
        - DEV: Telegram + Slack + Email + PostgreSQL
    """
    rule_id = "D75.CROSS_SYNC.HIGH_IMBALANCE"
    severity = AlertSeverity.P2
    
    success = manager.send_alert(
        severity=severity,
        source=AlertSource.CROSS_SYNC,
        title="High Inventory Imbalance",
        message="BTC inventory imbalance across exchanges: 62.5%. "
                "Upbit: 3.2 BTC, Binance: 0.8 BTC. Consider rebalancing.",
        rule_id=rule_id,
        metadata={
            "symbol": "BTC",
            "imbalance_ratio": 0.625,
            "threshold": 0.50,
            "exchange_a": "Upbit",
            "exchange_b": "Binance",
            "inventory_a": 3.2,
            "inventory_b": 0.8,
        }
    )
    
    from arbitrage.alerting.models import AlertRecord
    alert = AlertRecord(
        severity=severity,
        source=AlertSource.CROSS_SYNC,
        title="High Inventory Imbalance",
        message="Test",
    )
    dispatch_plan = manager.rule_engine.evaluate_alert(alert, rule_id, skip_throttle=True)
    
    return IncidentResult(
        name="CrossSync High Imbalance",
        rule_id=rule_id,
        severity=severity,
        dispatch_plan=dispatch_plan,
        storage_saved=success and dispatch_plan.postgres,
        telegram_sent=success and dispatch_plan.telegram and "telegram" in manager._notifiers,
        slack_sent=success and dispatch_plan.slack and "slack" in manager._notifiers,
        email_sent=success and dispatch_plan.email and "email" in manager._notifiers,
        timestamp=datetime.now(),
        metadata={"environment": environment.value},
    )


# ============================================================================
# Incident 10: State Snapshot Save Failed
# ============================================================================

def simulate_state_save_failed(
    manager: AlertManager,
    environment: Environment = Environment.PROD,
) -> IncidentResult:
    """
    Simulate state snapshot save failure
    
    Rule ID: D75.SYSTEM.STATE_SAVE_FAILED
    Severity: P2 (Medium)
    Expected Channels:
        - PROD: PostgreSQL only (Telegram opt-in)
        - DEV: Telegram + Slack + Email + PostgreSQL
    """
    rule_id = "D75.SYSTEM.STATE_SAVE_FAILED"
    severity = AlertSeverity.P2
    
    success = manager.send_alert(
        severity=severity,
        source=AlertSource.SYSTEM,
        title="State Snapshot Save Failed",
        message="Failed to save engine state snapshot to PostgreSQL. "
                "Error: Connection timeout. Failover/resume capability may be affected.",
        rule_id=rule_id,
        metadata={
            "snapshot_id": "snapshot_20251123_113000",
            "error_type": "ConnectionTimeout",
            "error_message": "Connection to PostgreSQL timed out after 5 seconds",
            "retry_attempt": 3,
        }
    )
    
    from arbitrage.alerting.models import AlertRecord
    alert = AlertRecord(
        severity=severity,
        source=AlertSource.SYSTEM,
        title="State Snapshot Save Failed",
        message="Test",
    )
    dispatch_plan = manager.rule_engine.evaluate_alert(alert, rule_id, skip_throttle=True)
    
    return IncidentResult(
        name="State Snapshot Save Failed",
        rule_id=rule_id,
        severity=severity,
        dispatch_plan=dispatch_plan,
        storage_saved=success and dispatch_plan.postgres,
        telegram_sent=success and dispatch_plan.telegram and "telegram" in manager._notifiers,
        slack_sent=success and dispatch_plan.slack and "slack" in manager._notifiers,
        email_sent=success and dispatch_plan.email and "email" in manager._notifiers,
        timestamp=datetime.now(),
        metadata={"environment": environment.value},
    )


# ============================================================================
# Incident 11: Exchange Health FROZEN (Bonus)
# ============================================================================

def simulate_exchange_health_frozen(
    manager: AlertManager,
    environment: Environment = Environment.PROD,
) -> IncidentResult:
    """
    Simulate exchange health status transition to FROZEN
    
    Rule ID: D75.HEALTH.FROZEN
    Severity: P0 (Critical)
    Expected Channels:
        - PROD: Telegram + PostgreSQL
        - DEV: Telegram + Slack + PostgreSQL
    """
    rule_id = "D75.HEALTH.FROZEN"
    severity = AlertSeverity.P0
    
    success = manager.send_alert(
        severity=severity,
        source=AlertSource.HEALTH_MONITOR,
        title="Exchange Health FROZEN",
        message="Binance health status degraded to FROZEN. Extended downtime detected (>10 minutes). "
                "All trading activities on this exchange are halted.",
        rule_id=rule_id,
        metadata={
            "exchange": "Binance",
            "previous_status": "DOWN",
            "current_status": "FROZEN",
            "downtime_minutes": 12.5,
            "freeze_threshold_minutes": 10.0,
        }
    )
    
    from arbitrage.alerting.models import AlertRecord
    alert = AlertRecord(
        severity=severity,
        source=AlertSource.HEALTH_MONITOR,
        title="Exchange Health FROZEN",
        message="Test",
    )
    dispatch_plan = manager.rule_engine.evaluate_alert(alert, rule_id, skip_throttle=True)
    
    return IncidentResult(
        name="Exchange Health FROZEN",
        rule_id=rule_id,
        severity=severity,
        dispatch_plan=dispatch_plan,
        storage_saved=success and dispatch_plan.postgres,
        telegram_sent=success and dispatch_plan.telegram and "telegram" in manager._notifiers,
        slack_sent=success and dispatch_plan.slack and "slack" in manager._notifiers,
        email_sent=success and dispatch_plan.email and "email" in manager._notifiers,
        timestamp=datetime.now(),
        metadata={"environment": environment.value},
    )


# ============================================================================
# Incident 12: CrossSync High Exposure (Bonus)
# ============================================================================

def simulate_cross_sync_high_exposure(
    manager: AlertManager,
    environment: Environment = Environment.PROD,
) -> IncidentResult:
    """
    Simulate high cross-exchange exposure risk
    
    Rule ID: D75.CROSS_SYNC.HIGH_EXPOSURE
    Severity: P1 (High)
    Expected Channels:
        - PROD: Telegram + PostgreSQL
        - DEV: Telegram + Slack + PostgreSQL
    """
    rule_id = "D75.CROSS_SYNC.HIGH_EXPOSURE"
    severity = AlertSeverity.P1
    
    success = manager.send_alert(
        severity=severity,
        source=AlertSource.CROSS_SYNC,
        title="High Cross-Exchange Exposure",
        message="Total cross-exchange exposure exceeds threshold: 85.2% of portfolio. "
                "Exposure limit: 80%. Recommend reducing open positions.",
        rule_id=rule_id,
        metadata={
            "exposure_ratio": 0.852,
            "threshold": 0.80,
            "total_exposure_usd": 42600.00,
            "portfolio_value_usd": 50000.00,
            "open_positions": 8,
        }
    )
    
    from arbitrage.alerting.models import AlertRecord
    alert = AlertRecord(
        severity=severity,
        source=AlertSource.CROSS_SYNC,
        title="High Cross-Exchange Exposure",
        message="Test",
    )
    dispatch_plan = manager.rule_engine.evaluate_alert(alert, rule_id, skip_throttle=True)
    
    return IncidentResult(
        name="CrossSync High Exposure",
        rule_id=rule_id,
        severity=severity,
        dispatch_plan=dispatch_plan,
        storage_saved=success and dispatch_plan.postgres,
        telegram_sent=success and dispatch_plan.telegram and "telegram" in manager._notifiers,
        slack_sent=success and dispatch_plan.slack and "slack" in manager._notifiers,
        email_sent=success and dispatch_plan.email and "email" in manager._notifiers,
        timestamp=datetime.now(),
        metadata={"environment": environment.value},
    )


# ============================================================================
# Helper Functions
# ============================================================================

def get_all_incidents():
    """Get all incident simulation functions"""
    return [
        ("Redis Connection Loss", simulate_redis_connection_loss),
        ("High Loop Latency", simulate_high_loop_latency),
        ("Global Risk Block", simulate_global_risk_block),
        ("WS Reconnect Storm", simulate_ws_reconnect_storm),
        ("RateLimiter Low Remaining", simulate_rate_limiter_low_remaining),
        ("RateLimiter HTTP 429", simulate_rate_limiter_http_429),
        ("Exchange Health DOWN", simulate_exchange_health_down),
        ("ArbUniverse ALL_SKIP", simulate_arb_universe_all_skip),
        ("CrossSync High Imbalance", simulate_cross_sync_high_imbalance),
        ("State Snapshot Save Failed", simulate_state_save_failed),
        ("Exchange Health FROZEN", simulate_exchange_health_frozen),
        ("CrossSync High Exposure", simulate_cross_sync_high_exposure),
    ]
