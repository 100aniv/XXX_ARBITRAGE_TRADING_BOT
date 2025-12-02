"""
D80-11: Fail-Safe Notifier Wrapper

Wraps Telegram/Slack notifiers with timeout, retry, and fallback logic.
Ensures notifier failures never block business logic.
"""

import time
import logging
from typing import Optional, Callable, Any, List
from enum import Enum
import threading

from .models import AlertRecord

logger = logging.getLogger(__name__)


class NotifierStatus(Enum):
    """Notifier availability status"""
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class FailSafeNotifier:
    """
    Fail-safe wrapper for notifiers (Telegram, Slack, etc.)
    
    Features:
    - Timeout protection (3 seconds default)
    - Circuit breaker (auto-disable after N failures)
    - Graceful degradation
    - No exception propagation to caller
    - Availability tracking
    
    Usage:
        telegram_notifier = TelegramNotifier(...)
        safe_notifier = FailSafeNotifier(
            notifier=telegram_notifier,
            name="telegram",
            timeout_seconds=3,
        )
        result = safe_notifier.send(alert)  # Never throws
    """
    
    def __init__(
        self,
        notifier: Any,
        name: str,
        timeout_seconds: float = 3.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_reset_seconds: int = 60,
    ):
        """
        Initialize fail-safe notifier wrapper
        
        Args:
            notifier: Underlying notifier (must have .send(alert) method)
            name: Notifier name ("telegram", "slack", etc.)
            timeout_seconds: Send timeout (default 3s)
            circuit_breaker_threshold: Failures before opening circuit
            circuit_breaker_reset_seconds: Time before trying to close circuit
        """
        self.notifier = notifier
        self.name = name
        self.timeout_seconds = timeout_seconds
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_reset_seconds = circuit_breaker_reset_seconds
        
        # Circuit breaker state
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_opened_at: Optional[float] = None
        self._last_success_at: Optional[float] = None
        self._last_failure_at: Optional[float] = None
        
        # Statistics
        self._stats = {
            "sent_total": 0,
            "success_total": 0,
            "failure_total": 0,
            "timeout_total": 0,
            "circuit_breaker_open_count": 0,
        }
        
        # Thread safety
        self._lock = threading.RLock()
    
    def send(self, alert: AlertRecord) -> bool:
        """
        Send alert with fail-safe protection
        
        Args:
            alert: Alert to send
        
        Returns:
            True if sent successfully, False otherwise
            (Never raises exception)
        """
        with self._lock:
            self._stats["sent_total"] += 1
            
            # Check circuit breaker
            if self._circuit_open:
                if self._should_try_close_circuit():
                    logger.info(f"[{self.name}] Attempting to close circuit breaker")
                    self._circuit_open = False
                    self._consecutive_failures = 0
                else:
                    logger.warning(f"[{self.name}] Circuit breaker open, skipping send")
                    return False
            
            # Try to send with timeout
            try:
                result = self._send_with_timeout(alert)
                
                if result:
                    # Success
                    self._on_success()
                    return True
                else:
                    # Failure (returned False)
                    self._on_failure(reason="send_returned_false")
                    return False
            
            except Exception as e:
                # Exception during send
                self._on_failure(reason=f"exception: {type(e).__name__}")
                logger.error(f"[{self.name}] Send failed: {e}")
                return False
    
    def _send_with_timeout(self, alert: AlertRecord) -> bool:
        """
        Send alert with timeout protection
        
        Uses threading to implement timeout (simple approach).
        More robust approach would use multiprocessing or async/await.
        """
        result_container = {"success": False, "done": False}
        
        def _send_worker():
            try:
                # Call underlying notifier
                result = self.notifier.send(alert)
                result_container["success"] = result
            except Exception as e:
                logger.error(f"[{self.name}] Notifier raised exception: {e}")
                result_container["success"] = False
            finally:
                result_container["done"] = True
        
        # Start worker thread
        worker = threading.Thread(target=_send_worker, daemon=True)
        worker.start()
        
        # Wait with timeout
        worker.join(timeout=self.timeout_seconds)
        
        if not result_container["done"]:
            # Timeout occurred
            self._stats["timeout_total"] += 1
            logger.warning(f"[{self.name}] Send timeout after {self.timeout_seconds}s")
            return False
        
        return result_container["success"]
    
    def _on_success(self):
        """Handle successful send"""
        self._stats["success_total"] += 1
        self._last_success_at = time.time()
        self._consecutive_failures = 0
    
    def _on_failure(self, reason: str):
        """Handle failed send"""
        self._stats["failure_total"] += 1
        self._last_failure_at = time.time()
        self._consecutive_failures += 1
        
        # Check if should open circuit breaker
        if self._consecutive_failures >= self.circuit_breaker_threshold:
            if not self._circuit_open:
                self._open_circuit()
    
    def _open_circuit(self):
        """Open circuit breaker (disable notifier)"""
        self._circuit_open = True
        self._circuit_opened_at = time.time()
        self._stats["circuit_breaker_open_count"] += 1
        logger.error(
            f"[{self.name}] Circuit breaker OPENED "
            f"(failures: {self._consecutive_failures}/{self.circuit_breaker_threshold})"
        )
    
    def _should_try_close_circuit(self) -> bool:
        """Check if should try to close circuit breaker"""
        if not self._circuit_open:
            return False
        
        if self._circuit_opened_at is None:
            return True
        
        elapsed = time.time() - self._circuit_opened_at
        return elapsed >= self.circuit_breaker_reset_seconds
    
    def get_status(self) -> NotifierStatus:
        """Get current notifier status"""
        with self._lock:
            if self._circuit_open:
                return NotifierStatus.UNAVAILABLE
            
            # Check recent failure rate
            if self._consecutive_failures >= self.circuit_breaker_threshold // 2:
                return NotifierStatus.DEGRADED
            
            return NotifierStatus.AVAILABLE
    
    def get_stats(self) -> dict:
        """Get notifier statistics"""
        with self._lock:
            stats = dict(self._stats)
            stats["status"] = self.get_status().value
            stats["consecutive_failures"] = self._consecutive_failures
            stats["circuit_open"] = self._circuit_open
            stats["last_success_at"] = self._last_success_at
            stats["last_failure_at"] = self._last_failure_at
            
            # Calculate success rate
            total = stats["sent_total"]
            if total > 0:
                stats["success_rate"] = stats["success_total"] / total
            else:
                stats["success_rate"] = 0.0
            
            return stats
    
    def is_available(self) -> bool:
        """Check if notifier is currently available"""
        return self.get_status() != NotifierStatus.UNAVAILABLE
    
    def reset_circuit(self):
        """Manually reset circuit breaker (for testing/ops)"""
        with self._lock:
            self._circuit_open = False
            self._consecutive_failures = 0
            self._circuit_opened_at = None
            logger.info(f"[{self.name}] Circuit breaker manually reset")


