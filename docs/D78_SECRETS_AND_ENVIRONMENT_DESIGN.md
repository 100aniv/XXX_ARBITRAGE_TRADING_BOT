# D78-0: Authentication & Secrets Layer - Design Document

**Status:** ✅ COMPLETE  
**Date:** 2025-12-01  
**Phase:** D78 (Advanced Trading Phase)

---

## 1. Overview

### 1.1 Purpose

D78-0은 arbitrage-lite 프로젝트의 **중앙화된 인증 및 비밀정보 관리 계층**을 제공합니다. 이전에는 credentials가 코드 전반에 흩어져 있었고 `os.getenv()` 직접 호출로 관리되었습니다. D78-0은 이를 단일 `Settings` 모듈로 통합하여:

- ✅ **보안 강화**: 코드에 credentials 하드코딩 방지
- ✅ **환경 분리**: local_dev, paper, live 환경 명확히 구분
- ✅ **유지보수성**: 단일 소스 오브 트루스 (Single Source of Truth)
- ✅ **확장성**: 향후 Vault/KMS 통합 준비

### 1.2 Scope

**구현 완료:**
- `arbitrage/config/settings.py` - 중앙 Settings 모듈
- `.env` 템플릿 4종 (`.env.example`, `.env.local_dev.example`, `.env.paper.example`, `.env.live.example`)
- 기존 코드 리팩토링 (Telegram notifier, AlertManager rule engine)
- 테스트 16종 (ALL PASS)
- 문서화

**Out of Scope (향후 작업):**
- Vault/KMS 통합 (D78-1)
- UI for secrets management (D78-2)
- Secrets rotation automation (D78-3)

---

## 2. Architecture

### 2.1 Settings Module Structure

```
arbitrage/config/settings.py
├── RuntimeEnv (Enum)
│   ├── LOCAL_DEV
│   ├── PAPER
│   └── LIVE
├── Settings (Dataclass)
│   ├── Environment Selection
│   ├── Exchange Credentials (Upbit, Binance)
│   ├── Telegram Configuration
│   ├── Database Connection (PostgreSQL)
│   ├── Cache Configuration (Redis)
│   ├── Email/Slack (Optional)
│   └── Monitoring (Prometheus, Grafana)
├── get_settings() → Singleton
├── reload_settings() → Force reload
└── get_app_env() → Backward compatibility
```

### 2.2 Environment Model

#### local_dev
- **용도**: 로컬 개발, 단위 테스트
- **Validation**: 느슨함 (warnings only)
- **Credentials**: 선택적 (mock 사용 가능)
- **Database**: 로컬 PostgreSQL/Redis
- **Alerts**: 테스트 Telegram 채팅 (선택적)

#### paper
- **용도**: 실제 시장 데이터를 사용한 PAPER 트레이딩
- **Validation**: 엄격함 (missing credentials → startup failure)
- **Credentials**: 필수 (Upbit/Binance API, Telegram, DB)
- **Database**: Production-grade PostgreSQL/Redis
- **Alerts**: 실제 Telegram 채팅

#### live
- **용도**: 실제 거래 (🔴 DANGER: Real Money)
- **Validation**: 매우 엄격함
- **Credentials**: 필수 (모든 시스템)
- **Security**: IP whitelisting, 2FA, withdrawal 비활성화
- **Monitoring**: 필수 (Prometheus/Grafana/Telegram)

---

## 3. Environment Variables

### 3.1 Naming Convention

| Category | Prefix | Example |
|----------|--------|---------|
| Environment | `ARBITRAGE_` | `ARBITRAGE_ENV` |
| Upbit | `UPBIT_` | `UPBIT_ACCESS_KEY` |
| Binance | `BINANCE_` | `BINANCE_API_KEY` |
| Telegram | `TELEGRAM_` | `TELEGRAM_BOT_TOKEN` |
| PostgreSQL | `POSTGRES_` | `POSTGRES_HOST`, `POSTGRES_DSN` |
| Redis | `REDIS_` | `REDIS_HOST`, `REDIS_URL` |
| Email | `SMTP_` | `SMTP_HOST` |
| Slack | `SLACK_` | `SLACK_WEBHOOK_URL` |
| Monitoring | `PROMETHEUS_`, `GRAFANA_` | `PROMETHEUS_PORT` |

### 3.2 Required Variables by Environment

#### local_dev (모두 선택적)
```bash
ARBITRAGE_ENV=local_dev
# 나머지는 선택적 또는 기본값 사용
```

#### paper (엄격한 필수 항목)
```bash
ARBITRAGE_ENV=paper

# Exchange (최소 1개 필수)
UPBIT_ACCESS_KEY=xxx
UPBIT_SECRET_KEY=xxx
# OR
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx

# Telegram (필수)
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx

# Database (필수)
POSTGRES_DSN=postgresql://user:pass@host:5432/db
# OR
POSTGRES_HOST=host
POSTGRES_PORT=5432
POSTGRES_DB=db
POSTGRES_USER=user
POSTGRES_PASSWORD=pass

# Redis (기본값: localhost:6379/0)
REDIS_URL=redis://host:6379/0
```

