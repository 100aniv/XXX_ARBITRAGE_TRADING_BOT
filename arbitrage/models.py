#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Models
===========
아비트라지 봇의 핵심 데이터 구조 정의

- Ticker: 거래소별 시세 정보
- SpreadOpportunity: 스프레드 기회 정보
- Position: 포지션 정보 (진입/청산 추적)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Ticker:
    """
    거래소별 시세 정보
    
    Attributes:
        exchange: 거래소 이름 ("upbit", "binance_futures" 등)
        symbol: 심볼 ("BTC", "ETH" 등)
        price: 현재가 (거래소 원래 통화 기준, 업비트=KRW, 바이낸스=USDT)
        timestamp: Unix timestamp (밀리초)
        volume_24h: 24시간 거래량 (선택)
    
    Examples:
        >>> ticker = Ticker(
        ...     exchange="upbit",
        ...     symbol="BTC",
        ...     price=50000000.0,
        ...     timestamp=1700000000000
        ... )
    """
    exchange: str
    symbol: str
    price: float
    timestamp: int
    volume_24h: Optional[float] = None
    
    def __repr__(self):
        return f"Ticker({self.exchange}/{self.symbol}: {self.price:,.2f} @ {self.timestamp})"


@dataclass
class SpreadOpportunity:
    """
    스프레드 기회 정보
    
    DB Mapping (PHASE D):
        → spreads 테이블
        - id (PK, bigserial)
        - symbol, upbit_price, binance_price, binance_price_krw
        - spread_pct, net_spread_pct, is_opportunity
        - timestamp (hypertable 시간 컬럼, TimescaleDB 사용 시)
    
    Attributes:
        symbol: 심볼 ("BTC", "ETH" 등)
        upbit_price: 업비트 가격 (KRW)
        binance_price: 바이낸스 가격 (USDT)
        binance_price_krw: 바이낸스 가격 환산 (KRW, FX 적용)
        spread_pct: 스프레드 비율 (%) = (업비트 - 바이낸스_KRW) / 바이낸스_KRW * 100
        net_spread_pct: 순 스프레드 (%) = 수수료/슬리피지 반영 후 실제 기대 수익률
        timestamp: Unix timestamp (밀리초)
        is_opportunity: 진입 기회 여부 (net_spread_pct >= 임계값)
    
    Examples:
        >>> opp = SpreadOpportunity(
        ...     symbol="BTC",
        ...     upbit_price=50000000.0,
        ...     binance_price=37000.0,
        ...     binance_price_krw=49950000.0,
        ...     spread_pct=0.10,
        ...     net_spread_pct=0.05,
        ...     timestamp=1700000000000,
        ...     is_opportunity=False
        ... )
    """
    symbol: str
    upbit_price: float
    binance_price: float
    binance_price_krw: float
    spread_pct: float
    net_spread_pct: float
    timestamp: int
    is_opportunity: bool = False
    
    def __repr__(self):
        direction = "📈 UP" if self.spread_pct > 0 else "📉 DOWN"
        opp_mark = "✨" if self.is_opportunity else "  "
        return (f"{opp_mark} SpreadOpp({self.symbol}: {direction} "
                f"{self.spread_pct:+.2f}% | Net: {self.net_spread_pct:+.2f}%)")


@dataclass
class Position:
    """
    포지션 정보 (진입/청산 추적)
    
    DB Mapping (PHASE D):
        → positions 테이블
        - id (PK, bigserial)
        - symbol, direction, size
        - entry_upbit_price, entry_binance_price, entry_spread_pct
        - exit_upbit_price, exit_binance_price, exit_spread_pct
        - pnl_krw, pnl_pct, status
        - timestamp_open, timestamp_close (hypertable 시간 컬럼, TimescaleDB 사용 시)
    
    Attributes:
        symbol: 심볼 ("BTC" 등)
        direction: 포지션 방향
            - "long_upbit_short_binance": 업비트 매수 + 바이낸스 숏
            - "long_binance_short_upbit": 바이낸스 매수 + 업비트 숏
        size: 베이스 수량 (예: BTC 0.01)
        entry_upbit_price: 진입 시 업비트 가격 (KRW)
        entry_binance_price: 진입 시 바이낸스 가격 (USDT)
        entry_spread_pct: 진입 시 스프레드 (%)
        timestamp_open: 포지션 오픈 시각 (Unix timestamp 밀리초)
        timestamp_close: 포지션 청산 시각 (Unix timestamp 밀리초, None이면 미청산)
        exit_upbit_price: 청산 시 업비트 가격 (KRW)
        exit_binance_price: 청산 시 바이낸스 가격 (USDT)
        exit_spread_pct: 청산 시 스프레드 (%)
        pnl_krw: 손익 (KRW, None이면 미청산)
        pnl_pct: 손익률 (%, None이면 미청산)
        status: 포지션 상태 ("open", "closed")
    
    Examples:
        >>> pos = Position(
        ...     symbol="BTC",
        ...     direction="long_upbit_short_binance",
        ...     size=0.01,
        ...     entry_upbit_price=50000000.0,
        ...     entry_binance_price=37000.0,
        ...     entry_spread_pct=0.8,
        ...     timestamp_open=1700000000000
        ... )
    """
    symbol: str
    direction: str
    size: float
    entry_upbit_price: float
    entry_binance_price: float
    entry_spread_pct: float
    timestamp_open: datetime
    
    timestamp_close: Optional[datetime] = None
    exit_upbit_price: Optional[float] = None
    exit_binance_price: Optional[float] = None
    exit_spread_pct: Optional[float] = None
    pnl_krw: Optional[float] = None
    pnl_pct: Optional[float] = None
    status: str = "OPEN"
    
    def __repr__(self):
        status_mark = "🔓" if self.status == "OPEN" else "🔒"
        pnl_str = f"PnL: {self.pnl_pct:+.2f}%" if self.pnl_pct is not None else "PnL: N/A"
        return (f"{status_mark} Position({self.symbol} {self.direction} "
                f"size={self.size} | {pnl_str})")
    
    def close(self, exit_upbit_price: float, exit_binance_price: float, 
              exit_spread_pct: float, pnl_krw: float, pnl_pct: float, 
              timestamp_close: datetime):
        """
        포지션 청산
        
        Args:
            exit_upbit_price: 청산 시 업비트 가격
            exit_binance_price: 청산 시 바이낸스 가격
            exit_spread_pct: 청산 시 스프레드
            pnl_krw: 손익 (KRW)
            pnl_pct: 손익률 (%)
            timestamp_close: 청산 시각
        """
        self.exit_upbit_price = exit_upbit_price
        self.exit_binance_price = exit_binance_price
        self.exit_spread_pct = exit_spread_pct
        self.pnl_krw = pnl_krw
        self.pnl_pct = pnl_pct
        self.timestamp_close = timestamp_close
        self.status = "CLOSED"


