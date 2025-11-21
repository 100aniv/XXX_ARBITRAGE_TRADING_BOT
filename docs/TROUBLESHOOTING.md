# Arbitrage Engine - Troubleshooting Guide

**Status:** PRODUCTION READY  
**Author:** Arbitrage Engine Team  
**Date:** 2025-11-21  
**Version:** 1.0

---

## Table of Contents

1. [Overview](#overview)
2. [Diagnostic Tools](#diagnostic-tools)
3. [Service Issues](#service-issues)
4. [Redis Issues](#redis-issues)
5. [PostgreSQL Issues](#postgresql-issues)
6. [WebSocket Issues](#websocket-issues)
7. [Engine Issues](#engine-issues)
8. [Performance Issues](#performance-issues)
9. [Resource Issues](#resource-issues)
10. [State Management Issues](#state-management-issues)
11. [Trading Issues](#trading-issues)
12. [Logging Issues](#logging-issues)
13. [Configuration Issues](#configuration-issues)
14. [Network Issues](#network-issues)
15. [Error Code Reference](#error-code-reference)

---

## Overview

이 문서는 Arbitrage Engine 운영 중 발생할 수 있는 20개 이상의 문제와 해결책을 제공합니다.

### Problem-Solving Framework

```
1. IDENTIFY: 문제 증상 파악
2. DIAGNOSE: 근본 원인 분석
3. MITIGATE: 즉각적인 완화 조치
4. RESOLVE: 영구적인 해결
5. PREVENT: 재발 방지
```

### Quick Diagnosis Commands

```bash
# Overall health check
python healthcheck.py

# Service status
docker-compose ps
sudo systemctl status arbitrage

# Recent errors
docker-compose logs --since 10m arbitrage-engine | grep ERROR

# Resource usage
docker stats arbitrage-engine --no-stream

# Trading activity
python tools/monitor.py --metrics
```

---

## Diagnostic Tools

### Health Check Tool

```bash
# Run full health check
python healthcheck.py

# Output interpretation:
# ✓ = OK
# ✗ = FAILED
```

### Monitoring CLI

```bash
# Real-time metrics
python tools/monitor.py --metrics

# Tail logs
python tools/monitor.py --tail

# Search logs
python tools/monitor.py --search "pattern"

# Errors only
python tools/monitor.py --errors
```

### Log Analysis

```bash
# Error frequency
docker-compose logs --since 1h arbitrage-engine | grep ERROR | wc -l

# Top errors
docker-compose logs --since 1h arbitrage-engine | grep ERROR | sort | uniq -c | sort -rn | head -n 10

# Error timeline
docker-compose logs --since 1h arbitrage-engine | grep ERROR | awk '{print $1, $2}'
```

### Database Queries

```bash
# Recent snapshots
psql -h localhost -U arbitrage -d arbitrage -c "SELECT session_id, created_at, status FROM session_snapshots ORDER BY created_at DESC LIMIT 10;"

# Session status
psql -h localhost -U arbitrage -d arbitrage -c "SELECT status, COUNT(*) FROM session_snapshots GROUP BY status;"

# System logs (errors)
psql -h localhost -U arbitrage -d arbitrage -c "SELECT * FROM system_logs WHERE level='ERROR' ORDER BY created_at DESC LIMIT 20;"
```

---

## Service Issues

### Problem 1: Service Won't Start

**Symptoms:**
- `sudo systemctl start arbitrage` fails immediately
- `docker-compose up` exits with error

**Diagnosis:**
```bash
# Check startup logs
sudo journalctl -u arbitrage --since "1 minute ago" -p err
docker-compose logs arbitrage-engine

# Check for port conflicts
sudo netstat -tulpn | grep -E ':(6379|5432|8080)'

# Check dependencies
docker-compose ps redis postgres
```

**Common Causes & Solutions:**

#### Cause 1.1: Dependencies Not Ready

**Error:** `ConnectionRefusedError: Redis/PostgreSQL not ready`

**Solution:**
```bash
# Start dependencies first
docker-compose up -d redis postgres

# Wait for health checks (30s)
watch -n 1 'docker-compose ps'

# Start engine
docker-compose up -d arbitrage-engine
```

#### Cause 1.2: Configuration Error

**Error:** `ConfigValidationError: Invalid configuration`

**Solution:**
```bash
# Validate config
python -c "from config.loader import load_config; load_config('production')"

# Check for syntax errors
python -m py_compile config/environments/production.py

# Fix configuration
nano config/environments/production.py
```

#### Cause 1.3: Missing Environment Variables

**Error:** `KeyError: 'REDIS_HOST'`

**Solution:**
```bash
# Check environment file exists
ls -l /etc/arbitrage/arbitrage.env

# Verify required variables
cat /etc/arbitrage/arbitrage.env

# Required variables:
# ENV, MODE, REDIS_HOST, POSTGRES_HOST, etc.
```

#### Cause 1.4: Database Migration Pending

**Error:** `ProgrammingError: relation "system_logs" does not exist`

**Solution:**
```bash
# Apply migrations
python scripts/apply_d72_migration.py
python scripts/apply_d72_4_migration.py

# Verify tables
psql -h localhost -U arbitrage -d arbitrage -c "\dt"
```

### Problem 2: Service Crashes Repeatedly

**Symptoms:**
- Service starts but crashes after 1-60 seconds
- systemd shows "activating (auto-restart)"
- Docker container restarts continuously

**Diagnosis:**
```bash
# Check crash logs
sudo journalctl -u arbitrage --since "10 minutes ago" | grep -A 10 "Traceback"

# Docker restart count
docker inspect arbitrage-engine | grep RestartCount

# Core dump (if available)
ls -l /var/crash/
```

**Common Causes & Solutions:**

#### Cause 2.1: Uncaught Exception

**Error:** `Exception in main loop: <error details>`

**Solution:**
```bash
# Identify exception type
docker-compose logs arbitrage-engine | grep -E "(Exception|Error)" | tail -n 20

# Check for known issues
# - NoneType error → Missing data validation
# - KeyError → Missing configuration
# - IndexError → Empty data structure

# Hotfix: Add try-except (code change required)
# Permanent fix: Fix root cause in code
```

#### Cause 2.2: Memory Leak (OOM Killer)

**Error:** `Killed` (exit code 137)

**Solution:**
```bash
# Check OOM events
dmesg | grep -i "out of memory"
docker inspect arbitrage-engine | grep OOMKilled

# Temporary fix: Increase memory limit
# Edit docker-compose.yml:
# mem_limit: 4g

# Permanent fix: Fix memory leak (profiling required)
```

#### Cause 2.3: Segmentation Fault

**Error:** `Segmentation fault (core dumped)`

**Solution:**
```bash
# Check for binary incompatibility
python --version
pip list | grep -E "(redis|psycopg2)"

# Reinstall problematic packages
pip install --force-reinstall redis psycopg2-binary
```

### Problem 3: Service Hangs/Freezes

**Symptoms:**
- Service running but not responding
- Health check timeout
- No recent logs

**Diagnosis:**
```bash
# Check process state
docker exec arbitrage-engine ps aux

# Check for deadlock
docker exec arbitrage-engine python -c "import psutil; print(psutil.Process().num_threads())"

# Check open files
docker exec arbitrage-engine lsof | wc -l
```

**Solution:**
```bash
# Send SIGUSR1 (dump stack trace if implemented)
docker exec arbitrage-engine kill -USR1 1

# Force restart
docker-compose restart arbitrage-engine

# Investigate deadlock in code
# Review async/await patterns, mutex usage
```

---

## Redis Issues

### Problem 4: Redis Connection Failed

**Symptoms:**
- Health check fails on Redis
- `ConnectionError: Error connecting to Redis`

**Diagnosis:**
```bash
# Check Redis container
docker-compose ps redis

# Test connection
redis-cli -h localhost -p 6380 ping

# Check Redis logs
docker-compose logs redis
```

**Common Causes & Solutions:**

#### Cause 4.1: Redis Container Not Running

**Solution:**
```bash
# Start Redis
docker-compose up -d redis

# Wait for healthy status
watch -n 1 'docker-compose ps redis'
```

#### Cause 4.2: Wrong Redis Host/Port

**Solution:**
```bash
# Check configuration
grep REDIS_HOST /etc/arbitrage/arbitrage.env

# Correct values:
# Docker: REDIS_HOST=redis, REDIS_PORT=6379
# Host: REDIS_HOST=localhost, REDIS_PORT=6380

# Update and restart
nano /etc/arbitrage/arbitrage.env
docker-compose restart arbitrage-engine
```

### Problem 5: Redis High Latency

**Symptoms:**
- Health check reports latency > 30ms
- Slow operations

**Diagnosis:**
```bash
# Check Redis stats
redis-cli -p 6380 INFO stats | grep -E "(instantaneous|latency)"

# Check slow log
redis-cli -p 6380 SLOWLOG GET 10

# Monitor operations
redis-cli -p 6380 MONITOR
```

**Solutions:**

#### Solution 5.1: High Memory Usage

```bash
# Check memory
redis-cli -p 6380 INFO memory | grep used_memory_human

# If > 400MB (maxmemory=512MB):
# Increase maxmemory in docker-compose.yml
# or
# Flush old keys (check TTL policy)
```

#### Solution 5.2: Network Latency

```bash
# Ping test
docker exec arbitrage-redis ping -c 5 arbitrage-engine

# If high latency:
# Check Docker network
docker network inspect arbitrage_arbitrage-network
```

### Problem 6: Redis Out of Memory

**Symptoms:**
- `OOM command not allowed when used memory > 'maxmemory'`

**Diagnosis:**
```bash
# Check memory usage
redis-cli -p 6380 INFO memory

# Check eviction stats
redis-cli -p 6380 INFO stats | grep evicted_keys
```

**Solution:**
```bash
# Temporary: Flush non-critical keys
redis-cli -p 6380 --scan --pattern "arbitrage:*:METRICS:*" | xargs redis-cli DEL

# Permanent: Increase maxmemory
# Edit docker-compose.yml:
command: >
  redis-server
  --maxmemory 1gb
  
# Restart Redis
docker-compose restart redis
```

---

## PostgreSQL Issues

### Problem 7: PostgreSQL Connection Failed

**Symptoms:**
- Health check fails on PostgreSQL
- `psycopg2.OperationalError: could not connect`

**Diagnosis:**
```bash
# Check PostgreSQL container
docker-compose ps postgres

# Test connection
psql -h localhost -U arbitrage -d arbitrage -c "SELECT 1"

# Check PostgreSQL logs
docker-compose logs postgres
```

**Common Causes & Solutions:**

#### Cause 7.1: PostgreSQL Not Ready

**Solution:**
```bash
# Wait for healthy status
docker-compose ps postgres
# Should show "Up (healthy)"

# If stuck in starting:
docker-compose restart postgres
```

#### Cause 7.2: Wrong Credentials

**Solution:**
```bash
# Check credentials
grep POSTGRES /etc/arbitrage/arbitrage.env

# Test manually
PGPASSWORD=arbitrage psql -h localhost -U arbitrage -d arbitrage

# If fails, reset password in docker-compose.yml
```

### Problem 8: PostgreSQL Slow Queries

**Symptoms:**
- Health check timeout on PostgreSQL
- Slow snapshot save/restore

**Diagnosis:**
```bash
# Check query performance
psql -h localhost -U arbitrage -d arbitrage -c "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Check active queries
psql -h localhost -U arbitrage -d arbitrage -c "SELECT pid, state, query FROM pg_stat_activity WHERE state='active';"

# Check table sizes
psql -h localhost -U arbitrage -d arbitrage -c "SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname='public';"
```

**Solutions:**

#### Solution 8.1: Missing Indexes

```bash
# Verify indexes exist
psql -h localhost -U arbitrage -d arbitrage -c "SELECT tablename, indexname FROM pg_indexes WHERE schemaname='public';"

# If missing, apply migration
python scripts/apply_d72_migration.py
```

#### Solution 8.2: Table Bloat

```bash
# Vacuum tables
psql -h localhost -U arbitrage -d arbitrage -c "VACUUM ANALYZE;"

# Or use helper function
psql -h localhost -U arbitrage -d arbitrage -c "SELECT vacuum_snapshot_tables();"
```

### Problem 9: PostgreSQL Disk Full

**Symptoms:**
- `ERROR: could not extend file: No space left on device`

**Diagnosis:**
```bash
# Check disk usage
df -h /var/lib/docker

# Check PostgreSQL data size
docker exec arbitrage-postgres du -sh /var/lib/postgresql/data
```

**Solution:**
```bash
# Clean old snapshots
psql -h localhost -U arbitrage -d arbitrage -c "SELECT cleanup_old_snapshots_30d();"

# Vacuum full (reclaims space)
psql -h localhost -U arbitrage -d arbitrage -c "VACUUM FULL;"

# Or increase disk size
```

---

## WebSocket Issues

### Problem 10: WebSocket Disconnected

**Symptoms:**
- Logs show `WebSocket disconnected`
- No market data updates
- Trading activity stops

**Diagnosis:**
```bash
# Check WS logs
docker-compose logs arbitrage-engine | grep -i websocket

# Check network connectivity
docker exec arbitrage-engine ping -c 3 stream.binance.com
docker exec arbitrage-engine ping -c 3 api.upbit.com
```

**Solution:**
```bash
# WebSocket will auto-reconnect (exponential backoff)
# Monitor reconnection:
docker-compose logs -f arbitrage-engine | grep "WebSocket"

# Expected: "WebSocket reconnected" within 60 seconds

# If not reconnecting:
# 1. Check firewall rules
# 2. Check exchange API status
# 3. Restart engine
docker-compose restart arbitrage-engine
```

### Problem 11: WebSocket High Latency

**Symptoms:**
- `avg_ws_latency_ms` > 200ms
- Delayed trade execution

**Diagnosis:**
```bash
# Check metrics
python tools/monitor.py --metrics | grep ws_latency

# Check network latency
ping -c 10 stream.binance.com
ping -c 10 api.upbit.com
```

**Solution:**
```bash
# If network latency is high:
# - Consider using VPS closer to exchange servers
# - Check ISP issues

# If exchange is slow:
# - Normal during high volatility
# - Monitor exchange status page
```

### Problem 12: WebSocket Rate Limited

**Symptoms:**
- Error: `429 Too Many Requests`
- WebSocket disconnects frequently

**Diagnosis:**
```bash
# Check request rate
docker-compose logs arbitrage-engine | grep "429"

# Check subscription count
docker-compose logs arbitrage-engine | grep "subscribe"
```

**Solution:**
```bash
# Reduce subscription frequency
# Edit config/environments/production.py:
# ws_ping_interval = 30  # Increase from 20

# Restart
docker-compose restart arbitrage-engine
```

---

## Engine Issues

### Problem 13: Engine Loop Hangs

**Symptoms:**
- `avg_loop_latency_ms` = 0 (no updates)
- Health check fails on metrics

**Diagnosis:**
```bash
# Check if process is running
docker exec arbitrage-engine ps aux | grep python

# Check for deadlock
docker exec arbitrage-engine python -c "
import psutil
p = psutil.Process()
print(f'Threads: {p.num_threads()}')
print(f'CPU: {p.cpu_percent()}')
"
```

**Solution:**
```bash
# Restart engine
docker-compose restart arbitrage-engine

# If persists:
# - Check code for blocking operations
# - Review async/await usage
# - Add timeout to long operations
```

### Problem 14: No Opportunities Detected

**Symptoms:**
- `trades_per_minute` = 0
- Logs show "No profitable opportunities"

**Diagnosis:**
```bash
# Check spread detection
docker-compose logs arbitrage-engine | grep -i "spread"

# Check configuration
python -c "from config.loader import load_config; c=load_config('production'); print(c.trading.min_profit_threshold)"
```

**Common Causes:**

1. **Threshold too high:** Reduce `min_profit_threshold`
2. **Market conditions:** Normal during low volatility
3. **Fees misconfigured:** Check fee configuration

**Solution:**
```bash
# Adjust threshold (if too high)
# Edit config/environments/production.py
nano config/environments/production.py

# Restart
docker-compose restart arbitrage-engine
```

### Problem 15: RiskGuard Blocking Trades

**Symptoms:**
- `guard_triggers_per_minute` > 10
- Logs show `RiskGuard blocked trade`

**Diagnosis:**
```bash
# Check guard status
docker-compose logs arbitrage-engine | grep "RiskGuard"

# Check limits
python -c "from config.loader import load_config; c=load_config('production'); print(c.risk_limits)"
```

**Solution:**
```bash
# If guards are too strict:
# Edit config/environments/production.py
# Adjust: max_position_size, max_daily_loss, etc.

# If legitimate risk:
# Guards are working correctly, do not override
```

---

## Performance Issues

### Problem 16: High Loop Latency

**Symptoms:**
- `avg_loop_latency_ms` > 50ms
- Slow trade execution

**Diagnosis:**
```bash
# Profile loop
python -m cProfile -o profile.stats -m arbitrage.live_runner

# Analyze
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
"

# Check CPU
docker stats arbitrage-engine --no-stream
```

**Solutions:**

#### Solution 16.1: High CPU Usage

```bash
# Check competing processes
docker exec arbitrage-engine top -b -n 1

# Reduce load:
# - Optimize hot code paths
# - Use caching
# - Reduce logging verbosity
```

#### Solution 16.2: Blocking I/O

```bash
# Identify blocking operations
# Review code for:
# - Synchronous Redis/PostgreSQL calls (should be async)
# - Long-running computations in main loop
# - Missing timeouts
```

### Problem 17: High Memory Usage

**Symptoms:**
- Memory > 1.5GB (limit: 2GB)
- Container OOMKilled

**Diagnosis:**
```bash
# Check memory usage
docker stats arbitrage-engine --no-stream

# Profile memory
python -m memory_profiler -m arbitrage.live_runner

# Check for leaks
docker exec arbitrage-engine python -c "
import psutil
p = psutil.Process()
print(f'RSS: {p.memory_info().rss / 1024 / 1024:.2f} MB')
"
```

**Solutions:**

#### Solution 17.1: Memory Leak

```bash
# Use objgraph to find leaks
docker exec arbitrage-engine python -c "
import objgraph
objgraph.show_most_common_types(limit=20)
"

# Fix leak in code (requires investigation)
```

#### Solution 17.2: Large Data Structures

```bash
# Reduce data retention:
# - Limit in-memory metrics window (currently 60s)
# - Clear old WebSocket messages
# - Use generators instead of lists
```

---

## Resource Issues

### Problem 18: Disk Space Full

**Symptoms:**
- `df -h` shows 100% usage
- `No space left on device` errors

**Diagnosis:**
```bash
# Find largest directories
du -sh /opt/arbitrage/* | sort -rh | head -n 10
du -sh /var/lib/docker/volumes/* | sort -rh | head -n 10

# Find largest files
find /opt/arbitrage -type f -size +100M -exec ls -lh {} \;
```

**Solutions:**

#### Solution 18.1: Large Log Files

```bash
# Clean old logs
find /opt/arbitrage/logs -name "*.log*" -mtime +7 -delete

# Compress logs
gzip /opt/arbitrage/logs/*.log

# Rotate logs more frequently
```

#### Solution 18.2: Docker Volumes

```bash
# Clean unused volumes
docker volume prune -f

# Clean old PostgreSQL data (use retention policy)
psql -h localhost -U arbitrage -d arbitrage -c "SELECT cleanup_old_snapshots_30d();"
```

### Problem 19: CPU Exhaustion

**Symptoms:**
- CPU > 90% sustained
- System unresponsive

**Diagnosis:**
```bash
# Check CPU usage
top -b -n 1 | head -n 20

# Check engine CPU
docker stats arbitrage-engine --no-stream

# Profile CPU
python -m cProfile -o cpu_profile.stats -m arbitrage.live_runner
```

**Solutions:**

```bash
# Temporary: Reduce load
# - Decrease trading frequency
# - Disable non-critical features

# Permanent: Optimize code or scale vertically
```

### Problem 20: Network Bandwidth Exhausted

**Symptoms:**
- WebSocket disconnects
- API timeouts

**Diagnosis:**
```bash
# Check network usage
iftop -i eth0

# Check Docker network
docker network inspect arbitrage_arbitrage-network
```

**Solution:**
```bash
# Reduce WebSocket subscriptions
# Optimize API call frequency
# Consider network upgrade
```

---

## State Management Issues

### Problem 21: Snapshot Save Failed

**Symptoms:**
- Logs show `Failed to save snapshot`
- State not persisting

**Diagnosis:**
```bash
# Check PostgreSQL connection
psql -h localhost -U arbitrage -d arbitrage -c "SELECT 1"

# Check recent snapshots
psql -h localhost -U arbitrage -d arbitrage -c "SELECT * FROM session_snapshots ORDER BY created_at DESC LIMIT 5;"

# Check error logs
docker-compose logs arbitrage-engine | grep -i "snapshot"
```

**Solution:**
```bash
# If PostgreSQL connection failed:
# - Check database health
# - Verify credentials

# If disk full:
# - Clean old snapshots
# - Increase disk space

# Restart engine to retry
docker-compose restart arbitrage-engine
```

### Problem 22: Snapshot Restore Failed

**Symptoms:**
- Engine starts but doesn't restore previous state
- Logs show `Snapshot restore failed`

**Diagnosis:**
```bash
# Check if snapshot exists
psql -h localhost -U arbitrage -d arbitrage -c "SELECT * FROM session_snapshots WHERE status='running' ORDER BY created_at DESC LIMIT 1;"

# Check restore logs
docker-compose logs arbitrage-engine | grep -i "restore"
```

**Solution:**
```bash
# If no snapshot found:
# - Normal for first start
# - Engine will start clean

# If snapshot corrupted:
# - Restore from backup
# - Or start clean (data loss)
```

### Problem 23: Redis Keyspace Mismatch

**Symptoms:**
- Warnings about unknown keys
- State inconsistency

**Diagnosis:**
```bash
# Check keyspace compliance
python -c "
from arbitrage.redis_keyspace import KeyspaceValidator
v = KeyspaceValidator()
v.audit_keyspace('production')
"

# List all keys
redis-cli -p 6380 --scan --pattern "arbitrage:*"
```

**Solution:**
```bash
# Run migration
python scripts/migrate_d72_redis_keys.py --env production

# Or flush Redis (data loss)
redis-cli -p 6380 FLUSHALL
```

---

## Trading Issues

### Problem 24: Trades Not Executing

**Symptoms:**
- Opportunities detected but no orders placed
- Logs show opportunities but no execution

**Diagnosis:**
```bash
# Check execution logs
docker-compose logs arbitrage-engine | grep -i "execution"

# Check API keys (live mode)
grep -E "(BINANCE|UPBIT)" /etc/arbitrage/arbitrage.env
```

**Common Causes:**

1. **Paper mode enabled:** Expected behavior
2. **API keys missing:** Required for live trading
3. **Exchange API error:** Check exchange status
4. **RiskGuard blocking:** Check guard logs

### Problem 25: Incorrect PnL Calculation

**Symptoms:**
- PnL doesn't match expected
- Negative PnL on profitable trades

**Diagnosis:**
```bash
# Check fee configuration
python -c "from config.loader import load_config; c=load_config('production'); print(c.trading.binance_fee, c.trading.upbit_fee)"

# Check trade logs
docker-compose logs arbitrage-engine | grep "PnL"
```

**Solution:**
```bash
# Verify fee configuration
# Binance: 0.001 (0.1%)
# Upbit: 0.0005 (0.05%)

# Update if incorrect
nano config/environments/production.py
```

---

## Logging Issues

### Problem 26: No Logs Produced

**Symptoms:**
- Log file empty or not updating
- Health check fails on logs

**Diagnosis:**
```bash
# Check log file
ls -l /opt/arbitrage/logs/arbitrage_production.log

# Check file permissions
docker exec arbitrage-engine ls -l /app/logs/

# Check logging configuration
grep LOG_LEVEL /etc/arbitrage/arbitrage.env
```

**Solution:**
```bash
# Fix permissions
docker exec arbitrage-engine chown -R arbitrage:arbitrage /app/logs

# Lower log level (if too high)
# Edit /etc/arbitrage/arbitrage.env:
LOG_LEVEL=INFO

# Restart
docker-compose restart arbitrage-engine
```

### Problem 27: Log Flooding

**Symptoms:**
- Log file growing too fast (>1GB/day)
- Disk filling up

**Diagnosis:**
```bash
# Check log size
du -sh /opt/arbitrage/logs/arbitrage_production.log

# Find frequent log patterns
cat /opt/arbitrage/logs/arbitrage_production.log | awk '{print $5}' | sort | uniq -c | sort -rn | head -n 20
```

**Solution:**
```bash
# Raise log level
# Edit /etc/arbitrage/arbitrage.env:
LOG_LEVEL=WARNING

# Fix spammy code (requires code change)

# Implement log rotation
# See RUNBOOK.md: Weekly Maintenance
```

---

## Configuration Issues

### Problem 28: Configuration Validation Failed

**Symptoms:**
- Engine won't start
- Error: `ConfigValidationError`

**Diagnosis:**
```bash
# Validate configuration
python -c "
from config.loader import load_config
try:
    c = load_config('production')
    print('Config valid')
except Exception as e:
    print(f'Config error: {e}')
"
```

**Common Causes:**

1. **Invalid spread threshold:** `min_profit_threshold` < fees
2. **Invalid risk limits:** Negative or zero values
3. **Syntax error:** Python syntax error in config file

**Solution:**
```bash
# Fix configuration
nano config/environments/production.py

# Example fix:
# min_profit_threshold should be > (binance_fee + upbit_fee)
# If fees = 0.0015 total, threshold should be > 0.0015 (e.g., 0.002)
```

### Problem 29: Environment Variable Not Loaded

**Symptoms:**
- Configuration uses default instead of env var
- Secrets not found

**Diagnosis:**
```bash
# Check if env file is sourced
systemctl show arbitrage | grep EnvironmentFile

# Check env vars in container
docker exec arbitrage-engine env | grep -E "(REDIS|POSTGRES)"
```

**Solution:**
```bash
# Ensure EnvironmentFile is set in systemd service
sudo nano /etc/systemd/system/arbitrage.service
# EnvironmentFile=/etc/arbitrage/arbitrage.env

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart arbitrage
```

---

## Network Issues

### Problem 30: API Rate Limit Exceeded

**Symptoms:**
- Error: `429 Too Many Requests`
- API calls failing

**Diagnosis:**
```bash
# Check error frequency
docker-compose logs arbitrage-engine | grep "429" | wc -l

# Check API call rate
docker-compose logs arbitrage-engine | grep -i "api"
```

**Solution:**
```bash
# Reduce API call frequency
# Implement backoff strategy (already implemented in WS reconnect)

# Wait for rate limit reset (usually 1 minute)

# If persists, contact exchange support
```

---

## Error Code Reference

### Engine Error Codes

| Code | Error | Cause | Solution |
|------|-------|-------|----------|
| E001 | ConfigValidationError | Invalid config | Fix configuration |
| E002 | RedisConnectionError | Redis not accessible | Check Redis container |
| E003 | PostgreSQLConnectionError | PostgreSQL not accessible | Check PostgreSQL container |
| E004 | WebSocketDisconnected | WS connection lost | Auto-reconnects, wait |
| E005 | SnapshotSaveFailed | Snapshot save error | Check PostgreSQL, disk space |
| E006 | SnapshotRestoreFailed | Snapshot restore error | Check snapshot exists |
| E007 | RiskGuardBlocked | Trade blocked by guard | Review risk limits |
| E008 | InsufficientBalance | Not enough balance | Add funds or reduce position size |
| E009 | OrderExecutionFailed | Order failed | Check API keys, exchange status |
| E010 | HighLatency | Loop latency > threshold | Check performance, resources |

### HTTP Error Codes

| Code | Meaning | Common Cause | Solution |
|------|---------|--------------|----------|
| 400 | Bad Request | Invalid API parameters | Check API call |
| 401 | Unauthorized | Invalid API keys | Verify API keys |
| 403 | Forbidden | API keys lack permissions | Check permissions |
| 429 | Too Many Requests | Rate limit exceeded | Reduce frequency, wait |
| 500 | Internal Server Error | Exchange issue | Retry, check exchange status |
| 503 | Service Unavailable | Exchange maintenance | Wait, check status page |

### PostgreSQL Error Codes

| Code | Error | Cause | Solution |
|------|-------|-------|----------|
| 08006 | connection_failure | PostgreSQL unreachable | Check container, network |
| 42P01 | undefined_table | Table doesn't exist | Run migrations |
| 23505 | unique_violation | Duplicate key | Check logic, constraints |
| 53100 | disk_full | No space left | Clean data, increase disk |

---

**End of TROUBLESHOOTING.md**

For deployment procedures, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).  
For operational procedures, see [RUNBOOK.md](RUNBOOK.md).  
For API reference, see [API_REFERENCE.md](API_REFERENCE.md).
