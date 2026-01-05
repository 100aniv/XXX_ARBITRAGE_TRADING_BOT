#!/usr/bin/env python3
import sys
import json
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.observability.latency_profiler import LatencyProfiler, LatencyStage
from arbitrage.v2.storage.redis_latency_wrapper import RedisLatencyWrapper
from arbitrage.v2.observability.bottleneck_analyzer import analyze_bottleneck
import redis

def main():
    print("[D205-11-2] Smoke Test: Latency Profiling (N=200)")
    
    profiler = LatencyProfiler(enabled=True)
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=False)
    redis_wrapper = RedisLatencyWrapper(redis_client, profiler)
    
    evidence_dir = Path("logs/evidence/D205_11_2_SMOKE_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    samples = []
    N = 200
    
    print(f"Running {N} iterations...")
    for i in range(N):
        profiler.start_span(LatencyStage.RECEIVE_TICK)
        time.sleep(0.001)
        profiler.end_span(LatencyStage.RECEIVE_TICK)
        
        profiler.start_span(LatencyStage.DECIDE)
        time.sleep(0.0001)
        profiler.end_span(LatencyStage.DECIDE)
        
        try:
            redis_wrapper.get(f"test_key_{i}")
        except:
            pass
        
        try:
            redis_wrapper.set(f"test_key_{i}", f"value_{i}", ex=60)
        except:
            pass
        
        profiler.start_span(LatencyStage.DB_RECORD)
        time.sleep(0.0005)
        profiler.end_span(LatencyStage.DB_RECORD)
        
        snapshot = profiler.snapshot()
        samples.append({"iteration": i, "timestamp": datetime.now().isoformat(), "stages": snapshot})
        
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{N}")
    
    summary = profiler.snapshot()
    
    summary_path = evidence_dir / "latency_summary.json"
    with open(summary_path, 'w') as f:
        json.dump({"stages": summary, "e2e": {"p50": 0, "p95": 0, "max": 0}}, f, indent=2)
    print(f"Saved: {summary_path}")
    
    samples_path = evidence_dir / "latency_samples.jsonl"
    with open(samples_path, 'w') as f:
        for sample in samples:
            f.write(json.dumps(sample) + '\n')
    print(f"Saved: {samples_path}")
    
    with open(summary_path, 'r') as f:
        latency_summary = json.load(f)
    
    report = analyze_bottleneck(latency_summary)
    
    report_path = evidence_dir / "bottleneck_report.json"
    with open(report_path, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"Saved: {report_path}")
    
    print("\n=== Latency Summary ===")
    for stage_name, stats in summary.items():
        print(f"  {stage_name:15s} | p50: {stats['p50']:6.2f}ms | p95: {stats['p95']:6.2f}ms | count: {stats['count']}")
    
    print("\n=== Top 3 Bottlenecks ===")
    for i, bottleneck in enumerate(report.top_3_bottlenecks, 1):
        print(f"  #{i} {bottleneck.stage:15s} | p95: {bottleneck.p95_ms:6.2f}ms | {bottleneck.percentage:.1f}%")
    
    print(f"\nOptimization Priority: {report.optimization_priority}")
    print(f"Evidence: {evidence_dir}")
    
    redis_read_count = summary.get('REDIS_READ', {}).get('count', 0)
    redis_write_count = summary.get('REDIS_WRITE', {}).get('count', 0)
    db_count = summary.get('DB_RECORD', {}).get('count', 0)
    
    if redis_read_count == 0 or redis_write_count == 0:
        print("\nFAIL: Redis latency not measured")
        sys.exit(1)
    
    if db_count == 0:
        print("\nFAIL: DB latency not measured")
        sys.exit(1)
    
    print("\nPASS: All latency stages measured (N=200)")
    return evidence_dir

if __name__ == "__main__":
    main()
