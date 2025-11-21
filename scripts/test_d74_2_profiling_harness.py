#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D74-2: Profiling Harness Test Suite

Purpose:
- profile_d74_multi_symbol_engine.py 동작 검증
- 프로파일 파일 생성 확인
- 텍스트 리포트 내용 검증

Usage:
    python scripts/test_d74_2_profiling_harness.py
"""

import os
import sys
import subprocess
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_profile_generates_files():
    """
    프로파일링 스크립트가 .prof 및 .txt 파일을 생성하는지 검증
    
    최소 파라미터(2 symbols, 10 iterations)로 빠른 테스트
    """
    print("\n[TEST] test_profile_generates_files")
    print("  Testing with: 2 symbols, 10 iterations")
    
    # 출력 경로 설정
    output_dir = Path(__file__).parent.parent / "profiles"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    test_profile = output_dir / "test_d74_2_minimal.prof"
    test_report = output_dir / "test_d74_2_minimal.txt"
    
    # 이전 테스트 파일 정리
    if test_profile.exists():
        test_profile.unlink()
    if test_report.exists():
        test_report.unlink()
    
    # 프로파일링 실행
    cmd = [
        "python",
        "scripts/profile_d74_multi_symbol_engine.py",
        "--symbols", "2",
        "--iterations", "10",
        "--output", str(test_profile),
        "--top-n", "20",
        "--log-level", "ERROR",  # 테스트 중에는 에러만 출력
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    # 실행 성공 여부
    if result.returncode != 0:
        print(f"  ❌ FAIL: profiler exited with code {result.returncode}")
        print(f"  stderr: {result.stderr}")
        return False
    
    # 파일 생성 확인
    if not test_profile.exists():
        print(f"  ❌ FAIL: {test_profile} not created")
        return False
    
    if not test_report.exists():
        print(f"  ❌ FAIL: {test_report} not created")
        return False
    
    # 파일 크기 확인 (최소한 비어있지 않은지)
    if test_profile.stat().st_size == 0:
        print(f"  ❌ FAIL: {test_profile} is empty")
        return False
    
    if test_report.stat().st_size == 0:
        print(f"  ❌ FAIL: {test_report} is empty")
        return False
    
    print(f"  ✅ PASS: .prof file created ({test_profile.stat().st_size} bytes)")
    print(f"  ✅ PASS: .txt report created ({test_report.stat().st_size} bytes)")
    
    # 정리
    test_profile.unlink()
    test_report.unlink()
    
    return True


def test_profile_output_contains_functions():
    """
    텍스트 리포트에 엔진 관련 함수명이 포함되는지 검증
    
    예상 함수:
    - run_multi (MultiSymbolEngineRunner)
    - _run_for_symbol (per-symbol coroutine)
    - evaluate_* (RiskGuard)
    """
    print("\n[TEST] test_profile_output_contains_functions")
    print("  Verifying profile report contains engine functions")
    
    # 출력 경로 설정
    output_dir = Path(__file__).parent.parent / "profiles"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    test_profile = output_dir / "test_d74_2_content.prof"
    test_report = output_dir / "test_d74_2_content.txt"
    
    # 이전 테스트 파일 정리
    if test_profile.exists():
        test_profile.unlink()
    if test_report.exists():
        test_report.unlink()
    
    # 프로파일링 실행 (약간 더 큰 케이스로)
    cmd = [
        "python",
        "scripts/profile_d74_multi_symbol_engine.py",
        "--symbols", "3",
        "--iterations", "20",
        "--output", str(test_profile),
        "--top-n", "30",
        "--log-level", "ERROR",
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    if result.returncode != 0:
        print(f"  ❌ FAIL: profiler exited with code {result.returncode}")
        return False
    
    # 리포트 읽기
    with open(test_report, "r", encoding="utf-8") as f:
        report_content = f.read()
    
    # 예상 함수/모듈 키워드 확인
    expected_keywords = [
        "run_multi",           # MultiSymbolEngineRunner.run_multi
        "multi_symbol_engine", # 모듈명
    ]
    
    found_keywords = []
    missing_keywords = []
    
    for keyword in expected_keywords:
        if keyword in report_content:
            found_keywords.append(keyword)
        else:
            missing_keywords.append(keyword)
    
    # 최소 1개 이상 발견되면 PASS
    if len(found_keywords) > 0:
        print(f"  ✅ PASS: Found {len(found_keywords)} expected keywords: {found_keywords}")
        
        # 정리
        test_profile.unlink()
        test_report.unlink()
        
        return True
    else:
        print(f"  ❌ FAIL: No expected keywords found in report")
        print(f"  Missing: {missing_keywords}")
        print(f"\n  Report preview (first 500 chars):")
        print(f"  {report_content[:500]}")
        return False


def main():
    """메인 테스트 함수"""
    print("="*80)
    print("D74-2 Profiling Harness Test Suite")
    print("="*80)
    
    tests = [
        ("Profile file generation", test_profile_generates_files),
        ("Profile content validation", test_profile_output_contains_functions),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    # 요약
    print("\n" + "="*80)
    print("Test Summary")
    print("="*80)
    print(f"  Passed: {passed}/{len(tests)}")
    print(f"  Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n✅ All tests passed!")
        print("="*80 + "\n")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed")
        print("="*80 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
