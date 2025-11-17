"""
D36 Kubernetes Tuning Pipeline Orchestrator (Safe-by-default)

Coordinates D29–D35 scripts into a single repeatable pipeline:
- Generate jobs (D29)
- Validate jobs (D30)
- Apply jobs (D31, optional)
- Monitor jobs (D32)
- Evaluate health (D33)
- Record history (D34)
- Send alerts (D35, optional)

Safe-by-default:
- No infrastructure mutations unless --enable-apply
- No real webhooks unless --enable-alerts
- All subprocess calls are mockable in tests
- No direct cluster mutations
"""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional

logger = logging.getLogger(__name__)

PipelineMode = Literal["dry_run", "apply", "full_alerts"]


@dataclass
class K8sTuningPipelineConfig:
    """Configuration for the K8s tuning pipeline."""

    jobs_dir: str
    namespace: str
    label_selector: str
    history_file: str
    kubeconfig: Optional[str] = None
    context: Optional[str] = None
    apply_enabled: bool = False  # if False → D31 runs dry-run
    alerts_enabled: bool = False  # if False → D35 in console/dry-run mode
    strict_health: bool = False  # pass through to D33/D34
    events_limit: int = 20
    history_limit: int = 20
    channel_type: str = "console"  # for D35
    webhook_url: Optional[str] = None  # for D35


@dataclass
class K8sTuningPipelineResult:
    """Result of a pipeline run."""

    mode: PipelineMode
    generated_jobs: int
    validated_jobs: int
    applied_jobs: int
    health_status: str  # "OK" | "WARN" | "ERROR"
    incidents_sent: int
    history_appended: bool
    exit_code: int
    steps: List[str] = field(default_factory=list)  # textual summary


