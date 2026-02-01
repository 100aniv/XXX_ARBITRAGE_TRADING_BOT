"""
D205-10-1: Threshold Sensitivity Sweep (Core)
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from arbitrage.v2.core.runtime_factory import build_break_even_params_from_config_path
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.v2.harness.paper_runner import PaperRunner, PaperRunnerConfig

logger = logging.getLogger(__name__)


def _with_buffer_params(base_params: BreakEvenParams, buffer_bps: float) -> BreakEvenParams:
    return BreakEvenParams(
        fee_model=base_params.fee_model,
        slippage_bps=base_params.slippage_bps,
        latency_bps=base_params.latency_bps,
        buffer_bps=buffer_bps,
    )


def run_single_sweep(
    buffer_bps: float,
    duration_minutes: int,
    use_real_data: bool,
    db_mode: str,
    evidence_base_dir: Path,
    fx_rate: float = 1450.0,
    symbols_top: int = 10,
    config_path: str = "config/v2/config.yml",
) -> Dict:
    """
    단일 buffer_bps 값으로 PaperRunner 실행

    Returns:
        {
            "buffer_bps": float,
            "kpi": dict,
            "evidence_path": str,
            "exit_code": int,
        }
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"d205_10_1_buffer_{int(buffer_bps)}_{timestamp}"
    evidence_dir = evidence_base_dir / run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)

    base_params = build_break_even_params_from_config_path(config_path)
    break_even_params = _with_buffer_params(base_params, buffer_bps)

    config = PaperRunnerConfig(
        duration_minutes=duration_minutes,
        phase="sweep",
        run_id=run_id,
        output_dir=str(evidence_dir),
        symbols_top=symbols_top,
        db_mode=db_mode,
        use_real_data=use_real_data,
        fx_krw_per_usdt=fx_rate,
        break_even_params=break_even_params,
    )

    logger.info(f"[D205-10-1] Sweep {buffer_bps} bps (duration={duration_minutes}m)")

    runner = PaperRunner(config)
    exit_code = runner.run()

    kpi_path = evidence_dir / "kpi_sweep.json"
    if not kpi_path.exists():
        logger.error(f"[D205-10-1] KPI file not found: {kpi_path}")
        return {
            "buffer_bps": buffer_bps,
            "kpi": {},
            "evidence_path": str(evidence_dir),
            "exit_code": exit_code,
            "error": "KPI file not found",
        }

    with open(kpi_path, "r") as f:
        kpi = json.load(f)

    return {
        "buffer_bps": buffer_bps,
        "kpi": kpi,
        "evidence_path": str(evidence_dir),
        "exit_code": exit_code,
    }


def select_best_buffer(sweep_results: List[Dict]) -> Dict:
    """
    Best buffer 선정

    기준:
    1. closed_trades > 0
    2. error_count == 0
    3. net_pnl 최대

    Returns:
        {
            "best_buffer_bps": float,
            "reason": str,
            "candidates": list,
            "rejected": list,
        }
    """
    candidates = []
    rejected = []

    for result in sweep_results:
        buffer_bps = result["buffer_bps"]
        kpi = result.get("kpi", {})

        closed_trades = kpi.get("closed_trades", 0)
        error_count = kpi.get("error_count", 0)
        net_pnl = kpi.get("net_pnl_krw", 0.0)

        if closed_trades <= 0:
            rejected.append({
                "buffer_bps": buffer_bps,
                "reason": f"closed_trades={closed_trades} (expected > 0)",
                "kpi": kpi,
            })
            continue

        if error_count != 0:
            rejected.append({
                "buffer_bps": buffer_bps,
                "reason": f"error_count={error_count} (expected 0)",
                "kpi": kpi,
            })
            continue

        candidates.append({
            "buffer_bps": buffer_bps,
            "closed_trades": closed_trades,
            "error_count": error_count,
            "net_pnl_krw": net_pnl,
            "gross_pnl_krw": kpi.get("gross_pnl_krw", 0.0),
            "total_fees_krw": kpi.get("total_fees_krw", 0.0),
            "winrate_pct": kpi.get("winrate_pct", 0.0),
            "opportunities": kpi.get("opportunities_generated", 0),
            "intents": kpi.get("intents_created", 0),
        })

    if not candidates:
        return {
            "best_buffer_bps": None,
            "reason": "No valid candidates (all failed AC-1 or AC-2)",
            "candidates": [],
            "rejected": rejected,
        }

    best = max(candidates, key=lambda x: x["net_pnl_krw"])

    return {
        "best_buffer_bps": best["buffer_bps"],
        "reason": f"Highest net_pnl_krw={best['net_pnl_krw']:.2f} KRW",
        "candidates": candidates,
        "rejected": rejected,
        "best_candidate": best,
    }


