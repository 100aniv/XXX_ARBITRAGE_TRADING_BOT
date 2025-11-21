# Arbitrage Engine - Operations Runbook

**Status:** PRODUCTION READY  
**Author:** Arbitrage Engine Team  
**Date:** 2025-11-21  
**Version:** 1.0

---

## Table of Contents

1. [Overview](#overview)
2. [Daily Operations](#daily-operations)
3. [Service Management](#service-management)
4. [Health Monitoring](#health-monitoring)
5. [Incident Response](#incident-response)
6. [Maintenance Procedures](#maintenance-procedures)
7. [Emergency Procedures](#emergency-procedures)
8. [On-Call Procedures](#on-call-procedures)
9. [Escalation Matrix](#escalation-matrix)
10. [Common Scenarios](#common-scenarios)

---

## Overview

이 Runbook은 Arbitrage Engine의 일상 운영 절차를 단계별로 정리한 문서입니다.

### Purpose

- **운영자 가이드:** 24/7 운영을 위한 표준 절차
- **신규 온보딩:** 새로운 운영자 교육 자료
- **인시던트 대응:** 비정상 상태 발생 시 대응 절차
- **일관성 유지:** 모든 운영자가 동일한 방식으로 작업

### Roles

| Role | Responsibilities |
|------|------------------|
| **Operator** | 일상 모니터링, 서비스 재시작, 로그 확인 |
| **On-Call Engineer** | 인시던트 대응, 긴급 수정, 에스컬레이션 |
| **SRE** | 시스템 안정성, 성능 최적화, 자동화 |
| **Developer** | 버그 수정, 기능 개발, 코드 리뷰 |

---

## Daily Operations

### Morning Checklist (매일 09:00)

#### 1. Service Health Check

```bash
# Check service status
sudo systemctl status arbitrage

# Expected: active (running)
```

**Action if FAILED:**
- If stopped → See [Service Start Procedure](#service-start)
- If failed → See [Service Recovery](#service-recovery)

#### 2. Docker Container Status

```bash
# Check all containers
cd /opt/arbitrage/docker
docker-compose ps

# Expected output:
# arbitrage-redis      Up (healthy)
# arbitrage-postgres   Up (healthy)
# arbitrage-engine     Up (healthy)
```

**Action if UNHEALTHY:**
- See [Container Health Issues](#container-health-issues)

#### 3. Health Check Verification

```bash
# Run health check
docker exec arbitrage-engine python healthcheck.py

# Expected: All checks PASS
```

**Action if FAILED:**
- Redis failed → Check Redis logs
- PostgreSQL failed → Check PostgreSQL logs
- Logs not updated → Engine not running
- High latency → Check system resources

#### 4. Recent Logs Review

```bash
# Check for errors in last hour
docker-compose logs --since 1h arbitrage-engine | grep -i error

# Check critical errors
docker-compose logs --since 1h arbitrage-engine | grep -i critical
```

**Action if ERRORS:**
- Error count < 5 → Monitor
- Error count 5-20 → Investigate
- Error count > 20 → See [High Error Rate](#high-error-rate)

#### 5. Trading Activity Check

```bash
# Check recent metrics
python tools/monitor.py --metrics

# Verify:
# - trades_per_minute > 0 (if in trading hours)
# - errors_per_minute < 10
# - avg_loop_latency_ms < 50
# - guard_triggers_per_minute < 5
```

**Action if ABNORMAL:**
- No trades → See [No Trading Activity](#no-trading-activity)
- High errors → See [High Error Rate](#high-error-rate)
- High latency → See [High Latency](#high-latency)

#### 6. Database Status

```bash
# PostgreSQL connection
psql -h localhost -U arbitrage -d arbitrage -c "SELECT COUNT(*) FROM session_snapshots;"

# Redis connection
redis-cli -p 6380 ping
# Expected: PONG
```

**Action if FAILED:**
- See [Database Connection Issues](#database-connection-issues)

#### 7. Disk Space Check

```bash
# Check disk usage
df -h /opt/arbitrage
df -h /var/lib/docker

# Expected: Usage < 80%
```

**Action if FULL:**
- See [Disk Space Management](#disk-space-management)

#### 8. System Resources

```bash
# CPU and Memory
docker stats arbitrage-engine --no-stream

# Expected:
# CPU < 70%
# Memory < 1.5GB (out of 2GB limit)
```

**Action if HIGH:**
- See [High Resource Usage](#high-resource-usage)

### Daily Report (매일 18:00)

#### Generate Daily Report

```bash
# Create report
cat > /tmp/daily_report_$(date +%Y%m%d).txt << EOF
=== Arbitrage Engine Daily Report ===
Date: $(date)

Service Status:
$(sudo systemctl status arbitrage | head -n 5)

Uptime:
$(uptime)

Trading Metrics (Last 24h):
$(python tools/monitor.py --metrics --duration 24h)

Error Summary:
$(docker-compose logs --since 24h arbitrage-engine | grep -i error | wc -l) errors

Top Errors:
$(docker-compose logs --since 24h arbitrage-engine | grep -i error | head -n 10)

Disk Usage:
$(df -h /opt/arbitrage | tail -n 1)

Resource Usage:
$(docker stats arbitrage-engine --no-stream)

=== End of Report ===
EOF

# Send report (email or Slack)
cat /tmp/daily_report_$(date +%Y%m%d).txt
```

---

## Service Management

### Service Start

#### Method 1: Docker Compose

```bash
# Navigate to docker directory
cd /opt/arbitrage/docker

# Start all services
docker-compose up -d

# Verify
docker-compose ps
docker exec arbitrage-engine python healthcheck.py
```

**Expected duration:** 30-60 seconds

**Validation:**
- [ ] All containers show "Up (healthy)"
- [ ] Health check passes
- [ ] Recent logs present

#### Method 2: systemd

```bash
# Start service
sudo systemctl start arbitrage

# Wait for startup (30s)
sleep 30

# Verify
sudo systemctl status arbitrage
python healthcheck.py
```

**Expected duration:** 30-60 seconds

**Validation:**
- [ ] Service shows "active (running)"
- [ ] Health check passes
- [ ] journalctl shows startup logs

### Service Stop

#### Graceful Stop (RECOMMENDED)

```bash
# Docker Compose
cd /opt/arbitrage/docker
docker-compose stop arbitrage-engine

# Wait for graceful shutdown (max 60s)
# Engine will save snapshot to PostgreSQL

# systemd
sudo systemctl stop arbitrage
```

**Expected duration:** 10-60 seconds

**Validation:**
- [ ] No error logs during shutdown
- [ ] Snapshot saved (check PostgreSQL)
- [ ] No orphaned processes

#### Force Stop (EMERGENCY ONLY)

```bash
# Docker Compose
docker-compose kill arbitrage-engine

# systemd
sudo systemctl kill arbitrage
```

**⚠️ WARNING:** May lose unsaved state

**Use only when:**
- Graceful stop hangs (> 60s)
- Critical security issue
- System resource exhaustion

### Service Restart

#### Standard Restart

```bash
# Docker Compose
docker-compose restart arbitrage-engine

# systemd
sudo systemctl restart arbitrage
```

**Expected duration:** 40-90 seconds

**Validation:**
- [ ] Service restarted successfully
- [ ] Health check passes
- [ ] Snapshot restored (check logs for "SNAPSHOT RESTORED")

#### Rolling Restart (Zero-Downtime)

```bash
# Pull latest code
cd /opt/arbitrage
git pull origin production

# Rebuild and restart
cd docker
docker-compose up -d --no-deps --build arbitrage-engine

# Verify
docker-compose ps
docker exec arbitrage-engine python healthcheck.py
```

**Expected duration:** 60-120 seconds

**Validation:**
- [ ] New container healthy
- [ ] Old container stopped gracefully
- [ ] State restored
- [ ] Trading resumed

---

## Health Monitoring

### Real-Time Monitoring

#### Metrics Dashboard

```bash
# Launch metrics dashboard (auto-refresh)
python tools/monitor.py --metrics

# Dashboard shows:
# - trades_per_minute
# - errors_per_minute
# - avg_ws_latency_ms
# - avg_loop_latency_ms
# - guard_triggers_per_minute
# - pnl_change_1min
```

**Run continuously during critical periods:**
- After deployment
- During high volatility
- After configuration change
- During incident

#### Log Monitoring

```bash
# Tail logs with filtering
python tools/monitor.py --tail

# Errors only
python tools/monitor.py --errors

# Search specific pattern
python tools/monitor.py --search "WebSocket"
```

#### Container Monitoring

```bash
# Real-time stats
docker stats arbitrage-engine

# Specific metrics
docker stats arbitrage-engine --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}"
```

### Health Check Automation

#### Cron Job Setup

```bash
# Add to crontab
crontab -e

# Health check every 5 minutes
*/5 * * * * /opt/arbitrage/scripts/health_check_cron.sh
```

**health_check_cron.sh:**
```bash
#!/bin/bash
cd /opt/arbitrage
python healthcheck.py > /tmp/healthcheck.log 2>&1

if [ $? -ne 0 ]; then
  # Health check failed
  echo "ALERT: Health check failed at $(date)" | mail -s "Arbitrage Health Check FAILED" ops@example.com
fi
```

#### Alert Rules (Future: Prometheus Alertmanager)

- Health check failed > 3 consecutive times → Page on-call
- CPU > 80% for 5 minutes → Warning
- Memory > 90% for 2 minutes → Critical
- No trades for 30 minutes (during trading hours) → Warning
- Error rate > 50/min for 5 minutes → Critical

---

## Incident Response

### Incident Severity Levels

| Severity | Description | Response Time | Examples |
|----------|-------------|---------------|----------|
| **P0 - Critical** | Service down, data loss | 15 minutes | Service crashed, database corruption |
| **P1 - High** | Degraded service | 1 hour | High error rate, slow performance |
| **P2 - Medium** | Minor issues | 4 hours | Single component failure, low error rate |
| **P3 - Low** | Cosmetic issues | 1 business day | Logging issues, UI glitches |

### Incident Response Flow

```
Incident Detected
       ↓
   Assess Severity (P0/P1/P2/P3)
       ↓
   Page On-Call (if P0/P1)
       ↓
   Gather Information
   - Logs
   - Metrics
   - Timeline
       ↓
   Immediate Mitigation
   - Restart service
   - Rollback
   - Disable feature
       ↓
   Root Cause Analysis
       ↓
   Permanent Fix
       ↓
   Post-Mortem (if P0/P1)
```

### P0 - Critical Incident

#### Example: Service Crashed

**Symptoms:**
- `sudo systemctl status arbitrage` shows "failed"
- No recent logs
- Health check fails completely

**Immediate Actions:**

1. **Alert team:**
   ```bash
   # Send alert (Slack/PagerDuty/email)
   echo "P0: Arbitrage service crashed at $(date)" | mail -s "P0 ALERT" team@example.com
   ```

2. **Gather crash logs:**
   ```bash
   # systemd logs
   sudo journalctl -u arbitrage --since "10 minutes ago" > /tmp/crash_logs.txt
   
   # Docker logs
   docker-compose logs --tail=500 arbitrage-engine > /tmp/crash_docker_logs.txt
   ```

3. **Check recent changes:**
   ```bash
   # Git history
   git log --oneline -10
   
   # Recent deployments
   ls -lt /opt/arbitrage/ | head -n 10
   ```

4. **Attempt restart:**
   ```bash
   sudo systemctl restart arbitrage
   # or
   docker-compose restart arbitrage-engine
   ```

5. **If restart fails:**
   ```bash
   # Rollback to last known good version
   git checkout <previous-commit>
   docker-compose up -d --build arbitrage-engine
   ```

6. **Verify recovery:**
   ```bash
   python healthcheck.py
   python tools/monitor.py --metrics
   ```

7. **Document incident:**
   - Time of occurrence
   - Root cause
   - Resolution
   - Preventive measures

### P1 - High Severity

#### Example: High Error Rate

**Symptoms:**
- Error count > 50/minute
- Normal trading disrupted
- Health check passing but degraded

**Immediate Actions:**

1. **Check error patterns:**
   ```bash
   # Most common errors
   docker-compose logs --since 10m arbitrage-engine | grep ERROR | sort | uniq -c | sort -rn | head -n 10
   ```

2. **Identify error source:**
   - WebSocket errors → Exchange connectivity
   - Database errors → PostgreSQL/Redis issue
   - Trading errors → Logic bug

3. **Temporary mitigation:**
   ```bash
   # If WebSocket errors → Will auto-reconnect
   # If database errors → Check database health
   # If trading logic errors → May need to disable trading temporarily
   ```

4. **Monitor impact:**
   ```bash
   python tools/monitor.py --metrics
   # Check if trades are still executing
   ```

5. **Escalate if not resolved in 30 minutes**

---

## Maintenance Procedures

### Weekly Maintenance (Every Monday 02:00 AM)

#### 1. Log Rotation

```bash
# Rotate application logs
cd /opt/arbitrage/logs
gzip arbitrage_production.log
mv arbitrage_production.log.gz arbitrage_production_$(date +%Y%m%d).log.gz

# Remove logs older than 30 days
find /opt/arbitrage/logs -name "*.log.gz" -mtime +30 -delete
```

#### 2. Database Cleanup

```bash
# Clean old snapshots (stopped/crashed sessions > 30 days)
psql -h localhost -U arbitrage -d arbitrage -c "SELECT cleanup_old_snapshots_30d();"

# Vacuum tables
psql -h localhost -U arbitrage -d arbitrage -c "SELECT vacuum_snapshot_tables();"
```

#### 3. Redis Cleanup

```bash
# Check memory usage
redis-cli -p 6380 INFO memory | grep used_memory_human

# If needed, flush old keys (non-active sessions)
# Automated via TTL policy
```

#### 4. Docker Cleanup

```bash
# Remove unused images
docker image prune -f

# Remove unused volumes
docker volume prune -f

# Remove stopped containers
docker container prune -f
```

#### 5. Disk Space Check

```bash
# Check and alert if > 80%
df -h /opt/arbitrage | awk 'NR==2 {if ($5+0 > 80) print "ALERT: Disk usage high: " $5}'
```

### Monthly Maintenance (First Sunday 02:00 AM)

#### 1. Dependency Updates

```bash
# Update Python packages
cd /opt/arbitrage
source venv/bin/activate
pip list --outdated

# Update selectively (test in staging first)
pip install --upgrade package_name
```

#### 2. Security Patches

```bash
# System updates
sudo apt update
sudo apt upgrade -y

# Docker updates
sudo apt install docker-ce docker-ce-cli containerd.io
```

#### 3. Backup Verification

```bash
# Test PostgreSQL backup restore
docker exec arbitrage-postgres pg_dump -U arbitrage arbitrage > /tmp/test_backup.sql
psql -h localhost -U arbitrage -d arbitrage_test < /tmp/test_backup.sql

# Verify restored data
psql -h localhost -U arbitrage -d arbitrage_test -c "SELECT COUNT(*) FROM session_snapshots;"
```

#### 4. Performance Review

```bash
# Generate performance report
python scripts/performance_report.py --period 30d

# Review:
# - Average latency trend
# - Error rate trend
# - Trading volume trend
# - Resource usage trend
```

### Quarterly Maintenance

#### 1. Secret Rotation

```bash
# Rotate API keys
# 1. Generate new keys on exchange
# 2. Update /etc/arbitrage/arbitrage.env
# 3. Restart service
sudo systemctl restart arbitrage
```

#### 2. Disaster Recovery Drill

```bash
# Simulate complete failure
# 1. Stop all services
# 2. Restore from backup
# 3. Verify full recovery
# 4. Document findings
```

#### 3. Capacity Planning

- Review resource usage trends
- Plan for scaling (horizontal/vertical)
- Update hardware if needed

---

## Emergency Procedures

### Emergency Stop (Kill Switch)

#### When to Use

- Security breach detected
- Runaway trading (abnormal losses)
- Exchange API rate limit exceeded
- Critical bug discovered

#### Procedure

```bash
# STOP EVERYTHING IMMEDIATELY
docker-compose down
sudo systemctl stop arbitrage

# Verify stopped
docker ps | grep arbitrage
# Should return nothing

# Check for orphaned processes
ps aux | grep python | grep arbitrage
# Kill if found

# Notify team
echo "EMERGENCY STOP executed at $(date) by $(whoami)" | mail -s "EMERGENCY STOP" team@example.com
```

#### Post-Stop Actions

1. **Document reason** for emergency stop
2. **Preserve state:**
   ```bash
   # Backup current logs
   cp -r /opt/arbitrage/logs /opt/arbitrage/logs_emergency_$(date +%Y%m%d_%H%M%S)
   
   # Export database
   docker exec arbitrage-postgres pg_dump -U arbitrage arbitrage > /tmp/emergency_backup_$(date +%Y%m%d_%H%M%S).sql
   ```

3. **Investigate root cause**
4. **Fix issue**
5. **Test in staging**
6. **Resume service** only after approval

### Data Corruption Recovery

#### Symptoms

- Snapshot restore fails
- Inconsistent state between Redis and PostgreSQL
- Position data mismatch

#### Procedure

```bash
# 1. Stop service
docker-compose stop arbitrage-engine

# 2. Backup current state
docker exec arbitrage-postgres pg_dump -U arbitrage arbitrage > /tmp/corrupted_backup.sql
docker exec arbitrage-redis redis-cli --rdb /tmp/corrupted_redis.rdb

# 3. Restore from last known good backup
# Find latest backup
ls -lt /opt/arbitrage/backups/

# Restore PostgreSQL
psql -h localhost -U arbitrage -d arbitrage < /opt/arbitrage/backups/arbitrage_YYYYMMDD.sql

# Restore Redis (if needed)
docker exec arbitrage-redis redis-cli FLUSHALL
docker cp /opt/arbitrage/backups/dump.rdb arbitrage-redis:/data/dump.rdb
docker-compose restart redis

# 4. Verify restored data
psql -h localhost -U arbitrage -d arbitrage -c "SELECT * FROM session_snapshots ORDER BY created_at DESC LIMIT 5;"

# 5. Start service
docker-compose start arbitrage-engine

# 6. Verify health
python healthcheck.py
```

---

## On-Call Procedures

### On-Call Duties

**Duration:** 1 week rotation

**Responsibilities:**
- Respond to alerts within 15 minutes (P0/P1)
- Perform incident triage
- Execute standard recovery procedures
- Escalate to senior engineer if needed
- Document all incidents

### Alert Channels

1. **PagerDuty:** Critical alerts (P0/P1)
2. **Slack:** Warning alerts (P2)
3. **Email:** Informational (P3)

### Response Checklist

When paged:

1. **Acknowledge alert** within 5 minutes
2. **Assess severity** (P0/P1/P2/P3)
3. **Gather context:**
   ```bash
   # Quick health check
   python healthcheck.py
   
   # Recent errors
   docker-compose logs --tail=100 arbitrage-engine | grep ERROR
   
   # Metrics
   python tools/monitor.py --metrics
   ```

4. **Apply standard fix** (see [Common Scenarios](#common-scenarios))
5. **Escalate** if not resolved in:
   - P0: 30 minutes
   - P1: 2 hours
6. **Update incident ticket** with:
   - Actions taken
   - Current status
   - Next steps

### Escalation

**Level 1:** On-call engineer (first responder)  
**Level 2:** Senior SRE (if L1 cannot resolve)  
**Level 3:** System architect (if L2 cannot resolve)  
**Level 4:** CTO (critical business impact)

---

## Escalation Matrix

| Issue Type | L1 (On-Call) | L2 (Senior SRE) | L3 (Architect) |
|------------|--------------|-----------------|----------------|
| Service restart | ✅ | ✅ | ✅ |
| Configuration change | ✅ | ✅ | ✅ |
| Database migration | ❌ | ✅ | ✅ |
| Code deployment | ❌ | ✅ | ✅ |
| Architecture change | ❌ | ❌ | ✅ |
| Security incident | Notify | ✅ | ✅ |

---

## Common Scenarios

### Scenario 1: Service Won't Start

**Symptoms:**
- `systemctl start arbitrage` fails
- Container exits immediately

**Diagnosis:**
```bash
# Check recent logs
sudo journalctl -u arbitrage --since "5 minutes ago"
docker-compose logs --tail=100 arbitrage-engine
```

**Common Causes:**

1. **Database not ready:**
   ```bash
   # Verify PostgreSQL
   docker-compose ps postgres
   # Should be "Up (healthy)"
   ```
   **Fix:** Wait for database health check, then restart

2. **Config error:**
   ```bash
   # Validate config
   python -c "from config.loader import load_config; load_config('production')"
   ```
   **Fix:** Correct configuration syntax

3. **Port conflict:**
   ```bash
   # Check port usage
   sudo lsof -i :8080
   ```
   **Fix:** Stop conflicting process or change port

### Scenario 2: High Latency

**Symptoms:**
- `avg_loop_latency_ms` > 50ms
- Slow trade execution

**Diagnosis:**
```bash
# Check system resources
docker stats arbitrage-engine --no-stream

# Check database latency
psql -h localhost -U arbitrage -d arbitrage -c "\timing on" -c "SELECT COUNT(*) FROM session_snapshots;"
```

**Common Causes:**

1. **High CPU:**
   **Fix:** Check for CPU-intensive processes, consider scaling

2. **Slow database:**
   **Fix:** Run `VACUUM`, check indexes

3. **Network issues:**
   **Fix:** Check WebSocket latency, network connectivity

### Scenario 3: No Trading Activity

**Symptoms:**
- `trades_per_minute` = 0
- No recent trades in logs

**Diagnosis:**
```bash
# Check if trading hours
date

# Check RiskGuard status
docker-compose logs arbitrage-engine | grep "RiskGuard"

# Check spread detection
docker-compose logs arbitrage-engine | grep "opportunity"
```

**Common Causes:**

1. **Outside trading hours:** Wait
2. **RiskGuard triggered:** Review guard conditions, adjust if needed
3. **No profitable opportunities:** Normal market condition
4. **WebSocket disconnected:** Check WS logs, will auto-reconnect

---

**End of RUNBOOK.md**

For deployment procedures, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).  
For troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).  
For API reference, see [API_REFERENCE.md](API_REFERENCE.md).
