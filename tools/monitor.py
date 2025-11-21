#!/usr/bin/env python3
"""
CLI Monitoring Tool for D72-4

Real-time monitoring of logs and metrics from Redis/PostgreSQL.

Usage:
    python tools/monitor.py --tail         # Tail logs in real-time
    python tools/monitor.py --metrics      # Watch metrics dashboard
    python tools/monitor.py --errors       # Monitor errors only
    python tools/monitor.py --search "keyword"  # Search logs
"""

import argparse
import time
import sys
from datetime import datetime
from typing import Dict, Any, List

import redis
import psycopg2
from psycopg2.extras import RealDictCursor


class LogMonitor:
    """Real-time log monitoring"""
    
    def __init__(self, redis_config: Dict[str, Any], env: str = "development"):
        self.redis = redis.Redis(**redis_config, decode_responses=False)
        self.env = env
        self.stream_key = f"arbitrage:logs:{env}"
        self.last_id = "0-0"
    
    def tail(self, follow: bool = True):
        """Tail logs in real-time"""
        print(f"[Monitor] Tailing logs from {self.stream_key}...")
        print("=" * 100)
        
        try:
            while True:
                # Read from stream
                entries = self.redis.xread(
                    {self.stream_key: self.last_id},
                    count=10,
                    block=1000 if follow else 0
                )
                
                if not entries:
                    if not follow:
                        break
                    continue
                
                for stream_name, messages in entries:
                    for msg_id, data in messages:
                        self._print_log_entry(data)
                        self.last_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
                
                if not follow:
                    break
        
        except KeyboardInterrupt:
            print("\n[Monitor] Stopped")
    
    def _print_log_entry(self, data: Dict[bytes, bytes]):
        """Print a single log entry"""
        # Decode data
        decoded = {k.decode(): v.decode() for k, v in data.items()}
        
        # Color codes
        colors = {
            "DEBUG": "\033[36m",     # Cyan
            "INFO": "\033[32m",      # Green
            "WARNING": "\033[33m",   # Yellow
            "ERROR": "\033[31m",     # Red
            "CRITICAL": "\033[35m",  # Magenta
        }
        reset = "\033[0m"
        
        level = decoded.get("level", "INFO")
        color = colors.get(level, reset)
        
        timestamp_str = decoded.get("timestamp", "")
        if timestamp_str:
            try:
                dt = datetime.fromisoformat(timestamp_str)
                timestamp_str = dt.strftime("%H:%M:%S")
            except:
                pass
        
        component = decoded.get("component", "")
        category = decoded.get("category", "")
        message = decoded.get("message", "")
        
        print(
            f"{color}[{timestamp_str}] [{level:8s}] "
            f"[{component:20s}] [{category:10s}] {message}{reset}"
        )


