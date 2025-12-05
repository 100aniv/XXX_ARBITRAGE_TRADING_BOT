#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-11: Full Validation Pipeline (10m → 20m → 60m)

완전 자동화 파이프라인:
- 환경 자동 정리 및 준비
- Phase 1 (10분) → Phase 2 (20분) → Phase 3 (60분) 자동 실행
- Acceptance Criteria 자동 검증
- 실패 시 즉시 NO-GO 처리 및 문서화
- 성공 시 GO 처리 및 다음 단계 제안

사용자 개입 없이 전체 파이프라인 실행 완료
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Environment Preparation (완전 자동화)
# =============================================================================

def kill_existing_processes():
    """기존 PAPER 관련 프로세스 모두 종료 (validation_pipeline 제외)"""
    logger.info("Killing existing PAPER processes...")
    
    try:
        import psutil
        current_pid = os.getpid()
        killed_count = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Skip self
                if proc.info['pid'] == current_pid:
                    continue
                
                # Check if it's a python process
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    cmdline = proc.info.get('cmdline', [])
                    if not cmdline:
                        continue
                    
                    cmdline_str = ' '.join(str(arg) for arg in cmdline)
                    
                    # Skip validation_pipeline scripts
                    if 'validation_pipeline' in cmdline_str:
                        continue
                    
                    # Only kill smoke_test or paper test scripts
                    if 'smoke_test' in cmdline_str or 'run_d82' in cmdline_str or 'paper_test' in cmdline_str:
                        logger.info(f"Killing process {proc.info['pid']}: {' '.join(cmdline[:3])}")
                        proc.kill()
                        killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if killed_count > 0:
            logger.info(f"Killed {killed_count} PAPER-related processes")
        else:
            logger.info("No PAPER-related processes to kill")
            
    except Exception as e:
        logger.warning(f"Failed to kill processes: {e}")


def check_docker_services():
    """Docker 서비스 상태 확인"""
    logger.info("Checking Docker services...")
    
    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8',
            errors='replace',
        )
        
        if result.returncode != 0:
            logger.error("Docker is not running!")
            return False
        
        # Check required services
        required_services = ["redis", "postgres", "prometheus"]
        output = result.stdout
        if output is None:
            logger.error("Docker ps returned None")
            return False
            
        output_lower = output.lower()
        
        for service in required_services:
            if service not in output_lower:
                logger.error(f"Required service not running: {service}")
                return False
        
        logger.info("All required Docker services are running")
        return True
    
    except Exception as e:
        logger.error(f"Failed to check Docker services: {e}")
        return False


def prepare_environment():
    """환경 준비 (완전 자동화)"""
    logger.info("=" * 80)
    logger.info("Environment Preparation")
    logger.info("=" * 80)
    
    # 1. Kill existing processes
    kill_existing_processes()
    
    # 2. Check Docker services
    if not check_docker_services():
        logger.error("Docker services check failed!")
        sys.exit(1)
    
    # 3. Create output directories
    output_dir = Path("logs/d82-11")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "runs").mkdir(exist_ok=True)
    
    logger.info("Environment preparation complete")
    logger.info("")


# =============================================================================
# Phase Execution
# =============================================================================

def run_phase(
    phase_name: str,
    duration_seconds: int,
    top_n: int,
    candidates_json: Path,
    output_dir: Path,
    dry_run: bool = False,
) -> Tuple[bool, Path]:
    """
    Phase 실행
    
    Returns:
        (success, summary_json_path)
    """
    logger.info("=" * 80)
    logger.info(f"{phase_name} - Duration: {duration_seconds}s, Top-N: {top_n}")
    logger.info("=" * 80)
    
    summary_output = output_dir / f"d82_11_summary_{duration_seconds}.json"
    
    cmd = [
        sys.executable,
        "scripts/run_d82_11_smoke_test.py",
        "--duration-seconds", str(duration_seconds),
        "--top-n", str(top_n),
        "--candidates-json", str(candidates_json),
        "--summary-output", str(summary_output),
    ]
    
    if dry_run:
        cmd.append("--dry-run")
    
    logger.info(f"Command: {' '.join(cmd)}")
    logger.info(f"Executing {phase_name}...")
    
    try:
        # Execute with timeout
        timeout = duration_seconds * top_n + 300  # Buffer for overhead
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        
        if result.returncode != 0:
            logger.error(f"{phase_name} failed with exit code: {result.returncode}")
            logger.error(f"Stderr: {result.stderr[:1000]}")
            return False, summary_output
        
        logger.info(f"{phase_name} completed successfully")
        return True, summary_output
    
    except subprocess.TimeoutExpired:
        logger.error(f"{phase_name} timed out after {timeout}s")
        return False, summary_output
    
    except Exception as e:
        logger.exception(f"{phase_name} exception: {e}")
        return False, summary_output


