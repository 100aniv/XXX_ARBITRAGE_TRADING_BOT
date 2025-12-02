"""
D80-11: Alert System Hardening & Fail-Safe Architecture Tests

Tests for:
- PersistentAlertQueue (Redis-based, retry, DLQ)
- FailSafeNotifier (timeout, circuit breaker, fallback)
- AlertDispatcher (async delivery, worker thread)
- AlertMetrics (Prometheus integration)
"""

import pytest
import time
import threading
from unittest.mock import Mock, MagicMock, patch

from arbitrage.alerting import (
    AlertRecord,
    AlertSeverity,
    AlertSource,
    # D80-11
    PersistentAlertQueue,
    FailSafeNotifier,
    NotifierFallbackChain,
    LocalLogNotifier,
    NotifierStatus,
    AlertDispatcher,
    AlertMetrics,
    get_global_alert_dispatcher,
    reset_global_alert_dispatcher,
    get_global_alert_metrics,
    reset_global_alert_metrics,
)


# =============================================================================
# PersistentAlertQueue Tests
# =============================================================================

class TestPersistentAlertQueue:
    """Test persistent alert queue with retry and DLQ"""
    
    def setup_method(self):
        """Setup test queue (in-memory mode)"""
        self.queue = PersistentAlertQueue(
            redis_client=None,  # In-memory mode
            queue_name="test_queue",
            max_retries=3,
        )
    
    def test_enqueue_dequeue(self):
        """Test basic enqueue and dequeue"""
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Test Alert",
            message="Test message",
        )
        
        # Enqueue
        success = self.queue.enqueue(alert)
        assert success is True
        
        # Dequeue
        payload = self.queue.dequeue(timeout_seconds=0)
        assert payload is not None
        assert payload["alert"]["title"] == "Test Alert"
    
    def test_ack_removes_from_processing(self):
        """Test ack removes alert from processing queue"""
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Test Alert",
            message="Test message",
        )
        
        self.queue.enqueue(alert)
        payload = self.queue.dequeue(timeout_seconds=0)
        
        # Check in processing
        stats = self.queue.get_stats()
        assert stats["processing"] == 1
        
        # Ack
        self.queue.ack(payload)
        
        # Check removed from processing
        stats = self.queue.get_stats()
        assert stats["processing"] == 0
        assert stats["acked"] == 1
    
    def test_nack_moves_to_retry(self):
        """Test nack moves alert to retry queue"""
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Test Alert",
            message="Test message",
        )
        
        self.queue.enqueue(alert)
        payload = self.queue.dequeue(timeout_seconds=0)
        
        # Nack with retry
        self.queue.nack(payload, retry=True)
        
        # Check moved to retry
        stats = self.queue.get_stats()
        assert stats["retry"] == 1
        assert stats["retried"] == 1
    
    def test_nack_max_retries_moves_to_dlq(self):
        """Test nack after max retries moves to DLQ"""
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Test Alert",
            message="Test message",
        )
        
        # Simulate 3 retries
        for i in range(4):  # 0, 1, 2, 3 (4th goes to DLQ)
            self.queue.enqueue(alert, metadata={"retry_count": i})
            payload = self.queue.dequeue(timeout_seconds=0)
            self.queue.nack(payload, retry=True)
        
        # Check moved to DLQ
        stats = self.queue.get_stats()
        assert stats["dlq"] >= 1


# =============================================================================
# FailSafeNotifier Tests
# =============================================================================

