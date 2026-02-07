"""
D206-0: Standard Engine Report Generator (Artifact-First)

Purpose:
- Generate engine_report.json (Gate SSOT)
- Atomic flush with fsync
- No Runner dependency (pure artifact)

Author: D206-0 Gate Integrity Restore
Date: 2026-01-16
"""

import hashlib
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def get_git_sha() -> str:
    """Get current git commit SHA"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        return result.stdout.strip()
    except Exception as e:
        logger.warning(f"Failed to get git SHA: {e}")
        return "unknown"


def get_git_branch() -> str:
    """Get current git branch name"""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        return result.stdout.strip() or "unknown"
    except Exception as e:
        logger.warning(f"Failed to get git branch: {e}")
        return "unknown"


def compute_config_fingerprint(config: Any, config_path: Optional[str] = None) -> str:
    """
    Compute config fingerprint (SHA256) - D206-3 AC-6
    
    Strategy:
    1. If config_path provided: Load config.yml → canonical JSON → SHA256
    2. Else: Use config.__dict__ (fallback)
    
    Canonical form: sorted keys, compact JSON (no whitespace)
    
    Args:
        config: EngineConfig or Runner config
        config_path: Path to config.yml (preferred)
    
    Returns:
        SHA256 fingerprint (format: "sha256:<hex>")
    """
    try:
        # Preferred: Load config.yml directly (SSOT)
        if config_path and Path(config_path).exists():
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)
        else:
            # Fallback: Use config.__dict__
            if hasattr(config, '__dict__'):
                config_dict = {k: v for k, v in config.__dict__.items() 
                             if not k.startswith('_') and not callable(v)}
            else:
                config_dict = {}
        
        # Canonical form: sorted keys, compact JSON
        canonical = json.dumps(config_dict, sort_keys=True, separators=(',', ':'))
        fingerprint = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        
        return f"sha256:{fingerprint}"
    except Exception as e:
        logger.info(f"Config fingerprint fallback (non-serializable): {e}")
        return "sha256:unknown"


def generate_engine_report(
    run_id: str,
    config: Any,
    kpi: Any,
    warning_counts: Dict[str, int],
    wallclock_duration: float,
    expected_duration: float,
    db_counts: Optional[Dict[str, int]],
    exit_code: int,
    stop_reason: str = "",
    stop_message: str = ""
) -> Dict[str, Any]:
    """
    Generate standard engine report (D206-0 SSOT)
    
    Args:
        run_id: Run ID
        config: Runner config
        kpi: PaperMetrics instance
        warning_counts: {"warning_count": int, "error_count": int}
        wallclock_duration: Actual wallclock duration (seconds)
        expected_duration: Expected duration (seconds)
        db_counts: DB insert counts
        exit_code: 0 (PASS) or 1 (FAIL)
    
    Returns:
        Engine report dict
    """
    now = datetime.now().astimezone()
    started_at = kpi.start_time if hasattr(kpi, 'start_time') and kpi.start_time else now.isoformat()
    
    # Git SHA
    git_sha = get_git_sha()
    
    # Config fingerprint
    config_path = getattr(config, "config_path", None)
    config_fingerprint = compute_config_fingerprint(config, config_path=config_path)
    
    # Exchanges/Symbols
    exchanges = getattr(config, 'exchanges', ['upbit', 'binance'])
    symbols = getattr(config, 'symbols', [])
    if not symbols and hasattr(kpi, 'symbols_count'):
        symbols = [f"TOP{kpi.symbols_count}"]

    # Run meta (D207-5)
    run_meta = {
        "run_id": run_id,
        "git_sha": git_sha,
        "branch": get_git_branch(),
        "config_path": config_path,
        "symbols": symbols,
        "cli_args": getattr(config, "cli_args", None),
    }
    
    # Wallclock drift
    wallclock_drift_pct = 0.0
    if expected_duration > 0:
        wallclock_drift_pct = abs(wallclock_duration - expected_duration) / expected_duration * 100.0
    
    # Heartbeat summary
    max_gap_sec = getattr(kpi, 'max_heartbeat_gap_sec', 0)
    
    # DB integrity
    inserts_ok = kpi.db_inserts_ok
    inserts_failed = kpi.db_inserts_failed
    if db_counts and isinstance(db_counts, dict):
        if "total_inserts" in db_counts or "failed_inserts" in db_counts:
            inserts_ok = int(db_counts.get("total_inserts", inserts_ok) or 0)
            inserts_failed = int(db_counts.get("failed_inserts", inserts_failed) or 0)
        elif "v2_orders" in db_counts or "v2_fills" in db_counts or "v2_trades" in db_counts:
            v2_orders = int(db_counts.get("v2_orders", 0) or 0)
            v2_fills = int(db_counts.get("v2_fills", 0) or 0)
            v2_trades = int(db_counts.get("v2_trades", 0) or 0)
            inserts_ok = v2_orders + v2_fills + v2_trades
    expected_inserts = kpi.closed_trades * 5  # D207-1-4 AV: 2 orders + 2 fills + 1 trade

    # Redis status
    redis_ok = bool(getattr(kpi, "redis_ok", False))
    
    # Status
    status = "PASS" if exit_code == 0 else "FAIL"
    
    net_pnl_full_value = getattr(kpi, "net_pnl_full", kpi.net_pnl)

    report = {
        "schema_version": "1.0",
        "run_id": run_id,
        "git_sha": git_sha,
        "started_at": started_at,
        "ended_at": now.isoformat(),
        "duration_sec": round(wallclock_duration, 2),
        "mode": getattr(config, 'mode', 'paper'),
        "exchanges": exchanges,
        "symbols": symbols,
        "config_fingerprint": config_fingerprint,
        "run_meta": run_meta,
        
        "gate_validation": {
            "warnings_count": warning_counts.get("warning_count", 0),
            "skips_count": 0,  # pytest SKIP은 별도 gate에서 검증
            "errors_count": warning_counts.get("error_count", 0),
            "exit_code": exit_code
        },
        
        "trades": {
            "count": kpi.closed_trades,
            "winrate": round(kpi.winrate_pct / 100.0, 3),
            "gross_pnl": round(kpi.gross_pnl, 2),
            "net_pnl": round(net_pnl_full_value, 2),
            "net_pnl_full": round(net_pnl_full_value, 2),
            "fees": round(kpi.fees, 2)
        },
        
        "cost_summary": {
            "fee_total": round(kpi.fees, 2),
            "slippage_total": round(getattr(kpi, "slippage_total", 0.0), 2),
            "latency_total_ms": round(getattr(kpi, "latency_total", 0.0), 2),
            "partial_fill_total": round(getattr(kpi, "partial_fill_total", 0.0), 4),
            "reject_total": round(getattr(kpi, "reject_total", 0.0), 4),
            "exec_cost_total": round(getattr(kpi, "exec_cost_total", kpi.fees + getattr(kpi, "slippage_total", 0.0)), 2)
        },
        
        "heartbeat_summary": {
            "wallclock_duration_sec": round(wallclock_duration, 2),
            "expected_duration_sec": round(expected_duration, 2),
            "wallclock_drift_pct": round(wallclock_drift_pct, 2),
            "max_gap_sec": max_gap_sec
        },
        
        "db_integrity": {
            "inserts_ok": inserts_ok,
            "inserts_failed": inserts_failed,
            "expected_inserts": expected_inserts,
            "closed_trades": kpi.closed_trades,
            "enabled": inserts_ok > 0 or inserts_failed > 0,  # D207-1-4: DB 사용 여부 명시
            "reason": "DB mode active" if (inserts_ok > 0 or inserts_failed > 0) else "Paper mode (no DB)"
        },

        "redis": {
            "ok": redis_ok,
        },
        
        # D207-1-5: StopReason Single Truth Chain (SSOT)
        "stop_reason": stop_reason if stop_reason else ("TIME_REACHED" if exit_code == 0 else "ERROR"),
        "stop_message": stop_message,
        
        "status": status
    }
    
    return report


def save_engine_report_atomic(report: Dict[str, Any], output_dir: str, filename: str = "engine_report.json"):
    """
    Save engine report with atomic flush (D206-0 Add-on A)
    
    - Write to temp file
    - fsync
    - Atomic rename
    
    Args:
        report: Engine report dict
        output_dir: Output directory
        filename: Report filename (default: engine_report.json)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    final_path = output_path / filename
    temp_path = output_path / f"{filename}.tmp"
    
    try:
        # Write to temp file
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk
        
        # Atomic rename
        temp_path.replace(final_path)
        
        logger.info(f"[D206-0] Engine report saved (atomic): {final_path}")
        
    except Exception as e:
        logger.error(f"[D206-0] Failed to save engine report: {e}")
        # Cleanup temp file
        if temp_path.exists():
            temp_path.unlink()
        raise
