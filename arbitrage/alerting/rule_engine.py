"""
Alert Rule Engine: Rule-based alerting with environment-aware channel routing

Design Philosophy (Telegram-first Policy):
- PROD: Telegram + PostgreSQL only (Slack/Email OFF by default)
- DEV/TEST: All channels available for testing

Severity → Channel Mapping:
- P0 (Critical): Always Telegram + PostgreSQL
- P1 (High): Telegram + PostgreSQL, Slack optional (DEV only)
- P2 (Medium): Telegram (optional), PostgreSQL, Slack/Email for DEV
- P3 (Low): PostgreSQL only, Email for daily summary
"""

import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta

from .models import AlertSeverity, AlertSource, AlertRecord


class Environment(Enum):
    """Deployment environment"""
    PROD = "production"
    STAGING = "staging"
    DEV = "development"
    TEST = "test"


class AlertChannel(Enum):
    """Available alert channels"""
    TELEGRAM = "telegram"
    SLACK = "slack"
    EMAIL = "email"
    POSTGRES = "postgres"


@dataclass
class AlertRule:
    """
    Alert rule definition
    
    Attributes:
        rule_id: Unique rule identifier (e.g., "D75.RISK_GUARD.GLOBAL_BLOCK")
        source: Alert source
        severity: Alert severity level
        title: Rule title/name
        description: Rule description
        enabled: Whether rule is enabled
        channels: Target channels (environment-dependent)
        throttle_seconds: Minimum seconds between alerts (0 = no throttle)
    """
    rule_id: str
    source: AlertSource
    severity: AlertSeverity
    title: str
    description: str
    enabled: bool = True
    channels: Set[AlertChannel] = field(default_factory=set)
    throttle_seconds: int = 0
    
    def __hash__(self):
        return hash(self.rule_id)


@dataclass
class AlertDispatchPlan:
    """
    Alert dispatch decision
    
    Specifies which channels should receive the alert
    """
    telegram: bool = False
    slack: bool = False
    email: bool = False
    postgres: bool = False
    
    def any_channel_enabled(self) -> bool:
        """Check if any channel is enabled"""
        return self.telegram or self.slack or self.email or self.postgres


