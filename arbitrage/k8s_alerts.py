"""
D35 Kubernetes Alert & Incident Summary Layer (Slack/Webhook-ready, Dry-run-by-default)

This module models incidents and alert payloads, and provides an alert manager
for converting K8s health + history + events into actionable alerts.

Key concepts:
- K8sIncident: Represents a detected problem (ERROR/WARN/INFO).
- K8sAlertPayload: Human-friendly alert text suitable for Slack/webhook.
- K8sAlertManager: Builds incidents and dispatches alerts.
- AlertChannelConfig: Configures alert destination (console/webhook).

Read-only: No K8s mutations; only consumes data from D32/D33/D34.
Safe by default: dry_run=True; HTTP calls only when explicitly enabled.
"""

import json
import logging
import requests
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Literal
from hashlib import md5

from .k8s_history import K8sHealthHistoryRecord
from .k8s_events import K8sEvent
from .k8s_health import HealthLevel

logger = logging.getLogger(__name__)

IncidentSeverity = Literal["INFO", "WARN", "CRITICAL"]


@dataclass
class K8sIncident:
    """Represents a detected incident (problem or resolution)."""
    id: str                                    # e.g. timestamp + namespace + selector hash
    severity: IncidentSeverity                 # INFO, WARN, CRITICAL
    namespace: str                             # K8s namespace
    selector: str                              # label selector
    current_health: HealthLevel                # OK, WARN, ERROR
    previous_health: Optional[HealthLevel]     # previous health state
    started_at: str                            # when non-OK first detected (ISO format)
    detected_at: str                           # when this incident was detected (ISO format)
    summary: str                               # human-readable summary
    job_counts: Dict[str, int]                 # e.g. {"OK": 2, "WARN": 1, "ERROR": 0}
    recent_events: List[K8sEvent] = field(default_factory=list)  # recent K8s events


@dataclass
class AlertChannelConfig:
    """Configuration for alert dispatch channel."""
    channel_type: Literal["console", "slack_webhook", "generic_webhook"]
    webhook_url: Optional[str] = None          # required for webhook types
    timeout_seconds: int = 5
    dry_run: bool = True                       # default safe: only print payload


@dataclass
class K8sAlertPayload:
    """Human-friendly alert payload suitable for Slack/webhook."""
    title: str                                 # alert title
    text: str                                  # alert body (Markdown-like)
    severity: IncidentSeverity                 # INFO, WARN, CRITICAL
    namespace: str                             # K8s namespace
    selector: str                              # label selector
    current_health: HealthLevel                # current health state
    metadata: Dict[str, str]                   # additional metadata
    raw_incident: Dict                         # serialized incident for webhook


