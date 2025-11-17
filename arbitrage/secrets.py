#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Secrets & Environment Configuration (PHASE D13)
===============================================

.env 파일 기반 시크릿 관리 및 환경 변수 로딩.

특징:
- python-dotenv 기반 .env 파일 지원
- 환경 변수 우선순위 (환경 변수 > .env 파일)
- 필수 키 검증 (missing key → fail-closed)
- 타입 변환 (str → int, bool 등)
- 상세한 에러 로깅
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# python-dotenv 선택적 임포트
try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False
    logger.warning("[Secrets] python-dotenv not installed, using environment variables only")


class SecretsManager:
    """시크릿 및 환경 변수 관리자"""
    
    # 필수 키 목록
    REQUIRED_KEYS = {
        'UPBIT_API_KEY': str,
        'UPBIT_API_SECRET': str,
        'BINANCE_API_KEY': str,
        'BINANCE_API_SECRET': str,
    }
    
    # 선택적 키 목록
    OPTIONAL_KEYS = {
        'TELEGRAM_BOT_TOKEN': str,
        'TELEGRAM_CHAT_ID': str,
        'LIVE_TRADING': lambda x: x.lower() in ('1', 'true', 'yes'),
        'LOG_LEVEL': str,
        'ENVIRONMENT': str,  # dev, staging, prod
    }
    
    def __init__(self, env_file: Optional[str] = None, fail_on_missing: bool = True):
        """
        Args:
            env_file: .env 파일 경로 (기본: .env)
            fail_on_missing: 필수 키 누락 시 예외 발생 여부
        """
        self.env_file = env_file or ".env"
        self.fail_on_missing = fail_on_missing
        self.secrets: Dict[str, Any] = {}
        self.missing_keys: list = []
        
        # .env 파일 로드
        self._load_env_file()
        
        # 환경 변수 로드
        self._load_environment()
        
        # 필수 키 검증
        self._validate_required_keys()
    
    def _load_env_file(self) -> None:
        """
        .env 파일 로드
        
        python-dotenv가 설치되어 있으면 사용, 없으면 수동 파싱
        """
        if not Path(self.env_file).exists():
            logger.warning(f"[Secrets] .env file not found: {self.env_file}")
            return
        
        if HAS_DOTENV:
            load_dotenv(self.env_file)
            logger.info(f"[Secrets] Loaded .env file: {self.env_file}")
        else:
            # 수동 파싱 (python-dotenv 없을 때)
            self._parse_env_file_manual()
    
    def _parse_env_file_manual(self) -> None:
        """
        .env 파일 수동 파싱
        
        python-dotenv 없을 때 대체 방법
        """
        try:
            with open(self.env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    # 주석 및 빈 줄 스킵
                    if not line or line.startswith('#'):
                        continue
                    
                    # KEY=VALUE 파싱
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        
                        # 환경 변수에 설정 (기존 값 유지)
                        if key not in os.environ:
                            os.environ[key] = value
            
            logger.info(f"[Secrets] Manually parsed .env file: {self.env_file}")
        
        except Exception as e:
            logger.error(f"[Secrets] Failed to parse .env file: {e}")
    
    def _load_environment(self) -> None:
        """환경 변수에서 필수 및 선택적 키 로드"""
        # 필수 키
        for key, key_type in self.REQUIRED_KEYS.items():
            value = os.environ.get(key)
            if value is not None:
                self.secrets[key] = value
            else:
                self.missing_keys.append(key)
        
        # 선택적 키
        for key, converter in self.OPTIONAL_KEYS.items():
            value = os.environ.get(key)
            if value is not None:
                try:
                    self.secrets[key] = converter(value)
                except Exception as e:
                    logger.warning(f"[Secrets] Failed to convert {key}: {e}")
    
    def _validate_required_keys(self) -> None:
        """필수 키 검증"""
        if self.missing_keys:
            msg = f"Missing required environment variables: {', '.join(self.missing_keys)}"
            logger.error(f"[Secrets] {msg}")
            
            if self.fail_on_missing:
                raise ValueError(msg)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        시크릿 값 조회
        
        Args:
            key: 키 이름
            default: 기본값
        
        Returns:
            값 또는 기본값
        """
        return self.secrets.get(key, default)
    
    def get_required(self, key: str) -> Any:
        """
        필수 시크릿 값 조회
        
        Args:
            key: 키 이름
        
        Returns:
            값
        
        Raises:
            KeyError: 키가 없으면 예외
        """
        if key not in self.secrets:
            raise KeyError(f"Required secret not found: {key}")
        return self.secrets[key]
    
    def get_all(self) -> Dict[str, Any]:
        """모든 시크릿 반환 (민감한 정보 마스킹)"""
        masked = {}
        for key, value in self.secrets.items():
            if key in ('UPBIT_API_SECRET', 'BINANCE_API_SECRET', 'TELEGRAM_BOT_TOKEN'):
                masked[key] = f"***{str(value)[-4:]}" if value else "***"
            else:
                masked[key] = value
        return masked
    
    def is_live_mode(self) -> bool:
        """라이브 모드 여부"""
        return self.get('LIVE_TRADING', False)
    
    def get_environment(self) -> str:
        """환경 (dev, staging, prod)"""
        return self.get('ENVIRONMENT', 'dev')
    
    def get_log_level(self) -> str:
        """로그 레벨"""
        return self.get('LOG_LEVEL', 'INFO')


# 글로벌 시크릿 매니저 인스턴스
_secrets_manager: Optional[SecretsManager] = None


def init_secrets(env_file: str = ".env", fail_on_missing: bool = True) -> SecretsManager:
    """
    글로벌 시크릿 매니저 초기화
    
    Args:
        env_file: .env 파일 경로
        fail_on_missing: 필수 키 누락 시 예외 발생 여부
    
    Returns:
        SecretsManager 인스턴스
    """
    global _secrets_manager
    _secrets_manager = SecretsManager(env_file, fail_on_missing)
    return _secrets_manager


def get_secrets() -> SecretsManager:
    """글로벌 시크릿 매니저 조회"""
    if _secrets_manager is None:
        raise RuntimeError("Secrets manager not initialized. Call init_secrets() first.")
    return _secrets_manager
