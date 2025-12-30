"""
D205-1: V2 Reporting Module

목적:
- Daily PnL 및 Operational metrics 집계
- v2_pnl_daily, v2_ops_daily 테이블 자동 업데이트
- 자동화된 리포팅 파이프라인

Author: arbitrage-lite V2
Date: 2025-12-30
"""

from .aggregator import aggregate_pnl_daily, aggregate_ops_daily
from .writer import upsert_pnl_daily, upsert_ops_daily

__all__ = [
    "aggregate_pnl_daily",
    "aggregate_ops_daily",
    "upsert_pnl_daily",
    "upsert_ops_daily",
]
