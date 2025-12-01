# -*- coding: utf-8 -*-
"""
D78-2: Environment Variables Secrets Provider

환경변수에서 secrets를 읽는 기본 provider.
D78-0, D78-1과 완전히 호환됨.
"""

import os
from typing import Optional, Dict, Any, List
from .base import SecretsProviderBase, SecretNotFoundError


class EnvSecretsProvider(SecretsProviderBase):
    """
    환경변수 기반 Secrets Provider
    
    - .env 파일 또는 OS 환경변수에서 secrets 읽기
    - 기본 provider (backward compatibility)
    - Read-only (set_secret은 지원하지 않음)
    """
    
    def __init__(self):
        """Initialize EnvSecretsProvider"""
        pass
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        환경변수에서 secret 조회
        
        Args:
            key: 환경변수 이름
            default: 기본값
        
        Returns:
            환경변수 값 또는 default
        """
        value = os.getenv(key, default)
        if value is None and default is None:
            raise SecretNotFoundError(f"Environment variable '{key}' not found and no default provided")
        return value
    
    def set_secret(self, key: str, value: str) -> None:
        """
        환경변수 설정 (runtime only, .env 파일에는 저장하지 않음)
        
        Args:
            key: 환경변수 이름
            value: 값
        """
        os.environ[key] = value
    
    def list_secrets(self) -> List[str]:
        """
        현재 환경변수 목록 반환
        
        Returns:
            환경변수 키 목록
        """
        # 모든 환경변수가 secret은 아니지만, 일단 전체 목록 반환
        return list(os.environ.keys())
    
    def health(self) -> Dict[str, Any]:
        """
        Provider 상태 확인
        
        Returns:
            항상 healthy (환경변수는 항상 사용 가능)
        """
        return {
            "status": "healthy",
            "provider_type": "env",
            "details": {
                "env_count": len(os.environ),
            }
        }
