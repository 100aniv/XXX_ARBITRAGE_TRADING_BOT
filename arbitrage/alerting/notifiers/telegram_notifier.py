"""Telegram notifier with mockable network calls"""

import os
from typing import Optional, Callable
from ..models import AlertRecord, AlertSeverity
from .base import NotifierBase


class TelegramNotifier(NotifierBase):
    """
    Telegram notifier
    
    Features:
    - Environment-based configuration (BOT_TOKEN, CHAT_ID)
    - Mockable send_message for testing
    - Severity-based emoji mapping
    """
    
    SEVERITY_EMOJI = {
        AlertSeverity.P0: "🚨",  # Critical
        AlertSeverity.P1: "⚠️",   # High
        AlertSeverity.P2: "⚡",   # Medium
        AlertSeverity.P3: "ℹ️",   # Low
    }
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        send_message_fn: Optional[Callable] = None,
    ):
        """
        Initialize Telegram notifier
        
        Args:
            bot_token: Telegram bot token (defaults to env TELEGRAM_BOT_TOKEN)
            chat_id: Telegram chat ID (defaults to env TELEGRAM_CHAT_ID)
            send_message_fn: Optional mock function for testing
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self._send_message_fn = send_message_fn or self._default_send_message
    
    def send(self, alert: AlertRecord) -> bool:
        """Send alert to Telegram"""
        if not self.is_available():
            return False
        
        message = self._format_message(alert)
        
        try:
            result = self._send_message_fn(
                bot_token=self.bot_token,
                chat_id=self.chat_id,
                message=message,
            )
            return result
        except Exception as e:
            print(f"Telegram send error: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if Telegram is configured"""
        return bool(self.bot_token and self.chat_id)
    
    def _format_message(self, alert: AlertRecord) -> str:
        """Format alert as Telegram message"""
        emoji = self.SEVERITY_EMOJI.get(alert.severity, "📢")
        
        lines = [
            f"{emoji} **{alert.severity.value}: {alert.title}**",
            "",
            f"**Source:** {alert.source.value}",
            f"**Time:** {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            alert.message,
        ]
        
        if alert.metadata:
            lines.append("")
            lines.append("**Metadata:**")
            for key, value in alert.metadata.items():
                lines.append(f"  - {key}: {value}")
        
        return "\n".join(lines)
    
    def _default_send_message(self, bot_token: str, chat_id: str, message: str) -> bool:
        """
        Default implementation using requests library
        
        Note: This is a placeholder. In production, use python-telegram-bot or requests.
        """
        try:
            import requests
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }
            
            response = requests.post(url, json=payload, timeout=5)
            return response.status_code == 200
        except ImportError:
            print("requests library not installed. Install with: pip install requests")
            return False
        except Exception as e:
            print(f"Telegram API error: {e}")
            return False
