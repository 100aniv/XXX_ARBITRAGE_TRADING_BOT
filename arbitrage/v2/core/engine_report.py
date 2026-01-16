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


def compute_config_fingerprint(config: Any) -> str:
    """
    Compute config fingerprint (SHA256)
    
    D206-3 AC-6: Use EngineConfig._compute_config_fingerprint() for canonical fingerprint.
    If config has _config_raw_dict (set by from_config_file), use that.
    Otherwise, fallback to config.__dict__ (legacy).
    """
    try:
        # D206-3: Prefer raw config dict (canonical, from config.yml)
        if hasattr(config, '_config_raw_dict'):
            from arbitrage.v2.core.engine import EngineConfig
            fingerprint = EngineConfig._compute_config_fingerprint(config._config_raw_dict)
            return f"sha256:{fingerprint[:16]}"
        
        # Legacy fallback
        config_str = str(config.__dict__)
        return f"sha256:{hashlib.sha256(config_str.encode()).hexdigest()[:16]}"
    except Exception as e:
        logger.warning(f"Failed to compute config fingerprint: {e}")
        return "sha256:unknown"


def generate_engine_report(
    run_id: str,
    config: Any,
    kpi: Any,
    warning_counts: Dict[str, int],
    wallclock_duration: float,
    expected_duration: float,
    db_counts: Optional[Dict[str, int]],
    exit_code: int
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
    config_fingerprint = compute_config_fingerprint(config)
    
    # Exchanges/Symbols
    exchanges = getattr(config, 'exchanges', ['upbit', 'binance'])
    symbols = getattr(config, 'symbols', [])
    if not symbols and hasattr(kpi, 'symbols_count'):
        symbols = [f"TOP{kpi.symbols_count}"]
    
    # Wallclock drift
    wallclock_drift_pct = 0.0
    if expected_duration > 0:
        wallclock_drift_pct = abs(wallclock_duration - expected_duration) / expected_duration * 100.0
    
    # Heartbeat summary
    max_gap_sec = getattr(kpi, 'max_heartbeat_gap_sec', 0)
    
    # DB integrity
    inserts_ok = db_counts.get('total_inserts', 0) if db_counts else kpi.db_inserts_ok
    inserts_failed = db_counts.get('failed_inserts', 0) if db_counts else kpi.db_inserts_failed
    expected_inserts = kpi.closed_trades * 3  # order + fill + trade
    
    # Status
    status = "PASS" if exit_code == 0 else "FAIL"
    
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
            "net_pnl": round(kpi.net_pnl, 2),
            "fees": round(kpi.fees, 2)
        },
        
        "cost_summary": {
            "fee_total": round(kpi.fees, 2),
            "slippage_total": 0.0,  # V2에서 slippage 미구현
            "exec_cost_total": round(kpi.fees, 2)
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
            "closed_trades": kpi.closed_trades
        },
        
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
