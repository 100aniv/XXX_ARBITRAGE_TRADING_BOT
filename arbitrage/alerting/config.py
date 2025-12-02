"""
D80-7: Alert Configuration

Configuration management for alerting system.
"""

import os
import logging
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TelegramConfig:
    """Telegram notification configuration"""
    enabled: bool = True
    bot_token: str = ""
    chat_id: str = ""
    timeout_seconds: int = 5
    retry_max_attempts: int = 3
    retry_backoff_multiplier: float = 2.0
    
    @classmethod
    def from_env(cls) -> "TelegramConfig":
        """Load from environment variables"""
        return cls(
            enabled=os.getenv("TELEGRAM_ENABLED", "true").lower() in ("true", "1", "yes"),
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            timeout_seconds=int(os.getenv("TELEGRAM_TIMEOUT_SECONDS", "5")),
            retry_max_attempts=int(os.getenv("TELEGRAM_RETRY_MAX_ATTEMPTS", "3")),
            retry_backoff_multiplier=float(os.getenv("TELEGRAM_RETRY_BACKOFF_MULTIPLIER", "2.0")),
        )
    
    def is_configured(self) -> bool:
        """Check if Telegram is properly configured"""
        return bool(self.bot_token and self.chat_id)


@dataclass
class SlackConfig:
    """Slack notification configuration"""
    enabled: bool = False
    webhook_url: str = ""
    timeout_seconds: int = 5
    retry_max_attempts: int = 3
    retry_backoff_multiplier: float = 2.0
    
    @classmethod
    def from_env(cls) -> "SlackConfig":
        """Load from environment variables"""
        return cls(
            enabled=os.getenv("SLACK_ENABLED", "false").lower() in ("true", "1", "yes"),
            webhook_url=os.getenv("SLACK_WEBHOOK_URL", ""),
            timeout_seconds=int(os.getenv("SLACK_TIMEOUT_SECONDS", "5")),
            retry_max_attempts=int(os.getenv("SLACK_RETRY_MAX_ATTEMPTS", "3")),
            retry_backoff_multiplier=float(os.getenv("SLACK_RETRY_BACKOFF_MULTIPLIER", "2.0")),
        )
    
    def is_configured(self) -> bool:
        """Check if Slack is properly configured"""
        return bool(self.webhook_url)


@dataclass
class ThrottlerConfig:
    """Throttler configuration"""
    enabled: bool = True
    window_seconds: int = 300  # 5 minutes
    use_redis: bool = True
    use_memory_fallback: bool = True
    
    @classmethod
    def from_env(cls) -> "ThrottlerConfig":
        """Load from environment variables"""
        return cls(
            enabled=os.getenv("ALERT_THROTTLE_ENABLED", "true").lower() in ("true", "1", "yes"),
            window_seconds=int(os.getenv("ALERT_THROTTLE_WINDOW_SECONDS", "300")),
            use_redis=os.getenv("ALERT_THROTTLE_USE_REDIS", "true").lower() in ("true", "1", "yes"),
            use_memory_fallback=os.getenv("ALERT_THROTTLE_MEMORY_FALLBACK", "true").lower() in ("true", "1", "yes"),
        )


@dataclass
class AggregatorConfig:
    """Aggregator configuration"""
    enabled: bool = True
    window_seconds: int = 30
    auto_flush: bool = True
    
    @classmethod
    def from_env(cls) -> "AggregatorConfig":
        """Load from environment variables"""
        return cls(
            enabled=os.getenv("ALERT_AGGREGATION_ENABLED", "true").lower() in ("true", "1", "yes"),
            window_seconds=int(os.getenv("ALERT_AGGREGATION_WINDOW_SECONDS", "30")),
            auto_flush=os.getenv("ALERT_AGGREGATION_AUTO_FLUSH", "true").lower() in ("true", "1", "yes"),
        )


@dataclass
class QueueConfig:
    """Queue configuration"""
    enabled: bool = True
    use_redis: bool = True
    queue_name: str = "alert_queue"
    max_size: int = 1000
    max_concurrency: int = 10
    
    @classmethod
    def from_env(cls) -> "QueueConfig":
        """Load from environment variables"""
        return cls(
            enabled=os.getenv("ALERT_QUEUE_ENABLED", "true").lower() in ("true", "1", "yes"),
            use_redis=os.getenv("ALERT_QUEUE_USE_REDIS", "true").lower() in ("true", "1", "yes"),
            queue_name=os.getenv("ALERT_QUEUE_NAME", "alert_queue"),
            max_size=int(os.getenv("ALERT_QUEUE_MAX_SIZE", "1000")),
            max_concurrency=int(os.getenv("ALERT_QUEUE_MAX_CONCURRENCY", "10")),
        )


