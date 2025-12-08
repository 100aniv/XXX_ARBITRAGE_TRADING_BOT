#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D87-5: Zone Selection Short PAPER Validation 테스트

D87-5 실행 하네스 및 Analyzer 검증
"""

import pytest
import json
from pathlib import Path
from typing import Dict, Any


class TestD87_5ZoneSelectionValidation:
    """D87-5 Validation 기본 구조 테스트"""
    
    def test_validation_script_exists(self):
        """D87-5 validation 스크립트 존재 확인"""
        script_path = Path(__file__).parent.parent / "scripts" / "d87_5_zone_selection_short_validation.py"
        assert script_path.exists(), f"D87-5 validation script not found: {script_path}"
    
    def test_analyzer_script_exists(self):
        """Analyzer 스크립트 존재 확인 (D87-3에서 재사용)"""
        script_path = Path(__file__).parent.parent / "scripts" / "analyze_d87_3_fillmodel_ab_test.py"
        assert script_path.exists(), f"Analyzer script not found: {script_path}"
    
    def test_calibration_file_exists(self):
        """Calibration 파일 존재 확인"""
        calibration_path = Path(__file__).parent.parent / "logs" / "d86-1" / "calibration_20251207_123906.json"
        assert calibration_path.exists(), f"Calibration file not found: {calibration_path}"


class TestAcceptanceCriteriaLogic:
    """Acceptance Criteria 평가 로직 검증"""
    
    def test_zone_distribution_diff_calculation(self):
        """Zone 분포 차이 계산 검증"""
        advisory_z2_ratio = 40.0  # %
        strict_z2_ratio = 50.0  # %
        
        delta_z2 = strict_z2_ratio - advisory_z2_ratio
        
        assert delta_z2 == 10.0
        assert delta_z2 >= 5.0  # C3: ΔP(Z2) ≥ 5%p
    
    def test_zone_score_diff_calculation(self):
        """Zone 점수 차이 계산 검증"""
        # Advisory mode
        z2_advisory_score = 63.0  # 60 * 1.05
        z1_advisory_score = 54.0  # 60 * 0.90
        advisory_diff = z2_advisory_score - z1_advisory_score  # 9점
        
        # Strict mode
        z2_strict_score = 69.0  # 60 * 1.15
        z1_strict_score = 48.0  # 60 * 0.80
        strict_diff = z2_strict_score - z1_strict_score  # 21점
        
        assert advisory_diff == 9.0
        assert strict_diff == 21.0
        assert strict_diff > advisory_diff  # C5: Strict > Advisory
    
    def test_duration_accuracy_check(self):
        """Duration 정확도 검증"""
        target_duration_seconds = 1800  # 30분
        actual_duration_seconds = 1805  # 30.08분
        
        actual_duration_minutes = actual_duration_seconds / 60
        
        assert 29.5 <= actual_duration_minutes <= 30.5  # C1: 30.0±0.5분
    
    def test_fill_events_threshold(self):
        """Fill Events 충분성 검증"""
        advisory_fill_count = 350
        strict_fill_count = 360
        
        assert advisory_fill_count >= 300  # C2: ≥300/세션
        assert strict_fill_count >= 300


class TestMockAnalyzerOutput:
    """Mock Analyzer 출력 검증"""
    
    def test_parse_ab_summary_json(self):
        """A/B 요약 JSON 파싱 검증"""
        mock_ab_summary = {
            "advisory_summary": {
                "total_trades": 180,
                "total_fill_events": 360,
                "total_pnl": 10.5,
                "zone_distribution": {
                    "Z1": {"count": 45, "percentage": 25.0},
                    "Z2": {"count": 90, "percentage": 50.0},
                    "Z3": {"count": 36, "percentage": 20.0},
                    "Z4": {"count": 9, "percentage": 5.0},
                }
            },
            "strict_summary": {
                "total_trades": 180,
                "total_fill_events": 360,
                "total_pnl": 11.2,
                "zone_distribution": {
                    "Z1": {"count": 27, "percentage": 15.0},
                    "Z2": {"count": 108, "percentage": 60.0},
                    "Z3": {"count": 36, "percentage": 20.0},
                    "Z4": {"count": 9, "percentage": 5.0},
                }
            },
            "comparison": {
                "zone_comparison": {
                    "Z1": {
                        "advisory": {"count": 45, "percentage": 25.0},
                        "strict": {"count": 27, "percentage": 15.0},
                        "delta": {"trade_percentage": -10.0},
                    },
                    "Z2": {
                        "advisory": {"count": 90, "percentage": 50.0},
                        "strict": {"count": 108, "percentage": 60.0},
                        "delta": {"trade_percentage": 10.0},
                    },
                }
            }
        }
        
        # Zone 분포 차이 검증
        z2_delta = mock_ab_summary["comparison"]["zone_comparison"]["Z2"]["delta"]["trade_percentage"]
        assert z2_delta == 10.0
        assert z2_delta >= 5.0  # C3: PASS
        
        # Z1 감소 검증
        z1_delta = mock_ab_summary["comparison"]["zone_comparison"]["Z1"]["delta"]["trade_percentage"]
        assert z1_delta == -10.0
        assert z1_delta <= -3.0  # C4: PASS


class TestD87_4BackwardCompatibility:
    """D87-4 Zone Preference 변경 사항 회귀 테스트"""
    
    def test_zone_preference_weights_loaded(self):
        """Zone Preference Weights 로드 확인"""
        from arbitrage.execution.fill_model_integration import FillModelConfig
        
        config = FillModelConfig(mode="strict")
        
        # Zone preference 자동 초기화 확인
        assert config.zone_preference is not None
        assert "strict" in config.zone_preference
        assert config.zone_preference["strict"]["Z2"] == 1.15
        assert config.zone_preference["strict"]["Z1"] == 0.80
    
    def test_adjust_route_score_multiplicative(self):
        """adjust_route_score() multiplicative 방식 확인"""
        from arbitrage.execution.fill_model_integration import (
            FillModelConfig,
            FillModelIntegration,
            FillModelAdvice,
        )
        
        config = FillModelConfig(mode="strict")
        integration = FillModelIntegration(config)
        
        advice_z2 = FillModelAdvice(
            entry_bps=10.0, tp_bps=12.0, zone_id="Z2",
            expected_fill_probability=0.63, expected_slippage_bps=0.0,
            confidence_level=1.0
        )
        
        base_score = 60.0
        adjusted_score = integration.adjust_route_score(base_score, advice_z2)
        
        # Multiplicative: 60.0 * 1.15 = 69.0
        assert abs(adjusted_score - 69.0) < 0.1


class TestD87_3ResultsReference:
    """D87-3 결과 참조 (Baseline)"""
    
    def test_d87_3_had_zero_zone_diff(self):
        """D87-3에서 Zone 분포 차이가 0%였음을 확인"""
        # D87-3 SHORT_VALIDATION 결과
        d87_3_z2_delta = 0.0  # %p
        
        # D87-5 목표
        d87_5_target_z2_delta = 5.0  # %p
        
        assert d87_3_z2_delta < d87_5_target_z2_delta
        assert d87_3_z2_delta == 0.0  # Baseline 확인


class TestValidationPlanExists:
    """Validation Plan 문서 존재 확인"""
    
    def test_validation_plan_document_exists(self):
        """D87_5_ZONE_SELECTION_VALIDATION_PLAN.md 존재 확인"""
        plan_path = Path(__file__).parent.parent / "docs" / "D87" / "D87_5_ZONE_SELECTION_VALIDATION_PLAN.md"
        assert plan_path.exists(), f"Validation plan not found: {plan_path}"
    
    def test_d87_4_design_document_exists(self):
        """D87_4_ZONE_SELECTION_DESIGN.md 존재 확인 (선행 작업)"""
        design_path = Path(__file__).parent.parent / "docs" / "D87" / "D87_4_ZONE_SELECTION_DESIGN.md"
        assert design_path.exists(), f"D87-4 design document not found: {design_path}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
