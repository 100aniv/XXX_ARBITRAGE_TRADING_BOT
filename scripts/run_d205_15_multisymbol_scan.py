#!/usr/bin/env python3
"""
D205-15: Multi-Symbol Profit Candidate Scan

멀티심볼 스캔 (Upbit Spot × Binance Futures) + TopK AutoTune

Usage:
    python scripts/run_d205_15_multisymbol_scan.py --duration-minutes 10 --topk 3
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from statistics import mean, median
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.marketdata.rest.upbit import UpbitRestProvider
from arbitrage.v2.marketdata.rest.binance import BinanceRestProvider
from arbitrage.v2.replay.recorder import MarketRecorder
from arbitrage.v2.replay.schemas import MarketTick
from arbitrage.v2.execution_quality.autotune import AutoTuner
from arbitrage.v2.core.config import load_config

logger = logging.getLogger(__name__)


SYMBOL_UNIVERSE = [
    "BTC/KRW",
    "ETH/KRW",
    "XRP/KRW",
    "SOL/KRW",
    "ADA/KRW",
    "DOT/KRW",
    "MATIC/KRW",
    "AVAX/KRW",
    "LINK/KRW",
    "UNI/KRW",
    "ATOM/KRW",
    "DOGE/KRW",
]

BINANCE_SYMBOL_MAP = {
    "BTC/KRW": "BTC/USDT",
    "ETH/KRW": "ETH/USDT",
    "XRP/KRW": "XRP/USDT",
    "SOL/KRW": "SOL/USDT",
    "ADA/KRW": "ADA/USDT",
    "DOT/KRW": "DOT/USDT",
    "MATIC/KRW": "MATIC/USDT",
    "AVAX/KRW": "AVAX/USDT",
    "LINK/KRW": "LINK/USDT",
    "UNI/KRW": "UNI/USDT",
    "ATOM/KRW": "ATOM/USDT",
    "DOGE/KRW": "DOGE/USDT",
}


def record_symbol(
    symbol: str,
    output_dir: Path,
    duration_seconds: int,
    polling_interval: float = 1.0,
) -> Dict[str, Any]:
    """
    단일 심볼 Recording
    
    Args:
        symbol: Upbit 심볼 (예: BTC/KRW)
        output_dir: 출력 디렉토리
        duration_seconds: 기록 시간 (초)
        polling_interval: 폴링 주기 (초)
    
    Returns:
        Recording 결과 딕셔너리
    """
    symbol_safe = symbol.replace("/", "_")
    symbol_dir = output_dir / symbol_safe
    symbol_dir.mkdir(parents=True, exist_ok=True)
    
    market_file = symbol_dir / "market.ndjson"
    recorder = MarketRecorder(output_path=market_file)
    
    upbit = UpbitRestProvider()
    binance = BinanceRestProvider(market_type="futures")
    binance_symbol = BINANCE_SYMBOL_MAP.get(symbol)
    
    if not binance_symbol:
        logger.warning(f"[D205-15] No Binance mapping for {symbol}, skipping")
        return {"symbol": symbol, "status": "skipped", "reason": "no_binance_mapping"}
    
    logger.info(f"[D205-15] Recording {symbol} → {binance_symbol} for {duration_seconds}s")
    
    start_time = time.time()
    tick_count = 0
    error_count = 0
    
    while time.time() - start_time < duration_seconds:
        try:
            upbit_ticker = upbit.get_ticker(symbol)
            binance_ticker = binance.get_ticker(binance_symbol)
            
            if upbit_ticker and binance_ticker:
                tick = MarketTick(
                    timestamp=datetime.now(),
                    upbit_bid=upbit_ticker.bid,
                    upbit_ask=upbit_ticker.ask,
                    upbit_last=upbit_ticker.last,
                    upbit_volume=upbit_ticker.volume,
                    binance_bid=binance_ticker.bid,
                    binance_ask=binance_ticker.ask,
                    binance_last=binance_ticker.last,
                    binance_volume=binance_ticker.volume,
                )
                
                recorder.record_tick(tick)
                tick_count += 1
            else:
                error_count += 1
                logger.warning(f"[D205-15] Failed to fetch ticker for {symbol}")
        
        except Exception as e:
            error_count += 1
            logger.error(f"[D205-15] Error recording {symbol}: {e}")
        
        time.sleep(polling_interval)
    
    elapsed = time.time() - start_time
    recorder.save_manifest(symbols=[symbol], duration_sec=elapsed)
    recorder.close()
    
    logger.info(f"[D205-15] Recorded {symbol}: {tick_count} ticks, {error_count} errors")
    
    return {
        "symbol": symbol,
        "binance_symbol": binance_symbol,
        "status": "completed",
        "tick_count": tick_count,
        "error_count": error_count,
        "duration_seconds": elapsed,
        "market_file": str(market_file.relative_to(output_dir.parent)),
    }


def calculate_symbol_metrics(market_file: Path, symbol: str) -> Dict[str, Any]:
    """
    심볼별 메트릭 계산
    
    Args:
        market_file: market.ndjson 파일 경로
        symbol: 심볼 이름
    
    Returns:
        메트릭 딕셔너리
    """
    if not market_file.exists():
        return {"symbol": symbol, "status": "no_data"}
    
    ticks = []
    with open(market_file, "r", encoding="utf-8") as f:
        for line in f:
            tick_dict = json.loads(line)
            ticks.append(tick_dict)
    
    if not ticks:
        return {"symbol": symbol, "status": "empty"}
    
    spreads = []
    raw_edges = []
    net_edges = []
    
    upbit_fee_bps = 5.0
    binance_fee_bps = 1.0
    total_fee_bps = upbit_fee_bps + binance_fee_bps
    slippage_bps = 8.0
    fx_conversion_bps = 2.0
    total_cost_bps = total_fee_bps + slippage_bps + fx_conversion_bps
    
    for tick in ticks:
        upbit_mid = (tick["upbit_bid"] + tick["upbit_ask"]) / 2.0
        binance_mid = (tick["binance_bid"] + tick["binance_ask"]) / 2.0
        
        spread_abs = abs(upbit_mid - binance_mid)
        spread_bps = (spread_abs / upbit_mid) * 10000 if upbit_mid > 0 else 0
        
        raw_edge_bps = spread_bps - total_fee_bps
        net_edge_bps = raw_edge_bps - slippage_bps - fx_conversion_bps
        
        spreads.append(spread_bps)
        raw_edges.append(raw_edge_bps)
        net_edges.append(net_edge_bps)
    
    positive_count = sum(1 for edge in net_edges if edge > 0)
    positive_rate = positive_count / len(net_edges) if net_edges else 0.0
    
    return {
        "symbol": symbol,
        "status": "calculated",
        "tick_count": len(ticks),
        "metrics": {
            "mean_spread_bps": round(mean(spreads), 2),
            "median_spread_bps": round(median(spreads), 2),
            "p90_spread_bps": round(np.percentile(spreads, 90), 2),
            "mean_raw_edge_bps": round(mean(raw_edges), 2),
            "mean_net_edge_bps": round(mean(net_edges), 2),
            "positive_rate": round(positive_rate, 4),
        },
        "cost_breakdown": {
            "upbit_fee_bps": upbit_fee_bps,
            "binance_fee_bps": binance_fee_bps,
            "total_fee_bps": total_fee_bps,
            "slippage_bps": slippage_bps,
            "fx_conversion_bps": fx_conversion_bps,
            "total_cost_bps": total_cost_bps,
        }
    }


def main():
    parser = argparse.ArgumentParser(description="D205-15: Multi-Symbol Scan")
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=10,
        help="Recording duration per symbol (minutes, default: 10)",
    )
    parser.add_argument(
        "--topk",
        type=int,
        default=3,
        help="Number of top symbols to autotune (default: 3)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/v2/config.yml"),
        help="Config file path (default: config/v2/config.yml)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output evidence directory (default: auto-generated)",
    )
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    output_dir = args.output_dir or Path(f"logs/evidence/d205_15_multisymbol_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    duration_seconds = args.duration_minutes * 60
    
    logger.info("[D205-15] ===== MULTI-SYMBOL SCAN START =====")
    logger.info(f"[D205-15] Symbols: {len(SYMBOL_UNIVERSE)}")
    logger.info(f"[D205-15] Duration: {args.duration_minutes} minutes/symbol")
    logger.info(f"[D205-15] TopK: {args.topk}")
    logger.info(f"[D205-15] Output: {output_dir}")
    
    # Phase 1: Recording
    logger.info("[D205-15] Phase 1: Multi-Symbol Recording")
    recording_results = []
    
    for symbol in SYMBOL_UNIVERSE:
        result = record_symbol(
            symbol=symbol,
            output_dir=output_dir,
            duration_seconds=duration_seconds,
        )
        recording_results.append(result)
    
    # Phase 2: Scan Summary
    logger.info("[D205-15] Phase 2: Scan Summary Generation")
    symbol_metrics = []
    
    for rec_result in recording_results:
        if rec_result["status"] != "completed":
            continue
        
        symbol = rec_result["symbol"]
        symbol_safe = symbol.replace("/", "_")
        market_file = output_dir / symbol_safe / "market.ndjson"
        
        metrics = calculate_symbol_metrics(market_file, symbol)
        if metrics["status"] == "calculated":
            symbol_metrics.append(metrics)
    
    symbol_metrics_sorted = sorted(
        symbol_metrics,
        key=lambda x: x["metrics"]["mean_spread_bps"],
        reverse=True
    )
    
    ranking = [
        {
            "rank": i + 1,
            "symbol": m["symbol"],
            "score": m["metrics"]["mean_spread_bps"],
        }
        for i, m in enumerate(symbol_metrics_sorted)
    ]
    
    topk_symbols = [r["symbol"] for r in ranking[:args.topk]]
    
    scan_summary = {
        "scan_id": output_dir.name,
        "timestamp": datetime.now().isoformat(),
        "duration_minutes": args.duration_minutes,
        "symbols": symbol_metrics,
        "ranking": ranking,
        "topk_selection": {
            "topk": args.topk,
            "selected": topk_symbols,
            "selection_criteria": "mean_spread_bps descending",
        }
    }
    
    scan_summary_file = output_dir / "scan_summary.json"
    with open(scan_summary_file, "w", encoding="utf-8") as f:
        json.dump(scan_summary, f, indent=2, ensure_ascii=False)
    
    logger.info(f"[D205-15] Scan summary saved: {scan_summary_file}")
    logger.info(f"[D205-15] TopK selected: {topk_symbols}")
    
    # Phase 3: TopK AutoTune
    logger.info("[D205-15] Phase 3: TopK AutoTune")
    config = load_config(args.config)
    
    autotune_results = []
    for symbol in topk_symbols:
        symbol_safe = symbol.replace("/", "_")
        input_path = output_dir / symbol_safe / "market.ndjson"
        autotune_dir = output_dir / symbol_safe / "autotune"
        
        logger.info(f"[D205-15] AutoTuning {symbol}...")
        
        try:
            tuner = AutoTuner(
                config=config,
                input_path=input_path,
                output_dir=autotune_dir,
            )
            
            result = tuner.run()
            autotune_results.append({
                "symbol": symbol,
                "status": "completed",
                "output_dir": str(autotune_dir.relative_to(output_dir)),
                "leaderboard_entries": len(result.get("leaderboard", [])),
            })
            
            logger.info(f"[D205-15] AutoTune {symbol} completed: {len(result.get('leaderboard', []))} entries")
        
        except Exception as e:
            logger.error(f"[D205-15] AutoTune {symbol} failed: {e}")
            autotune_results.append({
                "symbol": symbol,
                "status": "failed",
                "error": str(e),
            })
    
    # Phase 4: Evidence Packaging
    logger.info("[D205-15] Phase 4: Evidence Packaging")
    
    cost_breakdown = {
        "summary": {
            "total_symbols": len(symbol_metrics),
            "profitable_symbols": sum(1 for m in symbol_metrics if m["metrics"]["positive_rate"] > 0),
            "avg_spread_bps": round(mean([m["metrics"]["mean_spread_bps"] for m in symbol_metrics]), 2),
            "avg_net_edge_bps": round(mean([m["metrics"]["mean_net_edge_bps"] for m in symbol_metrics]), 2),
        },
        "cost_components": symbol_metrics[0]["cost_breakdown"] if symbol_metrics else {},
        "break_even_analysis": {
            "min_spread_required_bps": 16.0,
            "symbols_above_breakeven": sum(1 for m in symbol_metrics if m["metrics"]["mean_spread_bps"] >= 16.0),
            "symbols_below_breakeven": sum(1 for m in symbol_metrics if m["metrics"]["mean_spread_bps"] < 16.0),
        }
    }
    
    cost_breakdown_file = output_dir / "cost_breakdown.json"
    with open(cost_breakdown_file, "w", encoding="utf-8") as f:
        json.dump(cost_breakdown, f, indent=2, ensure_ascii=False)
    
    logger.info(f"[D205-15] Cost breakdown saved: {cost_breakdown_file}")
    
    # Final Report
    final_report = output_dir / "FINAL_REPORT.md"
    with open(final_report, "w", encoding="utf-8") as f:
        f.write(f"# D205-15: Multi-Symbol Scan Final Report\n\n")
        f.write(f"**Date:** {datetime.now().isoformat()}\n")
        f.write(f"**Output:** {output_dir}\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- Total Symbols: {len(symbol_metrics)}\n")
        f.write(f"- TopK Selected: {args.topk}\n")
        f.write(f"- Recording Duration: {args.duration_minutes} minutes/symbol\n\n")
        f.write(f"## TopK Symbols\n\n")
        for r in ranking[:args.topk]:
            f.write(f"{r['rank']}. {r['symbol']} (spread: {r['score']} bps)\n")
        f.write(f"\n## AutoTune Results\n\n")
        for ar in autotune_results:
            f.write(f"- {ar['symbol']}: {ar['status']}\n")
        f.write(f"\n## Evidence Files\n\n")
        f.write(f"- `scan_summary.json`\n")
        f.write(f"- `cost_breakdown.json`\n")
        f.write(f"- TopK autotune results in `<SYMBOL>/autotune/`\n")
    
    logger.info(f"[D205-15] Final report saved: {final_report}")
    logger.info("[D205-15] ===== MULTI-SYMBOL SCAN COMPLETE =====")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
