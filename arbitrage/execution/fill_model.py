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


class AdvancedFillModel(BaseFillModel):
    """
    Advanced Fill Model (D81-1)
    
    Multi-level orderbook simulation + Non-linear market impact.
    
    메커니즘:
        1. 가상 L2 레벨 생성: Best bid/ask 기준으로 k개 레벨 생성
        2. 레벨별 유동성 분배: 지수 감소 함수로 각 레벨의 available_volume 설정
        3. 주문 분할: 주문을 레벨별로 나누어 체결
        4. 비선형 Impact: 레벨이 깊어질수록 slippage 증가
        5. Partial Fill 자연 발생: 큰 주문 시 모든 레벨을 소진하면 fill_ratio < 1.0
    
    Args:
        enable_partial_fill: 부분 체결 활성화 여부 (기본: True)
        enable_slippage: 슬리피지 활성화 여부 (기본: True)
        default_slippage_alpha: 기본 슬리피지 계수 (기본: 0.0002, SimpleFillModel의 2배)
        num_levels: 가상 L2 레벨 수 (기본: 5)
        level_spacing_bps: 레벨 간 가격 간격 in bps (기본: 1.0 bps)
        decay_rate: 레벨별 유동성 감소 속도 (기본: 0.3)
        slippage_exponent: 슬리피지 비선형 지수 (기본: 1.2)
        base_volume_multiplier: 기본 유동성 배율 (기본: 0.8)
    """
    
    def __init__(
        self,
        enable_partial_fill: bool = True,
        enable_slippage: bool = True,
        default_slippage_alpha: float = 0.0002,
        num_levels: int = 5,
        level_spacing_bps: float = 1.0,
        decay_rate: float = 0.3,
        slippage_exponent: float = 1.2,
        base_volume_multiplier: float = 0.8,
    ):
        """
        AdvancedFillModel 초기화
        
        Args:
            enable_partial_fill: 부분 체결 활성화
            enable_slippage: 슬리피지 활성화
            default_slippage_alpha: 기본 슬리피지 계수
            num_levels: 가상 L2 레벨 수
            level_spacing_bps: 레벨 간 가격 간격
            decay_rate: 레벨별 유동성 감소 속도
            slippage_exponent: 슬리피지 비선형 지수
            base_volume_multiplier: 기본 유동성 배율
        """
        self.enable_partial_fill = enable_partial_fill
        self.enable_slippage = enable_slippage
        self.default_slippage_alpha = default_slippage_alpha
        self.num_levels = max(1, num_levels)  # 최소 1 레벨
        self.level_spacing_bps = level_spacing_bps
        self.decay_rate = decay_rate
        self.slippage_exponent = slippage_exponent
        self.base_volume_multiplier = base_volume_multiplier
        
        logger.info(
            f"[D81-1_ADVANCED_FILL] AdvancedFillModel 초기화: "
            f"부분체결={enable_partial_fill}, "
            f"슬리피지={enable_slippage}, "
            f"alpha={default_slippage_alpha}, "
            f"레벨={num_levels}, "
            f"간격={level_spacing_bps}bps, "
            f"감소율={decay_rate}, "
            f"지수={slippage_exponent}, "
            f"유동성배율={base_volume_multiplier}"
        )
    
    def execute(self, context: FillContext) -> FillResult:
        """
        Fill Model 실행
        
        1. 입력 검증
        2. 가상 L2 레벨 생성
        3. 레벨별 주문 분할 & 체결
        4. FillResult 생성
        
        Args:
            context: 주문 및 시장 정보
        
        Returns:
            체결 결과
        """
        # 입력 검증
        if context.order_quantity <= 0:
            logger.warning(
                f"[D81-1_ADVANCED_FILL] {context.symbol}: "
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
                f"[D81-1_ADVANCED_FILL] {context.symbol}: "
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
        
        # 1. 가상 L2 레벨 생성
        levels = self._generate_virtual_levels(context)
        
        if not levels:
            logger.warning(
                f"[D81-1_ADVANCED_FILL] {context.symbol}: "
                f"가상 L2 레벨 생성 실패"
            )
            return FillResult(
                filled_quantity=0.0,
                unfilled_quantity=context.order_quantity,
                effective_price=context.target_price,
                slippage_bps=0.0,
                fill_ratio=0.0,
                status="unfilled",
            )
        
        # 2. 레벨별 주문 분할 & 체결
        filled_qty, total_cost = self._execute_across_levels(context, levels)
        
        # 3. FillResult 생성
        unfilled_qty = context.order_quantity - filled_qty
        fill_ratio = filled_qty / context.order_quantity if context.order_quantity > 0 else 0.0
        
        if filled_qty > 0:
            effective_price = total_cost / filled_qty
            slippage_bps = abs((effective_price - context.target_price) / context.target_price * 10000.0) if context.target_price > 0 else 0.0
        else:
            effective_price = context.target_price
            slippage_bps = 0.0
        
        # Status 결정
        if filled_qty == 0:
            status = "unfilled"
        elif filled_qty < context.order_quantity:
            status = "partially_filled"
        else:
            status = "filled"
        
        logger.debug(
            f"[D81-1_ADVANCED_FILL] {context.symbol} {context.side.value}: "
            f"주문={context.order_quantity:.4f}, 체결={filled_qty:.4f}, "
            f"가격={context.target_price:.2f}→{effective_price:.2f}, "
            f"슬리피지={slippage_bps:.2f}bps, 상태={status}, "
            f"레벨={len(levels)}, fill_ratio={fill_ratio:.2%}"
        )
        
        return FillResult(
            filled_quantity=filled_qty,
            unfilled_quantity=unfilled_qty,
            effective_price=effective_price,
            slippage_bps=slippage_bps,
            fill_ratio=fill_ratio,
            status=status,
        )
    
    def _generate_virtual_levels(
        self, context: FillContext
    ) -> list:
        """
        가상 L2 레벨 생성
        
        각 레벨은 (price, available_volume) 튜플.
        
        Args:
            context: 주문 정보
        
        Returns:
            List of (level_price, level_volume)
        """
        import math
        
        levels = []
        base_volume = context.available_volume * self.base_volume_multiplier
        
        if base_volume <= 0:
            return []
        
        for i in range(self.num_levels):
            # 레벨 가격 계산
            if context.side == OrderSide.BUY:
                # 매수: ask 가격이 증가
                level_price = context.target_price * (1.0 + self.level_spacing_bps * i / 10000.0)
            else:
                # 매도: bid 가격이 감소
                level_price = context.target_price * (1.0 - self.level_spacing_bps * i / 10000.0)
            
            # 레벨별 유동성: 지수 감소
            level_volume = base_volume * math.exp(-self.decay_rate * i)
            
            levels.append((level_price, level_volume))
        
        return levels
    
    def _execute_across_levels(
        self, context: FillContext, levels: list
    ) -> Tuple[float, float]:
        """
        레벨별로 주문 분할 체결
        
        Args:
            context: 주문 정보
            levels: 가상 L2 레벨 리스트
        
        Returns:
            (total_filled_qty, total_cost)
        """
        remaining_qty = context.order_quantity
        total_cost = 0.0
        total_filled_qty = 0.0
        slippage_alpha = context.slippage_alpha or self.default_slippage_alpha
        
        for level_price, level_volume in levels:
            if remaining_qty <= 0:
                break
            
            if not self.enable_partial_fill:
                # Partial Fill 비활성화: 전량 체결 가정
                fill_at_level = remaining_qty
            else:
                # 이 레벨에서 체결 가능한 수량
                fill_at_level = min(remaining_qty, level_volume)
            
            if fill_at_level <= 0:
                continue
            
            # 이 레벨의 slippage 계산 (비선형)
            if self.enable_slippage and level_volume > 0:
                level_impact_factor = min(fill_at_level / level_volume, 1.0)
                # 비선형 지수 적용
                level_slippage_ratio = slippage_alpha * (level_impact_factor ** self.slippage_exponent)
                
                if context.side == OrderSide.BUY:
                    level_effective_price = level_price * (1.0 + level_slippage_ratio)
                else:
                    level_effective_price = level_price * (1.0 - level_slippage_ratio)
            else:
                level_effective_price = level_price
            
            # 이 레벨에서의 비용
            total_cost += fill_at_level * level_effective_price
            total_filled_qty += fill_at_level
            remaining_qty -= fill_at_level
        
        return total_filled_qty, total_cost


@dataclass
class CalibrationZone:
    """
    D84-1: Calibration Zone 정의
    
    Entry/TP Threshold 구간별 Fill Ratio 보정 정보.
    
    Attributes:
        zone_id: Zone 식별자 (예: "Z1", "Z2")
        entry_min: Entry Threshold 하한 (bps)
        entry_max: Entry Threshold 상한 (bps)
        tp_min: TP Threshold 하한 (bps)
        tp_max: TP Threshold 상한 (bps)
        buy_fill_ratio: BUY 체결률 (0.0 ~ 1.0)
        sell_fill_ratio: SELL 체결률 (0.0 ~ 1.0)
        samples: 샘플 수 (통계적 신뢰도)
    """
    zone_id: str
    entry_min: float
    entry_max: float
    tp_min: float
    tp_max: float
    buy_fill_ratio: float
    sell_fill_ratio: float
    samples: int


@dataclass
class CalibrationTable:
    """
    D84-1: Calibration Table
    
    Zone별 Fill Ratio 보정 데이터를 담는 테이블.
    
    Attributes:
        version: Calibration 버전 (예: "d84_1")
        zones: Zone 리스트
        default_buy_fill_ratio: Zone 미매칭 시 기본 BUY Fill Ratio
        default_sell_fill_ratio: Zone 미매칭 시 기본 SELL Fill Ratio
        created_at: 생성 시각
        source: 데이터 출처
    """
    version: str
    zones: list
    default_buy_fill_ratio: float
    default_sell_fill_ratio: float
    created_at: str
    source: str
    
    def select_zone(self, entry_bps: float, tp_bps: float) -> CalibrationZone:
        """
        Entry/TP에 해당하는 Zone 선택
        
        Args:
            entry_bps: Entry Threshold (bps)
            tp_bps: TP Threshold (bps)
        
        Returns:
            매칭된 Zone (없으면 None)
        """
        for zone_data in self.zones:
            if isinstance(zone_data, dict):
                # CalibrationZone에 필요한 필드만 추출
                zone = CalibrationZone(
                    zone_id=zone_data["zone_id"],
                    entry_min=zone_data["entry_min"],
                    entry_max=zone_data["entry_max"],
                    tp_min=zone_data["tp_min"],
                    tp_max=zone_data["tp_max"],
                    buy_fill_ratio=zone_data["buy_fill_ratio"],
                    sell_fill_ratio=zone_data["sell_fill_ratio"],
                    samples=zone_data["samples"],
                )
            else:
                zone = zone_data
            
            if (zone.entry_min <= entry_bps <= zone.entry_max and
                zone.tp_min <= tp_bps <= zone.tp_max):
                return zone
        return None
    
    def get_fill_ratio(self, zone: CalibrationZone, side: OrderSide) -> float:
        """
        Zone/side별 Fill Ratio 반환
        
        Args:
            zone: Calibration Zone (None이면 기본값)
            side: OrderSide (BUY/SELL)
        
        Returns:
            Fill Ratio (0.0 ~ 1.0)
        """
        if zone is None:
            return self.default_buy_fill_ratio if side == OrderSide.BUY else self.default_sell_fill_ratio
        
        return zone.buy_fill_ratio if side == OrderSide.BUY else zone.sell_fill_ratio


class CalibratedFillModel(BaseFillModel):
    """
    D84-1: Calibrated Fill Model v1
    
    실측 데이터 기반 Zone별 Fill Ratio 보정.
    
    메커니즘:
        1. 기존 SimpleFillModel로 baseline Fill 계산
        2. Entry/TP Zone 판단
        3. Zone별 Calibration Ratio 적용
        4. 최종 Fill Ratio = baseline * calibration_ratio
    
    특징:
        - DO-NOT-TOUCH: SimpleFillModel 로직 그대로 사용
        - 상속 대신 Composition으로 기존 모델 재사용
        - Zone 미매칭 시 기본 모델 동작 유지
    
    Args:
        base_model: 기존 Fill Model (SimpleFillModel 또는 AdvancedFillModel)
        calibration: Calibration Table
        entry_bps: Entry Threshold (Zone matching용)
        tp_bps: TP Threshold (Zone matching용)
    """
    
    def __init__(
        self,
        base_model: BaseFillModel,
        calibration: CalibrationTable,
        entry_bps: float = 0.0,
        tp_bps: float = 0.0,
    ):
        """
        CalibratedFillModel 초기화
        
        Args:
            base_model: 기존 Fill Model
            calibration: Calibration Table
            entry_bps: Entry Threshold
            tp_bps: TP Threshold
        """
        self.base_model = base_model
        self.calibration = calibration
        self.entry_bps = entry_bps
        self.tp_bps = tp_bps
        
        # Zone 선택
        self.zone = calibration.select_zone(entry_bps, tp_bps)
        zone_id = self.zone.zone_id if self.zone else "DEFAULT"
        
        logger.info(
            f"[D84-1_CALIBRATED_FILL_MODEL] 초기화: "
            f"Entry={entry_bps:.1f}bps, TP={tp_bps:.1f}bps, "
            f"Zone={zone_id}, "
            f"Calibration={calibration.version}"
        )
    
    def execute(self, context: FillContext) -> FillResult:
        """
        Calibrated Fill Model 실행
        
        1. 기존 모델로 baseline Fill 계산
        2. Zone/side별 Calibration Ratio 적용
        3. Fill Ratio 보정
        
        Args:
            context: 주문 및 시장 정보
        
        Returns:
            Calibration이 적용된 체결 결과
        """
        # 1. 기존 모델로 baseline 계산
        base_result = self.base_model.execute(context)
        
        # 2. Calibration Ratio 가져오기
        calibrated_fill_ratio = self.calibration.get_fill_ratio(self.zone, context.side)
        
        # 3. Fill Ratio 보정 (baseline 대비 calibrated 비율 적용)
        # 예: baseline=0.5, calibrated=0.3 → 최종=0.3 (calibrated 값을 직접 사용)
        if calibrated_fill_ratio > 0:
            adjustment_factor = calibrated_fill_ratio / max(base_result.fill_ratio, 0.01)
            adjusted_filled_qty = base_result.filled_quantity * adjustment_factor
            adjusted_fill_ratio = calibrated_fill_ratio
        else:
            adjusted_filled_qty = base_result.filled_quantity
            adjusted_fill_ratio = base_result.fill_ratio
        
        # Clamp to valid range
        adjusted_filled_qty = min(adjusted_filled_qty, context.order_quantity)
        adjusted_filled_qty = max(adjusted_filled_qty, 0.0)
        adjusted_fill_ratio = adjusted_filled_qty / context.order_quantity if context.order_quantity > 0 else 0.0
        
        # Status 재결정
        if adjusted_filled_qty == 0:
            status = "unfilled"
        elif adjusted_filled_qty < context.order_quantity:
            status = "partially_filled"
        else:
            status = "filled"
        
        # Effective Price는 baseline 사용 (Slippage 로직은 기존 모델 그대로)
        effective_price = base_result.effective_price
        slippage_bps = base_result.slippage_bps
        
        logger.debug(
            f"[D84-1_CALIBRATED_FILL_MODEL] {context.symbol} {context.side.value}: "
            f"Baseline={base_result.fill_ratio:.4f} → Calibrated={adjusted_fill_ratio:.4f}, "
            f"Zone={self.zone.zone_id if self.zone else 'DEFAULT'}"
        )
        
        return FillResult(
            filled_quantity=adjusted_filled_qty,
            unfilled_quantity=context.order_quantity - adjusted_filled_qty,
            effective_price=effective_price,
            slippage_bps=slippage_bps,
            fill_ratio=adjusted_fill_ratio,
            status=status,
        )


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
