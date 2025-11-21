#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D74-1: Performance Benchmarks Test Suite

Purpose:
- benchmark_d74_performance.py 동작 검증
- 각 벤치마크 케이스의 기본 실행 확인

Usage:
    python scripts/test_d74_1_performance_benchmarks.py
"""

import sys
import asyncio
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# benchmark 모듈 import 테스트
try:
    from scripts.benchmark_d74_performance import (
        benchmark_loop_latency,
        benchmark_redis_latency,
        create_benchmark_config,
    )
    print("✅ benchmark_d74_performance 모듈 import 성공")
except ImportError as e:
    print(f"❌ benchmark_d74_performance 모듈 import 실패: {e}")
    sys.exit(1)


def test_create_config():
    """Config 생성 테스트"""
    print("\n[TEST] create_benchmark_config()")
    
    config = create_benchmark_config(num_symbols=5)
    
    assert config is not None, "Config should not be None"
    assert config.universe.top_n == 5, "TOP_N should be 5"
    assert config.engine.mode == "multi", "Engine mode should be 'multi'"
    
    print("  ✅ Config 생성 성공")


async def test_loop_latency_small():
    """Loop latency 벤치마크 (작은 파라미터)"""
    print("\n[TEST] benchmark_loop_latency(symbols=2, iterations=10)")
    
    result = await benchmark_loop_latency(num_symbols=2, num_iterations=10)
    
    assert result is not None, "Result should not be None"
    assert result["case"] == "loop", "Case should be 'loop'"
    assert "metrics" in result, "Result should contain metrics"
    assert "latency_avg_ms" in result["metrics"], "Metrics should contain latency_avg_ms"
    
    print(f"  ✅ Loop benchmark 성공: avg={result['metrics']['latency_avg_ms']}ms")
    return result


async def test_redis_latency_small():
    """Redis latency 벤치마크 (작은 파라미터)"""
    print("\n[TEST] benchmark_redis_latency(requests=50)")
    
    result = await benchmark_redis_latency(num_requests=50)
    
    assert result is not None, "Result should not be None"
    assert result["case"] == "redis", "Case should be 'redis'"
    assert "metrics" in result, "Result should contain metrics"
    
    # Redis 연결 실패 시에도 결과 구조는 유지되어야 함
    metrics = result["metrics"]
    assert "latency_avg_ms" in metrics, "Metrics should contain latency_avg_ms"
    
    print(f"  ✅ Redis benchmark 성공: avg={metrics['latency_avg_ms']}ms")
    return result


def main():
    """메인 테스트 함수"""
    print("="*80)
    print("D74-1 Performance Benchmarks Test Suite")
    print("="*80)
    
    try:
        # Test 1: Config 생성
        test_create_config()
        
        # Test 2: Loop latency (작은 파라미터)
        loop_result = asyncio.run(test_loop_latency_small())
        
        # Test 3: Redis latency (작은 파라미터)
        redis_result = asyncio.run(test_redis_latency_small())
        
        # 요약
        print("\n" + "="*80)
        print("Test Summary")
        print("="*80)
        print("✅ All tests passed")
        print(f"  - Config generation: OK")
        print(f"  - Loop benchmark: OK (avg={loop_result['metrics']['latency_avg_ms']}ms)")
        print(f"  - Redis benchmark: OK (avg={redis_result['metrics']['latency_avg_ms']})")
        print("="*80 + "\n")
        
        return 0
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
