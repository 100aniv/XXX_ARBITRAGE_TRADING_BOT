"""
D205-18-4: FX Provider (복원)

Purpose: USD/KRW 환율 제공
"""

class FXProvider:
    """환율 제공자"""
    
    def __init__(self, default_krw_per_usdt: float = 1450.0):
        self.default_krw_per_usdt = default_krw_per_usdt
    
    def get_krw_per_usdt(self) -> float:
        """USD/KRW 환율 반환"""
        return self.default_krw_per_usdt
    
    def get_rate(self, from_currency: str, to_currency: str) -> float:
        """D205-18-4-FIX: 범용 get_rate() 메서드 (opportunity_source 호환)"""
        if from_currency == "USDT" and to_currency == "KRW":
            return self.default_krw_per_usdt
        elif from_currency == "KRW" and to_currency == "USDT":
            return 1.0 / self.default_krw_per_usdt
        else:
            raise ValueError(f"Unsupported currency pair: {from_currency}/{to_currency}")
