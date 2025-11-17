#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D13 Risk Model Tests
"""

from arbitrage.risk_model import RiskModel, RiskMode, VolatilityCalculator

print('=== D13 Risk Model Tests ===')
print()

# TEST 1: 변동성 계산
print('TEST 1: Volatility Calculation')
calc = VolatilityCalculator(window_size=10)
prices = [100, 101, 102, 101, 100, 99, 98, 99, 100, 101]
for price in prices:
    calc.add_price(price)

volatility = calc.get_volatility_estimate()
print(f'  Prices: {prices}')
print(f'  Volatility estimate: {volatility:.2f}')
print()

# TEST 2: 정상 상태 리스크 평가
print('TEST 2: Normal State Risk Evaluation')
risk_model = RiskModel()
for i in range(20):
    risk_model.update_market_data(
        price=100.0 + i * 0.1,
        ws_lag_ms=100.0,
        spread_pct=0.3
    )

metrics = {
    'redis_heartbeat_age_ms': 5000.0,
    'loop_latency_ms': 50.0
}
decision = risk_model.evaluate_risk(metrics)
print(f'  Allow trade: {decision.allow_trade}')
print(f'  Risk mode: {decision.risk_mode.value}')
print(f'  Position multiplier: {decision.position_size_multiplier}')
print(f'  Slippage tolerance: {decision.slippage_tolerance_pct}%')
print()

# TEST 3: 높은 변동성 상태
print('TEST 3: High Volatility State')
risk_model = RiskModel()
# 큰 가격 변동
prices = [100, 110, 90, 120, 80, 130, 70, 140, 60, 150]
for price in prices:
    risk_model.update_market_data(price=price, ws_lag_ms=100.0)

metrics = {'redis_heartbeat_age_ms': 5000.0, 'loop_latency_ms': 50.0}
decision = risk_model.evaluate_risk(metrics)
print(f'  Volatility: {decision.volatility_estimate:.2f}')
print(f'  Risk mode: {decision.risk_mode.value}')
print(f'  Position multiplier: {decision.position_size_multiplier}')
print(f'  Allow trade: {decision.allow_trade}')
print()

# TEST 4: WS 지연 스파이크 감지
print('TEST 4: WebSocket Lag Spike Detection')
risk_model = RiskModel()
for i in range(20):
    if i == 10:
        # 스파이크 발생
        risk_model.update_market_data(price=100.0, ws_lag_ms=2000.0)
    else:
        risk_model.update_market_data(price=100.0, ws_lag_ms=100.0)

stats = risk_model.get_stats()
print(f'  WS lag spike count: {stats["ws_lag_spike_count"]}')
print(f'  Last WS lag: {stats["last_ws_lag_ms"]:.0f}ms')
print()

# TEST 5: 스프레드 역전 감지
print('TEST 5: Spread Inversion Detection')
risk_model = RiskModel()
spreads = [0.3, 0.3, 0.2, -0.1, 0.3, 0.2, -0.2, 0.3]
for spread in spreads:
    risk_model.update_market_data(price=100.0, spread_pct=spread)

stats = risk_model.get_stats()
print(f'  Spread inversion count: {stats["spread_inversion_count"]}')
print()

# TEST 6: Redis 문제로 인한 거래 차단
print('TEST 6: Trade Block - Redis Issue')
risk_model = RiskModel()
metrics = {
    'redis_heartbeat_age_ms': 35000.0,  # 에러 임계치 초과
    'loop_latency_ms': 50.0
}
decision = risk_model.evaluate_risk(metrics)
print(f'  Allow trade: {decision.allow_trade}')
print(f'  Block reason: {decision.block_reason}')
print()

# TEST 7: 루프 지연 과다로 인한 거래 차단
print('TEST 7: Trade Block - Loop Latency')
risk_model = RiskModel()
metrics = {
    'redis_heartbeat_age_ms': 5000.0,
    'loop_latency_ms': 6000.0  # 에러 임계치 초과
}
decision = risk_model.evaluate_risk(metrics)
print(f'  Allow trade: {decision.allow_trade}')
print(f'  Block reason: {decision.block_reason}')
print()

# TEST 8: 극단적 변동성으로 인한 거래 차단
print('TEST 8: Trade Block - Extreme Volatility')
risk_model = RiskModel()
# 매우 큰 가격 변동
prices = [100, 150, 50, 200, 30, 250, 20, 300, 10, 350]
for price in prices:
    risk_model.update_market_data(price=price, ws_lag_ms=100.0)

metrics = {'redis_heartbeat_age_ms': 5000.0, 'loop_latency_ms': 50.0}
decision = risk_model.evaluate_risk(metrics)
print(f'  Volatility: {decision.volatility_estimate:.2f}')
print(f'  Allow trade: {decision.allow_trade}')
print(f'  Block reason: {decision.block_reason}')
print()

# TEST 9: 조심 모드 (CAUTIOUS)
print('TEST 9: Cautious Mode')
risk_model = RiskModel()
# 중간 정도의 변동성
prices = [100, 105, 95, 110, 90, 105, 95, 105]
for price in prices:
    risk_model.update_market_data(price=price, ws_lag_ms=100.0)

metrics = {'redis_heartbeat_age_ms': 5000.0, 'loop_latency_ms': 50.0}
decision = risk_model.evaluate_risk(metrics)
print(f'  Risk mode: {decision.risk_mode.value}')
print(f'  Position multiplier: {decision.position_size_multiplier}')
print(f'  Slippage tolerance: {decision.slippage_tolerance_pct}%')
print()

print('=== All Tests Completed ===')
