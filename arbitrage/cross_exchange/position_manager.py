# -*- coding: utf-8 -*-
"""
D79-2: Cross-Exchange Position Manager

교차 거래소 아비트라지 Position 관리.

Features:
- Position SSOT: Redis storage
- Multi-symbol support
- Position state machine (open → closing → closed)
- Inventory tracking
- D75 PortfolioBudget 철학 준수
"""

import logging
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class PositionState(str, Enum):
    """Position 상태"""
    OPEN = "open"  # 진입 완료
    CLOSING = "closing"  # 청산 중
    CLOSED = "closed"  # 청산 완료


@dataclass
class CrossExchangePosition:
    """
    교차 거래소 포지션
    
    SSOT: Redis `cross_position:{symbol}`
    """
    symbol_mapping: Dict  # SymbolMapping (serialized)
    entry_side: str  # "positive" or "negative"
    
    # Entry info
    entry_spread_percent: float
    entry_fx_rate: float
    entry_timestamp: float
    entry_upbit_price_krw: float
    entry_binance_price_usdt: float
    
    # State
    state: PositionState
    
    # Exit info (optional)
    exit_timestamp: Optional[float] = None
    exit_spread_percent: Optional[float] = None
    exit_reason: Optional[str] = None
    exit_pnl_krw: Optional[float] = None
    
    # Metadata
    position_id: Optional[str] = None  # Unique ID
    
    def to_dict(self) -> Dict:
        """Dict로 변환 (Redis 저장용)"""
        data = asdict(self)
        data["state"] = self.state.value  # Enum → str
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> "CrossExchangePosition":
        """Dict에서 복원"""
        data["state"] = PositionState(data["state"])  # str → Enum
        return cls(**data)
    
    def get_holding_time(self) -> float:
        """보유 시간 (초)"""
        if self.exit_timestamp:
            return self.exit_timestamp - self.entry_timestamp
        else:
            return time.time() - self.entry_timestamp
    
    def is_open(self) -> bool:
        """Position이 open 상태인지 확인"""
        return self.state == PositionState.OPEN
    
    def is_closed(self) -> bool:
        """Position이 closed 상태인지 확인"""
        return self.state == PositionState.CLOSED
    
    def is_closing(self) -> bool:
        """Position이 closing 상태인지 확인"""
        return self.state == PositionState.CLOSING


