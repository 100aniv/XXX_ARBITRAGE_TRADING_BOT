#!/usr/bin/env python3
"""
Arbitrage Engine - Health Check Script
Used by Docker HEALTHCHECK and monitoring systems
Exit codes: 0 = healthy, 1 = unhealthy
"""

import os
import sys
import time
from typing import Dict, Tuple

def check_redis() -> Tuple[bool, str]:
    """Check Redis connection and latency"""
    try:
        import redis
        
        host = os.getenv('REDIS_HOST', 'localhost')
        port = int(os.getenv('REDIS_PORT', '6379'))
        db = int(os.getenv('REDIS_DB', '0'))
        
        r = redis.Redis(host=host, port=port, db=db, socket_timeout=5)
        
        # Measure latency
        start = time.time()
        r.ping()
        latency_ms = (time.time() - start) * 1000
        
        if latency_ms > 30:
            return False, f"Redis latency too high: {latency_ms:.2f}ms"
        
        return True, f"Redis OK (latency: {latency_ms:.2f}ms)"
        
    except Exception as e:
        return False, f"Redis connection failed: {str(e)}"


def check_postgres() -> Tuple[bool, str]:
    """Check PostgreSQL connection"""
    try:
        import psycopg2
        
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = int(os.getenv('POSTGRES_PORT', '5432'))
        database = os.getenv('POSTGRES_DB', 'arbitrage')
        user = os.getenv('POSTGRES_USER', 'arbitrage')
        password = os.getenv('POSTGRES_PASSWORD', 'arbitrage')
        
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=5
        )
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        
        return True, "PostgreSQL OK"
        
    except Exception as e:
        return False, f"PostgreSQL connection failed: {str(e)}"


def check_log_volume() -> Tuple[bool, str]:
    """Check if logs are being written (indicates engine is running)"""
    try:
        env = os.getenv('ENV', 'development')
        log_file = f"logs/arbitrage_{env}.log"
        
        if not os.path.exists(log_file):
            return True, "Log file not created yet (startup phase)"
        
        # Check file modification time (should be recent)
        mtime = os.path.getmtime(log_file)
        age_seconds = time.time() - mtime
        
        if age_seconds > 300:  # 5 minutes
            return False, f"Log file not updated in {age_seconds:.0f}s"
        
        # Check file size (should have content)
        size = os.path.getsize(log_file)
        if size == 0:
            return False, "Log file is empty"
        
        return True, f"Log file OK (updated {age_seconds:.0f}s ago, size: {size} bytes)"
        
    except Exception as e:
        return False, f"Log check failed: {str(e)}"


def check_engine_metrics() -> Tuple[bool, str]:
    """Check engine loop latency from Redis metrics"""
    try:
        import redis
        
        host = os.getenv('REDIS_HOST', 'localhost')
        port = int(os.getenv('REDIS_PORT', '6379'))
        db = int(os.getenv('REDIS_DB', '0'))
        
        r = redis.Redis(host=host, port=port, db=db, socket_timeout=5)
        
        # Get latest metrics
        env = os.getenv('ENV', 'development')
        pattern = f"arbitrage:{env}:*:METRICS"
        
        keys = r.keys(pattern)
        if not keys:
            return True, "No metrics yet (startup phase)"
        
        # Check most recent metric key
        latest_key = keys[0]
        metrics_data = r.hgetall(latest_key)
        
        if not metrics_data:
            return True, "Metrics data not populated yet"
        
        # Check loop latency if available
        loop_latency_key = b'avg_loop_latency_ms'
        if loop_latency_key in metrics_data:
            loop_latency = float(metrics_data[loop_latency_key])
            if loop_latency > 100:  # 100ms threshold
                return False, f"Loop latency too high: {loop_latency:.2f}ms"
        
        return True, "Engine metrics OK"
        
    except Exception as e:
        # Not critical for health check
        return True, f"Metrics check skipped: {str(e)}"


def main() -> int:
    """Run all health checks"""
    checks: Dict[str, Tuple[bool, str]] = {
        'Redis': check_redis(),
        'PostgreSQL': check_postgres(),
        'Logs': check_log_volume(),
        'Metrics': check_engine_metrics(),
    }
    
    # Print results
    all_healthy = True
    for name, (healthy, message) in checks.items():
        status = "✓" if healthy else "✗"
        print(f"{status} {name}: {message}")
        if not healthy:
            all_healthy = False
    
    # Exit code
    if all_healthy:
        print("\n✓ Health check PASSED")
        return 0
    else:
        print("\n✗ Health check FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
