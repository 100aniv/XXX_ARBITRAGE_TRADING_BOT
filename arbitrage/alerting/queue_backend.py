"""
D80-11: Persistent Alert Queue Backend (Redis-based)

Provides durable queue with retry, DLQ, and ack mechanism.
"""

import json
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import asdict
from datetime import datetime

from .models import AlertRecord

logger = logging.getLogger(__name__)


class PersistentAlertQueue:
    """
    Redis-based persistent alert queue with retry and DLQ support
    
    Features:
    - Durable storage (survives process crashes)
    - Retry mechanism (failed alerts move to retry queue)
    - Dead Letter Queue (DLQ) for permanently failed alerts
    - Acknowledgment-based delivery
    - In-memory fallback for testing
    
    Redis Keys:
    - {queue_name}:pending - Main queue (RPUSH/LPOP)
    - {queue_name}:processing - Processing queue (RPUSH when dequeued)
    - {queue_name}:retry - Retry queue
    - {queue_name}:dlq - Dead letter queue
    - {queue_name}:stats - Stats hash
    """
    
    def __init__(
        self,
        redis_client: Optional[Any] = None,
        queue_name: str = "alert_queue_v2",
        max_retries: int = 3,
        retry_delay_seconds: int = 5,
    ):
        """
        Initialize persistent alert queue
        
        Args:
            redis_client: Redis client (None for in-memory fallback)
            queue_name: Base name for Redis keys
            max_retries: Maximum retry attempts before DLQ
            retry_delay_seconds: Delay between retries
        """
        self.redis_client = redis_client
        self.queue_name = queue_name
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        
        # Redis key names
        self.pending_key = f"{queue_name}:pending"
        self.processing_key = f"{queue_name}:processing"
        self.retry_key = f"{queue_name}:retry"
        self.dlq_key = f"{queue_name}:dlq"
        self.stats_key = f"{queue_name}:stats"
        
        # In-memory fallback
        self._memory_pending: List[Dict[str, Any]] = []
        self._memory_processing: List[Dict[str, Any]] = []
        self._memory_retry: List[Dict[str, Any]] = []
        self._memory_dlq: List[Dict[str, Any]] = []
        self._memory_stats: Dict[str, int] = {
            "enqueued": 0,
            "dequeued": 0,
            "acked": 0,
            "nacked": 0,
            "retried": 0,
            "dlq": 0,
        }
    
    def enqueue(self, alert: AlertRecord, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Enqueue alert to pending queue
        
        Args:
            alert: Alert record
            metadata: Additional metadata (retry_count, original_timestamp, etc.)
        
        Returns:
            True if successfully enqueued
        """
        try:
            # Serialize alert
            payload = {
                "alert": self._serialize_alert(alert),
                "metadata": metadata or {},
                "enqueued_at": time.time(),
            }
            
            if self.redis_client:
                # Redis mode
                self.redis_client.rpush(self.pending_key, json.dumps(payload))
                self.redis_client.hincrby(self.stats_key, "enqueued", 1)
            else:
                # In-memory mode
                self._memory_pending.append(payload)
                self._memory_stats["enqueued"] += 1
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to enqueue alert: {e}")
            return False
    
    def dequeue(self, timeout_seconds: int = 1) -> Optional[Dict[str, Any]]:
        """
        Dequeue alert from pending queue (blocking with timeout)
        
        Returns:
            Alert payload with metadata, or None if queue empty
        """
        try:
            if self.redis_client:
                # Redis mode (BLPOP with timeout)
                result = self.redis_client.blpop(self.pending_key, timeout=timeout_seconds)
                if result:
                    _, payload_json = result
                    payload = json.loads(payload_json)
                    
                    # Move to processing queue
                    self.redis_client.rpush(self.processing_key, json.dumps(payload))
                    self.redis_client.hincrby(self.stats_key, "dequeued", 1)
                    
                    return payload
                return None
            
            else:
                # In-memory mode (non-blocking)
                if self._memory_pending:
                    payload = self._memory_pending.pop(0)
                    self._memory_processing.append(payload)
                    self._memory_stats["dequeued"] += 1
                    return payload
                return None
        
        except Exception as e:
            logger.error(f"Failed to dequeue alert: {e}")
            return None
    
    def ack(self, payload: Dict[str, Any]) -> bool:
        """
        Acknowledge successful processing (remove from processing queue)
        
        Args:
            payload: Alert payload that was processed
        
        Returns:
            True if successfully acknowledged
        """
        try:
            if self.redis_client:
                # Redis mode: remove from processing queue
                payload_json = json.dumps(payload)
                removed = self.redis_client.lrem(self.processing_key, 1, payload_json)
                if removed:
                    self.redis_client.hincrby(self.stats_key, "acked", 1)
                return removed > 0
            
            else:
                # In-memory mode
                if payload in self._memory_processing:
                    self._memory_processing.remove(payload)
                    self._memory_stats["acked"] += 1
                    return True
                return False
        
        except Exception as e:
            logger.error(f"Failed to ack alert: {e}")
            return False
    
    def nack(self, payload: Dict[str, Any], retry: bool = True) -> bool:
        """
        Negative acknowledge (processing failed)
        
        Args:
            payload: Alert payload that failed
            retry: If True, move to retry queue; if False, move to DLQ
        
        Returns:
            True if successfully handled
        """
        try:
            # Remove from processing queue
            if self.redis_client:
                payload_json = json.dumps(payload)
                self.redis_client.lrem(self.processing_key, 1, payload_json)
                self.redis_client.hincrby(self.stats_key, "nacked", 1)
            else:
                if payload in self._memory_processing:
                    self._memory_processing.remove(payload)
                self._memory_stats["nacked"] += 1
            
            # Update retry count
            metadata = payload.get("metadata", {})
            retry_count = metadata.get("retry_count", 0)
            
            if retry and retry_count < self.max_retries:
                # Move to retry queue
                metadata["retry_count"] = retry_count + 1
                metadata["retry_at"] = time.time() + self.retry_delay_seconds
                payload["metadata"] = metadata
                
                if self.redis_client:
                    self.redis_client.rpush(self.retry_key, json.dumps(payload))
                    self.redis_client.hincrby(self.stats_key, "retried", 1)
                else:
                    self._memory_retry.append(payload)
                    self._memory_stats["retried"] += 1
                
                logger.info(f"Alert moved to retry queue (attempt {retry_count + 1}/{self.max_retries})")
            
            else:
                # Move to DLQ (max retries exhausted or explicit no-retry)
                metadata["dlq_at"] = time.time()
                metadata["dlq_reason"] = "max_retries" if retry else "permanent_failure"
                payload["metadata"] = metadata
                
                if self.redis_client:
                    self.redis_client.rpush(self.dlq_key, json.dumps(payload))
                    self.redis_client.hincrby(self.stats_key, "dlq", 1)
                else:
                    self._memory_dlq.append(payload)
                    self._memory_stats["dlq"] += 1
                
                logger.warning(f"Alert moved to DLQ (reason: {metadata['dlq_reason']})")
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to nack alert: {e}")
            return False
    
    def process_retry_queue(self) -> int:
        """
        Move ready-to-retry alerts back to pending queue
        
        Returns:
            Number of alerts moved
        """
        moved_count = 0
        now = time.time()
        
        try:
            if self.redis_client:
                # Redis mode: scan retry queue
                retry_items = self.redis_client.lrange(self.retry_key, 0, -1)
                for item_json in retry_items:
                    payload = json.loads(item_json)
                    retry_at = payload.get("metadata", {}).get("retry_at", 0)
                    
                    if now >= retry_at:
                        # Move back to pending
                        self.redis_client.lrem(self.retry_key, 1, item_json)
                        self.redis_client.rpush(self.pending_key, item_json)
                        moved_count += 1
            
            else:
                # In-memory mode
                ready_items = [
                    p for p in self._memory_retry
                    if now >= p.get("metadata", {}).get("retry_at", 0)
                ]
                for payload in ready_items:
                    self._memory_retry.remove(payload)
                    self._memory_pending.append(payload)
                    moved_count += 1
            
            if moved_count > 0:
                logger.info(f"Moved {moved_count} alerts from retry queue to pending")
        
        except Exception as e:
            logger.error(f"Failed to process retry queue: {e}")
        
        return moved_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        try:
            if self.redis_client:
                stats = {
                    "pending": self.redis_client.llen(self.pending_key),
                    "processing": self.redis_client.llen(self.processing_key),
                    "retry": self.redis_client.llen(self.retry_key),
                    "dlq": self.redis_client.llen(self.dlq_key),
                }
                
                # Get counters from hash
                counters = self.redis_client.hgetall(self.stats_key)
                for key, value in counters.items():
                    stats[key.decode() if isinstance(key, bytes) else key] = int(value)
                
                return stats
            
            else:
                return {
                    "pending": len(self._memory_pending),
                    "processing": len(self._memory_processing),
                    "retry": len(self._memory_retry),
                    "dlq": len(self._memory_dlq),
                    **self._memory_stats,
                }
        
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
    
    def clear_all(self):
        """Clear all queues (for testing)"""
        try:
            if self.redis_client:
                self.redis_client.delete(
                    self.pending_key,
                    self.processing_key,
                    self.retry_key,
                    self.dlq_key,
                    self.stats_key,
                )
            else:
                self._memory_pending.clear()
                self._memory_processing.clear()
                self._memory_retry.clear()
                self._memory_dlq.clear()
                self._memory_stats = {k: 0 for k in self._memory_stats}
        
        except Exception as e:
            logger.error(f"Failed to clear queues: {e}")
    
    def _serialize_alert(self, alert: AlertRecord) -> Dict[str, Any]:
        """Serialize AlertRecord to dict"""
        data = asdict(alert)
        # Convert enums to strings
        data["severity"] = alert.severity.value
        data["source"] = alert.source.value
        data["timestamp"] = alert.timestamp.isoformat()
        return data
    
    def _deserialize_alert(self, data: Dict[str, Any]) -> AlertRecord:
        """Deserialize dict to AlertRecord"""
        from .models import AlertSeverity, AlertSource
        
        return AlertRecord(
            severity=AlertSeverity(data["severity"]),
            source=AlertSource(data["source"]),
            title=data["title"],
            message=data["message"],
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )
