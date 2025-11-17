#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Health Monitoring Module (PHASE D – MODULE D2)
===============================================

시스템 헬스 체크 및 모니터링.

특징:
- Redis 연결 상태 확인
- PostgreSQL 연결 상태 확인
- 헬스 상태 집계
"""

import logging
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """헬스 상태 정보"""
    component: str          # 컴포넌트 이름 (redis, postgres 등)
    status: str             # 상태 (OK, WARN, ERROR, SKIP, DISABLED)
    details: str            # 상세 정보
    checked_at: datetime    # 확인 시간


def check_redis(config: dict) -> HealthStatus:
    """Redis 연결 상태 확인
    
    Args:
        config: 전체 설정 딕셔너리
    
    Returns:
        HealthStatus 객체
    """
    redis_cfg = config.get("redis", {})
    enabled = redis_cfg.get("enabled", False)
    url = redis_cfg.get("url", "redis://localhost:6379/0")
    
    checked_at = datetime.now(timezone.utc)
    
    if not enabled:
        return HealthStatus(
            component="REDIS",
            status="DISABLED",
            details="Redis disabled in config",
            checked_at=checked_at
        )
    
    try:
        import redis
        client = redis.from_url(url, decode_responses=True)
        client.ping()
        client.close()
        
        return HealthStatus(
            component="REDIS",
            status="OK",
            details=f"Connected to {url}",
            checked_at=checked_at
        )
    except ImportError:
        return HealthStatus(
            component="REDIS",
            status="ERROR",
            details="redis-py not installed (pip install redis)",
            checked_at=checked_at
        )
    except Exception as e:
        return HealthStatus(
            component="REDIS",
            status="ERROR",
            details=f"Connection failed: {str(e)}",
            checked_at=checked_at
        )


def check_postgres(config: dict) -> HealthStatus:
    """PostgreSQL 연결 상태 확인
    
    Args:
        config: 전체 설정 딕셔너리
    
    Returns:
        HealthStatus 객체
    """
    storage_cfg = config.get("storage", {})
    backend = storage_cfg.get("backend", "csv")
    postgres_cfg = storage_cfg.get("postgres", {})
    dsn = postgres_cfg.get("dsn", "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage")
    
    checked_at = datetime.now(timezone.utc)
    
    if backend != "postgres":
        return HealthStatus(
            component="POSTGRES",
            status="SKIP",
            details=f"Backend is '{backend}', not postgres",
            checked_at=checked_at
        )
    
    try:
        import psycopg2
        conn = psycopg2.connect(dsn)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        
        return HealthStatus(
            component="POSTGRES",
            status="OK",
            details=f"Connected to {dsn.split('@')[1] if '@' in dsn else dsn}",
            checked_at=checked_at
        )
    except ImportError:
        return HealthStatus(
            component="POSTGRES",
            status="ERROR",
            details="psycopg2 not installed (pip install psycopg2-binary)",
            checked_at=checked_at
        )
    except Exception as e:
        return HealthStatus(
            component="POSTGRES",
            status="ERROR",
            details=f"Connection failed: {str(e)}",
            checked_at=checked_at
        )


def check_csv_storage(config: dict) -> HealthStatus:
    """CSV 저장소 상태 확인
    
    Args:
        config: 전체 설정 딕셔너리
    
    Returns:
        HealthStatus 객체
    """
    from pathlib import Path
    
    storage_cfg = config.get("storage", {})
    backend = storage_cfg.get("backend", "csv")
    data_dir = config.get("data_dir", "data")
    
    checked_at = datetime.now(timezone.utc)
    
    if backend != "csv":
        return HealthStatus(
            component="CSV",
            status="SKIP",
            details=f"Backend is '{backend}', not csv",
            checked_at=checked_at
        )
    
    try:
        path = Path(data_dir)
        path.mkdir(parents=True, exist_ok=True)
        
        return HealthStatus(
            component="CSV",
            status="OK",
            details=f"CSV storage at {data_dir}",
            checked_at=checked_at
        )
    except Exception as e:
        return HealthStatus(
            component="CSV",
            status="ERROR",
            details=f"Failed to access {data_dir}: {str(e)}",
            checked_at=checked_at
        )


def aggregate_status(statuses: List[HealthStatus]) -> str:
    """헬스 상태 집계
    
    Args:
        statuses: HealthStatus 리스트
    
    Returns:
        집계된 상태 ("OK", "WARN", "ERROR")
    """
    if not statuses:
        return "OK"
    
    # ERROR가 있으면 ERROR
    if any(s.status == "ERROR" for s in statuses):
        return "ERROR"
    
    # WARN이 있으면 WARN
    if any(s.status == "WARN" for s in statuses):
        return "WARN"
    
    # 나머지는 OK
    return "OK"


def format_health_report(statuses: List[HealthStatus]) -> str:
    """헬스 리포트 포맷팅
    
    Args:
        statuses: HealthStatus 리스트
    
    Returns:
        포맷된 리포트 문자열
    """
    lines = []
    lines.append("─" * 60)
    lines.append("Arbitrage-Lite: Health Check Report")
    lines.append("─" * 60)
    lines.append("")
    
    for status in statuses:
        # 상태별 기호
        symbol = {
            "OK": "✅",
            "WARN": "⚠️ ",
            "ERROR": "❌",
            "SKIP": "⊘ ",
            "DISABLED": "⊘ "
        }.get(status.status, "?")
        
        # 상태별 색상 (ANSI 코드)
        color_code = {
            "OK": "\033[92m",        # 녹색
            "WARN": "\033[93m",      # 노랑
            "ERROR": "\033[91m",     # 빨강
            "SKIP": "\033[94m",      # 파랑
            "DISABLED": "\033[94m"   # 파랑
        }.get(status.status, "")
        reset_code = "\033[0m"
        
        lines.append(
            f"[{status.component:10s}] {symbol} {color_code}{status.status:8s}{reset_code} {status.details}"
        )
    
    lines.append("")
    overall = aggregate_status(statuses)
    overall_symbol = {
        "OK": "✅",
        "WARN": "⚠️ ",
        "ERROR": "❌"
    }.get(overall, "?")
    
    overall_color = {
        "OK": "\033[92m",
        "WARN": "\033[93m",
        "ERROR": "\033[91m"
    }.get(overall, "")
    
    lines.append(
        f"Overall:       {overall_symbol} {overall_color}{overall}{reset_code}"
    )
    lines.append("─" * 60)
    
    return "\n".join(lines)
