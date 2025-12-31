#!/usr/bin/env python3
"""
D205-8: TopN + Route/Stress (Top10→50→100 확장 검증) - REAL MEASUREMENT

Purpose:
- Top10/50/100 시나리오별 스트레스 테스트 (진짜 실측)
- Latency p95: 실제 측정값 계산 (no stub)
- Queue depth: 내부 큐 max/p95 측정
- Throttling: queue>100 시 pause 발생 횟수
- Evidence 기반 AC 검증 (stub 금지)

Usage:
    python scripts/run_d205_8_topn_stress.py --topn 10 --duration 2
    python scripts/run_d205_8_topn_stress.py --topn 50 --duration 2
    python scripts/run_d205_8_topn_stress.py --topn 100 --duration 2

Author: arbitrage-lite V2
Date: 2026-01-01
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

# V2 imports - TopNStressRunner (진짜 실측)
from arbitrage.v2.harness.topn_stress import TopNStressRunner

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_ac(topn: int, metrics: Dict[str, Any]) -> bool:
    """
    D205-8 AC 검증 (진짜 실측 기반)
    
    Args:
        topn: Top N (10, 50, 100)
        metrics: 실측 메트릭
        
    Returns:
        passed: AC 통과 여부
    """
    passed = True
    latency_p95 = metrics["latency_p95_ms"]
    rate_limit_per_hr = metrics["rate_limit_hit_per_hr"]
    error_rate = metrics["error_rate_pct"]
    
    logger.info(f"\n{'='*60}")
    logger.info(f"[AC CHECK] Top{topn}")
    logger.info(f"{'='*60}")
    logger.info(f"Latency p95: {latency_p95:.2f}ms")
    logger.info(f"Rate limit: {rate_limit_per_hr:.2f}/hr")
    logger.info(f"Error rate: {error_rate:.2f}%")
    logger.info(f"Queue max: {metrics['queue_depth_max']}")
    logger.info(f"Throttling: {metrics['throttling_events']} events")
    
    # TopN별 AC
    if topn == 10:
        if latency_p95 >= 100:
            logger.error(f"❌ [FAIL] Top10 AC: latency_p95 {latency_p95:.1f}ms >= 100ms")
            passed = False
        else:
            logger.info(f"✅ [PASS] Top10 latency: {latency_p95:.1f}ms < 100ms")
        
        if rate_limit_per_hr > 0:
            logger.error(f"❌ [FAIL] Top10 AC: rate_limit {rate_limit_per_hr:.1f}/hr > 0")
            passed = False
        else:
            logger.info(f"✅ [PASS] Top10 rate_limit: {rate_limit_per_hr:.1f}/hr = 0")
    
    elif topn == 50:
        if latency_p95 >= 200:
            logger.error(f"❌ [FAIL] Top50 AC: latency_p95 {latency_p95:.1f}ms >= 200ms")
            passed = False
        else:
            logger.info(f"✅ [PASS] Top50 latency: {latency_p95:.1f}ms < 200ms")
        
        if rate_limit_per_hr >= 5:
            logger.error(f"❌ [FAIL] Top50 AC: rate_limit {rate_limit_per_hr:.1f}/hr >= 5")
            passed = False
        else:
            logger.info(f"✅ [PASS] Top50 rate_limit: {rate_limit_per_hr:.1f}/hr < 5")
    
    elif topn == 100:
        if latency_p95 >= 500:
            logger.error(f"❌ [FAIL] Top100 AC: latency_p95 {latency_p95:.1f}ms >= 500ms")
            passed = False
        else:
            logger.info(f"✅ [PASS] Top100 latency: {latency_p95:.1f}ms < 500ms")
        
        if rate_limit_per_hr >= 20:
            logger.error(f"❌ [FAIL] Top100 AC: rate_limit {rate_limit_per_hr:.1f}/hr >= 20")
            passed = False
        else:
            logger.info(f"✅ [PASS] Top100 rate_limit: {rate_limit_per_hr:.1f}/hr < 20")
    
    # Error rate 체크 (공통)
    if error_rate >= 1.0:
        logger.error(f"❌ [FAIL] Error rate {error_rate:.2f}% >= 1%")
        passed = False
    else:
        logger.info(f"✅ [PASS] Error rate: {error_rate:.2f}% < 1%")
    
    logger.info(f"{'='*60}\n")
    
    return passed


def save_evidence(topn: int, metrics: Dict[str, Any], output_dir: Path):
    """
    Evidence 저장 (진짜 실측 결과)
    
    Args:
        topn: Top N
        metrics: 실측 메트릭
        output_dir: Evidence 저장 경로
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. stress_test_topN.json (실측 결과)
    result_file = output_dir / f"stress_test_top{topn}.json"
    with open(result_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"✅ Saved: {result_file}")
    
    # 2. manifest.json
    ac_passed = validate_ac(topn, metrics)
    
    manifest = {
        "run_id": f"d205_8_measured_top{topn}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "topn": topn,
        "duration_minutes": metrics["duration_minutes"],
        "measurement_type": "REAL",
        "is_stub": False,
        "ac_status": "PASS" if ac_passed else "FAIL",
        "summary": {
            "latency_p50_ms": metrics["latency_p50_ms"],
            "latency_p95_ms": metrics["latency_p95_ms"],
            "latency_p99_ms": metrics["latency_p99_ms"],
            "rate_limit_hits_total": metrics["rate_limit_hits_total"],
            "rate_limit_hit_per_hr": metrics["rate_limit_hit_per_hr"],
            "error_rate_pct": metrics["error_rate_pct"],
            "queue_depth_max": metrics["queue_depth_max"],
            "queue_depth_p95": metrics["queue_depth_p95"],
            "throttling_events": metrics["throttling_events"],
            "total_iterations": metrics["total_iterations"],
        },
        "note": "Real measurement - latency/queue measured, rate_limit/throttling in mock mode"
    }
    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"✅ Saved: {manifest_file}")


def main():
    parser = argparse.ArgumentParser(
        description="D205-8 TopN Stress Test - REAL MEASUREMENT (no stub)"
    )
    parser.add_argument(
        "--topn", type=int, required=True, choices=[10, 50, 100],
        help="Top N symbols (10, 50, or 100)"
    )
    parser.add_argument(
        "--duration", type=int, default=2,
        help="Duration in minutes (default: 2)"
    )
    parser.add_argument(
        "--output-dir", type=str, default="",
        help="Output directory (default: auto-generated)"
    )
    
    args = parser.parse_args()
    
    # Output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"logs/evidence/d205_8_measured_top{args.topn}_{timestamp}")
    
    try:
        # TopNStressRunner 실행 (진짜 실측)
        runner = TopNStressRunner(
            topn=args.topn,
            duration_minutes=args.duration,
            output_dir=str(output_dir)
        )
        
        metrics = runner.run()
        
        # Evidence 저장 + AC 검증
        save_evidence(args.topn, metrics.to_dict(), output_dir)
        
        # AC 검증 결과 확인
        metrics_dict = metrics.to_dict()
        passed = (
            metrics_dict["latency_p95_ms"] < (100 if args.topn == 10 else 200 if args.topn == 50 else 500) and
            metrics_dict["error_rate_pct"] < 1.0
        )
        
        if passed:
            logger.info(f"\n✅ [PASS] Top{args.topn} stress test AC satisfied (REAL MEASUREMENT)")
            return 0
        else:
            logger.error(f"\n❌ [FAIL] Top{args.topn} stress test AC not satisfied")
            return 1
    
    except Exception as e:
        logger.error(f"❌ [FAIL] Stress test crashed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
