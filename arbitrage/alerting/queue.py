"""
D80-7: Alert Queue (Redis/In-memory)

Async queue for alert processing with Redis or in-memory backend.
"""

import json
import logging
import asyncio
from typing import Optional, Callable, Awaitable, Any, Dict
from datetime import datetime
import queue as stdlib_queue

from .models import AlertRecord, AlertSeverity, AlertSource

logger = logging.getLogger(__name__)


class AlertQueue:
    """
    Async alert queue with Redis or in-memory backend
    
    Features:
    - Redis list-based queue for production
    - In-memory queue for testing/paper mode
    - Async consumer pattern
    - Automatic JSON serialization
    """
    
    def __init__(
        self,
        redis_client: Optional[Any] = None,
        queue_name: str = "alert_queue",
        max_size: int = 1000,
    ):
        """
        Initialize alert queue
        
        Args:
            redis_client: Redis client (None for in-memory mode)
            queue_name: Redis list name or in-memory queue identifier
            max_size: Maximum queue size (in-memory mode only)
        """
        self.redis_client = redis_client
        self.queue_name = queue_name
        self.max_size = max_size
        
        # In-memory fallback
        self._memory_queue: stdlib_queue.Queue = stdlib_queue.Queue(maxsize=max_size)
        
        # Consumer control
        self._consumer_running = False
        self._consumer_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._stats = {
            "enqueued": 0,
            "dequeued": 0,
            "processed": 0,
            "errors": 0,
        }
        
        # Determine mode
        self._use_redis = redis_client is not None
        if self._use_redis:
            try:
                redis_client.ping()
                logger.info(f"[AlertQueue] Using Redis backend (queue={queue_name})")
            except Exception as e:
                logger.warning(f"[AlertQueue] Redis unavailable: {e}")
                self._use_redis = False
                logger.info("[AlertQueue] Falling back to in-memory mode")
        else:
            logger.info("[AlertQueue] Using in-memory backend")
    
    async def enqueue(self, alert: AlertRecord) -> bool:
        """
        Add alert to queue
        
        Args:
            alert: Alert record
        
        Returns:
            True if enqueued successfully
        """
        try:
            if self._use_redis:
                await self._enqueue_redis(alert)
            else:
                await self._enqueue_memory(alert)
            
            self._stats["enqueued"] += 1
            return True
        
        except Exception as e:
            logger.error(f"[AlertQueue] Enqueue error: {e}")
            self._stats["errors"] += 1
            return False
    
    async def dequeue(self, timeout: float = 1.0) -> Optional[AlertRecord]:
        """
        Get alert from queue (blocking with timeout)
        
        Args:
            timeout: Timeout in seconds
        
        Returns:
            AlertRecord or None if queue empty
        """
        try:
            if self._use_redis:
                alert = await self._dequeue_redis(timeout)
            else:
                alert = await self._dequeue_memory(timeout)
            
            if alert:
                self._stats["dequeued"] += 1
            
            return alert
        
        except Exception as e:
            logger.error(f"[AlertQueue] Dequeue error: {e}")
            self._stats["errors"] += 1
            return None
    
    async def start_consumer(
        self,
        handler: Callable[[AlertRecord], Awaitable[None]],
        max_concurrency: int = 10,
    ) -> None:
        """
        Start async consumer
        
        Args:
            handler: Async handler function for processing alerts
            max_concurrency: Maximum concurrent handlers
        """
        if self._consumer_running:
            logger.warning("[AlertQueue] Consumer already running")
            return
        
        self._consumer_running = True
        logger.info(f"[AlertQueue] Starting consumer (max_concurrency={max_concurrency})")
        
        # Semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def process_alert(alert: AlertRecord):
            async with semaphore:
                try:
                    await handler(alert)
                    self._stats["processed"] += 1
                except Exception as e:
                    logger.error(f"[AlertQueue] Handler error: {e}")
                    self._stats["errors"] += 1
        
        # Consumer loop
        while self._consumer_running:
            try:
                alert = await self.dequeue(timeout=1.0)
                if alert:
                    # Fire and forget (don't await)
                    asyncio.create_task(process_alert(alert))
                else:
                    # Queue empty, short sleep
                    await asyncio.sleep(0.1)
            
            except asyncio.CancelledError:
                logger.info("[AlertQueue] Consumer cancelled")
                break
            
            except Exception as e:
                logger.error(f"[AlertQueue] Consumer loop error: {e}")
                await asyncio.sleep(1.0)
        
        logger.info("[AlertQueue] Consumer stopped")
    
    def stop_consumer(self) -> None:
        """Stop consumer"""
        self._consumer_running = False
        if self._consumer_task:
            self._consumer_task.cancel()
    
    async def _enqueue_redis(self, alert: AlertRecord) -> None:
        """Enqueue to Redis"""
        # Serialize alert
        alert_data = {
            "severity": alert.severity.value,
            "source": alert.source.value,
            "title": alert.title,
            "message": alert.message,
            "timestamp": alert.timestamp.isoformat(),
            "metadata": alert.metadata,
        }
        alert_json = json.dumps(alert_data)
        
        # Push to Redis list (RPUSH for FIFO)
        await asyncio.to_thread(self.redis_client.rpush, self.queue_name, alert_json)
    
    async def _dequeue_redis(self, timeout: float) -> Optional[AlertRecord]:
        """Dequeue from Redis"""
        # BLPOP with timeout
        result = await asyncio.to_thread(
            self.redis_client.blpop,
            self.queue_name,
            timeout=int(timeout)
        )
        
        if not result:
            return None
        
        # Parse alert
        _, alert_json = result
        alert_data = json.loads(alert_json)
        
        # Reconstruct AlertRecord
        alert = AlertRecord(
            severity=AlertSeverity(alert_data["severity"]),
            source=AlertSource(alert_data["source"]),
            title=alert_data["title"],
            message=alert_data["message"],
            timestamp=datetime.fromisoformat(alert_data["timestamp"]),
            metadata=alert_data.get("metadata", {}),
        )
        
        return alert
    
    async def _enqueue_memory(self, alert: AlertRecord) -> None:
        """Enqueue to in-memory queue"""
        await asyncio.to_thread(self._memory_queue.put, alert, block=False)
    
    async def _dequeue_memory(self, timeout: float) -> Optional[AlertRecord]:
        """Dequeue from in-memory queue"""
        try:
            alert = await asyncio.to_thread(
                self._memory_queue.get,
                block=True,
                timeout=timeout
            )
            return alert
        except stdlib_queue.Empty:
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "backend": "redis" if self._use_redis else "memory",
            "queue_name": self.queue_name,
            "consumer_running": self._consumer_running,
            "enqueued": self._stats["enqueued"],
            "dequeued": self._stats["dequeued"],
            "processed": self._stats["processed"],
            "errors": self._stats["errors"],
            "pending": self.get_pending_count(),
        }
    
    def get_pending_count(self) -> int:
        """
        Get number of pending alerts in queue
        
        Returns:
            Pending count
        """
        if self._use_redis:
            try:
                return self.redis_client.llen(self.queue_name)
            except Exception as e:
                logger.error(f"[AlertQueue] Redis llen error: {e}")
                return 0
        else:
            return self._memory_queue.qsize()
    
    def clear(self) -> None:
        """Clear all alerts from queue"""
        if self._use_redis:
            try:
                self.redis_client.delete(self.queue_name)
            except Exception as e:
                logger.error(f"[AlertQueue] Redis clear error: {e}")
        else:
            while not self._memory_queue.empty():
                try:
                    self._memory_queue.get_nowait()
                except stdlib_queue.Empty:
                    break
