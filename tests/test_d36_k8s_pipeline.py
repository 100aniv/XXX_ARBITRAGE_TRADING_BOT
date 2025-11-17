"""
D36 K8s Tuning Pipeline Orchestrator Tests

Tests for:
- K8sTuningPipelineConfig
- K8sTuningPipelineResult
- K8sTuningPipelineRunner
- run_k8s_tuning_pipeline.py CLI

All subprocess calls are mocked.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from arbitrage.k8s_pipeline import (
    K8sTuningPipelineConfig,
    K8sTuningPipelineResult,
    K8sTuningPipelineRunner,
)


class TestK8sTuningPipelineConfig:
    """Test pipeline configuration."""

    def test_config_creation_minimal(self):
        """Test creating config with minimal arguments."""
        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
        )

        assert config.jobs_dir == "outputs/jobs"
        assert config.namespace == "trading-bots"
        assert config.label_selector == "app=arbitrage-tuning"
        assert config.history_file == "outputs/history.jsonl"
        assert config.apply_enabled is False
        assert config.alerts_enabled is False
        assert config.strict_health is False

    def test_config_creation_full(self):
        """Test creating config with all arguments."""
        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            kubeconfig="/home/user/.kube/config",
            context="my-cluster",
            apply_enabled=True,
            alerts_enabled=True,
            strict_health=True,
            events_limit=30,
            history_limit=50,
            channel_type="slack_webhook",
            webhook_url="https://hooks.slack.com/services/...",
        )

        assert config.apply_enabled is True
        assert config.alerts_enabled is True
        assert config.strict_health is True
        assert config.events_limit == 30
        assert config.history_limit == 50
        assert config.channel_type == "slack_webhook"
        assert config.webhook_url == "https://hooks.slack.com/services/..."


class TestK8sTuningPipelineResult:
    """Test pipeline result."""

    def test_result_creation(self):
        """Test creating result."""
        result = K8sTuningPipelineResult(
            mode="dry_run",
            generated_jobs=5,
            validated_jobs=5,
            applied_jobs=0,
            health_status="OK",
            incidents_sent=0,
            history_appended=True,
            exit_code=0,
            steps=["Step 1", "Step 2"],
        )

        assert result.mode == "dry_run"
        assert result.generated_jobs == 5
        assert result.validated_jobs == 5
        assert result.applied_jobs == 0
        assert result.health_status == "OK"
        assert result.incidents_sent == 0
        assert result.history_appended is True
        assert result.exit_code == 0
        assert len(result.steps) == 2


class TestK8sTuningPipelineRunner:
    """Test pipeline runner."""

    def test_runner_creation(self):
        """Test creating runner."""
        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
        )
        runner = K8sTuningPipelineRunner(config)

        assert runner.config == config

    def test_determine_mode_dry_run(self):
        """Test determining mode: dry_run."""
        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            apply_enabled=False,
            alerts_enabled=False,
        )
        runner = K8sTuningPipelineRunner(config)

        assert runner._determine_mode() == "dry_run"

    def test_determine_mode_apply(self):
        """Test determining mode: apply."""
        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            apply_enabled=True,
            alerts_enabled=False,
        )
        runner = K8sTuningPipelineRunner(config)

        assert runner._determine_mode() == "apply"

    def test_determine_mode_full_alerts(self):
        """Test determining mode: full_alerts."""
        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            apply_enabled=False,
            alerts_enabled=True,
        )
        runner = K8sTuningPipelineRunner(config)

        assert runner._determine_mode() == "full_alerts"

    @patch("subprocess.run")
    def test_run_happy_path_dry_run(self, mock_run):
        """Test happy path: all steps succeed, dry-run mode."""
        # Mock all subprocess calls to succeed
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            apply_enabled=False,
            alerts_enabled=False,
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml", "job-2.yaml"]):
            result = runner.run()

        assert result.exit_code == 0
        assert result.mode == "dry_run"
        assert result.health_status == "OK"
        assert result.history_appended is True
        assert len(result.steps) == 7

    @patch("subprocess.run")
    def test_run_apply_enabled(self, mock_run):
        """Test with apply_enabled=True."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            apply_enabled=True,
            alerts_enabled=False,
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml"]):
            result = runner.run()

        assert result.exit_code == 0
        assert result.mode == "apply"

        # Verify apply_k8s_jobs.py was called with --apply
        calls = [str(call) for call in mock_run.call_args_list]
        apply_call = [c for c in calls if "apply_k8s_jobs.py" in c]
        assert len(apply_call) > 0
        assert "--apply" in apply_call[0]

    @patch("subprocess.run")
    def test_run_alerts_enabled(self, mock_run):
        """Test with alerts_enabled=True."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            apply_enabled=False,
            alerts_enabled=True,
            channel_type="slack_webhook",
            webhook_url="https://hooks.slack.com/services/...",
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml"]):
            result = runner.run()

        assert result.exit_code == 0
        assert result.mode == "full_alerts"

        # Verify send_k8s_alerts.py was called with --no-dry-run
        calls = [str(call) for call in mock_run.call_args_list]
        alert_call = [c for c in calls if "send_k8s_alerts.py" in c]
        assert len(alert_call) > 0
        assert "--no-dry-run" in alert_call[0]

    @patch("subprocess.run")
    def test_run_health_warn(self, mock_run):
        """Test when health check returns WARN."""

        def mock_run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "check_k8s_health.py" in cmd_str:
                return Mock(returncode=1, stdout="", stderr="")  # WARN
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_run_side_effect

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            apply_enabled=False,
            alerts_enabled=False,
            strict_health=False,
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml"]):
            result = runner.run()

        assert result.health_status == "WARN"
        assert result.exit_code == 0  # Not strict

    @patch("subprocess.run")
    def test_run_health_warn_strict(self, mock_run):
        """Test when health check returns WARN with strict_health=True."""

        def mock_run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "check_k8s_health.py" in cmd_str:
                return Mock(returncode=1, stdout="", stderr="")  # WARN
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_run_side_effect

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            apply_enabled=False,
            alerts_enabled=False,
            strict_health=True,
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml"]):
            result = runner.run()

        assert result.health_status == "WARN"
        assert result.exit_code == 1  # Strict mode

    @patch("subprocess.run")
    def test_run_health_error(self, mock_run):
        """Test when health check returns ERROR."""

        def mock_run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "check_k8s_health.py" in cmd_str:
                return Mock(returncode=2, stdout="", stderr="")  # ERROR
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_run_side_effect

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            apply_enabled=False,
            alerts_enabled=False,
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml"]):
            result = runner.run()

        assert result.health_status == "ERROR"
        assert result.exit_code == 2

    @patch("subprocess.run")
    def test_run_generate_jobs_fails(self, mock_run):
        """Test when generate jobs step fails."""

        def mock_run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "gen_d29_k8s_jobs.py" in cmd_str:
                return Mock(returncode=1, stdout="", stderr="Generate failed")
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_run_side_effect

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
        )
        runner = K8sTuningPipelineRunner(config)

        result = runner.run()

        assert result.exit_code == 3
        assert "Generate: FAILED" in result.steps[0]

    @patch("subprocess.run")
    def test_run_validate_jobs_fails(self, mock_run):
        """Test when validate jobs step fails."""

        def mock_run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "validate_k8s_jobs.py" in cmd_str:
                return Mock(returncode=1, stdout="", stderr="Validation failed")
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_run_side_effect

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml"]):
            result = runner.run()

        assert result.exit_code == 3
        assert "Validate: FAILED" in result.steps[1]

    @patch("subprocess.run")
    def test_run_apply_jobs_fails(self, mock_run):
        """Test when apply jobs step fails."""

        def mock_run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "apply_k8s_jobs.py" in cmd_str:
                return Mock(returncode=1, stdout="", stderr="Apply failed")
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_run_side_effect

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            apply_enabled=True,
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml"]):
            result = runner.run()

        assert result.exit_code == 3
        assert "Apply: FAILED" in result.steps[2]

    @patch("subprocess.run")
    def test_run_record_history_fails(self, mock_run):
        """Test when record history step fails."""

        def mock_run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "record_k8s_health.py" in cmd_str:
                return Mock(returncode=1, stdout="", stderr="Record failed")
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_run_side_effect

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml"]):
            result = runner.run()

        assert result.exit_code == 3
        assert "History: FAILED" in result.steps[5]

    @patch("subprocess.run")
    def test_run_with_kubeconfig_and_context(self, mock_run):
        """Test that kubeconfig and context are passed to all scripts."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            kubeconfig="/home/user/.kube/config",
            context="my-cluster",
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml"]):
            result = runner.run()

        # Verify kubeconfig and context are in calls
        calls = [str(call) for call in mock_run.call_args_list]
        for call in calls:
            if "gen_d29_k8s_jobs.py" not in call:  # gen doesn't use them
                assert "--kubeconfig" in call or "gen_d29_k8s_jobs.py" in call
                assert "--context" in call or "gen_d29_k8s_jobs.py" in call

    @patch("subprocess.run")
    def test_run_monitor_non_zero_exit_non_fatal(self, mock_run):
        """Test that monitor step non-zero exit is non-fatal."""

        def mock_run_side_effect(cmd, **kwargs):
            if "watch_k8s_jobs.py" in cmd:
                return Mock(returncode=1, stdout="", stderr="Monitor warning")
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_run_side_effect

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml"]):
            result = runner.run()

        # Pipeline should continue despite monitor failure
        assert result.exit_code == 0
        assert len(result.steps) == 7

    @patch("subprocess.run")
    def test_run_alert_with_incident(self, mock_run):
        """Test alert dispatch with incident detected."""

        def mock_run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "send_k8s_alerts.py" in cmd_str:
                return Mock(returncode=0, stdout="Incident detected: CRITICAL", stderr="")
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_run_side_effect

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            alerts_enabled=True,
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml"]):
            result = runner.run()

        assert result.incidents_sent == 1

    @patch("subprocess.run")
    def test_run_exception_handling(self, mock_run):
        """Test exception handling in pipeline."""
        mock_run.side_effect = Exception("Unexpected error")

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
        )
        runner = K8sTuningPipelineRunner(config)

        result = runner.run()

        assert result.exit_code == 3
        assert "Pipeline: ERROR" in result.steps[-1]


