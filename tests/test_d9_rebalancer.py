#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D9 Rebalancer Engine Tests
"""

from arbitrage.rebalancer import RebalancerEngine
from arbitrage.position_engine import PositionEngine

print('=== D9 Rebalancer Engine Tests ===')
print()

# 리밸런서 엔진 초기화
rebalancer_config = {
    'enabled': True,
    'max_exposure_krw': 600000,
    'reduce_pct': 0.3
}
rebalancer = RebalancerEngine(rebalancer_config)

# 포지션 엔진 초기화
position_config = {
    'max_open_positions': 10,
    'max_exposure_krw': 2000000,
    'max_daily_loss_krw': 150000
}
position_engine = PositionEngine(position_config)

# TEST 1: 리밸런싱 필요 여부
print('TEST 1: Should Rebalance')
print(f'  Exposure 500,000₩: {rebalancer.should_rebalance(500000)}')
print(f'  Exposure 700,000₩: {rebalancer.should_rebalance(700000)}')
print()

# TEST 2: 감소량 계산
print('TEST 2: Calculate Reduction')
reduction = rebalancer.calculate_reduction(800000)
print(f'  Current exposure: 800,000₩')
print(f'  Max exposure: 600,000₩')
print(f'  Reduction needed: {reduction:.0f}₩')
print()

# TEST 3: 리밸런싱 실행
print('TEST 3: Execute Rebalancing')
# 포지션 추가
pos1 = position_engine.open_position('BTC-KRW', 'BUY', 0.01, 50000000.0)
pos2 = position_engine.open_position('ETH-KRW', 'BUY', 0.1, 2000000.0)
pos3 = position_engine.open_position('XRP-KRW', 'BUY', 100, 1000.0)

print(f'  Open positions: {position_engine.get_open_positions_count()}')
print(f'  Total exposure: {position_engine.get_total_exposure_krw():.0f}₩')

# 리밸런싱 실행
current_exposure = position_engine.get_total_exposure_krw()
if rebalancer.should_rebalance(current_exposure):
    reduction = rebalancer.calculate_reduction(current_exposure)
    positions_to_close = rebalancer.rebalance(position_engine, reduction)
    print(f'  Positions to close: {len(positions_to_close)}')
    print(f'  Rebalance actions: {rebalancer.rebalance_actions}')
print()

# TEST 4: 리밸런서 통계
print('TEST 4: Rebalancer Stats')
stats = rebalancer.get_stats()
print(f'  Rebalance actions: {stats["rebalance_actions"]}')
print(f'  Enabled: {stats["enabled"]}')
print(f'  Max exposure: {stats["max_exposure_krw"]:.0f}₩')
print()

print('=== All Tests Completed ===')
