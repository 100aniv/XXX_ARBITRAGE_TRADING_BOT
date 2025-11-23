"""Alert models and enums"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional


class AlertSeverity(Enum):
    """Alert severity levels"""
    P0 = "P0"  # Critical
    P1 = "P1"  # High
    P2 = "P2"  # Medium
    P3 = "P3"  # Low


class AlertSource(Enum):
    """Alert event sources"""
    RATE_LIMITER = "RATE_LIMITER"
    HEALTH_MONITOR = "HEALTH_MONITOR"
    EXCHANGE_HEALTH = "HEALTH_MONITOR"  # Alias for backward compatibility
    ARB_ROUTE = "ARB_ROUTE"
    ARB_UNIVERSE = "ARB_UNIVERSE"
    CROSS_SYNC = "CROSS_SYNC"
    RISK_GUARD = "RISK_GUARD"
    SYSTEM = "SYSTEM"


@dataclass
class AlertRecord:
    """Alert record"""
    severity: AlertSeverity
    source: AlertSource
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "severity": self.severity.value,
            "source": self.source.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
        }
