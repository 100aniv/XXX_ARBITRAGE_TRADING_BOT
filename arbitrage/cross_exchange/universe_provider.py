# -*- coding: utf-8 -*-
"""
D79: Cross-Exchange Universe Provider

Upbit ↔ Binance 교차 거래소 유니버스 제공자.

Features:
- 양쪽 거래소에 존재하는 심볼 필터링
- 유동성 기반 필터링
- TopN 심볼 선택
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from arbitrage.common.currency import Currency

logger = logging.getLogger(__name__)


@dataclass
class CrossSymbol:
    """
    교차 거래소 심볼 정보
    
    D80-2: base_currency 추가
    """
    mapping: any  # SymbolMapping
    upbit_volume_24h: float  # Upbit 24h 거래량 (KRW)
    binance_volume_24h: float  # Binance 24h 거래량 (USDT)
    combined_score: float  # 종합 점수 (유동성 기준)
    base_currency: Currency = Currency.KRW  # D80-2: 기본 통화 (Upbit=KRW)


class CrossExchangeUniverseProvider:
    """
    교차 거래소 유니버스 제공자
    
    양쪽 거래소에 모두 존재하고 유동성이 충분한 심볼을 선택한다.
    
    Example:
        provider = CrossExchangeUniverseProvider(
            symbol_mapper=mapper,
            upbit_client=upbit_client,
            binance_client=binance_client,
        )
        
        symbols = provider.get_top_symbols(top_n=50)
        # [CrossSymbol(mapping=..., ...), ...]
    """
    
    MIN_UPBIT_VOLUME_KRW = 100_000_000.0  # 최소 Upbit 거래량 (100M KRW)
    MIN_BINANCE_VOLUME_USDT = 100_000.0  # 최소 Binance 거래량 (100K USDT)
    
    def __init__(
        self,
        symbol_mapper,
        upbit_client,
        binance_client,
        fx_converter=None,
    ):
        """
        Initialize CrossExchangeUniverseProvider
        
        Args:
            symbol_mapper: SymbolMapper instance
            upbit_client: Upbit public data client
            binance_client: Binance public data client
            fx_converter: FXConverter instance (optional, for volume conversion)
        """
        self.symbol_mapper = symbol_mapper
        self.upbit_client = upbit_client
        self.binance_client = binance_client
        self.fx_converter = fx_converter
        
        logger.info("[CROSS_UNIVERSE] Initialized")
    
    def get_top_symbols(
        self,
        top_n: int = 50,
        min_upbit_volume_krw: Optional[float] = None,
        min_binance_volume_usdt: Optional[float] = None,
    ) -> List[CrossSymbol]:
        """
        Top N 교차 거래소 심볼 조회
        
        Args:
            top_n: 개수
            min_upbit_volume_krw: 최소 Upbit 거래량 (KRW)
            min_binance_volume_usdt: 최소 Binance 거래량 (USDT)
        
        Returns:
            List[CrossSymbol] (종합 점수 기준 정렬)
        
        Logic:
            1. Upbit KRW 마켓 심볼 조회
            2. 각 심볼을 Binance로 매핑
            3. 양쪽 거래소 볼륨 조회
            4. 유동성 필터링
            5. 종합 점수 계산 및 정렬
            6. Top N 반환
        """
        if min_upbit_volume_krw is None:
            min_upbit_volume_krw = self.MIN_UPBIT_VOLUME_KRW
        
        if min_binance_volume_usdt is None:
            min_binance_volume_usdt = self.MIN_BINANCE_VOLUME_USDT
        
        logger.info(
            f"[CROSS_UNIVERSE] Fetching Top{top_n} cross-exchange symbols "
            f"(min_upbit: {min_upbit_volume_krw:,.0f} KRW, "
            f"min_binance: {min_binance_volume_usdt:,.0f} USDT)"
        )
        
        # 1. Upbit KRW 마켓 심볼 조회 (거래량 기준)
        upbit_symbols = self.upbit_client.fetch_top_symbols(
            market="KRW",
            limit=200,  # 넉넉하게 조회
            sort_by="acc_trade_price_24h",
        )
        
        if not upbit_symbols:
            logger.warning("[CROSS_UNIVERSE] No Upbit symbols fetched")
            return []
        
        logger.info(f"[CROSS_UNIVERSE] Fetched {len(upbit_symbols)} Upbit symbols")
        
        # 2. 매핑 및 필터링
        cross_symbols: List[CrossSymbol] = []
        
        for upbit_symbol in upbit_symbols:
            # 2-1. Upbit → Binance 매핑
            mapping = self.symbol_mapper.map_upbit_to_binance(upbit_symbol)
            
            if not mapping:
                logger.debug(f"[CROSS_UNIVERSE] Failed to map: {upbit_symbol}")
                continue
            
            # 2-2. 양쪽 거래소 티커 조회
            upbit_ticker = self.upbit_client.fetch_ticker(upbit_symbol)
            binance_ticker = self.binance_client.fetch_ticker(mapping.binance_symbol)
            
            if not upbit_ticker or not binance_ticker:
                logger.debug(f"[CROSS_UNIVERSE] Failed to fetch tickers for {upbit_symbol}")
                continue
            
            # 2-3. 볼륨 확인
            upbit_volume_krw = upbit_ticker.acc_trade_price_24h  # 24h 거래대금 (KRW)
            binance_volume_usdt = binance_ticker.quote_volume_24h  # 24h 거래대금 (USDT)
            
            # 2-4. 유동성 필터링
            if upbit_volume_krw < min_upbit_volume_krw:
                logger.debug(
                    f"[CROSS_UNIVERSE] Low Upbit volume: {upbit_symbol} "
                    f"({upbit_volume_krw:,.0f} KRW)"
                )
                continue
            
            if binance_volume_usdt < min_binance_volume_usdt:
                logger.debug(
                    f"[CROSS_UNIVERSE] Low Binance volume: {mapping.binance_symbol} "
                    f"({binance_volume_usdt:,.0f} USDT)"
                )
                continue
            
            # 2-5. 종합 점수 계산
            combined_score = self._calculate_combined_score(
                upbit_volume_krw, binance_volume_usdt
            )
            
            # 2-6. CrossSymbol 생성
            cross_symbol = CrossSymbol(
                mapping=mapping,
                upbit_volume_24h=upbit_volume_krw,
                binance_volume_24h=binance_volume_usdt,
                combined_score=combined_score,
                base_currency=Currency.KRW,  # D80-2: Upbit KRW 마켓
            )
            
            cross_symbols.append(cross_symbol)
        
        if not cross_symbols:
            logger.warning("[CROSS_UNIVERSE] No cross-exchange symbols after filtering")
            return []
        
        # 3. 종합 점수 기준 정렬
        cross_symbols.sort(key=lambda x: x.combined_score, reverse=True)
        
        # 4. Top N 반환
        top_symbols = cross_symbols[:top_n]
        
        logger.info(
            f"[CROSS_UNIVERSE] Selected {len(top_symbols)} cross-exchange symbols. "
            f"Top 5: {[s.mapping.upbit_symbol for s in top_symbols[:5]]}"
        )
        
        return top_symbols
    
    def _calculate_combined_score(
        self,
        upbit_volume_krw: float,
        binance_volume_usdt: float,
    ) -> float:
        """
        종합 점수 계산
        
        Args:
            upbit_volume_krw: Upbit 거래량 (KRW)
            binance_volume_usdt: Binance 거래량 (USDT)
        
        Returns:
            종합 점수 (높을수록 좋음)
        
        Logic:
            - Weighted average of volumes
            - Binance volume은 KRW로 변환하여 동일 단위로 계산
            - Weight: Upbit 60%, Binance 40% (Upbit이 주 마켓)
        """
        # Binance volume을 KRW로 변환 (FX converter 있으면 사용, 없으면 고정 환율)
        if self.fx_converter:
            fx_rate = self.fx_converter.get_fx_rate().rate
        else:
            fx_rate = 1300.0  # Fallback
        
        binance_volume_krw = binance_volume_usdt * fx_rate
        
        # Weighted average (Upbit 60%, Binance 40%)
        combined_score = (upbit_volume_krw * 0.6) + (binance_volume_krw * 0.4)
        
        return combined_score
    
    def get_mapping_stats(self) -> Dict[str, any]:
        """
        매핑 통계 반환
        
        Returns:
            SymbolMapper의 통계
        """
        return self.symbol_mapper.get_mapping_stats()
