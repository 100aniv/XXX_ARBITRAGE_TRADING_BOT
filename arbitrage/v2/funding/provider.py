"""
D205-15-3: Funding Rate Provider

Binance Futures 펀딩비 수집 모듈
- /fapi/v1/premiumIndex 엔드포인트 활용
- funding_adjusted_edge_bps 계산 지원

SSOT: D_ROADMAP.md D205-15-3 AC-3, AC-4
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class FundingRateInfo:
    """펀딩비 정보 데이터클래스"""
    symbol: str
    funding_rate: float  # 8시간 펀딩비 (예: 0.0001 = 0.01%)
    funding_rate_bps: float  # bps 단위 (예: 1.0 = 1bps)
    mark_price: float
    index_price: float
    next_funding_time: Optional[datetime]
    timestamp: datetime
    
    def get_funding_component_bps(self, horizon_hours: float = 1.0) -> float:
        """
        주어진 기간에 대한 펀딩비 성분 계산 (bps)
        
        Args:
            horizon_hours: 보유 예정 시간 (기본 1시간)
        
        Returns:
            funding_component_bps: 해당 기간의 펀딩비 성분 (bps)
        
        Note:
            - Binance Futures 펀딩비는 8시간마다 정산
            - SHORT 포지션: funding_rate > 0이면 수취, < 0이면 지급
            - 보수적 계산: SHORT 기준으로 최악의 경우를 가정
        """
        funding_periods = horizon_hours / 8.0
        return self.funding_rate_bps * funding_periods


class FundingRateProvider:
    """
    Binance Futures 펀딩비 Provider
    
    기능:
    - Premium Index API에서 펀딩비/마크가격/인덱스가격 조회
    - funding_adjusted_edge_bps 계산 지원
    
    사용법:
        provider = FundingRateProvider()
        info = provider.get_funding_rate("BTCUSDT")
        funding_component = info.get_funding_component_bps(horizon_hours=1.0)
    """
    
    BINANCE_FUTURES_BASE_URL = "https://fapi.binance.com"
    PREMIUM_INDEX_ENDPOINT = "/fapi/v1/premiumIndex"
    
    def __init__(self, timeout: float = 10.0):
        """
        Args:
            timeout: API 요청 타임아웃 (초)
        """
        self.timeout = timeout
        self._session = None
        logger.info("[D205-15-3_FUNDING] FundingRateProvider initialized")
    
    def _get_session(self):
        """Lazy session initialization"""
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "Accept": "application/json",
            })
        return self._session
    
    def get_funding_rate(self, symbol: str) -> Optional[FundingRateInfo]:
        """
        특정 심볼의 펀딩비 정보 조회
        
        Args:
            symbol: Binance Futures 심볼 (예: "BTCUSDT")
        
        Returns:
            FundingRateInfo 또는 None (실패 시)
        """
        try:
            session = self._get_session()
            url = f"{self.BINANCE_FUTURES_BASE_URL}{self.PREMIUM_INDEX_ENDPOINT}"
            params = {"symbol": symbol}
            
            response = session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            return self._parse_premium_index(data)
            
        except Exception as e:
            logger.error(f"[D205-15-3_FUNDING] Failed to get funding rate for {symbol}: {e}")
            return None
    
    def get_all_funding_rates(self) -> List[FundingRateInfo]:
        """
        전체 심볼의 펀딩비 정보 조회
        
        Returns:
            FundingRateInfo 리스트
        """
        try:
            session = self._get_session()
            url = f"{self.BINANCE_FUTURES_BASE_URL}{self.PREMIUM_INDEX_ENDPOINT}"
            
            response = session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data_list = response.json()
            results = []
            
            for data in data_list:
                info = self._parse_premium_index(data)
                if info:
                    results.append(info)
            
            logger.info(f"[D205-15-3_FUNDING] Fetched {len(results)} funding rates")
            return results
            
        except Exception as e:
            logger.error(f"[D205-15-3_FUNDING] Failed to get all funding rates: {e}")
            return []
    
    def _parse_premium_index(self, data: Dict[str, Any]) -> Optional[FundingRateInfo]:
        """Premium Index API 응답 파싱"""
        try:
            funding_rate = float(data.get("lastFundingRate", 0))
            funding_rate_bps = funding_rate * 10000  # 비율 → bps 변환
            
            next_funding_time = None
            if "nextFundingTime" in data and data["nextFundingTime"]:
                next_funding_time = datetime.fromtimestamp(
                    data["nextFundingTime"] / 1000, tz=timezone.utc
                )
            
            return FundingRateInfo(
                symbol=data.get("symbol", ""),
                funding_rate=funding_rate,
                funding_rate_bps=funding_rate_bps,
                mark_price=float(data.get("markPrice", 0)),
                index_price=float(data.get("indexPrice", 0)),
                next_funding_time=next_funding_time,
                timestamp=datetime.now(timezone.utc),
            )
            
        except Exception as e:
            logger.error(f"[D205-15-3_FUNDING] Parse error: {e}, data: {data}")
            return None
    
    def calculate_funding_adjusted_edge(
        self,
        net_edge_bps: float,
        funding_info: FundingRateInfo,
        horizon_hours: float = 1.0,
        is_short: bool = True,
    ) -> Dict[str, float]:
        """
        펀딩비 조정 Edge 계산
        
        Args:
            net_edge_bps: 기존 net_edge (비용 차감 후)
            funding_info: 펀딩비 정보
            horizon_hours: 예상 보유 시간 (시간)
            is_short: SHORT 포지션 여부 (기본 True)
        
        Returns:
            Dict with funding_component_bps, funding_adjusted_edge_bps
        
        Note:
            - SHORT 포지션: funding_rate > 0이면 펀딩비 수취 (edge 증가)
            - SHORT 포지션: funding_rate < 0이면 펀딩비 지급 (edge 감소)
            - 보수적 계산: 항상 최악의 경우를 가정 (펀딩비를 비용으로 차감)
        """
        funding_component_bps = funding_info.get_funding_component_bps(horizon_hours)
        
        if is_short:
            adjusted_edge_bps = net_edge_bps - abs(funding_component_bps)
        else:
            adjusted_edge_bps = net_edge_bps - abs(funding_component_bps)
        
        return {
            "net_edge_bps": round(net_edge_bps, 4),
            "funding_rate_bps": round(funding_info.funding_rate_bps, 4),
            "funding_component_bps": round(funding_component_bps, 4),
            "funding_adjusted_edge_bps": round(adjusted_edge_bps, 4),
            "horizon_hours": horizon_hours,
            "calculation_note": "conservative: funding always subtracted as cost",
        }


def get_funding_rates_for_symbols(symbols: List[str]) -> Dict[str, FundingRateInfo]:
    """
    여러 심볼의 펀딩비를 한번에 조회 (효율적인 bulk fetch)
    
    Args:
        symbols: Binance Futures 심볼 리스트 (예: ["BTCUSDT", "ETHUSDT"])
    
    Returns:
        {symbol: FundingRateInfo} 딕셔너리
    """
    provider = FundingRateProvider()
    all_rates = provider.get_all_funding_rates()
    
    symbol_set = set(symbols)
    return {
        info.symbol: info
        for info in all_rates
        if info.symbol in symbol_set
    }