#### live (paper와 동일 + 추가 보안 권장)
```bash
ARBITRAGE_ENV=live
# paper와 동일한 필수 항목
# + 추가 보안 고려사항
```

---

## 4. Usage

### 4.1 Basic Usage

```python
from arbitrage.config.settings import get_settings

# Get settings (singleton)
settings = get_settings()

# Access credentials
upbit_key = settings.upbit_access_key
telegram_token = settings.telegram_bot_token

# Get DSN/URL
postgres_dsn = settings.get_postgres_dsn()
redis_url = settings.get_redis_url()

# Check environment
if settings.env == RuntimeEnv.LIVE:
    print("⚠️  WARNING: LIVE MODE")
```

### 4.2 Testing with Overrides

```python
from arbitrage.config.settings import get_settings, RuntimeEnv

# Override for testing
settings = get_settings(overrides={
    "env": RuntimeEnv.LOCAL_DEV,
    "upbit_access_key": "test_key",
    "telegram_bot_token": "test_token",
})
```

### 4.3 Integration Example (Telegram Notifier)

**Before (D77):**
```python
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")
```

**After (D78):**
```python
from arbitrage.config.settings import get_settings

settings = get_settings()
bot_token = settings.telegram_bot_token
chat_id = settings.telegram_default_chat_id
```

### 4.4 Backward Compatibility

```python
from arbitrage.config.settings import get_app_env

# Maps ARBITRAGE_ENV to APP_ENV
# local_dev → "development"
# paper → "staging"
# live → "production"
app_env = get_app_env()
```

---

## 5. .env File Templates

### 5.1 File Structure

```
arbitrage-lite/
├── .env                    # Actual credentials (gitignored)
├── .env.example            # Base template
├── .env.local_dev.example  # Local development template
├── .env.paper.example      # Paper trading template
└── .env.live.example       # Live trading template
```

### 5.2 Creating Your .env File

```bash
# For local development
cp .env.local_dev.example .env.local_dev
# Edit .env.local_dev with your values

# For paper trading
cp .env.paper.example .env.paper
# Edit .env.paper with REAL credentials

# Set environment
export ARBITRAGE_ENV=local_dev
# OR
export ARBITRAGE_ENV=paper
```

### 5.3 Security Best Practices

✅ **DO:**
- Keep `.env*` files in `.gitignore`
- Use separate `.env` files for each environment
- Rotate credentials regularly (quarterly)
- Use read-only API keys for paper mode
- Enable 2FA on exchange accounts
- Use IP whitelisting

❌ **DON'T:**
- Commit `.env` files to git
- Share credentials via email/Slack
- Use same credentials across environments
- Enable withdrawal permissions on API keys
- Hardcode credentials in code

---

## 6. Validation & Error Handling

### 6.1 Validation Logic

```python
def validate(self):
    if self.env == RuntimeEnv.LOCAL_DEV:
        # Warnings only
        if not self.telegram_bot_token:
            print("Warning: TELEGRAM_BOT_TOKEN not set")
    
    elif self.env in (RuntimeEnv.PAPER, RuntimeEnv.LIVE):
        # Strict validation
        missing = []
        
        # At least one exchange
        if not (self.upbit_access_key and self.upbit_secret_key) and \
           not (self.binance_api_key and self.binance_api_secret):
            missing.append("Exchange credentials")
        
        # Telegram required
        if not self.telegram_bot_token or not self.telegram_default_chat_id:
            missing.append("Telegram")
        
        # Database required
        if not self.postgres_dsn and not self.postgres_host:
            missing.append("PostgreSQL")
        
        if missing:
            raise ValueError(f"Missing: {', '.join(missing)}")
```

### 6.2 Error Messages

**Missing credentials (paper/live):**
```
============================================================
CRITICAL: Missing required credentials for paper environment:
  - At least one exchange (Upbit or Binance) credentials required
  - TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required for paper/live

Please set the following environment variables:
  ARBITRAGE_ENV=paper
  UPBIT_ACCESS_KEY=your_upbit_access_key
  UPBIT_SECRET_KEY=your_upbit_secret_key
  TELEGRAM_BOT_TOKEN=your_telegram_bot_token
  TELEGRAM_CHAT_ID=your_telegram_chat_id

Alternatively, create a .env.paper file at project root.
============================================================
```

---

## 7. Migration Guide

### 7.1 코드 마이그레이션

**Step 1: Import Settings**
```python
from arbitrage.config.settings import get_settings
```

**Step 2: Replace os.getenv()**
```python
# Before
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))

# After
settings = get_settings()
redis_host = settings.redis_host
redis_port = settings.redis_port
```

