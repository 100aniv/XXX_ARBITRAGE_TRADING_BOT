#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alert System (PHASE D9 + D10 + D13)
===================================

알림 시스템 (Telegram 실제 연동 포함, D13: 시크릿 관리).
"""

import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# D13: 시크릿 매니저 선택적 임포트
try:
    from arbitrage.secrets import get_secrets
    HAS_SECRETS = True
except (ImportError, RuntimeError):
    HAS_SECRETS = False


class AlertSystem:
    """알림 시스템"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: 알림 설정
        """
        self.config = config or {}
        
        # 알림 설정
        self.enabled = self.config.get("enabled", True)
        self.telegram_enabled = self.config.get("telegram_enabled", False)
        
        # D13: Telegram 설정 (시크릿 매니저 > 환경 변수 > config)
        telegram_config = self.config.get("telegram", {})
        
        # 시크릿 매니저에서 먼저 시도
        self.telegram_token = ""
        self.telegram_chat_id = ""
        
        if HAS_SECRETS:
            try:
                secrets = get_secrets()
                self.telegram_token = secrets.get("TELEGRAM_BOT_TOKEN", "")
                self.telegram_chat_id = secrets.get("TELEGRAM_CHAT_ID", "")
            except Exception as e:
                logger.debug(f"[Alert] Secrets manager not available: {e}")
        
        # 폴백: 환경 변수
        self.telegram_token = self.telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = self.telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        
        # 폴백: config
        self.telegram_token = self.telegram_token or telegram_config.get("bot_token", "")
        self.telegram_chat_id = self.telegram_chat_id or telegram_config.get("chat_id", "")
        
        self.telegram_timeout = telegram_config.get("timeout_seconds", 5)
        
        # 통계
        self.alerts_sent = 0
        self.telegram_errors = 0
    
    def send_alert(self, alert_type: str, message: str, severity: str = "INFO"):
        """
        알림 전송
        
        Args:
            alert_type: 알림 유형 (stoploss, rebalance, safety, loss_limit, trade, error)
            message: 메시지
            severity: 심각도 (INFO, WARNING, ERROR)
        """
        if not self.enabled:
            return
        
        try:
            # 타임스탬프
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 포맷팅
            formatted_message = f"[{timestamp}] [{alert_type.upper()}] [{severity}] {message}"
            
            # 콘솔 출력 (항상)
            if severity == "ERROR":
                logger.error(formatted_message)
            elif severity == "WARNING":
                logger.warning(formatted_message)
            else:
                logger.info(formatted_message)
            
            # Telegram 전송 (스텁)
            if self.telegram_enabled and self.telegram_token and self.telegram_chat_id:
                self._send_telegram(formatted_message)
            
            self.alerts_sent += 1
        
        except Exception as e:
            logger.error(f"[AlertSystem] Send alert error: {e}")
    
    def _send_telegram(self, message: str):
        """
        Telegram 메시지 전송
        
        실제 API 호출 또는 스텁 모드
        """
        try:
            # 토큰 또는 채팅 ID 없으면 스텁
            if not self.telegram_token or not self.telegram_chat_id:
                logger.debug(f"[AlertSystem] Telegram credentials missing, using stub: {message}")
                return
            
            # requests 라이브러리 동적 임포트
            try:
                import requests
            except ImportError:
                logger.warning(
                    "[AlertSystem] requests library not installed, Telegram disabled. "
                    "Install with: pip install requests"
                )
                self.telegram_errors += 1
                return
            
            # Telegram Bot API 호출
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            
            try:
                response = requests.post(url, data=data, timeout=self.telegram_timeout)
                if response.status_code != 200:
                    logger.warning(
                        f"[AlertSystem] Telegram API error: {response.status_code} - {response.text}"
                    )
                    self.telegram_errors += 1
                else:
                    logger.debug(f"[AlertSystem] Telegram message sent successfully")
            
            except requests.exceptions.Timeout:
                logger.warning(f"[AlertSystem] Telegram API timeout ({self.telegram_timeout}s)")
                self.telegram_errors += 1
            
            except requests.exceptions.RequestException as e:
                logger.warning(f"[AlertSystem] Telegram API request error: {e}")
                self.telegram_errors += 1
        
        except Exception as e:
            logger.error(f"[AlertSystem] Telegram send error: {e}")
            self.telegram_errors += 1
    
    def alert_stoploss_triggered(self, symbol: str, price: float):
        """손절매 발동 알림"""
        message = f"Stop-loss triggered for {symbol} at {price:.0f}₩"
        self.send_alert("stoploss", message, "WARNING")
    
    def alert_rebalance_executed(self, positions_closed: int, reduction_krw: float):
        """리밸런싱 실행 알림"""
        message = f"Rebalancing executed: closed {positions_closed} positions, reduction={reduction_krw:.0f}₩"
        self.send_alert("rebalance", message, "WARNING")
    
    def alert_safety_rejection(self, reason: str):
        """안전 거부 알림"""
        message = f"Safety check rejected: {reason}"
        self.send_alert("safety", message, "WARNING")
    
    def alert_daily_loss_limit_hit(self, daily_loss_krw: float, limit_krw: float):
        """일일 손실 제한 도달 알림"""
        message = f"Daily loss limit hit: {daily_loss_krw:.0f}₩ >= {limit_krw:.0f}₩"
        self.send_alert("loss_limit", message, "ERROR")
    
    def alert_trade_opened(self, symbol: str, side: str, quantity: float, price: float):
        """거래 오픈 알림"""
        message = f"Trade opened: {side} {quantity} {symbol} @ {price:.0f}₩"
        self.send_alert("trade", message, "INFO")
    
    def alert_trade_closed(self, symbol: str, pnl_krw: float):
        """거래 종료 알림"""
        message = f"Trade closed: {symbol}, PnL={pnl_krw:.0f}₩"
        self.send_alert("trade", message, "INFO")
    
    def alert_system_error(self, error_message: str):
        """시스템 에러 알림"""
        message = f"System error: {error_message}"
        self.send_alert("error", message, "ERROR")
    
    def get_stats(self) -> Dict[str, Any]:
        """알림 통계"""
        return {
            "alerts_sent": self.alerts_sent,
            "enabled": self.enabled,
            "telegram_enabled": self.telegram_enabled,
            "telegram_errors": self.telegram_errors,
            "telegram_configured": bool(self.telegram_token and self.telegram_chat_id)
        }
