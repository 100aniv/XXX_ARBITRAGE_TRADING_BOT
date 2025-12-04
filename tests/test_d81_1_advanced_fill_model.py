# -*- coding: utf-8 -*-
"""
D81-1: Advanced Fill Model Unit Tests

AdvancedFillModel의 multi-level orderbook simulation 및
partial fill 발생 로직을 검증하는 테스트.
"""

import pytest
from arbitrage.execution.fill_model import (
    AdvancedFillModel,
    FillContext,
    FillResult,
)
from arbitrage.types import OrderSide


class TestAdvancedFillModel:
    """AdvancedFillModel Unit Tests"""
    
    def test_small_order_full_fill(self):
        """작은 주문: 첫 번째 레벨에서 전량 체결"""
        model = AdvancedFillModel(
            enable_partial_fill=True,
            enable_slippage=True,
            default_slippage_alpha=0.0002,
            num_levels=5,
            level_spacing_bps=1.0,
            decay_rate=0.3,
            slippage_exponent=1.2,
            base_volume_multiplier=0.8,
        )
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=0.01,  # 작은 주문
            target_price=50000.0,
            available_volume=1.0,  # 충분한 유동성
            slippage_alpha=None,  # 기본값 사용
        )
        
        result = model.execute(context)
        
        # 전량 체결 확인
        assert result.filled_quantity == pytest.approx(0.01, rel=1e-6)
        assert result.unfilled_quantity == pytest.approx(0.0, rel=1e-6)
        assert result.fill_ratio == pytest.approx(1.0, rel=1e-6)
        assert result.status == "filled"
        
        # 슬리피지는 발생 (작지만)
        assert result.slippage_bps > 0
        assert result.slippage_bps < 1.0  # 작은 주문이므로 슬리피지 작음
    
    def test_large_order_partial_fill(self):
        """큰 주문: 여러 레벨에 걸쳐 부분 체결"""
        model = AdvancedFillModel(
            enable_partial_fill=True,
            enable_slippage=True,
            default_slippage_alpha=0.0002,
            num_levels=5,
            level_spacing_bps=1.0,
            decay_rate=0.3,
            slippage_exponent=1.2,
            base_volume_multiplier=0.8,
        )
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=10.0,  # 큰 주문
            target_price=50000.0,
            available_volume=1.0,  # 제한된 유동성
            slippage_alpha=None,
        )
        
        result = model.execute(context)
        
        # 부분 체결 확인
        assert result.filled_quantity < 10.0
        assert result.filled_quantity > 0
        assert result.unfilled_quantity > 0
        assert 0 < result.fill_ratio < 1.0
        assert result.status == "partially_filled"
        
        # 큰 주문이므로 슬리피지 증가
        assert result.slippage_bps > 0.5
    
    def test_very_large_order_all_levels_exhausted(self):
        """매우 큰 주문: 모든 레벨 소진, fill_ratio 매우 낮음"""
        model = AdvancedFillModel(
            enable_partial_fill=True,
            enable_slippage=True,
            default_slippage_alpha=0.0002,
            num_levels=3,  # 레벨 수 적음
            level_spacing_bps=1.0,
            decay_rate=0.5,  # 빠른 감소
            slippage_exponent=1.2,
            base_volume_multiplier=0.5,  # 낮은 유동성
        )
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_quantity=100.0,  # 매우 큰 주문
            target_price=50000.0,
            available_volume=0.5,  # 매우 제한된 유동성
            slippage_alpha=None,
        )
        
        result = model.execute(context)
        
        # 부분 체결, fill_ratio 낮음
        assert result.filled_quantity > 0
        assert result.filled_quantity < 100.0
        assert result.fill_ratio < 0.5  # 50% 미만 체결
        assert result.status == "partially_filled"
        
        # 매우 큰 주문이므로 슬리피지 큼
        assert result.slippage_bps > 1.0
    
    def test_edge_case_zero_order_quantity(self):
        """Edge Case: 주문 수량 0"""
        model = AdvancedFillModel()
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=0.0,  # 0 수량
            target_price=50000.0,
            available_volume=1.0,
            slippage_alpha=None,
        )
        
        result = model.execute(context)
        
        assert result.filled_quantity == 0.0
        assert result.unfilled_quantity == 0.0
        assert result.fill_ratio == 0.0
        assert result.status == "unfilled"
        assert result.slippage_bps == 0.0
    
    def test_edge_case_zero_target_price(self):
        """Edge Case: 목표 가격 0"""
        model = AdvancedFillModel()
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=1.0,
            target_price=0.0,  # 0 가격
            available_volume=1.0,
            slippage_alpha=None,
        )
        
        result = model.execute(context)
        
        assert result.filled_quantity == 0.0
        assert result.fill_ratio == 0.0
        assert result.status == "unfilled"
    
    def test_edge_case_zero_available_volume(self):
        """Edge Case: 가용 잔량 0"""
        model = AdvancedFillModel()
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=1.0,
            target_price=50000.0,
            available_volume=0.0,  # 0 잔량
            slippage_alpha=None,
        )
        
        result = model.execute(context)
        
        assert result.filled_quantity == 0.0
        assert result.fill_ratio == 0.0
        assert result.status == "unfilled"
    
    def test_buy_vs_sell_direction(self):
        """BUY vs SELL: 양방향 동일한 로직 적용"""
        model = AdvancedFillModel(
            enable_partial_fill=True,
            enable_slippage=True,
            default_slippage_alpha=0.0002,
            num_levels=5,
            level_spacing_bps=1.0,
            decay_rate=0.3,
            slippage_exponent=1.2,
            base_volume_multiplier=0.8,
        )
        
        # BUY
        context_buy = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=5.0,
            target_price=50000.0,
            available_volume=1.0,
            slippage_alpha=None,
        )
        result_buy = model.execute(context_buy)
        
        # SELL
        context_sell = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_quantity=5.0,
            target_price=50000.0,
            available_volume=1.0,
            slippage_alpha=None,
        )
        result_sell = model.execute(context_sell)
        
        # 양방향 모두 부분 체결
        assert 0 < result_buy.fill_ratio < 1.0
        assert 0 < result_sell.fill_ratio < 1.0
        
        # 슬리피지 발생
        assert result_buy.slippage_bps > 0
        assert result_sell.slippage_bps > 0
        
        # BUY: effective_price > target_price
        assert result_buy.effective_price > context_buy.target_price
        
        # SELL: effective_price < target_price
        assert result_sell.effective_price < context_sell.target_price
    
    def test_num_levels_1_behaves_like_simple(self):
        """Num Levels = 1: SimpleFillModel과 유사하게 동작"""
        model_advanced = AdvancedFillModel(
            enable_partial_fill=True,
            enable_slippage=True,
            default_slippage_alpha=0.0002,
            num_levels=1,  # 단일 레벨
            level_spacing_bps=1.0,
            decay_rate=0.3,
            slippage_exponent=1.0,  # Linear
            base_volume_multiplier=0.8,
        )
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=0.5,
            target_price=50000.0,
            available_volume=1.0,
            slippage_alpha=None,
        )
        
        result = model_advanced.execute(context)
        
        # 단일 레벨이므로 SimpleFillModel과 유사
        # (정확히 같진 않지만, 비슷한 결과)
        assert result.filled_quantity > 0
        assert result.fill_ratio > 0
    
    def test_slippage_disabled(self):
        """슬리피지 비활성화: effective_price = target_price"""
        model = AdvancedFillModel(
            enable_partial_fill=True,
            enable_slippage=False,  # 슬리피지 비활성화
            default_slippage_alpha=0.0002,
            num_levels=5,
            level_spacing_bps=1.0,
            decay_rate=0.3,
            slippage_exponent=1.2,
            base_volume_multiplier=0.8,
        )
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=0.5,
            target_price=50000.0,
            available_volume=1.0,
            slippage_alpha=None,
        )
        
        result = model.execute(context)
        
        # 슬리피지 비활성화 시 slippage_bps = 0
        assert result.slippage_bps == pytest.approx(0.0, abs=1e-6)
        # effective_price는 레벨 가격의 가중 평균 (slippage는 0이지만 레벨 간격은 있음)
        assert result.effective_price >= context.target_price
    
    def test_partial_fill_disabled(self):
        """부분 체결 비활성화: 항상 전량 체결"""
        model = AdvancedFillModel(
            enable_partial_fill=False,  # 부분 체결 비활성화
            enable_slippage=True,
            default_slippage_alpha=0.0002,
            num_levels=5,
            level_spacing_bps=1.0,
            decay_rate=0.3,
            slippage_exponent=1.2,
            base_volume_multiplier=0.8,
        )
        
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=10.0,  # 큰 주문
            target_price=50000.0,
            available_volume=0.5,  # 제한된 유동성
            slippage_alpha=None,
        )
        
        result = model.execute(context)
        
        # 부분 체결 비활성화 시 항상 전량 체결
        assert result.filled_quantity == pytest.approx(10.0, rel=1e-6)
        assert result.fill_ratio == pytest.approx(1.0, rel=1e-6)
        assert result.status == "filled"
        
        # 슬리피지는 여전히 발생 (매우 큼)
        assert result.slippage_bps > 1.0
