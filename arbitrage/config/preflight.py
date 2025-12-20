"""
D98-5: Preflight 관련 예외 및 유틸리티

Preflight Real-Check 실패 시 발생하는 예외 클래스.
"""


class PreflightError(Exception):
    """Preflight 검증 실패 예외 (Fail-Closed)"""
    pass
