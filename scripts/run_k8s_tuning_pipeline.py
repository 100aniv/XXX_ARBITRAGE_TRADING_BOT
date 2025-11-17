#!/usr/bin/env python3
"""
D36 K8s Tuning Pipeline Orchestrator CLI

Runs the full K8s tuning pipeline end-to-end:
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
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from arbitrage.k8s_pipeline import K8sTuningPipelineConfig, K8sTuningPipelineRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the pipeline CLI."""
    parser = argparse.ArgumentParser(
        description="D36 K8s Tuning Pipeline Orchestrator (Safe-by-default)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # Full pipeline, dry-run (safe default)
  python scripts/run_k8s_tuning_pipeline.py \\
    --jobs-dir outputs/d29_k8s_jobs \\
    --namespace trading-bots \\
    --label-selector app=arbitrage-tuning \\
    --history-file outputs/k8s_health_history.jsonl

  # Enable infrastructure mutations, but keep alerts in dry-run
  python scripts/run_k8s_tuning_pipeline.py \\
    --jobs-dir outputs/d29_k8s_jobs \\
    --namespace trading-bots \\
    --label-selector app=arbitrage-tuning \\
    --history-file outputs/k8s_health_history.jsonl \\
    --enable-apply

  # Enable mutations + real alerts
  python scripts/run_k8s_tuning_pipeline.py \\
    --jobs-dir outputs/d29_k8s_jobs \\
    --namespace trading-bots \\
    --label-selector app=arbitrage-tuning \\
    --history-file outputs/k8s_health_history.jsonl \\
    --enable-apply \\
    --enable-alerts \\
    --channel-type slack_webhook \\
    --webhook-url https://hooks.slack.com/services/YOUR/WEBHOOK/URL
        """,
    )

    # Required arguments
    parser.add_argument(
        "--jobs-dir",
        required=True,
        help="Directory containing K8s job YAML files (D29 output)",
    )
    parser.add_argument(
        "--namespace",
        required=True,
        help="Kubernetes namespace",
    )
    parser.add_argument(
        "--label-selector",
        required=True,
        help="Kubernetes label selector (e.g., app=arbitrage-tuning)",
    )
    parser.add_argument(
        "--history-file",
        required=True,
        help="Path to health history JSONL file (D34)",
    )

    # Optional K8s arguments
    parser.add_argument(
        "--kubeconfig",
        default=None,
        help="Path to kubeconfig file",
    )
    parser.add_argument(
        "--context",
        default=None,
        help="Kubernetes context name",
    )

    # Pipeline control flags
    parser.add_argument(
        "--enable-apply",
        action="store_true",
        default=False,
        help="Enable infrastructure mutations (default: dry-run only)",
    )
    parser.add_argument(
        "--enable-alerts",
        action="store_true",
        default=False,
        help="Enable real webhook alerts (default: console/dry-run only)",
    )
    parser.add_argument(
        "--strict-health",
        action="store_true",
        default=False,
        help="Treat WARN as failure (exit code 1)",
    )

    # Alert configuration
    parser.add_argument(
        "--channel-type",
        default="console",
        choices=["console", "slack_webhook", "generic_webhook"],
        help="Alert channel type (default: console)",
    )
    parser.add_argument(
        "--webhook-url",
        default=None,
        help="Webhook URL (required for webhook channel types)",
    )

    # Limits
    parser.add_argument(
        "--events-limit",
        type=int,
        default=20,
        help="Maximum number of events to include (default: 20)",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=20,
        help="Maximum number of history records to include (default: 20)",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.channel_type != "console" and not args.webhook_url:
        logger.error("--webhook-url is required for webhook channel types")
        return 1

    # Create config
    config = K8sTuningPipelineConfig(
        jobs_dir=args.jobs_dir,
        namespace=args.namespace,
        label_selector=args.label_selector,
        history_file=args.history_file,
        kubeconfig=args.kubeconfig,
        context=args.context,
        apply_enabled=args.enable_apply,
        alerts_enabled=args.enable_alerts,
        strict_health=args.strict_health,
        events_limit=args.events_limit,
        history_limit=args.history_limit,
        channel_type=args.channel_type,
        webhook_url=args.webhook_url,
    )

    # Log configuration
    logger.info("[D36_PIPELINE] Starting K8s Tuning Pipeline")
    logger.info(f"[D36_PIPELINE] Mode: {config.apply_enabled and 'apply' or 'dry-run'}")
    logger.info(f"[D36_PIPELINE] Alerts: {config.alerts_enabled and 'enabled' or 'disabled'}")
    logger.info(f"[D36_PIPELINE] Namespace: {config.namespace}")
    logger.info(f"[D36_PIPELINE] Label Selector: {config.label_selector}")
    logger.info(f"[D36_PIPELINE] Jobs Dir: {config.jobs_dir}")
    logger.info(f"[D36_PIPELINE] History File: {config.history_file}")

    # Run pipeline
    runner = K8sTuningPipelineRunner(config)
    result = runner.run()

    # Print summary
    print("\n" + "=" * 80)
    print("[D36_PIPELINE] SUMMARY")
    print("=" * 80)
    print(f"Mode: {result.mode}")
    print(f"Health: {result.health_status}")
    print(f"Generated Jobs: {result.generated_jobs}")
    print(f"Validated Jobs: {result.validated_jobs}")
    print(f"Applied Jobs: {result.applied_jobs}")
    print(f"Incidents Sent: {result.incidents_sent}")
    print(f"History Appended: {result.history_appended}")
    print(f"Exit Code: {result.exit_code}")
    print("\nSteps:")
    for step in result.steps:
        print(f"  - {step}")
    print("=" * 80 + "\n")

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
