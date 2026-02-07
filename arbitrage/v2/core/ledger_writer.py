from typing import Optional, Dict, List
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import logging
import uuid

from arbitrage.v2.domain.order_intent import OrderIntent, OrderSide
from arbitrage.v2.storage.ledger import V2LedgerStorage

logger = logging.getLogger(__name__)


DECIMAL_QUANTIZE = Decimal("0.00000001")


def _to_decimal(value: Optional[float]) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(DECIMAL_QUANTIZE, rounding=ROUND_HALF_UP)


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
            order_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc)
            
            order_quantity = _quantize(_to_decimal(intent.base_qty)) if intent.base_qty else None
            self.storage.insert_order(
                run_id=self.config.run_id,
                order_id=order_id,
                timestamp=timestamp,
                exchange=intent.exchange,
                symbol=intent.symbol,
                side=intent.side.value,
                order_type=intent.order_type.value,
                quantity=order_quantity,
                price=None,
                status="filled",
            )
            rows_inserted += 1
            
            fill_id = str(uuid.uuid4())
            filled_at = datetime.now(timezone.utc)
            
            filled_qty = _quantize(_to_decimal(order_result.filled_qty))
            filled_price = _quantize(_to_decimal(order_result.filled_price))
            fee = _quantize(_to_decimal(order_result.fee))
            self.storage.insert_fill(
                run_id=self.config.run_id,
                order_id=order_id,
                fill_id=fill_id,
                timestamp=filled_at,
                exchange=intent.exchange,
                symbol=intent.symbol,
                side=intent.side.value,
                filled_quantity=filled_qty,
                filled_price=filled_price,
                fee=fee,
                fee_currency="KRW",
            )
            rows_inserted += 1
            kpi.db_inserts_ok += rows_inserted
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[D207-1] DB insert failed: {e}")
            
            if self.config.db_mode == "strict":
                logger.error(f"[D207-1] FAIL: strict mode")
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
            timestamp = datetime.now(timezone.utc)
            
            # Generate fake order IDs (assume they exist from record_order_and_fill)
            entry_order_id = f"entry_{trade_id[:8]}"
            exit_order_id = f"exit_{trade_id[:8]}"
            
            entry_qty = _quantize(_to_decimal(entry_result.filled_qty))
            entry_price = _quantize(_to_decimal(entry_result.filled_price))
            exit_qty = _quantize(_to_decimal(exit_result.filled_qty))
            exit_price = _quantize(_to_decimal(exit_result.filled_price))
            realized_pnl_decimal = _quantize(_to_decimal(realized_pnl))
            total_fee = _quantize(_to_decimal(entry_result.fee) + _to_decimal(exit_result.fee))
            self.storage.insert_trade(
                run_id=self.config.run_id,
                trade_id=trade_id,
                timestamp=timestamp,
                entry_exchange=entry_intent.exchange,
                entry_symbol=candidate.symbol,
                entry_side=entry_intent.side.value,
                entry_order_id=entry_order_id,
                entry_quantity=entry_qty,
                entry_price=entry_price,
                entry_timestamp=timestamp,
                status="closed",
                exit_exchange=exit_intent.exchange,
                exit_symbol=candidate.symbol,
                exit_side=exit_intent.side.value,
                exit_order_id=exit_order_id,
                exit_quantity=exit_qty,
                exit_price=exit_price,
                exit_timestamp=timestamp,
                realized_pnl=realized_pnl_decimal,
                total_fee=total_fee,
            )
            rows_inserted += 1
            kpi.db_inserts_ok += rows_inserted
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[D207-1] Trade record failed: {e}")
            
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
            logger.warning(f"[D207-1] DB counts failed: {e}")
            return None
