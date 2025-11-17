#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D13 Environment Loader Tests
"""

import os
import tempfile
from pathlib import Path
from arbitrage.secrets import SecretsManager

print('=== D13 Environment Loader Tests ===')
print()

# TEST 1: 필수 키 검증
print('TEST 1: Required Keys Validation')
try:
    # 필수 키 없이 초기화 (fail_on_missing=True)
    manager = SecretsManager(env_file=".env_nonexistent", fail_on_missing=True)
    print('  ❌ Should have raised ValueError')
except ValueError as e:
    print(f'  ✅ Correctly raised ValueError: {str(e)[:60]}...')
except Exception as e:
    print(f'  ⚠️  Unexpected error: {type(e).__name__}')
print()

# TEST 2: 필수 키 누락 시 fail_on_missing=False
print('TEST 2: Missing Keys with fail_on_missing=False')
manager = SecretsManager(env_file=".env_nonexistent", fail_on_missing=False)
print(f'  Missing keys: {manager.missing_keys}')
print(f'  Secrets loaded: {len(manager.secrets)}')
print()

# TEST 3: 환경 변수에서 로드
print('TEST 3: Load from Environment Variables')
os.environ['UPBIT_API_KEY'] = 'test_upbit_key'
os.environ['UPBIT_API_SECRET'] = 'test_upbit_secret'
os.environ['BINANCE_API_KEY'] = 'test_binance_key'
os.environ['BINANCE_API_SECRET'] = 'test_binance_secret'
os.environ['TELEGRAM_BOT_TOKEN'] = 'test_telegram_token'
os.environ['TELEGRAM_CHAT_ID'] = '123456'

manager = SecretsManager(env_file=".env_nonexistent", fail_on_missing=True)
print(f'  ✅ Loaded {len(manager.secrets)} secrets from environment')
print(f'  UPBIT_API_KEY: {manager.get("UPBIT_API_KEY")[:10]}...')
print()

# TEST 4: .env 파일 파싱 (수동)
print('TEST 4: Manual .env File Parsing')
with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False, encoding='utf-8') as f:
    f.write('# Test .env file\n')
    f.write('TEST_KEY1=value1\n')
    f.write('TEST_KEY2="value2"\n')
    f.write('TEST_KEY3=\'value3\'\n')
    env_file = f.name

try:
    # 환경 변수 초기화
    os.environ.pop('TEST_KEY1', None)
    os.environ.pop('TEST_KEY2', None)
    os.environ.pop('TEST_KEY3', None)
    
    manager = SecretsManager(env_file=env_file, fail_on_missing=False)
    print(f'  ✅ TEST_KEY1: {os.environ.get("TEST_KEY1")}')
    print(f'  ✅ TEST_KEY2: {os.environ.get("TEST_KEY2")}')
    print(f'  ✅ TEST_KEY3: {os.environ.get("TEST_KEY3")}')
finally:
    Path(env_file).unlink()
print()

# TEST 5: 시크릿 마스킹
print('TEST 5: Secret Masking')
manager = SecretsManager(env_file=".env_nonexistent", fail_on_missing=False)
all_secrets = manager.get_all()
print(f'  UPBIT_API_SECRET masked: {all_secrets.get("UPBIT_API_SECRET")}')
print(f'  BINANCE_API_SECRET masked: {all_secrets.get("BINANCE_API_SECRET")}')
print(f'  TELEGRAM_BOT_TOKEN masked: {all_secrets.get("TELEGRAM_BOT_TOKEN")}')
print()

# TEST 6: 선택적 키 타입 변환
print('TEST 6: Optional Keys Type Conversion')
os.environ['LIVE_TRADING'] = 'true'
os.environ['ENVIRONMENT'] = 'prod'
os.environ['LOG_LEVEL'] = 'DEBUG'

manager = SecretsManager(env_file=".env_nonexistent", fail_on_missing=False)
print(f'  LIVE_TRADING (bool): {manager.get("LIVE_TRADING")} (type: {type(manager.get("LIVE_TRADING")).__name__})')
print(f'  ENVIRONMENT (str): {manager.get("ENVIRONMENT")}')
print(f'  LOG_LEVEL (str): {manager.get("LOG_LEVEL")}')
print(f'  is_live_mode(): {manager.is_live_mode()}')
print(f'  get_environment(): {manager.get_environment()}')
print()

print('=== All Tests Completed ===')
