# D78-2: Vault/KMS Integration Design

**Status:** ✅ **COMPLETE**  
**Date:** 2025-12-01  
**Owner:** Arbitrage Bot Team

---

## 📋 Summary

Enterprise-grade Secrets Management Layer를 기존 D78-0, D78-1과 호환되도록 구현.

**핵심 목표:**
1. ✅ Pluggable SecretsProvider 인터페이스
2. ✅ 4가지 Provider 구현 (Env, Vault, KMS, LocalFallback)
3. ✅ Settings와 투명한 통합
4. ✅ 완전한 Backward Compatibility
5. ✅ Production-ready Vault/KMS 지원

---

## 🏗️ Architecture

### SecretsProvider 계층 구조

```
arbitrage/config/secrets_providers/
├── __init__.py
├── base.py                     # SecretsProviderBase (abstract interface)
├── env_provider.py             # EnvSecretsProvider (기본, backward compatible)
├── local_fallback_provider.py  # LocalFallbackProvider (개발용)
├── vault_provider.py           # VaultSecretsProvider (HashiCorp Vault KV v2)
└── kms_provider.py             # KMSSecretsProvider (AWS Secrets Manager)
```

### 인터페이스 (SecretsProviderBase)

모든 provider는 다음 메서드를 구현:

```python
class SecretsProviderBase(ABC):
    @abstractmethod
    def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
        """Secret 값 조회"""
        pass
    
    @abstractmethod
    def set_secret(key: str, value: str) -> None:
        """Secret 저장"""
        pass
    
    @abstractmethod
    def list_secrets() -> List[str]:
        """사용 가능한 secret 키 목록"""
        pass
    
    @abstractmethod
    def health() -> Dict[str, Any]:
        """Provider 상태 확인"""
        pass
```

---

## 🔌 Provider 구현

### 1. EnvSecretsProvider (기본)

**특징:**
- 환경변수에서 secrets 읽기
- `.env` 파일과 완전 호환
- D78-0, D78-1과 backward compatible
- Read-only (runtime 환경변수 설정만 가능)

**사용:**
```python
from arbitrage.config.secrets_providers import EnvSecretsProvider

provider = EnvSecretsProvider()
api_key = provider.get_secret("UPBIT_ACCESS_KEY")
```

**환경:**
- ✅ local_dev
- ✅ paper
- ✅ live

---

### 2. LocalFallbackProvider (개발용)

**특징:**
- 로컬 JSON 파일에서 secrets 읽기/쓰기
- 개발 환경 전용
- `.secrets.local.json` 파일 사용
- **Production 사용 금지!**

**사용:**
```python
from arbitrage.config.secrets_providers import LocalFallbackProvider

provider = LocalFallbackProvider(secrets_file=".secrets.local.json")
provider.set_secret("UPBIT_ACCESS_KEY", "your_key")
api_key = provider.get_secret("UPBIT_ACCESS_KEY")
```

**환경:**
- ✅ local_dev (권장)
- ⚠️ paper (테스트 목적만)
- ❌ live (절대 금지)

---

### 3. VaultSecretsProvider (Production)

**특징:**
- HashiCorp Vault KV v2 engine 사용
- Token 기반 인증
- Enterprise-grade security
- Production 환경 권장

**Optional Dependency:**
```bash
pip install hvac
```

**환경변수:**
```bash
VAULT_ADDR=https://vault.example.com:8200
VAULT_TOKEN=your_vault_token
VAULT_NAMESPACE=your_namespace  # (선택적, Enterprise only)
VAULT_MOUNT_POINT=secret         # (기본값: "secret")
VAULT_PATH=arbitrage             # (기본값: "arbitrage")
```

**사용:**
```python
from arbitrage.config.secrets_providers import VaultSecretsProvider

provider = VaultSecretsProvider(
    vault_addr="https://vault.example.com:8200",
    vault_token="your_token",
    mount_point="secret",
    path="arbitrage",
)

# Get secret
api_key = provider.get_secret("UPBIT_ACCESS_KEY")

# Set secret
provider.set_secret("BINANCE_API_KEY", "new_key")

# Health check
health = provider.health()
```

**환경:**
- ❌ local_dev (불필요)
- ✅ paper (optional)
- ✅ live (**권장**)

