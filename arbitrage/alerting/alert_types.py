"""
D80-7: Alert Types and Rules for Cross-Exchange Arbitrage

Alert rule definitions for FX, Executor, RiskGuard, and WebSocket layers.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum

from .models import AlertSeverity, AlertSource


class AlertCategory(Enum):
    """Alert categories for aggregation"""
    FX = "FX"
    EXECUTOR = "EXECUTOR"
    RISK_GUARD = "RISK_GUARD"
    WEBSOCKET = "WEBSOCKET"


@dataclass
class AlertRuleDefinition:
    """
    Alert rule definition
    
    Attributes:
        rule_id: Unique rule identifier (e.g., "FX-001")
        category: Alert category for aggregation
        severity: Default severity level
        title_template: Alert title template
        message_template: Alert message template
        aggregation_key: Key for grouping related alerts
    """
    rule_id: str
    category: AlertCategory
    severity: AlertSeverity
    source: AlertSource
    title_template: str
    message_template: str
    aggregation_key: Optional[str] = None
    
    def format(self, **kwargs) -> tuple[str, str]:
        """
        Format title and message with provided kwargs
        
        Returns:
            (title, message) tuple
        """
        title = self.title_template.format(**kwargs)
        message = self.message_template.format(**kwargs)
        return title, message


# =============================================================================
# FX Layer Alert Rules
# =============================================================================

FX_001 = AlertRuleDefinition(
    rule_id="FX-001",
    category=AlertCategory.FX,
    severity=AlertSeverity.P2,
    source=AlertSource.FX_LAYER,
    title_template="FX Source Down: {source}",
    message_template=(
        "⚠️ FX source '{source}' has been down for {duration_seconds}s (threshold: 30s)\n"
        "Pair: {pair}\n"
        "Last update: {last_update}\n"
        "Action: Using fallback rate provider"
    ),
    aggregation_key="fx_source_down",
)

FX_002 = AlertRuleDefinition(
    rule_id="FX-002",
    category=AlertCategory.FX,
    severity=AlertSeverity.P0,  # Critical
    source=AlertSource.FX_LAYER,
    title_template="🔴 ALL FX Sources Down - CRITICAL",
    message_template=(
        "🚨 CRITICAL: ALL FX sources are DOWN\n"
        "Pair: {pair}\n"
        "Down sources: {down_sources}\n"
        "Duration: {duration_seconds}s\n"
        "⚠️ Action Required: Check network connectivity and external FX APIs"
    ),
    aggregation_key="fx_all_sources_down",
)

FX_003 = AlertRuleDefinition(
    rule_id="FX-003",
    category=AlertCategory.FX,
    severity=AlertSeverity.P0,  # Critical
    source=AlertSource.FX_LAYER,
    title_template="🔴 FX Median Deviation Alert",
    message_template=(
        "🚨 CRITICAL: FX median rate deviation exceeds 5%\n"
        "Pair: {pair}\n"
        "Median rate: {median_rate:.2f}\n"
        "Expected range: {expected_min:.2f} - {expected_max:.2f}\n"
        "Deviation: {deviation_percent:.2f}%\n"
        "Outliers: {outliers}\n"
        "⚠️ Action Required: Investigate FX rate anomaly"
    ),
    aggregation_key="fx_median_deviation",
)

FX_004 = AlertRuleDefinition(
    rule_id="FX-004",
    category=AlertCategory.FX,
    severity=AlertSeverity.P2,
    source=AlertSource.FX_LAYER,
    title_template="FX Rate Staleness: {source}",
    message_template=(
        "⚠️ FX rate is stale for source '{source}'\n"
        "Pair: {pair}\n"
        "Age: {age_seconds}s (threshold: 60s)\n"
        "Last rate: {last_rate:.2f}\n"
        "Action: Using cached rate with warning"
    ),
    aggregation_key="fx_staleness",
)


# =============================================================================
# Executor Layer Alert Rules
# =============================================================================

EX_001 = AlertRuleDefinition(
    rule_id="EX-001",
    category=AlertCategory.EXECUTOR,
    severity=AlertSeverity.P2,
    source=AlertSource.EXECUTOR,
    title_template="Executor Order Error: {exchange}",
    message_template=(
        "⚠️ Order execution failed on {exchange}\n"
        "Symbol: {symbol}\n"
        "Side: {side}\n"
        "Error: {error_message}\n"
        "Action: {action}"
    ),
    aggregation_key="executor_order_error",
)

EX_002 = AlertRuleDefinition(
    rule_id="EX-002",
    category=AlertCategory.EXECUTOR,
    severity=AlertSeverity.P2,
    source=AlertSource.EXECUTOR,
    title_template="Executor Rollback: Partial Fill",
    message_template=(
        "⚠️ Order rollback due to partial fill\n"
        "Symbol: {symbol}\n"
        "Exchange: {exchange}\n"
        "Filled: {filled_qty} / {requested_qty}\n"
        "Status: {status}\n"
        "Action: Position rolled back to prevent exposure"
    ),
    aggregation_key="executor_rollback",
)


# =============================================================================
# RiskGuard Layer Alert Rules
# =============================================================================

RG_001 = AlertRuleDefinition(
    rule_id="RG-001",
    category=AlertCategory.RISK_GUARD,
    severity=AlertSeverity.P0,  # Critical
    source=AlertSource.RISK_GUARD,
    title_template="🔴 Circuit Breaker Triggered",
    message_template=(
        "🚨 CRITICAL: Circuit breaker triggered\n"
        "Reason: {reason}\n"
        "Threshold: {threshold}\n"
        "Current value: {current_value}\n"
        "Cooldown: {cooldown_seconds}s\n"
        "⚠️ Action Required: All trading BLOCKED until cooldown expires"
    ),
    aggregation_key="circuit_breaker",
)

RG_002 = AlertRuleDefinition(
    rule_id="RG-002",
    category=AlertCategory.RISK_GUARD,
    severity=AlertSeverity.P2,
    source=AlertSource.RISK_GUARD,
    title_template="Risk Limit Hit: {limit_type}",
    message_template=(
        "⚠️ Risk limit hit: {limit_type}\n"
        "Current: {current_value}\n"
        "Limit: {limit_value}\n"
        "Action: {action}"
    ),
    aggregation_key="risk_limit",
)


# =============================================================================
# WebSocket Layer Alert Rules
# =============================================================================

WS_001 = AlertRuleDefinition(
    rule_id="WS-001",
    category=AlertCategory.WEBSOCKET,
    severity=AlertSeverity.P2,
    source=AlertSource.WS_CLIENT,
    title_template="WebSocket Data Staleness: {source}",
    message_template=(
        "⚠️ WebSocket data is stale for {source}\n"
        "Stream: {stream}\n"
        "Age: {age_seconds}s (threshold: 60s)\n"
        "Last message: {last_message_time}\n"
        "Action: Connection health check in progress"
    ),
    aggregation_key="ws_staleness",
)

WS_002 = AlertRuleDefinition(
    rule_id="WS-002",
    category=AlertCategory.WEBSOCKET,
    severity=AlertSeverity.P2,
    source=AlertSource.WS_CLIENT,
    title_template="WebSocket Reconnect Failed: {source}",
    message_template=(
        "⚠️ WebSocket reconnect failed for {source}\n"
        "Stream: {stream}\n"
        "Attempts: {attempts} / {max_attempts}\n"
        "Last error: {error_message}\n"
        "Action: {action}"
    ),
    aggregation_key="ws_reconnect_failed",
)


# =============================================================================
# Alert Rules Registry
# =============================================================================

ALERT_RULES: Dict[str, AlertRuleDefinition] = {
    # FX Layer
    "FX-001": FX_001,
    "FX-002": FX_002,
    "FX-003": FX_003,
    "FX-004": FX_004,
    # Executor
    "EX-001": EX_001,
    "EX-002": EX_002,
    # RiskGuard
    "RG-001": RG_001,
    "RG-002": RG_002,
    # WebSocket
    "WS-001": WS_001,
    "WS-002": WS_002,
}


def get_alert_rule(rule_id: str) -> Optional[AlertRuleDefinition]:
    """
    Get alert rule by ID
    
    Args:
        rule_id: Rule ID (e.g., "FX-001")
    
    Returns:
        AlertRuleDefinition or None if not found
    """
    return ALERT_RULES.get(rule_id)


def format_alert(rule_id: str, **kwargs) -> Optional[tuple[AlertRuleDefinition, str, str]]:
    """
    Format alert message using rule template
    
    Args:
        rule_id: Rule ID
        **kwargs: Template parameters
    
    Returns:
        (rule, title, message) tuple or None if rule not found
    """
    rule = get_alert_rule(rule_id)
    if not rule:
        return None
    
    title, message = rule.format(**kwargs)
    return rule, title, message
