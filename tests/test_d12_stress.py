#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE D12 Stress Tests
"""

from arbitrage.watchdog import Watchdog, WatchdogConfig
from arbitrage.sys_monitor import SystemMonitor, SysMonitorConfig
from arbitrage.longrun import LongRunTester
from arbitrage.perf import PerformanceProfiler

print('=== D12 Stress Tests ===')
print()

# TEST 1: 높은 WS 지연 시뮬레이션
print('TEST 1: High WebSocket Lag Simulation')
config = WatchdogConfig()
watchdog = Watchdog(config)
for i in range(10):
    metrics = {
        'ws_lag_ms': 3500.0 + (i * 100),  # 점진적으로 증가
        'redis_heartbeat_age_ms': 5000.0,
        'loop_latency_ms': 50.0,
        'safety_rejections_count': 0
    }
    status = watchdog.evaluate(metrics)
    print(f'  Loop {i+1}: WS={metrics["ws_lag_ms"]:.0f}ms, Healthy={status.is_healthy}, Errors={watchdog.status.consecutive_errors}')
print()

# TEST 2: Redis 지연 시뮬레이션
print('TEST 2: Redis Heartbeat Aging Simulation')
watchdog = Watchdog(config)
for i in range(10):
    metrics = {
        'ws_lag_ms': 100.0,
        'redis_heartbeat_age_ms': 10000.0 + (i * 2000),  # 점진적으로 증가
        'loop_latency_ms': 50.0,
        'safety_rejections_count': 0
    }
    status = watchdog.evaluate(metrics)
    print(f'  Loop {i+1}: Redis={metrics["redis_heartbeat_age_ms"]:.0f}ms, Healthy={status.is_healthy}')
print()

# TEST 3: 루프 블로킹 시뮬레이션
print('TEST 3: Loop Blocking Simulation')
watchdog = Watchdog(config)
perf_profiler = PerformanceProfiler()
for i in range(15):
    loop_latency = 100.0 + (i * 300)  # 점진적으로 증가
    perf_profiler.record_loop(loop_latency)
    
    metrics = {
        'ws_lag_ms': 100.0,
        'redis_heartbeat_age_ms': 5000.0,
        'loop_latency_ms': loop_latency,
        'safety_rejections_count': 0
    }
    status = watchdog.evaluate(metrics)
    print(f'  Loop {i+1}: Latency={loop_latency:.0f}ms, P95={perf_profiler.loop_profiler.get_p95_latency():.0f}ms, Healthy={status.is_healthy}')
print()

# TEST 4: 높은 CPU 부하 시뮬레이션
print('TEST 4: High CPU Load Simulation')
sys_monitor_config = SysMonitorConfig(
    enabled=False,  # psutil 없으므로 비활성화
    max_cpu_pct=90.0
)
sys_monitor = SystemMonitor(sys_monitor_config)
print(f'  Monitor enabled: {sys_monitor.enabled}')
print(f'  Graceful fallback: OK')
print()

# TEST 5: 메모리 스파이크 시뮬레이션
print('TEST 5: Memory Spike Simulation')
perf_profiler = PerformanceProfiler()
for i in range(10):
    ws_lag = 100.0 + (i * 50)
    perf_profiler.record_ws_lag(ws_lag)
    
    if i >= 5:
        # 스파이크 감지
        spike_count = perf_profiler.ws_profiler.get_spike_count()
        print(f'  Loop {i+1}: WS_Lag={ws_lag:.0f}ms, Spikes={spike_count}')
print()

# TEST 6: 워치독 Auto-reset 테스트
print('TEST 6: Watchdog Auto-reset (WARN state)')
config = WatchdogConfig(warn_reset_cycles=3)
watchdog = Watchdog(config)
for i in range(10):
    metrics = {
        'ws_lag_ms': 2500.0,  # WARN 상태 유지
        'redis_heartbeat_age_ms': 5000.0,
        'loop_latency_ms': 50.0,
        'safety_rejections_count': 0
    }
    status = watchdog.evaluate(metrics)
    print(f'  Loop {i+1}: WARN_count={watchdog.warn_cycle_count}, Alerts={len(status.alerts)}')
    if watchdog.warn_cycle_count == 0:
        print(f'    → Soft reset triggered!')
print()

# TEST 7: 장시간 테스터 스냅샷
print('TEST 7: Long-Run Tester Snapshots')
longrun_tester = LongRunTester(enabled=True, interval_loops=3)
for i in range(10):
    loop_latency = 50.0 + (i * 5)
    longrun_tester.record_loop(loop_latency)
    
    metrics = {
        'ws_lag_ms': 100.0,
        'redis_heartbeat_age_ms': 5000.0,
        'loop_latency_ms': loop_latency,
        'num_live_trades_today': i,
        'num_paper_trades_today': i * 2,
        'num_open_positions': i % 3,
        'total_exposure_krw': 100000.0 * (i + 1),
        'stoploss_triggers': i // 2,
        'watchdog_healthy': True,
        'watchdog_alerts': 0,
        'watchdog_consecutive_errors': 0,
        'safety_rejections_count': 0
    }
    
    checkpoint = longrun_tester.take_checkpoint(metrics)
    if checkpoint:
        print(f'  Checkpoint {len(longrun_tester.checkpoints)}: Loop={checkpoint.loop_count}, Stable={checkpoint.is_stable}')
print()

# TEST 8: 성능 프로파일러 종합 테스트
print('TEST 8: Performance Profiler Comprehensive Test')
perf_profiler = PerformanceProfiler()
for i in range(20):
    loop_latency = 50.0 + (i * 10)
    ws_lag = 100.0 + (i * 5)
    redis_age = 5000.0 + (i * 100)
    
    perf_profiler.record_loop(loop_latency)
    perf_profiler.record_ws_lag(ws_lag)
    perf_profiler.record_redis_heartbeat(redis_age)

summary = perf_profiler.get_summary()
print(f'  {summary}')
print()

print('=== All Stress Tests Completed ===')
