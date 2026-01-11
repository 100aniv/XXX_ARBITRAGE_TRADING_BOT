from typing import Optional, Dict, List
from datetime import datetime, timezone
import logging
import uuid

from arbitrage.v2.domain.order_intent import OrderIntent, OrderSide
from arbitrage.v2.storage.ledger import V2LedgerStorage

logger = logging.getLogger(__name__)


class LedgerWriter:
    """DB 기록 전담 (orders/fills/trades)"""
    
    def __init__(self, storage: Optional[V2LedgerStorage], config):
        self.storage = storage
        self.config = config
        
        if storage and config.db_mode == "strict":
            self._verify_schema()
    
    def _verify_schema(self):
        """스키마 검증 (strict mode)"""
        required_tables = ["v2_orders", "v2_fills", "v2_trades"]
        
        try:
            missing = self.storage.verify_schema(required_tables)
            if missing:
                raise RuntimeError(f"Missing tables: {missing}")
            logger.info(f"[D205-18-2D] DB schema verified")
        except Exception as e:
            logger.error(f"[D205-18-2D] Schema verification failed: {e}")
            raise
    
    def record_order_and_fill(
        self,
        intent: OrderIntent,
        order_result,
        candidate,
        kpi,
    ) -> int:
        """주문 + 체결 기록"""
        if not self.storage:
            return 0
        
        rows_inserted = 0
        error_msg = ""
        
        try:
            order_record = {
                "order_id": str(uuid.uuid4()),
                "run_id": self.config.run_id,
                "symbol": intent.symbol,
                "exchange": intent.exchange,
                "side": intent.side.value,
                "order_type": intent.order_type.value,
                "base_qty": intent.base_qty,
                "quote_amount": intent.quote_amount,
                "limit_price": None,
                "status": "filled",
                "created_at": datetime.now(timezone.utc),
            }
            
            self.storage.insert_order(order_record)
            rows_inserted += 1
            
            fill_record = {
                "fill_id": str(uuid.uuid4()),
                "order_id": order_record["order_id"],
                "run_id": self.config.run_id,
                "symbol": intent.symbol,
                "exchange": intent.exchange,
                "side": intent.side.value,
                "filled_qty": order_result.filled_qty,
                "filled_price": order_result.filled_price,
                "fee": order_result.fee,
                "filled_at": datetime.now(timezone.utc),
            }
            
            self.storage.insert_fill(fill_record)
            rows_inserted += 1
            kpi.db_inserts_ok += rows_inserted
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[D205-18-2D] DB insert failed: {e}")
            
            if self.config.db_mode == "strict":
                logger.error(f"[D205-18-2D] FAIL: strict mode")
                raise RuntimeError(f"DB insert failed in strict mode: {error_msg}")
            
            kpi.db_inserts_failed += rows_inserted
        
        return rows_inserted
    
    def record_trade_complete(
        self,
        trade_id: str,
        candidate,
        intents: List[OrderIntent],
        entry_result,
        exit_result,
        realized_pnl: float,
        kpi,
    ) -> int:
        """거래 완료 기록"""
        if not self.storage:
            return 0
        
        rows_inserted = 0
        error_msg = ""
        
        try:
            entry_intent = intents[0]
            exit_intent = intents[1]
            
            trade_record = {
                "trade_id": trade_id,
                "run_id": self.config.run_id,
                "symbol": candidate.symbol,
                "entry_exchange": entry_intent.exchange,
                "exit_exchange": exit_intent.exchange,
                "entry_price": entry_result.filled_price,
                "exit_price": exit_result.filled_price,
                "quantity": entry_result.filled_qty,
                "entry_fee": entry_result.fee,
                "exit_fee": exit_result.fee,
                "realized_pnl": realized_pnl,
                "opened_at": datetime.now(timezone.utc),
                "closed_at": datetime.now(timezone.utc),
            }
            
            self.storage.insert_trade(trade_record)
            rows_inserted += 1
            kpi.db_inserts_ok += rows_inserted
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[D205-18-2D] Trade record failed: {e}")
            
            if self.config.db_mode == "strict":
                logger.error(f"[D205-18-2D] FAIL: strict mode")
                raise RuntimeError(f"Trade record failed in strict mode: {error_msg}")
            
            kpi.db_inserts_failed += rows_inserted
        
        return rows_inserted
    
    def get_counts(self) -> Optional[Dict[str, int]]:
        """DB row count 조회"""
        if not self.storage:
            return None
        
        try:
            orders = self.storage.get_orders_by_run_id(self.config.run_id, limit=10000)
            fills = self.storage.get_fills_by_run_id(self.config.run_id, limit=10000)
            trades = self.storage.get_trades_by_run_id(self.config.run_id, limit=10000)
            
            return {
                "v2_orders": len(orders),
                "v2_fills": len(fills),
                "v2_trades": len(trades),
            }
        except Exception as e:
            logger.warning(f"[D205-18-2D] DB counts failed: {e}")
            return None
