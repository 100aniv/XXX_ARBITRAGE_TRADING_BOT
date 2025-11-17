#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D18 Docker Paper/Shadow Mode Smoke Test
========================================

Docker 스택이 실행 중일 때 Paper/Shadow 모드 검증.

검사 항목:
1. /health 엔드포인트 확인
2. Redis 연결 확인
3. Paper trader 로그 확인
4. 시나리오 실행 완료 확인

사용법:
    python scripts/docker_paper_smoke.py
"""

import sys
import time
import subprocess
import json
import logging
from pathlib import Path
from typing import Tuple, Dict, Any

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def check_docker_running() -> bool:
    """Docker가 실행 중인지 확인"""
    try:
        result = subprocess.run(
            ['docker', 'ps'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Docker check failed: {e}")
        return False


def check_container_status(container_name: str) -> Tuple[bool, str]:
    """컨테이너 상태 확인"""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Status}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            status = result.stdout.strip()
            if status:
                return True, status
            else:
                return False, "Container not running"
        else:
            return False, result.stderr.strip()
    except Exception as e:
        return False, str(e)


def check_redis_connection() -> Tuple[bool, str]:
    """Redis 연결 확인"""
    try:
        import redis
        # 호스트에서 접속할 때는 6380 사용 (docker-compose.yml에서 6380:6379 매핑)
        r = redis.Redis(host='localhost', port=6380, db=0, socket_connect_timeout=5)
        r.ping()
        return True, "Redis connected"
    except Exception as e:
        return False, f"Redis connection failed: {e}"


def check_api_health() -> Tuple[bool, str]:
    """API /health 엔드포인트 확인"""
    try:
        import requests
        response = requests.get('http://localhost:8001/health', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'healthy':
                return True, f"API healthy: {data}"
            else:
                return False, f"API not healthy: {data}"
        else:
            return False, f"API returned status {response.status_code}"
    except Exception as e:
        return False, f"API check failed: {e}"


def get_docker_logs(container_name: str, lines: int = 30) -> str:
    """Docker 컨테이너 로그 조회"""
    try:
        result = subprocess.run(
            ['docker', 'logs', '--tail', str(lines), container_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout
    except Exception as e:
        return f"Failed to get logs: {e}"


def check_paper_trader_completion() -> Tuple[bool, str]:
    """Paper trader 실행 완료 확인"""
    try:
        logs = get_docker_logs('arbitrage-paper-trader', lines=50)
        
        # 성공 패턴 확인
        if 'Paper trader run completed' in logs:
            return True, "Paper trader completed successfully"
        elif 'Error' in logs or 'FATAL' in logs or 'error' in logs:
            return False, f"Paper trader error detected in logs"
        else:
            return False, "Paper trader not yet completed"
    except Exception as e:
        return False, f"Failed to check paper trader: {e}"


def check_redis_keys() -> Tuple[bool, str]:
    """Redis에 저장된 키 확인"""
    try:
        import redis
        # 호스트에서 접속할 때는 6380 사용 (docker-compose.yml에서 6380:6379 매핑)
        r = redis.Redis(host='localhost', port=6380, db=0, socket_connect_timeout=5)
        
        # 모든 키 조회
        keys = r.keys('*')
        if keys:
            key_list = [k.decode('utf-8') if isinstance(k, bytes) else k for k in keys]
            return True, f"Redis keys found: {len(keys)} keys - {key_list[:10]}"
        else:
            return False, "No keys found in Redis"
    except Exception as e:
        return False, f"Redis key check failed: {e}"


def main():
    """메인 smoke test 실행"""
    
    logger.info("=" * 70)
    logger.info("D18 Docker Paper/Shadow Mode Smoke Test")
    logger.info("=" * 70)
    
    results = {}
    
    # 1. Docker 확인
    logger.info("\n[1] Checking Docker...")
    if not check_docker_running():
        logger.error("Docker is not running")
        return 1
    logger.info("✅ Docker is running")
    
    # 2. 컨테이너 상태 확인
    logger.info("\n[2] Checking container status...")
    containers = [
        'arbitrage-redis',
        'arbitrage-paper-trader',
        'arbitrage-dashboard'
    ]
    
    for container in containers:
        running, status = check_container_status(container)
        if running:
            logger.info(f"✅ {container}: {status}")
            results[f'{container}_status'] = 'running'
        else:
            logger.warning(f"⚠️  {container}: {status}")
            results[f'{container}_status'] = 'not_running'
    
    # 3. Redis 연결 확인
    logger.info("\n[3] Checking Redis connection...")
    time.sleep(2)  # Redis 시작 대기
    redis_ok, redis_msg = check_redis_connection()
    if redis_ok:
        logger.info(f"✅ {redis_msg}")
        results['redis_connection'] = 'ok'
    else:
        logger.warning(f"⚠️  {redis_msg}")
        results['redis_connection'] = 'failed'
    
    # 4. Redis 키 확인
    if redis_ok:
        logger.info("\n[4] Checking Redis keys...")
        keys_ok, keys_msg = check_redis_keys()
        if keys_ok:
            logger.info(f"✅ {keys_msg}")
            results['redis_keys'] = 'found'
        else:
            logger.info(f"ℹ️  {keys_msg}")
            results['redis_keys'] = 'not_found'
    
    # 5. API 헬스 체크
    logger.info("\n[5] Checking API health...")
    time.sleep(2)  # API 시작 대기
    api_ok, api_msg = check_api_health()
    if api_ok:
        logger.info(f"✅ {api_msg}")
        results['api_health'] = 'healthy'
    else:
        logger.warning(f"⚠️  {api_msg}")
        results['api_health'] = 'unhealthy'
    
    # 6. Paper trader 로그 확인
    logger.info("\n[6] Checking paper trader logs...")
    time.sleep(5)  # Paper trader 실행 대기
    
    logger.info("\nPaper trader logs (last 30 lines):")
    logger.info("-" * 70)
    logs = get_docker_logs('arbitrage-paper-trader', lines=30)
    for line in logs.split('\n')[-30:]:
        if line.strip():
            logger.info(line)
    logger.info("-" * 70)
    
    # 7. Paper trader 완료 확인
    logger.info("\n[7] Checking paper trader completion...")
    completed_ok, completed_msg = check_paper_trader_completion()
    if completed_ok:
        logger.info(f"✅ {completed_msg}")
        results['paper_trader_completion'] = 'completed'
    else:
        logger.info(f"ℹ️  {completed_msg}")
        results['paper_trader_completion'] = 'not_completed'
    
    # 최종 결과
    logger.info("\n" + "=" * 70)
    logger.info("SMOKE TEST SUMMARY")
    logger.info("=" * 70)
    
    for key, value in results.items():
        status = "✅" if value in ['ok', 'running', 'healthy', 'completed', 'found'] else "⚠️ "
        logger.info(f"{status} {key}: {value}")
    
    # 종료 코드 결정
    critical_checks = [
        results.get('arbitrage-redis_status') == 'running',
        results.get('arbitrage-paper-trader_status') == 'running',
        results.get('redis_connection') == 'ok',
    ]
    
    if all(critical_checks):
        logger.info("\n✅ SMOKE TEST PASSED")
        return 0
    else:
        logger.warning("\n⚠️  SMOKE TEST FAILED (some checks did not pass)")
        return 1


if __name__ == '__main__':
    sys.exit(main())
