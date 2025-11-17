#!/usr/bin/env python3
"""
D35 Send Kubernetes Alerts CLI

This script:
1. Loads recent health history from K8sHealthHistoryStore (D34)
2. Optionally loads recent events using K8sEventCollector (D34)
3. Constructs an incident (if any)
4. Builds an alert payload
5. Dispatches via configured channel (console/slack/webhook)

Usage:
    # Console-only, dry-run style (default)
    python scripts/send_k8s_alerts.py \
      --history-file outputs/k8s_health_history.jsonl \
      --namespace trading-bots \
      --label-selector app=arbitrage-tuning

    # Slack webhook, but dry-run (no real HTTP)
    python scripts/send_k8s_alerts.py \
      --history-file outputs/k8s_health_history.jsonl \
      --namespace trading-bots \
      --label-selector app=arbitrage-tuning \
      --channel-type slack_webhook \
      --webhook-url https://hooks.slack.com/services/...

    # Slack webhook, actually send (user responsibility)
    python scripts/send_k8s_alerts.py \
      --history-file outputs/k8s_health_history.jsonl \
      --namespace trading-bots \
      --label-selector app=arbitrage-tuning \
      --channel-type slack_webhook \
      --webhook-url https://hooks.slack.com/services/... \
      --no-dry-run

Exit codes:
    0: Alert dispatched successfully or no incident detected (dry-run)
    1: Error (dispatch failed, missing config, etc.)
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.k8s_history import K8sHealthHistoryStore
from arbitrage.k8s_events import K8sEventCollector
from arbitrage.k8s_alerts import K8sAlertManager, AlertChannelConfig

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Send Kubernetes health alerts via console/webhook"
    )

    # Required arguments
    parser.add_argument(
        "--history-file",
        required=True,
        help="Path to K8s health history JSONL file (from D34)",
    )
    parser.add_argument(
        "--namespace",
        required=True,
        help="Kubernetes namespace",
    )
    parser.add_argument(
        "--label-selector",
        required=True,
        help="Label selector for filtering events",
    )

    # Optional arguments
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry-run mode (default: True, no real HTTP calls)",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_false",
        dest="dry_run",
        help="Disable dry-run mode (actually send alerts)",
    )
    parser.add_argument(
        "--events-limit",
        type=int,
        default=10,
        help="Limit number of events included in alert (default: 10)",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=20,
        help="Limit number of recent history records to consider (default: 20)",
    )
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

    args = parser.parse_args()

    # Validate webhook URL if needed
    if args.channel_type in ["slack_webhook", "generic_webhook"]:
        if not args.webhook_url:
            logger.error(
                f"--webhook-url is required for channel-type {args.channel_type}"
            )
            return 1

    try:
        logger.info("[D35_SEND] Starting K8s Alert Dispatch")
        logger.info(f"[D35_SEND] History File: {args.history_file}")
        logger.info(f"[D35_SEND] Namespace: {args.namespace}")
        logger.info(f"[D35_SEND] Label Selector: {args.label_selector}")
        logger.info(f"[D35_SEND] Channel Type: {args.channel_type}")
        logger.info(f"[D35_SEND] Dry-run: {args.dry_run}")

        # Load history
        logger.info("[D35_SEND] Loading health history...")
        history_store = K8sHealthHistoryStore(args.history_file)
        history = history_store.load_recent(limit=args.history_limit)

        if not history:
            logger.info("[D35_SEND] No history records found")
            print("\n[D35_SEND] No incident detected; health history is empty.\n")
            return 0

        logger.info(f"[D35_SEND] Loaded {len(history)} history records")

        # Load events
        logger.info("[D35_SEND] Loading recent events...")
        event_collector = K8sEventCollector(
            namespace=args.namespace,
            label_selector=args.label_selector,
            kubeconfig=args.kubeconfig,
            context=args.context,
        )
        event_snapshot = event_collector.load_events()
        recent_events = event_snapshot.events[-args.events_limit :]

        logger.info(f"[D35_SEND] Loaded {len(recent_events)} events")

        # Build incident
        logger.info("[D35_SEND] Building incident from history...")
        channel_config = AlertChannelConfig(
            channel_type=args.channel_type,
            webhook_url=args.webhook_url,
            dry_run=args.dry_run,
        )
        alert_manager = K8sAlertManager(channel_config)

        incident = alert_manager.build_incident_from_history(history, recent_events)

        if not incident:
            logger.info("[D35_SEND] No incident detected; health is OK")
            print("\n[D35_SEND] No incident detected; health OK.\n")
            return 0

        logger.info(f"[D35_SEND] Incident detected: {incident.severity}")

        # Build payload
        logger.info("[D35_SEND] Building alert payload...")
        payload = alert_manager.build_alert_payload(incident)

        # Dispatch
        logger.info("[D35_SEND] Dispatching alert...")
        success = alert_manager.dispatch(payload)

        if success:
            logger.info("[D35_SEND] Alert dispatch completed successfully")
            return 0
        else:
            logger.error("[D35_SEND] Alert dispatch failed")
            return 1

    except Exception as e:
        logger.error(f"[D35_SEND] Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
