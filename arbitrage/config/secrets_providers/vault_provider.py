# -*- coding: utf-8 -*-
"""
D78-2: HashiCorp Vault Secrets Provider

HashiCorp Vault KV v2 engine을 사용한 enterprise-grade secrets provider.
"""

import os
from typing import Optional, Dict, Any, List
from .base import SecretsProviderBase, SecretNotFoundError


class VaultSecretsProvider(SecretsProviderBase):
    """
    HashiCorp Vault Secrets Provider
    
    - KV v2 secrets engine 사용
    - Token 기반 인증
    - Production 환경 권장
    
    Environment Variables:
        VAULT_ADDR: Vault 서버 주소 (예: https://vault.example.com:8200)
        VAULT_TOKEN: Vault 인증 토큰
        VAULT_NAMESPACE: Vault namespace (선택적, Enterprise only)
        VAULT_MOUNT_POINT: KV secrets mount point (기본: "secret")
        VAULT_PATH: Secrets path (기본: "arbitrage")
    """
    
    def __init__(
        self,
        vault_addr: Optional[str] = None,
        vault_token: Optional[str] = None,
        namespace: Optional[str] = None,
        mount_point: str = "secret",
        path: str = "arbitrage",
    ):
        """
        Initialize VaultSecretsProvider
        
        Args:
            vault_addr: Vault 서버 주소 (기본: 환경변수 VAULT_ADDR)
            vault_token: Vault 토큰 (기본: 환경변수 VAULT_TOKEN)
            namespace: Vault namespace (선택적)
            mount_point: KV mount point (기본: "secret")
            path: Secrets 저장 경로 (기본: "arbitrage")
        """
        self.vault_addr = vault_addr or os.getenv("VAULT_ADDR")
        self.vault_token = vault_token or os.getenv("VAULT_TOKEN")
        self.namespace = namespace or os.getenv("VAULT_NAMESPACE")
        self.mount_point = mount_point
        self.path = path
        
        # hvac는 optional dependency
        try:
            import hvac
            self._hvac = hvac
        except ImportError:
            raise ImportError(
                "hvac library is required for VaultSecretsProvider. "
                "Install it with: pip install hvac"
            )
        
        # Validate configuration
        if not self.vault_addr:
            raise ValueError("VAULT_ADDR must be set (environment variable or parameter)")
        if not self.vault_token:
            raise ValueError("VAULT_TOKEN must be set (environment variable or parameter)")
        
        # Initialize Vault client
        self.client = self._hvac.Client(
            url=self.vault_addr,
            token=self.vault_token,
            namespace=self.namespace,
        )
        
        # Verify connection
        if not self.client.is_authenticated():
            raise PermissionError(f"Vault authentication failed (addr: {self.vault_addr})")
    
    def _get_full_path(self) -> str:
        """Full KV v2 path 반환"""
        return f"{self.mount_point}/data/{self.path}"
    
    def _get_metadata_path(self) -> str:
        """Metadata path 반환"""
        return f"{self.mount_point}/metadata/{self.path}"
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Vault에서 secret 조회
        
        Args:
            key: Secret 키
            default: 기본값
        
        Returns:
            Secret 값 또는 default
        
        Raises:
            SecretNotFoundError: Secret을 찾을 수 없고 default가 None일 때
        """
        try:
            # Read KV v2 secret
            response = self.client.secrets.kv.v2.read_secret_version(
                path=self.path,
                mount_point=self.mount_point,
            )
            
            data = response.get("data", {}).get("data", {})
            value = data.get(key, default)
            
            if value is None and default is None:
                raise SecretNotFoundError(f"Secret '{key}' not found in Vault path '{self.path}'")
            
            return value
        
        except self._hvac.exceptions.InvalidPath:
            # Path doesn't exist
            if default is None:
                raise SecretNotFoundError(f"Vault path '{self.path}' does not exist")
            return default
        
        except Exception as e:
            raise RuntimeError(f"Failed to read secret from Vault: {e}")
    
    def set_secret(self, key: str, value: str) -> None:
        """
        Vault에 secret 저장
        
        Args:
            key: Secret 키
            value: Secret 값
        """
        try:
            # Read existing secrets first
            try:
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=self.path,
                    mount_point=self.mount_point,
                )
                existing_data = response.get("data", {}).get("data", {})
            except self._hvac.exceptions.InvalidPath:
                existing_data = {}
            
            # Merge with new secret
            updated_data = {**existing_data, key: value}
            
            # Write KV v2 secret
            self.client.secrets.kv.v2.create_or_update_secret(
                path=self.path,
                secret=updated_data,
                mount_point=self.mount_point,
            )
        
        except Exception as e:
            raise RuntimeError(f"Failed to write secret to Vault: {e}")
    
    def list_secrets(self) -> List[str]:
        """
        사용 가능한 secret 키 목록 반환
        
        Returns:
            Secret 키 목록
        """
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=self.path,
                mount_point=self.mount_point,
            )
            data = response.get("data", {}).get("data", {})
            return list(data.keys())
        
        except self._hvac.exceptions.InvalidPath:
            return []
        
        except Exception as e:
            raise RuntimeError(f"Failed to list secrets from Vault: {e}")
    
    def health(self) -> Dict[str, Any]:
        """
        Vault 연결 상태 확인
        
        Returns:
            상태 정보
        """
        try:
            is_authed = self.client.is_authenticated()
            health_status = self.client.sys.read_health_status(method="GET")
            
            status = "healthy" if is_authed else "unhealthy"
            
            return {
                "status": status,
                "provider_type": "vault",
                "details": {
                    "vault_addr": self.vault_addr,
                    "authenticated": is_authed,
                    "vault_initialized": health_status.get("initialized", False),
                    "vault_sealed": health_status.get("sealed", True),
                    "mount_point": self.mount_point,
                    "path": self.path,
                }
            }
        
        except Exception as e:
            return {
                "status": "unhealthy",
                "provider_type": "vault",
                "details": {
                    "error": str(e),
                    "vault_addr": self.vault_addr,
                }
            }
