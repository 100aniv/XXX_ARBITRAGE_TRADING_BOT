"""
D80-7-INT: Alert Integration Helpers

Helper functions for emitting rule-based alerts from domain layers.
"""

import logging
from typing import Dict, Any, Optional

from .models import AlertSeverity, AlertSource, AlertRecord
from .manager import AlertManager
from .alert_types import format_alert, get_alert_rule
from .throttler import AlertThrottler
from .config import get_alert_config

logger = logging.getLogger(__name__)


# Global instances (lazy-loaded)
_alert_manager: Optional[AlertManager] = None
_alert_throttler: Optional[AlertThrottler] = None


def get_global_alert_manager() -> AlertManager:
    """
    Get global AlertManager instance
    
    Returns:
        Global AlertManager
    """
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
        logger.info("[AlertHelper] Global AlertManager initialized")
    return _alert_manager


def get_global_alert_throttler() -> AlertThrottler:
    """
    Get global AlertThrottler instance
    
    Returns:
        Global AlertThrottler
    """
    global _alert_throttler
    if _alert_throttler is None:
        _alert_throttler = AlertThrottler(redis_client=None, window_seconds=300)
        logger.info("[AlertHelper] Global AlertThrottler initialized (in-memory mode)")
    return _alert_throttler


def emit_rule_based_alert(
    rule_id: str,
    context: Optional[Dict[str, Any]] = None,
    *,
    manager: Optional[AlertManager] = None,
    throttler: Optional[AlertThrottler] = None,
    enabled: bool = True,
) -> bool:
    """
    Emit rule-based alert with throttling and formatting
    
    Args:
        rule_id: Alert rule ID (e.g., "FX-001")
        context: Template formatting context (kwargs for format_alert)
        manager: AlertManager instance (uses global if None)
        throttler: AlertThrottler instance (uses global if None)
    
    Returns:
        True if alert was sent
    """
    # Check explicit enabled flag
    if not enabled:
        return False
    
    # Get config
    config = get_alert_config()
    
    if not config.enabled:
        return False
    
    if not config.is_rule_enabled(rule_id):
        logger.debug(f"[AlertHelper] Rule {rule_id} is disabled in config")
        return False
    
    # Get rule
    rule = get_alert_rule(rule_id)
    if rule is None:
        logger.error(f"[AlertHelper] Alert rule not found: {rule_id}")
        return False
    
    # Format alert
    context = context or {}
    try:
        formatted = format_alert(rule_id, **context)
        if formatted is None:
            logger.error(f"[AlertHelper] Failed to format alert: {rule_id}")
            return False
        
        rule, title, message = formatted
    except Exception as e:
        logger.error(f"[AlertHelper] Error formatting alert {rule_id}: {e}")
        return False
    
    # Generate throttle key
    # Use rule_id + key context fields (e.g., source, symbol)
    throttle_key_parts = [rule_id]
    
    # Add context-specific key parts for better throttling granularity
    if "source" in context:
        throttle_key_parts.append(str(context["source"]))
    elif "exchange" in context:
        throttle_key_parts.append(str(context["exchange"]))
    elif "symbol" in context:
        throttle_key_parts.append(str(context["symbol"]))
    
    throttle_key = ":".join(throttle_key_parts)
    
    # Check throttling
    throttler = throttler or get_global_alert_throttler()
    if not throttler.should_send(throttle_key):
        logger.debug(f"[AlertHelper] Alert throttled: {throttle_key}")
        return False
    
    # Send alert
    manager = manager or get_global_alert_manager()
    
    try:
        sent = manager.send_alert(
            severity=rule.severity,
            source=rule.source,
            title=title,
            message=message,
            metadata=context,
            rule_id=rule_id,
        )
        
        if sent:
            # Mark as sent in throttler
            throttler.mark_sent(throttle_key)
            logger.info(f"[AlertHelper] Alert sent: {rule_id} ({throttle_key})")
        
        return sent
    
    except Exception as e:
        logger.error(f"[AlertHelper] Error sending alert {rule_id}: {e}")
        return False


