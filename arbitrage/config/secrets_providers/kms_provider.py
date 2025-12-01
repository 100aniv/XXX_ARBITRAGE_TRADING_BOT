# -*- coding: utf-8 -*-
"""
D78-2: AWS Secrets Manager (KMS) Secrets Provider

AWS Secrets Manager를 사용한 cloud-native secrets provider.
"""

import os
import json
from typing import Optional, Dict, Any, List
from .base import SecretsProviderBase, SecretNotFoundError


class KMSSecretsProvider(SecretsProviderBase):
    """
    AWS Secrets Manager Secrets Provider
    
    - AWS Secrets Manager 사용
    - IAM 인증 (boto3 credentials)
    - Cloud production 환경 권장
    
    Environment Variables:
        AWS_REGION: AWS 리전 (예: ap-northeast-2)
        AWS_ACCESS_KEY_ID: AWS access key (선택적, IAM role 권장)
        AWS_SECRET_ACCESS_KEY: AWS secret key (선택적)
        AWS_SECRET_NAME: Secrets Manager secret 이름 (기본: "arbitrage/secrets")
    """
    
    def __init__(
        self,
        region_name: Optional[str] = None,
        secret_name: str = "arbitrage/secrets",
    ):
        """
        Initialize KMSSecretsProvider
        
        Args:
            region_name: AWS 리전 (기본: 환경변수 AWS_REGION)
            secret_name: Secrets Manager secret 이름
        """
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-northeast-2")
        self.secret_name = os.getenv("AWS_SECRET_NAME", secret_name)
        
        # boto3는 optional dependency
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            self._boto3 = boto3
            self._ClientError = ClientError
            self._NoCredentialsError = NoCredentialsError
        except ImportError:
            raise ImportError(
                "boto3 library is required for KMSSecretsProvider. "
                "Install it with: pip install boto3"
            )
        
        # Initialize Secrets Manager client
        try:
            self.client = self._boto3.client(
                "secretsmanager",
                region_name=self.region_name,
            )
        except self._NoCredentialsError:
            raise PermissionError(
                "AWS credentials not found. "
                "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, "
                "or use IAM role."
            )
        
        # Cache for secrets (to reduce API calls)
        self._cache: Optional[Dict[str, str]] = None
    
    def _load_all_secrets(self, force_refresh: bool = False) -> Dict[str, str]:
        """
        모든 secrets를 한 번에 로드 (caching)
        
        Args:
            force_refresh: 캐시 무시하고 다시 로드
        
        Returns:
            Secret 키-값 딕셔너리
        """
        if self._cache is not None and not force_refresh:
            return self._cache
        
        try:
            response = self.client.get_secret_value(SecretId=self.secret_name)
            
            # SecretString은 JSON 형식이어야 함
            if "SecretString" in response:
                self._cache = json.loads(response["SecretString"])
            else:
                # Binary secret (not supported)
                raise ValueError(f"Binary secrets not supported (secret: {self.secret_name})")
            
            return self._cache
        
        except self._ClientError as e:
            error_code = e.response["Error"]["Code"]
            
            if error_code == "ResourceNotFoundException":
                # Secret doesn't exist yet
                self._cache = {}
                return self._cache
            else:
                raise RuntimeError(f"Failed to load secrets from AWS Secrets Manager: {e}")
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        AWS Secrets Manager에서 secret 조회
        
        Args:
            key: Secret 키
            default: 기본값
        
        Returns:
            Secret 값 또는 default
        
        Raises:
            SecretNotFoundError: Secret을 찾을 수 없고 default가 None일 때
        """
        secrets = self._load_all_secrets()
        value = secrets.get(key, default)
        
        if value is None and default is None:
            raise SecretNotFoundError(
                f"Secret '{key}' not found in AWS Secrets Manager (secret: {self.secret_name})"
            )
        
        return value
    
    def set_secret(self, key: str, value: str) -> None:
        """
        AWS Secrets Manager에 secret 저장
        
        Args:
            key: Secret 키
            value: Secret 값
        """
        try:
            # Load existing secrets
            secrets = self._load_all_secrets(force_refresh=True)
            
            # Update with new value
            secrets[key] = value
            
            # Save to AWS Secrets Manager
            secret_string = json.dumps(secrets, ensure_ascii=False)
            
            try:
                # Try to update existing secret
                self.client.update_secret(
                    SecretId=self.secret_name,
                    SecretString=secret_string,
                )
            except self._ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    # Create new secret
                    self.client.create_secret(
                        Name=self.secret_name,
                        SecretString=secret_string,
                        Description="Arbitrage Bot Secrets (D78-2)",
                    )
                else:
                    raise
            
            # Invalidate cache
            self._cache = None
        
        except Exception as e:
            raise RuntimeError(f"Failed to write secret to AWS Secrets Manager: {e}")
    
    def list_secrets(self) -> List[str]:
        """
        사용 가능한 secret 키 목록 반환
        
        Returns:
            Secret 키 목록
        """
        secrets = self._load_all_secrets()
        return list(secrets.keys())
    
    def health(self) -> Dict[str, Any]:
        """
        AWS Secrets Manager 연결 상태 확인
        
        Returns:
            상태 정보
        """
        try:
            # Try to describe secret (doesn't retrieve value, cheaper)
            self.client.describe_secret(SecretId=self.secret_name)
            
            return {
                "status": "healthy",
                "provider_type": "kms",
                "details": {
                    "region": self.region_name,
                    "secret_name": self.secret_name,
                    "secret_exists": True,
                }
            }
        
        except self._ClientError as e:
            error_code = e.response["Error"]["Code"]
            
            if error_code == "ResourceNotFoundException":
                # Secret doesn't exist (degraded but not critical)
                return {
                    "status": "degraded",
                    "provider_type": "kms",
                    "details": {
                        "region": self.region_name,
                        "secret_name": self.secret_name,
                        "secret_exists": False,
                        "message": "Secret will be created on first write",
                    }
                }
            else:
                return {
                    "status": "unhealthy",
                    "provider_type": "kms",
                    "details": {
                        "region": self.region_name,
                        "secret_name": self.secret_name,
                        "error": str(e),
                    }
                }
        
        except Exception as e:
            return {
                "status": "unhealthy",
                "provider_type": "kms",
                "details": {
                    "error": str(e),
                }
            }