# =============================================================================
# Acceptance Criteria Evaluation
# =============================================================================

def evaluate_phase1(summary: Dict[str, Any]) -> Tuple[bool, List[Dict], str]:
    """
    Phase 1 Acceptance Criteria 검증
    
    Criteria:
    - RT >= 5 (각 후보)
    - total_pnl_usd >= 0 (최소 1개)
    - win_rate_pct > 0 (최소 1개)
    - exit_reasons.take_profit > 0 (최소 1개)
    
    Returns:
        (passed, pass_candidates, reason)
    """
    candidates = summary.get("candidates", [])
    
    if not candidates:
        return False, [], "No candidates found in summary"
    
    pass_candidates = []
    reasons = []
    
    for cand in candidates:
        kpi = cand.get("kpi_summary", {})
        
        # Check criteria
        rt = kpi.get("round_trips_completed", 0)
        pnl = kpi.get("total_pnl_usd", -999999)
        wr = kpi.get("win_rate_pct", 0)
        tp_exits = kpi.get("exit_reasons", {}).get("take_profit", 0)
        
        # RT >= 5 (필수)
        if rt < 5:
            reasons.append(f"E{cand['entry_bps']}/TP{cand['tp_bps']}: RT={rt} < 5")
            continue
        
        # 나머지 조건 중 하나라도 만족하면 PASS
        if pnl >= 0 and wr > 0 and tp_exits > 0:
            pass_candidates.append(cand)
            logger.info(f"PASS: E{cand['entry_bps']}/TP{cand['tp_bps']} - RT={rt}, PnL=${pnl:.2f}, WR={wr}%, TP={tp_exits}")
        else:
            reasons.append(
                f"E{cand['entry_bps']}/TP{cand['tp_bps']}: "
                f"PnL=${pnl:.2f}, WR={wr}%, TP={tp_exits} (need PnL>=0 AND WR>0 AND TP>0)"
            )
    
    # Phase 1 전체 통과 조건: 최소 1개 통과
    passed = len(pass_candidates) >= 1
    
    if not passed:
        reason = "Phase 1 FAIL: No candidates met acceptance criteria\n" + "\n".join(reasons)
    else:
        reason = f"Phase 1 PASS: {len(pass_candidates)}/{len(candidates)} candidates passed"
    
    return passed, pass_candidates, reason


def evaluate_phase2(summary: Dict[str, Any]) -> Tuple[bool, List[Dict], str]:
    """
    Phase 2 Acceptance Criteria 검증
    
    Criteria:
    - RT >= 10 (각 후보)
    - total_pnl_usd > 0 (필수)
    - win_rate_pct >= 10 (필수)
    - exit_reasons.take_profit >= 1 (필수)
    
    Returns:
        (passed, pass_candidates, reason)
    """
    candidates = summary.get("candidates", [])
    
    if not candidates:
        return False, [], "No candidates found in summary"
    
    pass_candidates = []
    reasons = []
    
    for cand in candidates:
        kpi = cand.get("kpi_summary", {})
        
        rt = kpi.get("round_trips_completed", 0)
        pnl = kpi.get("total_pnl_usd", -999999)
        wr = kpi.get("win_rate_pct", 0)
        tp_exits = kpi.get("exit_reasons", {}).get("take_profit", 0)
        
        # All criteria must pass
        if rt >= 10 and pnl > 0 and wr >= 10 and tp_exits >= 1:
            pass_candidates.append(cand)
            logger.info(f"PASS: E{cand['entry_bps']}/TP{cand['tp_bps']} - RT={rt}, PnL=${pnl:.2f}, WR={wr}%, TP={tp_exits}")
        else:
            reasons.append(
                f"E{cand['entry_bps']}/TP{cand['tp_bps']}: "
                f"RT={rt}, PnL=${pnl:.2f}, WR={wr}%, TP={tp_exits}"
            )
    
    passed = len(pass_candidates) >= 1
    
    if not passed:
        reason = "Phase 2 FAIL: No candidates met acceptance criteria\n" + "\n".join(reasons)
    else:
        reason = f"Phase 2 PASS: {len(pass_candidates)}/{len(candidates)} candidates passed"
    
    return passed, pass_candidates, reason


