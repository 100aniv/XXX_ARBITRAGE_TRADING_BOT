# -*- coding: utf-8 -*-
"""
D78-2: Local Fallback Secrets Provider

로컬 파일에서 secrets를 읽는 fallback provider.
개발 환경에서만 사용 (production에서는 사용 금지).
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from .base import SecretsProviderBase, SecretNotFoundError


class LocalFallbackProvider(SecretsProviderBase):
    """
    로컬 파일 기반 Secrets Provider
    
    - JSON 파일에서 secrets 읽기/쓰기
    - 개발 환경 전용 (local_dev only)
    - Production 사용 금지!
    """
    
    def __init__(self, secrets_file: Optional[Path] = None):
        """
        Initialize LocalFallbackProvider
        
        Args:
            secrets_file: Secrets JSON 파일 경로 (기본: .secrets.local.json)
        """
        if secrets_file is None:
            # 프로젝트 루트/.secrets.local.json
            secrets_file = Path.cwd() / ".secrets.local.json"
        
        self.secrets_file = Path(secrets_file)
        self._secrets: Dict[str, str] = {}
        self._load_secrets()
    
    def _load_secrets(self) -> None:
        """파일에서 secrets 로드"""
        if self.secrets_file.exists():
            try:
                with open(self.secrets_file, "r", encoding="utf-8") as f:
                    self._secrets = json.load(f)
            except Exception as e:
                print(f"[Warning] Failed to load secrets from {self.secrets_file}: {e}")
                self._secrets = {}
        else:
            self._secrets = {}
    
    def _save_secrets(self) -> None:
        """파일에 secrets 저장"""
        try:
            with open(self.secrets_file, "w", encoding="utf-8") as f:
                json.dump(self._secrets, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise PermissionError(f"Failed to save secrets to {self.secrets_file}: {e}")
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        로컬 파일에서 secret 조회
        
        Args:
            key: Secret 키
            default: 기본값
        
        Returns:
            Secret 값 또는 default
        
        Raises:
            SecretNotFoundError: Secret을 찾을 수 없고 default가 None일 때
        """
        value = self._secrets.get(key, default)
        if value is None and default is None:
            raise SecretNotFoundError(f"Secret '{key}' not found in {self.secrets_file} and no default provided")
        return value
    
    def set_secret(self, key: str, value: str) -> None:
        """
        Secret 저장
        
        Args:
            key: Secret 키
            value: Secret 값
        """
        self._secrets[key] = value
        self._save_secrets()
    
    def list_secrets(self) -> List[str]:
        """
        사용 가능한 secret 키 목록 반환
        
        Returns:
            Secret 키 목록
        """
        return list(self._secrets.keys())
    
    def health(self) -> Dict[str, Any]:
        """
        Provider 상태 확인
        
        Returns:
            파일 접근 가능 여부
        """
        status = "healthy" if self.secrets_file.exists() else "degraded"
        
        return {
            "status": status,
            "provider_type": "local_fallback",
            "details": {
                "secrets_file": str(self.secrets_file),
                "file_exists": self.secrets_file.exists(),
                "secret_count": len(self._secrets),
            }
        }
