# M5 Release Checklist (Production Readiness SSOT)

**Owner:** DevOps Team  
**Last Updated:** 2025-12-23  
**Status:** 🚧 IN PROGRESS (D99-6 P5)

---

## Executive Summary

This checklist ensures safe, reproducible releases for the Arbitrage Trading Bot. All items must be verified before production deployment.

---

## Pre-Release Gate (Must Pass 100%)

### 1. Test Gates ✅
- [ ] **Core Regression:** 178/178 PASS (SSOT: `docs/CORE_REGRESSION_SSOT.md`)
- [ ] **Full Regression:** ≤ 100 FAIL (Current: 90 FAIL, Target: 50)
- [ ] **D98 Tests:** 46/46 PASS (ReadOnlyGuard, LiveSafetyValidator)
- [ ] **Paper Mode Smoke Test:** 5-min run, 0 crashes

### 2. Environment Configuration ✅
- [ ] `.env.production` file created (from `.env.example`)
- [ ] All secrets placeholders replaced with real values
- [ ] Secrets stored in secure vault (HashiCorp Vault / AWS Secrets Manager)
- [ ] No secrets in Git history (verified with `git log --all --full-history -- "*.env"`)

### 3. Infrastructure Readiness ✅
- [ ] Docker Compose: Postgres, Redis, Prometheus, Grafana running
- [ ] Database migrations applied (`db/migrations/*.sql`)
- [ ] Redis keyspace configured (`docs/REDIS_KEYSPACE.md`)
- [ ] Monitoring endpoints verified (`/health`, `/metrics`)

### 4. Security Gates ✅
- [ ] **ReadOnlyGuard:** Enabled in all environments (D98-1~3)
- [ ] **LiveSafetyValidator:** ARM + Timestamp + Notional checks (D98-4)
- [ ] **Live API Keys:** Production keys installed, test keys removed
- [ ] **Firewall Rules:** Inbound ports restricted (only monitoring)

---

## Release Execution (Step-by-Step)

### Step 1: Code Freeze
```bash
git checkout -b release/vX.Y.Z
git tag vX.Y.Z
git push origin vX.Y.Z
```

### Step 2: Build & Package
```bash
docker build -t arbitrage-bot:vX.Y.Z -f Dockerfile .
docker tag arbitrage-bot:vX.Y.Z gcr.io/project/arbitrage-bot:vX.Y.Z
docker push gcr.io/project/arbitrage-bot:vX.Y.Z
```

### Step 3: Deploy to Staging
```bash
# Update .env.staging with new version
docker-compose -f docker-compose.staging.yml up -d

# Verify health
curl http://staging:8080/health

# Run smoke test (5-min Paper mode)
python scripts/run_paper_smoke_test.py --duration 300
```

### Step 4: Deploy to Production (Manual Approval Required)
```bash
# Backup current database
pg_dump arbitrage_prod > backup_$(date +%Y%m%d_%H%M%S).sql

# Deploy new version
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d --no-deps arbitrage-engine

# Verify health
curl http://prod:8080/health

# Monitor logs for 5 minutes
docker logs -f arbitrage-engine --since 5m
```

### Step 5: Post-Deployment Verification
- [ ] Prometheus metrics collecting (check `/metrics`)
- [ ] Grafana dashboards updating
- [ ] Telegram alerts working (send test P0 alert)
- [ ] Database connections healthy
- [ ] No error logs in first 10 minutes

---

## Rollback Procedure (Emergency)

### Trigger Conditions
- Crash within 5 minutes of deployment
- Error rate > 10% of iterations
- Database connection failures
- Prometheus /metrics endpoint down

### Rollback Steps
```bash
# 1. Stop new version
docker-compose -f docker-compose.prod.yml stop arbitrage-engine

# 2. Restore previous version
docker tag arbitrage-bot:vX.Y.Z-1 arbitrage-bot:latest
docker-compose -f docker-compose.prod.yml up -d arbitrage-engine

# 3. Verify rollback success
curl http://prod:8080/health

# 4. Restore database if needed
psql arbitrage_prod < backup_YYYYMMDD_HHMMSS.sql
```

---

## Secrets Management (SSOT)

### Required Secrets (Production)

