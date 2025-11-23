"""
Email SMTP Notifier for Alerting System
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from datetime import datetime
from arbitrage.alerting.models import AlertRecord, AlertSeverity
from arbitrage.alerting.notifiers.base import NotifierBase


class EmailNotifier(NotifierBase):
    """
    SMTP-based email notifier
    
    Features:
    - Environment variable config (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS)
    - Daily Summary mode (batch P3 alerts)
    - Immediate alert mode (P0-P2)
    - HTML template rendering
    - Mock SMTP for testing
    """
    
    SEVERITY_ICON = {
        AlertSeverity.P0: "🔴",
        AlertSeverity.P1: "🟠",
        AlertSeverity.P2: "🟡",
        AlertSeverity.P3: "🔵"
    }
    
    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_pass: Optional[str] = None,
        from_email: Optional[str] = None,
        to_emails: Optional[List[str]] = None,
        mock_mode: bool = False
    ):
        """
        Initialize Email notifier
        
        Args:
            smtp_host: SMTP server host (env: SMTP_HOST if None)
            smtp_port: SMTP server port (env: SMTP_PORT if None, default: 587)
            smtp_user: SMTP username (env: SMTP_USER if None)
            smtp_pass: SMTP password (env: SMTP_PASS if None)
            from_email: Sender email (env: EMAIL_FROM if None)
            to_emails: Recipient emails (env: EMAIL_TO comma-separated if None)
            mock_mode: If True, skip actual SMTP connection (for testing)
        """
        self.smtp_host = smtp_host or os.getenv('SMTP_HOST')
        self.smtp_port = smtp_port or int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = smtp_user or os.getenv('SMTP_USER')
        self.smtp_pass = smtp_pass or os.getenv('SMTP_PASS')
        self.from_email = from_email or os.getenv('EMAIL_FROM', self.smtp_user)
        
        if to_emails:
            self.to_emails = to_emails
        else:
            to_env = os.getenv('EMAIL_TO', '')
            self.to_emails = [e.strip() for e in to_env.split(',') if e.strip()]
            
        self.mock_mode = mock_mode
        
    def is_available(self) -> bool:
        """Check if SMTP is configured"""
        return (
            bool(self.smtp_host and self.smtp_user and self.smtp_pass and self.to_emails)
            or self.mock_mode
        )
        
    def send(self, alert: AlertRecord) -> bool:
        """
        Send alert via email
        
        Args:
            alert: AlertRecord to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_available():
            return False
            
        if self.mock_mode:
            return True
            
        try:
            # Determine email mode based on severity
            if alert.severity in [AlertSeverity.P0, AlertSeverity.P1, AlertSeverity.P2]:
                return self._send_immediate(alert)
            else:
                # P3 alerts can be batched (handled by caller)
                return self._send_immediate(alert)
                
        except Exception:
            return False
            
    def send_summary(self, alerts: List[AlertRecord]) -> bool:
        """
        Send daily summary email with multiple alerts
        
        Args:
            alerts: List of AlertRecords to include in summary
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_available() or not alerts:
            return False
            
        if self.mock_mode:
            return True
            
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Daily Alert Summary - {datetime.now().strftime('%Y-%m-%d')}"
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            
            html_body = self._render_summary_html(alerts)
            msg.attach(MIMEText(html_body, 'html'))
            
            return self._send_email(msg)
            
        except Exception:
            return False
            
    def _send_immediate(self, alert: AlertRecord) -> bool:
        """Send immediate alert email"""
        msg = MIMEMultipart('alternative')
        
        icon = self.SEVERITY_ICON.get(alert.severity, "⚪")
        msg['Subject'] = f"{icon} [{alert.severity.value}] {alert.message[:50]}"
        msg['From'] = self.from_email
        msg['To'] = ', '.join(self.to_emails)
        
        html_body = self._render_alert_html(alert)
        msg.attach(MIMEText(html_body, 'html'))
        
        return self._send_email(msg)
        
    def _send_email(self, msg: MIMEMultipart) -> bool:
        """Send email via SMTP"""
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            return True
        except Exception:
            return False
            
    def _render_alert_html(self, alert: AlertRecord) -> str:
        """Render single alert as HTML"""
        icon = self.SEVERITY_ICON.get(alert.severity, "⚪")
        
        metadata_rows = ""
        if alert.metadata:
            for key, value in alert.metadata.items():
                metadata_rows += f"""
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">
                        {key.replace('_', ' ').title()}
                    </td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{value}</td>
                </tr>
                """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .alert-box {{ border: 2px solid #e74c3c; border-radius: 5px; padding: 20px; background-color: #fff5f5; }}
                .severity-p0 {{ border-color: #e74c3c; background-color: #fff5f5; }}
                .severity-p1 {{ border-color: #f39c12; background-color: #fffbf0; }}
                .severity-p2 {{ border-color: #f1c40f; background-color: #fffef0; }}
                .severity-p3 {{ border-color: #3498db; background-color: #f0f8ff; }}
                h2 {{ color: #2c3e50; margin-top: 0; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                th, td {{ text-align: left; }}
            </style>
        </head>
        <body>
            <div class="alert-box severity-{alert.severity.value.lower()}">
                <h2>{icon} {alert.severity.value} Alert</h2>
                <p style="font-size: 16px; margin: 10px 0;"><strong>{alert.message}</strong></p>
                
                <table>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold; width: 30%;">Source</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{alert.source.value}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Timestamp</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">
                            {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
                        </td>
                    </tr>
                    {metadata_rows}
                </table>
            </div>
            
            <p style="color: #7f8c8d; font-size: 12px; margin-top: 20px;">
                This is an automated alert from the Arbitrage Alert System.
            </p>
        </body>
        </html>
        """
        return html
        
    def _render_summary_html(self, alerts: List[AlertRecord]) -> str:
        """Render daily summary as HTML"""
        alert_rows = ""
        for alert in alerts:
            icon = self.SEVERITY_ICON.get(alert.severity, "⚪")
            alert_rows += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">{icon} {alert.severity.value}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{alert.source.value}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{alert.message}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">
                    {alert.timestamp.strftime('%H:%M:%S')}
                </td>
            </tr>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #2c3e50; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                th {{ background-color: #3498db; color: white; padding: 10px; text-align: left; }}
                td {{ padding: 8px; border: 1px solid #ddd; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Daily Alert Summary</h1>
            <p>Date: {datetime.now().strftime('%Y-%m-%d')}</p>
            <p>Total Alerts: {len(alerts)}</p>
            
            <table>
                <thead>
                    <tr>
                        <th>Severity</th>
                        <th>Source</th>
                        <th>Message</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody>
                    {alert_rows}
                </tbody>
            </table>
            
            <p style="color: #7f8c8d; font-size: 12px; margin-top: 20px;">
                This is an automated daily summary from the Arbitrage Alert System.
            </p>
        </body>
        </html>
        """
        return html