class CrossExchangePositionManager:
    """
    교차 거래소 Position 관리자
    
    SSOT: Redis
    - Key: `cross_position:{upbit_symbol}`
    - Value: JSON (CrossExchangePosition)
    
    Features:
    - open_position(): 포지션 진입
    - close_position(): 포지션 청산
    - get_position(): 포지션 조회
    - list_open_positions(): 모든 open 포지션 조회
    - get_inventory(): 인벤토리 상태 조회
    
    Example:
        pm = CrossExchangePositionManager(redis_client=redis_client)
        
        # Open position
        position = pm.open_position(
            symbol_mapping=mapping,
            entry_side="positive",
            entry_spread=spread,
        )
        
        # Close position
        pm.close_position(
            upbit_symbol="KRW-BTC",
            exit_spread=current_spread,
            exit_reason="TP",
        )
        
        # List open positions
        open_positions = pm.list_open_positions()
    """
    
    POSITION_KEY_PREFIX = "cross_position:"
    POSITION_TTL = 86400 * 7  # 7 days
    
    def __init__(self, redis_client=None):
        """
        Initialize CrossExchangePositionManager
        
        Args:
            redis_client: Redis client (optional, for testing mock can be None)
        """
        self.redis_client = redis_client
        logger.info("[CROSS_POSITION_MGR] Initialized")
    
    def open_position(
        self,
        symbol_mapping: any,
        entry_side: str,
        entry_spread: any,
    ) -> CrossExchangePosition:
        """
        포지션 진입
        
        Args:
            symbol_mapping: SymbolMapping
            entry_side: "positive" or "negative"
            entry_spread: CrossSpread
        
        Returns:
            CrossExchangePosition
        """
        upbit_symbol = symbol_mapping.upbit_symbol
        
        # Check if position already exists
        existing = self.get_position(upbit_symbol)
        if existing and existing.is_open():
            logger.warning(
                f"[CROSS_POSITION_MGR] Position already open for {upbit_symbol}, "
                f"closing existing position first"
            )
            self.close_position(
                upbit_symbol=upbit_symbol,
                exit_spread=entry_spread,
                exit_reason="Force close (new entry)",
            )
        
        # Create new position
        position = CrossExchangePosition(
            symbol_mapping=self._serialize_mapping(symbol_mapping),
            entry_side=entry_side,
            entry_spread_percent=entry_spread.spread_percent,
            entry_fx_rate=entry_spread.fx_rate,
            entry_timestamp=time.time(),
            entry_upbit_price_krw=entry_spread.upbit_price_krw,
            entry_binance_price_usdt=entry_spread.binance_price_usdt,
            state=PositionState.OPEN,
            position_id=self._generate_position_id(upbit_symbol),
        )
        
        # Save to Redis
        self._save_position(upbit_symbol, position)
        
        logger.info(
            f"[CROSS_POSITION_MGR] Opened position: {upbit_symbol} "
            f"(side={entry_side}, spread={entry_spread.spread_percent:.2f}%)"
        )
        
        return position
    
    def close_position(
        self,
        upbit_symbol: str,
        exit_spread: any,
        exit_reason: str,
    ) -> Optional[CrossExchangePosition]:
        """
        포지션 청산
        
        Args:
            upbit_symbol: Upbit 심볼
            exit_spread: 현재 CrossSpread
            exit_reason: 청산 이유
        
        Returns:
            Closed position 또는 None (position이 없으면)
        """
        position = self.get_position(upbit_symbol)
        
        if not position:
            logger.warning(f"[CROSS_POSITION_MGR] No position found for {upbit_symbol}")
            return None
        
        if position.is_closed():
            logger.warning(f"[CROSS_POSITION_MGR] Position already closed for {upbit_symbol}")
            return position
        
        # Update position
        position.state = PositionState.CLOSED
        position.exit_timestamp = time.time()
        position.exit_spread_percent = exit_spread.spread_percent
        position.exit_reason = exit_reason
        
        # Calculate PnL (simplified)
        spread_change = exit_spread.spread_percent - position.entry_spread_percent
        position.exit_pnl_krw = self._calculate_pnl(position, spread_change)
        
        # Save to Redis
        self._save_position(upbit_symbol, position)
        
        logger.info(
            f"[CROSS_POSITION_MGR] Closed position: {upbit_symbol} "
            f"(reason={exit_reason}, pnl={position.exit_pnl_krw:,.0f} KRW, "
            f"holding_time={position.get_holding_time():.0f}s)"
        )
        
        return position
    
    def mark_position_closing(
        self,
        upbit_symbol: str,
        upbit_order_id: Optional[str] = None,
        binance_order_id: Optional[str] = None,
    ) -> Optional[CrossExchangePosition]:
        """
        포지션을 CLOSING 상태로 전환 (주문 실행 시작)
        
        Args:
            upbit_symbol: Upbit 심볼
            upbit_order_id: Upbit 주문 ID (optional)
            binance_order_id: Binance 주문 ID (optional)
        
        Returns:
            Updated position 또는 None
        """
        position = self.get_position(upbit_symbol)
        
        if not position:
            logger.warning(f"[CROSS_POSITION_MGR] No position found for {upbit_symbol}")
            return None
        
        if not position.is_open():
            logger.warning(
                f"[CROSS_POSITION_MGR] Position not open for {upbit_symbol} "
                f"(state={position.state.value})"
            )
            return position
        
        # Update to CLOSING state
        position.state = PositionState.CLOSING
        
        if upbit_order_id:
            position.upbit_order_id = upbit_order_id
        if binance_order_id:
            position.binance_order_id = binance_order_id
        
        # Save to Redis
        self._save_position(upbit_symbol, position)
        
        logger.info(
            f"[CROSS_POSITION_MGR] Marked position as CLOSING: {upbit_symbol} "
            f"(upbit_order={upbit_order_id}, binance_order={binance_order_id})"
        )
        
        return position
    
    def get_position(self, upbit_symbol: str) -> Optional[CrossExchangePosition]:
        """
        포지션 조회
        
        Args:
            upbit_symbol: Upbit 심볼
        
        Returns:
            CrossExchangePosition 또는 None
        """
        if not self.redis_client:
            return None
        
        key = self._get_position_key(upbit_symbol)
        
        try:
            data = self.redis_client.get(key)
            if not data:
                return None
            
            position_dict = json.loads(data)
            return CrossExchangePosition.from_dict(position_dict)
        
        except Exception as e:
            logger.error(f"[CROSS_POSITION_MGR] Failed to get position for {upbit_symbol}: {e}")
            return None
    
    def list_open_positions(self) -> List[CrossExchangePosition]:
        """
        모든 open 포지션 조회
        
        Returns:
            List[CrossExchangePosition]
        """
        if not self.redis_client:
            return []
        
        try:
            # Scan all position keys
            pattern = f"{self.POSITION_KEY_PREFIX}*"
            keys = list(self.redis_client.scan_iter(match=pattern, count=100))
            
            positions = []
            for key in keys:
                data = self.redis_client.get(key)
                if data:
                    position_dict = json.loads(data)
                    position = CrossExchangePosition.from_dict(position_dict)
                    
                    if position.is_open():
                        positions.append(position)
            
            return positions
        
        except Exception as e:
            logger.error(f"[CROSS_POSITION_MGR] Failed to list open positions: {e}")
            return []
    
    def get_inventory(self) -> Dict[str, int]:
        """
        인벤토리 상태 조회
        
        Returns:
            {
                "total_open": int,
                "positive": int,
                "negative": int,
            }
        """
        open_positions = self.list_open_positions()
        
        inventory = {
            "total_open": len(open_positions),
            "positive": sum(1 for p in open_positions if p.entry_side == "positive"),
            "negative": sum(1 for p in open_positions if p.entry_side == "negative"),
        }
        
        return inventory
    
    def _save_position(self, upbit_symbol: str, position: CrossExchangePosition):
        """Position을 Redis에 저장"""
        if not self.redis_client:
            logger.warning("[CROSS_POSITION_MGR] No Redis client, skipping save")
            return
        
        key = self._get_position_key(upbit_symbol)
        data = json.dumps(position.to_dict())
        
        try:
            self.redis_client.setex(key, self.POSITION_TTL, data)
        except Exception as e:
            logger.error(f"[CROSS_POSITION_MGR] Failed to save position for {upbit_symbol}: {e}")
    
    def _get_position_key(self, upbit_symbol: str) -> str:
        """Redis key 생성"""
        return f"{self.POSITION_KEY_PREFIX}{upbit_symbol}"
    
    def _generate_position_id(self, upbit_symbol: str) -> str:
        """Position ID 생성"""
        timestamp = int(time.time() * 1000)
        return f"{upbit_symbol}_{timestamp}"
    
    def _serialize_mapping(self, symbol_mapping: any) -> Dict:
        """SymbolMapping을 Dict로 변환"""
        return {
            "upbit_symbol": symbol_mapping.upbit_symbol,
            "binance_symbol": symbol_mapping.binance_symbol,
            "base_asset": symbol_mapping.base_asset,
            "upbit_quote": symbol_mapping.upbit_quote,
            "binance_quote": symbol_mapping.binance_quote,
            "confidence": symbol_mapping.confidence,
        }
    
    def _calculate_pnl(self, position: CrossExchangePosition, spread_change: float) -> float:
        """
        PnL 계산 (간단 버전)
        
        Args:
            position: CrossExchangePosition
            spread_change: Spread 변화 (%)
        
        Returns:
            PnL (KRW)
        
        Note:
            실제로는 entry/exit 가격, 수량, 수수료 등을 고려해야 함.
            여기서는 간단히 spread_change * base_amount로 계산.
        """
        # Base amount (1M KRW 기준)
        base_amount_krw = 1_000_000.0
        
        # PnL = spread_change * base_amount
        # POSITIVE entry: spread 감소 → 수익
        # NEGATIVE entry: spread 증가 → 수익
        if position.entry_side == "positive":
            pnl = -spread_change * base_amount_krw / 100.0
        else:  # negative
            pnl = spread_change * base_amount_krw / 100.0
        
        return pnl
    
    def clear_all_positions(self):
        """
        모든 포지션 삭제 (테스트용)
        
        ⚠️ WARNING: Production에서는 사용 금지!
        """
        if not self.redis_client:
            return
        
        try:
            pattern = f"{self.POSITION_KEY_PREFIX}*"
            keys = list(self.redis_client.scan_iter(match=pattern, count=100))
            
            if keys:
                self.redis_client.delete(*keys)
                logger.warning(f"[CROSS_POSITION_MGR] Cleared {len(keys)} positions (TEST ONLY)")
        
        except Exception as e:
            logger.error(f"[CROSS_POSITION_MGR] Failed to clear positions: {e}")
