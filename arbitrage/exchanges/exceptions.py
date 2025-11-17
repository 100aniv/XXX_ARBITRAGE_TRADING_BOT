# -*- coding: utf-8 -*-
"""
D42 Exchange Adapter Layer - Exceptions

거래소 어댑터 관련 예외 정의.
"""


class ExchangeError(Exception):
    """거래소 관련 기본 예외"""
    pass


class NetworkError(ExchangeError):
    """네트워크 관련 예외"""
    pass


class AuthenticationError(ExchangeError):
    """인증 관련 예외 (API 키 오류 등)"""
    pass


class InsufficientBalanceError(ExchangeError):
    """잔고 부족 예외"""
    pass


class OrderError(ExchangeError):
    """주문 관련 예외"""
    pass


class OrderNotFoundError(OrderError):
    """주문을 찾을 수 없음"""
    pass


class InvalidOrderError(OrderError):
    """유효하지 않은 주문"""
    pass


class SymbolNotFoundError(ExchangeError):
    """거래 쌍을 찾을 수 없음"""
    pass
