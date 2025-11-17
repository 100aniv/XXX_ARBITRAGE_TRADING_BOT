#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D11 Watchdog Tests
"""

from arbitrage.watchdog import Watchdog, WatchdogConfig, AlertLevel

print('=== D11 Watchdog Tests ===')
print()

# TEST 1: 정상 상태
print('TEST 1: Healthy State')
config = WatchdogConfig()
watchdog = Watchdog(config)
metrics = {
    'ws_lag_ms': 100.0,
    'redis_heartbeat_age_ms': 5000.0,
    'loop_latency_ms': 50.0,
    'safety_rejections_count': 0
}
status = watchdog.evaluate(metrics)
print(f'  Is healthy: {status.is_healthy}')
print(f'  Alerts: {len(status.alerts)}')
print(f'  Summary: {watchdog.get_status_summary()}')
print()

# TEST 2: WebSocket 지연 경고
print('TEST 2: WebSocket Lag Warning')
watchdog = Watchdog(config)
metrics = {
    'ws_lag_ms': 3000.0,  # 경고 임계치 초과
    'redis_heartbeat_age_ms': 5000.0,
    'loop_latency_ms': 50.0,
    'safety_rejections_count': 0
}
status = watchdog.evaluate(metrics)
print(f'  Is healthy: {status.is_healthy}')
print(f'  Alerts: {len(status.alerts)}')
for alert in status.alerts:
    print(f'    - [{alert.level.value}] {alert.message}')
print()

# TEST 3: Redis heartbeat 에러
print('TEST 3: Redis Heartbeat Error')
watchdog = Watchdog(config)
metrics = {
    'ws_lag_ms': 100.0,
    'redis_heartbeat_age_ms': 35000.0,  # 에러 임계치 초과
    'loop_latency_ms': 50.0,
    'safety_rejections_count': 0
}
status = watchdog.evaluate(metrics)
print(f'  Is healthy: {status.is_healthy}')
print(f'  Alerts: {len(status.alerts)}')
for alert in status.alerts:
    print(f'    - [{alert.level.value}] {alert.message}')
print()

# TEST 4: 루프 지연 에러
print('TEST 4: Loop Latency Error')
watchdog = Watchdog(config)
metrics = {
    'ws_lag_ms': 100.0,
    'redis_heartbeat_age_ms': 5000.0,
    'loop_latency_ms': 6000.0,  # 에러 임계치 초과
    'safety_rejections_count': 0
}
status = watchdog.evaluate(metrics)
print(f'  Is healthy: {status.is_healthy}')
print(f'  Consecutive errors: {watchdog.status.consecutive_errors}')
print()

# TEST 5: 연속 에러 → Shutdown
print('TEST 5: Consecutive Errors → Shutdown')
watchdog = Watchdog(config)
for i in range(3):
    metrics = {
        'ws_lag_ms': 100.0,
        'redis_heartbeat_age_ms': 5000.0,
        'loop_latency_ms': 6000.0,  # 계속 에러
        'safety_rejections_count': 0
    }
    status = watchdog.evaluate(metrics)
    print(f'  Iteration {i+1}: errors={watchdog.status.consecutive_errors}, shutdown={status.should_shutdown}')
print()

# TEST 6: 안전 검증 거부 경고
print('TEST 6: Safety Rejections Warning')
watchdog = Watchdog(config)
metrics = {
    'ws_lag_ms': 100.0,
    'redis_heartbeat_age_ms': 5000.0,
    'loop_latency_ms': 50.0,
    'safety_rejections_count': 15  # 경고 임계치 초과
}
status = watchdog.evaluate(metrics)
print(f'  Is healthy: {status.is_healthy}')
print(f'  Alerts: {len(status.alerts)}')
for alert in status.alerts:
    print(f'    - [{alert.level.value}] {alert.message}')
print()

print('=== All Tests Completed ===')
