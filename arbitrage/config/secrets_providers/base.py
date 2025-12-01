# -*- coding: utf-8 -*-
"""
D78-2: Secrets Provider Base Interface

모든 Secrets Provider가 구현해야 하는 추상 인터페이스.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class SecretNotFoundError(Exception):
    """Secret을 찾을 수 없을 때 발생하는 예외"""
    pass


class SecretsProviderBase(ABC):
    """
    Secrets Provider 추상 기본 클래스
    
    모든 provider는 이 인터페이스를 구현해야 함:
    - get_secret: 단일 secret 조회
    - set_secret: secret 저장 (선택적, read-only provider는 NotImplementedError)
    - list_secrets: 사용 가능한 secret 목록 (선택적)
    - health: provider 상태 확인
    """
    
    @abstractmethod
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Secret 값 조회
        
        Args:
            key: Secret 키 (예: "UPBIT_ACCESS_KEY")
            default: Secret이 없을 때 반환할 기본값
        
        Returns:
            Secret 값 또는 default
        
        Raises:
            SecretNotFoundError: Secret을 찾을 수 없고 default가 None일 때
        """
        pass
    
    @abstractmethod
    def set_secret(self, key: str, value: str) -> None:
        """
        Secret 저장
        
        Args:
            key: Secret 키
            value: Secret 값
        
        Raises:
            NotImplementedError: Read-only provider인 경우
            PermissionError: 권한이 없는 경우
        """
        pass
    
    @abstractmethod
    def list_secrets(self) -> List[str]:
        """
        사용 가능한 secret 키 목록 반환
        
        Returns:
            Secret 키 목록
        """
        pass
    
    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """
        Provider 상태 확인
        
        Returns:
            상태 정보 딕셔너리:
            {
                "status": "healthy" | "degraded" | "unhealthy",
                "provider_type": "env" | "vault" | "kms" | "local_fallback",
                "details": {...}
            }
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Provider 정보를 딕셔너리로 반환
        
        Returns:
            Provider 메타데이터
        """
        return {
            "type": self.__class__.__name__,
            "health": self.health(),
        }
