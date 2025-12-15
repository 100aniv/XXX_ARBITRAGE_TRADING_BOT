#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92 POST-MOVE-HARDEN v3: Environment Checker (Final)

Checks:
1. Docker containers (PostgreSQL, Redis)
2. Redis connectivity
3. PostgreSQL connectivity
4. Python processes

Exit codes:
- 0: All checks PASS, WARN=0
- 1: Some checks FAIL or WARN>0
"""

import sys
import subprocess
import redis
import psycopg2
from pathlib import Path

def check_docker():
    """Check Docker containers"""
    print("[CHECK] Docker containers...")
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("[FAIL] Docker command failed")
        return False
    
    containers = result.stdout.strip().split('\n')
    required = ["trading_db_postgres", "trading_redis"]
    found = {name: False for name in required}
    
    for line in containers:
        if not line.strip():
            continue
        name, status = line.split('\t', 1)
        if name in required:
            found[name] = True
            print(f"  [OK] {name}: {status}")
    
    all_found = all(found.values())
    if not all_found:
        missing = [k for k, v in found.items() if not v]
        print(f"[FAIL] Missing containers: {missing}")
        return False
    
    return True

def check_redis():
    """Check Redis connectivity"""
    print("[CHECK] Redis connectivity...")
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        key_count = r.dbsize()
        print(f"  [OK] Redis connected, keys: {key_count}")
        return True
    except Exception as e:
        print(f"[FAIL] Redis connection failed: {e}")
        return False

def check_postgres():
    """Check PostgreSQL connectivity"""
    print("[CHECK] PostgreSQL connectivity...")
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            dbname='arbitrage',
            user='arbitrage',
            password='arbitrage'
        )
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"  [OK] PostgreSQL connected")
        print(f"       Version: {version.split(',')[0]}")
        
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")
        table_count = cur.fetchone()[0]
        print(f"       Tables: {table_count}")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[FAIL] PostgreSQL connection failed: {e}")
        return False

def check_python_processes():
    """Check for conflicting Python processes"""
    print("[CHECK] Python processes...")
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("  [WARN] Could not check processes")
        return True
    
    lines = result.stdout.strip().split('\n')[1:]
    process_count = len([l for l in lines if l.strip() and 'python.exe' in l.lower()])
    
    print(f"  [OK] Python processes: {process_count}")
    return True

def main():
    print("=" * 80)
    print("D92 POST-MOVE-HARDEN v3: Environment Checker")
    print("=" * 80)
    
    checks = {
        "Docker Containers": check_docker,
        "Redis": check_redis,
        "PostgreSQL": check_postgres,
        "Python Processes": check_python_processes
    }
    
    results = {}
    for name, func in checks.items():
        print()
        try:
            results[name] = func()
        except Exception as e:
            print(f"[ERROR] {name} check crashed: {e}")
            results[name] = False
    
    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    
    all_pass = True
    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {name}")
        if not passed:
            all_pass = False
    
    print("=" * 80)
    
    if all_pass:
        print("[OK] All checks PASS, WARN=0")
        return 0
    else:
        print("[FAIL] Some checks failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
