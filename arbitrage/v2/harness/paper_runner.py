"""
D204-2: Paper Execution Gate Runner

계단식 Paper 테스트 (20m → 1h → 3~12h) 자동 실행

Purpose:
- Opportunity 생성 → OrderIntent 변환 → 모의 실행 → DB ledger 기록
- KPI 자동 집계 (1분 단위)
- Evidence 저장 (logs/evidence/d204_2_{duration}_YYYYMMDD_HHMM/)

Usage:
    python -m arbitrage.v2.harness.paper_runner --duration 20 --phase smoke
    python -m arbitrage.v2.harness.paper_runner --duration 60 --phase baseline
    python -m arbitrage.v2.harness.paper_runner --duration 180 --phase longrun

Author: arbitrage-lite V2
Date: 2025-12-30
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import psutil
except ImportError:
    psutil = None

# V2 imports
from arbitrage.v2.core import OrderIntent, OrderSide, OrderType
from arbitrage.v2.opportunity import (
    BreakEvenParams,
    build_candidate,
    candidate_to_order_intents,
)
from arbitrage.v2.adapters import MockAdapter
from arbitrage.v2.storage import V2LedgerStorage
from arbitrage.v2.utils.timestamp import to_utc_naive, now_utc_naive
from arbitrage.domain.fee_model import FeeModel, FeeStructure
from arbitrage.v2.marketdata.rest.upbit import UpbitRestProvider
from arbitrage.v2.marketdata.rest.binance import BinanceRestProvider
from arbitrage.redis_client import RedisClient
from arbitrage.infrastructure.rate_limiter import TokenBucketRateLimiter, RateLimitConfig
# D205-9-3: FX Provider (D205-8 인프라 재사용)
from arbitrage.v2.core.fx_provider import FixedFxProvider
from arbitrage.v2.core.quote_normalizer import normalize_price_to_krw

import uuid

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PaperRunnerConfig:
    """
    Paper Runner 설정
    
    Attributes:
        duration_minutes: 실행 시간 (분)
        phase: 실행 단계 (smoke/baseline/longrun)
        run_id: 실행 ID (자동 생성: d204_2_20m_YYYYMMDD_HHMM)
        output_dir: Evidence 저장 경로
        symbols_top: Top N 심볼 (기본값: 10)
        db_connection_string: PostgreSQL 연결 문자열
        read_only: READ_ONLY 강제 (기본값: True)
        fx_krw_per_usdt: USDT → KRW 환율 (기본값: 1450.0, D205-9-3)
    """
    duration_minutes: int
    phase: str = "smoke"
    run_id: str = ""
    output_dir: str = ""
    symbols_top: int = 10
    db_connection_string: str = ""
    read_only: bool = True
    db_mode: str = "strict"  # strict/optional/off
    ensure_schema: bool = True  # strict면 강제 True
    use_real_data: bool = False  # D205-9: Real MarketData 사용 여부
    fx_krw_per_usdt: float = 1450.0  # D205-9-3: FX rate (USDT → KRW)
    
    def __post_init__(self):
        """자동 생성: run_id, output_dir"""
        if not self.run_id:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            self.run_id = f"d204_2_{self.phase}_{timestamp}"
        
        if not self.output_dir:
            self.output_dir = f"logs/evidence/{self.run_id}"
        
        if not self.db_connection_string:
            self.db_connection_string = os.getenv(
                "POSTGRES_CONNECTION_STRING",
                "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage"
            )
        
        # strict mode면 ensure_schema 강제
        if self.db_mode == "strict":
            self.ensure_schema = True


@dataclass
class MockBalance:
    """Mock 잔고 관리"""
    balances: Dict[str, float] = field(default_factory=lambda: {
        "KRW": 10_000_000.0,  # 1천만원
        "USDT": 10_000.0,     # 1만 USDT
        "BTC": 0.0,
        "ETH": 0.0,
    })
    
    def get(self, currency: str) -> float:
        """잔고 조회"""
        return self.balances.get(currency, 0.0)
    
    def update(self, currency: str, amount: float):
        """잔고 업데이트 (증가/감소)"""
        self.balances[currency] = self.balances.get(currency, 0.0) + amount


@dataclass
class KPICollector:
    """KPI 수집기"""
    start_time: float = field(default_factory=time.time)
    opportunities_generated: int = 0
    intents_created: int = 0
    mock_executions: int = 0
    db_inserts_ok: int = 0
    db_inserts_failed: int = 0
    error_count: int = 0
    errors: List[str] = field(default_factory=list)
    db_last_error: str = ""
    memory_mb: float = 0.0
    cpu_pct: float = 0.0
    
    # D205-3: PnL 필드 추가
    closed_trades: int = 0
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    fees: float = 0.0
    wins: int = 0
    losses: int = 0
    winrate_pct: float = 0.0
    
    # D205-9: Real MarketData 증거 필드
    marketdata_mode: str = "MOCK"  # MOCK or REAL
    upbit_marketdata_ok: bool = False
    binance_marketdata_ok: bool = False
    real_ticks_ok_count: int = 0
    real_ticks_fail_count: int = 0
    
    # D205-9 RECOVERY: Redis 지표
    redis_ok: bool = False
    ratelimit_hits: int = 0
    dedup_hits: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """KPI를 dict로 변환"""
        duration_seconds = time.time() - self.start_time
        
        kpi = {
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "duration_seconds": round(duration_seconds, 2),
            "duration_minutes": round(duration_seconds / 60, 2),
            "opportunities_generated": self.opportunities_generated,
            "intents_created": self.intents_created,
            "mock_executions": self.mock_executions,
            "db_inserts_ok": self.db_inserts_ok,
            "db_inserts_failed": self.db_inserts_failed,
            "error_count": self.error_count,
            "errors": self.errors[:10],  # 최대 10개만
            "db_last_error": self.db_last_error,
            "memory_mb": self.memory_mb,
            "cpu_pct": self.cpu_pct,
            # D205-3: PnL 필드
            "closed_trades": self.closed_trades,
            "gross_pnl": round(self.gross_pnl, 2),
            "net_pnl": round(self.net_pnl, 2),
            "fees": round(self.fees, 2),
            "wins": self.wins,
            "losses": self.losses,
            "winrate_pct": round(self.winrate_pct, 2),
            # D205-9: Real MarketData 증거
            "marketdata_mode": self.marketdata_mode,
            "upbit_marketdata_ok": self.upbit_marketdata_ok,
            "binance_marketdata_ok": self.binance_marketdata_ok,
            "real_ticks_ok_count": self.real_ticks_ok_count,
            "real_ticks_fail_count": self.real_ticks_fail_count,
            # D205-9 RECOVERY: Redis 지표
            "redis_ok": self.redis_ok,
            "ratelimit_hits": self.ratelimit_hits,
            "dedup_hits": self.dedup_hits,
        }
        
        # 시스템 메트릭 (psutil 있으면)
        if psutil:
            process = psutil.Process()
            kpi["memory_mb"] = round(process.memory_info().rss / 1024 / 1024, 2)
            kpi["cpu_pct"] = round(process.cpu_percent(interval=0.1), 2)
        
        return kpi


class PaperRunner:
    """
    Paper Execution Gate Runner
    
    Flow:
        1. Opportunity 생성 (Mock 가격)
        2. OrderIntent 변환 (candidate_to_order_intents)
        3. 모의 실행 (MockAdapter)
        4. DB 기록 (V2LedgerStorage)
        5. KPI 집계 (1분 단위)
    """
    
    def __init__(self, config: PaperRunnerConfig):
        """
        Initialize Paper Runner
        
        Args:
            config: Paper Runner 설정
        """
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # V2 Components
        self.mock_adapter = MockAdapter(exchange_name="mock_paper")
        self.balance = MockBalance()
        self.kpi = KPICollector()
        
        # D205-9: Real MarketData Providers (BOTH Upbit + Binance REQUIRED)
        self.use_real_data = config.use_real_data
        if self.use_real_data:
            logger.info("[D205-9] Real MarketData mode: Initializing Upbit + Binance providers...")
            
            # Upbit Provider (retry 3회)
            upbit_ok = False
            for attempt in range(1, 4):
                try:
                    self.upbit_provider = UpbitRestProvider(timeout=15.0)
                    # 연결 테스트
                    test_ticker = self.upbit_provider.get_ticker("BTC/KRW")
                    if test_ticker and test_ticker.last > 0:
                        logger.info(f"[D205-9] ✅ Upbit Provider initialized (attempt {attempt}/3, price={test_ticker.last:.0f} KRW)")
                        upbit_ok = True
                        self.kpi.upbit_marketdata_ok = True
                        break
                    else:
                        logger.warning(f"[D205-9] ⚠️ Upbit ticker invalid (attempt {attempt}/3)")
                except Exception as e:
                    logger.warning(f"[D205-9] ⚠️ Upbit init failed (attempt {attempt}/3): {e}")
                    if attempt < 3:
                        time.sleep(2 ** attempt)  # backoff: 2s, 4s, 8s
            
            if not upbit_ok:
                logger.error("[D205-9] ❌ CRITICAL: Upbit Provider init FAILED after 3 attempts")
                raise RuntimeError("Upbit Provider initialization failed (required for D205-9)")
            
            # Binance Provider (retry 3회)
            binance_ok = False
            for attempt in range(1, 4):
                try:
                    self.binance_provider = BinanceRestProvider(timeout=15.0)
                    # 연결 테스트
                    test_ticker = self.binance_provider.get_ticker("BTC/USDT")
                    if test_ticker and test_ticker.last > 0:
                        logger.info(f"[D205-9] ✅ Binance Provider initialized (attempt {attempt}/3, price={test_ticker.last:.2f} USDT)")
                        binance_ok = True
                        self.kpi.binance_marketdata_ok = True
                        break
                    else:
                        logger.warning(f"[D205-9] ⚠️ Binance ticker invalid (attempt {attempt}/3)")
                except Exception as e:
                    logger.warning(f"[D205-9] ⚠️ Binance init failed (attempt {attempt}/3): {e}")
                    if attempt < 3:
                        time.sleep(2 ** attempt)  # backoff: 2s, 4s, 8s
            
            if not binance_ok:
                logger.error("[D205-9] ❌ CRITICAL: Binance Provider init FAILED after 3 attempts")
                raise RuntimeError("Binance Provider initialization failed (required for D205-9)")
            
            # BOTH OK: Real Data 모드 확정
            self.kpi.marketdata_mode = "REAL"
            logger.info("[D205-9] ✅ Real MarketData mode: BOTH Upbit + Binance initialized")
            
        else:
            self.upbit_provider = None
            self.binance_provider = None
            self.kpi.marketdata_mode = "MOCK"
            logger.info("[D204-2] Mock Data mode")
        
        # D205-2 REOPEN: trade tracking (opportunity 단위)
        self.open_trades: Dict[str, Dict[str, Any]] = {}  # trade_id -> {entry_*, candidate, orders_executed}
        
        # D205-9-3: FX Provider 초기화 (D205-8 인프라 재사용)
        self.fx_provider = FixedFxProvider(fx_krw_per_usdt=config.fx_krw_per_usdt)
        logger.info(f"[D205-9-3] ✅ FX Provider initialized: {config.fx_krw_per_usdt} KRW/USDT")
        
        # FX Safety Guard (1300원 참사 방지)
        if config.fx_krw_per_usdt < 1000 or config.fx_krw_per_usdt > 2000:
            raise ValueError(
                f"🚨 FATAL: Suspicious FX rate {config.fx_krw_per_usdt} KRW/USDT!\n"
                f"Expected range: 1000~2000 (typical: 1300~1500).\n"
                f"This safeguard prevents '1300원 참사' (wrong FX orders)."
            )
        
        # D205-9 RECOVERY: Redis REQUIRED (SSOT_DATA_ARCHITECTURE 준수)
        logger.info("[D205-9 RECOVERY] Initializing Redis (REQUIRED for Paper/Live)")
        redis_config = {
            "enabled": True,
            "url": "redis://localhost:6379/0",
            "prefix": f"v2:{config.run_id}",
            "health_ttl_seconds": 60,
        }
        try:
            self.redis = RedisClient(redis_config)
            if not self.redis.available:
                raise RuntimeError("Redis connection failed (REQUIRED)")
            self.kpi.redis_ok = True
            logger.info(f"[D205-9 RECOVERY] ✅ Redis initialized: {redis_config['url']}")
        except Exception as e:
            logger.error(f"[D205-9 RECOVERY] ❌ CRITICAL: Redis init failed: {e}")
            raise RuntimeError(f"Redis REQUIRED for Paper mode (SSOT violation): {e}")
        
        # D205-9 RECOVERY: RateLimit (Upbit/Binance)
        self.rate_limiter_upbit = TokenBucketRateLimiter(
            RateLimitConfig(max_requests=10, window_seconds=1.0, burst_allowance=5)
        )
        self.rate_limiter_binance = TokenBucketRateLimiter(
            RateLimitConfig(max_requests=20, window_seconds=1.0, burst_allowance=10)
        )
        logger.info("[D205-9 RECOVERY] ✅ RateLimit initialized (Upbit: 10req/s, Binance: 20req/s)")
        
        # D205-9 RECOVERY: Dedup tracking
        self.dedup_hits = 0
        logger.info("[D205-9 RECOVERY] ✅ Dedup tracking initialized")
        
        # V2 Storage (PostgreSQL) - D204-2 REOPEN: strict mode
        if config.db_mode == "off":
            logger.info(f"[D204-2] DB mode: OFF (no DB operations)")
            self.storage = None
        else:
            try:
                self.storage = V2LedgerStorage(config.db_connection_string)
                logger.info(f"[D204-2] V2LedgerStorage initialized: {config.db_connection_string}")
                
                # strict mode: 스키마 체크 필수
                if config.ensure_schema:
                    self._verify_schema()
                    
            except Exception as e:
                error_msg = f"V2LedgerStorage init failed: {e}"
                logger.error(f"[D204-2] {error_msg}")
                
                if config.db_mode == "strict":
                    logger.error(f"[D204-2] ❌ FAIL: DB mode is strict, cannot continue")
                    raise RuntimeError(f"DB init failed in strict mode: {e}")
                else:
                    logger.warning(f"[D204-2] DB mode: optional, will skip DB operations")
                    self.storage = None
        
        # BreakEvenParams (기본값)
        # FeeStructure + FeeModel 생성 (V1 재사용)
        fee_a = FeeStructure(
            exchange_name="upbit",
            maker_fee_bps=5.0,   # 0.05%
            taker_fee_bps=25.0,  # 0.25%
        )
        fee_b = FeeStructure(
            exchange_name="binance",
            maker_fee_bps=10.0,  # 0.10%
            taker_fee_bps=25.0,  # 0.25%
        )
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        # Break-even params (D205-9-1: latency_bps 추가)
        self.break_even_params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=15.0,   # 15 bps (0.15%) - D205-9 RECOVERY 현실화
            latency_bps=10.0,    # 10 bps (0.1%) - D205-9-1 추가
            buffer_bps=5.0,      # 5 bps safety buffer
        )
        
        logger.info(f"[D204-2] PaperRunner initialized")
        logger.info(f"[D204-2] run_id: {config.run_id}")
        logger.info(f"[D204-2] output_dir: {self.output_dir}")
        logger.info(f"[D204-2] duration: {config.duration_minutes} min")
        logger.info(f"[D204-2] db_mode: {config.db_mode}")
        logger.info(f"[D204-2] ensure_schema: {config.ensure_schema}")
    
    def _verify_schema(self):
        """스키마 검증 (strict mode)"""
        required_tables = ["v2_orders", "v2_fills", "v2_trades"]
        
        try:
            # V2LedgerStorage는 connection pool 사용, _execute_query() 메서드로 쿼리 실행
            for table_name in required_tables:
                query = "SELECT to_regclass(%s) IS NOT NULL AS exists"
                
                # 직접 psycopg2 연결 사용
                import psycopg2
                conn = psycopg2.connect(self.config.db_connection_string)
                try:
                    with conn.cursor() as cur:
                        cur.execute(query, (f"public.{table_name}",))
                        row = cur.fetchone()
                        exists = row[0] if row else False
                        
                        if not exists:
                            raise RuntimeError(f"Required table '{table_name}' does not exist")
                        
                        logger.info(f"[D204-2] ✅ {table_name} exists")
                finally:
                    conn.close()
            
            logger.info(f"[D204-2] Schema verification: PASS")
            
        except Exception as e:
            logger.error(f"[D204-2] Schema verification: FAIL - {e}")
            raise
    
    def run(self):
        """
        메인 실행 루프 (Duration-based)
        
        Returns:
            0: 성공
            1: 실패
        """
        if not self.config.read_only:
            logger.error("[D204-2] ❌ READ_ONLY=False 금지 (Paper 전용)")
            return 1
        
        logger.info("[D204-2] ========================================")
        logger.info(f"[D204-2] PAPER EXECUTION GATE - {self.config.phase.upper()}")
        logger.info("[D204-2] ========================================")
        
        start_time = time.time()
        end_time = start_time + (self.config.duration_minutes * 60)
        iteration = 0
        
        try:
            while time.time() < end_time:
                iteration += 1
                logger.info(f"[D204-2] Iteration {iteration} (elapsed: {int(time.time() - start_time)}s)")
                
                # 1. Opportunity 생성 (Real or Mock 가격)
                if self.use_real_data:
                    candidate = self._generate_real_opportunity(iteration)
                else:
                    candidate = self._generate_mock_opportunity(iteration)
                if candidate:
                    self.kpi.opportunities_generated += 1
                    
                    # 2. OrderIntent 변환
                    intents = self._convert_to_intents(candidate)
                    self.kpi.intents_created += len(intents)
                    
                    # D205-2 REOPEN: opportunity 단위 trade 처리 (entry + exit)
                    # D205-9: Fake-Optimism 감지 시 즉시 종료
                    exit_code = self._process_opportunity_as_trade(candidate, intents)
                    if exit_code == 1:
                        logger.error("[D205-9] Fake-Optimism detected, exiting loop immediately")
                        return 1
                
                # 1분 단위 KPI 출력
                if iteration % 10 == 0:
                    logger.info(f"[D204-2 KPI] {self.kpi.to_dict()}")
                
                # 1초 대기 (CPU 부하 방지)
                time.sleep(1.0)
            
            # 종료 시 KPI 저장
            self._save_kpi()
            self._save_db_counts()
            
            logger.info("[D204-2] ========================================")
            logger.info(f"[D204-2] PAPER EXECUTION GATE - {self.config.phase.upper()} COMPLETE")
            logger.info("[D204-2] ========================================")
            logger.info(f"[D204-2 FINAL KPI] {self.kpi.to_dict()}")
            
            return 0
        
        except KeyboardInterrupt:
            logger.warning("[D204-2] Interrupted by user (Ctrl+C)")
            self._save_kpi()
            self._save_db_counts()
            return 1
        
        except Exception as e:
            logger.error(f"[D204-2] Fatal error: {e}", exc_info=True)
            self.kpi.errors.append(str(e))
            self._save_kpi()
            self._save_db_counts()
            return 1
        
        # D205-9: DB REQUIRED 검증 (strict mode)
        if self.config.db_mode == "strict":
            if self.storage and self.kpi.db_inserts_ok == 0:
                logger.error("[D205-9] ❌ FAIL: DB mode is strict, but db_inserts_ok = 0 (no ledger growth)")
                self._save_kpi()
                self._save_db_counts()
                return 1
        
        # 성공 종료
        logger.info("[D204-2] ========================================")
        logger.info(f"[D204-2] PAPER EXECUTION GATE - {self.config.phase.upper()} - SUCCESS")
        logger.info("[D204-2] ========================================")
        self._save_kpi()
        self._save_db_counts()
        return 0
    
    def _generate_real_opportunity(self, iteration: int):
        """Real MarketData 기반 Opportunity 생성 (D205-9)
        
        REQUIRED: Upbit + Binance BOTH OK
        - Market Data: Upbit BTC/KRW + Binance BTC/USDT (REAL)
        - Execution: Paper (simulated)
        - Spread: Real spread between Upbit/Binance prices
        """
        try:
            # Defensive: 둘 다 None이면 즉시 에러
            if self.upbit_provider is None or self.binance_provider is None:
                logger.error(f"[D205-9] ❌ CRITICAL: provider is None (upbit={self.upbit_provider}, binance={self.binance_provider})")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            # D205-9 RECOVERY: RateLimit 체크 (Upbit)
            if not self.rate_limiter_upbit.consume(weight=1):
                self.kpi.ratelimit_hits += 1
                if iteration % 10 == 1:  # spam 방지
                    logger.warning(f"[D205-9 RECOVERY] ⚠️ Upbit RateLimit exceeded")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            # Real 시세 조회 (Upbit BTC/KRW)
            ticker_upbit = self.upbit_provider.get_ticker("BTC/KRW")
            if not ticker_upbit or ticker_upbit.last <= 0:
                if iteration % 10 == 1:  # spam 방지
                    logger.warning(f"[D205-9] ❌ Upbit ticker fetch failed")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            # D205-9 RECOVERY: RateLimit 체크 (Binance)
            if not self.rate_limiter_binance.consume(weight=1):
                self.kpi.ratelimit_hits += 1
                if iteration % 10 == 1:  # spam 방지
                    logger.warning(f"[D205-9 RECOVERY] ⚠️ Binance RateLimit exceeded")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            # Real 시세 조회 (Binance BTC/USDT)
            ticker_binance = self.binance_provider.get_ticker("BTC/USDT")
            if not ticker_binance or ticker_binance.last <= 0:
                if iteration % 10 == 1:  # spam 방지
                    logger.warning(f"[D205-9] ❌ Binance ticker fetch failed")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            # 가격 범위 확인 (Mock 의심 감지)
            if ticker_upbit.last < 50_000_000 or ticker_upbit.last > 200_000_000:
                logger.error(f"[D205-9] ❌ Upbit price suspicious: {ticker_upbit.last:.0f} KRW (expected 50M~200M)")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            if ticker_binance.last < 20_000 or ticker_binance.last > 150_000:
                logger.error(f"[D205-9] ❌ Binance price suspicious: {ticker_binance.last:.2f} USDT (expected 20k~150k)")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            # Real Data 확인 로그 (첫 iteration만)
            if iteration == 1:
                logger.info(f"[D205-9] ✅ Real Upbit price: {ticker_upbit.last:,.0f} KRW")
                logger.info(f"[D205-9] ✅ Real Binance price: {ticker_binance.last:.2f} USDT")
            
            # D205-9-3: FX Provider 사용 (하드코딩 제거)
            fx_rate = self.fx_provider.get_fx_rate("USDT", "KRW")
            
            # D205-9-3: Quote Normalizer로 통화 정규화
            price_a = ticker_upbit.last  # KRW (이미 정규화됨)
            price_b_usdt = ticker_binance.last  # USDT (원본)
            price_b = normalize_price_to_krw(price_b_usdt, "USDT", fx_rate)
            
            if iteration == 1:
                logger.info(f"[D205-9-3] ✅ FX rate: {fx_rate} KRW/USDT")
                logger.info(f"[D205-9-3] ✅ Normalized Binance: {price_b:,.0f} KRW (from {price_b_usdt:.2f} USDT)")
            
            candidate = build_candidate(
                symbol="BTC/KRW",
                exchange_a="upbit",
                exchange_b="binance",
                price_a=price_a,
                price_b=price_b,
                params=self.break_even_params,
            )
            
            self.kpi.real_ticks_ok_count += 1
            return candidate
            
        except Exception as e:
            logger.warning(f"[D205-9] Real opportunity generation failed: {e}")
            self.kpi.errors.append(f"real_opportunity: {e}")
            self.kpi.real_ticks_fail_count += 1
            return None
    
    def _generate_mock_opportunity(self, iteration: int):
        """
        Mock Opportunity 생성 (가상 가격)
        
        D205-9-3: FX Provider 적용 (Mock mode에서도 통화 정규화 일관성 유지)
        """
        # Mock 가격 (iteration 기반으로 변동)
        base_price_a_krw = 50_000_000.0  # Upbit BTC/KRW
        base_price_b_usdt = 40_000.0      # Binance BTC/USDT
        
        # D205-9-3: FX Provider로 통화 정규화
        fx_rate = self.fx_provider.get_fx_rate("USDT", "KRW")
        base_price_b_krw = normalize_price_to_krw(base_price_b_usdt, "USDT", fx_rate)
        
        # 스프레드 시뮬레이션 (0.3%~0.5% 변동)
        spread_pct = 0.003 + (iteration % 10) * 0.0002
        price_a = base_price_a_krw * (1 + spread_pct / 2)
        price_b = base_price_b_krw * (1 - spread_pct / 2)
        
        try:
            candidate = build_candidate(
                symbol="BTC/KRW",
                exchange_a="upbit",
                exchange_b="binance",
                price_a=price_a,
                price_b=price_b,
                params=self.break_even_params,
            )
            return candidate
        except Exception as e:
            logger.warning(f"[D204-2] Failed to build candidate: {e}")
            self.kpi.errors.append(f"build_candidate: {e}")
            return None
    
    def _convert_to_intents(self, candidate) -> List[OrderIntent]:
        """OpportunityCandidate → OrderIntent 변환"""
        try:
            intents = candidate_to_order_intents(
                candidate=candidate,
                base_qty=0.01,  # 0.01 BTC
                quote_amount=500_000.0,  # 50만원
                order_type=OrderType.MARKET,
            )
            return intents
        except Exception as e:
            logger.error(f"[D204-2] Failed to convert to intents: {e}", exc_info=True)
            self.kpi.errors.append(f"candidate_to_order_intents: {e}")
            return []
    
    def _execute_order(self, intent: OrderIntent):
        """Mock 주문 실행 (DB 기록 없이 순수 실행만)
        
        D205-2 REOPEN: trade close를 위해 분리
        """
        # 1. MockAdapter로 변환
        payload = self.mock_adapter.translate_intent(intent)
        
        # 2. Mock 체결 (항상 성공)
        response = self.mock_adapter.submit_order(payload)
        order_result = self.mock_adapter.parse_response(response)
        
        # 3. KPI 업데이트
        self.kpi.mock_executions += 1
        
        return order_result
    
    def _execute_mock_order(self, intent: OrderIntent):
        """Mock 주문 실행 + DB 기록"""
        try:
            # 1. MockAdapter로 변환
            payload = self.mock_adapter.translate_intent(intent)
            
            # 2. Mock 체결 (항상 성공)
            response = self.mock_adapter.submit_order(payload)
            order_result = self.mock_adapter.parse_response(response)
            
            # 3. Balance 업데이트 (Mock)
            self._update_mock_balance(intent, order_result)
            
            # 4. DB 기록 (V2LedgerStorage)
            if self.storage:
                self._record_to_db(intent, order_result)
                self.kpi.db_inserts_ok += 1
            
            logger.debug(f"[D204-2] Mock executed: {order_result.order_id}")
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[D204-2] Failed to execute mock order: {error_msg}")
            self.kpi.error_count += 1
            self.kpi.errors.append(f"execute_mock_order: {error_msg}")
            self.kpi.db_last_error = error_msg
            
            # strict mode: DB insert 실패 시 즉시 종료
            if self.config.db_mode == "strict" and "relation" in error_msg:
                logger.error(f"[D204-2] ❌ FAIL: DB insert failed in strict mode")
                raise RuntimeError(f"DB insert failed in strict mode: {error_msg}")
            self.kpi.db_inserts_failed += 1
    
    def _update_mock_balance(self, intent: OrderIntent, order_result):
        """Mock Balance 업데이트"""
        if intent.side == OrderSide.BUY:
            # BUY: KRW/USDT 차감, BTC/ETH 증가
            if "KRW" in intent.symbol:
                self.balance.update("KRW", -intent.quote_amount)
                self.balance.update("BTC", order_result.filled_qty or 0.01)
            else:
                self.balance.update("USDT", -intent.quote_amount)
                self.balance.update("BTC", order_result.filled_qty or 0.01)
        else:
            # SELL: BTC/ETH 차감, KRW/USDT 증가
            if "KRW" in intent.symbol:
                self.balance.update("BTC", -(intent.base_qty or 0.01))
                self.balance.update("KRW", (order_result.filled_qty or 0.01) * (order_result.filled_price or 50_000_000.0))
            else:
                self.balance.update("BTC", -(intent.base_qty or 0.01))
                self.balance.update("USDT", (order_result.filled_qty or 0.01) * (order_result.filled_price or 40_000.0))
    
    def _record_to_db(self, intent: OrderIntent, order_result):
        """DB 기록 (v2_orders, v2_fills, v2_trades)
        
        D205-1 Hotfix:
        - insert_order + insert_fill + insert_trade (리포팅 재료 확보)
        - KPI db_inserts_ok = 실제 rows inserted (중복 카운트 제거)
        """
        timestamp = datetime.now(timezone.utc)
        rows_inserted = 0
        
        if not self.storage:
            return
        
        try:
            # 1. v2_orders 기록
            self.storage.insert_order(
                run_id=self.config.run_id,
                order_id=order_result.order_id,
                timestamp=timestamp,
                exchange=intent.exchange,
                symbol=intent.symbol,
                side=intent.side.value,
                order_type=intent.order_type.value,
                quantity=intent.base_qty or order_result.filled_qty,
                price=intent.quote_amount or order_result.filled_price,
                status="filled",
                route_id=intent.route_id,
                strategy_id=intent.strategy_id or "d204_2_paper",
            )
            rows_inserted += 1
            
            # 2. v2_fills 기록 (D205-1 Hotfix: 리포팅 재료)
            # fee 계산: FeeModel 활용 (taker_fee_bps)
            filled_qty = order_result.filled_qty or intent.base_qty or 0.01
            filled_price = order_result.filled_price or intent.limit_price or 50_000_000.0
            
            # exchange별 fee_bps (self.break_even_params.fee_model 사용)
            if intent.exchange == "upbit":
                fee_bps = self.break_even_params.fee_model.fee_a.taker_fee_bps
            else:
                fee_bps = self.break_even_params.fee_model.fee_b.taker_fee_bps
            
            # fee 계산: filled_qty * filled_price * fee_bps / 10000
            fee = filled_qty * filled_price * fee_bps / 10000.0
            fee_currency = "KRW" if "KRW" in intent.symbol else "USDT"
            
            # D205-2 REOPEN-2: uuid4 기반 fill_id (충돌 제거)
            fill_id = f"{order_result.order_id}_fill_{uuid.uuid4().hex[:8]}"
            
            self.storage.insert_fill(
                run_id=self.config.run_id,
                order_id=order_result.order_id,
                fill_id=fill_id,
                timestamp=timestamp,
                exchange=intent.exchange,
                symbol=intent.symbol,
                side=intent.side.value,
                filled_quantity=filled_qty,
                filled_price=filled_price,
                fee=fee,
                fee_currency=fee_currency,
            )
            rows_inserted += 1
            
            # 3. v2_trades 기록 (D205-1 Hotfix: 리포팅 재료)
            # 단일 주문 → trade entry로 기록 (exit은 나중에)
            # D205-2 REOPEN-2: uuid4 기반 trade_id (초 단위 충돌 제거)
            trade_id = f"trade_{self.config.run_id}_{uuid.uuid4().hex[:8]}"
            
            self.storage.insert_trade(
                run_id=self.config.run_id,
                trade_id=trade_id,
                timestamp=timestamp,
                entry_exchange=intent.exchange,
                entry_symbol=intent.symbol,
                entry_side=intent.side.value,
                entry_order_id=order_result.order_id,
                entry_quantity=filled_qty,
                entry_price=filled_price,
                entry_timestamp=timestamp,
                status="open",  # paper에서는 즉시 entry만
                total_fee=fee,
                route_id=intent.route_id,
                strategy_id=intent.strategy_id or "d204_2_paper",
            )
            rows_inserted += 1
            
            # KPI: 실제 insert rows 수 (order + fill + trade = 3)
            self.kpi.db_inserts_ok += rows_inserted
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[D204-2] Failed to record to DB: {error_msg}")
            self.kpi.error_count += 1
            self.kpi.errors.append(f"record_to_db: {error_msg}")
            self.kpi.db_last_error = error_msg
            
            # strict mode: DB insert 실패 시 즉시 종료
            if self.config.db_mode == "strict":
                logger.error(f"[D204-2] ❌ FAIL: DB insert failed in strict mode")
                raise RuntimeError(f"DB insert failed in strict mode: {error_msg}")
            
            self.kpi.db_inserts_failed += rows_inserted  # 실패한 rows 수
    
    def _process_opportunity_as_trade(
        self,
        candidate,
        intents: List[OrderIntent],
    ):
        """
        D205-2 REOPEN: Opportunity를 하나의 trade로 처리 (entry + exit)
        
        Args:
            candidate: OpportunityCandidate
            intents: 2개의 OrderIntent (entry, exit)
        
        Flow:
            1. 첫 번째 order: entry 기록 (trade status=open)
            2. 두 번째 order: exit 기록 + trade close (status=closed, realized_pnl 계산)
        """
        if len(intents) != 2:
            logger.warning(f"[D205-2] Expected 2 intents, got {len(intents)}")
            # Fallback: 기존 로직
            for intent in intents:
                order_result = self._execute_order(intent)
                self._update_mock_balance(intent, order_result)
            return
        
        # D205-2 REOPEN-2: UTC naive timestamp + uuid4 기반 trade_id
        timestamp = now_utc_naive()
        trade_id = f"trade_{self.config.run_id}_{uuid.uuid4().hex[:8]}"
        
        # Entry order (첫 번째)
        entry_intent = intents[0]
        entry_result = self._execute_order(entry_intent)
        self._update_mock_balance(entry_intent, entry_result)
        
        # Exit order (두 번째)
        exit_intent = intents[1]
        exit_result = self._execute_order(exit_intent)
        self._update_mock_balance(exit_intent, exit_result)
        
        # DB 기록 (entry + exit + trade close)
        self._record_trade_complete(
            trade_id=trade_id,
            candidate=candidate,
            entry_intent=entry_intent,
            entry_result=entry_result,
            exit_intent=exit_intent,
            exit_result=exit_result,
            timestamp=timestamp,
        )
        
        # D205-9: Fake-Optimism 즉시중단 룰 (winrate 100% 감지)
        # NOTE: Real Data 모드에서만 체크 (Mock 모드는 테스트/개발용이므로 100% winrate 허용)
        if self.use_real_data and self.kpi.closed_trades >= 50 and self.kpi.winrate_pct >= 99.9:
            logger.error("[D205-9] ❌ FAIL: Fake-Optimism detected (winrate 100% after 50+ trades)")
            logger.error(f"[D205-9] closed_trades={self.kpi.closed_trades}, wins={self.kpi.wins}, losses={self.kpi.losses}")
            logger.error("[D205-9] Reason: Unrealistic winrate indicates model does not reflect reality")
            
            # 마지막 K개 트레이드 요약 덤프 (evidence)
            last_trades_summary = {
                "closed_trades": self.kpi.closed_trades,
                "wins": self.kpi.wins,
                "losses": self.kpi.losses,
                "winrate_pct": self.kpi.winrate_pct,
                "gross_pnl": self.kpi.gross_pnl,
                "fees": self.kpi.fees,
                "net_pnl": self.kpi.net_pnl,
                "fake_optimism_trigger": "winrate >= 99.9% after 50+ trades",
            }
            
            # evidence 저장
            fake_optimism_file = self.output_dir / "fake_optimism_trigger.json"
            with open(fake_optimism_file, "w", encoding="utf-8") as f:
                json.dump(last_trades_summary, f, indent=2)
            
            logger.error(f"[D205-9] Fake-Optimism evidence saved: {fake_optimism_file}")
            
            self._save_kpi()
            self._save_db_counts()
            return 1
    
    def _record_trade_complete(
        self,
        trade_id: str,
        candidate,
        entry_intent: OrderIntent,
        entry_result,
        exit_intent: OrderIntent,
        exit_result,
        timestamp: datetime,
    ):
        """
        D205-2 REOPEN: 완전한 trade 기록 (entry + exit + close)
        
        Args:
            trade_id: Trade ID
            candidate: OpportunityCandidate
            entry_intent: Entry order intent
            entry_result: Entry order result
            exit_intent: Exit order intent
            exit_result: Exit order result
            timestamp: Trade timestamp
        """
        rows_inserted = 0
        
        try:
            # Entry order
            # D205-2 REOPEN-2: uuid4 기반 order_id (충돌 제거)
            order_id = f"order_{self.config.run_id}_{uuid.uuid4().hex[:8]}_entry"
            entry_qty = entry_result.filled_qty or entry_intent.base_qty or 0.01
            entry_base_price = entry_result.filled_price or entry_intent.limit_price or 50_000_000.0
            
            # D205-9-1: Execution-Risk Fill Model (가격 왜곡)
            # BUY: 슬리피지+레이턴시로 인해 더 비싸게 체결
            # SELL: 슬리피지+레이턴시로 인해 더 싸게 체결
            slippage_bps = self.break_even_params.slippage_bps
            latency_bps = self.break_even_params.latency_bps
            execution_risk_bps = slippage_bps + latency_bps
            
            if entry_intent.side.value.upper() == "BUY":
                entry_price = entry_base_price * (1 + execution_risk_bps / 10000.0)
            else:  # SELL
                entry_price = entry_base_price * (1 - execution_risk_bps / 10000.0)
            
            # Entry fee
            if entry_intent.exchange == "upbit":
                entry_fee_bps = self.break_even_params.fee_model.fee_a.taker_fee_bps
            else:
                entry_fee_bps = self.break_even_params.fee_model.fee_b.taker_fee_bps
            entry_fee = entry_qty * entry_price * entry_fee_bps / 10000.0
            entry_fee_currency = "KRW" if "KRW" in entry_intent.symbol else "USDT"
            
            # Exit order
            # D205-2 REOPEN-2: uuid4 기반 order_id (충돌 제거)
            order_id_exit = f"order_{self.config.run_id}_{uuid.uuid4().hex[:8]}_exit"
            exit_qty = exit_result.filled_qty or exit_intent.base_qty or 0.01
            exit_base_price = exit_result.filled_price or exit_intent.limit_price or 50_000_000.0
            
            # D205-9-1: Execution-Risk Fill Model (가격 왜곡)
            if exit_intent.side.value.upper() == "BUY":
                exit_price = exit_base_price * (1 + execution_risk_bps / 10000.0)
            else:  # SELL
                exit_price = exit_base_price * (1 - execution_risk_bps / 10000.0)
            
            # Exit fee
            if exit_intent.exchange == "upbit":
                exit_fee_bps = self.break_even_params.fee_model.fee_a.taker_fee_bps
            else:
                exit_fee_bps = self.break_even_params.fee_model.fee_b.taker_fee_bps
            exit_fee = exit_qty * exit_price * exit_fee_bps / 10000.0
            exit_fee_currency = "KRW" if "KRW" in exit_intent.symbol else "USDT"
            
            total_fee = entry_fee + exit_fee
            
            # D205-9-1: realized_pnl 계산 (Arbitrage 방향 고려)
            # entry/exit fill price에 execution_risk(슬리피지+레이턴시)가 이미 반영되어 있음
            # intents[0] = entry (BUY exchange), intents[1] = exit (SELL exchange)
            if entry_intent.side.value.upper() == "BUY" and exit_intent.side.value.upper() == "SELL":
                # Normal arbitrage: BUY at entry_price, SELL at exit_price
                # profit = (SELL price - BUY price) * qty - fees
                gross_pnl = (exit_price - entry_price) * entry_qty
            elif entry_intent.side.value.upper() == "SELL" and exit_intent.side.value.upper() == "BUY":
                # Reverse arbitrage: SELL at entry_price, BUY at exit_price
                # profit = (SELL price - BUY price) * qty - fees
                gross_pnl = (entry_price - exit_price) * entry_qty
            else:
                # Unexpected: both BUY or both SELL
                logger.error(f"[D205-9-1] Unexpected side combination: entry={entry_intent.side.value}, exit={exit_intent.side.value}")
                gross_pnl = 0.0
            
            realized_pnl = gross_pnl - total_fee
            
            # DB 기록 (storage 있을 때만)
            if self.storage:
                # 1. v2_orders: entry
                self.storage.insert_order(
                    run_id=self.config.run_id,
                    order_id=entry_result.order_id,
                    timestamp=timestamp,
                    exchange=entry_intent.exchange,
                    symbol=entry_intent.symbol,
                    side=entry_intent.side.value,
                    order_type=entry_intent.order_type.value,
                    quantity=entry_qty,
                    price=entry_price,
                    status="filled",
                    route_id=entry_intent.route_id,
                    strategy_id=entry_intent.strategy_id or "d204_2_paper",
                )
                rows_inserted += 1
                
                # 2. v2_orders: exit
                self.storage.insert_order(
                    run_id=self.config.run_id,
                    order_id=exit_result.order_id,
                    timestamp=timestamp,
                    exchange=exit_intent.exchange,
                    symbol=exit_intent.symbol,
                    side=exit_intent.side.value,
                    order_type=exit_intent.order_type.value,
                    quantity=exit_qty,
                    price=exit_price,
                    status="filled",
                    route_id=exit_intent.route_id,
                    strategy_id=exit_intent.strategy_id or "d204_2_paper",
                )
                rows_inserted += 1
                
                # 3. v2_fills: entry
                entry_fill_id = f"{entry_result.order_id}_fill_1"
                self.storage.insert_fill(
                    run_id=self.config.run_id,
                    order_id=entry_result.order_id,
                    fill_id=entry_fill_id,
                    timestamp=timestamp,
                    exchange=entry_intent.exchange,
                    symbol=entry_intent.symbol,
                    side=entry_intent.side.value,
                    filled_quantity=entry_qty,
                    filled_price=entry_price,
                    fee=entry_fee,
                    fee_currency=entry_fee_currency,
                )
                rows_inserted += 1
                
                # 4. v2_fills: exit
                exit_fill_id = f"{exit_result.order_id}_fill_1"
                self.storage.insert_fill(
                    run_id=self.config.run_id,
                    order_id=exit_result.order_id,
                    fill_id=exit_fill_id,
                    timestamp=timestamp,
                    exchange=exit_intent.exchange,
                    symbol=exit_intent.symbol,
                    side=exit_intent.side.value,
                    filled_quantity=exit_qty,
                    filled_price=exit_price,
                    fee=exit_fee,
                    fee_currency=exit_fee_currency,
                )
                rows_inserted += 1
                
                # 5. v2_trades: closed trade
                self.storage.insert_trade(
                    run_id=self.config.run_id,
                    trade_id=trade_id,
                    timestamp=timestamp,
                    entry_exchange=entry_intent.exchange,
                    entry_symbol=entry_intent.symbol,
                    entry_side=entry_intent.side.value,
                    entry_order_id=entry_result.order_id,
                    entry_quantity=entry_qty,
                    entry_price=entry_price,
                    entry_timestamp=timestamp,
                    exit_exchange=exit_intent.exchange,
                    exit_symbol=exit_intent.symbol,
                    exit_side=exit_intent.side.value,
                    exit_order_id=exit_result.order_id,
                    exit_quantity=exit_qty,
                    exit_price=exit_price,
                    exit_timestamp=timestamp,
                    realized_pnl=realized_pnl,
                    unrealized_pnl=0.0,  # Paper에서는 즉시 close
                    total_fee=total_fee,
                    status="closed",  # D205-2 REOPEN: closed trade
                    route_id=entry_intent.route_id,
                    strategy_id=entry_intent.strategy_id or "d204_2_paper",
                )
                rows_inserted += 1
                
                # KPI 업데이트 (DB inserts)
                self.kpi.db_inserts_ok += rows_inserted
            
            # D205-3: PnL KPI 업데이트 (DB off 모드에서도 실행)
            self.kpi.closed_trades += 1
            self.kpi.gross_pnl += realized_pnl
            self.kpi.fees += total_fee
            self.kpi.net_pnl = self.kpi.gross_pnl - self.kpi.fees
            
            if realized_pnl > 0:
                self.kpi.wins += 1
            else:
                self.kpi.losses += 1
            
            if self.kpi.closed_trades > 0:
                self.kpi.winrate_pct = (self.kpi.wins / self.kpi.closed_trades) * 100
            
            logger.debug(f"[D205-2] Trade closed: {trade_id}, realized_pnl={realized_pnl:.2f}, total_fee={total_fee:.2f}")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[D205-2] Failed to record trade: {error_msg}")
            self.kpi.error_count += 1
            self.kpi.errors.append(f"record_trade: {error_msg}")
            self.kpi.db_last_error = error_msg
            
            if self.config.db_mode == "strict":
                logger.error(f"[D205-2] ❌ FAIL: Trade record failed in strict mode")
                raise RuntimeError(f"Trade record failed in strict mode: {error_msg}")
            
            self.kpi.db_inserts_failed += rows_inserted
    
    def _save_kpi(self):
        """KPI JSON 저장 (+ result.json 통합)"""
        kpi_dict = self.kpi.to_dict()
        
        # D205-9: result.json 통합 (DB counts 포함)
        result = {
            "run_id": self.config.run_id,
            "phase": self.config.phase,
            "duration_minutes": self.config.duration_minutes,
            "db_mode": self.config.db_mode,
            "use_real_data": self.use_real_data,
            "kpi": kpi_dict,
        }
        
        # DB counts 추가 (storage 있을 때만)
        if self.storage:
            try:
                import psycopg2
                conn = psycopg2.connect(self.config.db_connection_string)
                try:
                    with conn.cursor() as cur:
                        # run_id 기준 count
                        cur.execute("SELECT COUNT(*) FROM v2_orders WHERE run_id = %s", (self.config.run_id,))
                        orders_count = cur.fetchone()[0]
                        
                        cur.execute("SELECT COUNT(*) FROM v2_fills WHERE run_id = %s", (self.config.run_id,))
                        fills_count = cur.fetchone()[0]
                        
                        cur.execute("SELECT COUNT(*) FROM v2_trades WHERE run_id = %s", (self.config.run_id,))
                        trades_count = cur.fetchone()[0]
                        
                        result["db_ledger_counts"] = {
                            "v2_orders": orders_count,
                            "v2_fills": fills_count,
                            "v2_trades": trades_count,
                        }
                        
                        logger.info(f"[D205-9] DB ledger counts: orders={orders_count}, fills={fills_count}, trades={trades_count}")
                finally:
                    conn.close()
            except Exception as e:
                logger.warning(f"[D205-9] Failed to query DB ledger counts: {e}")
                result["db_ledger_counts"] = {"error": str(e)}
        
        # kpi_*.json 저장 (기존 호환)
        kpi_file = self.output_dir / f"kpi_{self.config.phase}.json"
        with open(kpi_file, "w", encoding="utf-8") as f:
            json.dump(kpi_dict, f, indent=2, ensure_ascii=False)
        logger.info(f"[D204-2] KPI saved: {kpi_file}")
        
        # result.json 저장 (D205-9 통합)
        result_file = self.output_dir / "result.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"[D205-9] Result saved: {result_file}")
    
    def _save_db_counts(self):
        """DB row count 저장 (v2_orders/fills/trades)"""
        if not self.storage:
            return
        
        try:
            orders = self.storage.get_orders_by_run_id(self.config.run_id, limit=10000)
            fills = self.storage.get_fills_by_run_id(self.config.run_id, limit=10000)
            trades = self.storage.get_trades_by_run_id(self.config.run_id, limit=10000)
            
            db_counts = {
                "v2_orders": len(orders),
                "v2_fills": len(fills),
                "v2_trades": len(trades),
            }
            
            db_file = self.output_dir / f"db_counts_{self.config.phase}.json"
            with open(db_file, "w", encoding="utf-8") as f:
                json.dump(db_counts, f, indent=2)
            
            logger.info(f"[D204-2] DB counts saved: {db_file}")
            logger.info(f"[D204-2] DB counts: {db_counts}")
        
        except Exception as e:
            logger.warning(f"[D204-2] Failed to save DB counts: {e}")


def main():
    """CLI 엔트리포인트"""
    parser = argparse.ArgumentParser(description="D204-2 Paper Execution Gate Runner")
    parser.add_argument("--duration", type=int, required=True, help="Duration in minutes")
    parser.add_argument("--phase", default="smoke", choices=["smoke", "smoke_test", "baseline", "longrun", "test_1min"], help="Execution phase")
    parser.add_argument("--symbols-top", type=int, default=10, help="Top N symbols")
    parser.add_argument("--db-connection-string", default="", help="PostgreSQL connection string")
    parser.add_argument("--db-mode", default="strict", choices=["strict", "optional", "off"], help="DB mode (strict: FAIL on DB error, optional: skip on DB error, off: no DB)")
    parser.add_argument("--ensure-schema", action=argparse.BooleanOptionalAction, default=True, help="Verify DB schema before run (default: True, use --no-ensure-schema to disable)")
    parser.add_argument("--use-real-data", action="store_true", help="D205-9: Use Real MarketData (Upbit + Binance)")
    
    args = parser.parse_args()
    
    config = PaperRunnerConfig(
        duration_minutes=args.duration,
        phase=args.phase,
        symbols_top=args.symbols_top,
        db_connection_string=args.db_connection_string or "",
        db_mode=args.db_mode,
        ensure_schema=args.ensure_schema,
        use_real_data=args.use_real_data,
    )
    
    runner = PaperRunner(config)
    exit_code = runner.run()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