---

### 4. KMSSecretsProvider (Cloud Production)

**특징:**
- AWS Secrets Manager 사용
- IAM 인증 (boto3)
- Cloud-native secrets management
- Production 환경 권장

**Optional Dependency:**
```bash
pip install boto3
```

**환경변수:**
```bash
AWS_REGION=ap-northeast-2
AWS_SECRET_NAME=arbitrage/secrets  # (기본값)
# IAM role 권장 (EC2/ECS/Lambda)
# 또는:
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

**사용:**
```python
from arbitrage.config.secrets_providers import KMSSecretsProvider

provider = KMSSecretsProvider(
    region_name="ap-northeast-2",
    secret_name="arbitrage/secrets",
)

# Get secret
api_key = provider.get_secret("UPBIT_ACCESS_KEY")

# Set secret
provider.set_secret("TELEGRAM_BOT_TOKEN", "new_token")

# Health check
health = provider.health()
```

**환경:**
- ❌ local_dev (불필요)
- ✅ paper (optional)
- ✅ live (**권장**)

---

## 🔗 Settings 통합

### Auto-Selection 로직

Settings.from_env()는 다음 우선순위로 SecretsProvider를 선택:

1. **Explicit provider** (파라미터로 전달)
2. **Environment-based auto-selection** (향후 구현)
3. **Default: EnvSecretsProvider** (backward compatible)

```python
from arbitrage.config.settings import Settings

# 1. 기본 (EnvSecretsProvider 자동 사용)
settings = Settings.from_env()

# 2. Custom provider 지정
from arbitrage.config.secrets_providers import VaultSecretsProvider

vault_provider = VaultSecretsProvider()
settings = Settings.from_env(secrets_provider=vault_provider)

# 3. LocalFallbackProvider (개발용)
from arbitrage.config.secrets_providers import LocalFallbackProvider

local_provider = LocalFallbackProvider()
settings = Settings.from_env(secrets_provider=local_provider)
```

### Backward Compatibility

**D78-0, D78-1과 100% 호환:**
- ✅ `.env` 파일 그대로 동작
- ✅ 환경변수 그대로 동작
- ✅ `setup_env.py`, `validate_env.py` 그대로 동작
- ✅ 기존 코드 변경 불필요

```python
# 기존 방식 (여전히 동작)
settings = Settings.from_env()
assert settings.upbit_access_key == os.getenv("UPBIT_ACCESS_KEY")

# 새로운 방식 (optional)
vault_provider = VaultSecretsProvider()
settings = Settings.from_env(secrets_provider=vault_provider)
assert settings.upbit_access_key == vault_provider.get_secret("UPBIT_ACCESS_KEY")
```

---

## 🧪 Testing

### 테스트 커버리지

**파일:** `tests/test_d78_2_secrets_providers.py`

**테스트 수:** 16/16 PASS

**테스트 항목:**

1. **EnvSecretsProvider (6 tests)**
   - ✅ 환경변수에서 secret 조회
   - ✅ 기본값 사용
   - ✅ Secret 없을 때 예외
   - ✅ 환경변수 설정 (runtime)
   - ✅ Secret 목록 조회
   - ✅ Health check

2. **LocalFallbackProvider (7 tests)**
   - ✅ 파일에서 secret 조회
   - ✅ 기본값 사용
   - ✅ Secret 없을 때 예외
   - ✅ 파일에 secret 저장
   - ✅ Secret 목록 조회
   - ✅ Health check (파일 존재)
   - ✅ Health check (파일 없음, degraded)

3. **Settings 통합 (3 tests)**
   - ✅ 기본값으로 EnvSecretsProvider 사용
   - ✅ Custom provider 사용
   - ✅ Backward compatibility

4. **Vault/KMS Tests (skipped - optional dependencies)**
   - ⏭️ Vault provider tests (hvac 필요)
   - ⏭️ KMS provider tests (boto3 필요)

**실행:**
```bash
# 기본 테스트 (EnvSecretsProvider, LocalFallbackProvider)
pytest tests/test_d78_2_secrets_providers.py -v

