#!/usr/bin/env python3
"""
D75-2: Integration Benchmark
Loop latency 측정 및 D74 baseline 대비 개선율 검증
"""

import asyncio
import time
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arbitrage.config import load_config
from arbitrage.multi_symbol_engine import MultiSymbolEngineRunner

async def main():
    print("="*70)
    print("D75-2: Integration Benchmark (Top10, 1분)")
    print("="*70)
    
    # Top10 config 로드
    config_path = project_root / "configs" / "d74_4_top10_paper_loadtest.yaml"
    config = load_config(str(config_path))
    
    # Runtime 1분으로 설정
    config["live"]["max_runtime_seconds"] = 60
    
    # Runner 생성 및 실행
    print("\n[1/3] Multi-symbol runner 초기화 중...")
    runner = MultiSymbolEngineRunner(config)
    
    print("[2/3] 1분 로드테스트 실행 중...")
    start_time = time.time()
    await runner.run()
    end_time = time.time()
    
    # 결과 수집
    runtime = end_time - start_time
    summary = runner.get_summary()
    
    print("\n[3/3] 결과 분석")
    print("="*70)
    print(f"Runtime: {runtime:.2f}s")
    print(f"Total Iterations: {summary.get('total_iterations', 0):,}")
    print(f"Throughput: {summary.get('throughput_per_sec', 0):.2f} iter/s")
    print(f"Avg Loop Latency: {summary.get('avg_loop_latency_ms', 0):.2f}ms")
    print(f"P99 Loop Latency: {summary.get('p99_loop_latency_ms', 0):.2f}ms")
    print(f"Total Filled Orders: {summary.get('total_filled_orders', 0):,}")
    print(f"CPU (avg): {summary.get('cpu_avg_pct', 0):.2f}%")
    print(f"Memory (avg): {summary.get('memory_avg_mb', 0):.2f} MB")
    print("="*70)
    
    # D74 Baseline과 비교
    d74_latency = 62.0  # ms
    d75_1_latency = 62.0  # ms (async 변환 후에도 동일)
    d75_2_target = 25.0  # ms
    
    current_latency = summary.get('avg_loop_latency_ms', 999)
    
    print("\n📊 D75-2 Acceptance Criteria:")
    print(f"  Loop latency < 25ms (avg): {'✅ PASS' if current_latency < 25 else '❌ FAIL'} (current: {current_latency:.2f}ms)")
    print(f"  Loop latency < 40ms (p99): {'✅ PASS' if summary.get('p99_loop_latency_ms', 999) < 40 else '❌ FAIL'} (current: {summary.get('p99_loop_latency_ms', 0):.2f}ms)")
    print(f"  Throughput ≥ 40 iter/s: {'✅ PASS' if summary.get('throughput_per_sec', 0) >= 40 else '❌ FAIL'} (current: {summary.get('throughput_per_sec', 0):.2f}/s)")
    print(f"  CPU < 10%: {'✅ PASS' if summary.get('cpu_avg_pct', 0) < 10 else '❌ FAIL'} (current: {summary.get('cpu_avg_pct', 0):.2f}%)")
    
    print(f"\n📈 Performance Improvement:")
    if current_latency < d75_1_latency:
        improvement = ((d75_1_latency - current_latency) / d75_1_latency) * 100
        print(f"  D74 → D75-2: {d74_latency:.2f}ms → {current_latency:.2f}ms ({improvement:.1f}% improvement)")
    else:
        print(f"  D74 → D75-2: {d74_latency:.2f}ms → {current_latency:.2f}ms (No improvement)")
    
    # Overall 판정
    all_pass = (
        current_latency < 25 and
        summary.get('p99_loop_latency_ms', 999) < 40 and
        summary.get('throughput_per_sec', 0) >= 40 and
        summary.get('cpu_avg_pct', 0) < 10
    )
    
    print(f"\n{'🎉 D75-2 PASSED - All acceptance criteria met!' if all_pass else '⚠️  D75-2 INCOMPLETE - Some criteria not met'}")
    print("="*70)
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
