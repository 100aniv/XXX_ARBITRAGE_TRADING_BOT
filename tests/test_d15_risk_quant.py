#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D15 High-Performance Quantitative Risk Management Tests
"""

import sys
from pathlib import Path
import numpy as np
import time

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.risk_quant import QuantitativeRiskManager

print('=== D15 High-Performance Quantitative Risk Management Tests ===')
print()

# TEST 1: 리스크 관리자 초기화
print('TEST 1: Risk Manager Initialization')
manager = QuantitativeRiskManager(window_size=100)
print(f'  ✅ Risk manager initialized')
print(f'  Window size: {manager.window_size}')
print(f'  Returns dtype: {manager.returns_history.dtype}')
print()

# TEST 2: 벡터화 배치 수익률 기록 및 VaR 계산
print('TEST 2: Vectorized Batch Returns and VaR Calculation')
returns = np.array([0.5, -0.3, 0.2, -0.5, 0.4, 0.1, -0.2, 0.3, -0.4, 0.6], dtype=np.float32)
manager.record_returns_batch(returns)

var_95 = manager.calculate_var(0.95)
var_99 = manager.calculate_var(0.99)

print(f'  Recorded {len(manager.returns_history)} returns (vectorized)')
print(f'  VaR 95%: {var_95:.4f}')
print(f'  VaR 99%: {var_99:.4f}')
print(f'  VaR 99% <= VaR 95%: {var_99 <= var_95}')
print()

# TEST 3: 벡터화 Expected Shortfall
print('TEST 3: Vectorized Expected Shortfall')
es = manager.calculate_expected_shortfall(0.95)
print(f'  Expected Shortfall (95%): {es:.4f}')
print(f'  ES <= VaR: {es <= var_95}')
print()

# TEST 4: 벡터화 최대 낙폭
print('TEST 4: Vectorized Maximum Drawdown')
pnl_data = np.array([100, 105, 102, 98, 95, 100, 110, 108, 115, 120], dtype=np.float32)
manager.record_pnl_batch(pnl_data)

max_dd = manager.calculate_max_drawdown()
print(f'  PnL data: {pnl_data}')
print(f'  Max Drawdown: {max_dd:.2f}')
print()

# TEST 5: 벡터화 샤프 지수
print('TEST 5: Vectorized Sharpe Ratio')
sharpe = manager.calculate_sharpe_ratio()
print(f'  Sharpe Ratio: {sharpe:.4f}')
print()

# TEST 6: 벡터화 스트레스 테스트
print('TEST 6: Vectorized Stress Tests')
position_krw = 1000000.0

vol_spike_loss = manager.stress_test_volatility_spike(position_krw, volatility_multiplier=2.0)
spread_loss = manager.stress_test_spread_widening(position_krw, spread_multiplier=3.0)
outage_loss = manager.stress_test_exchange_outage(position_krw, outage_duration_hours=1.0)

print(f'  Position: {position_krw:,.0f}₩')
print(f'  Volatility spike loss: {vol_spike_loss:,.0f}₩')
print(f'  Spread widening loss: {spread_loss:,.0f}₩')
print(f'  Exchange outage loss: {outage_loss:,.0f}₩')
print()

# TEST 7: 배치 스트레스 테스트 (벡터화)
print('TEST 7: Batch Stress Tests (Vectorized)')
scenarios = {
    'vol_spike': 2.0,
    'spread_widening': 3.0,
    'exchange_outage': 1.0
}
batch_results = manager.stress_test_batch(position_krw, scenarios)
print(f'  Batch stress test results:')
for scenario, loss in batch_results.items():
    print(f'    {scenario}: {loss:,.0f}₩')
print()

# TEST 8: 벡터화 유동성 조정 리스크
print('TEST 8: Vectorized Liquidity-Adjusted Risk')
daily_volume = 10000000.0

penalty_small = manager.get_liquidity_adjusted_risk(100000.0, daily_volume)
penalty_medium = manager.get_liquidity_adjusted_risk(500000.0, daily_volume)
penalty_large = manager.get_liquidity_adjusted_risk(2000000.0, daily_volume)

print(f'  Daily volume: {daily_volume:,.0f}₩')
print(f'  Position 100K: penalty {penalty_small:.2f}%')
print(f'  Position 500K: penalty {penalty_medium:.2f}%')
print(f'  Position 2M: penalty {penalty_large:.2f}%')
print()

# TEST 9: 전체 리스크 메트릭
print('TEST 9: Full Risk Metrics')
metrics = manager.get_risk_metrics()
print(f'  VaR 95%: {metrics.var_95:.4f}')
print(f'  VaR 99%: {metrics.var_99:.4f}')
print(f'  Expected Shortfall: {metrics.expected_shortfall:.4f}')
print(f'  Max Drawdown: {metrics.max_drawdown:.2f}')
print(f'  Sharpe Ratio: {metrics.sharpe_ratio:.4f}')
print()

# TEST 10: 고성능 통계
print('TEST 10: High-Performance Statistics')
stats = manager.get_stats()
print(f'  Num returns: {stats["num_returns"]}')
print(f'  Num PnL: {stats["num_pnl"]}')
print(f'  Num volatility: {stats["num_volatility"]}')
print()

# TEST 11: 대규모 데이터 처리 (성능 테스트)
print('TEST 11: Large-Scale Data Processing (Performance Test)')
manager = QuantitativeRiskManager(window_size=10000)

# 10,000개 수익률 생성
large_returns = np.random.normal(0.001, 0.02, 10000).astype(np.float32)
large_pnl = np.random.normal(1000, 500, 10000).astype(np.float32)

start_time = time.time()
manager.record_returns_batch(large_returns)
manager.record_pnl_batch(large_pnl)
elapsed_record = time.time() - start_time

start_time = time.time()
var_95 = manager.calculate_var(0.95)
var_99 = manager.calculate_var(0.99)
es = manager.calculate_expected_shortfall(0.95)
elapsed_var = time.time() - start_time

start_time = time.time()
max_dd = manager.calculate_max_drawdown()
sharpe = manager.calculate_sharpe_ratio()
elapsed_stats = time.time() - start_time

print(f'  Record 10K returns + 10K PnL: {elapsed_record*1000:.2f}ms')
print(f'  Calculate VaR 95%, 99%, ES: {elapsed_var*1000:.2f}ms')
print(f'  Calculate Max DD, Sharpe: {elapsed_stats*1000:.2f}ms')
print(f'  Total: {(elapsed_record + elapsed_var + elapsed_stats)*1000:.2f}ms')
print()

print('=== All Tests Completed ===')
