#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D9 Position Engine Tests
"""

from arbitrage.position_engine import PositionEngine

print('=== D9 Position Engine Tests ===')
print()

# 포지션 엔진 초기화
config = {
    'max_open_positions': 5,
    'max_exposure_krw': 1000000,
    'max_daily_loss_krw': 150000
}
engine = PositionEngine(config)

# TEST 1: 포지션 오픈
print('TEST 1: Open Position')
pos1 = engine.open_position('BTC-KRW', 'BUY', 0.01, 50000000.0)
print(f'  Position opened: {pos1 is not None}')
print(f'  Open positions: {engine.get_open_positions_count()}')
print()

# TEST 2: 노출도 확인
print('TEST 2: Exposure Check')
exposure = engine.get_total_exposure_krw()
print(f'  Total exposure: {exposure:.0f}₩')
print(f'  Can open new position: {engine.can_open_new_position(100000)}')
print()

# TEST 3: 포지션 종료
print('TEST 3: Close Position')
if pos1:
    success = engine.close_position(pos1.symbol + '_BUY_' + str(int(pos1.entry_time.timestamp() * 1000)), 50500000.0)
    print(f'  Position closed: {success}')
    print(f'  Realized PnL: {engine.get_realized_pnl_today():.0f}₩')
print()

# TEST 4: 포지션 통계
print('TEST 4: Position Stats')
stats = engine.get_stats()
print(f'  Open positions: {stats["open_positions_count"]}')
print(f'  Total exposure: {stats["total_exposure_krw"]:.0f}₩')
print(f'  Realized PnL: {stats["realized_pnl_today"]:.0f}₩')
print(f'  Closed today: {stats["closed_positions_today"]}')
print()

# TEST 5: 최대 포지션 제한
print('TEST 5: Max Positions Limit')
for i in range(6):
    pos = engine.open_position(f'SYM{i}', 'BUY', 0.01, 50000000.0)
    if pos is None:
        print(f'  Position {i+1}: REJECTED (limit reached)')
    else:
        print(f'  Position {i+1}: OPENED')
print()

print('=== All Tests Completed ===')
