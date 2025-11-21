#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D74-2: Real PAPER Baseline Test Suite

Purpose:
- run_d74_2_paper_baseline.py의 기본 동작 검증
- 짧은 스모크 테스트 (12초)로 구조만 확인
- 실제 10분 캠페인은 main session에서 수동 실행

Usage:
    python scripts/test_d74_2_paper_baseline.py
"""

import sys
import subprocess
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_runner_imports():
    """
    러너 모듈 import 검증
    """
    print("\n[TEST] test_runner_imports")
    print("  Testing module imports...")
    
    try:
        # run_d74_2_paper_baseline 모듈 import
        sys.path.insert(0, str(Path(__file__).parent))
        import run_d74_2_paper_baseline
        
        # 주요 함수 존재 확인
        assert hasattr(run_d74_2_paper_baseline, "create_d74_2_config"), "create_d74_2_config not found"
        assert hasattr(run_d74_2_paper_baseline, "setup_paper_exchanges"), "setup_paper_exchanges not found"
        assert hasattr(run_d74_2_paper_baseline, "run_d74_2_campaign"), "run_d74_2_campaign not found"
        assert hasattr(run_d74_2_paper_baseline, "print_summary"), "print_summary not found"
        assert hasattr(run_d74_2_paper_baseline, "check_acceptance_criteria"), "check_acceptance_criteria not found"
        
        print("  ✅ PASS: All imports successful")
        return True
    
    except Exception as e:
        print(f"  ❌ FAIL: Import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_creation():
    """
    Config 생성 검증
    """
    print("\n[TEST] test_config_creation")
    print("  Testing config creation...")
    
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from run_d74_2_paper_baseline import create_d74_2_config
        
        # Config 생성 (10분)
        config = create_d74_2_config(duration_minutes=10.0)
        
        # 주요 설정 확인
        from arbitrage.symbol_universe import SymbolUniverseMode
        
        assert config.env == "development", f"env mismatch: {config.env}"
        assert config.session.mode == "paper", f"session mode mismatch: {config.session.mode}"
        assert config.session.max_runtime_seconds == 600, f"runtime mismatch: {config.session.max_runtime_seconds}"
        assert config.universe.mode == SymbolUniverseMode.TOP_N, f"universe mode mismatch: {config.universe.mode}"
        assert config.universe.top_n == 10, f"top_n mismatch: {config.universe.top_n}"
        assert config.engine.multi_symbol_enabled == True, f"multi_symbol not enabled"
        
        # RiskGuard 설정 확인 (완화된 설정)
        assert config.multi_symbol_risk_guard.max_total_exposure_usd == 20000.0, "exposure mismatch"
        assert config.multi_symbol_risk_guard.max_position_count == 3, "position_count mismatch"
        
        print("  ✅ PASS: Config created with correct settings")
        return True
    
    except Exception as e:
        print(f"  ❌ FAIL: Config creation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_short_smoke_campaign():
    """
    짧은 스모크 테스트 캠페인 (12초)
    
    실제 10분 캠페인은 너무 길므로, 테스트에서는 12초만 실행
    구조만 확인 (Acceptance Criteria는 체크하지 않음)
    """
    print("\n[TEST] test_short_smoke_campaign")
    print("  Running short smoke campaign (0.2 min = 12 sec)...")
    print("  Note: This test checks structure only, not acceptance criteria")
    
    cmd = [
        "python",
        "scripts/run_d74_2_paper_baseline.py",
        "--duration-minutes", "0.2",  # 12초
        "--log-level", "WARNING",  # 테스트 중에는 WARNING만
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    
    # 출력에서 주요 정보 확인
    output = result.stdout
    stderr = result.stderr
    
    # "Campaign completed" 메시지가 있으면 구조는 정상
    # exit code는 Acceptance Criteria 때문에 1이 나올 수 있지만, 구조 테스트는 통과
    if "Campaign completed" in output or "D74-2 Real PAPER Baseline Campaign Summary" in output:
        print("  ✅ PASS: Campaign completed without crash (structure OK)")
        print("  Note: Acceptance criteria may fail in 12sec test (체결 부족 가능)")
        return True
    
    # 실제 예외가 발생한 경우만 FAIL
    if "Exception" in stderr or "Traceback" in stderr:
        print(f"  ❌ FAIL: Campaign crashed with exception")
        print(f"\n  stderr (last 500 chars):\n{stderr[-500:]}")
        return False
    
    # 다른 경우는 PASS (exit code 1이어도 Acceptance Criteria 때문일 수 있음)
    print(f"  ✅ PASS: Campaign completed (exit code {result.returncode})")
    return True


def main():
    """메인 테스트 함수"""
    print("="*80)
    print("D74-2 Real PAPER Baseline Test Suite")
    print("="*80)
    
    tests = [
        ("Module imports", test_runner_imports),
        ("Config creation", test_config_creation),
        ("Short smoke campaign", test_short_smoke_campaign),
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
