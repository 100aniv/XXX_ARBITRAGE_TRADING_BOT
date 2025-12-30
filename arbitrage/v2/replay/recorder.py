"""
D205-5: Market Recorder

실시간 마켓 데이터를 NDJSON 파일로 기록
"""

import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from arbitrage.v2.replay.schemas import MarketTick

logger = logging.getLogger(__name__)


class MarketRecorder:
    """
    Market Data Recorder
    
    실시간 마켓 데이터를 market.ndjson 파일로 기록
    """
    
    def __init__(self, output_path: Path):
        """
        Args:
            output_path: market.ndjson 파일 경로
        """
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.tick_count = 0
        
        logger.info(f"[D205-5_RECORDER] Initialized: {output_path}")
    
    def record_tick(self, tick: MarketTick):
        """
        Tick 기록
        
        Args:
            tick: MarketTick 객체
        """
        try:
            with open(self.output_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(tick.to_dict(), ensure_ascii=False) + "\n")
            
            self.tick_count += 1
            
            if self.tick_count % 10 == 0:
                logger.debug(f"[D205-5_RECORDER] Recorded {self.tick_count} ticks")
        
        except Exception as e:
            logger.error(f"[D205-5_RECORDER] Record error: {e}")
    
    def close(self):
        """Recorder 종료"""
        logger.info(f"[D205-5_RECORDER] Closed: {self.tick_count} ticks recorded")
