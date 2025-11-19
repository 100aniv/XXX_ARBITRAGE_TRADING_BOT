# -*- coding: utf-8 -*-
"""
D63: Infrastructure Cleanup Script

Docker Redis/Postgres 환경 초기화 스크립트.
테스트/롱런 실행 전에 환경을 깨끗하게 정리한다.
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_docker_status():
    """Docker 컨테이너 상태 확인"""
    logger.info("[CLEANUP] Checking Docker container status...")
    
    try:
        result = subprocess.run(
            ["docker", "ps", "-a"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            check=True
        )
        logger.info("[CLEANUP] Docker containers:")
        if result.stdout:
            for line in result.stdout.split('\n')[:10]:  # 처음 10줄만
                if line.strip():
                    logger.info(f"  {line}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"[CLEANUP] Docker command failed: {e}")
        return False
    except FileNotFoundError:
        logger.warning("[CLEANUP] Docker not found in PATH")
        return False


def start_redis_container(container_name="arbitrage-redis"):
    """Redis 컨테이너 시작 (arbitrage 전용: 포트 6380)"""
    logger.info(f"[CLEANUP] Starting Redis container: {container_name}")
    
    try:
        # 컨테이너 상태 확인
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            check=True
        )
        
        status = result.stdout.strip()
        
        if "Up" in status:
            logger.info(f"[CLEANUP] Redis container already running")
            return True
        elif status:
            # 컨테이너가 존재하지만 정지 상태
            subprocess.run(["docker", "start", container_name], check=True)
            logger.info(f"[CLEANUP] Started Redis container")
            return True
        else:
            logger.warning(f"[CLEANUP] Redis container '{container_name}' not found")
            logger.info("[CLEANUP] Please create Redis container first:")
            logger.info(f"  docker run -d --name {container_name} -p 6380:6379 redis:latest")
            return False
    
    except subprocess.CalledProcessError as e:
        logger.error(f"[CLEANUP] Failed to start Redis: {e}")
        return False


def start_postgres_container(container_name="arbitrage-postgres"):
    """Postgres 컨테이너 시작 (arbitrage 전용: 포트 5432)"""
    logger.info(f"[CLEANUP] Starting Postgres container: {container_name}")
    
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            check=True
        )
        
        status = result.stdout.strip()
        
        if "Up" in status:
            logger.info(f"[CLEANUP] Postgres container already running")
            return True
        elif status:
            subprocess.run(["docker", "start", container_name], check=True)
            logger.info(f"[CLEANUP] Started Postgres container")
            return True
        else:
            logger.warning(f"[CLEANUP] Postgres container '{container_name}' not found")
            logger.info("[CLEANUP] Please create Postgres container first:")
            logger.info(f"  docker run -d --name {container_name} -p 5432:5432 -e POSTGRES_PASSWORD=arbitrage postgres:latest")
            return False
    
    except subprocess.CalledProcessError as e:
        logger.error(f"[CLEANUP] Failed to start Postgres: {e}")
        return False


def flush_redis(host="localhost", port=6380):
    """Redis FLUSHALL 실행 (arbitrage 전용: 포트 6380)"""
    logger.info(f"[CLEANUP] Flushing Redis at {host}:{port}...")
    
    try:
        import redis
        
        r = redis.Redis(host=host, port=port, decode_responses=True)
        r.flushall()
        logger.info("[CLEANUP] Redis FLUSHALL completed")
        return True
    
    except ImportError:
        logger.warning("[CLEANUP] redis-py not installed, trying redis-cli...")
        try:
            subprocess.run(["redis-cli", "FLUSHALL"], check=True)
            logger.info("[CLEANUP] Redis FLUSHALL completed via redis-cli")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"[CLEANUP] Failed to flush Redis: {e}")
            return False
    
    except Exception as e:
        logger.error(f"[CLEANUP] Failed to flush Redis: {e}")
        return False


def backup_logs(log_dir="logs", backup_dir="logs/backup"):
    """로그 파일 백업"""
    logger.info(f"[CLEANUP] Backing up logs from {log_dir} to {backup_dir}...")
    
    log_path = Path(log_dir)
    backup_path = Path(backup_dir)
    
    if not log_path.exists():
        logger.info(f"[CLEANUP] Log directory does not exist: {log_dir}")
        return True
    
    # 백업 디렉토리 생성
    backup_path.mkdir(parents=True, exist_ok=True)
    
    # 타임스탬프
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 로그 파일 백업
    backed_up = 0
    for log_file in log_path.glob("*.log"):
        if log_file.is_file():
            backup_file = backup_path / f"{log_file.stem}_{timestamp}{log_file.suffix}"
            shutil.copy2(log_file, backup_file)
            backed_up += 1
    
    logger.info(f"[CLEANUP] Backed up {backed_up} log files")
    return True


def clear_logs(log_dir="logs"):
    """로그 파일 초기화"""
    logger.info(f"[CLEANUP] Clearing logs in {log_dir}...")
    
    log_path = Path(log_dir)
    
    if not log_path.exists():
        logger.info(f"[CLEANUP] Log directory does not exist: {log_dir}")
        return True
    
    # 로그 파일 삭제
    cleared = 0
    for log_file in log_path.glob("*.log"):
        if log_file.is_file():
            log_file.unlink()
            cleared += 1
    
    logger.info(f"[CLEANUP] Cleared {cleared} log files")
    return True


def check_venv():
    """가상환경 활성화 여부 확인"""
    logger.info("[CLEANUP] Checking virtual environment...")
    
    venv_active = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if venv_active:
        logger.info(f"[CLEANUP] Virtual environment active: {sys.prefix}")
        return True
    else:
        logger.warning("[CLEANUP] Virtual environment NOT active")
        logger.info("[CLEANUP] Please activate venv:")
        logger.info("  .\\trading_bot_env\\Scripts\\activate  (Windows)")
        logger.info("  source trading_bot_env/bin/activate  (Linux/Mac)")
        return False


def main():
    """메인 실행"""
    parser = argparse.ArgumentParser(description="Infrastructure cleanup script")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker operations")
    parser.add_argument("--skip-redis", action="store_true", help="Skip Redis flush")
    parser.add_argument("--skip-logs", action="store_true", help="Skip log backup/clear")
    parser.add_argument("--redis-host", default="localhost", help="Redis host")
    parser.add_argument("--redis-port", type=int, default=6380, help="Redis port (arbitrage: 6380)")
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("D63 Infrastructure Cleanup")
    logger.info("=" * 70)
    
    success = True
    
    # 1. Virtual environment 확인
    check_venv()
    
    # 2. Docker 상태 확인 및 컨테이너 시작
    if not args.skip_docker:
        if check_docker_status():
            start_redis_container()
            start_postgres_container()
        else:
            logger.warning("[CLEANUP] Skipping Docker operations (Docker not available)")
    
    # 3. Redis FLUSHALL
    if not args.skip_redis:
        if not flush_redis(host=args.redis_host, port=args.redis_port):
            success = False
    
    # 4. 로그 백업 및 초기화
    if not args.skip_logs:
        backup_logs()
        clear_logs()
    
    logger.info("=" * 70)
    if success:
        logger.info("[CLEANUP] ✅ Cleanup completed successfully")
    else:
        logger.warning("[CLEANUP] ⚠️ Cleanup completed with warnings")
    logger.info("=" * 70)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