class TestCLIIntegration:
    """Test CLI integration."""

    @patch("arbitrage.k8s_pipeline.K8sTuningPipelineRunner.run")
    def test_cli_dry_run_default(self, mock_run):
        """Test CLI with dry-run default."""
        mock_result = K8sTuningPipelineResult(
            mode="dry_run",
            generated_jobs=2,
            validated_jobs=2,
            applied_jobs=0,
            health_status="OK",
            incidents_sent=0,
            history_appended=True,
            exit_code=0,
            steps=["Step 1", "Step 2"],
        )
        mock_run.return_value = mock_result

        from scripts.run_k8s_tuning_pipeline import main

        with patch("sys.argv", [
            "run_k8s_tuning_pipeline.py",
            "--jobs-dir", "outputs/jobs",
            "--namespace", "trading-bots",
            "--label-selector", "app=arbitrage-tuning",
            "--history-file", "outputs/history.jsonl",
        ]):
            exit_code = main()

        assert exit_code == 0

    @patch("arbitrage.k8s_pipeline.K8sTuningPipelineRunner.run")
    def test_cli_enable_apply(self, mock_run):
        """Test CLI with --enable-apply."""
        mock_result = K8sTuningPipelineResult(
            mode="apply",
            generated_jobs=2,
            validated_jobs=2,
            applied_jobs=2,
            health_status="OK",
            incidents_sent=0,
            history_appended=True,
            exit_code=0,
            steps=["Step 1", "Step 2"],
        )
        mock_run.return_value = mock_result

        from scripts.run_k8s_tuning_pipeline import main

        with patch("sys.argv", [
            "run_k8s_tuning_pipeline.py",
            "--jobs-dir", "outputs/jobs",
            "--namespace", "trading-bots",
            "--label-selector", "app=arbitrage-tuning",
            "--history-file", "outputs/history.jsonl",
            "--enable-apply",
        ]):
            exit_code = main()

        assert exit_code == 0

    @patch("arbitrage.k8s_pipeline.K8sTuningPipelineRunner.run")
    def test_cli_enable_alerts(self, mock_run):
        """Test CLI with --enable-alerts."""
        mock_result = K8sTuningPipelineResult(
            mode="full_alerts",
            generated_jobs=2,
            validated_jobs=2,
            applied_jobs=0,
            health_status="OK",
            incidents_sent=1,
            history_appended=True,
            exit_code=0,
            steps=["Step 1", "Step 2"],
        )
        mock_run.return_value = mock_result

        from scripts.run_k8s_tuning_pipeline import main

        with patch("sys.argv", [
            "run_k8s_tuning_pipeline.py",
            "--jobs-dir", "outputs/jobs",
            "--namespace", "trading-bots",
            "--label-selector", "app=arbitrage-tuning",
            "--history-file", "outputs/history.jsonl",
            "--enable-alerts",
            "--channel-type", "slack_webhook",
            "--webhook-url", "https://hooks.slack.com/services/...",
        ]):
            exit_code = main()

        assert exit_code == 0

    def test_cli_missing_required_argument(self):
        """Test CLI with missing required argument."""
        from scripts.run_k8s_tuning_pipeline import main

        with patch("sys.argv", [
            "run_k8s_tuning_pipeline.py",
            "--namespace", "trading-bots",
            "--label-selector", "app=arbitrage-tuning",
            "--history-file", "outputs/history.jsonl",
        ]):
            try:
                exit_code = main()
                assert False, "Should have raised SystemExit"
            except SystemExit as e:
                assert e.code != 0

    def test_cli_webhook_url_required(self):
        """Test CLI requires webhook-url for webhook channel types."""
        from scripts.run_k8s_tuning_pipeline import main

        with patch("sys.argv", [
            "run_k8s_tuning_pipeline.py",
            "--jobs-dir", "outputs/jobs",
            "--namespace", "trading-bots",
            "--label-selector", "app=arbitrage-tuning",
            "--history-file", "outputs/history.jsonl",
            "--channel-type", "slack_webhook",
        ]):
            exit_code = main()

        assert exit_code == 1


