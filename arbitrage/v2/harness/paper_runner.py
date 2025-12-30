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
from arbitrage.domain.fee_model import FeeModel, FeeStructure


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
        
        self.break_even_params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=5.0,
            buffer_bps=0.0,
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
                
                # 1. Opportunity 생성 (Mock 가격)
                candidate = self._generate_mock_opportunity(iteration)
                if candidate:
                    self.kpi.opportunities_generated += 1
                    
                    # 2. OrderIntent 변환
                    intents = self._convert_to_intents(candidate)
                    self.kpi.intents_created += len(intents)
                    
                    # 3. 모의 실행
                    for intent in intents:
                        self._execute_mock_order(intent)
                        self.kpi.mock_executions += 1
                
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
            return 1
        
        except Exception as e:
            logger.error(f"[D204-2] Fatal error: {e}", exc_info=True)
            self.kpi.errors.append(str(e))
            self._save_kpi()
            return 1
    
    def _generate_mock_opportunity(self, iteration: int):
        """Mock Opportunity 생성 (가상 가격)"""
        # Mock 가격 (iteration 기반으로 변동)
        base_price_a = 50_000_000.0  # Upbit BTC/KRW
        base_price_b = 40_000.0      # Binance BTC/USDT
        
        # 스프레드 시뮬레이션 (0.3%~0.5% 변동)
        spread_pct = 0.003 + (iteration % 10) * 0.0002
        price_a = base_price_a * (1 + spread_pct / 2)
        price_b = base_price_b * (1 - spread_pct / 2)
        
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
            logger.warning(f"[D204-2] Failed to convert to intents: {e}")
            self.kpi.errors.append(f"candidate_to_order_intents: {e}")
            return []
    
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
            
            fill_id = f"{order_result.order_id}_fill_1"
            
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
            trade_id = f"trade_{self.config.run_id}_{order_result.order_id}"
            
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
    
    def _save_kpi(self):
        """KPI JSON 저장"""
        kpi_file = self.output_dir / f"kpi_{self.config.phase}.json"
        
        with open(kpi_file, "w", encoding="utf-8") as f:
            json.dump(self.kpi.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"[D204-2] KPI saved: {kpi_file}")
    
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
    
    args = parser.parse_args()
    
    config = PaperRunnerConfig(
        duration_minutes=args.duration,
        phase=args.phase,
        symbols_top=args.symbols_top,
        db_connection_string=args.db_connection_string or "",
        db_mode=args.db_mode,
        ensure_schema=args.ensure_schema,
    )
    
    runner = PaperRunner(config)
    exit_code = runner.run()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
