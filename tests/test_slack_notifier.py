"""
Tests for SlackNotifier
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
import requests
from arbitrage.alerting.models import AlertRecord, AlertSeverity, AlertSource
from arbitrage.alerting.notifiers.slack_notifier import SlackNotifier


class TestSlackNotifier:
    """Test suite for Slack webhook notifier"""
    
    def test_initialization_with_env(self):
        """Test initialization with environment variable"""
        with patch.dict('os.environ', {'SLACK_WEBHOOK_URL': 'https://hooks.slack.com/test'}):
            notifier = SlackNotifier()
            assert notifier.webhook_url == 'https://hooks.slack.com/test'
            assert notifier.max_retries == 3
            
    def test_initialization_with_explicit_webhook(self):
        """Test initialization with explicit webhook URL"""
        webhook = 'https://hooks.slack.com/explicit'
        notifier = SlackNotifier(webhook_url=webhook)
        assert notifier.webhook_url == webhook
        
    def test_is_available_true(self):
        """Test is_available returns True when webhook configured"""
        notifier = SlackNotifier(webhook_url='https://hooks.slack.com/test')
        assert notifier.is_available() is True
        
    def test_is_available_false(self):
        """Test is_available returns False without webhook"""
        with patch.dict('os.environ', {}, clear=True):
            notifier = SlackNotifier()
            assert notifier.is_available() is False
            
    def test_is_available_mock_mode(self):
        """Test is_available returns True in mock mode"""
        notifier = SlackNotifier(mock_mode=True)
        assert notifier.is_available() is True
        
    def test_format_slack_message(self):
        """Test Slack message formatting"""
        notifier = SlackNotifier(webhook_url='https://test.com')
        
        alert = AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.RATE_LIMITER,
            title="Test Alert",
            message="Test alert",
            timestamp=datetime(2025, 1, 22, 12, 0, 0),
            metadata={"exchange": "upbit", "count": 10}
        )
        
        payload = notifier._format_slack_message(alert)
        
        assert "🔴" in payload["text"]
        assert "[P0]" in payload["text"]
        assert "Test alert" in payload["text"]
        assert payload["attachments"][0]["color"] == "danger"
        assert len(payload["attachments"][0]["fields"]) >= 2
        
    def test_send_with_mock_mode(self):
        """Test send in mock mode (no actual HTTP)"""
        notifier = SlackNotifier(mock_mode=True)
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.EXCHANGE_HEALTH,
            title="Test",
            message="Test",
            timestamp=datetime.now()
        )
        
        result = notifier.send(alert)
        assert result is True
        
    def test_send_success_200(self):
        """Test successful send (200 OK)"""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        
        notifier = SlackNotifier(
            webhook_url='https://hooks.slack.com/test',
            session=mock_session
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.ARB_ROUTE,
            title="Test",
            message="Test",
            timestamp=datetime.now()
        )
        
        result = notifier.send(alert)
        assert result is True
        mock_session.post.assert_called_once()
        
    def test_send_rate_limit_429_with_retry(self):
        """Test retry on 429 rate limit"""
        mock_session = Mock()
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {'Retry-After': '1'}
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        
        # First call returns 429, second call returns 200
        mock_session.post.side_effect = [mock_response_429, mock_response_200]
        
        notifier = SlackNotifier(
            webhook_url='https://hooks.slack.com/test',
            session=mock_session,
            max_retries=3
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.RISK_GUARD,
            title="Test",
            message="Test",
            timestamp=datetime.now()
        )
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = notifier.send(alert)
            
        assert result is True
        assert mock_session.post.call_count == 2
        
    def test_send_server_error_5xx_retry(self):
        """Test retry on 5xx server errors"""
        mock_session = Mock()
        mock_response_500 = Mock()
        mock_response_500.status_code = 500
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        
        mock_session.post.side_effect = [mock_response_500, mock_response_200]
        
        notifier = SlackNotifier(
            webhook_url='https://hooks.slack.com/test',
            session=mock_session
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.CROSS_SYNC,
            title="Test",
            message="Test",
            timestamp=datetime.now()
        )
        
        with patch('time.sleep'):
            result = notifier.send(alert)
            
        assert result is True
        assert mock_session.post.call_count == 2
        
    def test_send_client_error_4xx_no_retry(self):
        """Test no retry on 4xx client errors"""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 400
        mock_session.post.return_value = mock_response
        
        notifier = SlackNotifier(
            webhook_url='https://hooks.slack.com/test',
            session=mock_session
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P3,
            source=AlertSource.ARB_UNIVERSE,
            title="Test",
            message="Test",
            timestamp=datetime.now()
        )
        
        result = notifier.send(alert)
        assert result is False
        assert mock_session.post.call_count == 1
        
    def test_send_network_exception_with_retry(self):
        """Test retry on network exceptions"""
        mock_session = Mock()
        mock_session.post.side_effect = [
            requests.RequestException("Network error"),
            Mock(status_code=200)
        ]
        
        notifier = SlackNotifier(
            webhook_url='https://hooks.slack.com/test',
            session=mock_session
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.RATE_LIMITER,
            title="Test",
            message="Test",
            timestamp=datetime.now()
        )
        
        with patch('time.sleep'):
            result = notifier.send(alert)
            
        assert result is True
        assert mock_session.post.call_count == 2
        
    def test_send_unavailable(self):
        """Test send returns False when unavailable"""
        notifier = SlackNotifier()  # No webhook configured
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.EXCHANGE_HEALTH,
            title="Test",
            message="Test",
            timestamp=datetime.now()
        )
        
        result = notifier.send(alert)
        assert result is False
        
    def test_severity_emoji_mapping(self):
        """Test all severity levels have emoji mappings"""
        notifier = SlackNotifier(webhook_url='https://test.com')
        
        for severity in AlertSeverity:
            assert severity in SlackNotifier.SEVERITY_EMOJI
            assert severity in SlackNotifier.SEVERITY_COLOR


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
