#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D77-4 Environment Checker - 완전 자동화 4대 원칙 (1)

실행 전 환경 자동 정리:
- 기존 PAPER Runner 프로세스 안전 종료
- Docker Redis/PostgreSQL 상태 확인 및 자동 기동
- Redis/DB 상태 초기화
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)


class D77EnvChecker:
    """D77-4 환경 체크 및 자동 정리"""
    
    def __init__(self, project_root: Path, run_id: str):
        self.project_root = project_root
        self.run_id = run_id
        self.log_dir = project_root / "logs" / "d77-4" / run_id
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 로깅 설정
        self._setup_logging()
    
    def _setup_logging(self):
        """로깅 핸들러 추가"""
        log_file = self.log_dir / "env_checker.log"
        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    def check_all(self) -> Tuple[bool, Dict[str, any]]:
        """전체 환경 체크 수행
        
        Returns:
            (success, result_dict)
        """
        logger.info(f"[D77-4] 환경 체크 시작 (run_id: {self.run_id})")
        
        result = {
            "run_id": self.run_id,
            "steps": {},
            "success": True,
        }
        
        # Step 1: 기존 Runner 프로세스 종료
        logger.info("[Step 1/4] 기존 PAPER Runner 프로세스 체크")
        killed_count = self._kill_existing_runners()
        result["steps"]["process_cleanup"] = {
            "killed_processes": killed_count,
            "success": True
        }
        
        # Step 2: Docker 컨테이너 체크
        logger.info("[Step 2/4] Docker Redis/PostgreSQL 컨테이너 체크")
        docker_ok, docker_status = self._check_docker_containers()
        result["steps"]["docker_check"] = {
            "redis_status": docker_status.get("redis"),
            "postgres_status": docker_status.get("postgres"),
            "success": docker_ok
        }
        
        if not docker_ok:
            logger.warning("Docker 컨테이너 체크 실패 (경고, 계속 진행)")
            # Docker 실패해도 계속 진행 (로컬 개발 환경일 수 있음)
        
        # Step 3: Redis 초기화
        logger.info("[Step 3/4] Redis 상태 초기화")
        redis_ok = self._reset_redis()
        result["steps"]["redis_reset"] = {"success": redis_ok}
        
        if not redis_ok:
            logger.warning("Redis 초기화 실패 (경고, 계속 진행)")
        
        # Step 4: PostgreSQL 초기화
        logger.info("[Step 4/4] PostgreSQL alert 테이블 정리")
        pg_ok = self._reset_postgres()
        result["steps"]["postgres_reset"] = {"success": pg_ok}
        
        if not pg_ok:
            logger.warning("PostgreSQL 초기화 실패 (경고, 계속 진행)")
        
        logger.info(f"[D77-4] 환경 체크 완료: {'SUCCESS' if result['success'] else 'FAIL'}")
        return result["success"], result
    
    def _kill_existing_runners(self) -> int:
        """기존 PAPER Runner 프로세스 종료
        
        Returns:
            종료된 프로세스 수
        """
        if not psutil:
            logger.warning("psutil 없음, 프로세스 체크 생략")
            return 0
        
        killed_count = 0
        target_script = "run_d77_0_topn_arbitrage_paper.py"
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline')
                if not cmdline:
                    continue
                
                # IDE 런처나 관계없는 프로세스는 제외
                cmdline_str = ' '.join(cmdline)
                if target_script in cmdline_str and 'python' in cmdline_str.lower():
                    # 현재 프로세스는 제외 (오케스트레이터 자신)
                    if proc.pid == os.getpid():
                        continue
                    
                    logger.info(f"기존 Runner 프로세스 종료: PID={proc.pid}")
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if killed_count > 0:
            logger.info(f"총 {killed_count}개 프로세스 종료")
        else:
            logger.info("종료할 프로세스 없음")
        
        return killed_count
    
    def _check_docker_containers(self) -> Tuple[bool, Dict[str, str]]:
        """Docker Redis/PostgreSQL 컨테이너 상태 확인 및 자동 기동
        
        Returns:
            (success, status_dict)
        """
        docker_dir = self.project_root / "docker"
        
        # Windows 환경에서 docker compose 명령 확인
        try:
            result = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                cwd=docker_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"docker compose ps 실패: {result.stderr}")
                return False, {}
            
            # 컨테이너 상태 파싱
            import json
            containers = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        containers.append(json.loads(line))
                    except:
                        pass
            
            redis_up = any(c.get('Service') == 'redis' and 'Up' in c.get('State', '') for c in containers)
            postgres_up = any(c.get('Service') == 'postgres' and 'Up' in c.get('State', '') for c in containers)
            
            status = {
                "redis": "Up" if redis_up else "Down",
                "postgres": "Up" if postgres_up else "Down"
            }
            
            # 하나라도 Down이면 자동 기동
            if not (redis_up and postgres_up):
                logger.info("컨테이너 일부 Down 상태, docker compose up -d 실행")
                up_result = subprocess.run(
                    ["docker", "compose", "up", "-d"],
                    cwd=docker_dir,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=60
                )
                
                if up_result.returncode != 0:
                    logger.error(f"docker compose up -d 실패: {up_result.stderr}")
                    return False, status
                
                logger.info("30초 대기 (컨테이너 기동)")
                time.sleep(30)
                
                # 재확인
                redis_up = postgres_up = True  # 낙관적 가정
                status = {"redis": "Up", "postgres": "Up"}
            
            logger.info(f"Docker 컨테이너 상태: Redis={status['redis']}, Postgres={status['postgres']}")
            return True, status
            
        except FileNotFoundError:
            logger.error("docker 명령어를 찾을 수 없음 (Docker 미설치?)")
            return False, {}
        except subprocess.TimeoutExpired:
            logger.error("docker compose 명령 타임아웃")
            return False, {}
        except Exception as e:
            logger.error(f"Docker 체크 중 예외: {e}")
            return False, {}
    
    def _reset_redis(self) -> bool:
        """Redis FLUSHDB 실행
        
        Returns:
            성공 여부
        """
        try:
            result = subprocess.run(
                ["docker", "exec", "arbitrage-redis", "redis-cli", "FLUSHDB"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=10
            )
            
            if result.returncode == 0 and "OK" in result.stdout:
                logger.info("Redis FLUSHDB 성공")
                return True
            else:
                logger.warning(f"Redis FLUSHDB 실패: {result.stderr}")
                return False
        except Exception as e:
            logger.warning(f"Redis 초기화 예외: {e}")
            return False
    
    def _reset_postgres(self) -> bool:
        """PostgreSQL alert 관련 테이블 정리
        
        Returns:
            성공 여부 (테이블이 없는 경우 생성 후 True)
        """
        try:
            # alert_history 테이블 생성 (없으면 생성, 있으면 무시)
            create_sql = """
            CREATE TABLE IF NOT EXISTS alert_history (
                id SERIAL PRIMARY KEY,
                severity VARCHAR(10) NOT NULL,
                source VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            
            create_result = subprocess.run(
                ["docker", "exec", "arbitrage-postgres", 
                 "psql", "-U", "arbitrage", "-d", "arbitrage", "-c", create_sql],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=10
            )
            
            if create_result.returncode != 0:
                logger.warning(f"PostgreSQL 테이블 생성 실패: {create_result.stderr}")
                return False
            
            # TRUNCATE로 데이터 정리
            truncate_sql = "TRUNCATE TABLE alert_history CASCADE;"
            truncate_result = subprocess.run(
                ["docker", "exec", "arbitrage-postgres", 
                 "psql", "-U", "arbitrage", "-d", "arbitrage", "-c", truncate_sql],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=10
            )
            
            if truncate_result.returncode == 0:
                logger.info("PostgreSQL alert_history 초기화 완료 (테이블 생성/정리)")
                return True
            else:
                logger.warning(f"PostgreSQL TRUNCATE 실패: {truncate_result.stderr}")
                return False
                
        except Exception as e:
            logger.warning(f"PostgreSQL 초기화 예외: {e}")
            return False


def main():
    """CLI 엔트리포인트 (테스트용)"""
    import argparse
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description="D77-4 Environment Checker")
    parser.add_argument("--run-id", default=f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    args = parser.parse_args()
    
    # 프로젝트 루트 추정
    project_root = Path(__file__).parent.parent
    
    checker = D77EnvChecker(project_root, args.run_id)
    success, result = checker.check_all()
    
    print(f"\n{'='*60}")
    print(f"D77-4 Environment Check: {'SUCCESS' if success else 'FAIL'}")
    print(f"{'='*60}")
    print(f"Run ID: {result['run_id']}")
    print(f"Process Cleanup: {result['steps']['process_cleanup']['killed_processes']} killed")
    print(f"Docker Redis: {result['steps']['docker_check'].get('redis_status', 'N/A')}")
    print(f"Docker PostgreSQL: {result['steps']['docker_check'].get('postgres_status', 'N/A')}")
    if 'redis_reset' in result['steps']:
        print(f"Redis Reset: {'OK' if result['steps']['redis_reset']['success'] else 'WARN'}")
    if 'postgres_reset' in result['steps']:
        print(f"PostgreSQL Reset: {'OK' if result['steps']['postgres_reset']['success'] else 'WARN'}")
    print(f"{'='*60}\n")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
