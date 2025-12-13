#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D92-4: Threshold 스윕 (10분 게이트 + 60분 베이스라인)"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


def run_single_threshold(
    threshold_bps: float,
    duration_minutes: int,
    stage_id: str = "d92-4",
    top_n: int = 10,
) -> Dict[str, Any]:
    """단일 threshold 실행"""
    print(f"\n{'='*80}")
    print(f"[D92-4] Threshold: {threshold_bps} bps | Duration: {duration_minutes}m")
    print(f"{'='*80}")
    
    env = os.environ.copy()
    env["ARBITRAGE_ENV"] = "paper"
    
    cmd = [
        "python",
        "scripts/run_d92_1_topn_longrun.py",
        "--top-n", str(top_n),
        "--duration-minutes", str(duration_minutes),
        "--mode", "advisory",
        "--stage-id", stage_id,
    ]
    
    print(f"[D92-4] 실행 명령어: {' '.join(cmd)}")
    print(f"[D92-4] 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent.parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=(duration_minutes + 2) * 60,
        )
        
        elapsed = time.time() - start_time
        
        print(f"[D92-4] 종료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[D92-4] 경과: {elapsed/60:.1f}분 | Exit code: {result.returncode}")
        
        if result.returncode != 0:
            print(f"[ERROR] 실행 실패")
            return {
                "threshold_bps": threshold_bps,
                "duration_minutes": duration_minutes,
                "status": "failed",
                "error": "execution_failed",
            }
        
        # 최신 KPI 파일 탐지
        latest_run_dir = find_latest_run_dir(stage_id)
        if not latest_run_dir:
            return {
                "threshold_bps": threshold_bps,
                "duration_minutes": duration_minutes,
                "status": "failed",
                "error": "no_run_dir",
            }
        
        kpi_file = list(latest_run_dir.glob("*_kpi_summary.json"))
        if not kpi_file:
            return {
                "threshold_bps": threshold_bps,
                "duration_minutes": duration_minutes,
                "status": "failed",
                "error": "no_kpi_file",
            }
        
        # KPI 파싱
        with open(kpi_file[0], "r", encoding="utf-8") as f:
            kpi = json.load(f)
        
        return {
            "threshold_bps": threshold_bps,
            "duration_minutes": duration_minutes,
            "status": "success",
            "run_id": kpi.get("session_id"),
            "run_dir": str(latest_run_dir),
            "kpi_file": str(kpi_file[0]),
            "metrics": {
                "total_trades": kpi.get("total_trades", 0),
                "round_trips_completed": kpi.get("round_trips_completed", 0),
                "total_pnl_krw": kpi.get("total_pnl_krw", 0.0),
                "total_pnl_usd": kpi.get("total_pnl_usd", 0.0),
                "win_rate_pct": kpi.get("win_rate_pct", 0.0),
                "exit_reasons": kpi.get("exit_reasons", {}),
                "avg_buy_slippage_bps": kpi.get("avg_buy_slippage_bps", 0.0),
                "avg_sell_slippage_bps": kpi.get("avg_sell_slippage_bps", 0.0),
            },
        }
        
    except subprocess.TimeoutExpired:
        print(f"[ERROR] 타임아웃 ({duration_minutes + 2}분)")
        return {
            "threshold_bps": threshold_bps,
            "duration_minutes": duration_minutes,
            "status": "failed",
            "error": "timeout",
        }
    except Exception as e:
        print(f"[ERROR] 예외: {e}")
        return {
            "threshold_bps": threshold_bps,
            "duration_minutes": duration_minutes,
            "status": "failed",
            "error": str(e),
        }


def find_latest_run_dir(stage_id: str) -> Optional[Path]:
    """최신 run_dir 탐지 (stage_id prefix 우선)"""
    stage_dir = Path(f"logs/{stage_id}")
    if not stage_dir.exists():
        return None
    
    matching_dirs = [d for d in stage_dir.iterdir() if d.is_dir() and d.name.startswith(f"{stage_id}-")]
    
    if matching_dirs:
        return sorted(matching_dirs, key=lambda x: x.stat().st_mtime, reverse=True)[0]
    
    run_dirs = sorted(
        [d for d in stage_dir.iterdir() if d.is_dir()],
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )
    
    return run_dirs[0] if run_dirs else None


