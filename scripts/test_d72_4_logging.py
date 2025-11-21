#!/usr/bin/env python3
"""
D72-4 Logging & Monitoring MVP - Integration Tests

Tests:
1. LoggingManager initialization
2. File logger
3. Console logger
4. Redis logger (streams + metrics)
5. PostgreSQL logger
6. Metrics collector
7. End-to-end logging pipeline
"""

import os
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import redis
import psycopg2
from psycopg2.extras import RealDictCursor

from arbitrage.logging_manager import (
    LoggingManager,
    LogLevel,
    LogCategory,
    LogRecord
)
from arbitrage.metrics_collector import MetricsCollector, MetricsAggregator


class TestD72Logging:
    """Test suite for D72-4 logging"""
    
    def __init__(self):
        self.test_session_id = "test_d72_4"
        self.test_env = "development"
        
        # Redis config
        self.redis_config = {
            "host": "localhost",
            "port": 6379,
            "db": 0
        }
        
        # PostgreSQL config
        self.db_config = {
            "host": "localhost",
            "port": 5432,
            "database": "arbitrage",
            "user": "arbitrage",
            "password": "arbitrage"
        }
        
        self.redis_client = None
        self.db_conn = None
        self.logger = None
        self.passed = 0
        self.failed = 0
    
    def setup(self):
        """Setup test environment"""
        print("=" * 100)
        print("D72-4 LOGGING & MONITORING MVP - INTEGRATION TESTS")
        print("=" * 100)
        print()
        
        # Connect to Redis
        try:
            self.redis_client = redis.Redis(**self.redis_config, decode_responses=False)
            self.redis_client.ping()
            print("✅ Redis connection OK")
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            sys.exit(1)
        
        # Connect to PostgreSQL
        try:
            self.db_conn = psycopg2.connect(**self.db_config, cursor_factory=RealDictCursor)
            print("✅ PostgreSQL connection OK")
        except Exception as e:
            print(f"❌ PostgreSQL connection failed: {e}")
            sys.exit(1)
        
        # Clean up existing logs
        print("\n🧹 Cleaning up old test logs...")
        self._cleanup()
        
        print()
    
    def _cleanup(self):
        """Clean up test data"""
        # Clean Redis
        pattern = f"arbitrage:logs:{self.test_env}*"
        keys = self.redis_client.keys(pattern)
        if keys:
            self.redis_client.delete(*keys)
        
        pattern = f"arbitrage:metrics:{self.test_env}*"
        keys = self.redis_client.keys(pattern)
        if keys:
            self.redis_client.delete(*keys)
        
        # Clean PostgreSQL
        with self.db_conn.cursor() as cur:
            cur.execute("DELETE FROM system_logs WHERE session_id = %s", (self.test_session_id,))
        self.db_conn.commit()
    
    def teardown(self):
        """Cleanup"""
        if self.logger:
            self.logger.shutdown()
        
        if self.redis_client:
            self.redis_client.close()
        
        if self.db_conn:
            self.db_conn.close()
    
    def run_test(self, test_name: str, test_func):
        """Run a single test"""
        print(f"▶️  {test_name}...")
        try:
            test_func()
            print(f"   ✅ PASS\n")
            self.passed += 1
        except AssertionError as e:
            print(f"   ❌ FAIL: {e}\n")
            self.failed += 1
        except Exception as e:
            print(f"   ❌ ERROR: {e}\n")
            self.failed += 1
    
    def test_01_logging_manager_initialization(self):
        """Test LoggingManager initialization"""
        self.logger = LoggingManager.initialize(
            env=self.test_env,
            redis_config=self.redis_config,
            db_config=self.db_config,
            log_dir="logs/test"
        )
        
        assert self.logger is not None, "LoggingManager not initialized"
        assert self.logger.env == self.test_env, f"Wrong env: {self.logger.env}"
        
        # Set session ID
        self.logger.set_session_id(self.test_session_id)
        assert self.logger.session_id == self.test_session_id, "Session ID not set"
    
    def test_02_file_logging(self):
        """Test file logger"""
        log_file = Path("logs/test") / f"arbitrage_{self.test_env}.log"
        
        # Write log
        self.logger.info(
            "TestComponent",
            LogCategory.SYSTEM,
            "File logging test",
            test_data="hello"
        )
        
        time.sleep(0.1)  # Give file system time to write
        
        assert log_file.exists(), f"Log file not created: {log_file}"
        
        # Verify content
        with open(log_file, 'r') as f:
            content = f.read()
            assert "File logging test" in content, "Log message not found in file"
    
    def test_03_redis_stream_logging(self):
        """Test Redis Stream logger"""
        # Write logs
        for i in range(5):
            self.logger.info(
                "TestComponent",
                LogCategory.TRADE,
                f"Redis stream test {i}",
                trade_id=i
            )
        
        time.sleep(0.1)
        
        # Read from stream
        stream_key = f"arbitrage:logs:{self.test_env}"
        count = self.redis_client.xlen(stream_key)
        
        assert count >= 5, f"Expected at least 5 log entries, got {count}"
        
        # Read entries
        entries = self.redis_client.xrevrange(stream_key, count=5)
        assert len(entries) >= 5, f"Expected 5 entries, got {len(entries)}"
        
        # Verify structure
        _, data = entries[0]
        assert b'message' in data, "Log entry missing 'message' field"
        assert b'level' in data, "Log entry missing 'level' field"
    
    def test_04_postgres_logging(self):
        """Test PostgreSQL logger"""
        # Write ERROR log (only ERROR+ goes to DB)
        self.logger.error(
            "TestComponent",
            LogCategory.SYSTEM,
            "PostgreSQL logging test",
            error_code=500
        )
        
        time.sleep(0.2)
        
        # Query database
        with self.db_conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM system_logs 
                WHERE session_id = %s 
                    AND message = 'PostgreSQL logging test'
            """, (self.test_session_id,))
            rows = cur.fetchall()
        
        assert len(rows) > 0, "Log not found in database"
        
        row = rows[0]
        assert row['level'] == 'ERROR', f"Wrong log level: {row['level']}"
        assert row['category'] == 'system', f"Wrong category: {row['category']}"
        assert row['json_payload']['error_code'] == 500, "Payload not preserved"
    
    def test_05_metrics_collector(self):
        """Test MetricsCollector"""
        collector = MetricsCollector(
            redis_client=redis.Redis(**self.redis_config),
            env=self.test_env,
            session_id=self.test_session_id
        )
        
        # Record metrics
        collector.record_trade()
        collector.record_trade()
        collector.record_error()
        collector.record_ws_latency(15.5)
        collector.record_loop_latency(8.3)
        collector.record_guard_trigger()
        collector.record_pnl_change(125.50)
        
        # Flush to Redis
        collector.flush()
        
        time.sleep(0.1)
        
        # Read metrics from Redis
        metrics_key = f"arbitrage:metrics:{self.test_env}:{self.test_session_id}"
        metrics = self.redis_client.hgetall(metrics_key)
        
        assert len(metrics) > 0, "No metrics in Redis"
        
        # Decode and verify
        metrics_decoded = {
            k.decode(): v.decode() for k, v in metrics.items()
        }
        
        assert int(metrics_decoded.get('trades_per_minute', 0)) >= 2, "Trade count not recorded"
        assert int(metrics_decoded.get('errors_per_minute', 0)) >= 1, "Error count not recorded"
    
    def test_06_metrics_aggregator(self):
        """Test MetricsAggregator"""
        # Create multiple sessions
        collectors = []
        for i in range(3):
            session_id = f"{self.test_session_id}_s{i}"
            collector = MetricsCollector(
                redis_client=redis.Redis(**self.redis_config),
                env=self.test_env,
                session_id=session_id
            )
            
            # Record some trades
            for _ in range(i + 1):
                collector.record_trade()
            
            collector.flush()
            collectors.append(collector)
        
        time.sleep(0.1)
        
        # Aggregate
        aggregator = MetricsAggregator(
            redis_client=redis.Redis(**self.redis_config, decode_responses=True),
            env=self.test_env
        )
        
        all_metrics = aggregator.get_all_session_metrics()
        assert len(all_metrics) >= 3, f"Expected 3+ sessions, got {len(all_metrics)}"
        
        summary = aggregator.get_system_summary()
        assert summary['total_sessions'] >= 3, f"Expected 3+ sessions in summary"
        assert summary['total_trades_per_minute'] >= 6, "Trades not aggregated"
    
    def test_07_log_levels(self):
        """Test log level filtering"""
        # Write logs at different levels
        self.logger.debug("TestComponent", LogCategory.SYSTEM, "T07 Debug message")
        self.logger.info("TestComponent", LogCategory.SYSTEM, "T07 Info message")
        self.logger.warning("TestComponent", LogCategory.SYSTEM, "T07 Warning message")
        self.logger.error("TestComponent", LogCategory.SYSTEM, "T07 Error message")
        self.logger.critical("TestComponent", LogCategory.SYSTEM, "T07 Critical message")
        
        time.sleep(0.5)
        
        # Verify that ERROR level logs are written (from test_04, we know this works)
        # The key test is that only WARNING+ goes to DB, not DEBUG/INFO
        with self.db_conn.cursor() as cur:
            # Check for ERROR log
            cur.execute("""
                SELECT COUNT(*) as c FROM system_logs 
                WHERE session_id = %s AND message = 'T07 Error message'
            """, (self.test_session_id,))
            row = cur.fetchone()
            error_count = row['c'] if isinstance(row, dict) else row[0]
            assert error_count > 0, "ERROR log not found in database"
            
            # Check that DEBUG is NOT in database
            cur.execute("""
                SELECT COUNT(*) as c FROM system_logs 
                WHERE session_id = %s AND message = 'T07 Debug message'
            """, (self.test_session_id,))
            row = cur.fetchone()
            debug_count = row['c'] if isinstance(row, dict) else row[0]
            assert debug_count == 0, "DEBUG log should not be in database"
            
            # Check that INFO is NOT in database  
            cur.execute("""
                SELECT COUNT(*) as c FROM system_logs 
                WHERE session_id = %s AND message = 'T07 Info message'
            """, (self.test_session_id,))
            row = cur.fetchone()
            info_count = row['c'] if isinstance(row, dict) else row[0]
            assert info_count == 0, "INFO log should not be in database"
    
    def test_08_recent_logs_retrieval(self):
        """Test getting recent logs from Redis"""
        # Write some logs
        for i in range(10):
            self.logger.info(
                "TestComponent",
                LogCategory.TRADE,
                f"Retrieval test {i}"
            )
        
        time.sleep(0.1)
        
        # Get recent logs
        recent = self.logger.get_recent_logs(count=10)
        
        assert len(recent) >= 10, f"Expected 10+ logs, got {len(recent)}"
        assert 'message' in recent[0], "Log entry missing 'message'"
    
    def test_09_postgres_views(self):
        """Test PostgreSQL views"""
        # Write some errors
        for i in range(3):
            self.logger.error(
                "TestComponent",
                LogCategory.SYSTEM,
                f"View test error {i}"
            )
        
        time.sleep(0.2)
        
        # Query v_recent_errors
        with self.db_conn.cursor() as cur:
            cur.execute("SELECT * FROM v_recent_errors LIMIT 10")
            errors = cur.fetchall()
        
        assert len(errors) > 0, "v_recent_errors returned no results"
        
        # Query v_error_summary
        with self.db_conn.cursor() as cur:
            cur.execute("SELECT * FROM v_error_summary")
            summary = cur.fetchall()
        
        assert len(summary) > 0, "v_error_summary returned no results"
    
    def test_10_postgres_functions(self):
        """Test PostgreSQL functions"""
        # Test get_log_statistics
        with self.db_conn.cursor() as cur:
            cur.execute("SELECT * FROM get_log_statistics(24)")
            stats = cur.fetchall()
        
        assert len(stats) > 0, "get_log_statistics returned no results"
        
        # Test search_logs
        with self.db_conn.cursor() as cur:
            cur.execute("SELECT * FROM search_logs('test', 10)")
            results = cur.fetchall()
        
        assert len(results) > 0, "search_logs returned no results"
    
    def run_all_tests(self):
        """Run all tests"""
        self.setup()
        
        # Run tests
        self.run_test("Test 01: LoggingManager Initialization", self.test_01_logging_manager_initialization)
        self.run_test("Test 02: File Logging", self.test_02_file_logging)
        self.run_test("Test 03: Redis Stream Logging", self.test_03_redis_stream_logging)
        self.run_test("Test 04: PostgreSQL Logging", self.test_04_postgres_logging)
        self.run_test("Test 05: Metrics Collector", self.test_05_metrics_collector)
        self.run_test("Test 06: Metrics Aggregator", self.test_06_metrics_aggregator)
        self.run_test("Test 07: Log Level Filtering", self.test_07_log_levels)
        self.run_test("Test 08: Recent Logs Retrieval", self.test_08_recent_logs_retrieval)
        self.run_test("Test 09: PostgreSQL Views", self.test_09_postgres_views)
        self.run_test("Test 10: PostgreSQL Functions", self.test_10_postgres_functions)
        
        # Summary
        print("=" * 100)
        print(f"TEST SUMMARY: {self.passed} passed, {self.failed} failed")
        print("=" * 100)
        
        self.teardown()
        
        return self.failed == 0


if __name__ == "__main__":
    tester = TestD72Logging()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