# Vault/KMS 테스트 포함 (optional dependencies 설치 후)
pip install hvac boto3
pytest tests/test_d78_2_secrets_providers.py -v --run-all
```

---

## 🔒 Security Best Practices

### 1. Provider 선택 권고

| 환경 | 권장 Provider | 이유 |
|------|--------------|------|
| local_dev | EnvSecretsProvider 또는 LocalFallbackProvider | 간편함, 격리 |
| paper | EnvSecretsProvider (기본) | .env 파일 사용 |
| paper (Advanced) | VaultSecretsProvider | 실제 환경 테스트 |
| live | VaultSecretsProvider 또는 KMSSecretsProvider | Enterprise security |

### 2. Vault Production Setup

**필수 사항:**
1. ✅ TLS/HTTPS 사용 (VAULT_ADDR=https://...)
2. ✅ Token rotation 정책 설정
3. ✅ Audit logging 활성화
4. ✅ Namespace isolation (Vault Enterprise)
5. ✅ Least privilege 정책 (read-only tokens 사용)

**예시 Vault 정책:**
```hcl
path "secret/data/arbitrage" {
  capabilities = ["read"]
}

path "secret/metadata/arbitrage" {
  capabilities = ["list"]
}
```

### 3. KMS Production Setup

**필수 사항:**
1. ✅ IAM role 사용 (access key/secret key 대신)
2. ✅ Secrets Manager 암호화 (KMS key)
3. ✅ Secret rotation 활성화
4. ✅ CloudTrail 로깅 활성화
5. ✅ Least privilege IAM policy

**예시 IAM 정책:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:ap-northeast-2:123456789012:secret:arbitrage/secrets-*"
    }
  ]
}
```

### 4. 절대 금지 사항

❌ **Production에서 LocalFallbackProvider 사용**
❌ **Git에 `.secrets.local.json` 커밋**
❌ **Vault/KMS credentials hardcoding**
❌ **Live 환경에서 plaintext secrets**

---

## 📊 Usage Examples

### Example 1: Local Development (LocalFallbackProvider)

```python
from arbitrage.config.settings import Settings
from arbitrage.config.secrets_providers import LocalFallbackProvider

# Setup local secrets
provider = LocalFallbackProvider()
provider.set_secret("UPBIT_ACCESS_KEY", "your_test_key")
provider.set_secret("UPBIT_SECRET_KEY", "your_test_secret")

# Load settings
settings = Settings.from_env(secrets_provider=provider)
print(f"Upbit Key: {settings.upbit_access_key}")
```

### Example 2: Paper Trading (EnvSecretsProvider)

```bash
# .env.paper 파일
ARBITRAGE_ENV=paper
UPBIT_ACCESS_KEY=your_key
UPBIT_SECRET_KEY=your_secret
```

```python
from arbitrage.config.settings import Settings

# 기본 provider (EnvSecretsProvider) 자동 사용
settings = Settings.from_env()
print(f"Environment: {settings.env}")
```

### Example 3: Live Trading (VaultSecretsProvider)

```bash
# 환경변수
export VAULT_ADDR=https://vault.production.com
export VAULT_TOKEN=$(cat ~/.vault-token)
export ARBITRAGE_ENV=live
```

```python
from arbitrage.config.settings import Settings
from arbitrage.config.secrets_providers import VaultSecretsProvider

# Vault provider 사용
vault_provider = VaultSecretsProvider()
settings = Settings.from_env(secrets_provider=vault_provider)

# Health check
health = vault_provider.health()
print(f"Vault Status: {health['status']}")
```

---

## 🚀 Migration Guide

### From D78-1 (Env Setup Wizard) to D78-2 (Vault/KMS)

#### Step 1: 현재 상태 유지 (No Changes Required)

기존 `.env` 파일 방식은 그대로 동작합니다.

```bash
# 기존 workflow (여전히 동작)
python scripts/setup_env.py --env paper
python scripts/validate_env.py --env paper
```

#### Step 2: Vault로 마이그레이션 (Optional)

1. **Vault 설치 및 설정**
   ```bash
   # Vault 설치 (Docker)
   docker run -d --name vault \
     -p 8200:8200 \
     --cap-add=IPC_LOCK \
     -e 'VAULT_DEV_ROOT_TOKEN_ID=myroot' \
     vault
   
   # Vault CLI 설치
   brew install vault  # macOS
   # 또는 https://www.vaultproject.io/downloads
   ```