def emit_fx_source_down_alert(
    source: str,
    duration_seconds: int,
    pair: str = "USDT/USD",
    last_update: str = "",
    **kwargs
) -> bool:
    """
    Emit FX-001: FX source down alert
    
    Args:
        source: FX source name (e.g., "binance")
        duration_seconds: Down duration in seconds
        pair: Currency pair
        last_update: Last update timestamp
        **kwargs: Additional context
    
    Returns:
        True if alert was sent
    """
    context = {
        "source": source,
        "duration_seconds": duration_seconds,
        "pair": pair,
        "last_update": last_update or "N/A",
    }
    # Extract enabled flag
    enabled = kwargs.pop("enabled", True)
    context.update(kwargs)
    
    return emit_rule_based_alert("FX-001", context, enabled=enabled)


def emit_fx_all_sources_down_alert(
    pair: str,
    down_sources: str,
    duration_seconds: int,
    **kwargs
) -> bool:
    """
    Emit FX-002: All FX sources down alert
    
    Args:
        pair: Currency pair
        down_sources: Comma-separated list of down sources
        duration_seconds: Down duration in seconds
        **kwargs: Additional context
    
    Returns:
        True if alert was sent
    """
    context = {
        "pair": pair,
        "down_sources": down_sources,
        "duration_seconds": duration_seconds,
    }
    enabled = kwargs.pop("enabled", True)
    context.update(kwargs)
    
    return emit_rule_based_alert("FX-002", context, enabled=enabled)


def emit_fx_median_deviation_alert(
    pair: str,
    median_rate: float,
    expected_min: float,
    expected_max: float,
    deviation_percent: float,
    outliers: str,
    **kwargs
) -> bool:
    """
    Emit FX-003: FX median deviation alert
    
    Args:
        pair: Currency pair
        median_rate: Median rate
        expected_min: Expected minimum rate
        expected_max: Expected maximum rate
        deviation_percent: Deviation percentage
        outliers: Outlier sources
        **kwargs: Additional context
    
    Returns:
        True if alert was sent
    """
    context = {
        "pair": pair,
        "median_rate": median_rate,
        "expected_min": expected_min,
        "expected_max": expected_max,
        "deviation_percent": deviation_percent,
        "outliers": outliers,
    }
    enabled = kwargs.pop("enabled", True)
    context.update(kwargs)
    
    return emit_rule_based_alert("FX-003", context, enabled=enabled)


def emit_fx_staleness_alert(
    source: str,
    pair: str,
    age_seconds: int,
    last_rate: float,
    **kwargs
) -> bool:
    """
    Emit FX-004: FX rate staleness alert
    
    Args:
        source: FX source name
        pair: Currency pair
        age_seconds: Age in seconds
        last_rate: Last known rate
        **kwargs: Additional context
    
    Returns:
        True if alert was sent
    """
    context = {
        "source": source,
        "pair": pair,
        "age_seconds": age_seconds,
        "last_rate": last_rate,
    }
    enabled = kwargs.pop("enabled", True)
    context.update(kwargs)
    
    return emit_rule_based_alert("FX-004", context, enabled=enabled)


def emit_executor_order_error_alert(
    exchange: str,
    symbol: str,
    side: str,
    error_message: str,
    action: str = "Skipped",
    **kwargs
) -> bool:
    """
    Emit EX-001: Executor order error alert
    
    Args:
        exchange: Exchange name
        symbol: Trading symbol
        side: Order side (BUY/SELL)
        error_message: Error message
        action: Action taken
        **kwargs: Additional context
    
    Returns:
        True if alert was sent
    """
    context = {
        "exchange": exchange,
        "symbol": symbol,
        "side": side,
        "error_message": error_message,
        "action": action,
    }
    enabled = kwargs.pop("enabled", True)
    context.update(kwargs)
    
    return emit_rule_based_alert("EX-001", context, enabled=enabled)


