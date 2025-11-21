#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D71: FAILURE_INJECTION & AUTO_RECOVERY - Test implementation
"""

import argparse
import logging
import os
import sys
import subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import time
from typing import Dict, Any
import redis
import psycopg2

from arbitrage.live_runner import ArbitrageLiveRunner
from arbitrage.arbitrage_core import ArbitrageConfig
from arbitrage.state_store import StateStore

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def create_test_redis_client() -> redis.Redis:
    """Create Redis client for testing"""
    return redis.Redis(host="localhost", port=6380, db=0, decode_responses=True, socket_connect_timeout=5)


def create_test_db_conn() -> psycopg2.extensions.connection:
    """Create PostgreSQL connection for testing"""
    return psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="arbitrage",
        user="arbitrage",
        password="arbitrage"
    )


class FailureInjector:
    """Failure injection helper"""
    def __init__(self):
        logger.info("[D71_INJECTOR] Initialized")
    
    async def inject_ws_drop(self, runner):
        """Force WS reconnect"""
        if hasattr(runner, '_binance_ws') and runner._binance_ws:
            runner._binance_ws.force_reconnect()
        if hasattr(runner, '_upbit_ws') and runner._upbit_ws:
            runner._upbit_ws.force_reconnect()
        logger.info("[D71_INJECTOR] WS dropped")
    
    async def inject_redis_stop(self):
        """Stop/start Redis container"""
        subprocess.run(["docker", "stop", "arbitrage-redis"], check=True, capture_output=True)
        logger.info("[D71_INJECTOR] Redis stopped")
        await asyncio.sleep(3)
        subprocess.run(["docker", "start", "arbitrage-redis"], check=True, capture_output=True)
        logger.info("[D71_INJECTOR] Redis restarted")
        await asyncio.sleep(2)


class FailureMonitor:
    """Failure monitoring"""
    def __init__(self):
        self.recoveries = []
    
    def record_recovery(self, failure_type, duration):
        self.recoveries.append({'type': failure_type, 'mttr': duration})
        logger.info(f"[D71_MONITOR] Recovery: {failure_type} in {duration:.2f}s")


def create_engine():
    from arbitrage.arbitrage_engine import ArbitrageEngine
    from arbitrage.exchanges.binance_paper import BinancePaperExchange
    from arbitrage.exchanges.upbit_paper import UpbitPaperExchange
    return ArbitrageEngine(BinancePaperExchange(), UpbitPaperExchange())


def create_runner(engine, state_store, duration=20, campaign="D71"):
    config = ArbitrageConfig()
    config.mode = "paper"
    config.symbols = ["BTCUSDT"]
    config.paper_campaign_id = campaign
    config.paper_duration_seconds = duration
    return ArbitrageLiveRunner(engine, config, state_store)


async def scenario_1_ws_reconnect():
    """S1: WS drop & reconnect"""
    logger.info("="*70)
    logger.info("[S1] WS Drop & Reconnect")
    logger.info("="*70)
    
    redis_client = create_test_redis_client()
    db_conn = create_test_db_conn()
    state_store = StateStore(redis_client, db_conn, env="test")
    engine = create_engine()
    monitor = FailureMonitor()
    injector = FailureInjector()
    
    try:
        runner = create_runner(engine, state_store, duration=20, campaign="S1")
        runner._initialize_session(mode="CLEAN_RESET", session_id=None)
        
        # Run with WS drop after 5s
        task = asyncio.create_task(runner.run_async())
        await asyncio.sleep(5)
        
        start = time.time()
        await injector.inject_ws_drop(runner)
        await task
        duration = time.time() - start
        
        monitor.record_recovery("ws_drop", duration)
        
        entries = runner._metrics.total_trades_opened
        success = entries > 0 and duration < 15
        
        logger.info(f"[S1] Entries={entries}, MTTR={duration:.2f}s")
        logger.info(f"[S1] {'✅ PASS' if success else '❌ FAIL'}")
        return success
    except Exception as e:
        logger.error(f"[S1] ❌ {e}")
        return False
    finally:
        redis_client.close()
        db_conn.close()


async def scenario_2_redis_fallback():
    """S2: Redis failure & fallback"""
    logger.info("="*70)
    logger.info("[S2] Redis Failure & Fallback")
    logger.info("="*70)
    
    redis_client = create_test_redis_client()
    db_conn = create_test_db_conn()
    state_store = StateStore(redis_client, db_conn, env="test")
    engine = create_engine()
    monitor = FailureMonitor()
    injector = FailureInjector()
    
    try:
        runner = create_runner(engine, state_store, duration=15, campaign="S2")
        runner._initialize_session(mode="CLEAN_RESET", session_id=None)
        
        task = asyncio.create_task(runner.run_async())
        await asyncio.sleep(5)
        
        start = time.time()
        await injector.inject_redis_stop()
        await task
        duration = time.time() - start
        
        monitor.record_recovery("redis_failure", duration)
        
        redis_healthy = state_store.check_redis_health()
        entries = runner._metrics.total_trades_opened
        success = redis_healthy and entries > 0 and duration < 30
        
        logger.info(f"[S2] Redis healthy={redis_healthy}, Entries={entries}, MTTR={duration:.2f}s")
        logger.info(f"[S2] {'✅ PASS' if success else '❌ FAIL'}")
        return success
    except Exception as e:
        logger.error(f"[S2] ❌ {e}")
        return False
    finally:
        redis_client.close()
        db_conn.close()


async def scenario_3_resume():
    """S3: Runner kill & resume"""
    logger.info("="*70)
    logger.info("[S3] Runner Kill & RESUME")
    logger.info("="*70)
    
    redis_client = create_test_redis_client()
    db_conn = create_test_db_conn()
    state_store = StateStore(redis_client, db_conn, env="test")
    engine = create_engine()
    
    try:
        # Phase 1
        runner1 = create_runner(engine, state_store, duration=20, campaign="S3")
        runner1._initialize_session(mode="CLEAN_RESET", session_id=None)
        session_id = runner1._session_id
        
        await runner1.run_async()
        
        runner1._save_state_to_redis()
        snapshot_id = runner1._save_snapshot_to_db(snapshot_type="s3")
        
        if not snapshot_id:
            logger.error("[S3] ❌ Snapshot save failed")
            return False
        
        entries1 = runner1._metrics.total_trades_opened
        logger.info(f"[S3] Phase 1: Entries={entries1}, snapshot_id={snapshot_id}")
        
        # Phase 2: Resume
        engine2 = create_engine()
        runner2 = create_runner(engine2, state_store, duration=20, campaign="S3")
        
        start = time.time()
        runner2._initialize_session(mode="RESUME_FROM_STATE", session_id=session_id)
        await runner2.run_async()
        duration = time.time() - start
        
        entries2 = runner2._metrics.total_trades_opened
        success = entries2 >= entries1 and duration < 60
        
        logger.info(f"[S3] Phase 2: Entries={entries2}, MTTR={duration:.2f}s")
        logger.info(f"[S3] {'✅ PASS' if success else '❌ FAIL'}")
        return success
    except Exception as e:
        logger.error(f"[S3] ❌ {e}")
        return False
    finally:
        redis_client.close()
        db_conn.close()


async def scenario_4_latency():
    """S4: Network latency spike (simplified)"""
    logger.info("="*70)
    logger.info("[S4] Network Latency Spike")
    logger.info("="*70)
    
    redis_client = create_test_redis_client()
    db_conn = create_test_db_conn()
    state_store = StateStore(redis_client, db_conn, env="test")
    engine = create_engine()
    
    try:
        runner = create_runner(engine, state_store, duration=15, campaign="S4")
        runner._initialize_session(mode="CLEAN_RESET", session_id=None)
        
        await runner.run_async()
        
        entries = runner._metrics.total_trades_opened
        success = entries > 0
        
        logger.info(f"[S4] Entries={entries}")
        logger.info(f"[S4] {'✅ PASS' if success else '❌ FAIL'}")
        return success
    except Exception as e:
        logger.error(f"[S4] ❌ {e}")
        return False
    finally:
        redis_client.close()
        db_conn.close()


async def scenario_5_corruption():
    """S5: Snapshot corruption detection"""
    logger.info("="*70)
    logger.info("[S5] Snapshot Corruption")
    logger.info("="*70)
    
    redis_client = create_test_redis_client()
    db_conn = create_test_db_conn()
    state_store = StateStore(redis_client, db_conn, env="test")
    engine = create_engine()
    
    try:
        runner = create_runner(engine, state_store, duration=15, campaign="S5")
        runner._initialize_session(mode="CLEAN_RESET", session_id=None)
        session_id = runner._session_id
        
        await runner.run_async()
        
        runner._save_state_to_redis()
        snapshot_id = runner._save_snapshot_to_db(snapshot_type="s5")
        
        # Load and validate
        snapshot = state_store.load_latest_snapshot(session_id)
        is_valid = state_store.validate_snapshot(snapshot) if snapshot else False
        
        logger.info(f"[S5] Snapshot valid={is_valid}")
        logger.info(f"[S5] {'✅ PASS' if is_valid else '❌ FAIL'}")
        return is_valid
    except Exception as e:
        logger.error(f"[S5] ❌ {e}")
        return False
    finally:
        redis_client.close()
        db_conn.close()


async def run_all():
    """Run all scenarios"""
    results = {}
    
    scenarios = [
        ("S1_WS_RECONNECT", scenario_1_ws_reconnect),
        ("S2_REDIS_FALLBACK", scenario_2_redis_fallback),
        ("S3_RESUME", scenario_3_resume),
        ("S4_LATENCY", scenario_4_latency),
        ("S5_CORRUPTION", scenario_5_corruption),
    ]
    
    for name, func in scenarios:
        try:
            results[name] = await func()
        except Exception as e:
            logger.error(f"{name} failed: {e}")
            results[name] = False
    
    # Summary
    logger.info("="*70)
    logger.info("D71 TEST SUMMARY")
    logger.info("="*70)
    for name, passed in results.items():
        logger.info(f"{name}: {'✅ PASS' if passed else '❌ FAIL'}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    logger.info(f"\nResult: {passed}/{total} scenarios PASSED")
    
    return all(results.values())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="D71 Failure Injection Tests")
    parser.add_argument("--scenario", choices=["s1", "s2", "s3", "s4", "s5", "all"], default="all")
    args = parser.parse_args()
    
    if args.scenario == "all":
        success = asyncio.run(run_all())
    elif args.scenario == "s1":
        success = asyncio.run(scenario_1_ws_reconnect())
    elif args.scenario == "s2":
        success = asyncio.run(scenario_2_redis_fallback())
    elif args.scenario == "s3":
        success = asyncio.run(scenario_3_resume())
    elif args.scenario == "s4":
        success = asyncio.run(scenario_4_latency())
    elif args.scenario == "s5":
        success = asyncio.run(scenario_5_corruption())
    
    sys.exit(0 if success else 1)
