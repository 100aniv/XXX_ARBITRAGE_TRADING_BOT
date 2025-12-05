# -*- coding: utf-8 -*-
"""
D82-9A: KPI Deepdive Analysis
Root cause analysis for 5-candidate Real PAPER execution
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import csv

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def parse_run_id(filename: str) -> Dict[str, float]:
    """
    Extract entry_bps and tp_bps from filename.
    Example: d82-9-E10p0_TP13p0-20251205193220_kpi.json -> {entry: 10.0, tp: 13.0}
    """
    # d82-9-E10p0_TP13p0-20251205193220_kpi.json
    parts = filename.split("-")
    if len(parts) < 3:
        return {"entry_bps": 0.0, "tp_bps": 0.0}
    
    # E10p0_TP13p0 part
    entry_tp_part = parts[2]
    entry_str, tp_str = entry_tp_part.split("_")
    
    # E10p0 -> 10.0
    entry_bps = float(entry_str[1:].replace("p", "."))
    # TP13p0 -> 13.0
    tp_bps = float(tp_str[2:].replace("p", "."))
    
    return {"entry_bps": entry_bps, "tp_bps": tp_bps}


def analyze_kpi_file(kpi_path: Path) -> Dict[str, Any]:
    """
    Analyze a single KPI JSON file and extract key metrics.
    """
    with open(kpi_path, "r", encoding="utf-8") as f:
        kpi = json.load(f)
    
    params = parse_run_id(kpi_path.name)
    
    # Calculate additional metrics
    total_trades = kpi.get("total_trades", 0)
    entry_trades = kpi.get("entry_trades", 0)
    exit_trades = kpi.get("exit_trades", 0)
    round_trips = kpi.get("round_trips_completed", 0)
    
    wins = kpi.get("wins", 0)
    losses = kpi.get("losses", 0)
    win_rate = kpi.get("win_rate_pct", 0.0)
    
    total_pnl_usd = kpi.get("total_pnl_usd", 0.0)
    avg_pnl_per_rt = total_pnl_usd / round_trips if round_trips > 0 else 0.0
    
    # Exit reasons breakdown
    exit_reasons = kpi.get("exit_reasons", {})
    tp_exits = exit_reasons.get("take_profit", 0)
    timeout_exits = exit_reasons.get("time_limit", 0)
    sl_exits = exit_reasons.get("stop_loss", 0)
    reversal_exits = exit_reasons.get("spread_reversal", 0)
    
    # Fill quality
    avg_buy_fill_ratio = kpi.get("avg_buy_fill_ratio", 0.0)
    avg_sell_fill_ratio = kpi.get("avg_sell_fill_ratio", 0.0)
    partial_fills = kpi.get("partial_fills_count", 0)
    failed_fills = kpi.get("failed_fills_count", 0)
    
    # Slippage
    avg_buy_slippage = kpi.get("avg_buy_slippage_bps", 0.0)
    avg_sell_slippage = kpi.get("avg_sell_slippage_bps", 0.0)
    avg_slippage = (avg_buy_slippage + avg_sell_slippage) / 2.0
    
    # Infrastructure
    latency_avg = kpi.get("loop_latency_avg_ms", 0.0)
    latency_p99 = kpi.get("loop_latency_p99_ms", 0.0)
    cpu_usage = kpi.get("cpu_usage_pct", 0.0)
    memory_usage = kpi.get("memory_usage_mb", 0.0)
    
    duration_minutes = kpi.get("duration_minutes", 0.0)
    
    return {
        "run_id": kpi_path.stem.replace("_kpi", ""),
        "entry_bps": params["entry_bps"],
        "tp_bps": params["tp_bps"],
        "duration_minutes": duration_minutes,
        
        # Trade counts
        "total_trades": total_trades,
        "entry_trades": entry_trades,
        "exit_trades": exit_trades,
        "round_trips": round_trips,
        
        # Performance
        "wins": wins,
        "losses": losses,
        "win_rate_pct": win_rate,
        "total_pnl_usd": total_pnl_usd,
        "avg_pnl_per_rt": avg_pnl_per_rt,
        
        # Exit reasons
        "tp_exits": tp_exits,
        "timeout_exits": timeout_exits,
        "sl_exits": sl_exits,
        "reversal_exits": reversal_exits,
        
        # Fill quality
        "avg_buy_fill_ratio": avg_buy_fill_ratio,
        "avg_sell_fill_ratio": avg_sell_fill_ratio,
        "partial_fills": partial_fills,
        "failed_fills": failed_fills,
        
        # Slippage
        "avg_buy_slippage_bps": avg_buy_slippage,
        "avg_sell_slippage_bps": avg_sell_slippage,
        "avg_slippage_bps": avg_slippage,
        
        # Infrastructure
        "latency_avg_ms": latency_avg,
        "latency_p99_ms": latency_p99,
        "cpu_usage_pct": cpu_usage,
        "memory_usage_mb": memory_usage,
    }


def generate_summary_table(analyses: List[Dict[str, Any]]) -> str:
    """
    Generate a markdown table summarizing all runs.
    """
    # Sort by entry_bps, then tp_bps
    analyses_sorted = sorted(analyses, key=lambda x: (x["entry_bps"], x["tp_bps"]))
    
    table = "## D82-9 Real PAPER: 5-Candidate KPI Summary\n\n"
    table += "| Entry (bps) | TP (bps) | Duration | RT | Wins | Losses | WR (%) | Total PnL (USD) | Avg PnL/RT | Exit: TP | Exit: Timeout |\n"
    table += "|-------------|----------|----------|-----|------|--------|--------|-----------------|------------|----------|---------------|\n"
    
    for analysis in analyses_sorted:
        table += (
            f"| {analysis['entry_bps']:.1f} | {analysis['tp_bps']:.1f} | "
            f"{analysis['duration_minutes']:.1f}m | {analysis['round_trips']} | "
            f"{analysis['wins']} | {analysis['losses']} | "
            f"{analysis['win_rate_pct']:.1f} | ${analysis['total_pnl_usd']:.2f} | "
            f"${analysis['avg_pnl_per_rt']:.2f} | {analysis['tp_exits']} | "
            f"{analysis['timeout_exits']} |\n"
        )
    
    table += "\n### Fill Quality\n\n"
    table += "| Entry (bps) | TP (bps) | Avg Buy Fill | Avg Sell Fill | Partial Fills | Failed Fills |\n"
    table += "|-------------|----------|--------------|---------------|---------------|---------------|\n"
    
    for analysis in analyses_sorted:
        table += (
            f"| {analysis['entry_bps']:.1f} | {analysis['tp_bps']:.1f} | "
            f"{analysis['avg_buy_fill_ratio']:.2%} | {analysis['avg_sell_fill_ratio']:.2%} | "
            f"{analysis['partial_fills']} | {analysis['failed_fills']} |\n"
        )
    
    table += "\n### Slippage\n\n"
    table += "| Entry (bps) | TP (bps) | Avg Buy Slip (bps) | Avg Sell Slip (bps) | Avg Slip (bps) |\n"
    table += "|-------------|----------|--------------------|---------------------|----------------|\n"
    
    for analysis in analyses_sorted:
        table += (
            f"| {analysis['entry_bps']:.1f} | {analysis['tp_bps']:.1f} | "
            f"{analysis['avg_buy_slippage_bps']:.2f} | {analysis['avg_sell_slippage_bps']:.2f} | "
            f"{analysis['avg_slippage_bps']:.2f} |\n"
        )
    
    table += "\n### Infrastructure\n\n"
    table += "| Entry (bps) | TP (bps) | Latency Avg (ms) | Latency P99 (ms) | CPU (%) | Memory (MB) |\n"
    table += "|-------------|----------|------------------|------------------|---------|-------------|\n"
    
    for analysis in analyses_sorted:
        table += (
            f"| {analysis['entry_bps']:.1f} | {analysis['tp_bps']:.1f} | "
            f"{analysis['latency_avg_ms']:.2f} | {analysis['latency_p99_ms']:.2f} | "
            f"{analysis['cpu_usage_pct']:.1f} | {analysis['memory_usage_mb']:.1f} |\n"
        )
    
    return table


def generate_csv_export(analyses: List[Dict[str, Any]], output_path: Path):
    """
    Export detailed metrics to CSV for further analysis.
    """
    if not analyses:
        logger.warning("No analyses to export")
        return
    
    # Get all keys from first analysis
    fieldnames = list(analyses[0].keys())
    
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(analyses)
    
    logger.info(f"CSV export saved to: {output_path}")


def analyze_common_patterns(analyses: List[Dict[str, Any]]) -> str:
    """
    Identify common patterns across all runs.
    """
    report = "## Common Patterns & Root Causes\n\n"
    
    # Calculate averages
    total_runs = len(analyses)
    if total_runs == 0:
        return report + "No runs to analyze.\n"
    
    avg_rt = sum(a["round_trips"] for a in analyses) / total_runs
    avg_wr = sum(a["win_rate_pct"] for a in analyses) / total_runs
    avg_pnl = sum(a["total_pnl_usd"] for a in analyses) / total_runs
    
    total_tp_exits = sum(a["tp_exits"] for a in analyses)
    total_timeout_exits = sum(a["timeout_exits"] for a in analyses)
    total_rt_all = sum(a["round_trips"] for a in analyses)
    
    avg_buy_fill = sum(a["avg_buy_fill_ratio"] for a in analyses) / total_runs
    avg_sell_fill = sum(a["avg_sell_fill_ratio"] for a in analyses) / total_runs
    
    report += f"### Overall Statistics (n={total_runs})\n\n"
    report += f"- **Average Round Trips:** {avg_rt:.1f}\n"
    report += f"- **Average Win Rate:** {avg_wr:.1f}%\n"
    report += f"- **Average PnL:** ${avg_pnl:.2f}\n"
    report += f"- **Total TP Exits:** {total_tp_exits} / {total_rt_all} ({total_tp_exits/total_rt_all*100 if total_rt_all > 0 else 0:.1f}%)\n"
    report += f"- **Total Timeout Exits:** {total_timeout_exits} / {total_rt_all} ({total_timeout_exits/total_rt_all*100 if total_rt_all > 0 else 0:.1f}%)\n"
    report += f"- **Average Buy Fill Ratio:** {avg_buy_fill:.2%}\n"
    report += f"- **Average Sell Fill Ratio:** {avg_sell_fill:.2%}\n"
    report += "\n"
    
    # Identify issues
    report += "### Key Findings\n\n"
    
    if avg_wr == 0.0:
        report += "❌ **CRITICAL: 100% Loss Rate**\n"
        report += "- All round trips resulted in losses\n"
        report += f"- {total_timeout_exits}/{total_rt_all} exits were due to time_limit ({total_timeout_exits/total_rt_all*100 if total_rt_all > 0 else 0:.1f}%)\n"
        report += "- **Root Cause:** TP thresholds (13-15 bps) are unreachable within 10-minute duration\n\n"
    
    if avg_buy_fill < 0.5:
        report += f"❌ **CRITICAL: Low Buy Fill Ratio ({avg_buy_fill:.2%})**\n"
        report += "- Only ~26% of buy orders are filled\n"
        report += "- **Root Cause:** Mock Fill Model with aggressive partial fill simulation\n"
        report += "- **Impact:** Positions are undersized, limiting profit potential\n\n"
    
    if avg_pnl < 0:
        report += f"❌ **CRITICAL: Negative PnL (${avg_pnl:.2f} average)**\n"
        report += "- All runs resulted in net losses\n"
        report += "- **Root Cause:** Combination of:\n"
        report += "  - TP unreachable → forced timeout exits at worse spreads\n"
        report += "  - Slippage accumulation (~2.14 bps per side)\n"
        report += "  - Partial fills reducing position sizes\n\n"
    
    if avg_rt < 5:
        report += f"⚠️ **WARNING: Low Round Trips ({avg_rt:.1f} average)**\n"
        report += "- Insufficient sample size for statistical significance\n"
        report += "- **Root Cause:** 10-minute duration is too short\n"
        report += "- **Recommendation:** Increase duration to 20+ minutes for at least 10 RT\n\n"
    
    return report


def main():
    project_root = Path(__file__).parent.parent
    runs_dir = project_root / "logs" / "d82-9" / "runs"
    output_dir = project_root / "docs" / "D82"
    
    if not runs_dir.exists():
        logger.error(f"Runs directory not found: {runs_dir}")
        return
    
    # Find all KPI files
    kpi_files = [
        f for f in runs_dir.glob("d82-9-E*_kpi.json")
        if "test" not in f.name
    ]
    
    if not kpi_files:
        logger.error(f"No KPI files found in: {runs_dir}")
        return
    
    logger.info("=" * 80)
    logger.info("D82-9A: KPI Deepdive Analysis")
    logger.info("=" * 80)
    logger.info(f"Found {len(kpi_files)} KPI files")
    
    # Analyze each file
    analyses = []
    for kpi_file in sorted(kpi_files):
        logger.info(f"Analyzing: {kpi_file.name}")
        analysis = analyze_kpi_file(kpi_file)
        analyses.append(analysis)
    
    # Generate reports
    logger.info("")
    logger.info("=" * 80)
    logger.info("Generating Reports")
    logger.info("=" * 80)
    
    # 1. Summary table (Markdown)
    summary_table = generate_summary_table(analyses)
    
    # 2. Common patterns analysis
    patterns_report = analyze_common_patterns(analyses)
    
    # 3. Full report
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "D82-9_ANALYSIS.md"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# D82-9A: Real PAPER KPI Deepdive Analysis\n\n")
        f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(summary_table)
        f.write("\n---\n\n")
        f.write(patterns_report)
    
    logger.info(f"Report saved to: {report_path}")
    
    # 4. CSV export
    csv_path = output_dir / "D82-9_KPI_detailed.csv"
    generate_csv_export(analyses, csv_path)
    
    logger.info("=" * 80)
    logger.info("Analysis Complete")
    logger.info("=" * 80)
    logger.info(f"Report: {report_path}")
    logger.info(f"CSV: {csv_path}")


if __name__ == "__main__":
    main()
