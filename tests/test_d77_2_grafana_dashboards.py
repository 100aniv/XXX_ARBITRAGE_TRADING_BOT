"""
D77-2: Grafana Dashboard 검증 테스트

Tests:
1. Dashboard JSON 유효성 검증
2. 필수 필드 존재 여부 확인
3. 필수 메트릭 쿼리 포함 여부 확인
4. 패널 갯수 검증
"""

import json
import os
import pytest
from pathlib import Path


# Dashboard 파일 경로
DASHBOARD_DIR = Path(__file__).parent.parent / "monitoring" / "grafana" / "dashboards"
CORE_DASHBOARD = DASHBOARD_DIR / "topn_arbitrage_core.json"
ALERTING_DASHBOARD = DASHBOARD_DIR / "alerting_overview.json"


class TestTopNArbitrageCoreDashboard:
    """TopN Arbitrage Core Dashboard 검증"""

    @pytest.fixture
    def dashboard_data(self):
        """Dashboard JSON 로드"""
        with open(CORE_DASHBOARD, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_json_valid(self, dashboard_data):
        """JSON 형식 유효성 검증"""
        assert dashboard_data is not None
        assert isinstance(dashboard_data, dict)

    def test_required_fields_exist(self, dashboard_data):
        """필수 필드 존재 확인"""
        required_fields = ["title", "panels", "templating", "uid"]
        for field in required_fields:
            assert field in dashboard_data, f"Missing required field: {field}"

    def test_dashboard_metadata(self, dashboard_data):
        """Dashboard 메타데이터 검증"""
        assert dashboard_data["title"] == "TopN Arbitrage - Core Trading Dashboard"
        assert dashboard_data["uid"] == "topn-arbitrage-core"
        assert "arbitrage" in dashboard_data.get("tags", [])
        assert "topn" in dashboard_data.get("tags", [])

    def test_minimum_panels(self, dashboard_data):
        """최소 패널 갯수 검증 (8개 이상)"""
        panels = dashboard_data.get("panels", [])
        assert len(panels) >= 8, f"Expected at least 8 panels, got {len(panels)}"

    def test_template_variables(self, dashboard_data):
        """템플릿 변수 존재 확인"""
        variables = dashboard_data.get("templating", {}).get("list", [])
        variable_names = [v["name"] for v in variables]
        
        # 필수 템플릿 변수
        assert "env" in variable_names
        assert "universe" in variable_names
        assert "strategy" in variable_names

    def test_crossexchange_metrics_in_queries(self, dashboard_data):
        """CrossExchange 메트릭이 쿼리에 포함되어 있는지 확인"""
        panels = dashboard_data.get("panels", [])
        all_queries = []
        
        for panel in panels:
            targets = panel.get("targets", [])
            for target in targets:
                expr = target.get("expr", "")
                all_queries.append(expr)
        
        # 모든 쿼리 합치기
        all_queries_text = " ".join(all_queries)
        
        # 필수 CrossExchange 메트릭
        required_metrics = [
            "arb_topn_pnl_total",
            "arb_topn_trades_total",
            "arb_topn_win_rate",
            "arb_topn_loop_latency_seconds",
            "arb_topn_guard_triggers_total",
            "arb_topn_alerts_total",
            "arb_topn_active_positions"
        ]
        
        for metric in required_metrics:
            assert metric in all_queries_text, f"Missing required metric: {metric}"

    def test_optional_metrics_in_queries(self, dashboard_data):
        """추가 메트릭 확인"""
        panels = dashboard_data.get("panels", [])
        all_queries = []
        
        for panel in panels:
            targets = panel.get("targets", [])
            for target in targets:
                expr = target.get("expr", "")
                all_queries.append(expr)
        
        all_queries_text = " ".join(all_queries)
        
        # 추가 메트릭
        optional_metrics = [
            "arb_topn_round_trips_total",
            "arb_topn_cpu_usage_percent",
            "arb_topn_memory_usage_bytes"
        ]
        
        for metric in optional_metrics:
            assert metric in all_queries_text, f"Missing optional metric: {metric}"

    def test_panel_datasources(self, dashboard_data):
        """패널의 datasource 설정 확인"""
        panels = dashboard_data.get("panels", [])
        
        for i, panel in enumerate(panels):
            datasource = panel.get("datasource", {})
            assert datasource.get("type") == "prometheus", \
                f"Panel {i} should have prometheus datasource"

    def test_panel_titles(self, dashboard_data):
        """패널 제목 존재 확인"""
        panels = dashboard_data.get("panels", [])
        
        for i, panel in enumerate(panels):
            assert "title" in panel, f"Panel {i} missing title"
            assert len(panel["title"]) > 0, f"Panel {i} has empty title"


class TestAlertingOverviewDashboard:
    """Alerting Overview Dashboard 검증"""

    @pytest.fixture
    def dashboard_data(self):
        """Dashboard JSON 로드"""
        with open(ALERTING_DASHBOARD, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_json_valid(self, dashboard_data):
        """JSON 형식 유효성 검증"""
        assert dashboard_data is not None
        assert isinstance(dashboard_data, dict)

    def test_required_fields_exist(self, dashboard_data):
        """필수 필드 존재 확인"""
        required_fields = ["title", "panels", "uid"]
        for field in required_fields:
            assert field in dashboard_data, f"Missing required field: {field}"

    def test_dashboard_metadata(self, dashboard_data):
        """Dashboard 메타데이터 검증"""
        assert dashboard_data["title"] == "Alerting & Routing - Overview Dashboard"
        assert dashboard_data["uid"] == "alerting-overview"
        assert "alerting" in dashboard_data.get("tags", [])

    def test_minimum_panels(self, dashboard_data):
        """최소 패널 갯수 검증 (6개 이상)"""
        panels = dashboard_data.get("panels", [])
        assert len(panels) >= 6, f"Expected at least 6 panels, got {len(panels)}"

    def test_alert_metrics_in_queries(self, dashboard_data):
        """Alert 메트릭이 쿼리에 포함되어 있는지 확인"""
        panels = dashboard_data.get("panels", [])
        all_queries = []
        
        for panel in panels:
            targets = panel.get("targets", [])
            for target in targets:
                expr = target.get("expr", "")
                all_queries.append(expr)
        
        # 모든 쿼리 합치기
        all_queries_text = " ".join(all_queries)
        
        # 필수 Alert 메트릭
        required_metrics = [
            "alert_sent_total",
            "alert_failed_total",
            "alert_fallback_total",
            "alert_retry_total",
            "alert_dlq_total",
            "alert_delivery_latency_seconds",
            "notifier_available"
        ]
        
        for metric in required_metrics:
            assert metric in all_queries_text, f"Missing required metric: {metric}"

    def test_notifier_labels_in_queries(self, dashboard_data):
        """Notifier 레이블이 쿼리에 포함되어 있는지 확인"""
        panels = dashboard_data.get("panels", [])
        all_queries = []
        
        for panel in panels:
            targets = panel.get("targets", [])
            for target in targets:
                expr = target.get("expr", "")
                all_queries.append(expr)
        
        all_queries_text = " ".join(all_queries)
        
        # notifier 레이블 확인 (필수는 아니지만 권장)
        assert "notifier" in all_queries_text, "Should include notifier label in queries"

    def test_panel_datasources(self, dashboard_data):
        """패널의 datasource 설정 확인"""
        panels = dashboard_data.get("panels", [])
        
        for i, panel in enumerate(panels):
            datasource = panel.get("datasource", {})
            assert datasource.get("type") == "prometheus", \
                f"Panel {i} should have prometheus datasource"

    def test_success_rate_calculation(self, dashboard_data):
        """Success rate 계산 쿼리 확인"""
        panels = dashboard_data.get("panels", [])
        
        # Success rate 패널 찾기
        success_rate_panel = None
        for panel in panels:
            if "Success Rate" in panel.get("title", ""):
                success_rate_panel = panel
                break
        
        assert success_rate_panel is not None, "Success Rate panel not found"
        
        # 쿼리 확인
        targets = success_rate_panel.get("targets", [])
        assert len(targets) > 0, "Success Rate panel should have at least one target"
        
        expr = targets[0].get("expr", "")
        assert "alert_sent_total" in expr
        assert "alert_failed_total" in expr

    def test_dlq_critical_panel(self, dashboard_data):
        """DLQ Critical Alert 패널 확인"""
        panels = dashboard_data.get("panels", [])
        
        # DLQ 패널 찾기
        dlq_panel = None
        for panel in panels:
            if "DLQ" in panel.get("title", "") or "Dead Letter" in panel.get("title", ""):
                dlq_panel = panel
                break
        
        assert dlq_panel is not None, "DLQ panel not found"
        
        # alert_dlq_total 메트릭 확인
        targets = dlq_panel.get("targets", [])
        assert len(targets) > 0
        
        expr = targets[0].get("expr", "")
        assert "alert_dlq_total" in expr


class TestDashboardIntegration:
    """Dashboard 통합 검증"""

    def test_both_dashboards_exist(self):
        """두 대시보드 파일이 모두 존재하는지 확인"""
        assert CORE_DASHBOARD.exists(), f"Core dashboard not found: {CORE_DASHBOARD}"
        assert ALERTING_DASHBOARD.exists(), f"Alerting dashboard not found: {ALERTING_DASHBOARD}"

    def test_dashboard_file_sizes(self):
        """Dashboard 파일 크기가 적절한지 확인"""
        core_size = os.path.getsize(CORE_DASHBOARD)
        alerting_size = os.path.getsize(ALERTING_DASHBOARD)
        
        # 최소 크기 (1KB 이상)
        assert core_size > 1024, f"Core dashboard too small: {core_size} bytes"
        assert alerting_size > 1024, f"Alerting dashboard too small: {alerting_size} bytes"
        
        # 최대 크기 (1MB 이하, 너무 크면 문제)
        assert core_size < 1024 * 1024, f"Core dashboard too large: {core_size} bytes"
        assert alerting_size < 1024 * 1024, f"Alerting dashboard too large: {alerting_size} bytes"

    def test_unique_uids(self):
        """Dashboard UID가 고유한지 확인"""
        with open(CORE_DASHBOARD, "r", encoding="utf-8") as f:
            core_data = json.load(f)
        
        with open(ALERTING_DASHBOARD, "r", encoding="utf-8") as f:
            alerting_data = json.load(f)
        
        core_uid = core_data.get("uid")
        alerting_uid = alerting_data.get("uid")
        
        assert core_uid != alerting_uid, "Dashboard UIDs must be unique"
        assert core_uid is not None and len(core_uid) > 0
        assert alerting_uid is not None and len(alerting_uid) > 0

    def test_consistent_refresh_intervals(self):
        """Refresh interval이 설정되어 있는지 확인"""
        with open(CORE_DASHBOARD, "r", encoding="utf-8") as f:
            core_data = json.load(f)
        
        with open(ALERTING_DASHBOARD, "r", encoding="utf-8") as f:
            alerting_data = json.load(f)
        
        # Refresh가 설정되어 있어야 함
        assert "refresh" in core_data
        assert "refresh" in alerting_data

    def test_metrics_coverage(self):
        """모든 D77-1 메트릭이 대시보드에 포함되어 있는지 확인"""
        with open(CORE_DASHBOARD, "r", encoding="utf-8") as f:
            core_data = json.load(f)
        
        with open(ALERTING_DASHBOARD, "r", encoding="utf-8") as f:
            alerting_data = json.load(f)
        
        # Core Dashboard: CrossExchange 메트릭
        core_panels = core_data.get("panels", [])
        core_queries = []
        for panel in core_panels:
            for target in panel.get("targets", []):
                core_queries.append(target.get("expr", ""))
        
        core_queries_text = " ".join(core_queries)
        
        # Alerting Dashboard: Alert 메트릭
        alerting_panels = alerting_data.get("panels", [])
        alerting_queries = []
        for panel in alerting_panels:
            for target in panel.get("targets", []):
                alerting_queries.append(target.get("expr", ""))
        
        alerting_queries_text = " ".join(alerting_queries)
        
        # D77-1에서 정의한 메트릭들이 모두 포함되어 있는지 확인
        crossexchange_metrics = [
            "arb_topn_pnl_total",
            "arb_topn_trades_total",
            "arb_topn_round_trips_total",
            "arb_topn_win_rate",
            "arb_topn_loop_latency_seconds",
            "arb_topn_memory_usage_bytes",
            "arb_topn_cpu_usage_percent",
            "arb_topn_guard_triggers_total",
            "arb_topn_alerts_total",
            "arb_topn_active_positions"
        ]
        
        alert_metrics = [
            "alert_sent_total",
            "alert_failed_total",
            "alert_fallback_total",
            "alert_retry_total",
            "alert_dlq_total",
            "alert_delivery_latency_seconds",
            "notifier_available"
        ]
        
        # CrossExchange 메트릭 검증
        for metric in crossexchange_metrics:
            assert metric in core_queries_text, \
                f"CrossExchange metric '{metric}' not found in Core Dashboard"
        
        # Alert 메트릭 검증
        for metric in alert_metrics:
            assert metric in alerting_queries_text, \
                f"Alert metric '{metric}' not found in Alerting Dashboard"
