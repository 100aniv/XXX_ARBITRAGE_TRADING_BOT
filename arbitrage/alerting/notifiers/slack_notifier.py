"""
Slack Webhook Notifier for Alerting System
"""

import os
import time
from typing import Optional, Dict, Any
import requests
from arbitrage.alerting.models import AlertRecord, AlertSeverity
from arbitrage.alerting.notifiers.base import NotifierBase


class SlackNotifier(NotifierBase):
    """
    Slack Webhook based notifier
    
    Features:
    - Webhook-based delivery (no bot token required)
    - Severity-based formatting with emojis
    - Retry with exponential backoff (429, 5xx errors)
    - Mockable network layer (requests.Session injection)
    - Environment variable config (SLACK_WEBHOOK_URL)
    """
    
    SEVERITY_EMOJI = {
        AlertSeverity.P0: "🔴",
        AlertSeverity.P1: "🟠",
        AlertSeverity.P2: "🟡",
        AlertSeverity.P3: "🔵"
    }
    
    SEVERITY_COLOR = {
        AlertSeverity.P0: "danger",   # Red
        AlertSeverity.P1: "warning",  # Orange
        AlertSeverity.P2: "#FFD700",  # Gold
        AlertSeverity.P3: "good"      # Green
    }
    
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        max_retries: int = 3,
        session: Optional[requests.Session] = None,
        mock_mode: bool = False
    ):
        """
        Initialize Slack notifier
        
        Args:
            webhook_url: Slack webhook URL (env: SLACK_WEBHOOK_URL if None)
            max_retries: Maximum retry attempts for 429/5xx errors
            session: requests.Session for mockable network calls
            mock_mode: If True, skip actual HTTP requests (for testing)
        """
        self.webhook_url = webhook_url or os.getenv('SLACK_WEBHOOK_URL')
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.mock_mode = mock_mode
        
    def is_available(self) -> bool:
        """Check if Slack webhook is configured"""
        return bool(self.webhook_url) or self.mock_mode
        
    def send(self, alert: AlertRecord) -> bool:
        """
        Send alert to Slack via webhook
        
        Args:
            alert: AlertRecord to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_available():
            return False
            
        if self.mock_mode:
            # Mock mode for testing
            return True
            
        payload = self._format_slack_message(alert)
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10
                )
                
                if response.status_code == 200:
                    return True
                    
                elif response.status_code == 429:
                    # Rate limit - exponential backoff
                    retry_after = int(response.headers.get('Retry-After', 2 ** attempt))
                    time.sleep(retry_after)
                    continue
                    
                elif response.status_code >= 500:
                    # Server error - retry with backoff
                    time.sleep(2 ** attempt)
                    continue
                    
                else:
                    # Client error (4xx) - don't retry
                    return False
                    
            except requests.RequestException:
                if attempt == self.max_retries - 1:
                    return False
                time.sleep(2 ** attempt)
                
        return False
        
    def _format_slack_message(self, alert: AlertRecord) -> Dict[str, Any]:
        """
        Format alert as Slack message with attachments
        
        Args:
            alert: AlertRecord to format
            
        Returns:
            Slack webhook payload (dict)
        """
        emoji = self.SEVERITY_EMOJI.get(alert.severity, "⚪")
        color = self.SEVERITY_COLOR.get(alert.severity, "#808080")
        
        # Main text
        text = f"{emoji} *[{alert.severity.value}] {alert.message}*"
        
        # Attachment fields
        fields = [
            {
                "title": "Source",
                "value": alert.source.value,
                "short": True
            },
            {
                "title": "Timestamp",
                "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "short": True
            }
        ]
        
        # Add metadata if present
        if alert.metadata:
            for key, value in alert.metadata.items():
                fields.append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value),
                    "short": True
                })
        
        payload = {
            "text": text,
            "attachments": [
                {
                    "color": color,
                    "fields": fields,
                    "footer": "Arbitrage Alert System",
                    "ts": int(alert.timestamp.timestamp())
                }
            ]
        }
        
        return payload