class NotifierFallbackChain:
    """
    Fallback chain for notifiers (Primary → Secondary → Tertiary)
    
    Usage:
        chain = NotifierFallbackChain([
            FailSafeNotifier(telegram_notifier, "telegram"),
            FailSafeNotifier(slack_notifier, "slack"),
            LocalLogNotifier(),
        ])
        result = chain.send(alert)  # Tries each in order
    """
    
    def __init__(self, notifiers: List[FailSafeNotifier]):
        """
        Initialize fallback chain
        
        Args:
            notifiers: List of notifiers in fallback order
        """
        self.notifiers = notifiers
        
        # Statistics
        self._stats = {
            "sent_total": 0,
            "success_total": 0,
            "fallback_total": 0,
            "all_failed_total": 0,
        }
        
        self._lock = threading.RLock()
    
    def send(self, alert: AlertRecord) -> bool:
        """
        Send alert with fallback chain
        
        Tries each notifier in order until one succeeds.
        
        Returns:
            True if any notifier succeeded, False if all failed
        """
        with self._lock:
            self._stats["sent_total"] += 1
            
            for i, notifier in enumerate(self.notifiers):
                if not notifier.is_available():
                    logger.debug(f"[FallbackChain] Skipping unavailable notifier: {notifier.name}")
                    continue
                
                success = notifier.send(alert)
                
                if success:
                    self._stats["success_total"] += 1
                    if i > 0:
                        self._stats["fallback_total"] += 1
                        logger.warning(
                            f"[FallbackChain] Alert sent via fallback notifier: {notifier.name} "
                            f"(primary failed)"
                        )
                    return True
            
            # All notifiers failed
            self._stats["all_failed_total"] += 1
            logger.error("[FallbackChain] All notifiers failed")
            return False
    
    def get_stats(self) -> dict:
        """Get fallback chain statistics"""
        with self._lock:
            stats = dict(self._stats)
            stats["notifiers"] = [
                {
                    "name": n.name,
                    "status": n.get_status().value,
                    "success_rate": n.get_stats().get("success_rate", 0.0),
                }
                for n in self.notifiers
            ]
            return stats


class LocalLogNotifier:
    """
    Last-resort notifier that logs alerts locally
    
    Always succeeds (unless disk full, but we ignore that).
    """
    
    def __init__(self, log_file: Optional[str] = None):
        """
        Initialize local log notifier
        
        Args:
            log_file: Path to log file (None = use logger)
        """
        self.log_file = log_file
        self.name = "local_log"
    
    def send(self, alert: AlertRecord) -> bool:
        """Log alert locally"""
        try:
            message = (
                f"[ALERT] {alert.severity.value} | {alert.source.value} | "
                f"{alert.title} | {alert.message}"
            )
            
            if self.log_file:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(f"{time.time()}: {message}\n")
            else:
                logger.warning(message)
            
            return True
        
        except Exception as e:
            logger.error(f"LocalLogNotifier failed: {e}")
            return False
    
    def is_available(self) -> bool:
        """Local log always available"""
        return True
    
    def get_status(self) -> NotifierStatus:
        """Local log always available"""
        return NotifierStatus.AVAILABLE
