"""
Tests for EmailNotifier
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from arbitrage.alerting.models import AlertRecord, AlertSeverity, AlertSource
from arbitrage.alerting.notifiers.email_notifier import EmailNotifier


class TestEmailNotifier:
    """Test suite for Email SMTP notifier"""
    
    def test_initialization_with_env(self):
        """Test initialization with environment variables"""
        env_vars = {
            'SMTP_HOST': 'smtp.gmail.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'test@example.com',
            'SMTP_PASS': 'password123',
            'EMAIL_FROM': 'alerts@example.com',
            'EMAIL_TO': 'recipient1@example.com,recipient2@example.com'
        }
        with patch.dict('os.environ', env_vars):
            notifier = EmailNotifier()
            assert notifier.smtp_host == 'smtp.gmail.com'
            assert notifier.smtp_port == 587
            assert notifier.smtp_user == 'test@example.com'
            assert notifier.from_email == 'alerts@example.com'
            assert len(notifier.to_emails) == 2
            
    def test_initialization_with_explicit_params(self):
        """Test initialization with explicit parameters"""
        notifier = EmailNotifier(
            smtp_host='smtp.test.com',
            smtp_port=465,
            smtp_user='user@test.com',
            smtp_pass='pass',
            from_email='from@test.com',
            to_emails=['to1@test.com', 'to2@test.com']
        )
        assert notifier.smtp_host == 'smtp.test.com'
        assert notifier.smtp_port == 465
        assert len(notifier.to_emails) == 2
        
    def test_is_available_true(self):
        """Test is_available returns True when configured"""
        notifier = EmailNotifier(
            smtp_host='smtp.test.com',
            smtp_user='user@test.com',
            smtp_pass='pass',
            to_emails=['to@test.com']
        )
        assert notifier.is_available() is True
        
    def test_is_available_false(self):
        """Test is_available returns False when not configured"""
        with patch.dict('os.environ', {}, clear=True):
            notifier = EmailNotifier()
            assert notifier.is_available() is False
            
    def test_is_available_mock_mode(self):
        """Test is_available returns True in mock mode"""
        notifier = EmailNotifier(mock_mode=True)
        assert notifier.is_available() is True
        
    def test_send_with_mock_mode(self):
        """Test send in mock mode (no actual SMTP)"""
        notifier = EmailNotifier(mock_mode=True)
        
        alert = AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.RATE_LIMITER,
            title="Test",
            message="Test alert",
            timestamp=datetime.now()
        )
        
        result = notifier.send(alert)
        assert result is True
        
    def test_send_immediate_p0_alert(self):
        """Test sending immediate P0 alert"""
        notifier = EmailNotifier(
            smtp_host='smtp.test.com',
            smtp_user='user@test.com',
            smtp_pass='pass',
            to_emails=['to@test.com']
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.EXCHANGE_HEALTH,
            title="Test",
            message="Critical exchange failure",
            timestamp=datetime(2025, 1, 22, 14, 30, 0),
            metadata={"exchange": "upbit"}
        )
        
        with patch.object(notifier, '_send_email', return_value=True) as mock_send:
            result = notifier.send(alert)
            assert result is True
            mock_send.assert_called_once()
            
            # Check email content
            msg = mock_send.call_args[0][0]
            assert "🔴" in msg['Subject']
            assert "[P0]" in msg['Subject']
            
    def test_send_immediate_p1_alert(self):
        """Test sending immediate P1 alert"""
        notifier = EmailNotifier(
            smtp_host='smtp.test.com',
            smtp_user='user@test.com',
            smtp_pass='pass',
            to_emails=['to@test.com']
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.RISK_GUARD,
            title="Test",
            message="Risk limit exceeded",
            timestamp=datetime.now()
        )
        
        with patch.object(notifier, '_send_email', return_value=True) as mock_send:
            result = notifier.send(alert)
            assert result is True
            
    def test_render_alert_html(self):
        """Test HTML rendering for single alert"""
        notifier = EmailNotifier(
            smtp_host='smtp.test.com',
            smtp_user='user@test.com',
            smtp_pass='pass',
            to_emails=['to@test.com']
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.RATE_LIMITER,
            title="Test",
            message="Test message",
            timestamp=datetime(2025, 1, 22, 12, 0, 0),
            metadata={"exchange": "binance", "count": 5}
        )
        
        html = notifier._render_alert_html(alert)
        
        assert "🔴" in html
        assert "P0 Alert" in html
        assert "Test message" in html
        assert "rate_limiter" in html.lower()
        assert "binance" in html.lower()
        assert "2025-01-22 12:00:00" in html
        
    def test_send_summary(self):
        """Test sending daily summary email"""
        notifier = EmailNotifier(
            smtp_host='smtp.test.com',
            smtp_user='user@test.com',
            smtp_pass='pass',
            to_emails=['to@test.com']
        )
        
        alerts = [
            AlertRecord(
                severity=AlertSeverity.P3,
                source=AlertSource.ARB_ROUTE,
                title="Test",
                message="Low spread detected",
                timestamp=datetime.now()
            ),
            AlertRecord(
                severity=AlertSeverity.P2,
                source=AlertSource.CROSS_SYNC,
                title="Test",
                message="Inventory imbalance",
                timestamp=datetime.now()
            )
        ]
        
        with patch.object(notifier, '_send_email', return_value=True) as mock_send:
            result = notifier.send_summary(alerts)
            assert result is True
            mock_send.assert_called_once()
            
            # Check email content
            msg = mock_send.call_args[0][0]
            assert "Daily Alert Summary" in msg['Subject']
            
    def test_render_summary_html(self):
        """Test HTML rendering for summary"""
        notifier = EmailNotifier(
            smtp_host='smtp.test.com',
            smtp_user='user@test.com',
            smtp_pass='pass',
            to_emails=['to@test.com']
        )
        
        alerts = [
            AlertRecord(
                severity=AlertSeverity.P1,
                source=AlertSource.RATE_LIMITER,
                title="Test",
                message="Alert 1",
                timestamp=datetime.now()
            ),
            AlertRecord(
                severity=AlertSeverity.P3,
                source=AlertSource.ARB_UNIVERSE,
                title="Test",
                message="Alert 2",
                timestamp=datetime.now()
            )
        ]
        
        html = notifier._render_summary_html(alerts)
        
        assert "Daily Alert Summary" in html
        assert "Total Alerts: 2" in html
        assert "Alert 1" in html
        assert "Alert 2" in html
        assert "🟠" in html  # P1
        assert "🔵" in html  # P3
        
    def test_send_email_smtp_success(self):
        """Test successful SMTP email send"""
        notifier = EmailNotifier(
            smtp_host='smtp.test.com',
            smtp_port=587,
            smtp_user='user@test.com',
            smtp_pass='pass',
            to_emails=['to@test.com']
        )
        
        mock_msg = MagicMock()
        
        with patch('smtplib.SMTP') as mock_smtp_class:
            mock_server = MagicMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_server
            
            result = notifier._send_email(mock_msg)
            
            assert result is True
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with('user@test.com', 'pass')
            mock_server.send_message.assert_called_once_with(mock_msg)
            
    def test_send_email_smtp_failure(self):
        """Test SMTP email send failure"""
        notifier = EmailNotifier(
            smtp_host='smtp.test.com',
            smtp_user='user@test.com',
            smtp_pass='pass',
            to_emails=['to@test.com']
        )
        
        mock_msg = MagicMock()
        
        with patch('smtplib.SMTP') as mock_smtp_class:
            mock_smtp_class.side_effect = Exception("SMTP connection failed")
            
            result = notifier._send_email(mock_msg)
            assert result is False
            
    def test_send_unavailable(self):
        """Test send returns False when unavailable"""
        notifier = EmailNotifier()  # No config
        
        alert = AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.RATE_LIMITER,
            title="Test",
            message="Test",
            timestamp=datetime.now()
        )
        
        result = notifier.send(alert)
        assert result is False
        
    def test_send_summary_empty_list(self):
        """Test send_summary returns False for empty alert list"""
        notifier = EmailNotifier(
            smtp_host='smtp.test.com',
            smtp_user='user@test.com',
            smtp_pass='pass',
            to_emails=['to@test.com']
        )
        
        result = notifier.send_summary([])
        assert result is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