@dataclass
class AlertConfig:
    """
    Main alert configuration
    
    Central configuration for D80-7 alerting system.
    """
    # General
    enabled: bool = True
    
    # Channel configurations
    telegram: TelegramConfig = field(default_factory=TelegramConfig.from_env)
    slack: SlackConfig = field(default_factory=SlackConfig.from_env)
    
    # Feature configurations
    throttler: ThrottlerConfig = field(default_factory=ThrottlerConfig.from_env)
    aggregator: AggregatorConfig = field(default_factory=AggregatorConfig.from_env)
    queue: QueueConfig = field(default_factory=QueueConfig.from_env)
    
    # Rule filtering
    enabled_rule_ids: Optional[Set[str]] = None  # None = all rules enabled
    disabled_rule_ids: Set[str] = field(default_factory=set)
    
    # Severity filtering
    min_severity_telegram: str = "P3"  # Send all alerts to Telegram
    min_severity_slack: str = "P2"  # Send P0/P1/P2 to Slack
    
    @classmethod
    def from_env(cls) -> "AlertConfig":
        """
        Load configuration from environment variables
        
        Returns:
            AlertConfig instance
        """
        config = cls(
            enabled=os.getenv("ALERT_ENABLED", "true").lower() in ("true", "1", "yes"),
            telegram=TelegramConfig.from_env(),
            slack=SlackConfig.from_env(),
            throttler=ThrottlerConfig.from_env(),
            aggregator=AggregatorConfig.from_env(),
            queue=QueueConfig.from_env(),
        )
        
        # Disabled rules (comma-separated)
        disabled_rules_str = os.getenv("ALERT_DISABLED_RULES", "")
        if disabled_rules_str:
            config.disabled_rule_ids = set(r.strip() for r in disabled_rules_str.split(",") if r.strip())
        
        # Severity filtering
        config.min_severity_telegram = os.getenv("ALERT_MIN_SEVERITY_TELEGRAM", "P3")
        config.min_severity_slack = os.getenv("ALERT_MIN_SEVERITY_SLACK", "P2")
        
        return config
    
    def is_rule_enabled(self, rule_id: str) -> bool:
        """
        Check if a rule is enabled
        
        Args:
            rule_id: Rule ID (e.g., "FX-001")
        
        Returns:
            True if rule is enabled
        """
        # Check disabled list
        if rule_id in self.disabled_rule_ids:
            return False
        
        # Check enabled list (if specified)
        if self.enabled_rule_ids is not None:
            return rule_id in self.enabled_rule_ids
        
        # Default: enabled
        return True
    
    def should_send_to_telegram(self, severity: str) -> bool:
        """
        Check if alert should be sent to Telegram
        
        Args:
            severity: Alert severity (P0/P1/P2/P3)
        
        Returns:
            True if should send
        """
        if not self.telegram.enabled or not self.telegram.is_configured():
            return False
        
        # Severity hierarchy: P0 > P1 > P2 > P3
        severity_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        
        alert_level = severity_order.get(severity, 3)
        min_level = severity_order.get(self.min_severity_telegram, 3)
        
        return alert_level <= min_level
    
    def should_send_to_slack(self, severity: str) -> bool:
        """
        Check if alert should be sent to Slack
        
        Args:
            severity: Alert severity (P0/P1/P2/P3)
        
        Returns:
            True if should send
        """
        if not self.slack.enabled or not self.slack.is_configured():
            return False
        
        # Severity hierarchy
        severity_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        
        alert_level = severity_order.get(severity, 3)
        min_level = severity_order.get(self.min_severity_slack, 3)
        
        return alert_level <= min_level
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "enabled": self.enabled,
            "telegram": {
                "enabled": self.telegram.enabled,
                "configured": self.telegram.is_configured(),
                "timeout_seconds": self.telegram.timeout_seconds,
            },
            "slack": {
                "enabled": self.slack.enabled,
                "configured": self.slack.is_configured(),
                "timeout_seconds": self.slack.timeout_seconds,
            },
            "throttler": {
                "enabled": self.throttler.enabled,
                "window_seconds": self.throttler.window_seconds,
                "use_redis": self.throttler.use_redis,
            },
            "aggregator": {
                "enabled": self.aggregator.enabled,
                "window_seconds": self.aggregator.window_seconds,
            },
            "queue": {
                "enabled": self.queue.enabled,
                "use_redis": self.queue.use_redis,
                "queue_name": self.queue.queue_name,
            },
            "disabled_rule_ids": list(self.disabled_rule_ids),
            "min_severity_telegram": self.min_severity_telegram,
            "min_severity_slack": self.min_severity_slack,
        }


# Global config instance (lazy loaded)
_config: Optional[AlertConfig] = None


def get_alert_config() -> AlertConfig:
    """
    Get global alert configuration
    
    Returns:
        AlertConfig instance
    """
    global _config
    if _config is None:
        _config = AlertConfig.from_env()
        logger.info("[AlertConfig] Configuration loaded from environment")
    return _config


def reload_alert_config() -> AlertConfig:
    """
    Reload alert configuration from environment
    
    Returns:
        New AlertConfig instance
    """
    global _config
    _config = AlertConfig.from_env()
    logger.info("[AlertConfig] Configuration reloaded")
    return _config
