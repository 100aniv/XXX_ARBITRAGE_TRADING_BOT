"""
D80-11: Alert Dispatcher + D80-13: Alert Routing

Handles async alert delivery with queue, retry, DLQ, failover, and routing.
Decouples alert emission from delivery to prevent blocking business logic.
"""

import time
import logging
import threading
from typing import Optional, Dict, Any, List
from dataclasses import asdict

from .models import AlertRecord
from .queue_backend import PersistentAlertQueue
from .failsafe_notifier import FailSafeNotifier, NotifierFallbackChain, LocalLogNotifier, NotifierStatus
from .metrics_exporter import get_global_alert_metrics
from .rule_engine import RuleEngine, AlertDispatchPlan
from .routing import AlertRouter, get_global_alert_router

logger = logging.getLogger(__name__)


class AlertDispatcher:
    """
    Alert dispatcher with async delivery, retry, and failover
    
    Architecture:
    1. AlertManager calls enqueue() → PersistentAlertQueue (instant return, no blocking)
    2. Worker thread dequeues → FailSafeNotifier (timeout protected)
    3. Failure → Retry queue or DLQ
    4. Metrics exported to Prometheus
    
    Features:
    - Non-blocking enqueue (< 1ms)
    - Persistent queue (Redis-based)
    - Fail-safe notifier wrappers (timeout, circuit breaker)
    - Automatic retry (3 attempts default)
    - Dead Letter Queue (DLQ)
    - Failover chain (Telegram → Slack → Local log)
    - Prometheus metrics
    
    Usage:
        dispatcher = AlertDispatcher(redis_client=redis_client)
        dispatcher.register_notifier("telegram", telegram_notifier)
        dispatcher.register_notifier("slack", slack_notifier)
        dispatcher.start_worker()
        
        # Enqueue alert (non-blocking)
        dispatcher.enqueue(alert, rule_id="FX-001")
    """
    
    def __init__(
        self,
        redis_client: Optional[Any] = None,
        queue_name: str = "alert_queue_v2",
        max_retries: int = 3,
        worker_poll_interval_seconds: float = 0.1,
        notifier_timeout_seconds: float = 3.0,
        rule_engine: Optional[RuleEngine] = None,
        enable_routing: bool = False,
        router: Optional[AlertRouter] = None,
    ):
        """
        Initialize alert dispatcher
        
        Args:
            redis_client: Redis client (None for in-memory mode)
            queue_name: Queue name prefix
            max_retries: Maximum retry attempts
            worker_poll_interval_seconds: Worker polling interval
            notifier_timeout_seconds: Notifier send timeout
            rule_engine: Rule engine for channel routing
            enable_routing: Enable D80-13 routing layer (default: False for backward compatibility)
            router: AlertRouter instance (default: global router)
        """
        # Queue backend
        self.queue = PersistentAlertQueue(
            redis_client=redis_client,
            queue_name=queue_name,
            max_retries=max_retries,
        )
        
        # Rule engine
        self.rule_engine = rule_engine or RuleEngine()
        
        # D80-13: Routing layer (optional, backward compatible)
        self._enable_routing = enable_routing
        self._router = router or (get_global_alert_router() if enable_routing else None)
        
        # Notifiers (wrapped in FailSafeNotifier)
        self._notifiers: Dict[str, FailSafeNotifier] = {}
        self._fallback_chains: Dict[str, NotifierFallbackChain] = {}
        
        # Worker control
        self._worker_running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._worker_poll_interval = worker_poll_interval_seconds
        
        # Notifier config
        self._notifier_timeout = notifier_timeout_seconds
        
        # Metrics
        self._metrics = get_global_alert_metrics()
        
        # Statistics
        self._stats = {
            "enqueued": 0,
            "dispatched": 0,
            "success": 0,
            "failure": 0,
            "retry": 0,
            "dlq": 0,
        }
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Always have local log fallback
        self._local_log_notifier = LocalLogNotifier()
        
        # D80-12: Fault injection hooks (test-only, hidden)
        self._fault_handlers: Dict[str, Any] = {}
    
    def register_notifier(
        self,
        channel_name: str,
        notifier: Any,
        circuit_breaker_threshold: int = 5,
    ):
        """
        Register notifier with fail-safe wrapper
        
        Args:
            channel_name: Channel name ("telegram", "slack", etc.)
            notifier: Underlying notifier (must have .send(alert) method)
            circuit_breaker_threshold: Failures before circuit breaker opens
        """
        with self._lock:
            # Wrap in fail-safe notifier
            safe_notifier = FailSafeNotifier(
                notifier=notifier,
                name=channel_name,
                timeout_seconds=self._notifier_timeout,
                circuit_breaker_threshold=circuit_breaker_threshold,
            )
            
            self._notifiers[channel_name] = safe_notifier
            logger.info(f"Registered notifier: {channel_name}")
    
    def configure_fallback_chain(
        self,
        primary: str,
        fallbacks: Optional[List[str]] = None,
    ):
        """
        Configure fallback chain for a primary notifier
        
        Args:
            primary: Primary notifier name
            fallbacks: List of fallback notifier names (default: ["local_log"])
        
        Example:
            dispatcher.configure_fallback_chain("telegram", ["slack", "local_log"])
        """
        with self._lock:
            if primary not in self._notifiers:
                logger.warning(f"Primary notifier not registered: {primary}")
                return
            
            fallback_notifiers = [self._notifiers[primary]]
            
            if fallbacks:
                for fb_name in fallbacks:
                    if fb_name == "local_log":
                        fallback_notifiers.append(self._local_log_notifier)
                    elif fb_name in self._notifiers:
                        fallback_notifiers.append(self._notifiers[fb_name])
                    else:
                        logger.warning(f"Fallback notifier not registered: {fb_name}")
            else:
                # Default: add local log
                fallback_notifiers.append(self._local_log_notifier)
            
            self._fallback_chains[primary] = NotifierFallbackChain(fallback_notifiers)
            logger.info(f"Configured fallback chain: {primary} → {fallbacks or ['local_log']}")
    
    def enqueue(
        self,
        alert: AlertRecord,
        rule_id: Optional[str] = None,
    ) -> bool:
        """
        Enqueue alert for async delivery (non-blocking)
        
        D80-13: If routing is enabled, applies routing rules before enqueue.
        
        Args:
            alert: Alert to send
            rule_id: Optional rule ID for routing
        
        Returns:
            True if enqueued successfully (NOT delivery success)
        """
        with self._lock:
            self._stats["enqueued"] += 1
            
            # D80-13: Apply routing if enabled
            routing_decision = None
            if self._enable_routing and self._router:
                routing_decision = self._router.route_alert(alert, rule_id)
                
                # Check if should aggregate
                if routing_decision.get("should_aggregate", False):
                    # Add to aggregation buffer
                    flushed_batch = self._router.aggregate_alert(alert, rule_id or "DEFAULT")
                    
                    # If batch flushed, enqueue the batch (not individual alert)
                    if flushed_batch:
                        logger.debug(f"Aggregated batch flushed for {rule_id}: {len(flushed_batch.alerts)} alerts")
                        # For now, still enqueue individual alerts
                        # In production, you might want to send a summary alert
                    else:
                        # Alert added to buffer, don't enqueue yet
                        logger.debug(f"Alert added to aggregation buffer for {rule_id}")
                        return True  # Non-blocking success
            
            # Enqueue with metadata
            metadata = {
                "rule_id": rule_id,
                "enqueued_at": time.time(),
                "retry_count": 0,
            }
            
            # D80-13: Add routing decision to metadata
            if routing_decision:
                metadata["routing"] = routing_decision
            
            success = self.queue.enqueue(alert, metadata)
            
            if not success:
                logger.error("Failed to enqueue alert")
            
            return success
    
    def start_worker(self):
        """Start worker thread for alert delivery"""
        with self._lock:
            if self._worker_running:
                logger.warning("Worker already running")
                return
            
            self._worker_running = True
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="AlertDispatcherWorker",
            )
            self._worker_thread.start()
            logger.info("Alert dispatcher worker started")
    
    def stop_worker(self):
        """Stop worker thread"""
        with self._lock:
            if not self._worker_running:
                return
            
            self._worker_running = False
            
            if self._worker_thread:
                self._worker_thread.join(timeout=5.0)
            
            logger.info("Alert dispatcher worker stopped")
    
    def _worker_loop(self):
        """Worker thread main loop"""
        logger.info("Alert dispatcher worker loop started")
        
        while self._worker_running:
            try:
                # Process retry queue first
                self.queue.process_retry_queue()
                
                # Dequeue alert
                payload = self.queue.dequeue(timeout_seconds=int(self._worker_poll_interval))
                
                if payload:
                    self._dispatch_alert(payload)
                
            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)
                time.sleep(1.0)  # Backoff on error
        
        logger.info("Alert dispatcher worker loop stopped")
    
    def _dispatch_alert(self, payload: Dict[str, Any]):
        """
        Dispatch alert to notifiers
        
        Args:
            payload: Alert payload with metadata
        """
        try:
            self._stats["dispatched"] += 1
            
            # Extract alert and metadata
            alert_data = payload["alert"]
            metadata = payload.get("metadata", {})
            rule_id = metadata.get("rule_id")
            
            # Deserialize alert
            alert = self.queue._deserialize_alert(alert_data)
            
            # Get dispatch plan from rule engine
            dispatch_plan = self.rule_engine.evaluate_alert(alert, rule_id)
            
            # Dispatch to channels
            success = False
            start_time = time.time()
            
            for channel in self._get_dispatch_channels(dispatch_plan):
                if channel in self._fallback_chains:
                    # Use fallback chain
                    result = self._fallback_chains[channel].send(alert)
                elif channel in self._notifiers:
                    # Use single notifier
                    result = self._notifiers[channel].send(alert)
                else:
                    logger.warning(f"Notifier not registered: {channel}")
                    result = False
                
                if result:
                    success = True
                    
                    # Record metrics
                    latency = time.time() - start_time
                    self._metrics.record_sent(rule_id or "unknown", channel)
                    self._metrics.record_delivery_latency(channel, latency)
            
            # Handle result
            if success:
                self._on_dispatch_success(payload)
            else:
                self._on_dispatch_failure(payload)
        
        except Exception as e:
            logger.error(f"Dispatch error: {e}", exc_info=True)
            self._on_dispatch_failure(payload)
    
    def _get_dispatch_channels(self, dispatch_plan: AlertDispatchPlan) -> List[str]:
        """Get list of channels to dispatch to"""
        channels = []
        if dispatch_plan.telegram:
            channels.append("telegram")
        if dispatch_plan.slack:
            channels.append("slack")
        if dispatch_plan.email:
            channels.append("email")
        return channels
    
    def _on_dispatch_success(self, payload: Dict[str, Any]):
        """Handle successful dispatch"""
        self._stats["success"] += 1
        self.queue.ack(payload)
    
    def _on_dispatch_failure(self, payload: Dict[str, Any]):
        """Handle failed dispatch"""
        self._stats["failure"] += 1
        
        metadata = payload.get("metadata", {})
        rule_id = metadata.get("rule_id", "unknown")
        retry_count = metadata.get("retry_count", 0)
        
        # Nack with retry
        self.queue.nack(payload, retry=True)
        
        # Record metrics
        if retry_count < self.queue.max_retries:
            self._stats["retry"] += 1
            self._metrics.record_retry(rule_id)
        else:
            self._stats["dlq"] += 1
            self._metrics.record_dlq(rule_id, "max_retries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dispatcher statistics"""
        with self._lock:
            stats = dict(self._stats)
            stats["worker_running"] = self._worker_running
            stats["queue"] = self.queue.get_stats()
            stats["notifiers"] = {
                name: notifier.get_stats()
                for name, notifier in self._notifiers.items()
            }
            return stats
    
    def update_notifier_metrics(self):
        """Update notifier availability metrics"""
        with self._lock:
            for name, notifier in self._notifiers.items():
                status = notifier.get_status()
                
                if status == NotifierStatus.AVAILABLE:
                    value = 1.0
                elif status == NotifierStatus.DEGRADED:
                    value = 0.5
                else:
                    value = 0.0
                
                self._metrics.set_notifier_status(name, status.value, value)
    
    # D80-12: Fault injection methods (test-only, hidden from public API)
    def _inject_fault(self, fault_type: str, handler: Any = None):
        """
        Inject fault for chaos testing
        
        INTERNAL USE ONLY - DO NOT USE IN PRODUCTION
        
        Args:
            fault_type: Type of fault ("redis_down", "network_latency", etc.)
            handler: Optional fault handler callable
        """
        with self._lock:
            self._fault_handlers[fault_type] = handler
            logger.warning(f"[CHAOS] Fault injected: {fault_type}")
    
    def _clear_fault(self, fault_type: str):
        """Clear injected fault"""
        with self._lock:
            if fault_type in self._fault_handlers:
                del self._fault_handlers[fault_type]
                logger.info(f"[CHAOS] Fault cleared: {fault_type}")
    
    def _trigger_fault(self, fault_type: str) -> bool:
        """
        Trigger fault if injected
        
        Returns:
            True if fault was triggered (skip normal operation)
        """
        with self._lock:
            handler = self._fault_handlers.get(fault_type)
            if handler:
                if callable(handler):
                    handler()
                return True
            return False


# Global dispatcher instance
_global_dispatcher: Optional[AlertDispatcher] = None
_dispatcher_lock = threading.RLock()


def get_global_alert_dispatcher() -> AlertDispatcher:
    """Get global alert dispatcher instance"""
    global _global_dispatcher
    with _dispatcher_lock:
        if _global_dispatcher is None:
            _global_dispatcher = AlertDispatcher()
        return _global_dispatcher


def reset_global_alert_dispatcher():
    """Reset global dispatcher (for testing)"""
    global _global_dispatcher
    with _dispatcher_lock:
        if _global_dispatcher:
            _global_dispatcher.stop_worker()
        _global_dispatcher = None
