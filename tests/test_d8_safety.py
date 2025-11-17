#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D8 Safety Validation Tests
"""

from arbitrage.safety import SafetyContext, SafetyValidator
from arbitrage.signal_engine import ArbitrageSignal

print('=== D8 Safety Validation Tests ===')
print()

# 설정
safety_config = {
    'max_slippage_pct': 0.30,
    'max_order_delay_ms': 2500,
    'max_position_size_krw': 300000,
    'max_daily_loss_krw': 150000,
    'min_liquidity_krw': 20000000,
    'require_ws_freshness': True,
    'require_redis_heartbeat': True
}
context = SafetyContext(safety_config)
validator = SafetyValidator(context)

# 테스트 1: 유효한 신호
print('TEST 1: Valid Signal')
signal = ArbitrageSignal(
    opportunity_type='upbit_buy_binance_sell',
    spread_pct=0.8,
    buy_exchange='upbit',
    buy_price=50000000.0,
    sell_exchange='binance',
    sell_price=50400000.0,
    profit_krw=400000.0,
    profit_pct=0.8,
    confidence=0.8
)
is_valid, reason = validator.validate_signal(signal)
print(f'  Result: {is_valid}')
print()

# 테스트 2: 낮은 신뢰도 신호 (거부)
print('TEST 2: Low Confidence Signal (REJECTED)')
signal_low = ArbitrageSignal(
    opportunity_type='upbit_buy_binance_sell',
    spread_pct=0.05,
    buy_exchange='upbit',
    buy_price=50000000.0,
    sell_exchange='binance',
    sell_price=50025000.0,
    profit_krw=25000.0,
    profit_pct=0.05,
    confidence=0.2
)
is_valid, reason = validator.validate_signal(signal_low)
print(f'  Result: {is_valid}')
print(f'  Reason: {reason}')
print()

# 테스트 3: 유효한 실행 요청
print('TEST 3: Valid Execution Request')
execution_req = {
    'buy_exchange': 'upbit',
    'buy_price': 50000000.0,
    'sell_exchange': 'binance',
    'sell_price': 50400000.0,
    'quantity': 0.01,
    'estimated_slippage_pct': 0.15,
    'min_liquidity_krw': 25000000.0
}
is_valid, reason = validator.validate_execution(execution_req)
print(f'  Result: {is_valid}')
print()

# 테스트 4: 과도한 슬리피지 (거부)
print('TEST 4: Excessive Slippage (REJECTED)')
execution_req_high_slip = {
    'buy_exchange': 'upbit',
    'buy_price': 50000000.0,
    'sell_exchange': 'binance',
    'sell_price': 50400000.0,
    'quantity': 0.01,
    'estimated_slippage_pct': 0.50,
    'min_liquidity_krw': 25000000.0
}
is_valid, reason = validator.validate_execution(execution_req_high_slip)
print(f'  Result: {is_valid}')
print(f'  Reason: {reason}')
print()

# 테스트 5: 과도한 포지션 사이즈 (거부)
print('TEST 5: Excessive Position Size (REJECTED)')
execution_req_large = {
    'buy_exchange': 'upbit',
    'buy_price': 50000000.0,
    'sell_exchange': 'binance',
    'sell_price': 50400000.0,
    'quantity': 0.1,
    'estimated_slippage_pct': 0.15,
    'min_liquidity_krw': 25000000.0
}
is_valid, reason = validator.validate_execution(execution_req_large)
print(f'  Result: {is_valid}')
print(f'  Reason: {reason}')
print()

# 테스트 6: 주문 지연 검증
print('TEST 6: Order Latency Check')
is_valid, reason = validator.validate_order_latency(1500.0)
print(f'  Latency 1500ms: {is_valid}')
is_valid, reason = validator.validate_order_latency(3000.0)
print(f'  Latency 3000ms: {is_valid} (REJECTED)')
print()

# 테스트 7: 안전 통계
print('TEST 7: Safety Statistics')
stats = validator.get_safety_stats()
print(f'  Total rejections: {stats["safety_rejections_count"]}')
print(f'  Slippage excess count: {stats["slippage_excess_count"]}')
print(f'  Health fail count: {stats["health_fail_count"]}')
print()

print('=== All Tests Completed ===')