class K8sTuningPipelineRunner:
    """Orchestrates the K8s tuning pipeline."""

    def __init__(self, config: K8sTuningPipelineConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def run(self) -> K8sTuningPipelineResult:
        """
        Run the full pipeline:
        1. Generate jobs (D29)
        2. Validate jobs (D30)
        3. Apply jobs (D31, optional)
        4. Monitor jobs (D32)
        5. Evaluate health (D33)
        6. Record history (D34)
        7. Send alerts (D35, optional)

        Returns:
            K8sTuningPipelineResult with overall status and per-step summaries.
        """
        result = K8sTuningPipelineResult(
            mode=self._determine_mode(),
            generated_jobs=0,
            validated_jobs=0,
            applied_jobs=0,
            health_status="OK",
            incidents_sent=0,
            history_appended=False,
            exit_code=0,
            steps=[],
        )

        try:
            # Step 1: Generate jobs (D29)
            self.logger.info("[D36] Step 1: Generate jobs (D29)")
            gen_result = self._run_generate_jobs()
            if gen_result["exit_code"] != 0:
                self.logger.error(f"[D36] Generate jobs failed: {gen_result['exit_code']}")
                result.exit_code = 3
                result.steps.append(f"Generate: FAILED (exit {gen_result['exit_code']})")
                return result
            result.generated_jobs = gen_result.get("count", 0)
            result.steps.append(f"Generate: {result.generated_jobs} jobs created")

            # Step 2: Validate jobs (D30)
            self.logger.info("[D36] Step 2: Validate jobs (D30)")
            val_result = self._run_validate_jobs()
            if val_result["exit_code"] != 0:
                self.logger.error(f"[D36] Validate jobs failed: {val_result['exit_code']}")
                result.exit_code = 3
                result.steps.append(f"Validate: FAILED (exit {val_result['exit_code']})")
                return result
            result.validated_jobs = val_result.get("count", 0)
            result.steps.append(f"Validate: {result.validated_jobs} jobs validated")

            # Step 3: Apply jobs (D31, optional)
            self.logger.info(f"[D36] Step 3: Apply jobs (D31) - apply_enabled={self.config.apply_enabled}")
            apply_result = self._run_apply_jobs()
            if apply_result["exit_code"] != 0:
                self.logger.error(f"[D36] Apply jobs failed: {apply_result['exit_code']}")
                result.exit_code = 3
                result.steps.append(f"Apply: FAILED (exit {apply_result['exit_code']})")
                return result
            result.applied_jobs = apply_result.get("count", 0)
            mode_str = "apply" if self.config.apply_enabled else "dry-run"
            result.steps.append(f"Apply: {result.applied_jobs} jobs ({mode_str})")

            # Step 4: Monitor jobs (D32)
            self.logger.info("[D36] Step 4: Monitor jobs (D32)")
            monitor_result = self._run_monitor_jobs()
            if monitor_result["exit_code"] != 0:
                self.logger.warning(f"[D36] Monitor jobs returned non-zero: {monitor_result['exit_code']}")
                # Don't fail the pipeline on monitor; it's informational
            result.steps.append(f"Monitor: snapshot captured")

            # Step 5: Evaluate health (D33)
            self.logger.info("[D36] Step 5: Evaluate health (D33)")
            health_result = self._run_check_health()
            if health_result["exit_code"] not in [0, 1, 2]:
                self.logger.error(f"[D36] Check health failed: {health_result['exit_code']}")
                result.exit_code = 3
                result.steps.append(f"Health: FAILED (exit {health_result['exit_code']})")
                return result
            result.health_status = health_result.get("health", "OK")
            result.steps.append(f"Health: {result.health_status}")

            # Step 6: Record history (D34)
            self.logger.info("[D36] Step 6: Record history (D34)")
            history_result = self._run_record_history()
            if history_result["exit_code"] != 0:
                self.logger.error(f"[D36] Record history failed: {history_result['exit_code']}")
                result.exit_code = 3
                result.steps.append(f"History: FAILED (exit {history_result['exit_code']})")
                return result
            result.history_appended = history_result.get("appended", False)
            result.steps.append(f"History: appended to {self.config.history_file}")

            # Step 7: Send alerts (D35, optional)
            self.logger.info(f"[D36] Step 7: Send alerts (D35) - alerts_enabled={self.config.alerts_enabled}")
            alert_result = self._run_send_alerts()
            if alert_result["exit_code"] not in [0, 1]:
                self.logger.error(f"[D36] Send alerts failed: {alert_result['exit_code']}")
                result.exit_code = 3
                result.steps.append(f"Alerts: FAILED (exit {alert_result['exit_code']})")
                return result
            result.incidents_sent = alert_result.get("incidents", 0)
            result.steps.append(f"Alerts: {result.incidents_sent} incident(s) sent")

            # Determine final exit code based on health
            if result.health_status == "ERROR":
                result.exit_code = 2
            elif result.health_status == "WARN" and self.config.strict_health:
                result.exit_code = 1
            else:
                result.exit_code = 0

        except Exception as e:
            self.logger.error(f"[D36] Pipeline error: {e}", exc_info=True)
            result.exit_code = 3
            result.steps.append(f"Pipeline: ERROR ({e})")

        return result

    def _determine_mode(self) -> PipelineMode:
        """Determine the pipeline mode based on config."""
        if self.config.alerts_enabled:
            return "full_alerts"
        elif self.config.apply_enabled:
            return "apply"
        else:
            return "dry_run"

    def _run_generate_jobs(self) -> dict:
        """Run D29 generate jobs script."""
        cmd = [
            "python",
            "scripts/gen_d29_k8s_jobs.py",
            "--orchestrator-config",
            "configs/d29_k8s/orchestrator_k8s_baseline.yaml",
            "--output-dir",
            self.config.jobs_dir,
        ]
        if self.config.kubeconfig:
            cmd.extend(["--kubeconfig", self.config.kubeconfig])
        if self.config.context:
            cmd.extend(["--context", self.config.context])

        self.logger.info(f"[D36] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.logger.info(f"[D36] Generate jobs exit code: {result.returncode}")

        count = 0
        if result.returncode == 0:
            # Try to count generated files
            try:
                import os

                count = len([f for f in os.listdir(self.config.jobs_dir) if f.endswith(".yaml")])
            except Exception:
                count = 0

        return {"exit_code": result.returncode, "count": count, "stdout": result.stdout, "stderr": result.stderr}

    def _run_validate_jobs(self) -> dict:
        """Run D30 validate jobs script."""
        cmd = [
            "python",
            "scripts/validate_k8s_jobs.py",
            "--jobs-dir",
            self.config.jobs_dir,
        ]
        if self.config.kubeconfig:
            cmd.extend(["--kubeconfig", self.config.kubeconfig])
        if self.config.context:
            cmd.extend(["--context", self.config.context])

        self.logger.info(f"[D36] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.logger.info(f"[D36] Validate jobs exit code: {result.returncode}")

        count = 0
        if result.returncode == 0:
            # Try to count validated files
            try:
                import os

                count = len([f for f in os.listdir(self.config.jobs_dir) if f.endswith(".yaml")])
            except Exception:
                count = 0

        return {"exit_code": result.returncode, "count": count, "stdout": result.stdout, "stderr": result.stderr}

    def _run_apply_jobs(self) -> dict:
        """Run D31 apply jobs script."""
        cmd = [
            "python",
            "scripts/apply_k8s_jobs.py",
            "--jobs-dir",
            self.config.jobs_dir,
        ]

        if self.config.apply_enabled:
            cmd.append("--apply")
        # else: default is dry-run

        if self.config.kubeconfig:
            cmd.extend(["--kubeconfig", self.config.kubeconfig])
        if self.config.context:
            cmd.extend(["--context", self.config.context])

        self.logger.info(f"[D36] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.logger.info(f"[D36] Apply jobs exit code: {result.returncode}")

        count = 0
        if result.returncode == 0:
            # Try to count applied files
            try:
                import os

                count = len([f for f in os.listdir(self.config.jobs_dir) if f.endswith(".yaml")])
            except Exception:
                count = 0

        return {"exit_code": result.returncode, "count": count, "stdout": result.stdout, "stderr": result.stderr}

    def _run_monitor_jobs(self) -> dict:
        """Run D32 monitor jobs script (one-shot)."""
        cmd = [
            "python",
            "scripts/watch_k8s_jobs.py",
            "--namespace",
            self.config.namespace,
            "--label-selector",
            self.config.label_selector,
            "--one-shot",
        ]

        if self.config.kubeconfig:
            cmd.extend(["--kubeconfig", self.config.kubeconfig])
        if self.config.context:
            cmd.extend(["--context", self.config.context])

        self.logger.info(f"[D36] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.logger.info(f"[D36] Monitor jobs exit code: {result.returncode}")

        return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

    def _run_check_health(self) -> dict:
        """Run D33 check health script."""
        cmd = [
            "python",
            "scripts/check_k8s_health.py",
            "--namespace",
            self.config.namespace,
            "--label-selector",
            self.config.label_selector,
        ]

        if self.config.strict_health:
            cmd.append("--strict")

        if self.config.kubeconfig:
            cmd.extend(["--kubeconfig", self.config.kubeconfig])
        if self.config.context:
            cmd.extend(["--context", self.config.context])

        self.logger.info(f"[D36] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.logger.info(f"[D36] Check health exit code: {result.returncode}")

        # Map exit code to health status
        health_map = {0: "OK", 1: "WARN", 2: "ERROR"}
        health_status = health_map.get(result.returncode, "UNKNOWN")

        return {
            "exit_code": result.returncode,
            "health": health_status,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _run_record_history(self) -> dict:
        """Run D34 record history script."""
        cmd = [
            "python",
            "scripts/record_k8s_health.py",
            "--namespace",
            self.config.namespace,
            "--label-selector",
            self.config.label_selector,
            "--history-file",
            self.config.history_file,
        ]

        if self.config.kubeconfig:
            cmd.extend(["--kubeconfig", self.config.kubeconfig])
        if self.config.context:
            cmd.extend(["--context", self.config.context])

        self.logger.info(f"[D36] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.logger.info(f"[D36] Record history exit code: {result.returncode}")

        appended = result.returncode == 0

        return {
            "exit_code": result.returncode,
            "appended": appended,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _run_send_alerts(self) -> dict:
        """Run D35 send alerts script."""
        cmd = [
            "python",
            "scripts/send_k8s_alerts.py",
            "--history-file",
            self.config.history_file,
            "--namespace",
            self.config.namespace,
            "--label-selector",
            self.config.label_selector,
            "--channel-type",
            self.config.channel_type,
        ]

        if self.config.webhook_url:
            cmd.extend(["--webhook-url", self.config.webhook_url])

        if self.config.alerts_enabled:
            cmd.append("--no-dry-run")
        else:
            cmd.append("--dry-run")

        if self.config.kubeconfig:
            cmd.extend(["--kubeconfig", self.config.kubeconfig])
        if self.config.context:
            cmd.extend(["--context", self.config.context])

        self.logger.info(f"[D36] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.logger.info(f"[D36] Send alerts exit code: {result.returncode}")

        # Try to extract incident count from stdout
        incidents = 0
        if "Incident detected" in result.stdout:
            incidents = 1

        return {
            "exit_code": result.returncode,
            "incidents": incidents,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
