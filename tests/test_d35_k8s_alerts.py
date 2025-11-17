"""
D35 Kubernetes Alert & Incident Summary Layer Tests

Tests cover:
- Incident building from history
- Alert payload generation
- Dispatch behavior (console/webhook)
- CLI integration
- Policy compliance (no fake metrics, no destructive kubectl)
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from arbitrage.k8s_alerts import (
    K8sIncident,
    K8sAlertPayload,
    AlertChannelConfig,
    K8sAlertManager,
    IncidentSeverity,
)
from arbitrage.k8s_history import K8sHealthHistoryRecord
from arbitrage.k8s_events import K8sEvent
from arbitrage.k8s_health import HealthLevel


class TestK8sIncident:
    """Test K8sIncident data structure."""

    def test_incident_creation(self):
        """Test creating a K8sIncident."""
        incident = K8sIncident(
            id="abc123",
            severity="CRITICAL",
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            current_health="ERROR",
            previous_health="OK",
            started_at="2025-11-16T10:00:00Z",
            detected_at="2025-11-16T10:05:00Z",
            summary="Error detected in Job",
            job_counts={"OK": 1, "WARN": 0, "ERROR": 1},
            recent_events=[],
        )

        assert incident.id == "abc123"
        assert incident.severity == "CRITICAL"
        assert incident.namespace == "trading-bots"
        assert incident.current_health == "ERROR"
        assert incident.previous_health == "OK"
        assert incident.job_counts["ERROR"] == 1


class TestAlertChannelConfig:
    """Test AlertChannelConfig data structure."""

    def test_console_config(self):
        """Test console channel config."""
        config = AlertChannelConfig(
            channel_type="console",
            dry_run=True,
        )

        assert config.channel_type == "console"
        assert config.dry_run is True
        assert config.webhook_url is None

    def test_webhook_config(self):
        """Test webhook channel config."""
        config = AlertChannelConfig(
            channel_type="slack_webhook",
            webhook_url="https://hooks.slack.com/services/...",
            dry_run=True,
        )

        assert config.channel_type == "slack_webhook"
        assert config.webhook_url == "https://hooks.slack.com/services/..."
        assert config.dry_run is True


class TestK8sAlertManager:
    """Test K8sAlertManager."""

    def test_manager_creation(self):
        """Test creating an alert manager."""
        config = AlertChannelConfig(channel_type="console")
        manager = K8sAlertManager(config)

        assert manager.channel_config.channel_type == "console"

    def test_build_incident_from_history_error_state(self):
        """Test building incident when latest record is ERROR."""
        config = AlertChannelConfig(channel_type="console")
        manager = K8sAlertManager(config)

        # Create history: OK -> ERROR
        history = [
            K8sHealthHistoryRecord(
                timestamp="2025-11-16T10:00:00Z",
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                overall_health="OK",
                jobs_ok=2,
                jobs_warn=0,
                jobs_error=0,
                raw_snapshot=None,
            ),
            K8sHealthHistoryRecord(
                timestamp="2025-11-16T10:05:00Z",
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                overall_health="ERROR",
                jobs_ok=1,
                jobs_warn=0,
                jobs_error=1,
                raw_snapshot=None,
            ),
        ]

        incident = manager.build_incident_from_history(history, [])

        assert incident is not None
        assert incident.severity == "CRITICAL"
        assert incident.current_health == "ERROR"
        assert incident.previous_health == "OK"
        assert incident.job_counts["ERROR"] == 1

    def test_build_incident_from_history_warn_state(self):
        """Test building incident when latest record is WARN."""
        config = AlertChannelConfig(channel_type="console")
        manager = K8sAlertManager(config)

        history = [
            K8sHealthHistoryRecord(
                timestamp="2025-11-16T10:00:00Z",
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                overall_health="OK",
                jobs_ok=2,
                jobs_warn=0,
                jobs_error=0,
                raw_snapshot=None,
            ),
            K8sHealthHistoryRecord(
                timestamp="2025-11-16T10:05:00Z",
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                overall_health="WARN",
                jobs_ok=1,
                jobs_warn=1,
                jobs_error=0,
                raw_snapshot=None,
            ),
        ]

        incident = manager.build_incident_from_history(history, [])

        assert incident is not None
        assert incident.severity == "WARN"
        assert incident.current_health == "WARN"

    def test_build_incident_from_history_ok_state(self):
        """Test that no incident is built when latest record is OK."""
        config = AlertChannelConfig(channel_type="console")
        manager = K8sAlertManager(config)

        history = [
            K8sHealthHistoryRecord(
                timestamp="2025-11-16T10:00:00Z",
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                overall_health="OK",
                jobs_ok=2,
                jobs_warn=0,
                jobs_error=0,
                raw_snapshot=None,
            ),
        ]

        incident = manager.build_incident_from_history(history, [])

        assert incident is None

    def test_build_incident_from_history_empty(self):
        """Test that no incident is built from empty history."""
        config = AlertChannelConfig(channel_type="console")
        manager = K8sAlertManager(config)

        incident = manager.build_incident_from_history([], [])

        assert incident is None

    def test_build_incident_started_at_calculation(self):
        """Test that started_at is calculated from first non-OK record."""
        config = AlertChannelConfig(channel_type="console")
        manager = K8sAlertManager(config)

        history = [
            K8sHealthHistoryRecord(
                timestamp="2025-11-16T10:00:00Z",
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                overall_health="OK",
                jobs_ok=2,
                jobs_warn=0,
                jobs_error=0,
                raw_snapshot=None,
            ),
            K8sHealthHistoryRecord(
                timestamp="2025-11-16T10:05:00Z",
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                overall_health="WARN",
                jobs_ok=1,
                jobs_warn=1,
                jobs_error=0,
                raw_snapshot=None,
            ),
            K8sHealthHistoryRecord(
                timestamp="2025-11-16T10:10:00Z",
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                overall_health="ERROR",
                jobs_ok=0,
                jobs_warn=0,
                jobs_error=2,
                raw_snapshot=None,
            ),
        ]

        incident = manager.build_incident_from_history(history, [])

        assert incident is not None
        # started_at should be from first non-OK (WARN at 10:05)
        assert incident.started_at == "2025-11-16T10:05:00Z"

    def test_build_incident_with_events(self):
        """Test that recent events are included in incident."""
        config = AlertChannelConfig(channel_type="console")
        manager = K8sAlertManager(config)

        history = [
            K8sHealthHistoryRecord(
                timestamp="2025-11-16T10:00:00Z",
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                overall_health="ERROR",
                jobs_ok=0,
                jobs_warn=0,
                jobs_error=1,
                raw_snapshot=None,
            ),
        ]

        events = [
            K8sEvent(
                type="Warning",
                reason="BackoffLimitExceeded",
                message="Job has reached backoff limit",
                involved_kind="Job",
                involved_name="arb-tuning-worker-1",
                involved_namespace="trading-bots",
                first_timestamp="2025-11-16T10:00:00Z",
                last_timestamp="2025-11-16T10:00:00Z",
                count=1,
                raw={},
            ),
        ]

        incident = manager.build_incident_from_history(history, events)

        assert incident is not None
        assert len(incident.recent_events) == 1
        assert incident.recent_events[0].reason == "BackoffLimitExceeded"

    def test_build_incident_limits_events_to_3(self):
        """Test that only last 3 events are included."""
        config = AlertChannelConfig(channel_type="console")
        manager = K8sAlertManager(config)

        history = [
            K8sHealthHistoryRecord(
                timestamp="2025-11-16T10:00:00Z",
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                overall_health="ERROR",
                jobs_ok=0,
                jobs_warn=0,
                jobs_error=1,
                raw_snapshot=None,
            ),
        ]

        events = [
            K8sEvent(
                type="Normal",
                reason="Scheduled",
                message="Pod scheduled",
                involved_kind="Pod",
                involved_name=f"pod-{i}",
                involved_namespace="trading-bots",
                first_timestamp="2025-11-16T10:00:00Z",
                last_timestamp="2025-11-16T10:00:00Z",
                count=1,
                raw={},
            )
            for i in range(10)
        ]

        incident = manager.build_incident_from_history(history, events)

        assert incident is not None
        assert len(incident.recent_events) == 3

    def test_build_alert_payload_from_incident(self):
        """Test building alert payload from incident."""
        config = AlertChannelConfig(channel_type="console")
        manager = K8sAlertManager(config)

        incident = K8sIncident(
            id="abc123",
            severity="CRITICAL",
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            current_health="ERROR",
            previous_health="OK",
            started_at="2025-11-16T10:00:00Z",
            detected_at="2025-11-16T10:05:00Z",
            summary="Error detected in Job",
            job_counts={"OK": 1, "WARN": 0, "ERROR": 1},
            recent_events=[],
        )

        payload = manager.build_alert_payload(incident)

        assert payload.title is not None
        assert "CRITICAL" in payload.title
        assert payload.severity == "CRITICAL"
        assert payload.namespace == "trading-bots"
        assert "ERROR" in payload.text
        assert payload.current_health == "ERROR"

    def test_build_alert_payload_includes_job_counts(self):
        """Test that alert payload includes job counts."""
        config = AlertChannelConfig(channel_type="console")
        manager = K8sAlertManager(config)

        incident = K8sIncident(
            id="abc123",
            severity="WARN",
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            current_health="WARN",
            previous_health="OK",
            started_at="2025-11-16T10:00:00Z",
            detected_at="2025-11-16T10:05:00Z",
            summary="Warning detected",
            job_counts={"OK": 2, "WARN": 1, "ERROR": 0},
            recent_events=[],
        )

        payload = manager.build_alert_payload(incident)

        assert "OK: 2" in payload.text
        assert "WARN: 1" in payload.text
        assert "ERROR: 0" in payload.text

    def test_build_alert_payload_includes_events(self):
        """Test that alert payload includes recent events."""
        config = AlertChannelConfig(channel_type="console")
        manager = K8sAlertManager(config)

        event = K8sEvent(
            type="Warning",
            reason="BackoffLimitExceeded",
            message="Job has reached backoff limit",
            involved_kind="Job",
            involved_name="arb-tuning-worker-1",
            involved_namespace="trading-bots",
            first_timestamp="2025-11-16T10:00:00Z",
            last_timestamp="2025-11-16T10:00:00Z",
            count=1,
            raw={},
        )

        incident = K8sIncident(
            id="abc123",
            severity="CRITICAL",
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            current_health="ERROR",
            previous_health="OK",
            started_at="2025-11-16T10:00:00Z",
            detected_at="2025-11-16T10:05:00Z",
            summary="Error detected",
            job_counts={"OK": 0, "WARN": 0, "ERROR": 1},
            recent_events=[event],
        )

        payload = manager.build_alert_payload(incident)

        assert "BackoffLimitExceeded" in payload.text
        assert "arb-tuning-worker-1" in payload.text

    def test_dispatch_console(self, capsys):
        """Test dispatching to console."""
        config = AlertChannelConfig(channel_type="console")
        manager = K8sAlertManager(config)

        payload = K8sAlertPayload(
            title="Test Alert",
            text="Test alert body",
            severity="WARN",
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            current_health="WARN",
            metadata={},
            raw_incident={},
        )

        result = manager.dispatch(payload)

        assert result is True
        captured = capsys.readouterr()
        assert "Test Alert" in captured.out

    @patch("arbitrage.k8s_alerts.requests.post")
    def test_dispatch_webhook_dry_run(self, mock_post):
        """Test webhook dispatch in dry-run mode (no HTTP call)."""
        config = AlertChannelConfig(
            channel_type="slack_webhook",
            webhook_url="https://hooks.slack.com/services/...",
            dry_run=True,
        )
        manager = K8sAlertManager(config)

        payload = K8sAlertPayload(
            title="Test Alert",
            text="Test alert body",
            severity="WARN",
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            current_health="WARN",
            metadata={},
            raw_incident={},
        )

        result = manager.dispatch(payload)

        assert result is True
        # Verify that requests.post was NOT called
        mock_post.assert_not_called()

    @patch("arbitrage.k8s_alerts.requests.post")
    def test_dispatch_webhook_actual(self, mock_post):
        """Test webhook dispatch with actual HTTP call."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        config = AlertChannelConfig(
            channel_type="slack_webhook",
            webhook_url="https://hooks.slack.com/services/...",
            dry_run=False,
        )
        manager = K8sAlertManager(config)

        payload = K8sAlertPayload(
            title="Test Alert",
            text="Test alert body",
            severity="WARN",
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            current_health="WARN",
            metadata={},
            raw_incident={},
        )

        result = manager.dispatch(payload)

        assert result is True
        # Verify that requests.post WAS called
        mock_post.assert_called_once()

    @patch("arbitrage.k8s_alerts.requests.post")
    def test_dispatch_webhook_error(self, mock_post):
        """Test webhook dispatch with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        config = AlertChannelConfig(
            channel_type="slack_webhook",
            webhook_url="https://hooks.slack.com/services/...",
            dry_run=False,
        )
        manager = K8sAlertManager(config)

        payload = K8sAlertPayload(
            title="Test Alert",
            text="Test alert body",
            severity="WARN",
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            current_health="WARN",
            metadata={},
            raw_incident={},
        )

        result = manager.dispatch(payload)

        assert result is False

    @patch("arbitrage.k8s_alerts.requests.post")
    def test_dispatch_webhook_exception(self, mock_post):
        """Test webhook dispatch with exception."""
        mock_post.side_effect = Exception("Network error")

        config = AlertChannelConfig(
            channel_type="slack_webhook",
            webhook_url="https://hooks.slack.com/services/...",
            dry_run=False,
        )
        manager = K8sAlertManager(config)

        payload = K8sAlertPayload(
            title="Test Alert",
            text="Test alert body",
            severity="WARN",
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            current_health="WARN",
            metadata={},
            raw_incident={},
        )

        result = manager.dispatch(payload)

        assert result is False

    def test_dispatch_missing_webhook_url(self):
        """Test dispatch with missing webhook URL."""
        config = AlertChannelConfig(
            channel_type="slack_webhook",
            webhook_url=None,
            dry_run=False,
        )
        manager = K8sAlertManager(config)

        payload = K8sAlertPayload(
            title="Test Alert",
            text="Test alert body",
            severity="WARN",
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            current_health="WARN",
            metadata={},
            raw_incident={},
        )

        result = manager.dispatch(payload)

        assert result is False

    def test_build_slack_payload(self):
        """Test building Slack-compatible payload."""
        config = AlertChannelConfig(channel_type="slack_webhook")
        manager = K8sAlertManager(config)

        payload = K8sAlertPayload(
            title="Test Alert",
            text="Test alert body",
            severity="CRITICAL",
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            current_health="ERROR",
            metadata={},
            raw_incident={},
        )

        slack_payload = manager._build_slack_payload(payload)

        assert "attachments" in slack_payload
        assert slack_payload["attachments"][0]["color"] == "danger"

    def test_build_generic_payload(self):
        """Test building generic webhook payload."""
        config = AlertChannelConfig(channel_type="generic_webhook")
        manager = K8sAlertManager(config)

        payload = K8sAlertPayload(
            title="Test Alert",
            text="Test alert body",
            severity="WARN",
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            current_health="WARN",
            metadata={"key": "value"},
            raw_incident={"incident_id": "abc123"},
        )

        generic_payload = manager._build_generic_payload(payload)

        assert generic_payload["alert_type"] == "k8s_health"
        assert generic_payload["severity"] == "WARN"
        assert generic_payload["metadata"]["key"] == "value"


class TestCLIIntegration:
    """Test CLI integration."""

    @patch("arbitrage.k8s_history.K8sHealthHistoryStore.load_recent")
    @patch("arbitrage.k8s_events.K8sEventCollector.load_events")
    def test_send_k8s_alerts_no_incident(self, mock_load_events, mock_load_recent):
        """Test CLI when no incident is detected."""
        from scripts.send_k8s_alerts import main

        # Mock history with only OK records
        mock_load_recent.return_value = [
            K8sHealthHistoryRecord(
                timestamp="2025-11-16T10:00:00Z",
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                overall_health="OK",
                jobs_ok=2,
                jobs_warn=0,
                jobs_error=0,
                raw_snapshot=None,
            ),
        ]

        # Mock events
        mock_event_snapshot = Mock()
        mock_event_snapshot.events = []
        mock_load_events.return_value = mock_event_snapshot

        # Mock sys.argv
        import sys

        old_argv = sys.argv
        try:
            sys.argv = [
                "send_k8s_alerts.py",
                "--history-file",
                "outputs/k8s_health_history.jsonl",
                "--namespace",
                "trading-bots",
                "--label-selector",
                "app=arbitrage-tuning",
            ]

            exit_code = main()

            assert exit_code == 0
        finally:
            sys.argv = old_argv

    @patch("arbitrage.k8s_history.K8sHealthHistoryStore.load_recent")
    @patch("arbitrage.k8s_events.K8sEventCollector.load_events")
    def test_send_k8s_alerts_with_incident(self, mock_load_events, mock_load_recent):
        """Test CLI when incident is detected."""
        from scripts.send_k8s_alerts import main

        # Mock history with ERROR record
        mock_load_recent.return_value = [
            K8sHealthHistoryRecord(
                timestamp="2025-11-16T10:00:00Z",
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                overall_health="ERROR",
                jobs_ok=0,
                jobs_warn=0,
                jobs_error=1,
                raw_snapshot=None,
            ),
        ]

        # Mock events
        mock_event_snapshot = Mock()
        mock_event_snapshot.events = []
        mock_load_events.return_value = mock_event_snapshot

        # Mock sys.argv
        import sys

        old_argv = sys.argv
        try:
            sys.argv = [
                "send_k8s_alerts.py",
                "--history-file",
                "outputs/k8s_health_history.jsonl",
                "--namespace",
                "trading-bots",
                "--label-selector",
                "app=arbitrage-tuning",
                "--channel-type",
                "console",
            ]

            exit_code = main()

            assert exit_code == 0
        finally:
            sys.argv = old_argv

    def test_send_k8s_alerts_missing_webhook_url(self):
        """Test CLI with missing webhook URL."""
        from scripts.send_k8s_alerts import main

        import sys

        old_argv = sys.argv
        try:
            sys.argv = [
                "send_k8s_alerts.py",
                "--history-file",
                "outputs/k8s_health_history.jsonl",
                "--namespace",
                "trading-bots",
                "--label-selector",
                "app=arbitrage-tuning",
                "--channel-type",
                "slack_webhook",
            ]

            exit_code = main()

            assert exit_code == 1
        finally:
            sys.argv = old_argv


class TestObservabilityPolicyD35:
    """Test Observability Policy compliance."""

    def test_no_fake_metrics_in_d35_modules(self):
        """Verify no fake/expected metrics in D35 modules."""
        import arbitrage.k8s_alerts as alerts_module
        import scripts.send_k8s_alerts as cli_module

        forbidden_strings = [
            "expected output",
            "예상 결과",
            "sample output",
            "샘플 출력",
            "sample PnL",
            "샘플 PnL",
        ]

        # Read module source with UTF-8 encoding
        alerts_source = open(alerts_module.__file__, encoding="utf-8").read()
        cli_source = open(cli_module.__file__, encoding="utf-8").read()

        for forbidden in forbidden_strings:
            assert forbidden.lower() not in alerts_source.lower()
            assert forbidden.lower() not in cli_source.lower()


class TestReadOnlyBehaviorD35:
    """Test Read-Only behavior."""

    def test_no_kubectl_mutations_in_alerts(self):
        """Verify no destructive kubectl commands in alerts module."""
        import arbitrage.k8s_alerts as alerts_module

        alerts_source = open(alerts_module.__file__, encoding="utf-8").read()

        forbidden_commands = [
            "kubectl apply",
            "kubectl delete",
            "kubectl patch",
            "kubectl scale",
            "kubectl exec",
        ]

        for cmd in forbidden_commands:
            assert cmd not in alerts_source

    def test_no_kubectl_mutations_in_cli(self):
        """Verify no destructive kubectl commands in CLI."""
        import scripts.send_k8s_alerts as cli_module

        cli_source = open(cli_module.__file__, encoding="utf-8").read()

        forbidden_commands = [
            "kubectl apply",
            "kubectl delete",
            "kubectl patch",
            "kubectl scale",
            "kubectl exec",
        ]

        for cmd in forbidden_commands:
            assert cmd not in cli_source
