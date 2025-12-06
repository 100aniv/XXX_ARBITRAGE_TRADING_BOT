#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D84-0: D82-11/12 KPI JSON에서 Fill Event 추출

목적:
    기존 D82-11/12 실행 로그에서 Fill 관련 정보를 추출하여
    Fill Model v1 보정에 사용할 데이터 생성.

입력:
    logs/d82-11/runs/*.json (D82-11/12 KPI)

출력:
    logs/d84/d84_0_fill_events_d82.jsonl

Author: arbitrage-lite project
Date: 2025-12-06
"""

import json
import logging
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class FillEvent:
    """Fill Event 데이터"""
    # 식별 정보
    timestamp: str  # ISO format
    session_id: str
    run_id: str
    symbol: str  # "BTC/USDT" 등 (현재는 unknown)
    
    # 거래 파라미터
    side: str  # "BUY" or "SELL"
    entry_bps: float
    tp_bps: float
    order_quantity: float  # 추정치
    
    # Fill 결과
    filled: bool  # 체결 성공 여부
    filled_quantity: float
    fill_ratio: float  # 0.0 ~ 1.0
    slippage_bps: float
    
    # 시장 조건
    available_volume: float  # 추정치 (현재는 알 수 없음)
    spread_bps: float  # 추정치
    
    # 퇴출 이유
    exit_reason: str  # "take_profit", "stop_loss", "time_limit", "spread_reversal"
    latency_ms: Optional[float]  # 알 수 없음
    
    # 메타 정보
    source_file: str


# =============================================================================
# KPI Parser
# =============================================================================

def extract_fill_events_from_kpi(kpi_path: Path) -> List[FillEvent]:
    """
    KPI JSON에서 Fill Event 추출
    
    Args:
        kpi_path: KPI JSON 파일 경로
    
    Returns:
        Fill Event 리스트
    """
    logger.info(f"Parsing KPI: {kpi_path.name}")
    
    with open(kpi_path, "r") as f:
        kpi = json.load(f)
    
    events = []
    
    # KPI에서 정보 추출
    session_id = kpi.get("session_id", "unknown")
    entry_trades = kpi.get("entry_trades", 0)
    exit_trades = kpi.get("exit_trades", 0)
    round_trips = kpi.get("round_trips_completed", 0)
    
    buy_fill_ratio = kpi.get("avg_buy_fill_ratio", 0.0)
    sell_fill_ratio = kpi.get("avg_sell_fill_ratio", 1.0)
    buy_slippage = kpi.get("avg_buy_slippage_bps", 0.0)
    sell_slippage = kpi.get("avg_sell_slippage_bps", 0.0)
    
    exit_reasons = kpi.get("exit_reasons", {})
    dominant_exit = max(exit_reasons, key=exit_reasons.get) if exit_reasons else "time_limit"
    
    # run_id에서 Entry/TP 추출 (파일명 파싱)
    # 예: d82-11-600-E10p0_TP12p0-20251206004025_kpi.json
    filename = kpi_path.stem
    try:
        if "E" in filename and "TP" in filename:
            parts = filename.split("-")
            for part in parts:
                if part.startswith("E") and "_TP" in part:
                    entry_tp = part.split("_")
                    entry_str = entry_tp[0][1:]  # "E10p0" -> "10p0"
                    tp_str = entry_tp[1][2:]  # "TP12p0" -> "12p0"
                    entry_bps = float(entry_str.replace("p", "."))
                    tp_bps = float(tp_str.replace("p", "."))
                    break
            else:
                entry_bps = 0.0
                tp_bps = 0.0
        else:
            entry_bps = 0.0
            tp_bps = 0.0
    except Exception as e:
        logger.warning(f"Failed to parse Entry/TP from filename: {e}")
        entry_bps = 0.0
        tp_bps = 0.0
    
    # Round Trip당 BUY/SELL 이벤트 생성
    for i in range(round_trips):
        # BUY Event
        buy_event = FillEvent(
            timestamp=datetime.utcnow().isoformat(),
            session_id=session_id,
            run_id=filename,
            symbol="BTC/USDT",  # 추정
            side="BUY",
            entry_bps=entry_bps,
            tp_bps=tp_bps,
            order_quantity=1000.0,  # 추정치 (실제는 알 수 없음)
            filled=True,  # Round trip이 완료되었으므로
            filled_quantity=1000.0 * buy_fill_ratio,
            fill_ratio=buy_fill_ratio,
            slippage_bps=buy_slippage,
            available_volume=1000.0 / buy_fill_ratio if buy_fill_ratio > 0 else 0.0,  # 역산
            spread_bps=entry_bps,
            exit_reason=dominant_exit,
            latency_ms=None,
            source_file=str(kpi_path),
        )
        events.append(buy_event)
        
        # SELL Event
        sell_event = FillEvent(
            timestamp=datetime.utcnow().isoformat(),
            session_id=session_id,
            run_id=filename,
            symbol="BTC/USDT",
            side="SELL",
            entry_bps=entry_bps,
            tp_bps=tp_bps,
            order_quantity=1000.0 * buy_fill_ratio,  # 매수 체결량
            filled=True,
            filled_quantity=1000.0 * buy_fill_ratio * sell_fill_ratio,
            fill_ratio=sell_fill_ratio,
            slippage_bps=sell_slippage,
            available_volume=1000.0 * buy_fill_ratio / sell_fill_ratio if sell_fill_ratio > 0 else 0.0,
            spread_bps=tp_bps,
            exit_reason=dominant_exit,
            latency_ms=None,
            source_file=str(kpi_path),
        )
        events.append(sell_event)
    
    logger.info(f"  Extracted {len(events)} events ({round_trips} RTs)")
    return events


# =============================================================================
# Main
# =============================================================================

def main():
    """Main entry point"""
    logger.info("=" * 80)
    logger.info("D84-0: D82-11/12 Fill Event 추출")
    logger.info("=" * 80)
    
    # 1. D82-11/12 KPI 파일 검색
    d82_11_dir = Path("logs/d82-11/runs")
    d82_12_dir = Path("logs/d82-12")  # D82-12는 별도 runs 없을 수 있음
    
    kpi_files = []
    
    if d82_11_dir.exists():
        kpi_files.extend(d82_11_dir.glob("*_kpi.json"))
    
    if d82_12_dir.exists():
        kpi_files.extend(d82_12_dir.glob("*_kpi.json"))
    
    logger.info(f"Found {len(kpi_files)} KPI files")
    
    if not kpi_files:
        logger.error("No KPI files found in logs/d82-11 or logs/d82-12")
        return 1
    
    # 2. Fill Event 추출
    all_events = []
    for kpi_path in kpi_files:
        try:
            events = extract_fill_events_from_kpi(kpi_path)
            all_events.extend(events)
        except Exception as e:
            logger.error(f"Failed to parse {kpi_path.name}: {e}")
    
    logger.info(f"Total events extracted: {len(all_events)}")
    
    # 3. JSONL로 저장
    output_path = Path("logs/d84/d84_0_fill_events_d82.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        for event in all_events:
            f.write(json.dumps(asdict(event)) + "\n")
    
    logger.info(f"Saved to: {output_path}")
    logger.info("=" * 80)
    logger.info("✅ Fill Event 추출 완료")
    logger.info("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