def emit_executor_rollback_alert(
    symbol: str,
    exchange: str,
    filled_qty: float,
    requested_qty: float,
    status: str,
    **kwargs
) -> bool:
    """
    Emit EX-002: Executor rollback alert
    
    Args:
        symbol: Trading symbol
        exchange: Exchange name
        filled_qty: Filled quantity
        requested_qty: Requested quantity
        status: Order status
        **kwargs: Additional context
    
    Returns:
        True if alert was sent
    """
    context = {
        "symbol": symbol,
        "exchange": exchange,
        "filled_qty": filled_qty,
        "requested_qty": requested_qty,
        "status": status,
    }
    enabled = kwargs.pop("enabled", True)
    context.update(kwargs)
    
    return emit_rule_based_alert("EX-002", context, enabled=enabled)


def emit_circuit_breaker_alert(
    reason: str,
    threshold: str,
    current_value: str,
    cooldown_seconds: int,
    **kwargs
) -> bool:
    """
    Emit RG-001: Circuit breaker triggered alert
    
    Args:
        reason: Trigger reason
        threshold: Threshold value
        current_value: Current value
        cooldown_seconds: Cooldown duration
        **kwargs: Additional context
    
    Returns:
        True if alert was sent
    """
    context = {
        "reason": reason,
        "threshold": threshold,
        "current_value": current_value,
        "cooldown_seconds": cooldown_seconds,
    }
    enabled = kwargs.pop("enabled", True)
    context.update(kwargs)
    
    return emit_rule_based_alert("RG-001", context, enabled=enabled)


def emit_risk_limit_alert(
    limit_type: str,
    current_value: str,
    limit_value: str,
    action: str,
    **kwargs
) -> bool:
    """
    Emit RG-002: Risk limit hit alert
    
    Args:
        limit_type: Limit type
        current_value: Current value
        limit_value: Limit value
        action: Action taken
        **kwargs: Additional context
    
    Returns:
        True if alert was sent
    """
    context = {
        "limit_type": limit_type,
        "current_value": current_value,
        "limit_value": limit_value,
        "action": action,
    }
    enabled = kwargs.pop("enabled", True)
    context.update(kwargs)
    
    return emit_rule_based_alert("RG-002", context, enabled=enabled)


def emit_ws_staleness_alert(
    source: str,
    stream: str,
    age_seconds: int,
    last_message_time: str,
    **kwargs
) -> bool:
    """
    Emit WS-001: WebSocket data staleness alert
    
    Args:
        source: WebSocket source
        stream: Stream name
        age_seconds: Age in seconds
        last_message_time: Last message timestamp
        **kwargs: Additional context
    
    Returns:
        True if alert was sent
    """
    context = {
        "source": source,
        "stream": stream,
        "age_seconds": age_seconds,
        "last_message_time": last_message_time,
    }
    enabled = kwargs.pop("enabled", True)
    context.update(kwargs)
    
    return emit_rule_based_alert("WS-001", context, enabled=enabled)


def emit_ws_reconnect_failed_alert(
    source: str,
    stream: str,
    attempts: int,
    max_attempts: int,
    error_message: str,
    action: str = "Retry",
    **kwargs
) -> bool:
    """
    Emit WS-002: WebSocket reconnect failed alert
    
    Args:
        source: WebSocket source
        stream: Stream name
        attempts: Current attempts
        max_attempts: Maximum attempts
        error_message: Error message
        action: Action taken
        **kwargs: Additional context
    
    Returns:
        True if alert was sent
    """
    context = {
        "source": source,
        "stream": stream,
        "attempts": attempts,
        "max_attempts": max_attempts,
        "error_message": error_message,
        "action": action,
    }
    enabled = kwargs.pop("enabled", True)
    context.update(kwargs)
    
    return emit_rule_based_alert("WS-002", context, enabled=enabled)
