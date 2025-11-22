"""Base notifier interface"""

from abc import ABC, abstractmethod
from typing import Any
from ..models import AlertRecord


class NotifierBase(ABC):
    """Base class for all notifiers"""
    
    @abstractmethod
    def send(self, alert: AlertRecord) -> bool:
        """
        Send alert notification
        
        Args:
            alert: Alert record to send
        
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if notifier is available and configured"""
        pass
