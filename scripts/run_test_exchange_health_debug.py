"""test_exchange_health.py의 개별 테스트를 하나씩 실행하여 hang 원인 파악"""

import subprocess
import sys

# test_exchange_health.py의 모든 테스트
TESTS = [
    "test_initialization",
    "test_latency_tracking",
    "test_error_ratio_calculation",
    "test_orderbook_freshness",
    "test_health_status_healthy",
    "test_health_status_degraded",
    "test_health_status_down",
    "test_health_status_frozen",
    "test_health_status_frozen_by_stale_orderbook",
    "test_health_status_transition",
    "test_should_failover_frozen",
    "test_should_failover_high_error_ratio",
    "test_rate_limit_status_update",
    "test_ws_status_update",
    "test_get_metrics_summary",
    "test_reset",
]

def run_single_test(test_name: str) -> tuple[bool, float]:
    """단일 테스트 실행"""
    print(f"Running: {test_name}...", end=" ", flush=True)
    
    import time
    start = time.time()
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", 
         f"tests/test_exchange_health.py::TestHealthMonitor::{test_name}", 
         "-v", "--tb=line"],
        capture_output=True,
        text=True,
        timeout=10  # 10초 타임아웃
    )
    
    elapsed = time.time() - start
    passed = result.returncode == 0
    
    if passed:
        print(f"✅ PASS ({elapsed:.2f}s)")
    else:
        print(f"❌ FAIL ({elapsed:.2f}s)")
        print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    
    return passed, elapsed

def main():
    print("test_exchange_health.py 개별 테스트 디버깅")
    print("="*80)
    
    results = {}
    
    for test_name in TESTS:
        try:
            passed, elapsed = run_single_test(test_name)
            results[test_name] = ("PASS" if passed else "FAIL", elapsed)
        except subprocess.TimeoutExpired:
            print(f"⏱️ TIMEOUT (10s)")
            results[test_name] = ("TIMEOUT", 10.0)
        except Exception as e:
            print(f"💥 ERROR: {e}")
            results[test_name] = ("ERROR", 0.0)
    
    print("\n" + "="*80)
    print("요약")
    print("="*80)
    
    for test_name, (status, elapsed) in results.items():
        icon = "✅" if status == "PASS" else "❌"
        print(f"{icon} {test_name}: {status} ({elapsed:.2f}s)")

if __name__ == "__main__":
    main()
