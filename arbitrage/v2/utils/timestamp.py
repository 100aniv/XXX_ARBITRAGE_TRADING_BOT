"""
D205-2 REOPEN-2: Timestamp 정규화 유틸 (UTC naive SSOT)

Purpose:
- DB insert/query 시 UTC naive 통일
- D204-1 회귀 "UTC naive vs aware" 혼선 제거

Usage:
    from arbitrage.v2.utils.timestamp import to_utc_naive
    
    dt_aware = datetime.now(timezone.utc)
    dt_naive = to_utc_naive(dt_aware)
    
    # DB insert
    storage.insert_order(..., timestamp=to_utc_naive(dt), ...)

Author: arbitrage-lite V2
Date: 2025-12-30
"""

from datetime import datetime, timezone
from typing import Optional


def to_utc_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """
    datetime을 UTC naive로 변환 (SSOT)
    
    Args:
        dt: datetime 객체 (aware/naive 모두 허용)
        
    Returns:
        UTC naive datetime (timezone 정보 제거)
        
    Examples:
        >>> from datetime import datetime, timezone
        >>> dt_aware = datetime(2025, 12, 30, 12, 0, 0, tzinfo=timezone.utc)
        >>> dt_naive = to_utc_naive(dt_aware)
        >>> dt_naive.tzinfo is None
        True
        >>> dt_naive.isoformat()
        '2025-12-30T12:00:00'
    """
    if dt is None:
        return None
    
    # 이미 naive면 그대로 반환
    if dt.tzinfo is None:
        return dt
    
    # aware → UTC로 변환 → tzinfo 제거
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def now_utc_naive() -> datetime:
    """
    현재 시각을 UTC naive로 반환
    
    Returns:
        UTC naive datetime
        
    Examples:
        >>> dt = now_utc_naive()
        >>> dt.tzinfo is None
        True
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
