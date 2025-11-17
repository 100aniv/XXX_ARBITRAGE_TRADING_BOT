#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D9 Stop-Loss Engine Tests
"""

from arbitrage.stoploss import StopLossEngine
from arbitrage.position_engine import Position

print('=== D9 Stop-Loss Engine Tests ===')
print()

# 손절매 엔진 초기화
config = {
    'enabled': True,
    'mode': 'static',
    'static_pct': 1.2,
    'atr_window': 20
}
engine = StopLossEngine(config)

# TEST 1: 정적 손절매 (매수 포지션)
print('TEST 1: Static SL - Buy Position')
pos_buy = Position('BTC-KRW', 'BUY', 0.01, 50000000.0)
sl_price = engine.get_stoploss_price(pos_buy)
print(f'  Entry price: 50,000,000₩')
print(f'  SL price: {sl_price:.0f}₩')
print(f'  SL triggered at 49,400,000: {engine.check_stoploss(pos_buy, 49400000.0)}')
print(f'  SL not triggered at 49,500,000: {not engine.check_stoploss(pos_buy, 49500000.0)}')
print()

# TEST 2: 정적 손절매 (매도 포지션)
print('TEST 2: Static SL - Sell Position')
pos_sell = Position('BTC-KRW', 'SELL', 0.01, 50000000.0)
sl_price = engine.get_stoploss_price(pos_sell)
print(f'  Entry price: 50,000,000₩')
print(f'  SL price: {sl_price:.0f}₩')
print(f'  SL triggered at 50,600,000: {engine.check_stoploss(pos_sell, 50600000.0)}')
print(f'  SL not triggered at 50,500,000: {not engine.check_stoploss(pos_sell, 50500000.0)}')
print()

# TEST 3: 손절매 통계
print('TEST 3: Stop-Loss Stats')
stats = engine.get_stats()
print(f'  Triggers: {stats["stoploss_triggers"]}')
print(f'  Mode: {stats["mode"]}')
print(f'  Enabled: {stats["enabled"]}')
print()

print('=== All Tests Completed ===')