class TestFailSafeNotifier:
    """Test fail-safe notifier wrapper"""
    
    def test_successful_send(self):
        """Test successful alert send"""
        # Mock notifier
        mock_notifier = Mock()
        mock_notifier.send = Mock(return_value=True)
        
        # Wrap in fail-safe
        safe_notifier = FailSafeNotifier(
            notifier=mock_notifier,
            name="test",
            timeout_seconds=1.0,
        )
        
        # Send alert
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Test",
            message="Test",
        )
        
        result = safe_notifier.send(alert)
        assert result is True
        assert safe_notifier.get_status() == NotifierStatus.AVAILABLE
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures"""
        # Mock notifier that always fails
        mock_notifier = Mock()
        mock_notifier.send = Mock(return_value=False)
        
        safe_notifier = FailSafeNotifier(
            notifier=mock_notifier,
            name="test",
            timeout_seconds=1.0,
            circuit_breaker_threshold=3,
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Test",
            message="Test",
        )
        
        # Fail 3 times
        for _ in range(3):
            safe_notifier.send(alert)
        
        # Circuit should be open
        stats = safe_notifier.get_stats()
        assert stats["circuit_open"] is True
        assert stats["status"] == "unavailable"
    
    def test_timeout_protection(self):
        """Test timeout protection"""
        # Mock notifier that hangs
        def slow_send(alert):
            time.sleep(5.0)  # Longer than timeout
            return True
        
        mock_notifier = Mock()
        mock_notifier.send = slow_send
        
        safe_notifier = FailSafeNotifier(
            notifier=mock_notifier,
            name="test",
            timeout_seconds=0.5,  # Short timeout
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Test",
            message="Test",
        )
        
        start = time.time()
        result = safe_notifier.send(alert)
        elapsed = time.time() - start
        
        # Should return quickly (timeout)
        assert elapsed < 1.0
        assert result is False
        assert safe_notifier.get_stats()["timeout_total"] == 1


class TestNotifierFallbackChain:
    """Test notifier fallback chain"""
    
    def test_fallback_to_secondary(self):
        """Test fallback to secondary notifier when primary fails"""
        # Primary fails
        primary = Mock()
        primary.send = Mock(return_value=False)
        primary.is_available = Mock(return_value=True)
        primary.name = "primary"
        
        # Secondary succeeds
        secondary = Mock()
        secondary.send = Mock(return_value=True)
        secondary.is_available = Mock(return_value=True)
        secondary.name = "secondary"
        
        chain = NotifierFallbackChain([primary, secondary])
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Test",
            message="Test",
        )
        
        result = chain.send(alert)
        
        assert result is True
        assert chain.get_stats()["fallback_total"] == 1


# =============================================================================
# AlertDispatcher Tests
# =============================================================================

class TestAlertDispatcher:
    """Test alert dispatcher"""
    
    def setup_method(self):
        """Setup test dispatcher"""
        self.dispatcher = AlertDispatcher(
            redis_client=None,  # In-memory mode
            queue_name="test_dispatcher_queue",
        )
    
    def teardown_method(self):
        """Cleanup"""
        if self.dispatcher._worker_running:
            self.dispatcher.stop_worker()
    
    def test_enqueue_non_blocking(self):
        """Test enqueue is non-blocking"""
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Test",
            message="Test",
        )
        
        start = time.time()
        result = self.dispatcher.enqueue(alert, rule_id="TEST-001")
        elapsed = time.time() - start
        
        # Should be very fast (< 10ms)
        assert elapsed < 0.01
        assert result is True
    
    def test_worker_processes_queue(self):
        """Test worker thread processes queued alerts"""
        # Mock notifier
        mock_notifier = Mock()
        mock_notifier.send = Mock(return_value=True)
        
        self.dispatcher.register_notifier("telegram", mock_notifier)
        self.dispatcher.start_worker()
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Test",
            message="Test",
        )
        
        self.dispatcher.enqueue(alert, rule_id="TEST-001")
        
        # Wait for processing
        time.sleep(0.5)
        
        # Check stats
        stats = self.dispatcher.get_stats()
        assert stats["enqueued"] >= 1


# =============================================================================
# AlertMetrics Tests
# =============================================================================

class TestAlertMetrics:
    """Test alert metrics collector"""
    
    def setup_method(self):
        """Setup test metrics"""
        self.metrics = AlertMetrics(enable_prometheus=False)
    
    def test_record_sent(self):
        """Test record sent metric"""
        self.metrics.record_sent("FX-001", "telegram")
        self.metrics.record_sent("FX-001", "telegram")
        
        stats = self.metrics.get_stats()
        assert stats["counters"]["sent:FX-001:telegram"] == 2
    
    def test_record_failed(self):
        """Test record failed metric"""
        self.metrics.record_failed("FX-001", "telegram", "timeout")
        
        stats = self.metrics.get_stats()
        assert stats["counters"]["failed:FX-001:telegram:timeout"] == 1
    
    def test_record_delivery_latency(self):
        """Test record delivery latency"""
        self.metrics.record_delivery_latency("telegram", 0.5)
        self.metrics.record_delivery_latency("telegram", 1.0)
        
        stats = self.metrics.get_stats()
        histogram = stats["histograms"]["latency:telegram"]
        assert histogram["count"] == 2
        assert histogram["avg"] == 0.75


# =============================================================================
# Integration Tests
# =============================================================================

class TestAlertManagerWithDispatcher:
    """Test AlertManager with dispatcher integration"""
    
    def setup_method(self):
        """Setup with dispatcher"""
        from arbitrage.alerting import AlertManager
        
        # Create dispatcher
        self.dispatcher = AlertDispatcher(
            redis_client=None,
            queue_name="test_integration_queue",
        )
        
        # Create manager with dispatcher
        self.manager = AlertManager(use_dispatcher=True, dispatcher=self.dispatcher)
    
    def teardown_method(self):
        """Cleanup"""
        if self.dispatcher._worker_running:
            self.dispatcher.stop_worker()
    
    def test_send_alert_enqueues_to_dispatcher(self):
        """Test send_alert enqueues to dispatcher when use_dispatcher=True"""
        result = self.manager.send_alert(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Test",
            message="Test",
            rule_id="FX-001",
        )
        
        assert result is True
        
        # Check dispatcher stats
        stats = self.dispatcher.get_stats()
        assert stats["enqueued"] >= 1


class TestBackwardCompatibility:
    """Test backward compatibility with legacy mode"""
    
    def test_legacy_mode_without_dispatcher(self):
        """Test AlertManager works in legacy mode (use_dispatcher=False)"""
        from arbitrage.alerting import AlertManager
        
        # Create manager WITHOUT dispatcher (default)
        manager = AlertManager(use_dispatcher=False)
        
        # Should work without dispatcher
        result = manager.send_alert(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Test",
            message="Test",
        )
        
        # Returns True (not rate limited)
        assert result is True
