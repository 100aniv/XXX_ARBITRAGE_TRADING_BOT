#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D11 Logging Tests
"""

import os
from pathlib import Path
from arbitrage.logging_utils import (
    get_logger,
    get_live_loop_logger,
    get_health_logger,
    get_safety_logger,
    get_watchdog_logger,
    get_sys_monitor_logger,
    reset_loggers
)

print('=== D11 Logging Tests ===')
print()

# TEST 1: 로그 디렉토리 확인
print('TEST 1: Log Directory')
log_dir = Path(__file__).parent / "logs"
print(f'  Log directory: {log_dir}')
print(f'  Exists: {log_dir.exists()}')
print()

# TEST 2: 공통 로거 생성
print('TEST 2: Common Logger Creation')
logger = get_logger("test_module", component="test")
print(f'  Logger name: {logger.name}')
print(f'  Logger level: {logger.level}')
print(f'  Handlers: {len(logger.handlers)}')
print()

# TEST 3: 컴포넌트별 로거
print('TEST 3: Component-Specific Loggers')
loggers = {
    'live_loop': get_live_loop_logger(),
    'health': get_health_logger(),
    'safety': get_safety_logger(),
    'watchdog': get_watchdog_logger(),
    'sys_monitor': get_sys_monitor_logger()
}
for name, logger in loggers.items():
    print(f'  {name}: {logger.name}')
print()

# TEST 4: 로그 출력 테스트
print('TEST 4: Log Output Test')
reset_loggers()
logger = get_live_loop_logger()
logger.info("Test INFO message")
logger.warning("Test WARNING message")
logger.error("Test ERROR message")
print('  (Check logs/live_loop.log for output)')
print()

# TEST 5: 로그 파일 생성 확인
print('TEST 5: Log Files Created')
log_dir = Path(__file__).parent / "logs"
if log_dir.exists():
    log_files = list(log_dir.glob("*.log"))
    print(f'  Log files: {len(log_files)}')
    for log_file in log_files:
        size = log_file.stat().st_size
        print(f'    - {log_file.name} ({size} bytes)')
else:
    print('  Log directory not found')
print()

print('=== All Tests Completed ===')
