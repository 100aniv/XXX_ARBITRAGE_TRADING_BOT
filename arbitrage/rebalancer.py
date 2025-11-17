#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rebalancer Engine (PHASE D9)
=============================

포트폴리오 리밸런싱 및 노출도 관리.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class RebalancerEngine:
    """리밸런싱 엔진"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: 리밸런싱 설정
        """
        self.config = config or {}
        
        # 리밸런싱 설정
        self.enabled = self.config.get("enabled", True)
        self.max_exposure_krw = self.config.get("max_exposure_krw", 600000)
        self.reduce_pct = self.config.get("reduce_pct", 0.3)  # 30% 감소
        
        # 통계
        self.rebalance_actions = 0
    
    def should_rebalance(self, current_exposure_krw: float) -> bool:
        """
        리밸런싱 필요 여부
        
        Args:
            current_exposure_krw: 현재 노출도 (KRW)
        
        Returns:
            리밸런싱 필요 여부
        """
        if not self.enabled:
            return False
        
        return current_exposure_krw > self.max_exposure_krw
    
    def calculate_reduction(self, current_exposure_krw: float) -> float:
        """
        감소할 노출도 계산
        
        Args:
            current_exposure_krw: 현재 노출도 (KRW)
        
        Returns:
            감소할 노출도 (KRW)
        """
        excess = current_exposure_krw - self.max_exposure_krw
        return excess * (1 + self.reduce_pct)  # 여유있게 감소
    
    def rebalance(
        self,
        position_engine: Any,
        reduction_amount_krw: float
    ) -> List[str]:
        """
        포트폴리오 리밸런싱
        
        Args:
            position_engine: PositionEngine 객체
            reduction_amount_krw: 감소할 노출도 (KRW)
        
        Returns:
            종료할 포지션 ID 리스트
        """
        try:
            if not self.enabled:
                return []
            
            positions_to_close = []
            remaining_reduction = reduction_amount_krw
            
            # 가장 작은 포지션부터 종료
            sorted_positions = sorted(
                position_engine.open_positions.items(),
                key=lambda x: x[1].entry_price * x[1].quantity
            )
            
            for position_id, position in sorted_positions:
                if remaining_reduction <= 0:
                    break
                
                position_size = position.entry_price * position.quantity
                if position_size <= remaining_reduction:
                    positions_to_close.append(position_id)
                    remaining_reduction -= position_size
                    
                    logger.info(
                        f"[Rebalancer] Marked position for closure: {position_id}, "
                        f"size={position_size:.0f}₩"
                    )
            
            if positions_to_close:
                self.rebalance_actions += 1
                logger.warning(
                    f"[Rebalancer] Rebalancing triggered: "
                    f"closing {len(positions_to_close)} positions, "
                    f"reduction={reduction_amount_krw:.0f}₩"
                )
            
            return positions_to_close
        
        except Exception as e:
            logger.error(f"[Rebalancer] Rebalance error: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """리밸런싱 통계"""
        return {
            "rebalance_actions": self.rebalance_actions,
            "enabled": self.enabled,
            "max_exposure_krw": self.max_exposure_krw
        }