@dataclass
class TradeSignal:
    """
    거래 시그널 (진입/청산 신호)
    
    Attributes:
        symbol: 심볼
        action: 액션 ("OPEN", "CLOSE", "HOLD")
        direction: 포지션 방향 (action="OPEN"일 때만 유효)
        spread_opportunity: 관련 스프레드 기회 정보
        reason: 시그널 발생 이유
        timestamp: Unix timestamp (밀리초)
    
    Examples:
        >>> signal = TradeSignal(
        ...     symbol="BTC",
        ...     action="enter",
        ...     direction="long_upbit_short_binance",
        ...     spread_opportunity=opp,
        ...     reason="Net spread 0.8% > threshold 0.5%",
        ...     timestamp=1700000000000
        ... )
    """
    symbol: str
    action: str  # "OPEN", "CLOSE", "HOLD"
    direction: Optional[str] = None
    spread_opportunity: Optional[SpreadOpportunity] = None
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __repr__(self):
        action_emoji = {"OPEN": "🟢", "CLOSE": "🔴", "HOLD": "⏸️"}.get(self.action.upper(), "❓")
        return f"{action_emoji} TradeSignal({self.symbol} {self.action} | {self.reason})"


@dataclass
class OrderLeg:
    """
    주문 레그 (Order Routing & Slippage Model)
    
    포지션의 한쪽 레그(거래소별 주문)를 표현합니다.
    한 포지션은 일반적으로 2개의 OrderLeg로 구성됩니다:
    - Upbit leg (spot: buy/sell)
    - Binance leg (futures: long/short)
    
    DB Mapping (PHASE D):
        → orders 테이블
        - id (PK, bigserial)
        - position_id (FK → positions.id)
        - symbol, venue, side, qty
        - price_theoretical, price_effective, slippage_bps
        - leg_id, order_id
        - timestamp (hypertable 시간 컬럼, TimescaleDB 사용 시)
    
    Attributes:
        symbol: 심볼 ("BTC" 등)
        venue: 거래소 ("upbit" | "binance_futures")
        side: 주문 방향
            - "buy" / "sell" (Upbit spot)
            - "long" / "short" (Binance futures)
        qty: 주문 수량 (베이스 심볼 기준, 예: BTC 0.01)
        price_theoretical: 이론 체결가 (슬리피지 적용 전)
        price_effective: 실제 체결가 (슬리피지 적용 후, None이면 미체결)
        slippage_bps: 적용된 슬리피지 (bps, 기본값 None)
        timestamp: 주문 생성 시각 (UTC timezone aware)
        leg_id: 포지션 내 유니크 ID (예: "pos_123_leg_0")
        order_id: 거래소 주문 ID (Live 모드에서 채워짐, Paper 모드에서는 None)
    
    Examples:
        >>> leg = OrderLeg(
        ...     symbol="BTC",
        ...     venue="upbit",
        ...     side="sell",
        ...     qty=0.01,
        ...     price_theoretical=145500000.0,
        ...     price_effective=145485000.0,
        ...     slippage_bps=10,
        ...     timestamp=datetime.now(timezone.utc),
        ...     leg_id="pos_001_leg_0",
        ...     order_id=None
        ... )
    """
    symbol: str
    venue: str  # "upbit" | "binance_futures"
    side: str  # "buy" | "sell" | "long" | "short"
    qty: float
    price_theoretical: float
    timestamp: datetime
    leg_id: str
    
    price_effective: Optional[float] = None
    slippage_bps: Optional[float] = None
    order_id: Optional[str] = None
    
    def __repr__(self):
        slippage_str = f" (slippage: {self.slippage_bps:.1f}bps)" if self.slippage_bps is not None else ""
        return (f"OrderLeg({self.symbol} {self.venue}/{self.side} qty={self.qty:.6f} "
                f"price={self.price_effective or self.price_theoretical:,.0f}{slippage_str})")
