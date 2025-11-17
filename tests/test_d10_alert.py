#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D10 Alert System Tests (Telegram Integration)
"""

from arbitrage.alert import AlertSystem

print('=== D10 Alert System Tests ===')
print()

# TEST 1: 알림 비활성화 상태
print('TEST 1: Alerts Disabled')
config = {'enabled': False}
alert_system = AlertSystem(config)
alert_system.send_alert('test', 'This should not appear', 'INFO')
print(f'  Alerts sent: {alert_system.alerts_sent}')
print()

# TEST 2: 알림 활성화, Telegram 비활성화
print('TEST 2: Alerts Enabled, Telegram Disabled')
config = {
    'enabled': True,
    'telegram_enabled': False,
    'telegram': {
        'bot_token': '',
        'chat_id': '',
        'timeout_seconds': 5
    }
}
alert_system = AlertSystem(config)
alert_system.send_alert('test', 'Test message', 'INFO')
stats = alert_system.get_stats()
print(f'  Alerts sent: {stats["alerts_sent"]}')
print(f'  Telegram enabled: {stats["telegram_enabled"]}')
print(f'  Telegram configured: {stats["telegram_configured"]}')
print()

# TEST 3: Telegram 활성화, 자격증명 없음 (스텁 모드)
print('TEST 3: Telegram Enabled, No Credentials')
config = {
    'enabled': True,
    'telegram_enabled': True,
    'telegram': {
        'bot_token': '',
        'chat_id': '',
        'timeout_seconds': 5
    }
}
alert_system = AlertSystem(config)
alert_system.send_alert('test', 'Test message', 'INFO')
stats = alert_system.get_stats()
print(f'  Alerts sent: {stats["alerts_sent"]}')
print(f'  Telegram errors: {stats["telegram_errors"]}')
print(f'  Telegram configured: {stats["telegram_configured"]}')
print()

# TEST 4: 다양한 알림 유형
print('TEST 4: Various Alert Types')
config = {
    'enabled': True,
    'telegram_enabled': False,
    'telegram': {
        'bot_token': '',
        'chat_id': '',
        'timeout_seconds': 5
    }
}
alert_system = AlertSystem(config)
alert_system.alert_stoploss_triggered('BTC-KRW', 49400000.0)
alert_system.alert_rebalance_executed(2, 260000.0)
alert_system.alert_safety_rejection('Slippage too high')
alert_system.alert_daily_loss_limit_hit(150000.0, 150000.0)
alert_system.alert_trade_opened('BTC-KRW', 'BUY', 0.01, 50000000.0)
alert_system.alert_trade_closed('BTC-KRW', 5000.0)
alert_system.alert_system_error('WebSocket connection lost')
stats = alert_system.get_stats()
print(f'  Total alerts sent: {stats["alerts_sent"]}')
print()

print('=== All Tests Completed ===')