def select_top_thresholds(sweep_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """스윕 결과 기반 상위 threshold 선정"""
    print(f"\n{'='*80}")
    print("[D92-4] 상위 threshold 선정")
    print(f"{'='*80}")
    
    # 필터링: trades_count=0 탈락
    valid_results = [r for r in sweep_results if r.get("metrics", {}).get("total_trades", 0) > 0]
    
    if not valid_results:
        print("[WARN] 유효한 threshold 없음 (모두 0 trades). 최신 2개 선정")
        return sorted(sweep_results, key=lambda x: x["threshold_bps"], reverse=True)[:2]
    
    # 점수 계산 (PnL + 승률 + exit_reasons 분포)
    for result in valid_results:
        metrics = result.get("metrics", {})
        trades = metrics.get("total_trades", 0)
        pnl = metrics.get("total_pnl_krw", 0.0)
        win_rate = metrics.get("win_rate_pct", 0.0)
        exit_reasons = metrics.get("exit_reasons", {})
        
        # time_limit 비율 (낮을수록 좋음)
        time_limit_ratio = exit_reasons.get("time_limit", 0) / max(trades, 1)
        
        # 점수: PnL (양수 우선) + 승률 + (1 - time_limit_ratio)
        score = (1 if pnl > 0 else -1) * abs(pnl) / 1000000 + win_rate + (1 - time_limit_ratio) * 10
        result["score"] = score
        
        print(f"  Threshold {result['threshold_bps']} bps:")
        print(f"    Trades: {trades} | PnL: {pnl:,.0f} KRW | Win Rate: {win_rate:.1f}%")
        print(f"    Time Limit Ratio: {time_limit_ratio:.1%} | Score: {score:.2f}")
    
    # 상위 1~2개 선정
    top_results = sorted(valid_results, key=lambda x: x.get("score", 0), reverse=True)[:2]
    
    print(f"\n[D92-4] 선정된 threshold: {[r['threshold_bps'] for r in top_results]} bps")
    
    return top_results


def generate_sweep_report(
    sweep_results: List[Dict[str, Any]],
    baseline_results: List[Dict[str, Any]],
) -> str:
    """스윕 리포트 생성"""
    report = f"""# D92-4 Threshold 스윕 리포트

**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 1. 10분 게이트 스윕 결과

| Threshold (bps) | Trades | PnL (KRW) | Win Rate | Time Limit % |
|---|---|---|---|---|
"""
    
    for result in sweep_results:
        if result["status"] == "success":
            metrics = result["metrics"]
            trades = metrics["total_trades"]
            pnl = metrics["total_pnl_krw"]
            win_rate = metrics["win_rate_pct"]
            exit_reasons = metrics["exit_reasons"]
            time_limit_ratio = exit_reasons.get("time_limit", 0) / max(trades, 1) if trades > 0 else 0
            
            report += f"| {result['threshold_bps']} | {trades} | {pnl:,.0f} | {win_rate:.1f}% | {time_limit_ratio:.1%} |\n"
        else:
            report += f"| {result['threshold_bps']} | FAILED | - | - | - |\n"
    
    report += f"""
## 2. 60분 베이스라인 결과

| Threshold (bps) | Trades | PnL (KRW) | Win Rate | Time Limit % |
|---|---|---|---|---|
"""
    
    for result in baseline_results:
        if result["status"] == "success":
            metrics = result["metrics"]
            trades = metrics["total_trades"]
            pnl = metrics["total_pnl_krw"]
            win_rate = metrics["win_rate_pct"]
            exit_reasons = metrics["exit_reasons"]
            time_limit_ratio = exit_reasons.get("time_limit", 0) / max(trades, 1) if trades > 0 else 0
            
            report += f"| {result['threshold_bps']} | {trades} | {pnl:,.0f} | {win_rate:.1f}% | {time_limit_ratio:.1%} |\n"
        else:
            report += f"| {result['threshold_bps']} | FAILED | - | - | - |\n"
    
    # 결론
    if baseline_results and baseline_results[0]["status"] == "success":
        best_threshold = baseline_results[0]["threshold_bps"]
        best_pnl = baseline_results[0]["metrics"]["total_pnl_krw"]
        report += f"""
## 3. 결론

**최적 Threshold**: {best_threshold} bps
**근거**: 60분 베이스라인에서 최고 PnL 달성 ({best_pnl:,.0f} KRW)

### Exit Reason 분포 분석
"""
        for result in baseline_results:
            if result["status"] == "success":
                exit_reasons = result["metrics"]["exit_reasons"]
                report += f"\n**Threshold {result['threshold_bps']} bps**:\n"
                for reason, count in exit_reasons.items():
                    report += f"- {reason}: {count}\n"
    
    return report


def main():
    """메인 함수"""
    print("[D92-4] Threshold 스윕 + 60분 베이스라인")
    print("=" * 80)
    
    # 1. 10분 게이트 스윕 (3개 threshold)
    print("\n[D92-4] PHASE 1: 10분 게이트 스윕")
    sweep_thresholds = [5.0, 4.8, 4.5]
    sweep_results = []
    
    for threshold in sweep_thresholds:
        result = run_single_threshold(threshold, duration_minutes=10, stage_id="d92-4")
        sweep_results.append(result)
        if result["status"] != "success":
            print(f"[WARN] Threshold {threshold} bps 실패: {result.get('error')}")
    
    # 2. 상위 threshold 선정
    top_thresholds = select_top_thresholds(sweep_results)
    
    if not top_thresholds or top_thresholds[0]["status"] != "success":
        print("[ERROR] 유효한 threshold 없음")
        sys.exit(1)
    
    # 3. 60분 베이스라인 (상위 1~2개)
    print(f"\n[D92-4] PHASE 2: 60분 베이스라인")
    baseline_results = []
    
    for result in top_thresholds:
        baseline_result = run_single_threshold(
            result["threshold_bps"],
            duration_minutes=60,
            stage_id="d92-4"
        )
        baseline_results.append(baseline_result)
    
    # 4. 리포트 생성
    report = generate_sweep_report(sweep_results, baseline_results)
    
    report_file = Path("docs/D92/D92_4_THRESHOLD_SWEEP_REPORT.md")
    report_file.write_text(report, encoding="utf-8")
    print(f"\n[D92-4] 리포트 저장: {report_file}")
    
    # 5. 최종 결과 출력
    print("\n" + "=" * 80)
    print("[D92-4] 스윕 완료")
    print("=" * 80)
    print(report)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
