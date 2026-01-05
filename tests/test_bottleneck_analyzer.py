"""
D205-11-2: Bottleneck Analyzer Unit Tests

목적:
- BottleneckAnalyzer 기능 검증
- Top 3 병목 선정 확인
- 최적화 권장사항 검증

Author: arbitrage-lite V2
Date: 2026-01-05
"""

import pytest
from arbitrage.v2.observability.bottleneck_analyzer import analyze_bottleneck, BottleneckReport


class TestBottleneckAnalyzer:
    """Bottleneck Analyzer 테스트"""
    
    def test_analyze_bottleneck_basic(self):
        """Basic bottleneck analysis"""
        latency_summary = {
            "stages": {
                "RECEIVE_TICK": {"p50": 56.46, "p95": 120.5, "max": 673.42, "count": 36},
                "DECIDE": {"p50": 0.01, "p95": 0.02, "max": 0.05, "count": 36},
                "ADAPTER_PLACE": {"p50": 0.00, "p95": 0.00, "max": 0.00, "count": 0},
                "DB_RECORD": {"p50": 1.29, "p95": 2.15, "max": 5.80, "count": 36}
            },
            "e2e": {"p50": 58.0, "p95": 125.0, "max": 680.0}
        }
        
        report = analyze_bottleneck(latency_summary)
        
        assert len(report.top_3_bottlenecks) == 3
        assert report.top_3_bottlenecks[0].stage == "RECEIVE_TICK"
        assert report.top_3_bottlenecks[0].p95_ms == 120.5
        assert report.optimization_priority == "RECEIVE_TICK"
        assert report.total_e2e_p95_ms == 125.0
        
        percentage = report.top_3_bottlenecks[0].percentage
        assert percentage > 90.0
    
    def test_analyze_bottleneck_with_redis(self):
        """Bottleneck analysis with Redis stages"""
        latency_summary = {
            "stages": {
                "RECEIVE_TICK": {"p50": 20.5, "p95": 35.2, "max": 95.8, "count": 200},
                "DECIDE": {"p50": 0.01, "p95": 0.02, "max": 0.05, "count": 200},
                "ADAPTER_PLACE": {"p50": 0.00, "p95": 0.00, "max": 0.00, "count": 0},
                "DB_RECORD": {"p50": 1.20, "p95": 2.00, "max": 4.50, "count": 200},
                "REDIS_READ": {"p50": 0.50, "p95": 0.80, "max": 1.20, "count": 200},
                "REDIS_WRITE": {"p50": 0.40, "p95": 0.65, "max": 0.95, "count": 200}
            },
            "e2e": {"p50": 25.0, "p95": 40.0, "max": 105.0}
        }
        
        report = analyze_bottleneck(latency_summary)
        
        assert len(report.top_3_bottlenecks) == 3
        assert report.top_3_bottlenecks[0].stage == "RECEIVE_TICK"
        assert report.top_3_bottlenecks[1].stage == "DB_RECORD"
        assert report.optimization_priority == "RECEIVE_TICK"
    
    def test_analyze_bottleneck_empty(self):
        """Empty latency summary"""
        latency_summary = {
            "stages": {},
            "e2e": {"p50": 0.0, "p95": 0.0, "max": 0.0}
        }
        
        report = analyze_bottleneck(latency_summary)
        
        assert len(report.top_3_bottlenecks) == 0
        assert report.optimization_priority == ""
        assert report.total_e2e_p95_ms == 0.0
    
    def test_analyze_bottleneck_recommendation(self):
        """Check optimization recommendations"""
        latency_summary = {
            "stages": {
                "RECEIVE_TICK": {"p50": 56.46, "p95": 120.5, "max": 673.42, "count": 36},
                "DB_RECORD": {"p50": 5.5, "p95": 10.2, "max": 25.0, "count": 36}
            },
            "e2e": {"p50": 62.0, "p95": 130.0, "max": 700.0}
        }
        
        report = analyze_bottleneck(latency_summary)
        
        assert len(report.top_3_bottlenecks) >= 2
        
        receive_tick = report.top_3_bottlenecks[0]
        assert receive_tick.stage == "RECEIVE_TICK"
        assert "WebSocket" in receive_tick.recommendation or "캐싱" in receive_tick.recommendation
        
        db_record = report.top_3_bottlenecks[1]
        assert db_record.stage == "DB_RECORD"
        assert "Batch" in db_record.recommendation or "비동기" in db_record.recommendation
    
    def test_to_dict_serialization(self):
        """Test JSON serialization"""
        latency_summary = {
            "stages": {
                "RECEIVE_TICK": {"p50": 56.46, "p95": 120.5, "max": 673.42, "count": 36},
                "DECIDE": {"p50": 0.01, "p95": 0.02, "max": 0.05, "count": 36}
            },
            "e2e": {"p50": 58.0, "p95": 125.0, "max": 680.0}
        }
        
        report = analyze_bottleneck(latency_summary)
        result = report.to_dict()
        
        assert "top_3_bottlenecks" in result
        assert "optimization_priority" in result
        assert "total_e2e_p95_ms" in result
        
        assert isinstance(result["top_3_bottlenecks"], list)
        assert result["optimization_priority"] == "RECEIVE_TICK"
        assert result["total_e2e_p95_ms"] == 125.0
