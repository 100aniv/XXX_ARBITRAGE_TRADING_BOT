"""
D205-15-2: Universe Builder Module

V2 엔진용 심볼 Universe 생성 모듈.
TopNProvider(V1)를 재사용하여 config 기반 Universe 생성.
"""

from .builder import UniverseBuilder

__all__ = ["UniverseBuilder"]