class K8sAlertManager:
    """Manages incident detection and alert dispatch."""

    def __init__(self, channel_config: AlertChannelConfig):
        """Initialize alert manager with channel configuration."""
        self.channel_config = channel_config
        self.logger = logging.getLogger(__name__)

    def build_incident_from_history(
        self,
        history: List[K8sHealthHistoryRecord],
        recent_events: List[K8sEvent],
    ) -> Optional[K8sIncident]:
        """
        Build an incident from recent health history and events.

        Args:
            history: Recent health history records (should be sorted by timestamp, latest last)
            recent_events: Recent K8s events

        Returns:
            K8sIncident if a non-OK state is detected, else None
        """
        if not history:
            return None

        # Get latest record
        latest = history[-1]

        # If latest is OK, check if we should report resolution (optional)
        if latest.overall_health == "OK":
            # For now, we don't generate INFO incidents for OK states
            return None

        # Map health to severity
        severity_map = {
            "ERROR": "CRITICAL",
            "WARN": "WARN",
            "OK": "INFO",
        }
        severity = severity_map.get(latest.overall_health, "INFO")

        # Find previous health state
        previous_health = None
        if len(history) > 1:
            previous_health = history[-2].overall_health

        # Approximate started_at: find first non-OK in recent history
        started_at = latest.timestamp
        for record in reversed(history):
            if record.overall_health != "OK":
                started_at = record.timestamp
            else:
                break

        # Build incident ID
        incident_id = self._build_incident_id(
            latest.namespace,
            latest.selector,
            started_at,
        )

        # Limit recent events to last 3
        limited_events = recent_events[-3:] if recent_events else []

        # Build job counts
        job_counts = {
            "OK": latest.jobs_ok,
            "WARN": latest.jobs_warn,
            "ERROR": latest.jobs_error,
        }

        # Build summary
        summary = self._build_summary(
            latest.overall_health,
            previous_health,
            job_counts,
            limited_events,
        )

        incident = K8sIncident(
            id=incident_id,
            severity=severity,
            namespace=latest.namespace,
            selector=latest.selector,
            current_health=latest.overall_health,
            previous_health=previous_health,
            started_at=started_at,
            detected_at=latest.timestamp,
            summary=summary,
            job_counts=job_counts,
            recent_events=limited_events,
        )

        return incident

    def build_alert_payload(self, incident: K8sIncident) -> K8sAlertPayload:
        """
        Convert K8sIncident into a textual alert payload.

        Args:
            incident: K8sIncident to convert

        Returns:
            K8sAlertPayload suitable for console/webhook dispatch
        """
        # Build title
        severity_emoji = {
            "CRITICAL": "🚨",
            "WARN": "⚠️",
            "INFO": "ℹ️",
        }
        emoji = severity_emoji.get(incident.severity, "")
        title = f"{emoji} K8s Alert: {incident.severity} – {incident.namespace}"

        # Build text body
        lines = [
            f"**Namespace:** {incident.namespace}",
            f"**Selector:** {incident.selector}",
            f"**Severity:** {incident.severity}",
            f"**Current Health:** {incident.current_health}",
        ]

        if incident.previous_health:
            lines.append(f"**Previous Health:** {incident.previous_health}")

        lines.append("")
        lines.append(f"**Job Counts:**")
        for status, count in incident.job_counts.items():
            lines.append(f"  - {status}: {count}")

        if incident.recent_events:
            lines.append("")
            lines.append(f"**Recent Events ({len(incident.recent_events)}):**")
            for event in incident.recent_events:
                event_line = f"  - [{event.type}] {event.reason}: {event.message}"
                if event.involved_name:
                    event_line += f" ({event.involved_name})"
                lines.append(event_line)

        lines.append("")
        lines.append(f"**Started At:** {incident.started_at}")
        lines.append(f"**Detected At:** {incident.detected_at}")
        lines.append(f"**Summary:** {incident.summary}")

        text = "\n".join(lines)

        # Build metadata
        metadata = {
            "incident_id": incident.id,
            "started_at": incident.started_at,
            "detected_at": incident.detected_at,
            "severity": incident.severity,
            "namespace": incident.namespace,
            "selector": incident.selector,
        }

        # Serialize incident for webhook
        raw_incident = asdict(incident)
        # Convert K8sEvent objects to dicts
        raw_incident["recent_events"] = [
            asdict(e) if hasattr(e, "__dataclass_fields__") else e
            for e in incident.recent_events
        ]

        payload = K8sAlertPayload(
            title=title,
            text=text,
            severity=incident.severity,
            namespace=incident.namespace,
            selector=incident.selector,
            current_health=incident.current_health,
            metadata=metadata,
            raw_incident=raw_incident,
        )

        return payload

    def dispatch(self, payload: K8sAlertPayload) -> bool:
        """
        Dispatch alert payload via configured channel.

        Args:
            payload: K8sAlertPayload to dispatch

        Returns:
            True if dispatch succeeds or dry-run, False on error
        """
        try:
            if self.channel_config.channel_type == "console":
                return self._dispatch_console(payload)
            elif self.channel_config.channel_type == "slack_webhook":
                return self._dispatch_webhook(payload, "slack")
            elif self.channel_config.channel_type == "generic_webhook":
                return self._dispatch_webhook(payload, "generic")
            else:
                self.logger.error(
                    f"Unknown channel type: {self.channel_config.channel_type}"
                )
                return False
        except Exception as e:
            self.logger.error(f"Dispatch error: {e}")
            return False

    def _dispatch_console(self, payload: K8sAlertPayload) -> bool:
        """Dispatch to console (stdout)."""
        print("\n" + "=" * 80)
        print(f"[D35_ALERT] {payload.title}")
        print("=" * 80)
        print(payload.text)
        print("=" * 80 + "\n")
        return True

    def _dispatch_webhook(self, payload: K8sAlertPayload, webhook_type: str) -> bool:
        """Dispatch to webhook (Slack or generic)."""
        if not self.channel_config.webhook_url:
            self.logger.error(f"Webhook URL not configured for {webhook_type}")
            return False

        # Build webhook payload
        if webhook_type == "slack":
            webhook_payload = self._build_slack_payload(payload)
        else:
            webhook_payload = self._build_generic_payload(payload)

        # Print what would be sent
        print(f"\n[D35_ALERT] Webhook ({webhook_type}) payload:")
        print(json.dumps(webhook_payload, indent=2))

        if self.channel_config.dry_run:
            print(f"[D35_ALERT] DRY-RUN: Would send to {self.channel_config.webhook_url}")
            return True

        # Actually send (in tests, requests.post will be mocked)
        try:
            response = requests.post(
                self.channel_config.webhook_url,
                json=webhook_payload,
                timeout=self.channel_config.timeout_seconds,
            )

            if response.status_code >= 200 and response.status_code < 300:
                self.logger.info(f"Alert sent successfully (status {response.status_code})")
                return True
            else:
                self.logger.error(
                    f"Webhook returned status {response.status_code}: {response.text}"
                )
                return False
        except Exception as e:
            self.logger.error(f"Failed to send webhook: {e}")
            return False

    def _build_slack_payload(self, payload: K8sAlertPayload) -> Dict:
        """Build Slack-compatible webhook payload."""
        color_map = {
            "CRITICAL": "danger",
            "WARN": "warning",
            "INFO": "good",
        }
        color = color_map.get(payload.severity, "good")

        return {
            "text": payload.title,
            "attachments": [
                {
                    "color": color,
                    "title": payload.title,
                    "text": payload.text,
                    "fields": [
                        {
                            "title": "Namespace",
                            "value": payload.namespace,
                            "short": True,
                        },
                        {
                            "title": "Selector",
                            "value": payload.selector,
                            "short": True,
                        },
                        {
                            "title": "Severity",
                            "value": payload.severity,
                            "short": True,
                        },
                        {
                            "title": "Health",
                            "value": payload.current_health,
                            "short": True,
                        },
                    ],
                    "footer": "D35 K8s Alert Manager",
                    "ts": int(datetime.now(timezone.utc).timestamp()),
                }
            ],
        }

    def _build_generic_payload(self, payload: K8sAlertPayload) -> Dict:
        """Build generic webhook payload."""
        return {
            "alert_type": "k8s_health",
            "title": payload.title,
            "severity": payload.severity,
            "namespace": payload.namespace,
            "selector": payload.selector,
            "current_health": payload.current_health,
            "text": payload.text,
            "metadata": payload.metadata,
            "incident": payload.raw_incident,
        }

    @staticmethod
    def _build_incident_id(namespace: str, selector: str, started_at: str) -> str:
        """Build a unique incident ID."""
        key = f"{namespace}:{selector}:{started_at}"
        return md5(key.encode()).hexdigest()[:12]

    @staticmethod
    def _build_summary(
        current_health: HealthLevel,
        previous_health: Optional[HealthLevel],
        job_counts: Dict[str, int],
        recent_events: List[K8sEvent],
    ) -> str:
        """Build a human-readable summary."""
        lines = []

        # Health transition
        if previous_health:
            lines.append(f"Health transitioned from {previous_health} to {current_health}.")
        else:
            lines.append(f"Current health is {current_health}.")

        # Job status
        total_jobs = sum(job_counts.values())
        if total_jobs > 0:
            error_count = job_counts.get("ERROR", 0)
            warn_count = job_counts.get("WARN", 0)
            if error_count > 0:
                lines.append(f"{error_count} job(s) in ERROR state.")
            if warn_count > 0:
                lines.append(f"{warn_count} job(s) in WARN state.")

        # Recent events
        if recent_events:
            warning_events = [e for e in recent_events if e.type == "Warning"]
            if warning_events:
                reasons = [e.reason for e in warning_events]
                lines.append(f"Recent warnings: {', '.join(set(reasons))}.")

        return " ".join(lines) if lines else "Health status changed."
