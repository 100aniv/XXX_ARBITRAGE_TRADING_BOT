#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D14 Advanced Position Management Tests
"""

from arbitrage.position_adv import AdvancedPositionManager, MarketRegime

print('=== D14 Advanced Position Management Tests ===')
print()

# TEST 1: 기본 포지션 사이즈 계산
print('TEST 1: Basic Position Size Calculation')
manager = AdvancedPositionManager()
size = manager.get_dynamic_position_size(volatility_estimate=0.3, risk_mode='normal')
print(f'  Normal mode, volatility=0.3: {size:.0f}₩')
print()

# TEST 2: 리스크 모드별 포지션 사이즈
print('TEST 2: Position Size by Risk Mode')
for risk_mode in ['normal', 'cautious', 'extreme']:
    size = manager.get_dynamic_position_size(volatility_estimate=0.3, risk_mode=risk_mode)
    print(f'  {risk_mode}: {size:.0f}₩')
print()

# TEST 3: 시장 레짐 감지 (Ranging)
print('TEST 3: Market Regime Detection (Ranging)')
manager = AdvancedPositionManager()
prices = [100, 100.5, 99.8, 100.2, 99.9, 100.1, 99.95, 100.05, 100, 99.98]
for price in prices:
    manager.update_market_data(price)
print(f'  Prices: {prices}')
print(f'  Detected regime: {manager.market_regime.value}')
print()

# TEST 4: 시장 레짐 감지 (Trending)
print('TEST 4: Market Regime Detection (Trending)')
manager = AdvancedPositionManager()
prices = [100, 102, 104, 106, 108, 110, 112, 114, 116, 118]
for price in prices:
    manager.update_market_data(price)
print(f'  Prices: {prices}')
print(f'  Detected regime: {manager.market_regime.value}')
print()

# TEST 5: 슬리피지 비용 감쇠
print('TEST 5: Slippage Cost Decay')
manager = AdvancedPositionManager()
for i in range(5):
    manager.update_market_data(100.0, bid_ask_spread_pct=0.1)

size_before = manager.get_dynamic_position_size(0.3, 'normal')
print(f'  Position size (no slippage): {size_before:.0f}₩')
print(f'  Cumulative slippage: {manager.cumulative_slippage_cost:.2f}%')

size_after = manager.get_dynamic_position_size(0.3, 'normal')
print(f'  Position size (with slippage): {size_after:.0f}₩')
print(f'  Decay ratio: {size_after/size_before:.2f}')
print()

# TEST 6: 동적 노출도 한계 조정
print('TEST 6: Dynamic Exposure Limit Adjustment')
manager = AdvancedPositionManager(max_exposure_krw=500000.0)

# 정상 증가
limit = manager.get_adjusted_exposure_limit(current_exposure_krw=200000.0, exposure_increase_rate=0.02)
print(f'  Normal increase (2%): {limit:.0f}₩')

# 높은 증가
limit = manager.get_adjusted_exposure_limit(current_exposure_krw=200000.0, exposure_increase_rate=0.15)
print(f'  High increase (15%): {limit:.0f}₩')

# 매우 높은 증가
limit = manager.get_adjusted_exposure_limit(current_exposure_krw=200000.0, exposure_increase_rate=0.20)
print(f'  Very high increase (20%): {limit:.0f}₩')
print()

# TEST 7: 통계
print('TEST 7: Statistics')
manager = AdvancedPositionManager()
for i in range(20):
    manager.update_market_data(100.0 + i * 0.5, bid_ask_spread_pct=0.05)
    manager.record_trade(50000.0)

stats = manager.get_stats()
print(f'  Market regime: {stats["market_regime"]}')
print(f'  Cumulative slippage: {stats["cumulative_slippage_cost"]:.2f}%')
print(f'  Exposure counter: {stats["exposure_counter"]}')
print()

print('=== All Tests Completed ===')