class MetricsMonitor:
    """Real-time metrics monitoring"""
    
    def __init__(self, redis_config: Dict[str, Any], env: str = "development"):
        self.redis = redis.Redis(**redis_config, decode_responses=True)
        self.env = env
        self.base_key = f"arbitrage:metrics:{env}"
    
    def watch(self, interval: int = 2):
        """Watch metrics dashboard"""
        print(f"[Monitor] Watching metrics (refresh every {interval}s)...")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                self._print_dashboard()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[Monitor] Stopped")
    
    def _print_dashboard(self):
        """Print metrics dashboard"""
        # Clear screen (works on Windows and Unix)
        print("\033[2J\033[H", end="")
        
        print("=" * 100)
        print(f"ARBITRAGE MONITORING DASHBOARD - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)
        
        # Find all session metrics
        pattern = f"{self.base_key}:*"
        keys = self.redis.keys(pattern)
        
        if not keys:
            print("\n[No active sessions]")
            print("=" * 100)
            return
        
        # Print each session
        for key in keys:
            session_id = key.split(":")[-1]
            metrics = self.redis.hgetall(key)
            
            if not metrics:
                continue
            
            print(f"\n📊 Session: {session_id}")
            print("-" * 100)
            
            # Parse metrics
            trades = metrics.get("trades_per_minute", "0")
            errors = metrics.get("errors_per_minute", "0")
            ws_latency = metrics.get("avg_ws_latency_ms", "0.0")
            loop_latency = metrics.get("avg_loop_latency_ms", "0.0")
            guards = metrics.get("guard_triggers_per_minute", "0")
            pnl = metrics.get("pnl_change_1min", "0.0")
            last_update = metrics.get("last_update", "N/A")
            
            # Print with colors
            print(f"  Trades/min:    \033[32m{trades:>6s}\033[0m")
            print(f"  Errors/min:    \033[31m{errors:>6s}\033[0m")
            print(f"  WS Latency:    \033[36m{ws_latency:>8s} ms\033[0m")
            print(f"  Loop Latency:  \033[36m{loop_latency:>8s} ms\033[0m")
            print(f"  Guard Triggers:\033[33m{guards:>6s}\033[0m")
            print(f"  PnL Change:    \033[35m{pnl:>8s}\033[0m")
            print(f"  Last Update:   {last_update}")
        
        print("\n" + "=" * 100)


class ErrorMonitor:
    """Error-only monitoring from PostgreSQL"""
    
    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.conn = None
        self._connect()
    
    def _connect(self):
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(**self.db_config, cursor_factory=RealDictCursor)
        except Exception as e:
            print(f"[ErrorMonitor] Failed to connect: {e}")
    
    def watch(self, interval: int = 5):
        """Watch for errors"""
        print(f"[Monitor] Watching errors (refresh every {interval}s)...")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                self._print_recent_errors()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[Monitor] Stopped")
        finally:
            if self.conn:
                self.conn.close()
    
    def _print_recent_errors(self):
        """Print recent errors"""
        if not self.conn:
            self._connect()
        
        if not self.conn:
            print("[ErrorMonitor] No database connection")
            return
        
        # Clear screen
        print("\033[2J\033[H", end="")
        
        print("=" * 100)
        print(f"RECENT ERRORS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        created_at,
                        level,
                        component,
                        category,
                        message
                    FROM system_logs
                    WHERE level IN ('ERROR', 'CRITICAL')
                    ORDER BY created_at DESC
                    LIMIT 20
                """)
                
                errors = cur.fetchall()
                
                if not errors:
                    print("\n✅ No recent errors")
                else:
                    print(f"\n❌ {len(errors)} recent errors:\n")
                    for err in errors:
                        timestamp = err['created_at'].strftime("%H:%M:%S")
                        level = err['level']
                        component = err['component']
                        category = err['category']
                        message = err['message']
                        
                        color = "\033[31m" if level == "ERROR" else "\033[35m"
                        print(
                            f"{color}[{timestamp}] [{level:8s}] "
                            f"[{component:20s}] [{category:10s}] {message}\033[0m"
                        )
        except Exception as e:
            print(f"[ErrorMonitor] Query failed: {e}")
        
        print("\n" + "=" * 100)


class LogSearcher:
    """Search logs from PostgreSQL"""
    
    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
    
    def search(self, keyword: str, limit: int = 50):
        """Search logs by keyword"""
        conn = None
        try:
            conn = psycopg2.connect(**self.db_config, cursor_factory=RealDictCursor)
            
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM search_logs(%s, %s)
                    """,
                    (keyword, limit)
                )
                
                results = cur.fetchall()
                
                print(f"\n[Search] Found {len(results)} results for '{keyword}':\n")
                print("=" * 100)
                
                for row in results:
                    timestamp = row['created_at'].strftime("%Y-%m-%d %H:%M:%S")
                    level = row['level']
                    component = row['component']
                    category = row['category']
                    message = row['message']
                    
                    print(
                        f"[{timestamp}] [{level:8s}] "
                        f"[{component:20s}] [{category:10s}] {message}"
                    )
                    print("-" * 100)
        
        except Exception as e:
            print(f"[Search] Failed: {e}")
        finally:
            if conn:
                conn.close()


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Arbitrage Monitoring Tool")
    parser.add_argument("--tail", action="store_true", help="Tail logs in real-time")
    parser.add_argument("--metrics", action="store_true", help="Watch metrics dashboard")
    parser.add_argument("--errors", action="store_true", help="Monitor errors only")
    parser.add_argument("--search", type=str, help="Search logs by keyword")
    parser.add_argument("--env", type=str, default="development", help="Environment (development/staging/production)")
    parser.add_argument("--no-follow", action="store_true", help="Don't follow logs (print and exit)")
    
    args = parser.parse_args()
    
    # Redis config
    redis_config = {
        "host": "localhost",
        "port": 6379,
        "db": 0
    }
    
    # PostgreSQL config
    db_config = {
        "host": "localhost",
        "port": 5432,
        "database": "arbitrage",
        "user": "arbitrage",
        "password": "arbitrage"
    }
    
    try:
        if args.tail:
            monitor = LogMonitor(redis_config, args.env)
            monitor.tail(follow=not args.no_follow)
        
        elif args.metrics:
            monitor = MetricsMonitor(redis_config, args.env)
            monitor.watch()
        
        elif args.errors:
            monitor = ErrorMonitor(db_config)
            monitor.watch()
        
        elif args.search:
            searcher = LogSearcher(db_config)
            searcher.search(args.search)
        
        else:
            parser.print_help()
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n[Monitor] Stopped by user")
    except Exception as e:
        print(f"[Monitor] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
