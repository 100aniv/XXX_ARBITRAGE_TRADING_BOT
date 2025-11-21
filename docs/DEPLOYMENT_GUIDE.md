# Arbitrage Engine - Deployment Guide

**Status:** PRODUCTION READY  
**Author:** Arbitrage Engine Team  
**Date:** 2025-11-21  
**Version:** 1.0

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Environment Setup](#environment-setup)
4. [Deployment Methods](#deployment-methods)
5. [Configuration Management](#configuration-management)
6. [Secrets Management](#secrets-management)
7. [Database Setup](#database-setup)
8. [Docker Deployment](#docker-deployment)
9. [systemd Deployment](#systemd-deployment)
10. [Health Check Verification](#health-check-verification)
11. [Zero-Downtime Updates](#zero-downtime-updates)
12. [Rollback Procedures](#rollback-procedures)
13. [Monitoring Setup](#monitoring-setup)
14. [Production Checklist](#production-checklist)

---

## Overview

이 문서는 Arbitrage Trading Engine을 Production 환경에 배포하는 전체 절차를 설명합니다.

### Deployment Targets

- **Local Development:** Docker Compose (개발/테스트)
- **Production Server:** systemd + Docker (운영 서버)
- **Cloud:** Kubernetes (향후 D97-D98)

### Deployment Philosophy

- **Infrastructure as Code:** 모든 설정은 코드로 관리
- **Immutable Infrastructure:** 컨테이너 기반 배포
- **Health-First:** Health check 통과 후 트래픽 전환
- **Graceful Degradation:** 장애 시 자동 복구
- **Zero-Downtime:** 무중단 업데이트

---

## Prerequisites

### System Requirements

#### Hardware
- **CPU:** 2+ cores (권장 4 cores)
- **RAM:** 4GB minimum (권장 8GB)
- **Disk:** 50GB minimum (권장 100GB SSD)
- **Network:** 안정적인 인터넷 연결 (1Gbps+)

#### Software
- **OS:** Linux (Ubuntu 20.04+ / CentOS 8+) or Windows 10/11
- **Docker:** 20.10+
- **Docker Compose:** 2.0+
- **Python:** 3.10+
- **Git:** 2.30+
- **PostgreSQL Client:** psql (for verification)
- **Redis Client:** redis-cli (for verification)

### Network Requirements

#### Ports
- **6379 (Redis):** Internal only (Docker network)
- **6380 (Redis):** Host access (optional)
- **5432 (PostgreSQL):** Internal only (Docker network)
- **8080 (Engine):** Metrics endpoint (future)

#### External Access
- **Binance API:** api.binance.com (HTTPS)
- **Upbit API:** api.upbit.com (HTTPS)
- **WebSocket:** stream.binance.com, api.upbit.com/websocket

### Access Requirements

- **Server SSH Access:** sudo privileges
- **API Keys:** Binance, Upbit (for live trading)
- **Secrets:** Database passwords, API secrets

---

## Environment Setup

### Directory Structure

Production server에 다음 디렉토리 구조를 생성합니다:

```bash
/opt/arbitrage/                    # Application root
├── arbitrage/                     # Source code
├── config/                        # Configuration files
│   ├── environments/
│   │   ├── development.py
│   │   ├── staging.py
│   │   └── production.py
│   └── secrets.yaml              # Secrets (production)
├── docker/                        # Docker files
├── systemd/                       # systemd service files
├── scripts/                       # Helper scripts
├── logs/                          # Log files
├── tmp/                           # Temporary files
└── venv/                          # Python virtual environment (if not using Docker)

/etc/arbitrage/                    # System configuration
└── arbitrage.env                  # Environment variables

/var/log/arbitrage/                # System logs (systemd)
└── service.log

/var/lib/arbitrage/                # Persistent data (if not using Docker volumes)
├── redis/
└── postgres/
```

### User and Permissions

Production 서버에서 전용 사용자 생성:

```bash
# Create arbitrage user
sudo useradd -r -m -d /opt/arbitrage -s /bin/bash arbitrage

# Set ownership
sudo chown -R arbitrage:arbitrage /opt/arbitrage
sudo mkdir -p /etc/arbitrage /var/log/arbitrage /var/lib/arbitrage
sudo chown arbitrage:arbitrage /etc/arbitrage /var/log/arbitrage /var/lib/arbitrage

# Set permissions
sudo chmod 750 /opt/arbitrage
sudo chmod 640 /etc/arbitrage/arbitrage.env
```

---

## Deployment Methods

### Method 1: Docker Compose (Recommended for Development/Staging)

**Pros:**
- Simple one-command deployment
- All services managed together
- Easy rollback
- Suitable for single-server deployment

**Cons:**
- Not for distributed systems
- Limited scalability

**Use Cases:**
- Local development
- Staging environment
- Single-server production (small scale)

### Method 2: systemd + Docker (Recommended for Production)

**Pros:**
- System-level service management
- Auto-restart on boot
- Resource limits
- Integration with system logging

**Cons:**
- More complex setup
- Requires systemd knowledge

**Use Cases:**
- Production servers
- Long-running services
- Critical systems

### Method 3: Kubernetes (Future - D97-D98)

**Pros:**
- Horizontal scaling
- Rolling updates
- Service mesh
- Multi-region deployment

**Cons:**
- Complex infrastructure
- Higher cost

**Use Cases:**
- Large-scale production
- Multi-region deployment
- High availability requirements

---

## Configuration Management

### Configuration Hierarchy

```
Lowest Priority
    ↓
Default Config (config/base.py)
    ↓
Environment Config (config/environments/{env}.py)
    ↓
Environment Variables (REDIS_HOST, etc.)
    ↓
Secrets File (config/secrets.yaml)
    ↓
Highest Priority
```

### Environment Selection

**Environment variable:** `ENV`

- `development` (default)
- `staging`
- `production`

**Example:**
```bash
export ENV=production
```

### Configuration Files

#### 1. Base Configuration (`config/base.py`)

Default values for all environments.

#### 2. Environment Configurations

- `config/environments/development.py`
- `config/environments/staging.py`
- `config/environments/production.py`

**Production Config Example:**
```python
from config.base import TradingConfig, RiskLimits

TRADING_CONFIG = TradingConfig(
    min_profit_threshold=0.002,  # 0.2%
    max_position_size=1000.0,
    paper_mode=False,  # Live trading
    log_level="WARNING",
)

RISK_LIMITS = RiskLimits(
    max_daily_loss=500.0,
    max_open_positions=5,
    max_position_size=1000.0,
    min_profit_threshold=0.002,
)
```

#### 3. Secrets Configuration (`config/secrets.yaml`)

**Template:** `config/secrets.example.yaml`

**Production Secrets:**
```yaml
binance:
  api_key: ${BINANCE_API_KEY}
  secret_key: ${BINANCE_SECRET_KEY}

upbit:
  access_key: ${UPBIT_ACCESS_KEY}
  secret_key: ${UPBIT_SECRET_KEY}

redis:
  host: ${REDIS_HOST:-localhost}
  port: ${REDIS_PORT:-6379}
  password: ${REDIS_PASSWORD:-}

postgres:
  host: ${POSTGRES_HOST:-localhost}
  port: ${POSTGRES_PORT:-5432}
  database: ${POSTGRES_DB:-arbitrage}
  user: ${POSTGRES_USER:-arbitrage}
  password: ${POSTGRES_PASSWORD:-arbitrage}
```

### Configuration Validation

Start 전 자동 검증:

1. **Spread profitability:** min_profit_threshold > (binance_fee + upbit_fee)
2. **Risk constraints:** max_position_size, max_daily_loss 유효성
3. **API keys:** 존재 여부 (live mode에서만)
4. **Database connection:** Redis, PostgreSQL 연결 확인

---

## Secrets Management

### Environment Variables

Production 환경에서 모든 secrets는 환경변수로 주입됩니다.

#### `/etc/arbitrage/arbitrage.env`

```bash
# Environment
ENV=production
MODE=paper  # or live

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=arbitrage
POSTGRES_USER=arbitrage
POSTGRES_PASSWORD=your_secure_password_here

# Binance API (for live trading)
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key

# Upbit API (for live trading)
UPBIT_ACCESS_KEY=your_upbit_access_key
UPBIT_SECRET_KEY=your_upbit_secret_key

# Logging
LOG_LEVEL=INFO
```

### Security Best Practices

1. **File Permissions:**
   ```bash
   sudo chmod 600 /etc/arbitrage/arbitrage.env
   sudo chown arbitrage:arbitrage /etc/arbitrage/arbitrage.env
   ```

2. **Never commit secrets to Git:**
   - Add to `.gitignore`
   - Use templates (`.example` files)

3. **Rotate secrets regularly:**
   - API keys: every 90 days
   - Database passwords: every 180 days

4. **Use secret management tools (future):**
   - HashiCorp Vault
   - AWS Secrets Manager
   - Azure Key Vault

---

## Database Setup

### PostgreSQL

#### 1. Initial Setup (Docker)

PostgreSQL은 docker-compose.yml에서 자동 시작됩니다.

**Initial credentials:**
- Database: `arbitrage`
- User: `arbitrage`
- Password: `arbitrage` (production에서 변경!)

#### 2. Migration

첫 실행 시 자동으로 migration이 적용됩니다:

**Migration files:**
- `db/migrations/d70_state_persistence.sql`
- `db/migrations/d72_postgres_optimize.sql`
- `db/migrations/d72_4_logging_monitoring.sql`

**Manual migration:**
```bash
# Apply all migrations
python scripts/apply_d72_migration.py
python scripts/apply_d72_4_migration.py

# Verify
psql -h localhost -U arbitrage -d arbitrage -c "\dt"
```

#### 3. Verification

```bash
# Check tables
psql -h localhost -U arbitrage -d arbitrage -c "
  SELECT table_name 
  FROM information_schema.tables 
  WHERE table_schema='public';
"

# Expected tables:
# - session_snapshots
# - position_snapshots
# - metrics_snapshots
# - risk_guard_snapshots
# - system_logs
```

### Redis

#### 1. Initial Setup (Docker)

Redis는 docker-compose.yml에서 자동 시작됩니다.

**Configuration:**
- Port: 6380 (host), 6379 (container)
- Persistence: AOF (appendonly yes)
- Max memory: 512MB
- Eviction policy: allkeys-lru

#### 2. Verification

```bash
# Check Redis connection
docker exec arbitrage-redis redis-cli ping
# Expected: PONG

# Check keyspace
docker exec arbitrage-redis redis-cli --scan --pattern "arbitrage:*"
```

---

## Docker Deployment

### Step 1: Prepare Files

```bash
# Clone repository
git clone https://github.com/your-org/arbitrage-lite.git /opt/arbitrage
cd /opt/arbitrage

# Switch to production branch
git checkout production  # or master
```

### Step 2: Configure Environment

```bash
# Copy secrets template
cp config/secrets.example.yaml config/secrets.yaml

# Edit secrets
nano config/secrets.yaml

# Set environment variables
cp docker/arbitrage.env.example /etc/arbitrage/arbitrage.env
nano /etc/arbitrage/arbitrage.env
```

### Step 3: Build Image

```bash
cd /opt/arbitrage

# Build Docker image
docker build -t arbitrage-engine:latest -f docker/Dockerfile .

# Verify image
docker images arbitrage-engine
```

### Step 4: Start Services

```bash
cd /opt/arbitrage/docker

# Start all services
docker-compose up -d

# Verify services
docker-compose ps

# Expected output:
# NAME                  STATUS
# arbitrage-redis       Up (healthy)
# arbitrage-postgres    Up (healthy)
# arbitrage-engine      Up (healthy)
```

### Step 5: Verify Deployment

```bash
# Check logs
docker-compose logs -f arbitrage-engine

# Check health
docker exec arbitrage-engine python healthcheck.py

# Expected output:
# ✓ Redis: Redis OK (latency: 1.23ms)
# ✓ PostgreSQL: PostgreSQL OK
# ✓ Logs: Log file OK (updated 5s ago, size: 12345 bytes)
# ✓ Metrics: Engine metrics OK
# ✓ Health check PASSED
```

---

## systemd Deployment

### Step 1: Install Service File

```bash
# Copy service file
sudo cp /opt/arbitrage/systemd/arbitrage.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload
```

### Step 2: Configure Environment

```bash
# Create environment file
sudo nano /etc/arbitrage/arbitrage.env

# Add all required variables (see Secrets Management section)
```

### Step 3: Start Dependencies

Ensure Redis and PostgreSQL are running:

```bash
# Using Docker Compose
cd /opt/arbitrage/docker
docker-compose up -d redis postgres

# Wait for health checks
docker-compose ps
```

### Step 4: Start Service

```bash
# Enable service (auto-start on boot)
sudo systemctl enable arbitrage

# Start service
sudo systemctl start arbitrage

# Check status
sudo systemctl status arbitrage

# Expected output:
# ● arbitrage.service - Arbitrage Trading Engine
#    Loaded: loaded
#    Active: active (running)
```

### Step 5: Verify Logs

```bash
# Real-time logs
sudo journalctl -u arbitrage -f

# Recent logs
sudo journalctl -u arbitrage --since "10 minutes ago"

# Check for errors
sudo journalctl -u arbitrage -p err
```

---

## Health Check Verification

### Manual Health Check

```bash
# Docker deployment
docker exec arbitrage-engine python healthcheck.py

# systemd deployment
cd /opt/arbitrage
python healthcheck.py
```

### Expected Output

```
✓ Redis: Redis OK (latency: 1.23ms)
✓ PostgreSQL: PostgreSQL OK
✓ Logs: Log file OK (updated 5s ago, size: 12345 bytes)
✓ Metrics: Engine metrics OK

✓ Health check PASSED
```

### Health Check Failures

| Check | Failure Reason | Solution |
|-------|----------------|----------|
| Redis | Connection refused | Check Redis container status |
| Redis | High latency (>30ms) | Check network, Redis load |
| PostgreSQL | Connection refused | Check PostgreSQL container status |
| Logs | File not updated (>5min) | Engine not running, check logs |
| Metrics | Loop latency high (>100ms) | Check CPU/memory usage |

---

## Zero-Downtime Updates

### Strategy: Rolling Update with Health Checks

#### Docker Compose Method

```bash
cd /opt/arbitrage/docker

# Pull latest code
git pull origin production

# Rebuild image
docker-compose build arbitrage-engine

# Rolling update (depends_on health checks)
docker-compose up -d --no-deps --build arbitrage-engine

# Verify new container is healthy
docker-compose ps
docker-compose logs -f arbitrage-engine
```

**Process:**
1. New container starts
2. Health check passes (30s grace period)
3. Old container stops gracefully (SIGTERM)
4. State persists via Docker volumes

#### systemd Method

```bash
# Pull latest code
cd /opt/arbitrage
git pull origin production

# Restart service (graceful)
sudo systemctl restart arbitrage

# Verify
sudo systemctl status arbitrage
sudo journalctl -u arbitrage -f
```

**Process:**
1. SIGTERM sent to engine
2. Engine saves state to PostgreSQL snapshot
3. Engine stops gracefully
4. New process starts
5. State restored from snapshot

### Validation Steps

After update:

1. **Health check passes:**
   ```bash
   docker exec arbitrage-engine python healthcheck.py
   ```

2. **Recent logs present:**
   ```bash
   docker-compose logs --tail=100 arbitrage-engine | grep "Engine started"
   ```

3. **Metrics flowing:**
   ```bash
   python tools/monitor.py --metrics
   ```

4. **No position loss:**
   ```bash
   # Check snapshot restore
   docker-compose logs arbitrage-engine | grep "SNAPSHOT"
   ```

---

## Rollback Procedures

### Scenario 1: Bad Code Deployment

#### Quick Rollback (Git)

```bash
# Find last good commit
git log --oneline -10

# Rollback to last good commit
git checkout <commit-hash>

# Rebuild and restart
docker-compose up -d --build arbitrage-engine

# Or for systemd
sudo systemctl restart arbitrage
```

#### Docker Image Rollback

```bash
# List recent images
docker images arbitrage-engine

# Tag current as backup
docker tag arbitrage-engine:latest arbitrage-engine:backup

# Pull previous image
docker pull arbitrage-engine:previous

# Restart with previous image
docker-compose down
docker-compose up -d
```

### Scenario 2: Bad Configuration

```bash
# Restore config from backup
cp /opt/arbitrage/config/production.py.backup /opt/arbitrage/config/environments/production.py

# Or restore secrets
cp /etc/arbitrage/arbitrage.env.backup /etc/arbitrage/arbitrage.env

# Restart
docker-compose restart arbitrage-engine
```

### Scenario 3: Database Migration Failure

```bash
# Connect to PostgreSQL
docker exec -it arbitrage-postgres psql -U arbitrage

# Rollback migration manually
BEGIN;
-- Undo migration changes
DROP TABLE IF EXISTS new_table;
COMMIT;

# Restore from backup
docker exec arbitrage-postgres pg_restore -U arbitrage /backup/arbitrage_backup.sql
```

### Rollback Validation

1. **Service running:**
   ```bash
   docker-compose ps
   sudo systemctl status arbitrage
   ```

2. **Health check passing:**
   ```bash
   docker exec arbitrage-engine python healthcheck.py
   ```

3. **Logs clean:**
   ```bash
   docker-compose logs --tail=100 arbitrage-engine | grep ERROR
   ```

4. **Trading active:**
   ```bash
   python tools/monitor.py --metrics
   # Check trades/min > 0
   ```

---

## Monitoring Setup

### CLI Monitoring Tool

**Location:** `tools/monitor.py`

```bash
# Real-time metrics dashboard
python tools/monitor.py --metrics

# Tail logs
python tools/monitor.py --tail

# Errors only
python tools/monitor.py --errors

# Search logs
python tools/monitor.py --search "trade execution"
```

### Metrics Collection

Metrics are stored in Redis with 60-second rolling window:

**Key:** `arbitrage:{env}:{session_id}:METRICS`

**Metrics:**
- `trades_per_minute`
- `errors_per_minute`
- `avg_ws_latency_ms`
- `avg_loop_latency_ms`
- `guard_triggers_per_minute`
- `pnl_change_1min`

### Log Aggregation

Logs are written to multiple backends:

1. **File:** `logs/arbitrage_{env}.log`
2. **Console:** stdout (Docker logs)
3. **Redis Stream:** `arbitrage:logs:{env}`
4. **PostgreSQL:** `system_logs` table (WARNING+)

**Query recent logs:**
```bash
# File
tail -f logs/arbitrage_production.log

# Redis
redis-cli XREVRANGE arbitrage:logs:production + - COUNT 100

# PostgreSQL
psql -U arbitrage -c "SELECT * FROM system_logs ORDER BY created_at DESC LIMIT 100;"
```

### Future: Prometheus + Grafana (D73)

**Metrics endpoint:** `http://localhost:8080/metrics`

**Dashboards:**
- Engine performance
- Trading activity
- System resources
- Alert rules

---

## Production Checklist

### Pre-Deployment

- [ ] Server provisioned (CPU, RAM, Disk)
- [ ] Docker and Docker Compose installed
- [ ] Git repository cloned
- [ ] User `arbitrage` created
- [ ] Directories created (`/opt/arbitrage`, `/etc/arbitrage`, `/var/log/arbitrage`)
- [ ] Permissions set correctly
- [ ] Firewall configured (allow outbound HTTPS, WebSocket)
- [ ] API keys obtained (Binance, Upbit)
- [ ] Secrets configured (`/etc/arbitrage/arbitrage.env`)
- [ ] Configuration reviewed (`config/environments/production.py`)

### Deployment

- [ ] Docker image built successfully
- [ ] docker-compose.yml reviewed
- [ ] Services started: `docker-compose up -d`
- [ ] All services healthy: `docker-compose ps`
- [ ] Health check passing: `python healthcheck.py`
- [ ] Database migrations applied
- [ ] Redis keyspace clean
- [ ] Logs flowing: `docker-compose logs -f arbitrage-engine`

### Post-Deployment

- [ ] Health check passing (wait 60s)
- [ ] Recent logs present (no errors)
- [ ] Metrics collecting: `python tools/monitor.py --metrics`
- [ ] WebSocket connections active
- [ ] First trade executed (if in trading hours)
- [ ] Snapshot saved to PostgreSQL
- [ ] systemd service enabled (if applicable): `sudo systemctl enable arbitrage`
- [ ] Monitoring dashboard setup (future)
- [ ] Alert rules configured (future)
- [ ] Runbook reviewed
- [ ] On-call contact information updated

### Ongoing Maintenance

- [ ] Daily health checks
- [ ] Weekly log review
- [ ] Monthly secret rotation
- [ ] Quarterly dependency updates
- [ ] Backup verification (weekly)
- [ ] Disaster recovery drill (quarterly)

---

## Appendix

### A. Common Commands Reference

```bash
# Docker Compose
docker-compose up -d              # Start all services
docker-compose down               # Stop all services
docker-compose ps                 # List services
docker-compose logs -f <service>  # Follow logs
docker-compose restart <service>  # Restart service
docker-compose build              # Rebuild images

# systemd
sudo systemctl start arbitrage    # Start service
sudo systemctl stop arbitrage     # Stop service
sudo systemctl restart arbitrage  # Restart service
sudo systemctl status arbitrage   # Check status
sudo systemctl enable arbitrage   # Enable auto-start
sudo systemctl disable arbitrage  # Disable auto-start
sudo journalctl -u arbitrage -f   # Follow logs

# Health Check
python healthcheck.py             # Manual check
docker exec arbitrage-engine python healthcheck.py  # Container check

# Monitoring
python tools/monitor.py --metrics # Metrics dashboard
python tools/monitor.py --tail    # Tail logs
python tools/monitor.py --errors  # Errors only

# Database
psql -h localhost -U arbitrage -d arbitrage  # Connect to PostgreSQL
redis-cli -p 6380                            # Connect to Redis
```

### B. Environment Variables Reference

See "Secrets Management" section.

### C. Port Reference

| Service | Internal Port | Host Port | Description |
|---------|--------------|-----------|-------------|
| Redis | 6379 | 6380 | Redis server |
| PostgreSQL | 5432 | 5432 | PostgreSQL database |
| Engine | 8080 | 8080 | Metrics endpoint (future) |

### D. File Paths Reference

| Path | Description |
|------|-------------|
| `/opt/arbitrage` | Application root |
| `/etc/arbitrage/arbitrage.env` | Environment variables |
| `/var/log/arbitrage/service.log` | systemd service log |
| `/opt/arbitrage/logs/arbitrage_production.log` | Application log |
| `/opt/arbitrage/config/secrets.yaml` | Secrets configuration |

---

**End of DEPLOYMENT_GUIDE.md**

For operational procedures, see [RUNBOOK.md](RUNBOOK.md).  
For troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).  
For API reference, see [API_REFERENCE.md](API_REFERENCE.md).
