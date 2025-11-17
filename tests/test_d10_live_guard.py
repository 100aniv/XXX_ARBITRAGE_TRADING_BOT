#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D10 Live Guard Tests
"""

import os
from arbitrage.live_guard import LiveGuard

print('=== D10 Live Guard Tests ===')
print()

# 설정
config = {
    'mode': {
        'current': 'mock'
    },
    'live_guards': {
        'require_env_flag': True,
        'require_manual_confirm_file': True,
        'require_safety_pass': True,
        'dry_run_on_startup': True,
        'dry_run_cycles': 3
    }
}

# TEST 1: Mock 모드 (항상 안전)
print('TEST 1: Mock Mode')
live_guard = LiveGuard(config)
status = live_guard.evaluate(0)
print(f'  Mode: {status.mode}')
print(f'  Live allowed: {status.is_live_allowed()}')
print(f'  Blocked reasons: {status.reason_blocked}')
print()

# TEST 2: Paper 모드 (항상 안전)
print('TEST 2: Paper Mode')
config['mode']['current'] = 'paper'
live_guard = LiveGuard(config)
status = live_guard.evaluate(0)
print(f'  Mode: {status.mode}')
print(f'  Live allowed: {status.is_live_allowed()}')
print()

# TEST 3: Live 모드 - 환경 변수 없음 (차단)
print('TEST 3: Live Mode - No Env Flag')
config['mode']['current'] = 'live'
live_guard = LiveGuard(config)
status = live_guard.evaluate(0)
print(f'  Mode: {status.mode}')
print(f'  Live allowed: {status.is_live_allowed()}')
print(f'  Blocked reasons: {status.reason_blocked}')
print()

# TEST 4: Live 모드 - 환경 변수 설정 (여전히 파일 없음)
print('TEST 4: Live Mode - With Env Flag')
os.environ['LIVE_TRADING'] = '1'
live_guard = LiveGuard(config)
status = live_guard.evaluate(0)
print(f'  Mode: {status.mode}')
print(f'  Env flag OK: {status.env_flag_ok}')
print(f'  Live allowed: {status.is_live_allowed()}')
print(f'  Blocked reasons: {status.reason_blocked}')
print()

# TEST 5: 드라이런 사이클 확인
print('TEST 5: Dry-Run Cycles')
config['live_guards']['dry_run_cycles'] = 2
live_guard = LiveGuard(config)
for cycle in range(4):
    status = live_guard.evaluate(cycle)
    print(f'  Cycle {cycle}: dry_run_active={status.dry_run_active}, live_allowed={status.is_live_allowed()}')
print()

# TEST 6: 상태 배너
print('TEST 6: Status Banner')
config['mode']['current'] = 'mock'
live_guard = LiveGuard(config)
status = live_guard.evaluate(0)
banner = live_guard.get_status_banner(status)
print(f'  {banner}')
print()

# 정리
del os.environ['LIVE_TRADING']

print('=== All Tests Completed ===')
