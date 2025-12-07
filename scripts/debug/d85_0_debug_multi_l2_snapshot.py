# -*- coding: utf-8 -*-
"""
D85-0: Debug Multi L2 Snapshot Type

목적: MultiExchangeL2Provider.get_latest_snapshot() 반환값 타입 확인
"""

import sys
import time
import logging
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from arbitrage.exchanges.multi_exchange_l2_provider import MultiExchangeL2Provider

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def main():
    logger.info("[D85-0_DEBUG] Starting Multi L2 snapshot type check...")
    
    # MultiExchangeL2Provider 생성
    provider = MultiExchangeL2Provider(
        symbols=["BTC"],
        staleness_threshold_seconds=2.0,
    )
    
    # Start
    provider.start()
    logger.info("[D85-0_DEBUG] Provider started, waiting 5 seconds for first snapshots...")
    time.sleep(5)
    
    # Get snapshot
    snapshot = provider.get_latest_snapshot("BTC")
    
    logger.info(f"[D85-0_DEBUG] Snapshot type: {type(snapshot)}")
    logger.info(f"[D85-0_DEBUG] Snapshot: {snapshot}")
    
    if snapshot is None:
        logger.error("[D85-0_DEBUG] Snapshot is None!")
    else:
        logger.info(f"[D85-0_DEBUG] hasattr(snapshot, 'per_exchange'): {hasattr(snapshot, 'per_exchange')}")
        logger.info(f"[D85-0_DEBUG] hasattr(snapshot, 'bids'): {hasattr(snapshot, 'bids')}")
        logger.info(f"[D85-0_DEBUG] hasattr(snapshot, 'asks'): {hasattr(snapshot, 'asks')}")
        
        if hasattr(snapshot, 'per_exchange'):
            logger.info(f"[D85-0_DEBUG] per_exchange keys: {list(snapshot.per_exchange.keys())}")
            logger.info(f"[D85-0_DEBUG] best_bid_exchange: {snapshot.best_bid_exchange}")
            logger.info(f"[D85-0_DEBUG] best_ask_exchange: {snapshot.best_ask_exchange}")
    
    # Stop
    provider.stop()
    logger.info("[D85-0_DEBUG] Provider stopped")

if __name__ == "__main__":
    main()
