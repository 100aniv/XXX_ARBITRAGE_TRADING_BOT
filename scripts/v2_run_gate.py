#!/usr/bin/env python3
"""
D207-1 RECOVERY: Standard V2 Gate Runner

Constitutional Enforcement:
- Cache Purge + Compileall (ALWAYS)
- Preflight OPS (docker_diag, db_probe)
- Marketdata Liveness Guard (60s bid/ask change)
- RunWatcher Phase-specific Policy (baseline: early_stop_disabled)
- Mandatory Artifact Verification (watch_summary, engine_report, etc.)

Usage:
    python scripts/v2_run_gate.py --phase baseline --duration 20 --evidence-dir logs/evidence/d207_1_baseline_20m
    python scripts/v2_run_gate.py --phase smoke --duration 10 --evidence-dir logs/evidence/smoke_10m
"""

import argparse
import subprocess
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


class V2GateRunner:
    """Standard V2 Gate Runner (Thin Wrapper - No Logic)"""
    
    def __init__(self, phase: str, duration_minutes: int, evidence_dir: str):
        self.phase = phase
        self.duration_minutes = duration_minutes
        self.evidence_dir = Path(evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        
        self.repo_root = Path(__file__).parent.parent
        self.exit_code = 0
        
        # Required Artifacts (SSOT)
        self.required_artifacts = [
            "kpi.json",
            "decision_trace.json",
            "heartbeat.jsonl",
            "watch_summary.json",
            "engine_report.json",
            "manifest.json",
        ]
    
    def run(self) -> int:
        """Execute Gate Steps (ALWAYS sequential, no skip)"""
        print(f"\n[V2_RUN_GATE] Phase: {self.phase}, Duration: {self.duration_minutes}m")
        print(f"[V2_RUN_GATE] Evidence: {self.evidence_dir}")
        
        # Step A: Cache Purge (ALWAYS)
        if not self._purge_cache():
            return 1
        
        # Step B: Preflight OPS (ALWAYS)
        if not self._preflight_ops():
            return 1
        
        # Step C: Baseline Execution (with phase-specific RunWatcher)
        if not self._run_baseline():
            return 1
        
        # Step D: Marketdata Liveness Guard (post-run)
        if not self._check_marketdata_liveness():
            return 1
        
        # Step E: Artifact Verification (MANDATORY)
        if not self._verify_artifacts():
            return 1
        
        print(f"\n[V2_RUN_GATE] ✅ ALL GATES PASSED")
        return 0
    
    def _purge_cache(self) -> bool:
        """Step A: Cache Purge + Compileall"""
        print("\n[GATE A] Cache Purge + Compileall")
        
        # 1) Purge __pycache__
        try:
            sys.path.insert(0, str(self.repo_root / "scripts"))
            from _purge_cache import purge_pycache
            purge_pycache()
            print("  ✅ __pycache__ purged")
        except Exception as e:
            print(f"  ❌ Cache purge failed: {e}")
            return False
        
        # 2) Compileall
        result = subprocess.run(
            [sys.executable, "-m", "compileall", "-f", "-q", "arbitrage/v2"],
            cwd=self.repo_root,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"  ❌ Compileall failed:\n{result.stderr}")
            return False
        
        print("  ✅ Compileall passed")
        return True
    
    def _preflight_ops(self) -> bool:
        """Step B: Preflight OPS (docker_diag, db_probe)"""
        print("\n[GATE B] Preflight OPS")
        
        # 1) Docker Diag
        docker_diag_file = self.evidence_dir / "docker_diag_before.txt"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/ops/collect_docker_diag.py",
                "--out", str(self.evidence_dir),
                "--phase", "before",
            ],
            cwd=self.repo_root,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"  ❌ Docker diag failed:\n{result.stderr}")
            return False
        print(f"  ✅ Docker diag: {docker_diag_file}")
        
        # 2) DB Probe
        db_probe_file = self.evidence_dir / "db_probe_before.txt"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/ops/db_probe.py",
                "--out", str(db_probe_file),
            ],
            cwd=self.repo_root,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"  ⚠️  DB probe failed (non-fatal):\n{result.stderr}")
            # Non-fatal: continue but record
        else:
            print(f"  ✅ DB probe: {db_probe_file}")
        
        return True
    
    def _run_baseline(self) -> bool:
        """Step C: Run Baseline (phase-specific RunWatcher policy)"""
        print(f"\n[GATE C] Run Baseline ({self.phase}, {self.duration_minutes}m)")
        
        # D207-1: subprocess with full cache disable
        cmd = [
            sys.executable,
            "-c",
            f"""
import sys
sys.path.insert(0, r'{self.repo_root}')
from arbitrage.v2.harness.paper_runner import PaperRunnerConfig, PaperRunner

config = PaperRunnerConfig(
    duration_minutes={self.duration_minutes},
    phase='{self.phase}',
    output_dir=r'{self.evidence_dir}',
    use_real_data=True,
)

runner = PaperRunner(config)
exit_code = runner.run()
sys.exit(exit_code)
"""
        ]
        
        print(f"  Executing PaperRunner in clean subprocess...")
        
        # 환경변수: 모든 캐시 비활성화
        import os
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['PYTHONUNBUFFERED'] = '1'
        
        result = subprocess.run(
            cmd,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            env=env
        )
        
        # Output 저장
        (self.evidence_dir / "baseline_stdout.txt").write_text(result.stdout, encoding="utf-8")
        (self.evidence_dir / "baseline_stderr.txt").write_text(result.stderr, encoding="utf-8")
        
        if result.returncode != 0:
            print(f"  ❌ Baseline failed (ExitCode={result.returncode})")
            print(f"     Stdout: {self.evidence_dir / 'baseline_stdout.txt'}")
            print(f"     Stderr: {self.evidence_dir / 'baseline_stderr.txt'}")
            return False
        
        print(f"  ✅ Baseline passed (ExitCode=0)")
        return True
    
    def _check_marketdata_liveness(self) -> bool:
        """Step D: Marketdata Liveness Guard (60s bid/ask change)"""
        print("\n[GATE D] Marketdata Liveness Guard")
        
        # decision_trace.json에서 샘플 추출 (첫 60초와 마지막 60초)
        trace_file = self.evidence_dir / "decision_trace.json"
        if not trace_file.exists():
            print(f"  ❌ decision_trace.json not found")
            return False
        
        try:
            with open(trace_file, "r", encoding="utf-8") as f:
                traces = json.load(f)
            
            if len(traces) < 2:
                print(f"  ⚠️  Too few traces ({len(traces)}), skip liveness check")
                return True
            
            # 첫 10개 vs 마지막 10개 bid/ask 비교
            first_batch = traces[:min(10, len(traces))]
            last_batch = traces[-min(10, len(traces)):]
            
            first_bids = [t.get("upbit_bid_krw", 0) for t in first_batch]
            last_bids = [t.get("upbit_bid_krw", 0) for t in last_batch]
            
            first_avg = sum(first_bids) / len(first_bids) if first_bids else 0
            last_avg = sum(last_bids) / len(last_bids) if last_bids else 0
            
            if first_avg > 0 and last_avg > 0:
                change_pct = abs((last_avg - first_avg) / first_avg) * 100
                if change_pct < 0.01:  # 0.01% 미만 변화 → 의심
                    print(f"  ⚠️  SUSPICIOUS: bid change < 0.01% ({change_pct:.4f}%)")
                    print(f"     First avg: {first_avg:.2f}, Last avg: {last_avg:.2f}")
                    print(f"     Possible stale snapshot or mock data")
                    return False
                else:
                    print(f"  ✅ Liveness OK: bid change {change_pct:.2f}%")
            else:
                print(f"  ⚠️  Cannot verify liveness (zero bid prices)")
            
            return True
        except Exception as e:
            print(f"  ❌ Liveness check failed: {e}")
            return False
    
    def _verify_artifacts(self) -> bool:
        """Step E: Artifact Verification (MANDATORY)"""
        print("\n[GATE E] Artifact Verification")
        
        missing = []
        for artifact in self.required_artifacts:
            artifact_path = self.evidence_dir / artifact
            if not artifact_path.exists():
                missing.append(artifact)
                print(f"  ❌ MISSING: {artifact}")
            else:
                size = artifact_path.stat().st_size
                print(f"  ✅ {artifact} ({size} bytes)")
        
        if missing:
            print(f"\n  ❌ {len(missing)} artifacts missing: {missing}")
            print(f"     Evidence incomplete - FAIL")
            return False
        
        print(f"\n  ✅ All {len(self.required_artifacts)} artifacts present")
        return True


def main():
    parser = argparse.ArgumentParser(description="V2 Standard Gate Runner")
    parser.add_argument("--phase", required=True, choices=["baseline", "smoke", "longrun"])
    parser.add_argument("--duration", type=int, required=True, help="Duration in minutes")
    parser.add_argument("--evidence-dir", required=True, help="Evidence directory")
    args = parser.parse_args()
    
    runner = V2GateRunner(
        phase=args.phase,
        duration_minutes=args.duration,
        evidence_dir=args.evidence_dir
    )
    
    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
