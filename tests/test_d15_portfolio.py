#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D15 High-Performance Portfolio Optimization Tests
"""

import sys
from pathlib import Path
import numpy as np
import time

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.portfolio_optimizer import PortfolioOptimizer

print('=== D15 High-Performance Portfolio Optimization Tests ===')
print()

# TEST 1: 포트폴리오 초기화
print('TEST 1: Portfolio Initialization')
optimizer = PortfolioOptimizer(window_size=60)
print(f'  ✅ Portfolio optimizer initialized')
print(f'  Window size: {optimizer.window_size}')
print()

# TEST 2: 벡터화 배치 수익률 추가
print('TEST 2: Vectorized Batch Returns Addition')
symbols = ['BTC', 'ETH', 'XRP']
returns_data = {
    'BTC': np.array([0.5, 0.3, -0.2, 0.4, 0.6, 0.2, -0.1, 0.5], dtype=np.float32),
    'ETH': np.array([0.4, 0.2, -0.3, 0.5, 0.7, 0.1, -0.2, 0.6], dtype=np.float32),
    'XRP': np.array([0.3, 0.1, -0.1, 0.3, 0.5, 0.0, -0.3, 0.4], dtype=np.float32)
}

# 벡터화 배치 추가
optimizer.add_returns_batch(returns_data)

print(f'  Added returns for {len(symbols)} symbols (vectorized)')
print(f'  Returns DataFrame shape: {optimizer.returns_df.shape}')
print(f'  Symbols: {optimizer.symbols}')
print()

# TEST 3: 벡터화 상관관계 행렬
print('TEST 3: Vectorized Correlation Matrix')
corr_matrix = optimizer.calculate_correlation_matrix()
if corr_matrix is not None:
    print(f'  ✅ Correlation matrix calculated (vectorized)')
    print(f'  Shape: {corr_matrix.shape}')
    print(f'  Matrix:\n{corr_matrix}')
else:
    print(f'  ⚠️  Correlation matrix not available')
print()

# TEST 4: 벡터화 공분산 행렬
print('TEST 4: Vectorized Covariance Matrix')
cov_matrix = optimizer.calculate_covariance_matrix()
if cov_matrix is not None:
    print(f'  ✅ Covariance matrix calculated (vectorized)')
    print(f'  Shape: {cov_matrix.shape}')
    print(f'  Diagonal: {np.diag(cov_matrix)}')
else:
    print(f'  ⚠️  Covariance matrix not available')
print()

# TEST 5: 벡터화 리스크 패리티 가중치
print('TEST 5: Vectorized Risk Parity Weights')
weights = optimizer.get_risk_parity_weights()
print(f'  Weights (vectorized):')
for symbol, weight in weights.items():
    print(f'    {symbol}: {weight:.4f} ({weight*100:.2f}%)')
print(f'  Total: {sum(weights.values()):.4f}')
print()

# TEST 6: 벡터화 평균-분산 최적화
print('TEST 6: Vectorized Mean-Variance Optimization')
mv_weights = optimizer.get_mean_variance_weights()
print(f'  Weights (vectorized):')
for symbol, weight in mv_weights.items():
    print(f'    {symbol}: {weight:.4f} ({weight*100:.2f}%)')
print(f'  Total: {sum(mv_weights.values()):.4f}')
print()

# TEST 7: 최적 가중치 (특정 심볼 리스트)
print('TEST 7: Optimal Weights for Symbol List')
requested_symbols = ['BTC', 'ETH']
optimal_weights = optimizer.get_optimal_weights(requested_symbols, method='risk_parity')
print(f'  Requested symbols: {requested_symbols}')
print(f'  Optimal weights (vectorized):')
for symbol, weight in optimal_weights.items():
    print(f'    {symbol}: {weight:.4f} ({weight*100:.2f}%)')
print()

# TEST 8: 고성능 통계
print('TEST 8: High-Performance Statistics')
stats = optimizer.get_stats()
print(f'  Number of symbols: {stats["num_symbols"]}')
print(f'  Symbols: {stats["symbols"]}')
print(f'  Number of observations: {stats["num_observations"]}')
print(f'  Correlation matrix available: {stats["correlation_matrix_available"]}')
print(f'  Covariance matrix available: {stats["covariance_matrix_available"]}')
print()

# TEST 9: 대규모 데이터 처리 (성능 테스트)
print('TEST 9: Large-Scale Data Processing (Performance Test)')
optimizer = PortfolioOptimizer(window_size=1000)

# 100개 자산, 1000개 관측치 생성
num_assets = 100
num_observations = 1000
large_returns = {
    f'ASSET_{i}': np.random.normal(0.001, 0.02, num_observations).astype(np.float32)
    for i in range(num_assets)
}

start_time = time.time()
optimizer.add_returns_batch(large_returns)
elapsed_batch = time.time() - start_time

start_time = time.time()
corr = optimizer.calculate_correlation_matrix()
elapsed_corr = time.time() - start_time

start_time = time.time()
weights = optimizer.get_risk_parity_weights()
elapsed_weights = time.time() - start_time

print(f'  Batch add ({num_assets} assets, {num_observations} obs): {elapsed_batch*1000:.2f}ms')
print(f'  Correlation matrix ({num_assets}x{num_assets}): {elapsed_corr*1000:.2f}ms')
print(f'  Risk parity weights: {elapsed_weights*1000:.2f}ms')
print(f'  Total: {(elapsed_batch + elapsed_corr + elapsed_weights)*1000:.2f}ms')
print()

print('=== All Tests Completed ===')
