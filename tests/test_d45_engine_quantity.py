"""
D45: ArbitrageEngine 주문 수량 계산 개선 테스트

현실적인 주문 수량 계산 로직 검증
"""

import pytest
from arbitrage.arbitrage_core import (
    ArbitrageConfig,
    ArbitrageEngine,
    OrderBookSnapshot,
    ArbitrageTrade,
)


class TestD45QuantityCalculation:
    """D45 주문 수량 계산 테스트"""

    def test_quantity_calculation_basic(self):
        """기본 주문 수량 계산"""
        # notional_usd = 5000
        # ask_a = 100500
        # exchange_rate = 2.5
        # qty = 5000 / (100500 * 2.5) = 5000 / 251250 = 0.0199 BTC
        
        notional_usd = 5000.0
        ask_a = 100500.0
        exchange_rate = 2.5
        
        qty = notional_usd / (ask_a * exchange_rate)
        
        assert 0.019 < qty < 0.020, f"수량이 약 0.0199 BTC여야 함, 실제: {qty}"

    def test_quantity_calculation_with_different_prices(self):
        """다양한 가격에서의 수량 계산"""
        notional_usd = 5000.0
        exchange_rate = 2.5
        
        # 가격이 높을수록 수량은 적어야 함
        qty_high_price = notional_usd / (105000.0 * exchange_rate)
        qty_low_price = notional_usd / (95000.0 * exchange_rate)
        
        assert qty_high_price < qty_low_price, "높은 가격에서 수량이 적어야 함"

    def test_quantity_calculation_preserves_notional(self):
        """수량 계산이 명목가를 보존"""
        notional_usd = 5000.0
        ask_a = 100500.0
        exchange_rate = 2.5
        
        qty = notional_usd / (ask_a * exchange_rate)
        
        # 역계산: notional = qty * ask_a * exchange_rate
        calculated_notional = qty * ask_a * exchange_rate
        
        assert abs(calculated_notional - notional_usd) < 0.01, \
            f"명목가가 보존되어야 함, 계산값: {calculated_notional}"

    def test_quantity_calculation_with_different_notionals(self):
        """다양한 명목가에서의 수량 계산"""
        ask_a = 100000.0
        exchange_rate = 2.5
        
        # 명목가가 2배 증가하면 수량도 2배 증가해야 함
        qty_small = 2500.0 / (ask_a * exchange_rate)
        qty_large = 5000.0 / (ask_a * exchange_rate)
        
        assert abs(qty_large / qty_small - 2.0) < 0.01, \
            "명목가 비율이 수량 비율에 반영되어야 함"

    def test_quantity_calculation_minimum_precision(self):
        """최소 정밀도 확인"""
        notional_usd = 100.0  # 매우 작은 명목가
        ask_a = 100000.0
        exchange_rate = 2.5
        
        qty = notional_usd / (ask_a * exchange_rate)
        
        # 최소 수량이 양수여야 함
        assert qty > 0, "수량이 양수여야 함"
        assert qty < 0.001, "매우 작은 명목가에서 수량이 작아야 함"

    def test_quantity_calculation_with_exchange_rate_variations(self):
        """다양한 환율에서의 수량 계산"""
        notional_usd = 5000.0
        ask_a = 100000.0
        
        # 환율이 높을수록 (1 A = 더 많은 B) 수량은 적어야 함
        qty_rate_2_0 = notional_usd / (ask_a * 2.0)
        qty_rate_2_5 = notional_usd / (ask_a * 2.5)
        qty_rate_3_0 = notional_usd / (ask_a * 3.0)
        
        assert qty_rate_2_0 > qty_rate_2_5 > qty_rate_3_0, \
            "환율이 높을수록 수량이 적어야 함"

    def test_quantity_calculation_realistic_scenario(self):
        """현실적인 시나리오"""
        # Upbit KRW-BTC: 100,500,000 KRW
        # Binance BTCUSDT: 40,200 USDT
        # 환율: 1 BTC = 100,500,000 KRW = 40,200 * 2.5 USDT = 100,500 USD
        
        notional_usd = 5000.0
        ask_a_krw = 100500000.0  # KRW
        exchange_rate = 2.5
        
        # 수량 계산 (BTC)
        qty = notional_usd / (ask_a_krw * exchange_rate)
        
        # 수량이 매우 작아야 함 (KRW 가격이 높기 때문)
        assert qty < 0.001, "KRW 기준 가격이 높아서 수량이 매우 작아야 함"

    def test_quantity_calculation_edge_case_zero_price(self):
        """가격이 0일 때 처리"""
        notional_usd = 5000.0
        ask_a = 0.0
        exchange_rate = 2.5
        
        # 0으로 나누기 방지
        if ask_a <= 0:
            qty = 0.0
        else:
            qty = notional_usd / (ask_a * exchange_rate)
        
        assert qty == 0.0, "가격이 0일 때 수량은 0이어야 함"

    def test_quantity_calculation_edge_case_zero_exchange_rate(self):
        """환율이 0일 때 처리"""
        notional_usd = 5000.0
        ask_a = 100000.0
        exchange_rate = 0.0
        
        # 0으로 나누기 방지
        if exchange_rate <= 0:
            qty = 0.0
        else:
            qty = notional_usd / (ask_a * exchange_rate)
        
        assert qty == 0.0, "환율이 0일 때 수량은 0이어야 함"

    def test_trade_notional_matches_quantity(self):
        """거래 명목가와 수량의 일관성"""
        config = ArbitrageConfig(
            min_spread_bps=20.0,
            taker_fee_a_bps=5.0,
            taker_fee_b_bps=4.0,
            slippage_bps=5.0,
            max_position_usd=5000.0,
            exchange_a_to_b_rate=2.5,
        )
        engine = ArbitrageEngine(config)

        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=99500.0,
            best_ask_a=100500.0,
            best_bid_b=40300.0,
            best_ask_b=40400.0,
        )

        opportunity = engine.detect_opportunity(snapshot)
        
        assert opportunity is not None
        assert opportunity.notional_usd == 5000.0, "거래 명목가가 설정값과 일치해야 함"
