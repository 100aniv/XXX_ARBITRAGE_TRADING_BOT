"""
D205-8: Quote Normalizer v1

KRW/USDT 단위 불일치 해결을 위한 정규화 엔진

목표:
- USDT → KRW 변환 (명시적)
- SanityGuard (단위 불일치 감지)
- 모든 가격/노셔널을 KRW 단위로 정규화 후 spread/edge 계산

비범위:
- FX 실시간 수집 인프라 (API, 캐싱, DB 저장) - 후순위
- 고정값(1450) 또는 CLI 주입으로 충분

SSOT: docs/v2/design/D205_PROFIT_LOOP_PATCHPLAN.md
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# 기본 FX rate (USDT → KRW)
DEFAULT_FX_KRW_PER_USDT = 1450.0

# SanityGuard 임계값 (bps)
UNITS_MISMATCH_THRESHOLD_BPS = 100000.0


def normalize_price_to_krw(
    price: float,
    quote: str,
    fx_krw_per_usdt: float = DEFAULT_FX_KRW_PER_USDT,
) -> float:
    """
    가격을 KRW로 정규화
    
    Args:
        price: 원본 가격
        quote: Quote currency ("KRW", "USDT" 등)
        fx_krw_per_usdt: USDT → KRW 환율 (기본값 1450)
    
    Returns:
        KRW로 정규화된 가격
    
    Raises:
        ValueError: 지원하지 않는 quote currency
    
    Examples:
        >>> normalize_price_to_krw(100000, "KRW")
        100000.0
        >>> normalize_price_to_krw(100, "USDT", 1300)
        130000.0
    """
    quote_upper = quote.upper()
    
    if quote_upper == "KRW":
        return price
    elif quote_upper == "USDT":
        return price * fx_krw_per_usdt
    else:
        raise ValueError(f"[D205-8_QUOTE_NORMALIZER] Unsupported quote currency: {quote}")


def normalize_notional_to_krw(
    notional: float,
    quote: str,
    fx_krw_per_usdt: float = DEFAULT_FX_KRW_PER_USDT,
) -> float:
    """
    노셔널(거래 금액)을 KRW로 정규화
    
    Args:
        notional: 원본 노셔널
        quote: Quote currency ("KRW", "USDT" 등)
        fx_krw_per_usdt: USDT → KRW 환율 (기본값 1450)
    
    Returns:
        KRW로 정규화된 노셔널
    
    Examples:
        >>> normalize_notional_to_krw(100000, "KRW")
        100000.0
        >>> normalize_notional_to_krw(100, "USDT", 1300)
        130000.0
    """
    return normalize_price_to_krw(notional, quote, fx_krw_per_usdt)


def is_units_mismatch(
    spread_bps: float,
    edge_bps: float,
    threshold: float = UNITS_MISMATCH_THRESHOLD_BPS,
) -> bool:
    """
    단위 불일치 의심 감지 (SanityGuard)
    
    Args:
        spread_bps: 스프레드 (bps)
        edge_bps: 엣지 (bps)
        threshold: 임계값 (bps, 기본값 100000)
    
    Returns:
        True if 단위 불일치 의심 (spread 또는 edge가 임계값 초과)
    
    Logic:
        - abs(spread_bps) > threshold or abs(edge_bps) > threshold
        - 정상 범위: 수백~수천 bps
        - 비정상: 수십만~수백만 bps (KRW/USDT 단위 혼재 의심)
    
    Examples:
        >>> is_units_mismatch(1000, 500)  # 정상
        False
        >>> is_units_mismatch(150000, 145000)  # 비정상 (단위 혼재 의심)
        True
    """
    return abs(spread_bps) > threshold or abs(edge_bps) > threshold


def get_quote_mode(
    exchange_a: str,
    exchange_b: str,
    fx_krw_per_usdt: Optional[float] = None,
) -> str:
    """
    Quote mode 문자열 생성 (기록용)
    
    Args:
        exchange_a: 거래소 A 이름 (예: "upbit")
        exchange_b: 거래소 B 이름 (예: "binance")
        fx_krw_per_usdt: FX rate (None이면 기본값 사용)
    
    Returns:
        Quote mode 문자열 (예: "KRW", "USDT->KRW@1450.0")
    
    Examples:
        >>> get_quote_mode("upbit", "binance", 1300)
        "USDT->KRW@1300.0"
        >>> get_quote_mode("upbit", "upbit")
        "KRW"
    """
    # 간단한 휴리스틱: binance가 있으면 USDT->KRW
    if "binance" in exchange_b.lower() or "binance" in exchange_a.lower():
        fx_used = fx_krw_per_usdt if fx_krw_per_usdt is not None else DEFAULT_FX_KRW_PER_USDT
        return f"USDT->KRW@{fx_used}"
    else:
        return "KRW"
