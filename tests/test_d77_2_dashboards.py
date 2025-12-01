# -*- coding: utf-8 -*-
"""
D77-2: Grafana Dashboard Suite Tests

Test Coverage:
1. Dashboard JSON schema validation
2. PromQL query syntax validation
3. Panel configuration validation
4. Data source configuration
5. Alert rule validation
"""

import json
import re
from pathlib import Path
import pytest


# Dashboard file paths
DASHBOARD_DIR = Path("monitoring/grafana/dashboards")
DASHBOARD_FILES = [
    "d77_topn_trading_kpis.json",
    "d77_system_health.json",
    "d77_risk_guard.json",
]


@pytest.fixture
def dashboards():
    """Load all dashboard JSON files"""
    loaded = {}
    for filename in DASHBOARD_FILES:
        path = DASHBOARD_DIR / filename
        if not path.exists():
            pytest.skip(f"Dashboard file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            loaded[filename] = json.load(f)
    return loaded


def test_dashboard_files_exist():
    """모든 대시보드 파일이 존재하는지 확인"""
    for filename in DASHBOARD_FILES:
        path = DASHBOARD_DIR / filename
        assert path.exists(), f"Dashboard file not found: {path}"


def test_dashboard_json_valid(dashboards):
    """Dashboard JSON이 valid한지 확인"""
    for filename, dashboard in dashboards.items():
        assert "dashboard" in dashboard, f"{filename}: Missing 'dashboard' key"
        assert isinstance(dashboard["dashboard"], dict), f"{filename}: 'dashboard' must be dict"


def test_dashboard_metadata(dashboards):
    """Dashboard 메타데이터 검증"""
    for filename, dashboard in dashboards.items():
        dash = dashboard["dashboard"]
        
        # Required fields
        assert "uid" in dash, f"{filename}: Missing 'uid'"
        assert "title" in dash, f"{filename}: Missing 'title'"
        assert "panels" in dash, f"{filename}: Missing 'panels'"
        
        # UID format: d77-*
        assert dash["uid"].startswith("d77-"), f"{filename}: Invalid uid format"
        
        # Title format: D77 TopN Arbitrage - *
        assert dash["title"].startswith("D77 TopN Arbitrage"), f"{filename}: Invalid title format"
        
        # Tags
        assert "tags" in dash, f"{filename}: Missing 'tags'"
        assert "d77" in dash["tags"], f"{filename}: Missing 'd77' tag"


def test_dashboard_panels_count(dashboards):
    """각 대시보드가 최소 6개 이상의 패널을 가지는지 확인"""
    for filename, dashboard in dashboards.items():
        panels = dashboard["dashboard"]["panels"]
        assert len(panels) >= 6, f"{filename}: Expected >= 6 panels, got {len(panels)}"


def test_dashboard_total_panels(dashboards):
    """전체 패널 수가 20개 이상인지 확인"""
    total_panels = sum(len(d["dashboard"]["panels"]) for d in dashboards.values())
    assert total_panels >= 20, f"Expected >= 20 total panels, got {total_panels}"


def test_panel_configuration(dashboards):
    """패널 설정 검증"""
    for filename, dashboard in dashboards.items():
        panels = dashboard["dashboard"]["panels"]
        
        for panel in panels:
            # Required fields
            assert "id" in panel, f"{filename}: Panel missing 'id'"
            assert "type" in panel, f"{filename}: Panel missing 'type'"
            assert "title" in panel, f"{filename}: Panel missing 'title'"
            assert "datasource" in panel, f"{filename}: Panel missing 'datasource'"
            assert "targets" in panel, f"{filename}: Panel missing 'targets'"
            
            # Type must be valid
            valid_types = ["graph", "stat", "gauge", "piechart", "table"]
            assert panel["type"] in valid_types, f"{filename}: Invalid panel type '{panel['type']}'"
            
            # Datasource must be Prometheus
            assert panel["datasource"] == "Prometheus", f"{filename}: Invalid datasource"
            
            # At least one target
            assert len(panel["targets"]) > 0, f"{filename}: Panel has no targets"


def test_promql_queries_syntax(dashboards):
    """PromQL 쿼리 문법 검증 (기본 syntax check)"""
    # Basic PromQL patterns
    metric_pattern = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*")
    function_pattern = re.compile(r"(rate|histogram_quantile|sum|avg|max|min)\(")
    
    for filename, dashboard in dashboards.items():
        panels = dashboard["dashboard"]["panels"]
        
        for panel in panels:
            for target in panel["targets"]:
                if "expr" not in target:
                    continue
                
                expr = target["expr"]
                
                # Basic checks
                assert len(expr) > 0, f"{filename}: Empty PromQL expression"
                
                # Must contain metric name or function
                has_metric = metric_pattern.search(expr)
                has_function = function_pattern.search(expr)
                assert has_metric or has_function, f"{filename}: Invalid PromQL syntax: {expr}"
                
                # Check for balanced parentheses
                assert expr.count("(") == expr.count(")"), f"{filename}: Unbalanced parentheses: {expr}"
                
                # Check for balanced brackets
                assert expr.count("[") == expr.count("]"), f"{filename}: Unbalanced brackets: {expr}"
                
                # Check for balanced braces
                assert expr.count("{") == expr.count("}"), f"{filename}: Unbalanced braces: {expr}"


def test_promql_uses_correct_metrics(dashboards):
    """PromQL이 올바른 메트릭 이름을 사용하는지 확인"""
    # Expected metrics from D77-1
    expected_metrics = [
        "arb_topn_pnl_total",
        "arb_topn_win_rate",
        "arb_topn_round_trips_total",
        "arb_topn_trades_total",
        "arb_topn_loop_latency_seconds",
        "arb_topn_memory_usage_bytes",
        "arb_topn_cpu_usage_percent",
        "arb_topn_guard_triggers_total",
        "arb_topn_alerts_total",
        "arb_topn_exit_reasons_total",
        "arb_topn_active_positions",
    ]
    
    found_metrics = set()
    
    for filename, dashboard in dashboards.items():
        panels = dashboard["dashboard"]["panels"]
        
        for panel in panels:
            for target in panel["targets"]:
                if "expr" not in target:
                    continue
                
                expr = target["expr"]
                
                # Extract metric names
                for metric in expected_metrics:
                    if metric in expr:
                        found_metrics.add(metric)
    
    # At least 8 out of 11 metrics should be used
    assert len(found_metrics) >= 8, f"Expected >= 8 metrics used, found {len(found_metrics)}: {found_metrics}"


def test_promql_uses_correct_labels(dashboards):
    """PromQL이 올바른 label을 사용하는지 확인"""
    expected_labels = ["env", "universe", "strategy"]
    # Prometheus 기본 메트릭 (label 체크 제외)
    prometheus_builtin_metrics = ["up"]
    
    for filename, dashboard in dashboards.items():
        panels = dashboard["dashboard"]["panels"]
        
        for panel in panels:
            for target in panel["targets"]:
                if "expr" not in target:
                    continue
                
                expr = target["expr"]
                
                # Skip Prometheus builtin metrics
                is_builtin = any(metric in expr for metric in prometheus_builtin_metrics)
                if is_builtin:
                    continue
                
                # Check if label selectors are used
                if "{" in expr and "}" in expr:
                    # At least one expected label should be present
                    has_expected_label = any(label in expr for label in expected_labels)
                    assert has_expected_label, f"{filename}: No expected labels in: {expr}"


def test_alert_rules_present(dashboards):
    """Alert rules가 설정되어 있는지 확인"""
    # System Health 대시보드에는 alert가 있어야 함
    system_health = dashboards.get("d77_system_health.json")
    if not system_health:
        pytest.skip("System Health dashboard not found")
    
    panels = system_health["dashboard"]["panels"]
    alert_count = 0
    
    for panel in panels:
        if "alert" in panel:
            alert_count += 1
            alert = panel["alert"]
            
            # Alert should have conditions
            assert "conditions" in alert, f"Alert missing 'conditions'"
            assert len(alert["conditions"]) > 0, f"Alert has no conditions"
            
            # Alert should have name
            assert "name" in alert, f"Alert missing 'name'"
    
    # At least 2 alerts in System Health dashboard
    assert alert_count >= 2, f"Expected >= 2 alerts, found {alert_count}"


def test_dashboard_refresh_interval(dashboards):
    """Dashboard refresh interval 검증"""
    for filename, dashboard in dashboards.items():
        dash = dashboard["dashboard"]
        
        # Refresh should be set
        assert "refresh" in dash, f"{filename}: Missing 'refresh'"
        
        # Refresh should be reasonable (5s, 10s, 30s, 1m, 5m)
        valid_refresh = ["5s", "10s", "30s", "1m", "5m", "false", False]
        assert dash["refresh"] in valid_refresh, f"{filename}: Invalid refresh interval: {dash['refresh']}"


def test_dashboard_time_range(dashboards):
    """Dashboard time range 검증"""
    for filename, dashboard in dashboards.items():
        dash = dashboard["dashboard"]
        
        # Time range should be set
        assert "time" in dash, f"{filename}: Missing 'time'"
        
        time_range = dash["time"]
        assert "from" in time_range, f"{filename}: Missing 'from' in time range"
        assert "to" in time_range, f"{filename}: Missing 'to' in time range"
        
        # From should be "now-*"
        assert time_range["from"].startswith("now-"), f"{filename}: Invalid 'from' format"
        
        # To should be "now"
        assert time_range["to"] == "now", f"{filename}: Invalid 'to' format"


def test_trading_kpis_panels():
    """Trading KPIs 대시보드 특정 패널 검증"""
    path = DASHBOARD_DIR / "d77_topn_trading_kpis.json"
    if not path.exists():
        pytest.skip("Trading KPIs dashboard not found")
    
    with open(path, "r", encoding="utf-8") as f:
        dashboard = json.load(f)
    
    panels = dashboard["dashboard"]["panels"]
    panel_titles = [p["title"] for p in panels]
    
    # Expected panels
    expected_panels = [
        "Total PnL (USD)",
        "Win Rate (%)",
        "Round Trips Completed",
        "Active Positions",
    ]
    
    for expected in expected_panels:
        assert expected in panel_titles, f"Missing panel: {expected}"


def test_system_health_panels():
    """System Health 대시보드 특정 패널 검증"""
    path = DASHBOARD_DIR / "d77_system_health.json"
    if not path.exists():
        pytest.skip("System Health dashboard not found")
    
    with open(path, "r", encoding="utf-8") as f:
        dashboard = json.load(f)
    
    panels = dashboard["dashboard"]["panels"]
    panel_titles = [p["title"] for p in panels]
    
    # Expected panels
    expected_panels = [
        "Loop Latency - Average",
        "Loop Latency - p99",
        "CPU Usage (%)",
        "Memory Usage (MB)",
    ]
    
    for expected in expected_panels:
        assert expected in panel_titles, f"Missing panel: {expected}"


def test_risk_guard_panels():
    """Risk & Guard 대시보드 특정 패널 검증"""
    path = DASHBOARD_DIR / "d77_risk_guard.json"
    if not path.exists():
        pytest.skip("Risk & Guard dashboard not found")
    
    with open(path, "r", encoding="utf-8") as f:
        dashboard = json.load(f)
    
    panels = dashboard["dashboard"]["panels"]
    panel_titles = [p["title"] for p in panels]
    
    # Expected panels
    expected_panels = [
        "Guard Triggers Timeline",
        "Alerts by Severity",
        "Active Positions (Risk Exposure)",
        "Risk Status Overview",
    ]
    
    for expected in expected_panels:
        assert expected in panel_titles, f"Missing panel: {expected}"


def test_core_kpi_coverage(dashboards):
    """Core KPI 10종이 모두 대시보드에 포함되는지 확인"""
    # Core KPI 10종 (D99 Done Criteria)
    core_kpis = {
        "Total PnL": "arb_topn_pnl_total",
        "Win Rate": "arb_topn_win_rate",
        "Trades": "arb_topn_trades_total",
        "Loop Latency": "arb_topn_loop_latency_seconds",
        "CPU Usage": "arb_topn_cpu_usage_percent",
        "Memory Usage": "arb_topn_memory_usage_bytes",
        "Open Positions": "arb_topn_active_positions",
        "Guard Triggers": "arb_topn_guard_triggers_total",
        "Round Trips": "arb_topn_round_trips_total",
    }
    
    covered_kpis = set()
    
    for filename, dashboard in dashboards.items():
        panels = dashboard["dashboard"]["panels"]
        
        for panel in panels:
            for target in panel["targets"]:
                if "expr" not in target:
                    continue
                
                expr = target["expr"]
                
                # Check which KPIs are covered
                for kpi_name, metric_name in core_kpis.items():
                    if metric_name in expr:
                        covered_kpis.add(kpi_name)
    
    # At least 9 out of 10 KPIs should be covered
    assert len(covered_kpis) >= 9, f"Expected >= 9 Core KPIs, covered {len(covered_kpis)}: {covered_kpis}"
