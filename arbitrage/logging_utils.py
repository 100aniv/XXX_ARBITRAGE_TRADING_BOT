#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logging Utilities (PHASE D11)
=============================

중앙 로깅 시스템. 모든 모듈에서 공통으로 사용할 로거를 제공한다.

특징:
- 콘솔 + 파일 로그 지원
- 일 단위 로그 로테이션
- 구조화된 포맷 (timestamp, level, mode, component, message)
- 선택적 correlation_id 지원
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional, Dict, Any

# 로그 디렉토리
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 로그 포맷
LOG_FORMAT = "%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s"
LOG_FORMAT_DETAILED = "%(asctime)s [%(levelname)-8s] [%(name)s] [%(funcName)s:%(lineno)d] %(message)s"

# 로거 저장소
_loggers: Dict[str, logging.Logger] = {}


def get_logger(
    name: str,
    component: Optional[str] = None,
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    detailed: bool = False
) -> logging.Logger:
    """
    공통 로거 반환
    
    Args:
        name: 로거 이름 (보통 __name__)
        component: 컴포넌트 이름 (선택, 로그 파일명에 사용)
        log_file: 로그 파일명 (없으면 component 기반으로 자동 생성)
        level: 로깅 레벨 (기본: INFO)
        detailed: 상세 포맷 사용 여부 (함수명, 라인 번호 포함)
    
    Returns:
        logging.Logger 인스턴스
    """
    # 캐시 확인
    cache_key = f"{name}:{component}:{log_file}"
    if cache_key in _loggers:
        return _loggers[cache_key]
    
    # 새 로거 생성
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 기존 핸들러 제거 (중복 방지)
    logger.handlers.clear()
    
    # 포맷 선택
    fmt = LOG_FORMAT_DETAILED if detailed else LOG_FORMAT
    formatter = logging.Formatter(fmt)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 (선택)
    if log_file or component:
        file_name = log_file or f"{component}.log"
        log_path = LOG_DIR / file_name
        
        # 일 단위 로테이션 (자정마다 새 파일)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(log_path),
            when="midnight",
            interval=1,
            backupCount=7,  # 7일치 보관
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # 캐시 저장
    _loggers[cache_key] = logger
    
    return logger


def get_live_loop_logger() -> logging.Logger:
    """메인 루프 로거"""
    return get_logger("arbitrage.live_loop", component="live_loop", level=logging.INFO)


def get_health_logger() -> logging.Logger:
    """헬스 체크 로거"""
    return get_logger("arbitrage.health", component="health", level=logging.INFO)


def get_safety_logger() -> logging.Logger:
    """안전 검증 로거"""
    return get_logger("arbitrage.safety", component="safety", level=logging.INFO)


def get_watchdog_logger() -> logging.Logger:
    """워치독 로거"""
    return get_logger("arbitrage.watchdog", component="watchdog", level=logging.INFO)


def get_sys_monitor_logger() -> logging.Logger:
    """시스템 모니터 로거"""
    return get_logger("arbitrage.sys_monitor", component="sys_monitor", level=logging.INFO)


def reset_loggers() -> None:
    """모든 로거 리셋 (테스트용)"""
    global _loggers
    for logger in _loggers.values():
        logger.handlers.clear()
    _loggers.clear()