2. **Secrets 업로드**
   ```bash
   export VAULT_ADDR='http://127.0.0.1:8200'
   export VAULT_TOKEN='myroot'
   
   # KV v2 enable (이미 활성화되어 있을 수도 있음)
   vault secrets enable -path=secret kv-v2
   
   # Secrets 저장
   vault kv put secret/arbitrage \
     UPBIT_ACCESS_KEY="your_key" \
     UPBIT_SECRET_KEY="your_secret" \
     BINANCE_API_KEY="your_binance_key" \
     BINANCE_API_SECRET="your_binance_secret" \
     TELEGRAM_BOT_TOKEN="your_token" \
     TELEGRAM_CHAT_ID="your_chat_id" \
     POSTGRES_PASSWORD="your_db_password"
   ```

3. **애플리케이션 설정 변경**
   ```python
   from arbitrage.config.settings import Settings
   from arbitrage.config.secrets_providers import VaultSecretsProvider
   
   # Vault provider 사용
   vault_provider = VaultSecretsProvider(
       vault_addr="http://127.0.0.1:8200",
       vault_token="myroot",
       mount_point="secret",
       path="arbitrage",
   )
   
   settings = Settings.from_env(secrets_provider=vault_provider)
   ```

#### Step 3: AWS Secrets Manager로 마이그레이션 (Optional)

1. **AWS Secrets Manager에 Secret 생성**
   ```bash
   aws secretsmanager create-secret \
     --name arbitrage/secrets \
     --description "Arbitrage Bot Secrets" \
     --secret-string '{
       "UPBIT_ACCESS_KEY": "your_key",
       "UPBIT_SECRET_KEY": "your_secret",
       "BINANCE_API_KEY": "your_binance_key",
       "BINANCE_API_SECRET": "your_binance_secret",
       "TELEGRAM_BOT_TOKEN": "your_token",
       "TELEGRAM_CHAT_ID": "your_chat_id",
       "POSTGRES_PASSWORD": "your_db_password"
     }' \
     --region ap-northeast-2
   ```

2. **애플리케이션 설정 변경**
   ```python
   from arbitrage.config.settings import Settings
   from arbitrage.config.secrets_providers import KMSSecretsProvider
   
   # KMS provider 사용
   kms_provider = KMSSecretsProvider(
       region_name="ap-northeast-2",
       secret_name="arbitrage/secrets",
   )
   
   settings = Settings.from_env(secrets_provider=kms_provider)
   ```

---

## 📝 Done Criteria

- [x] ✅ SecretsProviderBase 인터페이스 설계
- [x] ✅ EnvSecretsProvider 구현
- [x] ✅ LocalFallbackProvider 구현
- [x] ✅ VaultSecretsProvider 구현
- [x] ✅ KMSSecretsProvider 구현
- [x] ✅ Settings 통합 (backward compatible)
- [x] ✅ Tests 16/16 PASS
- [x] ✅ Documentation (D78_VAULT_KMS_DESIGN.md)
- [x] ✅ No breaking changes to D78-0, D78-1

---

## 🔄 Next Steps

### D78-3: Auto-Selection Logic (Future)

환경변수 기반으로 provider 자동 선택:

```bash
# 환경변수 설정
ARBITRAGE_ENV=live
SECRETS_PROVIDER=vault  # or "kms", "env", "local_fallback"
```

```python
# Auto-select based on SECRETS_PROVIDER
settings = Settings.from_env()  # Vault provider 자동 사용
```

### D78-4: Secrets Rotation (Future)

- Vault/KMS에서 자동 rotation 지원
- Settings 런타임 reload 기능

---

## 📚 Related Documents

- [D78-0: Central Settings & Environment Management](./D78_SECRETS_AND_ENVIRONMENT_DESIGN.md)
- [D78-1: Env Setup Wizard & Validator](./D78_SECRETS_AND_ENVIRONMENT_DESIGN.md#d78-1-env-setup-wizard--validator)
- [Vault Documentation](https://www.vaultproject.io/docs)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)

---

**Status:** ✅ **COMPLETE**  
**Version:** 1.0.0  
**Last Updated:** 2025-12-01
