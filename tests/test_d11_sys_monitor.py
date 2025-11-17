#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D11 System Monitor Tests
"""

from arbitrage.sys_monitor import SystemMonitor, SysMonitorConfig

print('=== D11 System Monitor Tests ===')
print()

# TEST 1: 모니터 초기화
print('TEST 1: Monitor Initialization')
config = SysMonitorConfig(
    enabled=True,
    max_cpu_pct=90.0,
    max_rss_mb=2048.0,
    warn_cpu_pct=75.0,
    warn_rss_mb=1536.0
)
monitor = SystemMonitor(config)
print(f'  Enabled: {monitor.enabled}')
print(f'  Config: max_cpu={config.max_cpu_pct}%, max_rss={config.max_rss_mb}MB')
print()

# TEST 2: 리소스 샘플링
print('TEST 2: Resource Sampling')
if monitor.enabled:
    sample = monitor.sample()
    print(f'  Available: {sample.available}')
    print(f'  CPU: {sample.cpu_pct:.1f}%')
    print(f'  Memory: {sample.rss_mb:.1f}MB')
    print(f'  Open files: {sample.open_files}')
    print(f'  Threads: {sample.num_threads}')
else:
    print('  System monitoring disabled (psutil not available)')
print()

# TEST 3: 임계치 확인
print('TEST 3: Threshold Check')
if monitor.enabled:
    sample = monitor.sample()
    thresholds = monitor.check_thresholds(sample)
    print(f'  CPU OK: {thresholds["cpu_ok"]}')
    print(f'  CPU Warn: {thresholds["cpu_warn"]}')
    print(f'  Memory OK: {thresholds["memory_ok"]}')
    print(f'  Memory Warn: {thresholds["memory_warn"]}')
    if thresholds['alerts']:
        print(f'  Alerts:')
        for alert in thresholds['alerts']:
            print(f'    - {alert}')
else:
    print('  System monitoring disabled')
print()

# TEST 4: 통계 조회
print('TEST 4: Statistics')
if monitor.enabled:
    stats = monitor.get_stats()
    print(f'  Available: {stats["available"]}')
    print(f'  CPU: {stats["cpu_pct"]:.1f}%')
    print(f'  Memory: {stats["rss_mb"]:.1f}MB')
else:
    print('  System monitoring disabled')
print()

# TEST 5: psutil 없는 환경 (graceful fallback)
print('TEST 5: Graceful Fallback (psutil disabled)')
config = SysMonitorConfig(enabled=False)
monitor = SystemMonitor(config)
print(f'  Enabled: {monitor.enabled}')
sample = monitor.sample()
print(f'  Sample available: {sample.available}')
stats = monitor.get_stats()
print(f'  Stats available: {stats["available"]}')
print()

print('=== All Tests Completed ===')
