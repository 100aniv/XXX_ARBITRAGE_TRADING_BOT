# -*- coding: utf-8 -*-
"""
D80-4: Fill Model Unit Tests
Fill Model 모듈 단위 테스트

테스트 대상:
    - FillContext, FillResult 데이터 구조
    - SimpleFillModel: Partial Fill + Slippage
    - 각종 엣지 케이스

Author: arbitrage-lite project
Date: 2025-12-04
"""

import pytest
from arbitrage.execution.fill_model import (
    FillContext,
    FillResult,
    SimpleFillModel,
    create_default_fill_model,
)
from arbitrage.types import OrderSide


class TestFillModel:
    """Fill Model 테스트 클래스"""
    
    def test_partial_fill_sufficient_volume(self):
        """
        테스트 1: 호가 잔량 충분 → 전량 체결
        
        조건:
            - 주문 수량: 10.0
            - 호가 잔량: 20.0 (충분)
        
        기대 결과:
            - filled_qty = 10.0 (전량)
            - unfilled_qty = 0.0
            - fill_ratio = 1.0
            - status = "filled"
        """
        fill_model = SimpleFillModel(
            enable_partial_fill=True,
            enable_slippage=False,  # 슬리피지 비활성화 (Partial Fill만 테스트)
        )
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=10.0,
            target_price=100000.0,
            available_volume=20.0,  # 충분
        )
        
        result = fill_model.execute(context)
        
        assert result.filled_quantity == 10.0
        assert result.unfilled_quantity == 0.0
        assert result.fill_ratio == 1.0
        assert result.status == "filled"
        assert result.effective_price == 100000.0  # 슬리피지 없음
    
    def test_partial_fill_insufficient_volume(self):
        """
        테스트 2: 호가 잔량 부족 → 부분 체결
        
        조건:
            - 주문 수량: 10.0
            - 호가 잔량: 6.5 (부족)
        
        기대 결과:
            - filled_qty = 6.5 (호가 잔량만큼만)
            - unfilled_qty = 3.5
            - fill_ratio = 0.65
            - status = "partially_filled"
        """
        fill_model = SimpleFillModel(
            enable_partial_fill=True,
            enable_slippage=False,
        )
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=10.0,
            target_price=100000.0,
            available_volume=6.5,  # 부족
        )
        
        result = fill_model.execute(context)
        
        assert result.filled_quantity == 6.5
        assert result.unfilled_quantity == 3.5
        assert abs(result.fill_ratio - 0.65) < 0.01
        assert result.status == "partially_filled"
    
    def test_partial_fill_no_volume(self):
        """
        테스트 3: 호가 잔량 없음 → 미체결
        
        조건:
            - 주문 수량: 10.0
            - 호가 잔량: 0.0 (없음)
        
        기대 결과:
            - filled_qty = 0.0
            - unfilled_qty = 10.0
            - fill_ratio = 0.0
            - status = "unfilled"
        """
        fill_model = SimpleFillModel(
            enable_partial_fill=True,
            enable_slippage=False,
        )
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=10.0,
            target_price=100000.0,
            available_volume=0.0,  # 없음
        )
        
        result = fill_model.execute(context)
        
        assert result.filled_quantity == 0.0
        assert result.unfilled_quantity == 10.0
        assert result.fill_ratio == 0.0
        assert result.status == "unfilled"
    
    def test_slippage_buy_side(self):
        """
        테스트 4: 매수 시 슬리피지 → 가격 상승 (불리)
        
        조건:
            - Side: BUY
            - target_price: 100,000 USD
            - filled_qty: 6.5
            - available_volume: 10.0
            - slippage_alpha: 0.0001
        
        계산:
            - impact_factor = 6.5 / 10.0 = 0.65
            - slippage_ratio = 0.0001 * 0.65 = 0.000065
            - effective_price = 100,000 * (1 + 0.000065) = 100,006.5
            - slippage_bps = 0.65 bps
        
        기대 결과:
            - effective_price ≈ 100,006.5 (가격 상승)
            - slippage_bps ≈ 0.65
        """
        fill_model = SimpleFillModel(
            enable_partial_fill=False,  # 전량 체결 가정
            enable_slippage=True,
            default_slippage_alpha=0.0001,
        )
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=6.5,
            target_price=100000.0,
            available_volume=10.0,
        )
        
        result = fill_model.execute(context)
        
        # 가격 상승 확인
        assert result.effective_price > 100000.0
        assert abs(result.effective_price - 100006.5) < 0.1
        
        # 슬리피지 bps 확인
        assert abs(result.slippage_bps - 0.65) < 0.01
    
    def test_slippage_sell_side(self):
        """
        테스트 5: 매도 시 슬리피지 → 가격 하락 (불리)
        
        조건:
            - Side: SELL
            - target_price: 100,000 USD
            - filled_qty: 6.5
            - available_volume: 10.0
            - slippage_alpha: 0.0001
        
        계산:
            - impact_factor = 6.5 / 10.0 = 0.65
            - slippage_ratio = 0.0001 * 0.65 = 0.000065
            - effective_price = 100,000 * (1 - 0.000065) = 99,993.5
            - slippage_bps = 0.65 bps
        
        기대 결과:
            - effective_price ≈ 99,993.5 (가격 하락)
            - slippage_bps ≈ 0.65
        """
        fill_model = SimpleFillModel(
            enable_partial_fill=False,
            enable_slippage=True,
            default_slippage_alpha=0.0001,
        )
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_quantity=6.5,
            target_price=100000.0,
            available_volume=10.0,
        )
        
        result = fill_model.execute(context)
        
        # 가격 하락 확인
        assert result.effective_price < 100000.0
        assert abs(result.effective_price - 99993.5) < 0.1
        
        # 슬리피지 bps 확인
        assert abs(result.slippage_bps - 0.65) < 0.01
    
    def test_slippage_disabled(self):
        """
        테스트 6: 슬리피지 비활성화 → 가격 변동 없음
        
        조건:
            - enable_slippage = False
        
        기대 결과:
            - effective_price == target_price (변동 없음)
            - slippage_bps = 0.0
        """
        fill_model = SimpleFillModel(
            enable_partial_fill=False,
            enable_slippage=False,  # 비활성화
        )
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=6.5,
            target_price=100000.0,
            available_volume=10.0,
        )
        
        result = fill_model.execute(context)
        
        assert result.effective_price == 100000.0  # 변동 없음
        assert result.slippage_bps == 0.0
    
    def test_fill_result_status(self):
        """
        테스트 7: FillResult 상태 결정 로직 검증
        
        - filled = 0 → "unfilled"
        - filled < order → "partially_filled"
        - filled == order → "filled"
        """
        fill_model = SimpleFillModel()
        
        # Case 1: 미체결
        context_unfilled = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=10.0,
            target_price=100000.0,
            available_volume=0.0,
        )
        result_unfilled = fill_model.execute(context_unfilled)
        assert result_unfilled.status == "unfilled"
        
        # Case 2: 부분 체결
        context_partial = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=10.0,
            target_price=100000.0,
            available_volume=5.0,
        )
        result_partial = fill_model.execute(context_partial)
        assert result_partial.status == "partially_filled"
        
        # Case 3: 전량 체결
        context_filled = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=10.0,
            target_price=100000.0,
            available_volume=20.0,
        )
        result_filled = fill_model.execute(context_filled)
        assert result_filled.status == "filled"
    
    def test_combined_partial_fill_and_slippage(self):
        """
        테스트 8: Partial Fill + Slippage 동시 적용
        
        조건:
            - 주문 수량: 10.0
            - 호가 잔량: 6.5 (부분 체결)
            - slippage_alpha: 0.0002 (기본값보다 큰 값)
        
        기대 결과:
            - filled_qty = 6.5 (부분 체결)
            - effective_price != target_price (슬리피지 반영)
            - slippage_bps > 0
            - status = "partially_filled"
        """
        fill_model = SimpleFillModel(
            enable_partial_fill=True,
            enable_slippage=True,
            default_slippage_alpha=0.0002,
        )
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=10.0,
            target_price=100000.0,
            available_volume=6.5,
        )
        
        result = fill_model.execute(context)
        
        # Partial Fill 확인
        assert result.filled_quantity == 6.5
        assert result.unfilled_quantity == 3.5
        assert result.status == "partially_filled"
        
        # Slippage 확인
        assert result.effective_price > 100000.0  # BUY: 가격 상승
        assert result.slippage_bps > 0
    
    def test_create_default_fill_model(self):
        """
        테스트 9: 편의 함수 create_default_fill_model() 검증
        
        기본 설정으로 SimpleFillModel 인스턴스 생성 확인.
        """
        fill_model = create_default_fill_model(
            enable_partial_fill=True,
            enable_slippage=True,
            slippage_alpha=0.00015,
        )
        
        assert isinstance(fill_model, SimpleFillModel)
        assert fill_model.enable_partial_fill is True
        assert fill_model.enable_slippage is True
        assert fill_model.default_slippage_alpha == 0.00015
    
    def test_edge_case_zero_order_quantity(self):
        """
        테스트 10: 엣지 케이스 - 주문 수량 0
        
        기대 결과:
            - filled_qty = 0
            - status = "unfilled"
        """
        fill_model = SimpleFillModel()
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=0.0,  # 0
            target_price=100000.0,
            available_volume=10.0,
        )
        
        result = fill_model.execute(context)
        
        assert result.filled_quantity == 0.0
        assert result.status == "unfilled"
    
    def test_edge_case_zero_target_price(self):
        """
        테스트 11: 엣지 케이스 - 목표 가격 0
        
        기대 결과:
            - filled_qty = 0
            - status = "unfilled"
        """
        fill_model = SimpleFillModel()
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=10.0,
            target_price=0.0,  # 0
            available_volume=10.0,
        )
        
        result = fill_model.execute(context)
        
        assert result.filled_quantity == 0.0
        assert result.status == "unfilled"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
