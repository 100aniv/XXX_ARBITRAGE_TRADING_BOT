"""
D75 회귀 테스트 스크립트

pytest hang 문제를 우회하기 위해 테스트 파일을 개별적으로 실행합니다.
"""

import subprocess
import sys
from pathlib import Path

# 테스트 파일 목록
TEST_FILES = [
    "tests/test_rate_limiter.py",
    "tests/test_exchange_health.py",
    "tests/test_arb_route.py",
    "tests/test_arb_universe.py",
    "tests/test_cross_sync.py",
    "tests/test_risk_guard.py",
]

def run_test_file(test_file: str) -> tuple[bool, str]:
    """단일 테스트 파일 실행"""
    print(f"\n{'='*80}")
    print(f"Running: {test_file}")
    print('='*80)
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
        capture_output=True,
        text=True,
        timeout=60  # 60초 타임아웃
    )
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr, file=sys.stderr)
    
    return result.returncode == 0, result.stdout

def main():
    print("D75 회귀 테스트 시작")
    print(f"테스트 파일: {len(TEST_FILES)}개")
    
    results = {}
    all_passed = True
    
    for test_file in TEST_FILES:
        try:
            passed, output = run_test_file(test_file)
            results[test_file] = "PASS" if passed else "FAIL"
            
            if not passed:
                all_passed = False
                print(f"\n❌ {test_file}: FAILED")
            else:
                print(f"\n✅ {test_file}: PASSED")
                
        except subprocess.TimeoutExpired:
            print(f"\n⏱️ {test_file}: TIMEOUT (60s)")
            results[test_file] = "TIMEOUT"
            all_passed = False
        except Exception as e:
            print(f"\n💥 {test_file}: ERROR - {e}")
            results[test_file] = "ERROR"
            all_passed = False
    
    # 최종 요약
    print("\n" + "="*80)
    print("D75 회귀 테스트 결과 요약")
    print("="*80)
    
    for test_file, status in results.items():
        icon = "✅" if status == "PASS" else "❌"
        print(f"{icon} {test_file}: {status}")
    
    print("="*80)
    
    if all_passed:
        print("\n🎉 모든 테스트 PASSED!")
        return 0
    else:
        print("\n❌ 일부 테스트 FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
