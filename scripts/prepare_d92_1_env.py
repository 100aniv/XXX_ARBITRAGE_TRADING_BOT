#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92-1: 사전 인프라 체크 스크립트

1h Top10 PAPER 실행 전 환경 정리 및 검증.

기능:
1. 가상환경 확인 (abt_bot_env)
2. Docker 컨테이너 상태 확인 (PostgreSQL, Redis)
3. 기존 Python 프로세스 정리
4. Redis/DB 상태 초기화 (선택적)

Usage:
    python scripts/prepare_d92_1_env.py
    python scripts/prepare_d92_1_env.py --skip-process-cleanup
    python scripts/prepare_d92_1_env.py --skip-redis-cleanup

Author: arbitrage-lite project
Date: 2025-12-12 (D92-1)
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def check_venv():
    """가상환경 확인"""
    logger.info("=" * 80)
    logger.info("[1/5] Checking Virtual Environment...")
    logger.info("=" * 80)
    
    venv_name = os.getenv("VIRTUAL_ENV", "")
    
    if not venv_name:
        logger.warning("⚠️  No virtual environment detected")
        logger.warning("   Expected: abt_bot_env")
        logger.warning("   Please activate: .\\abt_bot_env\\Scripts\\activate")
        return False
    
    if "abt_bot_env" in venv_name:
        logger.info(f"✅ Virtual environment active: {venv_name}")
        return True
    else:
        logger.warning(f"⚠️  Different venv active: {venv_name}")
        logger.warning("   Expected: abt_bot_env")
        return False


def check_docker():
    """Docker 컨테이너 상태 확인"""
    logger.info("=" * 80)
    logger.info("[2/5] Checking Docker Containers...")
    logger.info("=" * 80)
    
    try:
        # docker ps 실행
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            check=True,
        )
        
        containers = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        if not containers:
            logger.warning("⚠️  No running Docker containers found")
            logger.warning("   PostgreSQL and Redis may not be available")
            return False
        
        logger.info(f"Found {len(containers)} running containers:")
        
        postgres_found = False
        redis_found = False
        
        for container in containers:
            if '\t' in container:
                name, status = container.split('\t', 1)
                logger.info(f"  - {name}: {status}")
                
                if 'postgres' in name.lower():
                    postgres_found = True
                if 'redis' in name.lower():
                    redis_found = True
        
        if postgres_found and redis_found:
            logger.info("✅ PostgreSQL and Redis containers are running")
            return True
        else:
            if not postgres_found:
                logger.warning("⚠️  PostgreSQL container not found")
            if not redis_found:
                logger.warning("⚠️  Redis container not found")
            return False
    
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Docker command failed: {e}")
        return False
    except FileNotFoundError:
        logger.error("❌ Docker not found. Is Docker installed?")
        return False


def check_python_processes(skip_cleanup=False):
    """기존 Python 프로세스 확인 및 정리"""
    logger.info("=" * 80)
    logger.info("[3/5] Checking Python Processes...")
    logger.info("=" * 80)
    
    try:
        import psutil
    except ImportError:
        logger.warning("⚠️  psutil not installed, skipping process check")
        return True
    
    current_pid = os.getpid()
    python_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                if proc.info['pid'] != current_pid:
                    cmdline = proc.info.get('cmdline', [])
                    cmdline_str = ' '.join(cmdline) if cmdline else ''
                    
                    # arbitrage-lite 관련 프로세스만 필터링
                    if 'arbitrage-lite' in cmdline_str or 'run_d' in cmdline_str:
                        python_processes.append({
                            'pid': proc.info['pid'],
                            'cmdline': cmdline_str[:100],  # 처음 100자만
                        })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if not python_processes:
        logger.info("✅ No conflicting Python processes found")
        return True
    
    logger.warning(f"⚠️  Found {len(python_processes)} Python processes:")
    for proc_info in python_processes:
        logger.warning(f"  - PID {proc_info['pid']}: {proc_info['cmdline']}")
    
    if skip_cleanup:
        logger.warning("   Skipping cleanup (--skip-process-cleanup)")
        return False
    
    # 사용자 확인 없이 자동 정리 (완전 자동 모드)
    logger.info("Terminating conflicting processes...")
    for proc_info in python_processes:
        try:
            proc = psutil.Process(proc_info['pid'])
            proc.terminate()
            logger.info(f"  ✅ Terminated PID {proc_info['pid']}")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"  ⚠️  Could not terminate PID {proc_info['pid']}: {e}")
    
    # 종료 대기
    time.sleep(2)
    logger.info("✅ Process cleanup complete")
    return True


def check_redis_state(skip_cleanup=False):
    """Redis 상태 확인 및 초기화"""
    logger.info("=" * 80)
    logger.info("[4/5] Checking Redis State...")
    logger.info("=" * 80)
    
    try:
        import redis
    except ImportError:
        logger.warning("⚠️  redis-py not installed, skipping Redis check")
        return True
    
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        logger.info("✅ Redis connection OK")
        
        # Redis 키 개수 확인
        keys_count = r.dbsize()
        logger.info(f"   Current keys: {keys_count}")
        
        if keys_count > 0 and not skip_cleanup:
            logger.info("   Flushing Redis DB...")
            r.flushdb()
            logger.info("   ✅ Redis DB flushed")
        
        return True
    
    except redis.ConnectionError:
        logger.warning("⚠️  Could not connect to Redis")
        return False
    except Exception as e:
        logger.error(f"❌ Redis error: {e}")
        return False


def check_db_state():
    """PostgreSQL 상태 확인"""
    logger.info("=" * 80)
    logger.info("[5/5] Checking PostgreSQL State...")
    logger.info("=" * 80)
    
    # DB 연결은 프로젝트의 DB 설정에 따라 다를 수 있음
    # 여기서는 간단히 Docker 컨테이너 확인으로 대체
    logger.info("✅ PostgreSQL check delegated to Docker container check")
    return True


def main():
    """메인 실행"""
    parser = argparse.ArgumentParser(description="D92-1 Environment Preparation")
    parser.add_argument(
        "--skip-process-cleanup",
        action="store_true",
        help="Skip Python process cleanup",
    )
    parser.add_argument(
        "--skip-redis-cleanup",
        action="store_true",
        help="Skip Redis state cleanup",
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("D92-1: Environment Preparation")
    logger.info("=" * 80)
    
    checks = []
    
    # 1. 가상환경
    checks.append(("Virtual Environment", check_venv()))
    
    # 2. Docker
    checks.append(("Docker Containers", check_docker()))
    
    # 3. Python 프로세스
    checks.append(("Python Processes", check_python_processes(args.skip_process_cleanup)))
    
    # 4. Redis
    checks.append(("Redis State", check_redis_state(args.skip_redis_cleanup)))
    
    # 5. PostgreSQL
    checks.append(("PostgreSQL State", check_db_state()))
    
    # 결과 요약
    logger.info("=" * 80)
    logger.info("Environment Check Summary")
    logger.info("=" * 80)
    
    all_passed = True
    for name, passed in checks:
        status = "✅ PASS" if passed else "⚠️  WARNING"
        logger.info(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    logger.info("=" * 80)
    
    if all_passed:
        logger.info("✅ All checks passed - environment is ready")
        logger.info("   You can now run: python scripts/run_d92_1_topn_longrun.py")
        return 0
    else:
        logger.warning("⚠️  Some checks failed - please review warnings above")
        logger.warning("   You may proceed with caution")
        return 1


if __name__ == "__main__":
    sys.exit(main())
