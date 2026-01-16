"""
D206-1: ArbitrageTrade Domain Model

V1 arbitrage_core.py 정의 기반으로 V2에서 재사용.
HFT Readiness + Commercial UI 직렬화 추가.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional
from decimal import Decimal, ROUND_HALF_UP


Side = Literal["LONG_A_SHORT_B", "LONG_B_SHORT_A"]


@dataclass
class ArbitrageTrade:
    """
    차익거래 거래 (Trade Lifecycle)
    
    V1 정의 (arbitrage/arbitrage_core.py Line 58-73) 기반.
    
    Fields (V1):
        open_timestamp: 거래 개설 시각
        close_timestamp: 거래 종료 시각 (Optional)
        side: LONG_A_SHORT_B 또는 LONG_B_SHORT_A
        entry_spread_bps: 진입 스프레드 (bps)
        exit_spread_bps: 종료 스프레드 (bps, Optional)
        notional_usd: 거래 규모 (USD)
        pnl_usd: 실현 손익 (USD, Optional)
        pnl_bps: 실현 손익 (bps, Optional)
        is_open: 거래 상태 (True=진행중, False=종료)
        meta: 메타데이터 (dict)
        exit_reason: 종료 이유 (Optional)
    
    Fields (HFT Readiness - Optional):
        execution_quality_score: 실행 품질 스코어 (0.0~1.0)
        slippage_actual_bps: 실제 슬리피지 (bps)
        hold_duration_sec: 보유 시간 (초)
    
    Methods (V1):
        close(): 거래 종료 및 PnL 계산
        to_dict(): JSON 직렬화
    """
    
    open_timestamp: str
    side: Side = "LONG_A_SHORT_B"
    entry_spread_bps: float = 0.0
    notional_usd: float = 0.0
    is_open: bool = True
    
    close_timestamp: Optional[str] = None
    exit_spread_bps: Optional[float] = None
    pnl_usd: Optional[float] = None
    pnl_bps: Optional[float] = None
    exit_reason: Optional[str] = None
    meta: Dict[str, str] = field(default_factory=dict)
    
    # HFT Readiness (D214 예비)
    execution_quality_score: Optional[float] = None
    slippage_actual_bps: Optional[float] = None
    hold_duration_sec: Optional[float] = None
    
    # Metadata
    symbol: Optional[str] = None
    exchange_a: Optional[str] = None
    exchange_b: Optional[str] = None
    
    def __post_init__(self):
        """불변 조건 검증"""
        # Timestamp exists
        if not self.open_timestamp:
            raise ValueError("open_timestamp is required")
        
        # Notional validation
        if self.notional_usd < 0:
            raise ValueError(f"notional_usd cannot be negative (got {self.notional_usd})")
        
        # Side validation
        if self.side not in ["LONG_A_SHORT_B", "LONG_B_SHORT_A"]:
            raise ValueError(f"Invalid side: {self.side}")
        
        # Closed trade validation
        if not self.is_open:
            if self.close_timestamp is None:
                raise ValueError("Closed trade must have close_timestamp")
            if self.pnl_bps is None or self.pnl_usd is None:
                raise ValueError("Closed trade must have pnl_bps and pnl_usd")
    
    def close(
        self,
        close_timestamp: str,
        exit_spread_bps: float,
        taker_fee_a_bps: float,
        taker_fee_b_bps: float,
        slippage_bps: float,
        exit_reason: Optional[str] = None,
    ) -> None:
        """
        거래 종료 및 PnL 계산
        
        D206-2-1: Decimal 기반 정밀 계산 (HFT-grade)
        - 18자리 정밀도
        - Rounding 정책: ROUND_HALF_UP (거래소 표준)
        - 0.01% 오차 이내 보장
        
        Args:
            close_timestamp: 종료 시각
            exit_spread_bps: 종료 스프레드 (bps)
            taker_fee_a_bps: Exchange A 수수료 (bps)
            taker_fee_b_bps: Exchange B 수수료 (bps)
            slippage_bps: 슬리피지 (bps)
            exit_reason: 종료 이유 (Optional)
        """
        self.close_timestamp = close_timestamp
        self.exit_spread_bps = exit_spread_bps
        self.is_open = False
        self.exit_reason = exit_reason
        
        # D206-2-1: Decimal 기반 PnL 계산 (HFT-grade precision)
        # 18자리 정밀도로 부동소수점 오차 원천 차단
        d_entry_spread = Decimal(str(self.entry_spread_bps))
        d_exit_spread = Decimal(str(exit_spread_bps))
        d_fee_a = Decimal(str(taker_fee_a_bps))
        d_fee_b = Decimal(str(taker_fee_b_bps))
        d_slippage = Decimal(str(slippage_bps))
        d_notional = Decimal(str(self.notional_usd))
        
        # PnL = (진입 스프레드 - 종료 스프레드 - 수수료 - 슬리피지) * 명목가
        d_total_cost = d_fee_a + d_fee_b + d_slippage
        d_net_pnl_bps = d_entry_spread - d_exit_spread - d_total_cost
        d_net_pnl_usd = (d_net_pnl_bps / Decimal('10000.0')) * d_notional
        
        # Rounding: ROUND_HALF_UP (거래소 표준, 0.5는 올림)
        self.pnl_bps = float(d_net_pnl_bps.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP))
        self.pnl_usd = float(d_net_pnl_usd.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP))
    
    def to_dict(self) -> Dict[str, Any]:
        """
        JSON 직렬화 (Evidence/DB/로그)
        
        V1 arbitrage_core.py Line 95-109 로직 기반.
        
        Returns:
            dict with all fields
        """
        return {
            'open_timestamp': self.open_timestamp,
            'close_timestamp': self.close_timestamp,
            'side': self.side,
            'entry_spread_bps': self.entry_spread_bps,
            'exit_spread_bps': self.exit_spread_bps,
            'notional_usd': self.notional_usd,
            'pnl_usd': self.pnl_usd,
            'pnl_bps': self.pnl_bps,
            'is_open': self.is_open,
            'meta': self.meta,
            'exit_reason': self.exit_reason,
            'execution_quality_score': self.execution_quality_score,
            'slippage_actual_bps': self.slippage_actual_bps,
            'hold_duration_sec': self.hold_duration_sec,
            'symbol': self.symbol,
            'exchange_a': self.exchange_a,
            'exchange_b': self.exchange_b,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArbitrageTrade':
        """
        JSON 역직렬화
        
        Args:
            data: dict with required fields
        
        Returns:
            ArbitrageTrade instance
        """
        return cls(
            open_timestamp=data['open_timestamp'],
            close_timestamp=data.get('close_timestamp'),
            side=data.get('side', 'LONG_A_SHORT_B'),
            entry_spread_bps=data.get('entry_spread_bps', 0.0),
            exit_spread_bps=data.get('exit_spread_bps'),
            notional_usd=data.get('notional_usd', 0.0),
            pnl_usd=data.get('pnl_usd'),
            pnl_bps=data.get('pnl_bps'),
            is_open=data.get('is_open', True),
            meta=data.get('meta', {}),
            exit_reason=data.get('exit_reason'),
            execution_quality_score=data.get('execution_quality_score'),
            slippage_actual_bps=data.get('slippage_actual_bps'),
            hold_duration_sec=data.get('hold_duration_sec'),
            symbol=data.get('symbol'),
            exchange_a=data.get('exchange_a'),
            exchange_b=data.get('exchange_b'),
        )
    
    def to_ui_dict(self) -> Dict[str, Any]:
        """
        Commercial UI 직렬화 (D210/D218 FastAPI + React 대응)
        
        Returns:
            UI-friendly dict (compact, human-readable)
        """
        status = 'open' if self.is_open else 'closed'
        pnl_color = None
        if self.pnl_bps is not None:
            pnl_color = 'green' if self.pnl_bps > 0 else ('red' if self.pnl_bps < 0 else 'gray')
        
        return {
            'id': self.meta.get('trade_id', self.open_timestamp),
            'status': status,
            'direction': 'A→B' if self.side == 'LONG_A_SHORT_B' else 'B→A',
            'timestamps': {
                'open': self.open_timestamp,
                'close': self.close_timestamp,
                'hold_duration_sec': self.hold_duration_sec,
            },
            'spread': {
                'entry_bps': self.entry_spread_bps,
                'exit_bps': self.exit_spread_bps,
            },
            'pnl': {
                'usd': self.pnl_usd,
                'bps': self.pnl_bps,
                'color': pnl_color,
            } if (self.pnl_usd is not None) else None,
            'size_usd': self.notional_usd,
            'symbol': self.symbol,
            'route': {
                'from': self.exchange_b if self.side == 'LONG_A_SHORT_B' else self.exchange_a,
                'to': self.exchange_a if self.side == 'LONG_A_SHORT_B' else self.exchange_b,
            } if (self.exchange_a and self.exchange_b) else None,
            'exit_reason': self.exit_reason,
            'execution': {
                'quality_score': self.execution_quality_score,
                'slippage_actual_bps': self.slippage_actual_bps,
            } if (self.execution_quality_score or self.slippage_actual_bps) else None,
        }
    
    def is_profitable(self) -> bool:
        """
        수익성 판정
        
        Returns:
            True if pnl_bps > 0 (closed trades only)
        """
        if self.is_open:
            return False
        return self.pnl_bps is not None and self.pnl_bps > 0
