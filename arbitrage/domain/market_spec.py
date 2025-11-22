"""
D75-4: Market Specification

거래소별 시장 스펙:
- 통화 단위 (KRW, USD, USDT)
- 환율 정규화
- Tick size, Lot size
"""

from dataclasses import dataclass
from typing import Literal

Currency = Literal["KRW", "USD", "USDT", "BTC"]


@dataclass
class ExchangeSpec:
    """거래소 스펙"""
    exchange_name: str  # "UPBIT", "BINANCE", etc.
    base_currency: Currency  # 기준 통화
    quote_currency: Currency  # 호가 통화
    
    # Price/Quantity precision
    price_decimals: int = 2
    quantity_decimals: int = 8
    
    # Tick/Lot size
    min_tick_size: float = 0.01
    min_lot_size: float = 0.00001
    
    # Orderbook depth
    orderbook_depth: int = 20
    
    def __post_init__(self):
        """Validation"""
        if self.exchange_name not in ["UPBIT", "BINANCE", "BYBIT", "OKX", "BITGET"]:
            raise ValueError(f"Unsupported exchange: {self.exchange_name}")


@dataclass
class MarketSpec:
    """
    두 거래소 간 마켓 스펙 매핑.
    
    예: Upbit KRW-BTC ↔ Binance BTCUSDT
    """
    exchange_a: ExchangeSpec
    exchange_b: ExchangeSpec
    symbol_a: str  # e.g., "KRW-BTC"
    symbol_b: str  # e.g., "BTCUSDT"
    
    # FX normalization
    fx_rate_a_to_b: float = 1.0  # A 통화 → B 통화 환율
    
    def normalize_price_a_to_b(self, price_a: float) -> float:
        """
        Exchange A 가격을 Exchange B 기준으로 정규화.
        
        예: Upbit KRW 100,000,000 → Binance USD 73,000
        (fx_rate = 1370 KRW/USD)
        """
        return price_a / self.fx_rate_a_to_b
    
    def normalize_price_b_to_a(self, price_b: float) -> float:
        """Exchange B 가격을 Exchange A 기준으로 정규화"""
        return price_b * self.fx_rate_a_to_b
    
    def spread_bps(self, price_a: float, price_b: float) -> float:
        """
        Spread 계산 (basis points).
        
        price_a와 price_b를 정규화 후 spread 계산.
        양수: A가 높음 (Buy B, Sell A)
        음수: B가 높음 (Buy A, Sell B)
        """
        price_a_norm = self.normalize_price_a_to_b(price_a)
        return (price_a_norm - price_b) / price_b * 10_000.0


# ================================================
# Preset Exchange Specs
# ================================================

UPBIT_SPEC = ExchangeSpec(
    exchange_name="UPBIT",
    base_currency="BTC",
    quote_currency="KRW",
    price_decimals=0,
    quantity_decimals=8,
    min_tick_size=1000.0,  # 1,000 KRW
    min_lot_size=0.00000001,
)

BINANCE_SPEC = ExchangeSpec(
    exchange_name="BINANCE",
    base_currency="BTC",
    quote_currency="USDT",
    price_decimals=2,
    quantity_decimals=6,
    min_tick_size=0.01,
    min_lot_size=0.00001,
)


def create_market_spec_upbit_binance(
    symbol_a: str = "KRW-BTC",
    symbol_b: str = "BTCUSDT",
    krw_usd_rate: float = 1370.0,
) -> MarketSpec:
    """Upbit-Binance 마켓 스펙 생성"""
    return MarketSpec(
        exchange_a=UPBIT_SPEC,
        exchange_b=BINANCE_SPEC,
        symbol_a=symbol_a,
        symbol_b=symbol_b,
        fx_rate_a_to_b=krw_usd_rate,
    )
