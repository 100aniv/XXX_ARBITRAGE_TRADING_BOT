# -*- coding: utf-8 -*-
"""
D82-7: Edge Analysis & Threshold Recalibration - Unit Tests

테스트 범위:
1. EdgeAnalysisResult 데이터 클래스
2. 슬리피지 통계 계산
3. Threshold 추천 로직
4. Edge 계산 로직

Author: arbitrage-lite project
Date: 2025-12-05
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# D82-7 스크립트의 클래스들을 import하기 위해 sys.path 조정
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from analyze_d82_7_edge_and_thresholds import (
    EdgeAnalysisResult,
    ThresholdRecommendation,
    EdgeAnalyzer
)


class TestEdgeAnalysisResult:
    """EdgeAnalysisResult 데이터 클래스 테스트"""
    
    def test_edge_analysis_result_creation(self):
        """EdgeAnalysisResult 생성 테스트"""
        result = EdgeAnalysisResult(
            entry_bps=0.5,
            tp_bps=1.5,
            run_id="test_run",
            entries=2,
            round_trips=1,
            win_rate_pct=0.0,
            pnl_usd=-500.0,
            avg_buy_slippage_bps=2.0,
            avg_sell_slippage_bps=2.0,
            avg_slippage_bps=2.0,
            estimated_avg_spread_bps=1.0,
            effective_edge_bps=-1.0,
            estimated_notional_usd=20000.0,
            pnl_bps=-250.0,
            is_structurally_profitable=False
        )
        
        assert result.entry_bps == 0.5
        assert result.tp_bps == 1.5
        assert result.effective_edge_bps == -1.0
        assert result.is_structurally_profitable is False
        assert result.fee_bps == 9.0  # default value
    
    def test_edge_analysis_result_with_custom_fee(self):
        """EdgeAnalysisResult with custom fee_bps"""
        result = EdgeAnalysisResult(
            entry_bps=0.5,
            tp_bps=1.5,
            run_id="test_run",
            entries=2,
            round_trips=1,
            win_rate_pct=0.0,
            pnl_usd=-500.0,
            avg_buy_slippage_bps=2.0,
            avg_sell_slippage_bps=2.0,
            avg_slippage_bps=2.0,
            estimated_avg_spread_bps=1.0,
            effective_edge_bps=-1.0,
            estimated_notional_usd=20000.0,
            pnl_bps=-250.0,
            is_structurally_profitable=False,
            fee_bps=10.0
        )
        
        assert result.fee_bps == 10.0


class TestSlippageStatistics:
    """슬리피지 통계 계산 테스트"""
    
    def test_calculate_slippage_statistics(self):
        """슬리피지 통계 계산 테스트"""
        edge_results = [
            EdgeAnalysisResult(
                entry_bps=0.3,
                tp_bps=1.0,
                run_id=f"run_{i}",
                entries=2,
                round_trips=1,
                win_rate_pct=0.0,
                pnl_usd=-400.0,
                avg_buy_slippage_bps=2.1,
                avg_sell_slippage_bps=2.1,
                avg_slippage_bps=2.1,
                estimated_avg_spread_bps=0.65,
                effective_edge_bps=-1.45,
                estimated_notional_usd=20000.0,
                pnl_bps=-200.0,
                is_structurally_profitable=False
            )
            for i in range(9)
        ]
        
        analyzer = EdgeAnalyzer(
            sweep_summary_path=Path("dummy.json"),
            output_dir=Path("dummy_output"),
            fee_bps=9.0
        )
        
        stats = analyzer.calculate_slippage_statistics(edge_results)
        
        assert stats['avg'] == pytest.approx(2.1, abs=0.01)
        assert stats['median'] == pytest.approx(2.1, abs=0.01)
        assert stats['min'] == pytest.approx(2.1, abs=0.01)
        assert stats['max'] == pytest.approx(2.1, abs=0.01)
    
    def test_empty_edge_results(self):
        """빈 결과 리스트 처리 테스트"""
        analyzer = EdgeAnalyzer(
            sweep_summary_path=Path("dummy.json"),
            output_dir=Path("dummy_output"),
            fee_bps=9.0
        )
        
        stats = analyzer.calculate_slippage_statistics([])
        
        assert stats['avg'] == 0.0
        assert stats['median'] == 0.0
        assert stats['p95'] == 0.0
        assert stats['max'] == 0.0


class TestThresholdRecommendation:
    """Threshold 추천 로직 테스트"""
    
    def test_recommend_thresholds(self):
        """Threshold 추천 계산 테스트"""
        analyzer = EdgeAnalyzer(
            sweep_summary_path=Path("dummy.json"),
            output_dir=Path("dummy_output"),
            fee_bps=9.0
        )
        
        slip_stats = {
            'avg': 2.14,
            'median': 2.14,
            'p95': 2.14,
            'max': 2.14,
            'min': 2.14,
            'std': 0.0
        }
        
        recommendation = analyzer.recommend_thresholds(slip_stats)
        
        # 최소 Entry = ceil(p95_slip + fee + margin) = ceil(2.14 + 9.0 + 2.0) = 14
        assert recommendation.recommended_entry_bps_list[0] == 14.0
        
        # 최소 TP = ceil(Entry + p95_slip + margin) = ceil(14 + 2.14 + 2.0) = 19
        assert recommendation.recommended_tp_bps_list[0] == 19.0
        
        # 3개씩 레인지 생성
        assert len(recommendation.recommended_entry_bps_list) == 3
        assert len(recommendation.recommended_tp_bps_list) == 3
        
        # 슬리피지 통계 저장 확인
        assert recommendation.avg_slippage_bps == 2.14
        assert recommendation.p95_slippage_bps == 2.14
    
    def test_recommend_thresholds_with_higher_slippage(self):
        """높은 슬리피지 케이스 테스트"""
        analyzer = EdgeAnalyzer(
            sweep_summary_path=Path("dummy.json"),
            output_dir=Path("dummy_output"),
            fee_bps=10.0
        )
        
        slip_stats = {
            'avg': 5.0,
            'median': 5.0,
            'p95': 6.0,
            'max': 7.0,
            'min': 4.0,
            'std': 1.0
        }
        
        recommendation = analyzer.recommend_thresholds(slip_stats)
        
        # 최소 Entry = ceil(6.0 + 10.0 + 2.0) = 18
        assert recommendation.recommended_entry_bps_list[0] == 18.0
        
        # 최소 TP = ceil(18 + 6.0 + 2.0) = 26
        assert recommendation.recommended_tp_bps_list[0] == 26.0


class TestEdgeCalculation:
    """Edge 계산 로직 테스트"""
    
    def test_calculate_edge_for_result(self):
        """개별 결과의 Edge 계산 테스트"""
        analyzer = EdgeAnalyzer(
            sweep_summary_path=Path("dummy.json"),
            output_dir=Path("dummy_output"),
            fee_bps=9.0,
            estimated_notional_per_rt=20000.0
        )
        
        result_data = {
            'entry_bps': 0.5,
            'tp_bps': 1.5,
            'run_id': 'test_run',
            'entries': 2,
            'round_trips': 1,
            'win_rate_pct': 0.0,
            'pnl_usd': -500.0,
            'avg_buy_slippage_bps': 2.0,
            'avg_sell_slippage_bps': 2.0
        }
        
        edge_result = analyzer.calculate_edge_for_result(result_data)
        
        # Spread = (0.5 + 1.5) / 2 = 1.0
        assert edge_result.estimated_avg_spread_bps == 1.0
        
        # Slippage = (2.0 + 2.0) / 2 = 2.0
        assert edge_result.avg_slippage_bps == 2.0
        
        # Edge = 1.0 - 2.0 = -1.0
        assert edge_result.effective_edge_bps == -1.0
        
        # Notional = 1 * 20000 = 20000
        assert edge_result.estimated_notional_usd == 20000.0
        
        # PnL bps = (-500 / 20000) * 10000 = -250
        assert edge_result.pnl_bps == pytest.approx(-250.0, abs=0.1)
        
        # Edge -1.0 < Fee 9.0 → 구조적 수익 불가
        assert edge_result.is_structurally_profitable is False
    
    def test_calculate_edge_with_positive_edge(self):
        """양수 Edge 케이스 테스트"""
        analyzer = EdgeAnalyzer(
            sweep_summary_path=Path("dummy.json"),
            output_dir=Path("dummy_output"),
            fee_bps=9.0,
            estimated_notional_per_rt=20000.0
        )
        
        result_data = {
            'entry_bps': 15.0,
            'tp_bps': 20.0,
            'run_id': 'test_run_positive',
            'entries': 2,
            'round_trips': 1,
            'win_rate_pct': 100.0,
            'pnl_usd': 500.0,
            'avg_buy_slippage_bps': 2.0,
            'avg_sell_slippage_bps': 2.0
        }
        
        edge_result = analyzer.calculate_edge_for_result(result_data)
        
        # Spread = (15.0 + 20.0) / 2 = 17.5
        assert edge_result.estimated_avg_spread_bps == 17.5
        
        # Edge = 17.5 - 2.0 = 15.5
        assert edge_result.effective_edge_bps == 15.5
        
        # Edge 15.5 > Fee 9.0 → 구조적 수익 가능
        assert edge_result.is_structurally_profitable is True
    
    def test_calculate_edge_with_zero_round_trips(self):
        """Round trip 0인 케이스 테스트"""
        analyzer = EdgeAnalyzer(
            sweep_summary_path=Path("dummy.json"),
            output_dir=Path("dummy_output"),
            fee_bps=9.0,
            estimated_notional_per_rt=20000.0
        )
        
        result_data = {
            'entry_bps': 0.5,
            'tp_bps': 1.5,
            'run_id': 'test_run_zero_rt',
            'entries': 0,
            'round_trips': 0,
            'win_rate_pct': 0.0,
            'pnl_usd': 0.0,
            'avg_buy_slippage_bps': 2.0,
            'avg_sell_slippage_bps': 2.0
        }
        
        edge_result = analyzer.calculate_edge_for_result(result_data)
        
        # Round trip 0이면 notional = 1.0 (division by zero 방지)
        # PnL bps = 0 / 1.0 * 10000 = 0
        assert edge_result.pnl_bps == 0.0


class TestEdgeAnalyzerIntegration:
    """EdgeAnalyzer 통합 테스트"""
    
    def test_analyzer_with_mock_data(self, tmp_path):
        """Mock 데이터로 전체 분석 플로우 테스트"""
        # Mock sweep summary 생성
        sweep_data = {
            'sweep_metadata': {
                'start_time': '2025-12-05T13:00:00',
                'total_runs': 2,
                'duration_per_run_sec': 360,
                'entry_bps_list': [0.3, 0.5],
                'tp_bps_list': [1.0],
                'topn_size': 20,
                'validation_profile': 'none',
                'dry_run': False,
                'end_time': '2025-12-05T13:12:00'
            },
            'results': [
                {
                    'entry_bps': 0.3,
                    'tp_bps': 1.0,
                    'run_id': 'run_1',
                    'entries': 2,
                    'round_trips': 1,
                    'win_rate_pct': 0.0,
                    'pnl_usd': -400.0,
                    'avg_buy_slippage_bps': 2.1,
                    'avg_sell_slippage_bps': 2.1
                },
                {
                    'entry_bps': 0.5,
                    'tp_bps': 1.0,
                    'run_id': 'run_2',
                    'entries': 2,
                    'round_trips': 1,
                    'win_rate_pct': 0.0,
                    'pnl_usd': -450.0,
                    'avg_buy_slippage_bps': 2.2,
                    'avg_sell_slippage_bps': 2.2
                }
            ]
        }
        
        # Mock 파일 생성
        sweep_path = tmp_path / "sweep_summary.json"
        with open(sweep_path, 'w') as f:
            json.dump(sweep_data, f)
        
        output_dir = tmp_path / "output"
        
        # Analyzer 생성 및 실행
        analyzer = EdgeAnalyzer(
            sweep_summary_path=sweep_path,
            output_dir=output_dir,
            fee_bps=9.0,
            estimated_notional_per_rt=20000.0
        )
        
        result = analyzer.analyze()
        
        # 결과 검증
        assert result is not None
        assert 'sweep_metadata' in result
        assert 'edge_analysis_results' in result
        assert 'slippage_statistics' in result
        assert 'threshold_recommendation' in result
        assert 'summary' in result
        
        # Edge 분석 결과 검증
        assert len(result['edge_analysis_results']) == 2
        
        # 슬리피지 통계 검증
        assert result['slippage_statistics']['avg'] == pytest.approx(2.15, abs=0.01)
        
        # Threshold 추천 검증
        assert len(result['threshold_recommendation']['recommended_entry_bps_list']) == 3
        assert len(result['threshold_recommendation']['recommended_tp_bps_list']) == 3
        
        # 요약 검증
        assert result['summary']['total_combinations'] == 2
        assert result['summary']['structurally_profitable_count'] == 0
        
        # 파일 저장 확인
        output_file = output_dir / "edge_analysis_summary.json"
        assert output_file.exists()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
