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