def run_negative_control(
    duration_minutes: int,
    use_real_data: bool,
    db_mode: str,
    evidence_base_dir: Path,
    fx_rate: float = 1450.0,
    symbols_top: int = 10,
    config_path: str = "config/v2/config.yml",
) -> Dict:
    """
    Negative-control run (buffer=999, 매우 큰 값으로 모든 기회 거절 예상)

    Returns:
        {
            "buffer_bps": 999.0,
            "duration_minutes": int,
            "kpi": dict,
            "evidence_dir": str,
            "reject_reasons": dict,
            "passed": bool,
            "reason": str,
        }
    """
    logger.info("[D205-10-1] Running negative-control (buffer=999)")

    result = run_single_sweep(
        buffer_bps=999.0,
        duration_minutes=duration_minutes,
        use_real_data=use_real_data,
        db_mode=db_mode,
        evidence_base_dir=evidence_base_dir,
        fx_rate=fx_rate,
        symbols_top=symbols_top,
        config_path=config_path,
    )

    kpi = result.get("kpi", {})
    reject_reasons = kpi.get("reject_reasons", {})
    profitable_false_count = reject_reasons.get("profitable_false", 0)

    passed = profitable_false_count > 0

    reason = (
        f"profitable_false={profitable_false_count} (expected > 0)"
        if passed
        else f"profitable_false={profitable_false_count} (FAIL: expected > 0, got 0)"
    )

    return {
        "buffer_bps": 999.0,
        "duration_minutes": duration_minutes,
        "kpi": kpi,
        "evidence_dir": result.get("evidence_path", ""),
        "reject_reasons": reject_reasons,
        "passed": passed,
        "reason": reason,
    }


def run_threshold_sweep(
    duration_minutes: int,
    use_real_data: bool,
    db_mode: str,
    fx_rate: float = 1450.0,
    out_evidence_dir: Optional[str] = None,
    buffer_values: Optional[List[float]] = None,
    symbols_top: int = 10,
    config_path: str = "config/v2/config.yml",
) -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if out_evidence_dir:
        evidence_base_dir = Path(out_evidence_dir)
    else:
        evidence_base_dir = Path(f"logs/evidence/d205_10_1_sweep_{timestamp}")
    evidence_base_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[D205-10-1] Starting Threshold Sensitivity Sweep")
    logger.info(f"[D205-10-1] Duration per sweep: {duration_minutes}m")
    logger.info(f"[D205-10-1] Evidence: {evidence_base_dir}")

    values = buffer_values or [0.0, 2.0, 5.0, 8.0, 10.0]
    sweep_results = []

    for buffer_bps in values:
        result = run_single_sweep(
            buffer_bps=buffer_bps,
            duration_minutes=duration_minutes,
            use_real_data=use_real_data,
            db_mode=db_mode,
            evidence_base_dir=evidence_base_dir,
            fx_rate=fx_rate,
            symbols_top=symbols_top,
            config_path=config_path,
        )
        sweep_results.append(result)
        time.sleep(2)

    best_selection = select_best_buffer(sweep_results)

    logger.info("[D205-10-1] Starting negative-control run (buffer=999)")
    negative_control = run_negative_control(
        duration_minutes=1,
        use_real_data=use_real_data,
        db_mode=db_mode,
        evidence_base_dir=evidence_base_dir,
        fx_rate=fx_rate,
        symbols_top=symbols_top,
        config_path=config_path,
    )

    summary = {
        "sweep_timestamp": timestamp,
        "duration_minutes_per_sweep": duration_minutes,
        "buffer_values": values,
        "sweep_results": sweep_results,
        "best_selection": best_selection,
        "negative_control": negative_control,
        "passed": best_selection["best_buffer_bps"] is not None and negative_control["passed"],
    }

    summary_path = evidence_base_dir / "sweep_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"[D205-10-1] Summary saved to {summary_path}")

    if best_selection["best_buffer_bps"] is not None:
        logger.info(f"[D205-10-1] ✅ Best buffer: {best_selection['best_buffer_bps']} bps")
        logger.info(f"[D205-10-1] Reason: {best_selection['reason']}")
    else:
        logger.error(f"[D205-10-1] ❌ No valid candidates: {best_selection['reason']}")

    logger.info(f"[D205-10-1] Negative-control: {'✅ PASS' if negative_control['passed'] else '❌ FAIL'}")

    if summary["passed"]:
        logger.info("[D205-10-1] ✅ Sweep PASS")
        return 0

    logger.error("[D205-10-1] ❌ Sweep FAIL")
    return 1
