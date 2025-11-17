#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Position Engine (PHASE D9)
==========================

포지션 회계 및 PnL 추적.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class Position:
    """포지션"""
    
    def __init__(
        self,
        symbol: str,
        side: str,  # BUY | SELL
        quantity: float,
        entry_price: float,
        entry_time: datetime = None
    ):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.entry_price = entry_price
        self.entry_time = entry_time or datetime.now()
        self.realized_pnl = 0.0
        self.closed_at = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "realized_pnl": self.realized_pnl,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None
        }


class PositionEngine:
    """포지션 엔진"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: 포지션 설정
        """
        self.config = config or {}
        
        # 포지션 제한
        self.max_open_positions = self.config.get("max_open_positions", 5)
        self.max_exposure_krw = self.config.get("max_exposure_krw", 1000000)
        self.max_daily_loss_krw = self.config.get("max_daily_loss_krw", 150000)
        
        # 포지션 추적
        self.open_positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self.daily_realized_pnl = 0.0
    
    def open_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float
    ) -> Optional[Position]:
        """
        포지션 오픈
        
        Args:
            symbol: 심볼
            side: BUY | SELL
            quantity: 수량
            entry_price: 진입가
        
        Returns:
            Position 객체 또는 None
        """
        try:
            # 포지션 수 확인
            if len(self.open_positions) >= self.max_open_positions:
                logger.warning(
                    f"[PositionEngine] Max open positions reached: "
                    f"{len(self.open_positions)} >= {self.max_open_positions}"
                )
                return None
            
            # 노출도 확인
            current_exposure = self.get_total_exposure_krw()
            new_exposure = entry_price * quantity
            if current_exposure + new_exposure > self.max_exposure_krw:
                logger.warning(
                    f"[PositionEngine] Exposure limit exceeded: "
                    f"{current_exposure + new_exposure:.0f}₩ > {self.max_exposure_krw:.0f}₩"
                )
                return None
            
            # 포지션 생성
            position = Position(
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=entry_price
            )
            
            position_id = f"{symbol}_{side}_{int(datetime.now().timestamp() * 1000)}"
            self.open_positions[position_id] = position
            
            logger.info(
                f"[PositionEngine] Position opened: {position_id}, "
                f"size={quantity}, entry={entry_price:.0f}₩"
            )
            
            return position
        
        except Exception as e:
            logger.error(f"[PositionEngine] Open position error: {e}")
            return None
    
    def close_position(
        self,
        position_id: str,
        exit_price: float
    ) -> bool:
        """
        포지션 종료
        
        Args:
            position_id: 포지션 ID
            exit_price: 청산가
        
        Returns:
            성공 여부
        """
        try:
            if position_id not in self.open_positions:
                logger.warning(f"[PositionEngine] Position not found: {position_id}")
                return False
            
            position = self.open_positions[position_id]
            
            # PnL 계산
            if position.side == "BUY":
                pnl = (exit_price - position.entry_price) * position.quantity
            else:  # SELL
                pnl = (position.entry_price - exit_price) * position.quantity
            
            position.realized_pnl = pnl
            position.closed_at = datetime.now()
            
            # 일일 PnL 업데이트
            self.daily_realized_pnl += pnl
            
            # 포지션 이동
            self.closed_positions.append(position)
            del self.open_positions[position_id]
            
            logger.info(
                f"[PositionEngine] Position closed: {position_id}, "
                f"pnl={pnl:.0f}₩, daily_pnl={self.daily_realized_pnl:.0f}₩"
            )
            
            return True
        
        except Exception as e:
            logger.error(f"[PositionEngine] Close position error: {e}")
            return False
    
    def get_unrealized_pnl(self, symbol: str, mid_price: float) -> float:
        """
        미실현 PnL 계산
        
        Args:
            symbol: 심볼
            mid_price: 중간가
        
        Returns:
            미실현 PnL (KRW)
        """
        total_pnl = 0.0
        
        for position in self.open_positions.values():
            if position.symbol == symbol:
                if position.side == "BUY":
                    pnl = (mid_price - position.entry_price) * position.quantity
                else:  # SELL
                    pnl = (position.entry_price - mid_price) * position.quantity
                
                total_pnl += pnl
        
        return total_pnl
    
    def get_realized_pnl_today(self) -> float:
        """일일 실현 PnL 조회"""
        return self.daily_realized_pnl
    
    def get_total_exposure_krw(self) -> float:
        """전체 노출도 조회 (KRW)"""
        total_exposure = 0.0
        
        for position in self.open_positions.values():
            exposure = position.entry_price * position.quantity
            total_exposure += exposure
        
        return total_exposure
    
    def get_open_positions_count(self) -> int:
        """열린 포지션 수"""
        return len(self.open_positions)
    
    def can_open_new_position(self, position_size_krw: float) -> bool:
        """새 포지션 오픈 가능 여부"""
        # 포지션 수 확인
        if len(self.open_positions) >= self.max_open_positions:
            return False
        
        # 노출도 확인
        current_exposure = self.get_total_exposure_krw()
        if current_exposure + position_size_krw > self.max_exposure_krw:
            return False
        
        # 일일 손실 확인
        if self.daily_realized_pnl < -self.max_daily_loss_krw:
            return False
        
        return True
    
    def reset_daily_pnl(self):
        """일일 PnL 리셋 (자정)"""
        self.daily_realized_pnl = 0.0
        logger.info("[PositionEngine] Daily PnL reset")
    
    def get_stats(self) -> Dict[str, Any]:
        """포지션 통계"""
        total_unrealized = 0.0
        for position in self.open_positions.values():
            # 현재가 없으므로 0으로 계산
            total_unrealized += 0.0
        
        return {
            "open_positions_count": len(self.open_positions),
            "total_exposure_krw": self.get_total_exposure_krw(),
            "realized_pnl_today": self.daily_realized_pnl,
            "unrealized_pnl": total_unrealized,
            "closed_positions_today": len(self.closed_positions)
        }
