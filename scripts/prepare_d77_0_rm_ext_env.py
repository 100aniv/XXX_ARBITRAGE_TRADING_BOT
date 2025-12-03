#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D77-0-RM-EXT 환경 준비 스크립트

- Docker 인프라 상태 확인 (Redis, PostgreSQL, Prometheus, Grafana)
- Redis/PostgreSQL 상태 정리 (쿨다운, 포지션, 가드 상태 등)
- 기존 실행 프로세스 정리
- 로그 디렉토리 준비

Usage:
    python scripts/prepare_d77_0_rm_ext_env.py --clean-all
    python scripts/prepare_d77_0_rm_ext_env.py --check-only
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

try:
    import redis
    import psycopg2
    import requests
except ImportError as e:
    print(f"[ERROR] 필수 패키지 누락: {e}")
    print("실행: pip install redis psycopg2-binary requests")
    sys.exit(1)


PROJECT_ROOT = Path(__file__).parent.parent


def check_docker_service(service_name: str, port: int) -> bool:
    """Docker 서비스 상태 확인"""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={service_name}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and "Up" in result.stdout:
            print(f"[OK] {service_name} 컨테이너 실행 중")
            return True
        else:
            print(f"[WARN] {service_name} 컨테이너가 실행 중이 아닙니다")
            return False
    except Exception as e:
        print(f"[ERROR] {service_name} 상태 확인 실패: {e}")
        return False


def check_redis(host="localhost", port=6379) -> bool:
    """Redis 연결 및 상태 확인"""
    try:
        r = redis.Redis(host=host, port=port, decode_responses=True, socket_timeout=3)
        r.ping()
        keys_count = r.dbsize()
        print(f"[OK] Redis 연결 성공 (Keys: {keys_count})")
        return True
    except Exception as e:
        print(f"[ERROR] Redis 연결 실패: {e}")
        return False


def clean_redis(host="localhost", port=6379):
    """Redis 상태 정리 (D77 관련 키만)"""
    try:
        r = redis.Redis(host=host, port=port, decode_responses=True, socket_timeout=3)
        
        # D77 관련 키 패턴
        patterns = [
            "arbitrage:*",
            "d77:*",
            "paper:*",
            "topn:*"
        ]
        
        deleted_count = 0
        for pattern in patterns:
            keys = r.keys(pattern)
            if keys:
                deleted = r.delete(*keys)
                deleted_count += deleted
                print(f"[INFO] Redis 키 삭제: {pattern} ({deleted}개)")
        
        print(f"[OK] Redis 정리 완료 (총 {deleted_count}개 키 삭제)")
        return True
    except Exception as e:
        print(f"[ERROR] Redis 정리 실패: {e}")
        return False


def check_postgres(host="localhost", port=5432, dbname="arbitrage", user="postgres", password="postgres") -> bool:
    """PostgreSQL 연결 확인"""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=3
        )
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(f"[OK] PostgreSQL 연결 성공")
        return True
    except Exception as e:
        print(f"[ERROR] PostgreSQL 연결 실패: {e}")
        return False


def check_prometheus(host="localhost", port=9090) -> bool:
    """Prometheus 상태 확인"""
    try:
        response = requests.get(f"http://{host}:{port}/-/healthy", timeout=3)
        if response.status_code == 200:
            print(f"[OK] Prometheus 실행 중 (http://{host}:{port})")
            return True
        else:
            print(f"[WARN] Prometheus 응답 이상: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Prometheus 연결 실패: {e}")
        return False


def check_grafana(host="localhost", port=3000) -> bool:
    """Grafana 상태 확인"""
    try:
        response = requests.get(f"http://{host}:{port}/api/health", timeout=3)
        if response.status_code == 200:
            print(f"[OK] Grafana 실행 중 (http://{host}:{port})")
            return True
        else:
            print(f"[WARN] Grafana 응답 이상: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Grafana 연결 실패: {e}")
        return False


def kill_existing_processes():
    """기존 D77 실행 프로세스 종료 (Windows)"""
    try:
        # PowerShell 명령어로 D77 관련 프로세스 찾기
        ps_command = 'Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like "*run_d77_0*"} | Select-Object -ExpandProperty Id'
        
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"[INFO] 발견된 D77 프로세스: {len(pids)}개")
            
            for pid in pids:
                try:
                    subprocess.run(["taskkill", "/F", "/PID", pid.strip()], timeout=3)
                    print(f"[OK] 프로세스 종료: PID {pid.strip()}")
                except:
                    pass
        else:
            print("[OK] 실행 중인 D77 프로세스 없음")
        
        return True
    except Exception as e:
        print(f"[WARN] 프로세스 정리 실패: {e}")
        return False


def prepare_log_directory():
    """로그 디렉토리 준비"""
    log_dir = PROJECT_ROOT / "logs" / "d77-0-rm-ext"
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"[OK] 로그 디렉토리 준비: {log_dir}")
    return True


def main():
    parser = argparse.ArgumentParser(description="D77-0-RM-EXT 환경 준비")
    parser.add_argument("--check-only", action="store_true", help="상태 확인만 수행 (정리 안 함)")
    parser.add_argument("--clean-all", action="store_true", help="Redis 상태 전체 정리")
    parser.add_argument("--kill-processes", action="store_true", help="기존 프로세스 종료")
    
    args = parser.parse_args()
    
    print("="*80)
    print("[D77-0-RM-EXT] 환경 준비 스크립트")
    print("="*80)
    
    # 1. Docker 서비스 확인
    print("\n[STEP 1] Docker 서비스 상태 확인")
    redis_ok = check_docker_service("redis", 6379)
    postgres_ok = check_docker_service("postgres", 5432)
    prometheus_ok = check_docker_service("prometheus", 9090)
    grafana_ok = check_docker_service("grafana", 3000)
    
    if not all([redis_ok, postgres_ok, prometheus_ok, grafana_ok]):
        print("\n[ERROR] 일부 Docker 서비스가 실행 중이 아닙니다")
        print("실행: docker-compose up -d redis postgres prometheus grafana")
        sys.exit(1)
    
    # 2. 서비스 연결 확인
    print("\n[STEP 2] 서비스 연결 확인")
    redis_conn = check_redis()
    postgres_conn = check_postgres()
    prometheus_conn = check_prometheus()
    grafana_conn = check_grafana()
    
    if not redis_conn:
        print("\n[ERROR] Redis 연결 실패 (필수)")
        sys.exit(1)
    
    if not postgres_conn:
        print("\n[WARN] PostgreSQL 연결 실패 (선택적, 계속 진행)")
    
    if args.check_only:
        print("\n[INFO] 상태 확인만 수행 (--check-only)")
        print("[OK] 모든 서비스 정상")
        return 0
    
    # 3. 프로세스 정리
    if args.kill_processes or args.clean_all:
        print("\n[STEP 3] 기존 프로세스 정리")
        kill_existing_processes()
        time.sleep(1)
    
    # 4. Redis 정리
    if args.clean_all:
        print("\n[STEP 4] Redis 상태 정리")
        clean_redis()
        time.sleep(1)
    
    # 5. 로그 디렉토리 준비
    print("\n[STEP 5] 로그 디렉토리 준비")
    prepare_log_directory()
    
    print("\n" + "="*80)
    print("[OK] 환경 준비 완료")
    print("="*80)
    print("\n다음 단계:")
    print("1. Smoke Test: python scripts/run_d77_0_rm_ext.py --scenario smoke")
    print("2. Primary (Top20): python scripts/run_d77_0_rm_ext.py --scenario primary")
    print("3. Extended (Top50): python scripts/run_d77_0_rm_ext.py --scenario extended")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
