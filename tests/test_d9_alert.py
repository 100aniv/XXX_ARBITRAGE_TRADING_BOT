#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D9 Alert System Tests
"""

from arbitrage.alert import AlertSystem

print('=== D9 Alert System Tests ===')
print()

# 알림 시스템 초기화
config = {
    'enabled': True,
    'telegram_enabled': False
}
alert_system = AlertSystem(config)

# TEST 1: 손절매 알림
print('TEST 1: Stop-Loss Alert')
alert_system.alert_stoploss_triggered('BTC-KRW', 49400000.0)
print()

# TEST 2: 리밸런싱 알림
print('TEST 2: Rebalance Alert')
alert_system.alert_rebalance_executed(2, 260000.0)
print()

# TEST 3: 안전 거부 알림
print('TEST 3: Safety Rejection Alert')
alert_system.alert_safety_rejection('Slippage too high: 0.50% > 0.30%')
print()

# TEST 4: 일일 손실 제한 알림
print('TEST 4: Daily Loss Limit Alert')
alert_system.alert_daily_loss_limit_hit(150000.0, 150000.0)
print()

# TEST 5: 거래 오픈 알림
print('TEST 5: Trade Opened Alert')
alert_system.alert_trade_opened('BTC-KRW', 'BUY', 0.01, 50000000.0)
print()

# TEST 6: 거래 종료 알림
print('TEST 6: Trade Closed Alert')
alert_system.alert_trade_closed('BTC-KRW', 5000.0)
print()

# TEST 7: 시스템 에러 알림
print('TEST 7: System Error Alert')
alert_system.alert_system_error('WebSocket connection lost')
print()

# TEST 8: 알림 통계
print('TEST 8: Alert Stats')
stats = alert_system.get_stats()
print(f'  Alerts sent: {stats["alerts_sent"]}')
print(f'  Enabled: {stats["enabled"]}')
print(f'  Telegram enabled: {stats["telegram_enabled"]}')
print()

print('=== All Tests Completed ===')