class RuleRegistry:
    """
    Central registry for alert rules
    
    Rules are defined here based on D76_ALERTING_INFRA_SKETCH.md
    """
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self._initialize_rules()
    
    def _initialize_rules(self):
        """Initialize all alert rules"""
        
        # =================================================================
        # 1. RATE LIMITER RULES (D75-3)
        # =================================================================
        self.register_rule(AlertRule(
            rule_id="D75.RATE_LIMITER.LOW_REMAINING",
            source=AlertSource.RATE_LIMITER,
            severity=AlertSeverity.P2,
            title="Rate Limit Warning",
            description="Rate limit remaining < 20%",
            throttle_seconds=60,  # Max 1/min
        ))
        
        self.register_rule(AlertRule(
            rule_id="D75.RATE_LIMITER.HTTP_429",
            source=AlertSource.RATE_LIMITER,
            severity=AlertSeverity.P1,
            title="Rate Limit Exceeded",
            description="HTTP 429 received from exchange",
            throttle_seconds=60,
        ))
        
        # =================================================================
        # 2. EXCHANGE HEALTH RULES (D75-3)
        # =================================================================
        self.register_rule(AlertRule(
            rule_id="D75.HEALTH.DEGRADED",
            source=AlertSource.HEALTH_MONITOR,
            severity=AlertSeverity.P2,
            title="Exchange Health Degraded",
            description="Exchange status changed to DEGRADED",
            throttle_seconds=120,
        ))
        
        self.register_rule(AlertRule(
            rule_id="D75.HEALTH.DOWN",
            source=AlertSource.HEALTH_MONITOR,
            severity=AlertSeverity.P1,
            title="Exchange Health DOWN",
            description="Exchange status changed to DOWN",
            throttle_seconds=300,  # 5 min
        ))
        
        self.register_rule(AlertRule(
            rule_id="D75.HEALTH.FROZEN",
            source=AlertSource.HEALTH_MONITOR,
            severity=AlertSeverity.P0,
            title="Exchange FROZEN",
            description="Exchange completely frozen, no response",
            throttle_seconds=300,
        ))
        
        # =================================================================
        # 3. ARB ROUTE / UNIVERSE RULES (D75-4)
        # =================================================================
        self.register_rule(AlertRule(
            rule_id="D75.ARB_ROUTE.LOW_SCORE",
            source=AlertSource.ARB_ROUTE,
            severity=AlertSeverity.P2,
            title="Route Score Low",
            description="Route score < 50 (no trading opportunity)",
            throttle_seconds=300,
        ))
        
        self.register_rule(AlertRule(
            rule_id="D75.ARB_UNIVERSE.ALL_SKIP",
            source=AlertSource.ARB_UNIVERSE,
            severity=AlertSeverity.P1,
            title="All Routes SKIP",
            description="No trading opportunities across all routes",
            throttle_seconds=300,
        ))
        
        # =================================================================
        # 4. CROSS-EXCHANGE SYNC RULES (D75-4)
        # =================================================================
        self.register_rule(AlertRule(
            rule_id="D75.CROSS_SYNC.HIGH_IMBALANCE",
            source=AlertSource.CROSS_SYNC,
            severity=AlertSeverity.P2,
            title="High Inventory Imbalance",
            description="Inventory imbalance > 50%",
            throttle_seconds=300,
        ))
        
        self.register_rule(AlertRule(
            rule_id="D75.CROSS_SYNC.HIGH_EXPOSURE",
            source=AlertSource.CROSS_SYNC,
            severity=AlertSeverity.P1,
            title="High Exposure Risk",
            description="Exposure > 80% of capital",
            throttle_seconds=300,
        ))
        
        self.register_rule(AlertRule(
            rule_id="D75.CROSS_SYNC.REBALANCE_FAILED",
            source=AlertSource.CROSS_SYNC,
            severity=AlertSeverity.P1,
            title="Rebalance Failed",
            description="Rebalance failed 3 consecutive times",
            throttle_seconds=600,
        ))
        
        # =================================================================
        # 5. RISK GUARD RULES (D75-5) - 4-Tier
        # =================================================================
        
        # Tier 1: ExchangeGuard
        self.register_rule(AlertRule(
            rule_id="D75.RISK_GUARD.EXCHANGE_BLOCK",
            source=AlertSource.RISK_GUARD,
            severity=AlertSeverity.P1,
            title="Exchange BLOCKED by RiskGuard",
            description="Exchange blocked due to daily loss or health",
            throttle_seconds=600,
        ))
        
        # Tier 2: RouteGuard
        self.register_rule(AlertRule(
            rule_id="D75.RISK_GUARD.ROUTE_COOLDOWN",
            source=AlertSource.RISK_GUARD,
            severity=AlertSeverity.P2,
            title="Route in COOLDOWN",
            description="Route cooldown due to consecutive losses",
            throttle_seconds=300,
        ))
        
        # Tier 3: SymbolGuard
        self.register_rule(AlertRule(
            rule_id="D75.RISK_GUARD.SYMBOL_DEGRADE",
            source=AlertSource.RISK_GUARD,
            severity=AlertSeverity.P2,
            title="Symbol DEGRADED",
            description="Symbol degraded due to exposure or volatility",
            throttle_seconds=300,
        ))
        
        # Tier 4: GlobalGuard (CRITICAL)
        self.register_rule(AlertRule(
            rule_id="D75.RISK_GUARD.GLOBAL_BLOCK",
            source=AlertSource.RISK_GUARD,
            severity=AlertSeverity.P0,
            title="GLOBAL BLOCK - Trading HALTED",
            description="Global daily loss limit exceeded",
            throttle_seconds=0,  # Never throttle P0
        ))
        
        # =================================================================
        # 6. SYSTEM RULES
        # =================================================================
        self.register_rule(AlertRule(
            rule_id="D75.SYSTEM.ENGINE_LATENCY",
            source=AlertSource.SYSTEM,
            severity=AlertSeverity.P1,
            title="Engine Latency Spike",
            description="Loop latency > 100ms sustained",
            throttle_seconds=300,
        ))
        
        self.register_rule(AlertRule(
            rule_id="D75.SYSTEM.STATE_SAVE_FAILED",
            source=AlertSource.SYSTEM,
            severity=AlertSeverity.P2,
            title="State Save Failed",
            description="Failed to save state snapshot",
            throttle_seconds=120,
        ))
        
        self.register_rule(AlertRule(
            rule_id="D75.SYSTEM.REDIS_CONNECTION_LOST",
            source=AlertSource.SYSTEM,
            severity=AlertSeverity.P0,
            title="Redis Connection Lost",
            description="Redis connection timeout or failure",
            throttle_seconds=0,  # Never throttle P0
        ))
        
        self.register_rule(AlertRule(
            rule_id="D75.SYSTEM.WS_RECONNECT_STORM",
            source=AlertSource.SYSTEM,
            severity=AlertSeverity.P1,
            title="WebSocket Reconnect Storm",
            description="Excessive WS reconnections detected",
            throttle_seconds=300,
        ))
    
    def register_rule(self, rule: AlertRule):
        """Register a rule"""
        self.rules[rule.rule_id] = rule
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get rule by ID"""
        return self.rules.get(rule_id)
    
    def get_rules_by_source(self, source: AlertSource) -> List[AlertRule]:
        """Get all rules for a source"""
        return [r for r in self.rules.values() if r.source == source]
    
    def get_rules_by_severity(self, severity: AlertSeverity) -> List[AlertRule]:
        """Get all rules for a severity"""
        return [r for r in self.rules.values() if r.severity == severity]


class RuleEngine:
    """
    Alert Rule Engine with environment-aware channel routing
    
    Telegram-first Policy:
    - PROD: Telegram + PostgreSQL (Slack/Email OFF)
    - DEV/TEST: All channels available
    """
    
    def __init__(
        self,
        environment: Optional[Environment] = None,
        registry: Optional[RuleRegistry] = None,
    ):
        """
        Initialize Rule Engine
        
        Args:
            environment: Deployment environment (auto-detect from env var if None)
            registry: Rule registry (creates default if None)
        """
        self.environment = environment or self._detect_environment()
        self.registry = registry or RuleRegistry()
        
        # Throttle tracking: rule_id -> last_alert_timestamp
        self._throttle_tracker: Dict[str, float] = {}
    
    def _detect_environment(self) -> Environment:
        """Detect environment from env var"""
        env_str = os.getenv("APP_ENV", "development").lower()
        
        if env_str in ["prod", "production"]:
            return Environment.PROD
        elif env_str in ["staging"]:
            return Environment.STAGING
        elif env_str in ["test", "testing"]:
            return Environment.TEST
        else:
            return Environment.DEV
    
    def evaluate_alert(
        self,
        alert: AlertRecord,
        rule_id: Optional[str] = None,
        skip_throttle: bool = False,
    ) -> AlertDispatchPlan:
        """
        Evaluate alert and determine which channels to use
        
        Args:
            alert: Alert record
            rule_id: Optional specific rule ID (auto-detect if None)
            skip_throttle: Skip throttle checking (for testing/simulation)
        
        Returns:
            AlertDispatchPlan specifying which channels to use
        """
        # Find matching rule
        rule = None
        if rule_id:
            rule = self.registry.get_rule(rule_id)
        
        # If no rule found, use default dispatch based on severity
        if not rule:
            return self._default_dispatch(alert)
        
        # Check if rule is enabled
        if not rule.enabled:
            return AlertDispatchPlan()  # All channels OFF
        
        # Check throttle (skip in simulation mode)
        if not skip_throttle and not self._check_throttle(rule):
            return AlertDispatchPlan()  # Throttled, no dispatch
        
        # Determine channels based on environment and severity
        return self._determine_channels(alert.severity)
    
    def _check_throttle(self, rule: AlertRule) -> bool:
        """Check if rule is throttled"""
        if rule.throttle_seconds == 0:
            return True  # No throttle
        
        now = datetime.now().timestamp()
        last_alert = self._throttle_tracker.get(rule.rule_id, 0)
        
        if now - last_alert >= rule.throttle_seconds:
            self._throttle_tracker[rule.rule_id] = now
            return True
        
        return False  # Throttled
    
    def _determine_channels(self, severity: AlertSeverity) -> AlertDispatchPlan:
        """
        Determine channels based on environment and severity
        
        Telegram-first Policy Implementation:
        
        PROD Environment:
        - P0: Telegram + PostgreSQL
        - P1: Telegram + PostgreSQL
        - P2: PostgreSQL (Telegram optional via config)
        - P3: PostgreSQL only
        
        DEV/TEST Environment:
        - P0: Telegram + Slack + PostgreSQL
        - P1: Telegram + Slack + PostgreSQL
        - P2: Telegram + Slack + Email + PostgreSQL
        - P3: Email + PostgreSQL
        """
        plan = AlertDispatchPlan()
        
        if self.environment == Environment.PROD:
            # PROD: Telegram-first, minimal noise
            if severity == AlertSeverity.P0:
                plan.telegram = True
                plan.postgres = True
            elif severity == AlertSeverity.P1:
                plan.telegram = True
                plan.postgres = True
            elif severity == AlertSeverity.P2:
                # P2 in PROD: PostgreSQL only by default
                # Telegram optional via env var
                plan.telegram = os.getenv("ALERT_P2_TELEGRAM", "false").lower() == "true"
                plan.postgres = True
            else:  # P3
                plan.postgres = True
        
        else:  # DEV, TEST, STAGING
            # DEV/TEST: All channels available for testing
            if severity == AlertSeverity.P0:
                plan.telegram = True
                plan.slack = True
                plan.postgres = True
            elif severity == AlertSeverity.P1:
                plan.telegram = True
                plan.slack = True
                plan.postgres = True
            elif severity == AlertSeverity.P2:
                plan.telegram = True
                plan.slack = True
                plan.email = True
                plan.postgres = True
            else:  # P3
                plan.email = True
                plan.postgres = True
        
        return plan
    
    def _default_dispatch(self, alert: AlertRecord) -> AlertDispatchPlan:
        """
        Default dispatch when no rule is found
        Uses severity-based routing
        """
        return self._determine_channels(alert.severity)
    
    def get_enabled_channels_for_severity(
        self,
        severity: AlertSeverity,
    ) -> List[AlertChannel]:
        """
        Get list of enabled channels for a severity level
        Useful for configuration/documentation
        """
        plan = self._determine_channels(severity)
        channels = []
        
        if plan.telegram:
            channels.append(AlertChannel.TELEGRAM)
        if plan.slack:
            channels.append(AlertChannel.SLACK)
        if plan.email:
            channels.append(AlertChannel.EMAIL)
        if plan.postgres:
            channels.append(AlertChannel.POSTGRES)
        
        return channels
    
    def get_environment_info(self) -> Dict[str, any]:
        """Get environment info and channel policy"""
        return {
            "environment": self.environment.value,
            "telegram_primary": self.environment == Environment.PROD,
            "channel_policy": {
                "P0": [ch.value for ch in self.get_enabled_channels_for_severity(AlertSeverity.P0)],
                "P1": [ch.value for ch in self.get_enabled_channels_for_severity(AlertSeverity.P1)],
                "P2": [ch.value for ch in self.get_enabled_channels_for_severity(AlertSeverity.P2)],
                "P3": [ch.value for ch in self.get_enabled_channels_for_severity(AlertSeverity.P3)],
            },
            "total_rules": len(self.registry.rules),
        }