**Step 3: Update Tests**
```python
# Before
@patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"})
def test_telegram():
    ...

# After
settings = get_settings(overrides={"telegram_bot_token": "test_token"})
# OR
from arbitrage.config import settings as settings_module
settings_module._settings_instance = Settings.from_env(overrides={...})
```

### 7.2 Migration Checklist

- [ ] Replace all `os.getenv("UPBIT_*")` with `settings.upbit_*`
- [ ] Replace all `os.getenv("BINANCE_*")` with `settings.binance_*`
- [ ] Replace all `os.getenv("TELEGRAM_*")` with `settings.telegram_*`
- [ ] Replace all `os.getenv("POSTGRES_*")` with `settings.postgres_*`
- [ ] Replace all `os.getenv("REDIS_*")` with `settings.redis_*`
- [ ] Update tests to use `get_settings(overrides={...})`
- [ ] Create `.env.local_dev` for local development
- [ ] Create `.env.paper` for paper trading (DO NOT COMMIT)
- [ ] Update deployment scripts to set `ARBITRAGE_ENV`
- [ ] Run regression tests

---

## 8. Future Enhancements

### 8.1 D78-1: Vault/KMS Integration (TODO)

**Objective:** Integrate with HashiCorp Vault or AWS Secrets Manager for production

**Features:**
- Dynamic secrets fetching
- Automatic credential rotation
- Audit logging
- Fine-grained access control

**Implementation:**
```python
class VaultSettings(Settings):
    def __init__(self, vault_client):
        self.vault = vault_client
        super().__init__()
    
    @property
    def upbit_access_key(self):
        return self.vault.get_secret("upbit/access_key")
```

### 8.2 D78-2: Secrets UI (TODO)

**Objective:** Web UI for secrets management (admin only)

**Features:**
- View/Edit credentials (masked)
- Test connection (Upbit/Binance/Telegram/DB)
- Audit log viewer
- Credential rotation workflow

### 8.3 D78-3: Rotation Automation (TODO)

**Objective:** Automated credential rotation

**Features:**
- Scheduled rotation (quarterly)
- Zero-downtime rotation
- Rollback on failure
- Notification (Telegram/Email)

---

## 9. Testing

### 9.1 Test Coverage

```bash
$ python -m pytest tests/test_d78_settings.py -v

16 tests PASS:
✅ Settings creation (local_dev)
✅ Settings with overrides
✅ PostgreSQL DSN generation
✅ Redis URL generation
✅ Environment validation (local_dev/paper/live)
✅ Singleton behavior
✅ Backward compatibility (APP_ENV)
✅ Environment variable loading
```

### 9.2 Running Tests

```bash
# All D78 tests
pytest tests/test_d78_settings.py -v

# Regression tests (ensure no breakage)
pytest -q
```

---

## 10. Troubleshooting

### 10.1 Common Issues

**Issue: "Missing required credentials for paper environment"**
```bash
# Solution: Create .env.paper and fill in all required fields
cp .env.paper.example .env.paper
vi .env.paper  # Fill in credentials
export ARBITRAGE_ENV=paper
```

**Issue: "Settings not reloading after env var change"**
```python
# Solution: Force reload
from arbitrage.config.settings import reload_settings
settings = reload_settings()
```

**Issue: "Tests failing with validation errors"**
```python
# Solution: Use overrides in tests
settings = get_settings(overrides={
    "env": RuntimeEnv.LOCAL_DEV,  # Skip strict validation
})
```

### 10.2 Debug Mode

```python
from arbitrage.config.settings import get_settings

settings = get_settings()
print(settings.to_dict())  # View configuration (credentials masked)
```

Output:
```json
{
  "env": "local_dev",
  "upbit_configured": true,
  "binance_configured": false,
  "telegram_configured": true,
  "postgres_configured": true,
  "redis_configured": true,
  ...
}
```

---

## 11. Related Documents

- **D77-1:** Prometheus Exporter (uses Settings for monitoring config)
- **D77-2:** Grafana Dashboards (visualizes system metrics)
- **D76:** Alerting Infrastructure (Telegram-first policy)
- **D75:** Core Arbitrage Infrastructure (RiskGuard, Health Monitor)

---

## 12. Summary

D78-0은 arbitrage-lite 프로젝트의 **인증 및 비밀정보 관리를 중앙화**하여:

✅ **보안**: Credentials 하드코딩 방지  
✅ **환경 분리**: local_dev / paper / live 명확히 구분  
✅ **유지보수성**: 단일 Settings 모듈로 통합  
✅ **확장성**: Vault/KMS 통합 준비 완료  
✅ **테스트**: 16/16 PASS  
✅ **문서화**: 완전한 설계 문서 및 사용 가이드  

**Next Steps:**
- D78-1: Vault/KMS Integration (향후)
- D77-0-RM: Real Market Validation with D78 (권장)
- Production deployment with `.env.live`

---

**Document Version:** 1.0  
**Last Updated:** 2025-12-01  
**Author:** D78-0 Implementation Team
