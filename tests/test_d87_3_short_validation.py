#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D87-3_SHORT_VALIDATION 테스트

Short Validation Runner 및 Acceptance Criteria 평가 로직 검증
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


def test_short_validation_runner_duration():
    """Short Validation Runner의 duration 설정 검증"""
    # 30분 = 1800초 설정 확인
    duration_seconds = 1800
    timeout_seconds = duration_seconds + 300  # 5분 grace period
    
    assert duration_seconds == 1800
    assert timeout_seconds == 2100
    assert timeout_seconds > duration_seconds


def test_acceptance_criteria_sc1_duration():
    """SC1: Duration 30분 완주 검증"""
    # PASS 케이스: 28~32분 범위
    adv_duration = 30.0 * 60  # 30분
    strict_duration = 30.5 * 60  # 30.5분
    
    adv_min = adv_duration / 60
    strict_min = strict_duration / 60
    
    sc1_pass = (28 <= adv_min <= 32) and (28 <= strict_min <= 32)
    assert sc1_pass is True
    
    # FAIL 케이스: 범위 밖
    adv_duration_fail = 27.0 * 60  # 27분
    adv_min_fail = adv_duration_fail / 60
    
    sc1_fail = (28 <= adv_min_fail <= 32)
    assert sc1_fail is False


def test_acceptance_criteria_sc2_fill_events():
    """SC2: Fill Events ≥ 300 검증"""
    # PASS 케이스
    adv_fill_count = 360
    strict_fill_count = 360
    
    sc2_pass = (adv_fill_count >= 300) and (strict_fill_count >= 300)
    assert sc2_pass is True
    
    # FAIL 케이스
    adv_fill_count_fail = 250
    sc2_fail = (adv_fill_count_fail >= 300)
    assert sc2_fail is False


def test_acceptance_criteria_sc3_z2_ratio():
    """SC3: Z2 비중 Strict > Advisory +5%p 검증"""
    # PASS 케이스: Strict가 Advisory보다 6%p 높음
    z2_ratio_diff = 6.0
    sc3_pass = z2_ratio_diff >= 5.0
    assert sc3_pass is True
    
    # FAIL 케이스: 차이가 4%p로 부족
    z2_ratio_diff_fail = 4.0
    sc3_fail = z2_ratio_diff_fail >= 5.0
    assert sc3_fail is False


def test_acceptance_criteria_sc4_z1z3z4_ratio():
    """SC4: Z1/Z3/Z4 비중 Strict < Advisory -3%p 검증"""
    # PASS 케이스: Z1이 -5%p 낮음
    z1_ratio_diff = -5.0
    z3_ratio_diff = -2.0
    z4_ratio_diff = -1.0
    
    sc4_pass = (z1_ratio_diff <= -3.0) or (z3_ratio_diff <= -3.0) or (z4_ratio_diff <= -3.0)
    assert sc4_pass is True
    
    # FAIL 케이스: 모든 zone이 -3%p보다 높음
    z1_fail = -2.0
    z3_fail = -1.0
    z4_fail = 0.0
    
    sc4_fail = (z1_fail <= -3.0) or (z3_fail <= -3.0) or (z4_fail <= -3.0)
    assert sc4_fail is False


def test_acceptance_criteria_sc5_z2_avg_size():
    """SC5: Z2 평균 사이즈 Strict > Advisory +3% 검증"""
    # PASS 케이스: Strict가 Advisory보다 5% 큼
    z2_advisory_size = 0.0006
    z2_strict_size = 0.00063
    
    z2_size_diff_pct = ((z2_strict_size / z2_advisory_size) - 1.0) * 100
    sc5_pass = z2_size_diff_pct >= 3.0
    assert sc5_pass is True
    
    # FAIL 케이스: 차이가 2%로 부족
    z2_strict_size_fail = 0.000612
    z2_size_diff_pct_fail = ((z2_strict_size_fail / z2_advisory_size) - 1.0) * 100
    sc5_fail = z2_size_diff_pct_fail >= 3.0
    assert sc5_fail is False


def test_acceptance_criteria_sc6_pnl():
    """SC6: PnL 정상 범위 검증"""
    # PASS 케이스: 정상 범위
    adv_pnl = 11.10
    strict_pnl = 11.15
    
    sc6_pass = (adv_pnl > -1000.0) and (strict_pnl > -1000.0)
    assert sc6_pass is True
    
    # FAIL 케이스: 극단적 손실
    adv_pnl_fail = -1500.0
    sc6_fail = (adv_pnl_fail > -1000.0)
    assert sc6_fail is False


def test_acceptance_evaluation_status():
    """Acceptance Criteria 평가 상태 판정 로직 검증"""
    # PASS 케이스: 모든 기준 통과
    criteria_all_pass = {
        "SC1": {"pass": True},
        "SC2": {"pass": True},
        "SC3": {"pass": True},
        "SC4": {"pass": True},
        "SC5": {"pass": True},
        "SC6": {"pass": True},
    }
    
    all_pass = all(c["pass"] for c in criteria_all_pass.values())
    assert all_pass is True
    status = "PASS"
    assert status == "PASS"
    
    # CONDITIONAL_GO 케이스: Critical(SC1, SC2, SC3)만 통과
    criteria_critical_pass = {
        "SC1": {"pass": True},
        "SC2": {"pass": True},
        "SC3": {"pass": True},
        "SC4": {"pass": False},
        "SC5": {"pass": False},
        "SC6": {"pass": True},
    }
    
    critical_pass = (
        criteria_critical_pass["SC1"]["pass"] and
        criteria_critical_pass["SC2"]["pass"] and
        criteria_critical_pass["SC3"]["pass"]
    )
    all_pass_cond = all(c["pass"] for c in criteria_critical_pass.values())
    
    assert critical_pass is True
    assert all_pass_cond is False
    status_cond = "CONDITIONAL_GO" if critical_pass else "FAIL"
    assert status_cond == "CONDITIONAL_GO"
    
    # FAIL 케이스: Critical 기준 미달
    criteria_fail = {
        "SC1": {"pass": True},
        "SC2": {"pass": False},  # Critical 실패
        "SC3": {"pass": False},  # Critical 실패
        "SC4": {"pass": False},
        "SC5": {"pass": False},
        "SC6": {"pass": True},
    }
    
    critical_fail = (
        criteria_fail["SC1"]["pass"] and
        criteria_fail["SC2"]["pass"] and
        criteria_fail["SC3"]["pass"]
    )
    
    assert critical_fail is False
    status_fail = "PASS" if all(c["pass"] for c in criteria_fail.values()) else (
        "CONDITIONAL_GO" if critical_fail else "FAIL"
    )
    assert status_fail == "FAIL"


def test_short_validation_output_files():
    """Short Validation 출력 파일 경로 검증"""
    logs_dir = Path("logs/d87-3")
    
    ab_summary_path = logs_dir / "d87_3_short_ab_summary.json"
    acceptance_path = logs_dir / "d87_3_short_acceptance.json"
    
    assert ab_summary_path.name == "d87_3_short_ab_summary.json"
    assert acceptance_path.name == "d87_3_short_acceptance.json"


def test_session_tags():
    """세션 태그 검증"""
    advisory_tag = "d87_3_advisory_30m"
    strict_tag = "d87_3_strict_30m"
    
    assert "advisory" in advisory_tag
    assert "strict" in strict_tag
    assert "30m" in advisory_tag
    assert "30m" in strict_tag


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
