#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D15 High-Performance Volatility Model Tests

NOTE: This test requires PyTorch (torch) which is environment-dependent.
      Marked as optional_ml for Core Regression SSOT.
"""
import pytest

# Mark entire module as optional_ml (excluded from Core Regression)
pytestmark = pytest.mark.optional_ml

import sys
from pathlib import Path
import numpy as np

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.volatility_model import VolatilityPredictor

print('=== D15 High-Performance Volatility Model Tests ===')
print()

# TEST 1: 모델 초기화 및 GPU 확인
print('TEST 1: Model Initialization with GPU Support')
predictor = VolatilityPredictor(sequence_length=20)
print(f'  ✅ Predictor initialized')
print(f'  Device: {predictor.device}')
print(f'  Sequence length: {predictor.sequence_length}')
print()

# TEST 2: 벡터화 변동성 기록
print('TEST 2: Vectorized Volatility Recording')
volatilities = np.array([0.2, 0.25, 0.22, 0.28, 0.30, 0.25, 0.23, 0.27, 0.29, 0.26], dtype=np.float32)
predictor.record_volatilities_batch(volatilities)

print(f'  Recorded {len(predictor.volatility_history)} volatilities (vectorized)')
print(f'  History dtype: {predictor.volatility_history.dtype}')
print(f'  Current volatility: {predictor.volatility_history[-1]:.2f}')

pred = predictor.predict()
print(f'  Predicted next volatility: {pred:.2f}')
print()

# TEST 3: 배치 예측 (벡터화)
print('TEST 3: Batch Prediction (Vectorized)')
predictor = VolatilityPredictor(sequence_length=10)

# 30개의 변동성 데이터 추가 (벡터화)
volatilities = np.linspace(0.2, 0.3, 30, dtype=np.float32)
predictor.record_volatilities_batch(volatilities)

# 배치 예측
batch_preds = predictor.predict_batch(num_predictions=5)
print(f'  Volatility history length: {len(predictor.volatility_history)}')
print(f'  Batch predictions shape: {batch_preds.shape}')
print(f'  Batch predictions: {batch_preds}')
print(f'  All predictions in range [0.0, 1.0]: {np.all((batch_preds >= 0.0) & (batch_preds <= 1.0))}')
print()

# TEST 4: 고성능 통계 (벡터화)
print('TEST 4: High-Performance Statistics (Vectorized)')
stats = predictor.get_stats()
print(f'  History length: {stats["history_length"]}')
print(f'  Current volatility: {stats["current_volatility"]:.4f}')
print(f'  Mean volatility: {stats["mean_volatility"]:.4f}')
print(f'  Std volatility: {stats["std_volatility"]:.4f}')
print(f'  Min volatility: {stats["min_volatility"]:.4f}')
print(f'  Max volatility: {stats["max_volatility"]:.4f}')
print()

# TEST 5: 데이터 부족 시 처리
print('TEST 5: Handling Insufficient Data')
predictor = VolatilityPredictor(sequence_length=20)
predictor.record_volatility(0.3)
predictor.record_volatility(0.35)

pred = predictor.predict()
print(f'  Data points: {len(predictor.volatility_history)}')
print(f'  Predicted volatility: {pred:.2f}')
print(f'  ✅ Graceful fallback to current volatility')
print()

# TEST 6: 모드 전환
print('TEST 6: Model Mode Switching')
predictor.train_mode()
print(f'  ✅ Switched to training mode')
predictor.eval_mode()
print(f'  ✅ Switched to evaluation mode')
print()

# TEST 7: 대규모 데이터 처리 (성능 테스트)
print('TEST 7: Large-Scale Data Processing (Performance Test)')
import time

predictor = VolatilityPredictor(sequence_length=20)
large_volatilities = np.random.uniform(0.1, 0.5, 10000).astype(np.float32)

start_time = time.time()
predictor.record_volatilities_batch(large_volatilities)
elapsed = time.time() - start_time

print(f'  Recorded 10,000 volatilities in {elapsed*1000:.2f}ms')
print(f'  History length: {len(predictor.volatility_history)}')
print(f'  Throughput: {10000/elapsed:.0f} records/sec')
print()

print('=== All Tests Completed ===')