def evaluate_phase3(summary: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Phase 3 Acceptance Criteria 검증
    
    Criteria:
    - RT >= 30 (필수)
    - total_pnl_usd > 0 (필수)
    - win_rate_pct >= 20 (필수)
    - exit_reasons.take_profit >= exit_reasons.time_limit (필수)
    - loop_latency_p99_ms < 25 (필수)
    
    Returns:
        (passed, reason)
    """
    candidates = summary.get("candidates", [])
    
    if not candidates or len(candidates) == 0:
        return False, "No candidates found in summary"
    
    # Phase 3는 1개 후보만 실행
    cand = candidates[0]
    kpi = cand.get("kpi_summary", {})
    
    rt = kpi.get("round_trips_completed", 0)
    pnl = kpi.get("total_pnl_usd", -999999)
    wr = kpi.get("win_rate_pct", 0)
    tp_exits = kpi.get("exit_reasons", {}).get("take_profit", 0)
    timeout_exits = kpi.get("exit_reasons", {}).get("time_limit", 0)
    latency_p99 = kpi.get("loop_latency_p99_ms", 999)
    
    # Check all criteria
    checks = {
        "RT >= 30": rt >= 30,
        "PnL > 0": pnl > 0,
        "WR >= 20": wr >= 20,
        "TP >= Timeout": tp_exits >= timeout_exits,
        "Latency P99 < 25ms": latency_p99 < 25,
    }
    
    passed = all(checks.values())
    
    reason_parts = [
        f"E{cand['entry_bps']}/TP{cand['tp_bps']}:",
        f"RT={rt}, PnL=${pnl:.2f}, WR={wr}%,",
        f"TP={tp_exits}, Timeout={timeout_exits}, Latency_P99={latency_p99:.2f}ms",
    ]
    
    for check_name, check_result in checks.items():
        status = "✓" if check_result else "✗"
        reason_parts.append(f"{status} {check_name}")
    
    reason = " ".join(reason_parts)
    
    if passed:
        reason = "Phase 3 PASS: " + reason
    else:
        reason = "Phase 3 FAIL: " + reason
    
    return passed, reason


# =============================================================================
# Main Pipeline
# =============================================================================

def run_validation_pipeline(args):
    """완전 자동화 파이프라인 실행"""
    
    # Step 1: Environment Preparation
    prepare_environment()
    
    # Load candidates
    candidates_json = Path(args.candidates_json)
    if not candidates_json.exists():
        logger.error(f"Candidates JSON not found: {candidates_json}")
        sys.exit(1)
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize report
    report = {
        "created_at": datetime.now().isoformat(),
        "candidates_source": str(candidates_json),
        "dry_run": args.dry_run,
        "phase1": {},
        "phase2": {},
        "phase3": {},
        "final_decision": "NO_GO",
        "notes": "",
    }
    
    # =============================================================================
    # Phase 1: 10min Smoke Test (Top 3)
    # =============================================================================
    
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1: 10min Smoke Test (Top 3)")
    logger.info("=" * 80 + "\n")
    
    success, summary_path = run_phase(
        "Phase 1",
        args.phase1_duration_seconds,
        3,  # Top 3
        candidates_json,
        output_dir,
        dry_run=args.dry_run,
    )
    
    if not success or not summary_path.exists():
        logger.error("Phase 1 execution failed!")
        report["phase1"]["status"] = "EXECUTION_FAILED"
        report["final_decision"] = "NO_GO"
        report["notes"] = "Phase 1 실행 실패 (subprocess error 또는 timeout)"
        save_report(report, output_dir)
        return report
    
    # Load summary
    with open(summary_path) as f:
        phase1_summary = json.load(f)
    
    # Evaluate
    passed, pass_candidates, reason = evaluate_phase1(phase1_summary)
    
    report["phase1"] = {
        "duration_seconds": args.phase1_duration_seconds,
        "candidates_tested": len(phase1_summary.get("candidates", [])),
        "pass_candidates": len(pass_candidates),
        "status": "PASS" if passed else "FAIL",
        "reason": reason,
        "summary_path": str(summary_path),
    }
    
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"Phase 1 Result: {report['phase1']['status']}")
    logger.info(f"Reason: {reason}")
    logger.info("=" * 80)
    logger.info("")
    
    if not passed:
        report["phase2"]["status"] = "SKIPPED"
        report["phase3"]["status"] = "SKIPPED"
        report["final_decision"] = "NO_GO"
        report["notes"] = "Phase 1 미달 → Phase 2/3 스킵. TP threshold 재검토 또는 D82-10 Edge 모델 수정 필요."
        save_report(report, output_dir)
        return report
    
    # =============================================================================
    # Phase 2: 20min Validation (Top 2 from Phase 1)
    # =============================================================================
    
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 2: 20min Validation (Top 2 from Phase 1)")
    logger.info("=" * 80 + "\n")
    
    # Select top 2 from pass_candidates
    # Sort by PnL desc
    sorted_candidates = sorted(
        pass_candidates,
        key=lambda x: x.get("kpi_summary", {}).get("total_pnl_usd", -999999),
        reverse=True,
    )
    top2_candidates = sorted_candidates[:2]
    
    if len(top2_candidates) < 2:
        logger.warning(f"Only {len(top2_candidates)} candidates passed Phase 1, proceeding with them")
    
    # Create temporary candidates JSON for Phase 2
    phase2_candidates_data = {
        "metadata": phase1_summary.get("metadata", {}),
        "candidates": [
            {
                "entry_bps": c["entry_bps"],
                "tp_bps": c["tp_bps"],
                "edge_optimistic": c.get("edge_optimistic", 0),
                "edge_realistic": c.get("edge_realistic", 0),
                "edge_conservative": c.get("edge_conservative", 0),
                "is_structurally_safe": True,
                "is_recommended": True,
                "rationale": "Phase 1 passed",
            }
            for c in top2_candidates
        ]
    }
    
    phase2_candidates_json = output_dir / "phase2_candidates.json"
    with open(phase2_candidates_json, "w") as f:
        json.dump(phase2_candidates_data, f, indent=2)
    
    success, summary_path = run_phase(
        "Phase 2",
        args.phase2_duration_seconds,
        len(top2_candidates),
        phase2_candidates_json,
        output_dir,
        dry_run=args.dry_run,
    )
    
    if not success or not summary_path.exists():
        logger.error("Phase 2 execution failed!")
        report["phase2"]["status"] = "EXECUTION_FAILED"
        report["phase3"]["status"] = "SKIPPED"
        report["final_decision"] = "CONDITIONAL_NO_GO"
        report["notes"] = "Phase 1 통과했으나 Phase 2 실행 실패"
        save_report(report, output_dir)
        return report
    
    # Load summary
    with open(summary_path) as f:
        phase2_summary = json.load(f)
    
    # Evaluate
    passed, pass_candidates, reason = evaluate_phase2(phase2_summary)
    
    report["phase2"] = {
        "duration_seconds": args.phase2_duration_seconds,
        "candidates_tested": len(phase2_summary.get("candidates", [])),
        "pass_candidates": len(pass_candidates),
        "status": "PASS" if passed else "FAIL",
        "reason": reason,
        "summary_path": str(summary_path),
    }
    
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"Phase 2 Result: {report['phase2']['status']}")
    logger.info(f"Reason: {reason}")
    logger.info("=" * 80)
    logger.info("")
    
    if not passed:
        report["phase3"]["status"] = "SKIPPED"
        report["final_decision"] = "CONDITIONAL_NO_GO"
        report["notes"] = (
            "Phase 1 통과, Phase 2 미달 → Phase 3 스킵. "
            "이론 Edge는 양수지만 20분 실전에서 재현 실패. "
            "L2 Orderbook (D83-x) 우선 또는 Fill Model 개선 필요."
        )
        save_report(report, output_dir)
        return report
    
    # =============================================================================
    # Phase 3: 60min Confirmation (Top 1 from Phase 2)
    # =============================================================================
    
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 3: 60min Confirmation (Top 1 from Phase 2)")
    logger.info("=" * 80 + "\n")
    
    # Select top 1 from pass_candidates
    sorted_candidates = sorted(
        pass_candidates,
        key=lambda x: x.get("kpi_summary", {}).get("total_pnl_usd", -999999),
        reverse=True,
    )
    top1_candidate = sorted_candidates[0]
    
    # Create temporary candidates JSON for Phase 3
    phase3_candidates_data = {
        "metadata": phase2_summary.get("metadata", {}),
        "candidates": [
            {
                "entry_bps": top1_candidate["entry_bps"],
                "tp_bps": top1_candidate["tp_bps"],
                "edge_optimistic": top1_candidate.get("edge_optimistic", 0),
                "edge_realistic": top1_candidate.get("edge_realistic", 0),
                "edge_conservative": top1_candidate.get("edge_conservative", 0),
                "is_structurally_safe": True,
                "is_recommended": True,
                "rationale": "Phase 2 best candidate",
            }
        ]
    }
    
    phase3_candidates_json = output_dir / "phase3_candidates.json"
    with open(phase3_candidates_json, "w") as f:
        json.dump(phase3_candidates_data, f, indent=2)
    
    success, summary_path = run_phase(
        "Phase 3",
        args.phase3_duration_seconds,
        1,
        phase3_candidates_json,
        output_dir,
        dry_run=args.dry_run,
    )
    
    if not success or not summary_path.exists():
        logger.error("Phase 3 execution failed!")
        report["phase3"]["status"] = "EXECUTION_FAILED"
        report["final_decision"] = "CONDITIONAL_NO_GO"
        report["notes"] = "Phase 1/2 통과했으나 Phase 3 실행 실패"
        save_report(report, output_dir)
        return report
    
    # Load summary
    with open(summary_path) as f:
        phase3_summary = json.load(f)
    
    # Evaluate
    passed, reason = evaluate_phase3(phase3_summary)
    
    report["phase3"] = {
        "duration_seconds": args.phase3_duration_seconds,
        "candidate_tested": {
            "entry_bps": top1_candidate["entry_bps"],
            "tp_bps": top1_candidate["tp_bps"],
        },
        "status": "PASS" if passed else "FAIL",
        "reason": reason,
        "summary_path": str(summary_path),
    }
    
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"Phase 3 Result: {report['phase3']['status']}")
    logger.info(f"Reason: {reason}")
    logger.info("=" * 80)
    logger.info("")
    
    if passed:
        report["final_decision"] = "GO"
        report["notes"] = (
            f"D82-11 검증 성공! 최종 후보: E{top1_candidate['entry_bps']}/TP{top1_candidate['tp_bps']} bps. "
            "단기 PAPER 기준선 통과. 다음 단계: "
            "1) L2 Orderbook (D83-x) 통합, "
            "2) 3~12h 장기 PAPER (D82-12), "
            "3) Fill Model 개선 (Mock → Real)"
        )
    else:
        report["final_decision"] = "CONDITIONAL_NO_GO"
        report["notes"] = (
            "Phase 1/2 통과했으나 Phase 3 미달. "
            "60분 장기 실행에서 안정성 부족. "
            "추가 분석 및 threshold 미세 조정 필요."
        )
    
    save_report(report, output_dir)
    return report


def save_report(report: Dict[str, Any], output_dir: Path):
    """Save validation report"""
    report_path = output_dir / "d82_11_validation_report.json"
    
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"Validation report saved: {report_path}")
    logger.info(f"Final Decision: {report['final_decision']}")
    logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="D82-11 Full Validation Pipeline")
    parser.add_argument(
        "--candidates-json",
        default="logs/d82-10/recalibrated_tp_entry_candidates.json",
        help="Candidates JSON from D82-10",
    )
    parser.add_argument(
        "--phase1-duration-seconds",
        type=int,
        default=600,
        help="Phase 1 duration (default: 600s = 10min)",
    )
    parser.add_argument(
        "--phase2-duration-seconds",
        type=int,
        default=1200,
        help="Phase 2 duration (default: 1200s = 20min)",
    )
    parser.add_argument(
        "--phase3-duration-seconds",
        type=int,
        default=3600,
        help="Phase 3 duration (default: 3600s = 60min)",
    )
    parser.add_argument(
        "--output-dir",
        default="logs/d82-11",
        help="Output directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run mode (no actual execution)",
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("D82-11: Full Validation Pipeline (10m → 20m → 60m)")
    logger.info("=" * 80)
    logger.info(f"Candidates JSON: {args.candidates_json}")
    logger.info(f"Phase 1: {args.phase1_duration_seconds}s (10min)")
    logger.info(f"Phase 2: {args.phase2_duration_seconds}s (20min)")
    logger.info(f"Phase 3: {args.phase3_duration_seconds}s (60min)")
    logger.info(f"Output Dir: {args.output_dir}")
    logger.info(f"Dry-run: {args.dry_run}")
    logger.info("=" * 80)
    logger.info("")
    
    report = run_validation_pipeline(args)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Final Decision: {report['final_decision']}")
    logger.info(f"Notes: {report['notes']}")
    logger.info("=" * 80)
    
    # Exit code based on decision
    if report["final_decision"] == "GO":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
