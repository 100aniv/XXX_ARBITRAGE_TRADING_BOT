"""
D205-18-4: Price Normalizer (복원)

Purpose: USD/KRW 환율 기반 가격 정규화
"""

def normalize_price_to_krw(price_usd: float, exchange_rate: float = 1300.0) -> float:
    """
    USD 가격을 KRW로 정규화
    
    Args:
        price_usd: USD 가격
        exchange_rate: USD/KRW 환율 (기본값 1300)
    
    Returns:
        KRW 가격
    """
    return price_usd * exchange_rate
