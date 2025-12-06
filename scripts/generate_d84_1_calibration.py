# -*-coding: utf-8 -*-
"""
D84-1: Calibration 데이터 생성 스크립트

목적:
    Fill Event JSONL 파일들을 분석하여 Calibration JSON 생성.

입력:
    logs/d84/d84_0_fill_events_d82.jsonl (D82 데이터)
    logs/d84/d84_1_fill_events_paper.jsonl (D84-1 PAPER 데이터, 선택)

출력:
    logs/d84/d84_1_calibration.json

Author: arbitrage-lite project
Date: 2025-12-06
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.analysis.fill_calibrator import FillModelCalibrator

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point"""
    logger.info("=" * 80)
    logger.info("D84-1: Calibration 데이터 생성")
    logger.info("=" * 80)
    
    # 입력 파일
    input_paths = [
        Path("logs/d84/d84_0_fill_events_d82.jsonl"),
    ]
    
    # D84-1 PAPER 데이터 있으면 추가
    paper_path = Path("logs/d84/d84_1_fill_events_paper.jsonl")
    if paper_path.exists():
        input_paths.append(paper_path)
        logger.info(f"D84-1 PAPER 데이터 포함: {paper_path}")
    
    # 출력 파일
    output_path = Path("logs/d84/d84_1_calibration.json")
    
    # Fill Events 로드
    events = FillModelCalibrator.load_fill_events(input_paths)
    
    if len(events) == 0:
        logger.error("No events found!")
        return 1
    
    # Calibration JSON 생성
    calibration = FillModelCalibrator.create_calibration_json(
        events=events,
        output_path=output_path,
        version="d84_1",
        source="D82-11/12 + D84-1 PAPER (if exists)",
    )
    
    logger.info("=" * 80)
    logger.info("✅ Calibration 생성 완료")
    logger.info(f"Total events: {calibration['total_events']}")
    logger.info(f"Zones: {len(calibration['zones'])}")
    logger.info(f"Output: {output_path}")
    logger.info("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
