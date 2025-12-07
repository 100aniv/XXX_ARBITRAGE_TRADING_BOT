# -*- coding: utf-8 -*-
"""
D85-0.1: Debug Multi L2 Runtime - Enhanced Monitoring

목적:
1. MultiExchangeL2Provider snapshot 수신 확인
2. Aggregator 상태 모니터링
3. Callback wiring 검증
"""

import sys
import time
import logging
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from arbitrage.exchanges.multi_exchange_l2_provider import MultiExchangeL2Provider, ExchangeId

logging.basicConfig(
    level=logging.DEBUG,  # DEBUG로 변경하여 더 자세한 로그 확인
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def main():
    logger.info("[D85-0.1_DEBUG] ========================================")
    logger.info("[D85-0.1_DEBUG] Multi L2 Runtime Debug - START")
    logger.info("[D85-0.1_DEBUG] ========================================")
    
    # MultiExchangeL2Provider 생성
    provider = MultiExchangeL2Provider(
        symbols=["BTC"],
        staleness_threshold_seconds=2.0,
    )
    
    # Start
    logger.info("[D85-0.1_DEBUG] Starting provider...")
    provider.start()
    
    # 주기적 모니터링 (30초)
    logger.info("[D85-0.1_DEBUG] Monitoring for 30 seconds...")
    for i in range(6):
        time.sleep(5)
        
        logger.info(f"[D85-0.1_DEBUG] ===== Check #{i+1} (t={5*(i+1)}s) =====")
        
        # Aggregator 상태
        stats = provider.aggregator.get_stats()
        logger.info(f"[D85-0.1_DEBUG] Aggregator stats: {stats}")
        
        # Snapshot 가져오기
        snapshot = provider.get_latest_snapshot("BTC")
        
        if snapshot is None:
            logger.error("[D85-0.1_DEBUG] ❌ Snapshot is None!")
            
            # 개별 Provider 상태 확인
            for ex_id, ex_provider in provider._exchange_providers.items():
                ex_snapshot = ex_provider.get_latest_snapshot("BTC")
                logger.info(
                    f"[D85-0.1_DEBUG] {ex_id.value} provider snapshot: "
                    f"{'AVAILABLE' if ex_snapshot else 'NONE'}"
                )
                if ex_snapshot:
                    logger.info(
                        f"[D85-0.1_DEBUG] {ex_id.value} bid={ex_snapshot.bids[0][0] if ex_snapshot.bids else None}, "
                        f"ask={ex_snapshot.asks[0][0] if ex_snapshot.asks else None}"
                    )
        else:
            logger.info(f"[D85-0.1_DEBUG] ✅ Snapshot type: {type(snapshot).__name__}")
            logger.info(f"[D85-0.1_DEBUG] hasattr(per_exchange): {hasattr(snapshot, 'per_exchange')}")
            
            if hasattr(snapshot, 'per_exchange'):
                logger.info(f"[D85-0.1_DEBUG] per_exchange keys: {list(snapshot.per_exchange.keys())}")
                logger.info(f"[D85-0.1_DEBUG] best_bid: {snapshot.best_bid}, exchange: {snapshot.best_bid_exchange}")
                logger.info(f"[D85-0.1_DEBUG] best_ask: {snapshot.best_ask}, exchange: {snapshot.best_ask_exchange}")
                
                # 각 거래소별 상세 정보
                for ex_id, ex_snapshot in snapshot.per_exchange.items():
                    if ex_snapshot:
                        logger.info(
                            f"[D85-0.1_DEBUG] {ex_id.value}: "
                            f"bid={ex_snapshot.bids[0][0] if ex_snapshot.bids else None}, "
                            f"ask={ex_snapshot.asks[0][0] if ex_snapshot.asks else None}, "
                            f"age={(time.time() - ex_snapshot.timestamp):.1f}s"
                        )
    
    # 최종 요약
    logger.info("[D85-0.1_DEBUG] ========================================")
    logger.info("[D85-0.1_DEBUG] Final Summary:")
    final_stats = provider.aggregator.get_stats()
    logger.info(f"[D85-0.1_DEBUG] Aggregation count: {final_stats['aggregation_count']}")
    logger.info(f"[D85-0.1_DEBUG] Both active: {final_stats['both_active_count']}")
    logger.info(f"[D85-0.1_DEBUG] Single active: {final_stats['single_active_count']}")
    logger.info(f"[D85-0.1_DEBUG] No active: {final_stats['no_active_count']}")
    
    # Stop
    provider.stop()
    logger.info("[D85-0.1_DEBUG] Provider stopped")
    logger.info("[D85-0.1_DEBUG] ========================================")
    logger.info("[D85-0.1_DEBUG] Multi L2 Runtime Debug - END")
    logger.info("[D85-0.1_DEBUG] ========================================")

if __name__ == "__main__":
    main()
