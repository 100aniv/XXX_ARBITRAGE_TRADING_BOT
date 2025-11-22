"""Tests for TelegramNotifier"""

import pytest
from arbitrage.alerting import AlertSeverity, AlertSource, AlertRecord
from arbitrage.alerting.notifiers import TelegramNotifier


class TestTelegramNotifier:
    """TelegramNotifier tests"""
    
    def test_initialization_with_env(self):
        """Initialization without explicit credentials"""
        notifier = TelegramNotifier()
        # Should use environment variables (may be None)
        assert hasattr(notifier, 'bot_token')
        assert hasattr(notifier, 'chat_id')
    
    def test_initialization_with_explicit_creds(self):
        """Initialization with explicit credentials"""
        notifier = TelegramNotifier(bot_token="test_token", chat_id="test_chat_id")
        assert notifier.bot_token == "test_token"
        assert notifier.chat_id == "test_chat_id"
    
    def test_is_available_true(self):
        """Notifier available when configured"""
        notifier = TelegramNotifier(bot_token="test_token", chat_id="test_chat_id")
        assert notifier.is_available() is True
    
    def test_is_available_false(self):
        """Notifier unavailable when not configured"""
        notifier = TelegramNotifier(bot_token=None, chat_id=None)
        assert notifier.is_available() is False
    
    def test_format_message(self):
        """Format alert as Telegram message"""
        notifier = TelegramNotifier(bot_token="test", chat_id="test")
        
        alert = AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.HEALTH_MONITOR,
            title="Test Alert",
            message="This is a test",
            metadata={"exchange": "UPBIT", "status": "DOWN"},
        )
        
        message = notifier._format_message(alert)
        
        assert "🚨" in message  # P0 emoji
        assert "Test Alert" in message
        assert "HEALTH_MONITOR" in message
        assert "This is a test" in message
        assert "exchange" in message
        assert "UPBIT" in message
    
    def test_send_with_mock(self):
        """Send alert with mocked network call"""
        sent_messages = []
        
        def mock_send(bot_token, chat_id, message):
            sent_messages.append({"bot_token": bot_token, "chat_id": chat_id, "message": message})
            return True
        
        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="test_chat",
            send_message_fn=mock_send,
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.RATE_LIMITER,
            title="Rate Limit Alert",
            message="Rate limit near exhaustion",
        )
        
        result = notifier.send(alert)
        
        assert result is True
        assert len(sent_messages) == 1
        assert sent_messages[0]["bot_token"] == "test_token"
        assert sent_messages[0]["chat_id"] == "test_chat"
        assert "Rate Limit Alert" in sent_messages[0]["message"]
    
    def test_send_unavailable(self):
        """Send fails when notifier not configured"""
        notifier = TelegramNotifier(bot_token=None, chat_id=None)
        
        alert = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.SYSTEM,
            title="Test",
            message="Test",
        )
        
        result = notifier.send(alert)
        assert result is False
    
    def test_severity_emoji_mapping(self):
        """Verify severity emoji mapping"""
        assert TelegramNotifier.SEVERITY_EMOJI[AlertSeverity.P0] == "🚨"
        assert TelegramNotifier.SEVERITY_EMOJI[AlertSeverity.P1] == "⚠️"
        assert TelegramNotifier.SEVERITY_EMOJI[AlertSeverity.P2] == "⚡"
        assert TelegramNotifier.SEVERITY_EMOJI[AlertSeverity.P3] == "ℹ️"
