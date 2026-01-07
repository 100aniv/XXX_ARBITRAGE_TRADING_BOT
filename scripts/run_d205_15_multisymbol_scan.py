#!/usr/bin/env python3
"""
D205-15: Multi-Symbol Profit Candidate Scan (CLI Wrapper)

멀티심볼 스캔 (Upbit Spot × Binance Futures) + TopK AutoTune

Fix-1: FX Normalization (--fx-krw-per-usdt 필수)
Fix-2: bid_size/ask_size 필드 포함 (누락 시 skip)
Fix-3: Config-driven costs (config.yml에서 로드)
Fix-4: TopK 선정 = mean_net_edge_bps + positive_rate

Usage:
    python scripts/run_d205_15_multisymbol_scan.py --fx-krw-per-usdt 1450.0 --duration-minutes 10 --topk 3
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from statistics import mean

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.scan.scanner import MultiSymbolScanner, ScanConfig, SYMBOL_UNIVERSE
from arbitrage.v2.scan.metrics import ScanMetricsCalculator, create_scan_config_from_v2_config
from arbitrage.v2.scan.topk import TopKSelector
from arbitrage.v2.execution_quality.autotune import AutoTuner
from arbitrage.v2.core.config import load_config

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="D205-15: Multi-Symbol Scan (Fix-1~4 Applied)"
    )
    
    # Fix-1: FX Rate (필수 인자)
    parser.add_argument(
        "--fx-krw-per-usdt",
        type=float,
        required=True,
        help="FX rate KRW/USDT (REQUIRED, e.g., 1450.0) - Fix-1",
    )
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
        "--min-positive-rate",
        type=float,
        default=0.0,
        help="Minimum positive_rate filter for TopK (default: 0.0)",
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
    parser.add_argument(
        "--skip-autotune",
        action="store_true",
        help="Skip AutoTune phase (scan summary only)",
    )
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # Fix-1: FX Rate 로깅
    logger.info(f"[D205-15] Fix-1: FX Rate = {args.fx_krw_per_usdt} KRW/USDT")
    
    output_dir = args.output_dir or Path(
        f"logs/evidence/d205_15_multisymbol_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    
    duration_seconds = args.duration_minutes * 60
    
    # Fix-3: Config에서 비용 파라미터 로드
    config = load_config(args.config)
    scan_config = create_scan_config_from_v2_config(config, args.fx_krw_per_usdt)
    
    logger.info("[D205-15] ===== MULTI-SYMBOL SCAN START (Fix-1~4 Applied) =====")
    logger.info(f"[D205-15] Symbols: {len(SYMBOL_UNIVERSE)}")
    logger.info(f"[D205-15] Duration: {args.duration_minutes} minutes/symbol")
    logger.info(f"[D205-15] TopK: {args.topk}")
    logger.info(f"[D205-15] FX Rate: {args.fx_krw_per_usdt} KRW/USDT (Fix-1)")
    logger.info(f"[D205-15] Config: {args.config} (Fix-3)")
    logger.info(f"[D205-15] Selection: mean_net_edge_bps + positive_rate (Fix-4)")
    logger.info(f"[D205-15] Output: {output_dir}")
    
    # Phase 1: Recording (Fix-1, Fix-2 적용)
    logger.info("[D205-15] Phase 1: Multi-Symbol Recording")
    scanner = MultiSymbolScanner(scan_config=scan_config, output_dir=output_dir)
    recording_results = scanner.scan_all(
        symbols=SYMBOL_UNIVERSE,
        duration_seconds=duration_seconds,
    )
    
    # Phase 2: Scan Summary (Fix-3 적용)
    logger.info("[D205-15] Phase 2: Scan Summary Generation")
    metrics_calculator = ScanMetricsCalculator(scan_config=scan_config)
    symbol_metrics = metrics_calculator.calculate_all_metrics(
        output_dir=output_dir,
        recording_results=recording_results,
    )
    
    # Phase 2.5: TopK Selection (Fix-4 적용)
    topk_selector = TopKSelector(
        topk=args.topk,
        min_positive_rate=args.min_positive_rate,
    )
    topk_symbols, ranking = topk_selector.select(symbol_metrics)
    
    scan_summary = topk_selector.create_scan_summary(
        output_dir_name=output_dir.name,
        duration_minutes=args.duration_minutes,
        symbol_metrics=symbol_metrics,
        topk_symbols=topk_symbols,
        ranking=ranking,
    )
    
    scan_summary_file = output_dir / "scan_summary.json"
    with open(scan_summary_file, "w", encoding="utf-8") as f:
        json.dump(scan_summary, f, indent=2, ensure_ascii=False)
    
    logger.info(f"[D205-15] Scan summary saved: {scan_summary_file}")
    logger.info(f"[D205-15] TopK selected (Fix-4): {topk_symbols}")
    
    # Phase 3: TopK AutoTune
    autotune_results = []
    
    if args.skip_autotune:
        logger.info("[D205-15] Phase 3: AutoTune SKIPPED (--skip-autotune)")
    else:
        logger.info("[D205-15] Phase 3: TopK AutoTune")
        
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
                
                logger.info(
                    f"[D205-15] AutoTune {symbol} completed: "
                    f"{len(result.get('leaderboard', []))} entries"
                )
            
            except Exception as e:
                logger.error(f"[D205-15] AutoTune {symbol} failed: {e}")
                autotune_results.append({
                    "symbol": symbol,
                    "status": "failed",
                    "error": str(e),
                })
    
    # Phase 4: Evidence Packaging
    logger.info("[D205-15] Phase 4: Evidence Packaging")
    
    # Filter valid metrics for summary
    valid_metrics = [m for m in symbol_metrics if m.get("status") == "calculated"]
    
    if valid_metrics:
        avg_spread = mean([m["metrics"]["mean_spread_bps"] for m in valid_metrics])
        avg_net_edge = mean([m["metrics"]["mean_net_edge_bps"] for m in valid_metrics])
        avg_positive_rate = mean([m["metrics"]["positive_rate"] for m in valid_metrics])
        profitable_count = sum(1 for m in valid_metrics if m["metrics"]["positive_rate"] > 0)
    else:
        avg_spread = 0.0
        avg_net_edge = 0.0
        avg_positive_rate = 0.0
        profitable_count = 0
    
    cost_breakdown = {
        "summary": {
            "total_symbols": len(symbol_metrics),
            "valid_symbols": len(valid_metrics),
            "profitable_symbols": profitable_count,
            "avg_spread_bps": round(avg_spread, 4),
            "avg_net_edge_bps": round(avg_net_edge, 4),
            "avg_positive_rate": round(avg_positive_rate, 4),
        },
        "cost_components": valid_metrics[0]["cost_breakdown"] if valid_metrics else {},
        "fx_info": {
            "fx_krw_per_usdt": args.fx_krw_per_usdt,
            "source": "CLI argument (--fx-krw-per-usdt)",
        },
        "break_even_analysis": {
            "total_cost_bps": scan_config.upbit_fee_bps + scan_config.binance_fee_bps + scan_config.slippage_bps + scan_config.fx_conversion_bps + scan_config.buffer_bps,
            "symbols_above_breakeven": sum(
                1 for m in valid_metrics
                if m["metrics"]["mean_net_edge_bps"] > 0
            ),
            "symbols_below_breakeven": sum(
                1 for m in valid_metrics
                if m["metrics"]["mean_net_edge_bps"] <= 0
            ),
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
        f.write(f"## Fixes Applied\n\n")
        f.write(f"- **Fix-1:** FX Normalization = {args.fx_krw_per_usdt} KRW/USDT\n")
        f.write(f"- **Fix-2:** bid_size/ask_size fields included (skip if missing)\n")
        f.write(f"- **Fix-3:** Config-driven costs from {args.config}\n")
        f.write(f"- **Fix-4:** TopK selection = mean_net_edge_bps + positive_rate\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- Total Symbols: {len(symbol_metrics)}\n")
        f.write(f"- Valid Symbols: {len(valid_metrics)}\n")
        f.write(f"- TopK Selected: {args.topk}\n")
        f.write(f"- Recording Duration: {args.duration_minutes} minutes/symbol\n")
        f.write(f"- Avg Net Edge: {avg_net_edge:.2f} bps\n")
        f.write(f"- Avg Positive Rate: {avg_positive_rate:.2%}\n\n")
        f.write(f"## TopK Symbols (Fix-4: mean_net_edge_bps + positive_rate)\n\n")
        for r in ranking[:args.topk]:
            f.write(
                f"{r['rank']}. {r['symbol']} "
                f"(net_edge: {r['mean_net_edge_bps']:.2f}bps, "
                f"positive_rate: {r['positive_rate']:.2%})\n"
            )
        if autotune_results:
            f.write(f"\n## AutoTune Results\n\n")
            for ar in autotune_results:
                f.write(f"- {ar['symbol']}: {ar['status']}\n")
        f.write(f"\n## Cost Breakdown (Fix-3: Config SSOT)\n\n")
        if valid_metrics:
            cb = valid_metrics[0]["cost_breakdown"]
            f.write(f"- Upbit Fee: {cb['upbit_fee_bps']} bps\n")
            f.write(f"- Binance Fee: {cb['binance_fee_bps']} bps\n")
            f.write(f"- Slippage: {cb['slippage_bps']} bps\n")
            f.write(f"- FX Conversion: {cb['fx_conversion_bps']} bps\n")
            f.write(f"- Buffer: {cb['buffer_bps']} bps\n")
            f.write(f"- **Total Cost:** {cb['total_cost_bps']} bps\n")
        f.write(f"\n## Evidence Files\n\n")
        f.write(f"- `scan_summary.json`\n")
        f.write(f"- `cost_breakdown.json`\n")
        if autotune_results:
            f.write(f"- TopK autotune results in `<SYMBOL>/autotune/`\n")
        f.write(f"\n## Reproduction Command\n\n")
        f.write(f"```bash\n")
        f.write(
            f"python scripts/run_d205_15_multisymbol_scan.py "
            f"--fx-krw-per-usdt {args.fx_krw_per_usdt} "
            f"--duration-minutes {args.duration_minutes} "
            f"--topk {args.topk}\n"
        )
        f.write(f"```\n")
    
    logger.info(f"[D205-15] Final report saved: {final_report}")
    logger.info("[D205-15] ===== MULTI-SYMBOL SCAN COMPLETE (Fix-1~4) =====")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
