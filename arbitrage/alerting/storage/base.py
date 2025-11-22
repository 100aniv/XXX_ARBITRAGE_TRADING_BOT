"""Base storage interface"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from ..models import AlertRecord, AlertSeverity, AlertSource


class StorageBase(ABC):
    """Base class for alert storage backends"""
    
    @abstractmethod
    def save(self, alert: AlertRecord) -> bool:
        """Save alert record"""
        pass
    
    @abstractmethod
    def get_recent(
        self,
        minutes: int = 60,
        severity: Optional[AlertSeverity] = None,
        source: Optional[AlertSource] = None,
    ) -> List[AlertRecord]:
        """Get recent alerts with optional filters"""
        pass
    
    @abstractmethod
    def get_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> List[AlertRecord]:
        """Get alerts within time range"""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """Clear all alerts (for testing)"""
        pass