class TestSafetyAndPolicy:
    """Test safety and policy compliance."""

    def test_no_direct_kubectl_in_pipeline_module(self):
        """Verify no direct kubectl calls in pipeline module."""
        import arbitrage.k8s_pipeline as pipeline_module

        source = open(pipeline_module.__file__, encoding="utf-8").read()

        forbidden_commands = [
            "kubectl apply",
            "kubectl delete",
            "kubectl patch",
            "kubectl scale",
            "kubectl exec",
        ]

        for cmd in forbidden_commands:
            assert cmd not in source, f"Found forbidden command: {cmd}"

    def test_no_direct_kubectl_in_cli(self):
        """Verify no direct kubectl calls in CLI."""
        import scripts.run_k8s_tuning_pipeline as cli_module

        source = open(cli_module.__file__, encoding="utf-8").read()

        forbidden_commands = [
            "kubectl apply",
            "kubectl delete",
            "kubectl patch",
            "kubectl scale",
            "kubectl exec",
        ]

        for cmd in forbidden_commands:
            assert cmd not in source, f"Found forbidden command: {cmd}"

    def test_no_fake_metrics_in_pipeline(self):
        """Verify no fake metrics in pipeline module."""
        import arbitrage.k8s_pipeline as pipeline_module

        source = open(pipeline_module.__file__, encoding="utf-8").read()

        forbidden_strings = [
            "expected output",
            "예상 결과",
            "sample output",
            "샘플 출력",
            "sample PnL",
            "샘플 PnL",
        ]

        for forbidden in forbidden_strings:
            assert forbidden.lower() not in source.lower()

    def test_no_fake_metrics_in_cli(self):
        """Verify no fake metrics in CLI."""
        import scripts.run_k8s_tuning_pipeline as cli_module

        source = open(cli_module.__file__, encoding="utf-8").read()

        forbidden_strings = [
            "expected output",
            "예상 결과",
            "sample output",
            "샘플 출력",
            "sample PnL",
            "샘플 PnL",
        ]

        for forbidden in forbidden_strings:
            assert forbidden.lower() not in source.lower()

    @patch("subprocess.run")
    def test_apply_disabled_by_default(self, mock_run):
        """Verify apply is disabled by default."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            apply_enabled=False,
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml"]):
            runner.run()

        # Verify apply_k8s_jobs.py was called WITHOUT --apply
        calls = mock_run.call_args_list
        apply_calls = [call for call in calls if "apply_k8s_jobs.py" in str(call)]
        assert len(apply_calls) > 0
        apply_cmd = apply_calls[0][0][0]  # Get the command list
        assert "--apply" not in apply_cmd

    @patch("subprocess.run")
    def test_alerts_disabled_by_default(self, mock_run):
        """Verify alerts are disabled by default."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        config = K8sTuningPipelineConfig(
            jobs_dir="outputs/jobs",
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            history_file="outputs/history.jsonl",
            alerts_enabled=False,
        )
        runner = K8sTuningPipelineRunner(config)

        with patch("os.listdir", return_value=["job-1.yaml"]):
            runner.run()

        # Verify send_k8s_alerts.py was called with --dry-run
        calls = mock_run.call_args_list
        alert_calls = [call for call in calls if "send_k8s_alerts.py" in str(call)]
        assert len(alert_calls) > 0
        alert_cmd = alert_calls[0][0][0]  # Get the command list
        assert "--dry-run" in alert_cmd


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