| Secret | Location | Rotation Period | Owner |
|--------|----------|----------------|-------|
| `UPBIT_ACCESS_KEY` | Vault: `secret/prod/upbit/access_key` | 90 days | DevOps |
| `UPBIT_SECRET_KEY` | Vault: `secret/prod/upbit/secret_key` | 90 days | DevOps |
| `BINANCE_API_KEY` | Vault: `secret/prod/binance/api_key` | 90 days | DevOps |
| `BINANCE_SECRET_KEY` | Vault: `secret/prod/binance/secret_key` | 90 days | DevOps |
| `POSTGRES_PASSWORD` | Vault: `secret/prod/postgres/password` | 180 days | DBA |
| `REDIS_PASSWORD` | Vault: `secret/prod/redis/password` | 180 days | DBA |
| `TELEGRAM_BOT_TOKEN` | Vault: `secret/prod/telegram/bot_token` | Never | DevOps |

### Secret Injection (Docker)
```yaml
# docker-compose.prod.yml
services:
  arbitrage-engine:
    environment:
      UPBIT_ACCESS_KEY: ${UPBIT_ACCESS_KEY}
      UPBIT_SECRET_KEY: ${UPBIT_SECRET_KEY}
      # ... (load from .env.production)
```

### Secret Rotation Procedure
1. Generate new secret in exchange/service
2. Update Vault entry with new secret
3. Update `.env.production` (pull from Vault)
4. Rolling restart: `docker-compose restart arbitrage-engine`
5. Verify old secret no longer used
6. Revoke old secret in exchange/service

---

## Monitoring & Alerting (SSOT)

### Prometheus Metrics (7 Core KPIs)
- `preflight_core_regression_pass` (gauge)
- `preflight_full_regression_pass` (gauge)
- `preflight_full_regression_fail` (gauge)
- `preflight_execution_duration_seconds` (gauge)
- `preflight_last_run_timestamp` (gauge)
- `preflight_last_run_exit_code` (gauge)
- `preflight_fail_gate_triggered` (gauge)

### Grafana Dashboards
- **Dashboard:** Arbitrage Bot Health
- **Panels:** 4 core panels (Pass/Fail/Duration/Timestamp)
- **URL:** `http://grafana:3000/d/arbitrage-health`

### Telegram Alerts (P0/P1)
- **P0 (CRITICAL):** Crash, DB down, Redis down, Core Regression FAIL
- **P1 (WARNING):** Full Regression FAIL > 100, High latency (>100ms)
- **P2 (INFO):** Release deployed, Config changed

---

## Compliance & Audit Trail

### Immutable Trade Logging
- All trades logged to PostgreSQL (`trades` table)
- Backup: Daily snapshots to S3 (30-day retention)
- Audit queries: `scripts/audit_trade_log.sql`

### Regulatory Reporting
- Daily P&L report: `scripts/generate_daily_pnl_report.py`
- Monthly reconciliation: Compare bot trades vs exchange statements
- Tax reporting: Generate 1099 forms (for US entities)

### Access Control
- Production SSH: Bastion host only (2FA required)
- Database access: Read-only for analysts, write for DBA only
- Secret access: Vault ACL (DevOps team only)

---

## Success Criteria (Release Sign-Off)

### Mandatory (Must Pass 100%)
- ✅ All Pre-Release Gates passed
- ✅ Staging deployment successful
- ✅ Production deployment successful
- ✅ Post-deployment verification passed
- ✅ Monitoring/alerting operational

### Recommended (Best Practice)
- ⚠️ Full Regression ≤ 50 FAIL (Current: 90)
- ⚠️ Load test: 1-hour continuous run (0 crashes)
- ⚠️ Rollback drill: Practice rollback procedure

---

## Contact & Escalation

| Role | Contact | Escalation |
|------|---------|------------|
| **Release Manager** | devops@example.com | CTO |
| **On-Call Engineer** | oncall@example.com | Engineering Lead |
| **DBA** | dba@example.com | Infrastructure Lead |

**Incident Hotline:** +1-XXX-XXX-XXXX (24/7)

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v1.0 | 2025-12-23 | Windsurf AI | Initial release checklist for D99-6 P5 |

---

## References

- `docs/DEPLOYMENT_GUIDE.md` - Detailed deployment procedures
- `docs/D98/D98_RUNBOOK.md` - Production runbook (D98-0)
- `docs/D78_SECRETS_AND_ENVIRONMENT_DESIGN.md` - Secrets architecture
- `docs/D78_VAULT_KMS_DESIGN.md` - Vault/KMS integration
- `docs/CORE_REGRESSION_SSOT.md` - Test gate definitions
