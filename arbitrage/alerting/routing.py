"""
D80-13: Alert Routing Rules

Implements rule-based alert routing with:
- Priority-based routing (P1/P2/P3)
- Multi-destination support (telegram, slack, email, local_log)
- Aggregation (5-minute grouping)
- Escalation (repeated failures → escalate channel)
- YAML-based configuration
- Backward compatible with existing dispatcher
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import yaml

from .models import AlertRecord, AlertSeverity

logger = logging.getLogger(__name__)


class AlertPriority(Enum):
    """Alert priority levels"""
    P1 = "P1"  # Critical - immediate notification
    P2 = "P2"  # Warning - batched notification
    P3 = "P3"  # Info - heavily batched/suppressed


class DestinationType(Enum):
    """Alert destination types"""
    TELEGRAM = "telegram"
    SLACK = "slack"
    EMAIL = "email"
    LOCAL_LOG = "local_log"


@dataclass
class RoutingRule:
    """
    Alert routing rule
    
    Defines how alerts matching a rule_id should be routed:
    - priority: P1/P2/P3
    - destinations: list of channels (telegram, slack, email, local_log)
    - escalate_after_failures: number of consecutive failures before escalation
    - escalation_target: destination to escalate to
    - aggregation_window_seconds: time window for aggregation (default: 300s = 5min)
    """
    rule_id: str
    priority: AlertPriority
    destinations: List[DestinationType]
    escalate_after_failures: Optional[int] = None
    escalation_target: Optional[DestinationType] = None
    aggregation_window_seconds: int = 300  # 5 minutes default
    
    def __post_init__(self):
        """Validate routing rule"""
        if not self.destinations:
            raise ValueError(f"Rule {self.rule_id}: destinations cannot be empty")
        
        if self.escalate_after_failures is not None:
            if self.escalate_after_failures < 1:
                raise ValueError(f"Rule {self.rule_id}: escalate_after_failures must be >= 1")
            if self.escalation_target is None:
                raise ValueError(f"Rule {self.rule_id}: escalation_target required when escalate_after_failures is set")


@dataclass
class AggregatedAlertBatch:
    """
    Batch of aggregated alerts
    
    Groups alerts by rule_id within a time window.
    """
    rule_id: str
    priority: AlertPriority
    alerts: List[AlertRecord] = field(default_factory=list)
    first_timestamp: float = field(default_factory=time.time)
    last_timestamp: float = field(default_factory=time.time)
    
    def add_alert(self, alert: AlertRecord):
        """Add alert to batch"""
        self.alerts.append(alert)
        self.last_timestamp = time.time()
    
    def should_flush(self, window_seconds: int) -> bool:
        """Check if batch should be flushed"""
        elapsed = time.time() - self.first_timestamp
        return elapsed >= window_seconds or len(self.alerts) >= 100  # Max 100 alerts per batch


class RoutingTable:
    """
    Alert routing table
    
    Loads routing rules from YAML configuration file.
    Provides rule lookup and destination resolution.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize routing table
        
        Args:
            config_path: Path to YAML config file (default: configs/alert_routing.yml)
        """
        self._rules: Dict[str, RoutingRule] = {}
        self._default_rule: Optional[RoutingRule] = None
        self._lock = threading.RLock()
        
        if config_path is None:
            config_path = Path("configs/alert_routing.yml")
        
        self._config_path = config_path
        
        # Load rules if config exists
        if config_path.exists():
            self.load_from_yaml(config_path)
        else:
            logger.warning(f"Routing config not found: {config_path}, using defaults")
            self._init_default_rules()
    
    def _init_default_rules(self):
        """Initialize default routing rules"""
        # Default rule: P3, local_log
        self._default_rule = RoutingRule(
            rule_id="DEFAULT",
            priority=AlertPriority.P3,
            destinations=[DestinationType.LOCAL_LOG],
        )
        logger.info("Initialized default routing rules")
    
    def load_from_yaml(self, config_path: Path):
        """
        Load routing rules from YAML file
        
        YAML format:
          FX-001:
            priority: P1
            destinations: [telegram]
          FX-003:
            priority: P2
            destinations: [telegram, slack]
            aggregation_window_seconds: 300
          EX-001:
            priority: P1
            destinations: [telegram]
            escalate_after_failures: 3
            escalation_target: email
          DEFAULT:
            priority: P3
            destinations: [local_log]
        """
        with self._lock:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                
                if not config:
                    logger.warning(f"Empty routing config: {config_path}")
                    self._init_default_rules()
                    return
                
                # Parse rules
                for rule_id, rule_config in config.items():
                    try:
                        # Parse priority
                        priority_str = rule_config.get('priority', 'P3')
                        priority = AlertPriority[priority_str]
                        
                        # Parse destinations
                        dest_list = rule_config.get('destinations', [])
                        destinations = [DestinationType(d) for d in dest_list]
                        
                        # Parse optional fields
                        escalate_after = rule_config.get('escalate_after_failures')
                        escalation_target = rule_config.get('escalation_target')
                        if escalation_target:
                            escalation_target = DestinationType(escalation_target)
                        
                        aggregation_window = rule_config.get('aggregation_window_seconds', 300)
                        
                        # Create rule
                        rule = RoutingRule(
                            rule_id=rule_id,
                            priority=priority,
                            destinations=destinations,
                            escalate_after_failures=escalate_after,
                            escalation_target=escalation_target,
                            aggregation_window_seconds=aggregation_window,
                        )
                        
                        # Store rule
                        if rule_id == "DEFAULT":
                            self._default_rule = rule
                        else:
                            self._rules[rule_id] = rule
                    
                    except (KeyError, ValueError) as e:
                        logger.error(f"Failed to parse rule {rule_id}: {e}")
                        continue
                
                logger.info(f"Loaded {len(self._rules)} routing rules from {config_path}")
                
                # Ensure default rule exists
                if self._default_rule is None:
                    self._init_default_rules()
            
            except Exception as e:
                logger.error(f"Failed to load routing config: {e}")
                self._init_default_rules()
    
    def get_rule(self, rule_id: str) -> RoutingRule:
        """
        Get routing rule by rule_id
        
        Returns default rule if rule_id not found.
        """
        with self._lock:
            return self._rules.get(rule_id, self._default_rule)
    
    def get_destinations(self, rule_id: str) -> List[DestinationType]:
        """Get destinations for rule_id"""
        rule = self.get_rule(rule_id)
        return rule.destinations if rule else [DestinationType.LOCAL_LOG]
    
    def get_priority(self, rule_id: str) -> AlertPriority:
        """Get priority for rule_id"""
        rule = self.get_rule(rule_id)
        return rule.priority if rule else AlertPriority.P3
    
    def should_escalate(self, rule_id: str, failure_count: int) -> bool:
        """Check if alert should be escalated"""
        rule = self.get_rule(rule_id)
        if rule and rule.escalate_after_failures is not None:
            return failure_count >= rule.escalate_after_failures
        return False
    
    def get_escalation_target(self, rule_id: str) -> Optional[DestinationType]:
        """Get escalation target for rule_id"""
        rule = self.get_rule(rule_id)
        return rule.escalation_target if rule else None
    
    def get_aggregation_window(self, rule_id: str) -> int:
        """Get aggregation window for rule_id"""
        rule = self.get_rule(rule_id)
        return rule.aggregation_window_seconds if rule else 300


class AlertRouter:
    """
    Alert router with aggregation and escalation
    
    Routes alerts based on rules, aggregates alerts within time windows,
    and escalates repeated failures.
    """
    
    def __init__(self, routing_table: Optional[RoutingTable] = None):
        """
        Initialize alert router
        
        Args:
            routing_table: RoutingTable instance (default: auto-load from config)
        """
        self.routing_table = routing_table or RoutingTable()
        
        # Aggregation buffers (rule_id → batch)
        self._aggregation_buffers: Dict[str, AggregatedAlertBatch] = {}
        
        # Escalation tracking (rule_id → failure_count)
        self._escalation_tracker: Dict[str, int] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            "routed": 0,
            "aggregated": 0,
            "escalated": 0,
            "flushed_batches": 0,
        }
    
    def route_alert(
        self,
        alert: AlertRecord,
        rule_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Route alert based on rules
        
        Returns routing decision with:
        - destinations: list of destinations
        - priority: P1/P2/P3
        - should_aggregate: whether to aggregate
        - escalated: whether alert was escalated
        - escalation_target: escalation destination (if escalated)
        
        Args:
            alert: Alert to route
            rule_id: Alert rule ID (optional, uses DEFAULT if not provided)
        
        Returns:
            Routing decision dict
        """
        with self._lock:
            self._stats["routed"] += 1
            
            # Default rule if not provided
            if rule_id is None:
                rule_id = "DEFAULT"
            
            # Get rule
            rule = self.routing_table.get_rule(rule_id)
            
            # Base routing decision
            decision = {
                "rule_id": rule_id,
                "destinations": rule.destinations,
                "priority": rule.priority,
                "should_aggregate": False,
                "escalated": False,
                "escalation_target": None,
            }
            
            # Check for aggregation (P2/P3 only)
            if rule.priority in [AlertPriority.P2, AlertPriority.P3]:
                decision["should_aggregate"] = True
            
            # Check for escalation
            failure_count = self._escalation_tracker.get(rule_id, 0)
            if self.routing_table.should_escalate(rule_id, failure_count):
                escalation_target = self.routing_table.get_escalation_target(rule_id)
                if escalation_target:
                    decision["escalated"] = True
                    decision["escalation_target"] = escalation_target
                    decision["destinations"] = [escalation_target]
                    self._stats["escalated"] += 1
                    logger.warning(f"Alert {rule_id} escalated to {escalation_target.value} after {failure_count} failures")
            
            return decision
    
    def aggregate_alert(
        self,
        alert: AlertRecord,
        rule_id: str,
    ) -> Optional[AggregatedAlertBatch]:
        """
        Add alert to aggregation buffer
        
        Returns flushed batch if window expired, else None.
        
        Args:
            alert: Alert to aggregate
            rule_id: Rule ID
        
        Returns:
            Flushed batch if ready, else None
        """
        with self._lock:
            self._stats["aggregated"] += 1
            
            # Get or create batch
            if rule_id not in self._aggregation_buffers:
                priority = self.routing_table.get_priority(rule_id)
                self._aggregation_buffers[rule_id] = AggregatedAlertBatch(
                    rule_id=rule_id,
                    priority=priority,
                )
            
            batch = self._aggregation_buffers[rule_id]
            batch.add_alert(alert)
            
            # Check if should flush
            window = self.routing_table.get_aggregation_window(rule_id)
            if batch.should_flush(window):
                # Flush batch
                flushed_batch = self._aggregation_buffers.pop(rule_id)
                self._stats["flushed_batches"] += 1
                logger.info(f"Flushed aggregated batch for {rule_id}: {len(flushed_batch.alerts)} alerts")
                return flushed_batch
            
            return None
    
    def record_failure(self, rule_id: str):
        """Record alert delivery failure for escalation tracking"""
        with self._lock:
            self._escalation_tracker[rule_id] = self._escalation_tracker.get(rule_id, 0) + 1
            logger.debug(f"Recorded failure for {rule_id}: {self._escalation_tracker[rule_id]} failures")
    
    def reset_escalation(self, rule_id: str):
        """Reset escalation tracking after successful delivery"""
        with self._lock:
            if rule_id in self._escalation_tracker:
                del self._escalation_tracker[rule_id]
                logger.debug(f"Reset escalation tracking for {rule_id}")
    
    def flush_all_batches(self) -> List[AggregatedAlertBatch]:
        """Flush all aggregation buffers (for shutdown or testing)"""
        with self._lock:
            batches = list(self._aggregation_buffers.values())
            self._aggregation_buffers.clear()
            self._stats["flushed_batches"] += len(batches)
            return batches
    
    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics"""
        with self._lock:
            return {
                **self._stats,
                "aggregation_buffers": len(self._aggregation_buffers),
                "escalation_trackers": len(self._escalation_tracker),
            }


# Global router instance
_global_router: Optional[AlertRouter] = None
_router_lock = threading.RLock()


def get_global_alert_router() -> AlertRouter:
    """Get global alert router instance"""
    global _global_router
    with _router_lock:
        if _global_router is None:
            _global_router = AlertRouter()
        return _global_router


def reset_global_alert_router():
    """Reset global router (for testing)"""
    global _global_router
    with _router_lock:
        _global_router = None
