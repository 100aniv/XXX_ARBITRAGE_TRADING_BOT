# -*- coding: utf-8 -*-
"""
D80-4: Realistic Fill & Slippage Model
현실적인 부분 체결 및 슬리피지 모델

목적:
    PAPER 모드에서 부분 체결(Partial Fill)과 슬리피지(Slippage)를 반영하여,
    100% 승률 구조를 깨고 현실적인 승률 범위(30~80%)로 내려오게 만든다.

설계 원칙:
    - 1차 버전: Simple Fill Model (Linear Slippage)
    - D81-x 확장 포인트: Advanced Market Impact, Multi-level Orderbook
    - 최소 침습: 기존 Executor와 독립적으로 동작

Author: arbitrage-lite project
Date: 2025-12-04
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple

from arbitrage.types import OrderSide

logger = logging.getLogger(__name__)


@dataclass
class FillContext:
    """
    Fill Model 실행 컨텍스트 (입력)
    
    주문 정보와 시장 상태를 담는 입력 구조체.
    
    Attributes:
        symbol: 거래 심볼 (예: "BTC/USDT")
        side: 주문 방향 (BUY or SELL)
        order_quantity: 주문 수량
        target_price: 목표 체결 가격 (호가 최우선 가격)
        available_volume: 해당 호가 레벨의 가용 잔량
        slippage_alpha: 슬리피지 계수 (기본값 사용 시 None)
    """
    symbol: str
    side: OrderSide
    order_quantity: float
    target_price: float
    available_volume: float
    slippage_alpha: float = None


@dataclass
class FillResult:
    """
    Fill Model 실행 결과 (출력)
    
    실제 체결 수량, 체결 가격, 슬리피지 정보를 담는 출력 구조체.
    
    Attributes:
        filled_quantity: 실제 체결된 수량
        unfilled_quantity: 미체결 수량
        effective_price: 슬리피지 반영된 실제 체결 가격
        slippage_bps: 슬리피지 (basis points)
        fill_ratio: 체결률 (filled_qty / order_qty)
        status: "filled" (전량 체결), "partially_filled" (부분 체결), "unfilled" (미체결)
    """
    filled_quantity: float
    unfilled_quantity: float
    effective_price: float
    slippage_bps: float
    fill_ratio: float
    status: str


class BaseFillModel(ABC):
    """
    Fill Model 추상 클래스
    
    부분 체결 및 슬리피지 모델링 인터페이스.
    D81-x에서 더 복잡한 모델로 확장 가능.
    """
    
    @abstractmethod
    def execute(self, context: FillContext) -> FillResult:
        """
        Fill Model 실행
        
        Args:
            context: 주문 및 시장 정보
        
        Returns:
            체결 결과 (수량, 가격, 슬리피지 등)
        """
        pass


class SimpleFillModel(BaseFillModel):
    """
    Simple Fill Model (1차 버전)
    
    Partial Fill + Linear Slippage 반영.
    
    메커니즘:
        1. Partial Fill: 호가 잔량이 주문 수량보다 적으면 부분 체결
        2. Linear Slippage: 주문 크기 대비 호가 잔량 비율에 비례하여 가격 악화
    
    수식:
        - impact_factor = filled_qty / available_volume
        - slippage_ratio = alpha * impact_factor
        - BUY: effective_price = target_price * (1 + slippage_ratio)
        - SELL: effective_price = target_price * (1 - slippage_ratio)
    
    Args:
        enable_partial_fill: 부분 체결 활성화 여부 (기본: True)
        enable_slippage: 슬리피지 활성화 여부 (기본: True)
        default_slippage_alpha: 기본 슬리피지 계수 (기본: 0.0001)
            - 0.0001 = 0.01% per unit impact (Conservative)
            - 0.0005 = 0.05% per unit impact (Moderate)
            - 0.001 = 0.1% per unit impact (Aggressive)
    """
    
    def __init__(
        self,
        enable_partial_fill: bool = True,
        enable_slippage: bool = True,
        default_slippage_alpha: float = 0.0001,
    ):
        """
        SimpleFillModel 초기화
        
        Args:
            enable_partial_fill: 부분 체결 활성화
            enable_slippage: 슬리피지 활성화
            default_slippage_alpha: 기본 슬리피지 계수
        """
        self.enable_partial_fill = enable_partial_fill
        self.enable_slippage = enable_slippage
        self.default_slippage_alpha = default_slippage_alpha
        
        logger.info(
            f"[D80-4_FILL_MODEL] SimpleFillModel 초기화: "
            f"부분체결={enable_partial_fill}, "
            f"슬리피지={enable_slippage}, "
            f"alpha={default_slippage_alpha}"
        )
    
    def execute(self, context: FillContext) -> FillResult:
        """
        Fill Model 실행
        
        1. Partial Fill 계산
        2. Slippage 계산
        3. FillResult 반환
        
        Args:
            context: 주문 및 시장 정보
        
        Returns:
            체결 결과
        """
        # 입력 검증
        if context.order_quantity <= 0:
            logger.warning(
                f"[D80-4_FILL_MODEL] {context.symbol}: "
                f"주문 수량이 0 이하입니다 (qty={context.order_quantity})"
            )
            return FillResult(
                filled_quantity=0.0,
                unfilled_quantity=context.order_quantity,
                effective_price=context.target_price,
                slippage_bps=0.0,
                fill_ratio=0.0,
                status="unfilled",
            )
        
        if context.target_price <= 0:
            logger.warning(
                f"[D80-4_FILL_MODEL] {context.symbol}: "
                f"목표 가격이 0 이하입니다 (price={context.target_price})"
            )
            return FillResult(
                filled_quantity=0.0,
                unfilled_quantity=context.order_quantity,
                effective_price=context.target_price,
                slippage_bps=0.0,
                fill_ratio=0.0,
                status="unfilled",
            )
        
        # 1. Partial Fill 계산
        filled_qty, unfilled_qty, fill_ratio = self._calculate_partial_fill(
            context.order_quantity,
            context.available_volume,
        )
        
        # 2. Slippage 계산
        slippage_alpha = context.slippage_alpha or self.default_slippage_alpha
        effective_price, slippage_bps = self._calculate_slippage(
            context.side,
            context.target_price,
            filled_qty,
            context.available_volume,
            slippage_alpha,
        )
        
        # 3. Status 결정
        if filled_qty == 0:
            status = "unfilled"
        elif filled_qty < context.order_quantity:
            status = "partially_filled"
        else:
            status = "filled"
        
        logger.debug(
            f"[D80-4_FILL_MODEL] {context.symbol} {context.side.value}: "
            f"주문={context.order_quantity:.4f}, 체결={filled_qty:.4f}, "
            f"가격={context.target_price:.2f}→{effective_price:.2f}, "
            f"슬리피지={slippage_bps:.2f}bps, 상태={status}"
        )
        
        return FillResult(
            filled_quantity=filled_qty,
            unfilled_quantity=unfilled_qty,
            effective_price=effective_price,
            slippage_bps=slippage_bps,
            fill_ratio=fill_ratio,
            status=status,
        )
    
    def _calculate_partial_fill(
        self,
        order_quantity: float,
        available_volume: float,
    ) -> Tuple[float, float, float]:
        """
        부분 체결 계산
        
        로직:
            - 호가 잔량이 0이면 → 미체결
            - 주문 수량 <= 호가 잔량 → 전량 체결
            - 주문 수량 > 호가 잔량 → 부분 체결 (호가 잔량만큼만 체결)
        
        Args:
            order_quantity: 주문 수량
            available_volume: 호가 잔량
        
        Returns:
            (filled_qty, unfilled_qty, fill_ratio)
        """
        if not self.enable_partial_fill:
            # Partial Fill 비활성화 시: 전량 체결 가정
            return order_quantity, 0.0, 1.0
        
        if available_volume <= 0:
            # 호가 잔량 없음 → 미체결
            return 0.0, order_quantity, 0.0
        
        if order_quantity <= available_volume:
            # 호가 잔량 충분 → 전량 체결
            return order_quantity, 0.0, 1.0
        
        # 호가 잔량 부족 → 부분 체결
        filled_qty = available_volume
        unfilled_qty = order_quantity - available_volume
        fill_ratio = available_volume / order_quantity
        
        return filled_qty, unfilled_qty, fill_ratio
    
    def _calculate_slippage(
        self,
        side: OrderSide,
        target_price: float,
        filled_quantity: float,
        available_volume: float,
        slippage_alpha: float,
    ) -> Tuple[float, float]:
        """
        슬리피지 계산 (Linear Model)
        
        주문 크기 대비 호가 잔량 비율에 비례하여 가격 악화.
        
        수식:
            impact_factor = filled_qty / available_volume
            slippage_ratio = alpha * impact_factor
            
            BUY: effective_price = target_price * (1 + slippage_ratio)
                 → 가격 상승 (매수자에게 불리)
            
            SELL: effective_price = target_price * (1 - slippage_ratio)
                  → 가격 하락 (매도자에게 불리)
            
            slippage_bps = |effective_price - target_price| / target_price * 10000
        
        Args:
            side: BUY or SELL
            target_price: 목표 가격
            filled_quantity: 체결 수량
            available_volume: 호가 잔량
            slippage_alpha: 슬리피지 계수
        
        Returns:
            (effective_price, slippage_bps)
        """
        if not self.enable_slippage:
            # Slippage 비활성화 시: 목표 가격 그대로
            return target_price, 0.0
        
        if available_volume <= 0 or filled_quantity <= 0:
            # 체결 없음 → 슬리피지 없음
            return target_price, 0.0
        
        # Volume Impact Factor
        impact_factor = min(filled_quantity / available_volume, 1.0)
        
        # Slippage Ratio
        slippage_ratio = slippage_alpha * impact_factor
        
        # 방향에 따라 가격 악화
        if side == OrderSide.BUY:
            # 매수: 가격 상승 (불리)
            effective_price = target_price * (1.0 + slippage_ratio)
        else:
            # 매도: 가격 하락 (불리)
            effective_price = target_price * (1.0 - slippage_ratio)
        
        # Basis Points 계산
        if target_price > 0:
            slippage_bps = abs((effective_price - target_price) / target_price * 10000.0)
        else:
            slippage_bps = 0.0
        
        return effective_price, slippage_bps


# 편의 함수: 기본 Fill Model 인스턴스 생성
def create_default_fill_model(
    enable_partial_fill: bool = True,
    enable_slippage: bool = True,
    slippage_alpha: float = 0.0001,
) -> SimpleFillModel:
    """
    기본 Fill Model 인스턴스 생성 (편의 함수)
    
    Args:
        enable_partial_fill: 부분 체결 활성화
        enable_slippage: 슬리피지 활성화
        slippage_alpha: 슬리피지 계수
    
    Returns:
        SimpleFillModel 인스턴스
    """
    return SimpleFillModel(
        enable_partial_fill=enable_partial_fill,
        enable_slippage=enable_slippage,
        default_slippage_alpha=slippage_alpha,
    )
