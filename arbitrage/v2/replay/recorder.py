"""
D205-5: Market Recorder

실시간 마켓 데이터를 NDJSON 파일로 기록
"""

import json
import logging
import sys
import platform
import subprocess
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
    
    def save_manifest(self, symbols: list, duration_sec: float):
        """
        Record manifest 저장 (git_sha, branch 등 메타 포함)
        
        Args:
            symbols: 기록한 심볼 리스트
            duration_sec: 기록 시간 (초)
        """
        # Git 메타 정보 수집
        git_sha_full = ""
        git_sha_short = ""
        git_branch = ""
        try:
            git_sha_full = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], 
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
            git_sha_short = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], 
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
            git_branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
        except Exception as e:
            logger.warning(f"[D205-5_RECORDER] Git info collection failed: {e}")
        
        manifest = {
            "run_id": self.output_path.parent.name,
            "mode": "record",
            "timestamp": datetime.now().isoformat(),
            "duration_sec": round(duration_sec, 2),
            "symbols": symbols,
            "ticks_recorded": self.tick_count,
            "output_path": str(self.output_path.relative_to(Path.cwd())) if self.output_path.is_relative_to(Path.cwd()) else str(self.output_path),
            "git_sha_full": git_sha_full,
            "git_sha_short": git_sha_short,
            "branch": git_branch,
            "cmdline": " ".join(sys.argv),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        }
        
        manifest_path = self.output_path.parent / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[D205-5_RECORDER] Saved manifest to {manifest_path}")
